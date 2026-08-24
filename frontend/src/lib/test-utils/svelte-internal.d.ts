/**
 * Ambient declarations for svelte internal APIs used by tests only.
 *
 * `svelte/internal/client` ships without type declarations; the test
 * suites import `effect_root` from it to run `$effect` outside of a
 * component (the same mechanism components use under the hood).
 */
declare module "svelte/internal/client" {
  /**
   * Creates an effect root, the non-component equivalent of a component
   * instance. `$effect` calls inside the returned scope are legal; the
   * returned function tears the root down (running effect cleanups).
   *
   * @param fn - The effect root body
   * @returns A teardown function for the root
   */
  export function effect_root(fn: () => void): () => void;
}
