import { mount, unmount } from "svelte";
import { toast } from "svelte-sonner";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { setLang } from "$lib/i18n";
import { FakeWebSocket } from "$lib/test-utils/fake-websocket";
import { flushEffects } from "$lib/test-utils/flush-effects";
import { websocketClient } from "$lib/ws";
import { routeState } from "$lib/ws/route-state.svelte";
import LangSelector from "./LangSelector.svelte";

// The rpc layer surfaces timeouts through svelte-sonner; keep the real
// toast library out of the jsdom tests.
vi.mock("svelte-sonner", () => ({
  toast: { error: vi.fn(), success: vi.fn() },
}));

vi.stubGlobal("WebSocket", FakeWebSocket);

/** Components mounted by the current test; unmounted in afterEach. */
// mount() is generic over the component's props/exports, so its return
// type cannot be spelled with ReturnType; the array only holds component
// handles for unmount.
let mounted: any[] = [];

/** Mounts LangSelector into a fresh detached container. */
function mountLangSelector() {
  const target = document.createElement("div");
  document.body.appendChild(target);
  const component = mount(LangSelector, { target });
  mounted.push(component);
  return { component, target };
}

/** Parsed messages the last socket sent (empty when none was created). */
function lastSent(): Record<string, any>[] {
  const ws = FakeWebSocket.last;
  if (!ws) return [];
  return ws.sent.map((raw) => JSON.parse(typeof raw === "string" ? raw : new TextDecoder().decode(raw)));
}

/** The set_lang rpc messages the last socket sent. */
function sentSetLangMessages(): Record<string, any>[] {
  return lastSent().filter((m) => m.t === "ConnState" && m.o === "rpc" && m.f === "set_lang");
}

describe("TestLangSelectorSetLang", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    FakeWebSocket.reset();
    vi.clearAllMocks();
    // Default to a private (non-public) route; public-route tests flip
    // the flag before mounting. All timers are fake so rpc timeout
    // timers left over from a test cannot fire into the next one.
    routeState.public = false;
    // Fresh session for each test: the singleton ws client keeps its
    // connection generation across tests, and a stale generation would
    // make resilientRpc treat the next serverOpen as a reconnect and
    // replay the last call (a second set_lang message).
    websocketClient.disconnect();
    websocketClient.connectionGeneration = 0;
    setLang("system");
  });

  afterEach(() => {
    // Unmount every component the test mounted, even on assertion
    // failure: a leaked component keeps its effects alive and its
    // set_lang rpc would fire into the next test (its effect depends
    // on the shared routeState / i18n state).
    for (const component of mounted) {
      unmount(component);
    }
    mounted = [];
    // Close any socket the test left on the shared singleton: a stale
    // #ws in OPEN/CONNECTING state would make the next test's
    // connect() a no-op and no socket would ever be created.
    websocketClient.disconnect();
    vi.useRealTimers();
    setLang("system");
  });

  it("does not connect or call set_lang on a public page", async () => {
    routeState.public = true;
    const { component } = mountLangSelector();
    await flushEffects();

    // The subscription and the lang sync are both blocked by the
    // public-route guard: no socket is ever created.
    expect(FakeWebSocket.instances).toHaveLength(0);
    expect(sentSetLangMessages()).toHaveLength(0);
  });

  it("shows no rpc timeout toast on a public page", async () => {
    routeState.public = true;
    mountLangSelector();
    await flushEffects();

    // Longer than the 5s rpc timeout: nothing was ever sent, so no
    // timeout toast can appear (regression: the unguarded sync used to
    // queue set_lang forever and toast "RPC call timeout" on /auth).
    vi.advanceTimersByTime(10_000);
    expect(toast.error).not.toHaveBeenCalled();
  });

  it("calls set_lang on a private page once the connection is open", async () => {
    mountLangSelector();
    await flushEffects();

    // The subscription creates a socket; the rpc is queued until open.
    expect(FakeWebSocket.instances).toHaveLength(1);
    expect(sentSetLangMessages()).toHaveLength(0);

    FakeWebSocket.last!.serverOpen();
    await flushEffects();

    const messages = sentSetLangMessages();
    expect(messages).toHaveLength(1);
    expect(messages[0]).toEqual({
      t: "ConnState",
      o: "rpc",
      f: "set_lang",
      v: { lang: expect.any(String) },
      i: expect.any(String),
    });
  });

  it("syncs the language after login when the private session mounts", async () => {
    // Public page: LangSelector mounts but stays disconnected.
    routeState.public = true;
    const publicComp = mountLangSelector();
    await flushEffects();
    expect(FakeWebSocket.instances).toHaveLength(0);

    // Login redirects into the private group: the layout swap destroys
    // the public instance and a fresh one mounts with the flag cleared.
    unmount(publicComp.component);
    mounted = mounted.filter((c) => c !== publicComp.component);
    await flushEffects();
    routeState.public = false;

    mountLangSelector();
    await flushEffects();
    expect(FakeWebSocket.instances).toHaveLength(1);

    FakeWebSocket.last!.serverOpen();
    await flushEffects();
    expect(sentSetLangMessages()).toHaveLength(1);
  });

  it("syncs the language when the route flips to private on a live instance", async () => {
    // Same-instance variant: the effect depends on routeState.public,
    // so the sync runs as soon as the flag clears even without a
    // component swap (the real flow swaps, but the dependency must
    // stay reactive).
    routeState.public = true;
    mountLangSelector();
    await flushEffects();
    expect(FakeWebSocket.instances).toHaveLength(0);

    routeState.public = false;
    await flushEffects();
    expect(FakeWebSocket.instances).toHaveLength(1);

    FakeWebSocket.last!.serverOpen();
    await flushEffects();
    expect(sentSetLangMessages()).toHaveLength(1);
  });

  it("re-syncs when the language changes on a private page", async () => {
    mountLangSelector();
    await flushEffects();
    FakeWebSocket.last!.serverOpen();
    await flushEffects();
    expect(sentSetLangMessages()).toHaveLength(1);

    setLang("zh-CN");
    await flushEffects();

    const messages = sentSetLangMessages();
    expect(messages).toHaveLength(2);
    expect(messages[1].v).toEqual({ lang: "zh-CN" });
  });
});
