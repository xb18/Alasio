<script lang="ts">
  import LayoutHorizontalLike from "$lib/components/arg/LayoutHorizontalLike.svelte";
  import type { ArgData } from "$lib/components/arg/utils.svelte";
  import { Checkbox } from "$lib/components/ui/checkbox";
  import ThemeToggle from "$lib/components/ui/theme/theme-toggle.svelte";
  import { dpiState, setDpiScaling } from "$lib/dpi/state.svelte";
  import { t } from "$lib/i18n";
  import LangSelector from "$lib/i18n/LangSelector.svelte";
  import { isElectron } from "$lib/use/useElectronEnv.svelte";

  // dpiScaling mirrors the host value (webapp main AppState) through the
  // alasio:dpi-scaling downlink/uplink; the real scaling is applied by the
  // electron startup parameters, so a change takes effect on the next
  // launch. Outside an embedded (electron) session the checkbox is
  // disabled (remote browsers have no host to apply the value).

  // $derived so name/help follow the current display language
  const langData = $derived.by<ArgData>(() => ({
    task: "SystemTool",
    group: "SystemTool",
    arg: "DisplayLang",
    dt: "static",
    value: null,
    name: t.DevTool.Language(),
  }));

  const themeData = $derived.by<ArgData>(() => ({
    task: "SystemTool",
    group: "SystemTool",
    arg: "DisplayTheme",
    dt: "static",
    value: null,
    name: t.DevTool.Theme(),
  }));

  const dpiData = $derived.by<ArgData>(() => ({
    task: "SystemTool",
    group: "SystemTool",
    arg: "DpiScaling",
    dt: "static",
    value: dpiState.value,
    name: t.DevTool.DpiScaling(),
    help: t.DevTool.DpiScalingHelp(),
  }));
</script>

<hr />
<div class="flex flex-col gap-y-1.5">
  <LayoutHorizontalLike data={langData}>
    {#snippet InputSnippet()}
      <LangSelector />
    {/snippet}
  </LayoutHorizontalLike>
</div>

<hr />
<div class="flex flex-col gap-y-1.5">
  <LayoutHorizontalLike data={themeData}>
    {#snippet InputSnippet()}
      <ThemeToggle />
    {/snippet}
  </LayoutHorizontalLike>
</div>

<hr />
<div class="flex flex-col gap-y-1.5">
  <LayoutHorizontalLike data={dpiData}>
    {#snippet InputSnippet()}
      <Checkbox
        checked={dpiState.value}
        onCheckedChange={(checked) => setDpiScaling(checked === true)}
        disabled={!isElectron.value}
        class="size-4.5"
        iconStrokeWidth={3.5}
      />
    {/snippet}
  </LayoutHorizontalLike>
</div>
