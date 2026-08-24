import { vi } from "vitest";

/**
 * Test stub for the SvelteKit virtual module `$app/navigation`.
 * Resolved by vitest.config.ts in the test environment only; product
 * code keeps importing the real virtual module at build time.
 *
 * The functions are vi.fn() so tests can assert calls, e.g. the
 * WebsocketManager redirect on close code 4001.
 */
export const goto = vi.fn();
export const invalidateAll = vi.fn();
