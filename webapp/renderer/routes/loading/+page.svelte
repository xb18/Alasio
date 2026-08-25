<script lang="ts">
  import { onMount } from "svelte";
  import StartupCard from "$lib/components/StartupCard.svelte";

  let logs = $state<string[]>([]);
  let logContainer: HTMLDivElement;

  onMount(() => {
    const unsubscribe = window.electronAPI.onBackendLog((log: string) => {
      logs.push(log);
      setTimeout(() => {
        if (logContainer) {
          logContainer.scrollTop = logContainer.scrollHeight;
        }
      }, 10);
    });

    return unsubscribe;
  });
</script>

<StartupCard title="Alasio" desc="Starting backend..." class="">
  <div
    bind:this={logContainer}
    class="bg-muted border-border h-64 w-[80%] max-w-4xl overflow-y-auto rounded-lg border p-4 font-mono text-sm"
  >
    {#each logs as log}
      <div class="text-muted-foreground whitespace-pre-wrap">{log}</div>
    {/each}
  </div>
</StartupCard>
