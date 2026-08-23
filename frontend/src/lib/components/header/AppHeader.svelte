<script lang="ts">
  import type { Snippet } from "svelte";
  import type { HTMLAttributes } from "svelte/elements";
  import ThemeToggle from "$lib/components/ui/theme/theme-toggle.svelte";
  import LangSelector from "$lib/i18n/LangSelector.svelte";
  import { WINDOW_CONTROLS_WIDTH, electronEnv } from "$lib/use/useElectronEnv.svelte";
  import { cn } from "$lib/utils.js";

  // props
  type $props = {
    children?: Snippet;
    class?: string;
  };
  let { children, class: className }: HTMLAttributes<HTMLHeadElement> & $props = $props();
</script>

<header
  class={cn(
    // global
    "app-header relative z-40",
    "bg-card flex h-12 w-full items-center gap-1 px-4",
    className,
  )}
  style={electronEnv.shouldAvoid ? `padding-right: ${WINDOW_CONTROLS_WIDTH}px` : undefined}
>
  <!-- header content -->
  {@render children?.()}

  <LangSelector></LangSelector>
  <ThemeToggle variant="ghost"></ThemeToggle>
</header>
