import os
import re

from starlette import status
from starlette.exceptions import HTTPException
from starlette.middleware.gzip import GZipResponder
from starlette.responses import FileResponse
from starlette.staticfiles import StaticFiles

from alasio.ext.starapi.param import HTTPExceptionJson
from alasio.logger import logger

# Fallback Content-Security-Policy for html responses without a CSP meta
# (the served page normally carries its own meta, kept in sync with the
# inline scripts by the build-time csp-inline-hash plugin; the response
# header then mirrors that meta so the browser enforces their
# intersection). frame-ancestors can only be set through a response
# header (the meta tag ignores it): it allows the electron host
# (app://bundle, production) and local loopback dev hosts (vite dev
# server, any port) to embed the page.
CSP = (
    "default-src 'self'; "
    "script-src 'self' 'sha256-/c574zxOUzzzs52yM/ATmZ7eBGoJ3nHgHTc8O5t7jRw='; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; "
    "connect-src 'self' ws: wss:; "
    "font-src 'self' data:; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "frame-src 'self'; "
    "frame-ancestors 'self' app://bundle http://127.0.0.1:* http://localhost:*"
)


# Inline script hashes are recomputed on every build (the sveltekit
# bootstrap script embeds build hashes), so the response header must
# follow the page's own meta instead of a hard-coded list.
#
# meta csp cache: file_path -> (mtime, size, csp). FileResponse streams
# the file again when the response is sent, so caching the meta
# extraction avoids reading the file twice per request; the mtime/size
# from the response's own stat_result keep the cache valid across
# rebuilds without an extra os.stat.
_CSP_CACHE = {}


def _html_meta_csp(file_path, stat_result):
    """
    Extract the Content-Security-Policy meta of an html file, or ''.

    The build-time csp-inline-hash plugin keeps the meta in sync with the
    inline scripts (both hash algorithms for every inline script), so
    serving the meta as the response header keeps the two identical
    (the browser enforces their intersection).

    Args:
        file_path (str): Path of the html file being served
        stat_result (os.stat_result): Stat of the file, used as the cache
            validity key (mtime + size) so unchanged files are not read
            again

    Returns:
        str: The meta CSP content, or '' when absent / unreadable
    """
    cached = _CSP_CACHE.get(file_path)
    if cached is not None and cached[0] == stat_result.st_mtime and cached[1] == stat_result.st_size:
        return cached[2]
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except OSError:
        return ''
    match = re.search(
        r'<meta[^>]*http-equiv="Content-Security-Policy"[^>]*content="([^"]*)"',
        content, re.IGNORECASE)
    csp = match.group(1).strip() if match else ''
    _CSP_CACHE[file_path] = (stat_result.st_mtime, stat_result.st_size, csp)
    return csp


class NoCacheStaticFiles(StaticFiles):
    """
    Static file server with no-cache headers (and an optional CSP hook).

    Subclasses:
    - ImageStaticFiles: mod dev assets, image-only
    - SPANoCacheStaticFiles: frontend page server, SPA fallback + CSP
    """

    def _csp_for(self, full_path, media_type, stat_result):
        """
        Hook: return the Content-Security-Policy header value for a
        response, or '' when the response needs none. Defaults to no CSP
        (images need none); SPANoCacheStaticFiles overrides this for html
        pages.

        Args:
            full_path (str): Path of the served file
            media_type (str | None): Response media type
            stat_result (os.stat_result): Stat of the served file, unused
                here but part of the hook signature

        Returns:
            str: CSP value, or '' for none
        """
        return ''

    def file_response(self, full_path, stat_result, scope, status_code=status.HTTP_200_OK):
        resp = super().file_response(full_path, stat_result, scope, status_code)
        if not isinstance(resp, FileResponse):
            # return NotModifiedResponse directly
            return resp

        # No cache for static files
        # We've seen too many styling issues in ALAS. We use electron as client and chromium caches static files on
        # user's disk. Those files may get broke for unknown reason, causing the styling issues.
        # To fix that, we tell the browsers don't cache any. Bandwidth increase should be acceptable on local service.
        resp.headers.setdefault('Cache-Control', 'no-cache, no-store, private, must-revalidate, max-age=0')
        resp.headers.setdefault('Expires', '0')
        resp.headers.setdefault('Pragma', 'no-cache')

        # CSP (hook): only the frontend page server attaches one
        csp = self._csp_for(full_path, resp.media_type, stat_result)
        if csp:
            resp.headers.setdefault('Content-Security-Policy', csp)

        # GZipMiddleware
        resp = GZipResponder(resp, minimum_size=500, compresslevel=9)

        return resp

    @classmethod
    def mount(
            cls,
            router,
            path,
            name: "str | None" = None,
            directory: "PathLike | None " = None,
            packages: "list[str | tuple[str, str]] | None" = None,
            html: bool = False,
            check_dir: bool = True,
            follow_symlink: bool = False,
    ):
        """
        Safely mount a directory to router or app
        """
        try:
            app = cls(directory=directory, packages=packages, html=html,
                      check_dir=check_dir, follow_symlink=follow_symlink)
        except RuntimeError as e:
            logger.error(f'Mount static files failed: {e}')
            return
        router.mount(path, app, name=name)


class ImageStaticFiles(NoCacheStaticFiles):
    """
    Static file server for mod dev assets: image-only.

    Only image files are served; any other content is rejected with 403
    (a mod asset directory must never serve executable content, e.g. an
    html file that would run without a CSP). No CSP is attached here:
    images do not need one.
    """

    # image whitelist; svg is deliberately absent (svg can embed scripts)
    IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp'}

    async def get_response(self, path, scope):
        """
        Reject non-image content outright.

        Args:
            path (str): The request path
            scope (Scope):

        Raises:
            HTTPExceptionJson: 403 when the file is not an image
        """
        suffix = os.path.splitext(path)[1].lower()
        if suffix not in self.IMAGE_EXTENSIONS:
            raise HTTPExceptionJson(status.HTTP_403_FORBIDDEN, err='ASSETS_IMAGE_ONLY')
        return await super().get_response(path, scope)


class SPAStaticFiles(StaticFiles):
    """
    Subclass StaticFiles to serve index.html for any path that doesn't match a file.
    This is the key to letting a client-side router handle routes.
    """

    async def get_response(self, path, scope):
        try:
            # Try to get the file from the parent class
            return await super().get_response(path, scope)
        except HTTPException as e:
            # If the file is not found (404), serve index.html
            if e.status_code == status.HTTP_404_NOT_FOUND:
                # Important: we need to serve index.html from the root path
                return await super().get_response('index.html', scope)
            # Re-raise any other exceptions
            raise e


class SPANoCacheStaticFiles(SPAStaticFiles, NoCacheStaticFiles):
    """Frontend page server: no-cache + SPA fallback + CSP."""

    def _csp_for(self, full_path, media_type, stat_result):
        """
        CSP for html pages: mirror the page's own meta CSP (kept in sync
        with the inline scripts by the build-time csp-inline-hash
        plugin), extended with frame-ancestors which the meta tag
        ignores. Fall back to the static CSP when the page has no meta.

        Args:
            full_path (str): Path of the served file
            media_type (str | None): Response media type
            stat_result (os.stat_result): Stat of the served file, passed
                to the meta extraction as its cache validity key

        Returns:
            str: CSP value, or '' for non-html responses
        """
        if media_type != 'text/html':
            return ''
        csp = _html_meta_csp(full_path, stat_result)
        if csp:
            if 'frame-ancestors' not in csp:
                csp = f"{csp}; frame-ancestors 'self' app://bundle http://127.0.0.1:* http://localhost:*"
            return csp
        return CSP
