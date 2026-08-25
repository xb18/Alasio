<script lang="ts">
  import { t } from "$lib/i18n";
  import { useSharedState } from "$lib/useSharedState.svelte";

  const sharedState = useSharedState();

  const errorMessage = $derived.by(() => {
    const key = sharedState.errorKey;
    if (key === "ConfigNotFound") return t.Error.ConfigNotFound();
    if (key === "PythonNotConfigured") return t.Error.PythonNotConfigured();
    if (key === "PythonNotFound") return t.Error.PythonNotFound();
    if (key === "GuiPyNotFound") return t.Error.GuiPyNotFound();
    if (key === "BackendStartFailed") return t.Error.BackendStartFailed();
    return t.Error.UnknownError();
  });
</script>

<div class="bg-background text-foreground flex h-full items-center justify-center">
  <div class="bg-card w-[600px] rounded-xl p-12 shadow-lg backdrop-blur-lg">
    <h1 class="text-destructive mb-6 text-4xl font-bold">Error</h1>

    <div class="mb-6">
      <p class="mb-4 text-xl">
        {errorMessage}
      </p>
      {#if sharedState.errorPath}
        <div class="text-sm">
          <p>{t.Error.CurrentPath()}: {sharedState.errorPath}</p>
        </div>
      {/if}
    </div>

    <button
      onclick={() => location.reload()}
      class="bg-primary hover:bg-primary/30 text-destructive-foreground w-full rounded-lg py-3 font-semibold transition-colors"
    >
      {t.Error.Retry()}
    </button>
  </div>
</div>
