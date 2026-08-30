<script lang="ts">
  import { onDestroy } from "svelte";
  import { routeState } from "$lib/ws/route-state.svelte";

  let { children } = $props();

  // The public flag is set (and a leftover connection torn down) in this
  // group's +layout.ts load, which runs before any component is created;
  // onMount would be too late because child components subscribe and
  // connect during creation, before onMount fires.
  //
  // Leaving the (public) group restores the ability to connect; the
  // private layout's components subscribe after this destroy hook runs
  // (SvelteKit destroys the old layout before mounting the new one), so
  // their connect() calls pass the guard.
  onDestroy(() => {
    routeState.public = false;
  });
</script>

{@render children()}
