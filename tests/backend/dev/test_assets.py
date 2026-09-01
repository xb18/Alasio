"""
Tests for the static asset servers (alasio/backend/dev/assets.py).

- ImageStaticFiles (mod dev assets): no-cache + image-only — non-image
  content is rejected with 403, no CSP is attached.
- SPANoCacheStaticFiles (frontend page server): no-cache + SPA fallback +
  CSP (mirrored from the page's meta, extended with frame-ancestors).
"""

import os as os_module

import pytest
from starlette.exceptions import HTTPException

from alasio.backend.dev.assets import CSP, ImageStaticFiles, SPANoCacheStaticFiles
from alasio.testing.filesystem import fs  # noqa: F401

HTML_WITH_META_CSP = """<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta http-equiv="Content-Security-Policy"
          content="default-src 'self'; script-src 'self' 'sha256-abc='; style-src 'self' 'unsafe-inline'" />
  </head>
  <body>hi</body>
</html>
"""

HTML_NO_META = """<!doctype html><html><head><title>x</title></head><body>hi</body></html>"""


@pytest.fixture(autouse=True)
def align_commonpath(monkeypatch):
    """
    The filesystem mock's realpath returns forward slashes while the
    real os.path.commonpath returns backslashes on Windows; starlette's
    StaticFiles path containment check then mismatches inside the mock.
    Align commonpath with the mock's separator style.
    """
    real_commonpath = os_module.path.commonpath

    def commonpath(paths):
        return real_commonpath(paths).replace('\\', '/')

    monkeypatch.setattr(os_module.path, 'commonpath', commonpath)


def make_scope(path):
    """
    Build a minimal http scope for StaticFiles.get_response.

    Args:
        path (str): The request path

    Returns:
        Scope:
    """
    return {
        'type': 'http',
        'method': 'GET',
        'path': path,
        'headers': [],
        'query_string': b'',
        'scheme': 'http',
        'server': ('127.0.0.1', 22267),
        'client': ('127.0.0.1', 123),
        'root_path': '',
    }


async def run_response(resp, scope):
    """
    Run a static response through the ASGI pipeline (the dev assets
    server wraps FileResponse in GZipResponder, a plain ASGI wrapper
    without status_code / headers attributes) and collect the response
    start message.

    Args:
        resp: The response object returned by StaticFiles.get_response
        scope (Scope):

    Returns:
        tuple[int, dict[str, str]]: (status code, headers)
    """
    messages = []

    async def receive():
        return {'type': 'http.request', 'body': b'', 'more_body': False}

    async def send(message):
        messages.append(message)

    await resp(scope, receive, send)
    start = next(message for message in messages if message['type'] == 'http.response.start')
    headers = {key.decode('latin-1'): value.decode('latin-1') for key, value in start['headers']}
    return start['status'], headers


class TestDevAssetsImageOnly:
    """ImageStaticFiles serves only images, no CSP."""

    @pytest.mark.parametrize('name', ['a.png', 'b.jpg', 'c.jpeg', 'd.gif', 'e.webp', 'f.bmp'])
    @pytest.mark.trio
    async def test_image_served(self, fs, name):
        fs.create_file(f'/assets/{name}', contents=b'img-data')
        app = ImageStaticFiles(directory='/assets', check_dir=False)
        resp = await app.get_response(name, make_scope(f'/{name}'))
        status, headers = await run_response(resp, make_scope(f'/{name}'))
        assert status == 200
        # no CSP on image responses
        assert 'content-security-policy' not in headers

    @pytest.mark.parametrize('name', ['a.json', 'b.py', 'c.html', 'd.svg', 'e.js', 'f.txt', 'g'])
    @pytest.mark.trio
    async def test_non_image_rejected(self, fs, name):
        fs.create_file(f'/assets/{name}', contents=b'x')
        app = ImageStaticFiles(directory='/assets', check_dir=False)
        with pytest.raises(HTTPException) as excinfo:
            await app.get_response(name, make_scope(f'/{name}'))
        assert excinfo.value.status_code == 403

    @pytest.mark.trio
    async def test_uppercase_extension_served(self, fs):
        fs.create_file('/assets/A.PNG', contents=b'img')
        app = ImageStaticFiles(directory='/assets', check_dir=False)
        resp = await app.get_response('A.PNG', make_scope('/A.PNG'))
        status, _ = await run_response(resp, make_scope('/A.PNG'))
        assert status == 200

    @pytest.mark.trio
    async def test_upload_like_html_rejected(self, fs):
        """An html file smuggled into the asset dir must never be served."""
        fs.create_file('/assets/evil.html', contents=HTML_WITH_META_CSP)
        app = ImageStaticFiles(directory='/assets', check_dir=False)
        with pytest.raises(HTTPException) as excinfo:
            await app.get_response('evil.html', make_scope('/evil.html'))
        assert excinfo.value.status_code == 403


class TestSpaPageServer:
    """SPANoCacheStaticFiles: pages carry the CSP, images/assets do not."""

    def make_app(self):
        return SPANoCacheStaticFiles(directory='/site', html=True, check_dir=False)

    @pytest.mark.trio
    async def test_html_mirrors_meta_csp(self, fs):
        fs.create_file('/site/index.html', contents=HTML_WITH_META_CSP)
        app = self.make_app()
        resp = await app.get_response('index.html', make_scope('/'))
        status, headers = await run_response(resp, make_scope('/'))
        assert status == 200
        csp = headers.get('content-security-policy', '')
        # the meta content is served verbatim ...
        assert csp.startswith("default-src 'self'; script-src 'self' 'sha256-abc='")
        # ... extended with frame-ancestors (the meta tag ignores it): the
        # electron host (production) and local loopback dev hosts
        assert "frame-ancestors 'self' app://bundle http://127.0.0.1:* http://localhost:*" in csp

    @pytest.mark.trio
    async def test_html_without_meta_uses_fallback(self, fs):
        fs.create_file('/site/index.html', contents=HTML_NO_META)
        app = self.make_app()
        resp = await app.get_response('index.html', make_scope('/'))
        _, headers = await run_response(resp, make_scope('/'))
        assert headers.get('content-security-policy', '') == CSP

    @pytest.mark.trio
    async def test_non_html_has_no_csp(self, fs):
        fs.create_file('/site/app.css', contents='body{}')
        fs.create_file('/site/app.js', contents='console.log(1)')
        fs.create_file('/site/icon.png', contents=b'png')
        app = self.make_app()
        for name in ['app.css', 'app.js', 'icon.png']:
            resp = await app.get_response(name, make_scope(f'/{name}'))
            _, headers = await run_response(resp, make_scope(f'/{name}'))
            assert headers.get('content-security-policy', '') == ''
            assert 'content-security-policy' not in headers

    @pytest.mark.trio
    async def test_spa_fallback_serves_index_with_csp(self, fs):
        fs.create_file('/site/index.html', contents=HTML_WITH_META_CSP)
        app = self.make_app()
        resp = await app.get_response('some/client/route', make_scope('/some/client/route'))
        status, headers = await run_response(resp, make_scope('/some/client/route'))
        assert status == 200
        assert 'frame-ancestors' in headers.get('content-security-policy', '')

    @pytest.mark.trio
    async def test_non_image_allowed(self, fs):
        """The frontend page server is not image-only."""
        fs.create_file('/site/asset.json', contents='{}')
        app = self.make_app()
        resp = await app.get_response('asset.json', make_scope('/asset.json'))
        status, _ = await run_response(resp, make_scope('/asset.json'))
        assert status == 200


class TestHtmlMetaCspCache:
    """Meta CSP extraction is cached; unchanged files are not re-read."""

    def make_app(self):
        return SPANoCacheStaticFiles(directory='/site', html=True, check_dir=False)

    @pytest.mark.trio
    async def test_unchanged_file_not_reread(self, fs, monkeypatch):
        """On cache hit the meta extraction must not open the file again."""
        fs.create_file('/site/index.html', contents=HTML_WITH_META_CSP)
        app = self.make_app()
        resp = await app.get_response('index.html', make_scope('/'))
        await run_response(resp, make_scope('/'))

        # count text-mode opens only: FileResponse still streams the file
        # once (mode='rb') on send, the meta extraction must not re-read it
        text_reads = []
        original_open = open

        def counting_open(file, *args, **kwargs):
            if args and args[0] == 'r':
                text_reads.append(file)
            return original_open(file, *args, **kwargs)

        monkeypatch.setattr('builtins.open', counting_open)
        resp = await app.get_response('index.html', make_scope('/'))
        await run_response(resp, make_scope('/'))
        assert text_reads == []

    @pytest.mark.trio
    async def test_cache_invalidated_on_content_change(self, fs):
        """A changed file (new size) must not serve the stale cached CSP."""
        fs.create_file('/site/index.html', contents=HTML_WITH_META_CSP)
        app = self.make_app()
        resp = await app.get_response('index.html', make_scope('/'))
        _, headers = await run_response(resp, make_scope('/'))
        assert headers.get('content-security-policy', '').startswith(
            "default-src 'self'; script-src 'self' 'sha256-abc='")

        fs.remove('/site/index.html')
        fs.create_file('/site/index.html', contents=HTML_NO_META)
        resp = await app.get_response('index.html', make_scope('/'))
        _, headers = await run_response(resp, make_scope('/'))
        assert headers.get('content-security-policy', '') == CSP
