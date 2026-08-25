<script lang="ts">
  import type { Snippet } from "svelte";
  import * as Card from "$lib/components/ui/card";
  import { cn } from "$lib/utils";

  let {
    title,
    desc,
    children,
    class: className,
  }: {
    title: string;
    desc: string;
    children?: Snippet;
    class?: string;
  } = $props();
</script>

<!-- The card fills most of the viewport; the padding around it exposes the
     dot-grid background decoration, matching the frontend look. -->
<div class="dotbg bg-background text-foreground flex h-full items-center justify-center p-8">
  <Card.Root class={cn("neushadow flex h-120 w-150 flex-col items-center justify-center border-none p-12", className)}>
    <Card.Content class="flex h-full w-full flex-col items-center">
      <!-- Upper half: title + desc -->
      <div class="flex w-full flex-1 flex-col items-center pt-6">
        <h1 class="text-5xl font-bold">{title}</h1>
        <p class="text-muted-foreground mt-2 text-xl">{desc}</p>
      </div>
      <!-- Lower half: children -->
      <div class="flex w-full h-60 flex-col items-center justify-center">
        {@render children?.()}
      </div>
    </Card.Content>
  </Card.Root>
</div>
