// Run with: tsx scripts/electron-cleanup.ts
import { existsSync, readdirSync, rmSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const webappRoot = fileURLToPath(new URL("..", import.meta.url));
const releaseDir = join(webappRoot, "release");

/**
 * Remove electron-builder leftovers that come with the local electron dist.
 *
 * electron-builder copies the electron distribution configured by
 * `electronDist` in electron-builder.yml as-is, so `default_app.asar`
 * (the default app Electron falls back to when no app.asar is found) and
 * the `version` file survive packaging. They are never loaded by the
 * packaged app and are pure dead weight, so remove them after packaging.
 *
 * Layouts handled:
 *   win/linux: {unpackedDir}/resources/default_app.asar, {unpackedDir}/version
 *   mac:       {unpackedDir}/{App}.app/Contents/Resources/{default_app.asar, version}
 */
function removeIfExists(file) {
  if (existsSync(file)) {
    rmSync(file, { force: true });
    console.log(`Removed ${relative(webappRoot, file)}`);
  }
}

function cleanupUnpackedDir(dir) {
  removeIfExists(join(dir, "resources", "default_app.asar"));
  removeIfExists(join(dir, "version"));
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (entry.isDirectory() && entry.name.endsWith(".app")) {
      const resourcesDir = join(dir, entry.name, "Contents", "Resources");
      removeIfExists(join(resourcesDir, "default_app.asar"));
      removeIfExists(join(resourcesDir, "version"));
    }
  }
}

function main() {
  if (!existsSync(releaseDir)) {
    console.log("No release directory found, nothing to clean up.");
    return;
  }
  for (const entry of readdirSync(releaseDir, { withFileTypes: true })) {
    if (entry.isDirectory()) {
      cleanupUnpackedDir(join(releaseDir, entry.name));
    }
  }
}

main();
