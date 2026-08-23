<script lang="ts">
  import Copy from "@lucide/svelte/icons/copy";
  import Minimize2 from "@lucide/svelte/icons/minimize-2";
  import Minus from "@lucide/svelte/icons/minus";
  import Square from "@lucide/svelte/icons/square";
  import X from "@lucide/svelte/icons/x";
  import CloseDialog from "./CloseDialog.svelte";

  let isMaximized = $state(false);
  let showCloseDialog = $state(false);

  function handleHide() {
    window.electronAPI.hideWindow();
  }

  function handleMinimize() {
    window.electronAPI.minimizeWindow();
  }

  function handleMaximize() {
    isMaximized = !isMaximized;
    window.electronAPI.maximizeWindow();
  }

  function handleClose() {
    showCloseDialog = true;
  }
</script>

<div class="flex items-center gap-1 pr-1.5" style="-webkit-app-region: no-drag">
  <button
    onclick={handleHide}
    class="hover:bg-accent hover:text-accent-foreground flex h-9 w-9 items-center justify-center rounded-md transition-colors"
    title="Hide to tray"
  >
    <Minimize2 class="h-4 w-4" strokeWidth={1.5} />
  </button>
  <button
    onclick={handleMinimize}
    class="hover:bg-accent hover:text-accent-foreground flex h-9 w-9 items-center justify-center rounded-md transition-colors"
    title="Minimize"
  >
    <Minus class="h-4 w-4" strokeWidth={1.5} />
  </button>
  <button
    onclick={handleMaximize}
    class="hover:bg-accent hover:text-accent-foreground flex h-9 w-9 items-center justify-center rounded-md transition-colors"
    title="Maximize"
  >
    {#if isMaximized}
      <Copy class="h-4 w-4" strokeWidth={1.5} />
    {:else}
      <Square class="h-4 w-4" strokeWidth={1.5} />
    {/if}
  </button>
  <button
    onclick={handleClose}
    class="hover:bg-destructive hover:text-destructive-foreground flex h-9 w-9 items-center justify-center rounded-md transition-colors"
    title="Close"
  >
    <X class="h-4 w-4" strokeWidth={1.5} />
  </button>
</div>

{#if showCloseDialog}
  <CloseDialog bind:show={showCloseDialog} />
{/if}
