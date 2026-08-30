import { effect_root } from "svelte/internal/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { authState } from "$lib/auth/state.svelte";
import { FakeWebSocket } from "$lib/test-utils/fake-websocket";
import { flushEffects } from "$lib/test-utils/flush-effects";
import { WebsocketManager } from "./client.svelte";
import { useTopic } from "./topic.svelte";

vi.stubGlobal("WebSocket", FakeWebSocket);

/**
 * useTopic is a thin wrapper over WebsocketManager: it owns the
 * sub/unsub lifecycle through $effect and mirrors `client.topics[topic]`
 * into a reactive signal. The subscription lifecycle and the rpc
 * factories are exercised here with effect_root (the non-component
 * equivalent of a component instance). The reactive data mirroring
 * itself depends on component render semantics in svelte 5.56 and is
 * covered indirectly by the WebsocketManager topic-data tests.
 */
describe("TestUseTopic", () => {
  let client: WebsocketManager;
  let stopEffect: (() => void) | undefined;

  beforeEach(() => {
    FakeWebSocket.reset();
    vi.clearAllMocks();
    // useTopic -> sub -> connect: the logged-out guard would block the
    // connection, so default to the logged-in state.
    authState.loggedIn = true;
    client = new WebsocketManager();
  });

  afterEach(async () => {
    stopEffect?.();
    stopEffect = undefined;
    await flushEffects();
  });

  it("subscribes to the topic while the effect is alive", async () => {
    let lifespan: ReturnType<typeof useTopic>;
    stopEffect = effect_root(() => {
      lifespan = useTopic("ConfigScan", client);
    });
    await flushEffects();
    expect(client.subscriptions).toEqual({ ConfigScan: 1 });
  });

  it("unsubscribes when the effect root stops", async () => {
    let lifespan: ReturnType<typeof useTopic>;
    stopEffect = effect_root(() => {
      lifespan = useTopic("ConfigScan", client);
    });
    await flushEffects();
    expect(client.subscriptions).toEqual({ ConfigScan: 1 });

    stopEffect();
    stopEffect = undefined;
    await flushEffects();
    expect(client.subscriptions).toEqual({});
  });

  it("rpc factory sends topic-scoped rpc payloads", async () => {
    let lifespan!: ReturnType<typeof useTopic>;
    stopEffect = effect_root(() => {
      lifespan = useTopic("ConfigScan", client);
    });
    await flushEffects();
    client.connect();
    FakeWebSocket.last!.serverOpen();
    FakeWebSocket.last!.sent.length = 0;

    const rpc = lifespan.rpc();
    rpc.call("config_add", { name: "a", mod: "m" });
    const raw = FakeWebSocket.last!.sent[0];
    const text = typeof raw === "string" ? raw : new TextDecoder().decode(raw);
    expect(JSON.parse(text)).toEqual({
      t: "ConfigScan",
      o: "rpc",
      f: "config_add",
      v: { name: "a", mod: "m" },
      i: expect.any(String),
    });
  });

  it("resilient rpc factory is available", async () => {
    let lifespan: ReturnType<typeof useTopic>;
    stopEffect = effect_root(() => {
      lifespan = useTopic("ConfigScan", client);
    });
    await flushEffects();
    client.connect();
    FakeWebSocket.last!.serverOpen();
    FakeWebSocket.last!.sent.length = 0;

    // The factory must be created inside an effect root: createResilientRpc
    // owns a $effect that needs a root in non-component tests.
    let resilientRpc!: ReturnType<ReturnType<typeof useTopic>["resilientRpc"]>;
    const stopRoot = effect_root(() => {
      resilientRpc = lifespan.resilientRpc();
    });
    await flushEffects();
    resilientRpc.call("config_del", { name: "a" });
    expect(FakeWebSocket.last!.sent).toHaveLength(1);
    stopRoot();
  });
});
