import { defineConfig } from "vite";
import { sveltekit } from "@sveltejs/kit/vite";
import adapter from "@sveltejs/adapter-static";
import { vitePreprocess } from "@sveltejs/vite-plugin-svelte";
import tailwindcss from "@tailwindcss/vite";
import electron from "vite-plugin-electron";
import { existsSync, mkdirSync, writeFileSync } from "fs";
import { resolve } from "path";
import { fileURLToPath } from "url";
import { i18nPlugin } from "./scripts/i18n/vite.ts";
import { mainI18nConfig, rendererI18nConfig } from "./scripts/i18n/config.ts";

const __dirname = fileURLToPath(new URL(".", import.meta.url));

/**
 * svelte-kit writes ESM output (e.g. .svelte-kit/output/server/*.js) into a
 * package without "type": "module", so node reparses those files and emits
 * MODULE_TYPELESS_PACKAGE_JSON warnings. Mark the generated .svelte-kit
 * directory as ESM (it is gitignored, so ensure the marker on every build).
 */
function ensureSvelteKitEsmMarker() {
  const dir = resolve(__dirname, ".svelte-kit");
  const pkg = resolve(dir, "package.json");
  if (existsSync(pkg)) {
    return;
  }
  mkdirSync(dir, { recursive: true });
  writeFileSync(pkg, '{\n  "type": "module"\n}\n');
}

export default defineConfig({
  // i18nPlugin (renderer instance) is listed first so its config hook
  // scans renderer sources before the sveltekit build starts
  plugins: [
    i18nPlugin(rendererI18nConfig),
    // SvelteKit options are passed directly (supported since SvelteKit
    // 2.62.0) instead of a svelte.config.js file: webapp has no
    // "type": "module" (electron 22 needs a CJS main process), so an ESM
    // config file would emit a MODULE_TYPELESS_PACKAGE_JSON warning while
    // a CJS one cannot load adapter-static ("import"-only exports).
    sveltekit({
      preprocess: vitePreprocess(),
      // SPA mode: no SSR, single fallback page for all routes
      adapter: adapter({
        pages: "dist/renderer",
        assets: "dist/renderer",
        fallback: "index.html",
      }),

      // Keep the existing electron project layout under renderer/
      files: {
        lib: "renderer/lib",
        routes: "renderer/routes",
        appTemplate: "renderer/app.html",
      },

      // Path aliases are declared here instead of tsconfig.json "paths",
      // so svelte-kit sync generates them into .svelte-kit/tsconfig.json.
      // $lib is generated automatically from kit.files.lib.
      alias: {
        $src: "renderer",
        $routes: "renderer/routes",
      },
    }),
    tailwindcss(),
    electron([
      {
        entry: resolve(__dirname, "main/index.ts"),
        vite: {
          // The main process runs as plain node (no HMR): the node-mode
          // i18n plugin rescans main sources on every buildStart, so
          // tray translations stay in sync during watch builds.
          plugins: [i18nPlugin(mainI18nConfig)],
          build: {
            // electron 22 bundles Node 16.17; do not follow vite 8's
            // default baseline-widely-available (2026-01) target
            target: "node16",
            outDir: "dist/main",
          },
        },
      },
      {
        entry: resolve(__dirname, "preload/index.ts"),
        vite: {
          build: {
            // electron 22 bundles Node 16.17; do not follow vite 8's
            // default baseline-widely-available (2026-01) target
            target: "node16",
            outDir: "dist/preload",
          },
        },
      },
    ]),
    {
      name: "svelte-kit-esm-marker",
      configResolved() {
        ensureSvelteKitEsmMarker();
      },
    },
  ],
  esbuild: {
    legalComments: "none",
  },
  build: {
    // electron 22 bundles Chromium 108; do not follow vite 8's default
    // baseline-widely-available (2026-01) target
    target: "chrome108",
  },
});
