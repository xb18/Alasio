import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { rewriteCspMeta } from "./vite";

/**
 * Post-build CSP fix: rewrite the script-src hashes of the built
 * renderer index.html so they cover every inline script (including the
 * sveltekit bootstrap script, whose content changes on every build).
 *
 * SvelteKit generates index.html in its own build pipeline (adapter
 * output), outside vite's transformIndexHtml, so the dev-mode plugin
 * middleware cannot help here. Run after `vite build` and before
 * packing (see package.json build script).
 */
const root = fileURLToPath(new URL("../..", import.meta.url));
const indexHtml = `${root}dist/renderer/index.html`;

const html = readFileSync(indexHtml, "utf8");
const patched = rewriteCspMeta(html);
if (patched !== html) {
  writeFileSync(indexHtml, patched, "utf8");
  console.log(`[csp-fix] updated ${indexHtml}`);
} else {
  console.log(`[csp-fix] no change for ${indexHtml}`);
}
