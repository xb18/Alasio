<script lang="ts">
  import { onMount } from "svelte";
  import TriangleAlert from "@lucide/svelte/icons/triangle-alert";
  import StartupCard from "$lib/components/StartupCard.svelte";
  import { Button } from "$lib/components/ui/button";
  import { t } from "$lib/i18n";
  import { getDevOverride, useSharedState } from "$lib/useSharedState.svelte";

  const sharedState = useSharedState();
  const failed = $derived(!sharedState.backendSuccess);

  // Dev preview mock logs, in chronological order (oldest first). The page
  // stores lines newest-first for the column-reverse layout, so the list is
  // reversed when filling. Previewed through DevRouteSwitcher URLs
  // (/loading?backendSuccess=true|false). Guarded by import.meta.env.DEV
  // so the build folds them to empty arrays and the mock data never
  // reaches production bundles (the preview path itself is already dead in
  // production: getDevOverride returns null there).
  // The filler prefix (meaningless lines) makes the log area overflow so
  // the preview shows the scrolling behavior.
  const DEV_LOG_FILLER = import.meta.env.DEV
    ? Array.from({ length: 40 }, (_, i) => `[Supervisor] dev preview filler line ${String(i + 1).padStart(2, "0")}`)
    : [];
  const DEV_LOGS = import.meta.env.DEV
    ? [
        ...DEV_LOG_FILLER,
        "Loading deploy.yaml ...",
        "[Supervisor] Electron mode, port 22267",
        "[Supervisor] Starting backend process...",
        "Loading module: alasio.backend",
        "Registering routes: /api, /topic, /assets",
        "Running on http://127.0.0.1:22267 (CTRL + C to quit)",
      ]
    : [];
  const DEV_LOGS_FAILED = import.meta.env.DEV
    ? [
        ...DEV_LOG_FILLER,
        "Loading deploy.yaml ...",
        "[Supervisor] Electron mode, port 22267",
        "[Supervisor] Starting backend process...",
        "Loading module: alasio.backend",
        "Registering routes: /api, /topic, /assets",
        "[Supervisor] ERROR: Backend exited before ready (code: 1)",
      ]
    : [];

  // Log lines are prepended and the container lays them out in column
  // reverse, so the newest line sits at the visual bottom. The scroll
  // origin of a column-reverse container is its visual bottom (scrollTop
  // 0), which keeps the newest line pinned at the bottom edge while older
  // lines are pushed upwards as new ones arrive.
  let logs = $state<string[]>([]);
  let retrying = $state(false);

  // Dev preview: fill the mock log for the URL backendSuccess flag, and
  // re-fill whenever the preview switches between success/failed
  // (component instance is reused across query changes). No-op in real
  // runs.
  $effect(() => {
    const override = getDevOverride();
    if (override?.route !== "loading" || override.backendSuccess === undefined) return;
    logs = [...(override.backendSuccess ? DEV_LOGS : DEV_LOGS_FAILED)].reverse();
  });

  onMount(() => {
    // Dev preview shows mock logs only; skip the real backend log stream.
    const override = getDevOverride();
    if (override?.route === "loading" && override.backendSuccess !== undefined) return;

    const unsubscribe = window.electronAPI.onBackendLog((log: string) => {
      logs.unshift(log);
    });

    return unsubscribe;
  });

  // Retry wipes the previous attempt's log (the shared-state failure flag
  // is cleared by the main process at the start of the new attempt, which
  // hides the failure hint), then the log accumulates from scratch again.
  // In dev preview the retry is simulated locally: the mock log is
  // re-filled without touching the real backend.
  async function retry() {
    logs = [];
    retrying = true;
    const override = getDevOverride();
    if (override?.route === "loading" && override.backendSuccess !== undefined) {
      logs = [...(override.backendSuccess ? DEV_LOGS : DEV_LOGS_FAILED)].reverse();
      retrying = false;
      return;
    }
    try {
      await window.electronAPI.startBackend();
    } finally {
      retrying = false;
    }
  }
</script>

<StartupCard title="Alasio" desc={t.Loading.StartingBackend()} class="">
  <div class="flex h-full w-full flex-col">
    <!-- Log area: newest line at the bottom, older lines pushed upwards -->
    <div class="min-h-0 w-full flex-1">
      <div class="flex h-full w-full flex-col-reverse overflow-y-auto border-t border-b font-mono text-xs">
        {#each logs as log}
          <div class="text-muted-foreground whitespace-pre-wrap">{log}</div>
        {/each}
      </div>
    </div>
    <!-- Placeholder below the log: blank while starting (or after a
         successful start, when the page has already navigated away);
         on startup failure it shows the hint and a retry button. -->
    <div class="mt-2 flex h-8 w-full shrink-0 items-center justify-end gap-4">
      {#if failed}
        <div class="flex items-center gap-2">
          <TriangleAlert class="text-destructive size-5" />
          <p class="ml-0 text-lg">{t.Error.BackendStartFailed()}</p>
        </div>
        <Button onclick={retry} disabled={retrying} class="h-8 w-16 font-semibold">
          {t.Error.Retry()}
        </Button>
      {/if}
    </div>
  </div>
</StartupCard>
