// Pack the vite build output (dist/) into app.asar and replace the archives
// found under the release directory, so small changes can be shipped without
// repacking the whole electron app.
//
// The archive layout replicates electron-builder's `files` config in
// electron-builder.yml (dist/**/* plus package.json at the archive root).
// Run with: tsx scripts/pack-asar.ts
import { createPackageFromFiles } from "@electron/asar";
import { existsSync, readdirSync, renameSync, rmSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const webappRoot = fileURLToPath(new URL("..", import.meta.url));
const distDir = join(webappRoot, "dist");
const releaseDir = join(webappRoot, "release");

/**
 * Collect all regular files under a directory recursively.
 *
 * Symlinks are resolved with stat so linked files and directories are
 * followed, matching how the asar package walks its input.
 *
 * Args:
 *     dir (str): Directory to walk
 *
 * Returns:
 *     list[str]: Absolute paths of regular files
 */
function walkFiles(dir) {
  const files = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const file = join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...walkFiles(file));
    } else if (entry.isFile()) {
      files.push(file);
    } else if (entry.isSymbolicLink()) {
      const st = statSync(file);
      if (st.isDirectory()) {
        files.push(...walkFiles(file));
      } else if (st.isFile()) {
        files.push(file);
      }
    }
  }
  return files;
}

/**
 * Find every existing app.asar archive under a directory recursively.
 *
 * Args:
 *     dir (str): Directory to search
 *
 * Returns:
 *     list[str]: Absolute paths of app.asar files
 */
function findAsarFiles(dir) {
  const files = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const file = join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...findAsarFiles(file));
    } else if (entry.isFile() && entry.name === "app.asar") {
      files.push(file);
    }
  }
  return files;
}

/**
 * Replace an app.asar archive atomically with a freshly packed one.
 *
 * The archive is written next to the target and renamed over it, so an
 * interrupted run never leaves a half-written app.asar in place.
 *
 * Args:
 *     target (str): Absolute path of the app.asar to replace
 *     files (list[str]): Archive entries, relative to webappRoot
 */
async function replaceAsar(target, files) {
  const tmp = `${target}.tmp`;
  try {
    await createPackageFromFiles(webappRoot, tmp, files);
    renameSync(tmp, target);
    console.log(`Updated ${relative(webappRoot, target)}`);
  } finally {
    rmSync(tmp, { force: true });
  }
}

async function main() {
  if (!existsSync(releaseDir)) {
    console.log("No release directory found, skip asar packaging.");
    return;
  }
  if (!existsSync(distDir)) {
    console.error("dist directory not found, run vite build first.");
    process.exitCode = 1;
    return;
  }
  const targets = findAsarFiles(releaseDir);
  if (targets.length === 0) {
    console.log("No app.asar found in release, skip asar packaging.");
    return;
  }
  const files = [
    ...walkFiles(distDir).map((file) => relative(webappRoot, file)),
    "package.json",
  ];
  for (const target of targets) {
    await replaceAsar(target, files);
  }
}

main();
