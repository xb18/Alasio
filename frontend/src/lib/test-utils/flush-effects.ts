import { flushSync, tick } from "svelte";

/**
 * Runs all pending svelte `$effect` callbacks and applies their state
 * changes.
 *
 * In svelte 5.56 effects are scheduled asynchronously (microtask), and
 * state writes made inside an effect are applied when its batch is
 * committed, so a single `flushSync()` is not enough outside of a
 * component render cycle. This helper drains several microtask turns
 * (effects may schedule further effects), flushes synchronously, and
 * finally awaits `tick()` for any remaining work. Tests that drive
 * `useTopic` / `createResilientRpc` through `effect_root` must await
 * this helper after every state change they want the effects to
 * observe.
 */
export async function flushEffects(): Promise<void> {
  for (let i = 0; i < 3; i++) {
    await Promise.resolve();
  }
  flushSync();
  await tick();
}
