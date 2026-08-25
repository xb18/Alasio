<script lang="ts">
  import Select from "$lib/components/Select.svelte";
  import { Button } from "$lib/components/ui/button";
  import { t } from "$lib/i18n";
  import { setLanguage } from "$lib/i18n/state.svelte";
  import { useSharedState } from "$lib/useSharedState.svelte";

  const sharedState = useSharedState();
  // Initial selection mirrors the persistent config values (may be 'system');
  // the UI display language/theme follows the derived values in shared state.
  let selectedLang = $state(sharedState.configLang);
  let selectedTheme = $state(sharedState.configTheme);

  const languages = $derived([
    { value: "system", label: t.Setup.FollowSystem() },
    { value: "zh-CN", label: "简体中文" },
    { value: "en-US", label: "English" },
    { value: "ja-JP", label: "日本語" },
    { value: "zh-TW", label: "繁體中文" },
    { value: "es-ES", label: "Español" },
  ]);

  const themes = $derived([
    { value: "system", label: t.Setup.FollowSystem() },
    { value: "light", label: t.Setup.Light() },
    { value: "dark", label: t.Setup.Dark() },
  ]);

  // Selection writes the config value immediately through IPC: the main
  // process AppState is the single source of truth, it broadcasts to the
  // backend once it is ready (no saveFirstTimeConfig anymore, the backend
  // self-bootstraps deploy.yaml). The bind:value on Select keeps the local
  // selection in sync; here we only trigger the side effects.
  function selectLang(value: string | undefined) {
    if (value === undefined) return;
    setLanguage(value);
  }

  function selectTheme(value: string | undefined) {
    if (value === undefined) return;
    window.electronAPI.setTheme(value);
  }

  async function handleStart() {
    // Values are already saved through the IPC on selection; starting the
    // backend persists them into deploy.yaml through the stdin contract.
    await window.electronAPI.startBackend();
  }
</script>

<div class="bg-background text-foreground flex h-full items-center justify-center">
  <div class="flex w-[600px] flex-col items-center">
    <h1 class="text-5xl font-bold">Alasio</h1>
    <p class="text-muted-foreground mt-2 mb-14 text-xl">{t.Setup.Welcome()}</p>

    <div class="w-full space-y-10">
      <div class="flex items-center justify-between gap-6">
        <label for="setup-language" class="text-lg">{t.Setup.SelectLanguage()}</label>
        <div class="w-72">
          <Select id="setup-language" bind:value={selectedLang} options={languages} onValueChange={selectLang} />
        </div>
      </div>

      <div class="flex items-center justify-between gap-6">
        <label for="setup-theme" class="text-lg">{t.Setup.SelectTheme()}</label>
        <div class="w-72">
          <Select id="setup-theme" bind:value={selectedTheme} options={themes} onValueChange={selectTheme} />
        </div>
      </div>
    </div>

    <Button onclick={handleStart} size="lg" class="mt-16 h-14 w-48 rounded-xl text-xl font-semibold">
      {t.Setup.Start()}
    </Button>
  </div>
</div>
