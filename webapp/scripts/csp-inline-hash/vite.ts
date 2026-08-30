import { createHash } from "node:crypto";
import type { ServerResponse } from "node:http";
import type { Connect, Plugin } from "vite";

/**
 * Compute the CSP sha256 hashes of one inline script.
 *
 * Two algorithms are emitted for the same content because the hash
 * algorithm differed across browsers:
 * - raw textContent (older Chromium, e.g. Electron 22 / Chromium 108);
 * - textContent with leading/trailing ASCII whitespace stripped (CSP3,
 *   modern Chrome / Firefox / Safari).
 * A browser only matches the hash its own algorithm produces, and the
 * directive accepts both (multiple hash sources are OR-ed).
 */
export function scriptHashes(content: string): string[] {
  const hashes = new Set<string>();
  const stripped = content.replace(/^[\t\n\f\r ]+|[\t\n\f\r ]+$/g, "");
  for (const text of [content, stripped]) {
    hashes.add(`'sha256-${createHash("sha256").update(text, "utf8").digest("base64")}'`);
  }
  return [...hashes];
}

/**
 * Rewrite the script-src hashes of the CSP meta in an html document so
 * they cover every inline script with both hash algorithms. Returns the
 * original html unchanged when there is nothing to do (no inline
 * scripts or no CSP meta).
 */
export function rewriteCspMeta(html: string): string {
  const inlineScripts: string[] = [];
  const scriptRe = /<script\b([^>]*)>([\s\S]*?)<\/script>/gi;
  let match: RegExpExecArray | null;
  while ((match = scriptRe.exec(html))) {
    const attrs = match[1] ?? "";
    if (!/\bsrc\s*=/.test(attrs)) {
      inlineScripts.push(match[2]);
    }
  }
  if (!inlineScripts.length) return html;
  const hashes = inlineScripts.flatMap(scriptHashes);
  // Replace the hash list of the script-src directive in the CSP meta
  // (keep 'self', drop stale hashes). vite formats the meta over
  // multiple lines, so whitespace between the attributes is tolerated.
  return html.replace(
    /(Content-Security-Policy"\s+content="[^"]*script-src\s+'self')([^;]*)(;)/,
    (_all, prefix: string, _old: string, suffix: string) => `${prefix} ${hashes.join(" ")}${suffix}`,
  );
}

/**
 * Rewrite the CSP meta of a dev server html response.
 *
 * SvelteKit injects its `__sveltekit_dev` bootstrap script in its own
 * dev middleware and serves the html directly (no transformIndexHtml
 * involved), so the only way to keep the CSP meta in sync is to
 * intercept the response before sveltekit's middleware runs (this
 * plugin is registered with enforce: 'pre') and rewrite the body once
 * it is complete.
 *
 * writeHead is deferred so the Content-Length can be fixed when the
 * rewritten body has a different size.
 */
export function cspInlineHashDev(): Plugin {
  return {
    name: "csp-inline-hash-dev",
    enforce: "pre",
    configureServer(server) {
      server.middlewares.use((req: Connect.IncomingMessage, res: ServerResponse, next: Connect.NextFunction) => {
        const accept = req.headers.accept ?? "";
        if (!req.url || !accept.includes("text/html")) {
          next();
          return;
        }
        const chunks: Buffer[] = [];
        let pendingStatus = 200;
        let pendingHeaders: Record<string, any> | undefined;
        let writeHeadCalled = false;
        const originalWriteHead = res.writeHead.bind(res);
        const originalEnd = res.end.bind(res);
        res.writeHead = ((status?: number, headers?: any) => {
          writeHeadCalled = true;
          pendingStatus = status ?? 200;
          if (headers !== undefined) {
            pendingHeaders = { ...(pendingHeaders ?? {}), ...headers };
          }
          return res;
        }) as any;
        res.write = ((chunk: any) => {
          chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
          return true;
        }) as any;
        res.end = ((chunk?: any) => {
          if (chunk !== undefined && chunk !== null) {
            chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
          }
          const body = Buffer.concat(chunks).toString("utf8");
          const patched = rewriteCspMeta(body);
          if (writeHeadCalled) {
            if (patched !== body) {
              // the rewritten body has a different size; drop the stale
              // Content-Length so node falls back to chunked encoding
              res.removeHeader("content-length");
            }
            originalWriteHead(pendingStatus, pendingHeaders);
            originalEnd(patched !== body ? patched : Buffer.concat(chunks));
          } else {
            if (patched !== body) {
              res.setHeader("Content-Length", Buffer.byteLength(patched, "utf8"));
            }
            originalEnd(patched !== body ? patched : Buffer.concat(chunks));
          }
          return res;
        }) as any;
        next();
      });
    },
  };
}
