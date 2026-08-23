<script lang="ts">
  import type { ArgData } from "$lib/components/arg/utils.svelte";
  import { cn } from "$lib/utils";
  import { formatToLocal, tzOffset } from "./dateutils.svelte";

  let {
    data = $bindable(),
    class: className,
  }: {
    data: ArgData;
    class?: string;
  } = $props();

  const displayValue = $derived(formatToLocal(data.value));
</script>

<div class={cn("group flex w-full items-center justify-end", className)}>
  <span class="text-muted-foreground truncate text-xs">{displayValue} {tzOffset}</span>
</div>
