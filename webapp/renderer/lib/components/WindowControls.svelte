<script lang="ts">
  import Copy from "@lucide/svelte/icons/copy";
  import Minimize2 from "@lucide/svelte/icons/minimize-2";
  import Minus from "@lucide/svelte/icons/minus";
  import Square from "@lucide/svelte/icons/square";
  import X from "@lucide/svelte/icons/x";
  import Button from "$lib/components/ui/button/button.svelte";
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
  <Button variant="ghost" size="icon" class="dark:hover:bg-muted" title="Hide to tray" onclick={handleHide}>
    <Minimize2 class="h-4 w-4" strokeWidth={1.5} />
  </Button>
  <Button variant="ghost" size="icon" class="dark:hover:bg-muted" title="Minimize" onclick={handleMinimize}>
    <Minus class="h-4 w-4" strokeWidth={1.5} />
  </Button>
  <Button variant="ghost" size="icon" class="dark:hover:bg-muted" title="Maximize" onclick={handleMaximize}>
    {#if isMaximized}
      <Copy class="h-4 w-4" strokeWidth={1.5} />
    {:else}
      <Square class="h-4 w-4" strokeWidth={1.5} />
    {/if}
  </Button>
  <Button
    variant="ghost"
    size="icon"
    class="hover:bg-destructive hover:text-destructive-foreground dark:hover:bg-destructive dark:hover:text-destructive-foreground"
    title="Close"
    onclick={handleClose}
  >
    <X class="h-4 w-4" strokeWidth={1.5} />
  </Button>
</div>

{#if showCloseDialog}
  <CloseDialog bind:show={showCloseDialog} />
{/if}
