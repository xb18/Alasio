<script lang="ts">
  import FlaskConical from "@lucide/svelte/icons/flask-conical";
  import { goto } from "$app/navigation";
  import { page } from "$app/state";
  import { buttonVariants } from "$lib/components/ui/button/button.svelte";
  import * as Popover from "$lib/components/ui/popover";
  import { cn } from "$lib/utils";

  // Dev-only launcher: preview any startup route without preparing the real
  // launch conditions (broken config, missing python, failed backend...).
  // Error entries inject the payload through the URL, which useSharedState
  // reads in dev mode (see getDevOverride); the URL stays the source of
  // truth until it is navigated away. The module is only loaded in dev:
  // +layout.svelte imports it dynamically behind import.meta.env.DEV.
  // Labels are internal identifiers, so this dev tool deliberately does
  // not participate in i18n.
  const PAGES = [
    { label: "Setup", path: "/setup" },
    { label: "Loading", path: "/loading" },
    { label: "App", path: "/app" },
  ];

  // Keys mirror i18n/Error.json; "UnknownError" is the fallback when no
  // errorKey is present.
  const ERROR_KEYS = ["ConfigNotFound", "PythonNotConfigured", "PythonNotFound", "GuiPyNotFound", "BackendStartFailed"];

  // Sample path injected into the error URL so the error page's path
  // section has content to render in dev; a real path only exists when the
  // error actually happened.
  const SAMPLE_ERROR_PATH = "C:\\ProgramData\\Pycharm\\Alasio";

  const currentRoute = $derived(page.route.id);
  const currentErrorKey = $derived(page.url.searchParams.get("errorKey"));

  function navigate(path: string, errorKey?: string) {
    if (path !== "/error") {
      goto(path);
      return;
    }
    const params = new URLSearchParams();
    if (errorKey) params.set("errorKey", errorKey);
    params.set("errorPath", SAMPLE_ERROR_PATH);
    goto(`/error?${params}`);
  }
</script>

<div class="fixed right-4 bottom-4 z-50">
  <Popover.Root>
    <Popover.Trigger class={cn(buttonVariants({ variant: "secondary", size: "icon" }), "shadow-lg")}>
      <FlaskConical class="size-4" />
    </Popover.Trigger>
    <Popover.Content side="top" align="end" class="z-100 w-64 p-2">
      <div class="text-muted-foreground px-2 py-1.5 text-xs font-medium">Dev Routes</div>
      {#each PAGES as item}
        <Popover.Close
          class={cn(
            buttonVariants({ variant: "ghost", size: "sm" }),
            "w-full justify-start",
            currentRoute === item.path && "bg-accent text-accent-foreground",
          )}
          onclick={() => navigate(item.path)}
        >
          {item.label}
        </Popover.Close>
      {/each}

      <div class="bg-border mx-2 my-1 h-px"></div>

      <div class="text-muted-foreground px-2 py-1.5 text-xs font-medium">Error</div>
      {#each ERROR_KEYS as key}
        <Popover.Close
          class={cn(
            buttonVariants({ variant: "ghost", size: "sm" }),
            "w-full justify-start",
            currentRoute === "/error" && currentErrorKey === key && "bg-accent text-accent-foreground",
          )}
          onclick={() => navigate("/error", key)}
        >
          {key}
        </Popover.Close>
      {/each}
      <Popover.Close
        class={cn(
          buttonVariants({ variant: "ghost", size: "sm" }),
          "w-full justify-start",
          currentRoute === "/error" && !currentErrorKey && "bg-accent text-accent-foreground",
        )}
        onclick={() => navigate("/error")}
      >
        UnknownError
      </Popover.Close>
    </Popover.Content>
  </Popover.Root>
</div>
