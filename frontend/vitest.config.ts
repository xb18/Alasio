import { fileURLToPath } from "node:url";
import { svelte } from "@sveltejs/vite-plugin-svelte";
import { defineConfig } from "vitest/config";

/**
 * Vitest configuration for the frontend.
 *
 * Kept separate from vite.config.ts on purpose: the sveltekit plugin
 * (and the i18n / dev-page plugins) are not needed in tests, and their
 * behavior (virtual modules, route scanning) would only add noise.
 * The svelte plugin alone compiles the runes in `.svelte.ts` source
 * files; svelte.config.js is not loaded (configFile: false) so kit
 * preprocessing stays out of the test pipeline.
 *
 * `$app/*` are SvelteKit virtual modules; tests resolve them to small
 * stubs under src/test-utils so product code can be imported without
 * modification.
 */
export default defineConfig({
  plugins: [svelte({ configFile: false })],
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.ts"],
  },
  // Expose the shared message fixtures path to the contract test. The
  // fixtures live outside the frontend tree (tests/ws_fixtures/), and
  // import.meta.url in vitest workers is not a file:// url, so the path
  // is computed here in the config file and injected at build time.
  define: {
    "import.meta.env.WS_FIXTURES_PATH": JSON.stringify(
      fileURLToPath(new URL("../tests/ws_fixtures/messages.json", import.meta.url)),
    ),
  },
  resolve: {
    alias: {
      // Same $lib alias the SvelteKit project config provides; vitest
      // loads this config standalone so it must be declared here.
      $lib: fileURLToPath(new URL("./src/lib", import.meta.url)),
      "$app/environment": fileURLToPath(new URL("./src/lib/test-utils/app-environment.ts", import.meta.url)),
      "$app/navigation": fileURLToPath(new URL("./src/lib/test-utils/app-navigation.ts", import.meta.url)),
    },
  },
});
