import { mount, unmount } from "svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { FakeWebSocket } from "$lib/test-utils/fake-websocket";
import { flushEffects } from "$lib/test-utils/flush-effects";
import { websocketClient } from "$lib/ws";
import { WebsocketManager } from "$lib/ws/client.svelte";
import { routeState } from "$lib/ws/route-state.svelte";
import { load } from "./+layout";
import Layout from "./+layout.svelte";

vi.stubGlobal("WebSocket", FakeWebSocket);

describe("TestPublicLayout", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    FakeWebSocket.reset();
    vi.clearAllMocks();
    routeState.public = false;
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe("load", () => {
    it("sets the public flag before any component mounts", async () => {
      // The load event is unused by this layout's load function.
      await load({} as never);
      expect(routeState.public).toBe(true);
    });

    it("tears down a connection a private session left behind", async () => {
      // Simulate a live private-session connection with topic data.
      websocketClient.connect();
      FakeWebSocket.last!.serverOpen();
      websocketClient.sub("ConfigScan");
      FakeWebSocket.last!.serverMessage(JSON.stringify({ t: "ConfigScan", o: "full", v: ["a"] }));
      expect(websocketClient.topics.ConfigScan).toEqual(["a"]);

      await load({} as never);

      expect(routeState.public).toBe(true);
      expect(websocketClient.connectionState).toBe("closed");
      expect(websocketClient.topics).toEqual({});
      expect(websocketClient.topicReady).toEqual({});
      expect(websocketClient.subscriptions).toEqual({});
      // The teardown does not schedule a reconnect.
      vi.advanceTimersByTime(30_000);
      expect(FakeWebSocket.instances).toHaveLength(1);
    });
  });

  describe("layout", () => {
    /** Mounts the layout with a null children snippet. */
    function mountLayout() {
      const target = document.createElement("div");
      document.body.appendChild(target);
      // The children snippet is never rendered in these tests; cast the
      // empty function because Snippet is a branded type that a plain
      // arrow function does not satisfy.
      const component = mount(Layout, { target, props: { children: (() => {}) as never } });
      return { component, target };
    }

    it("clears the public flag when the layout is destroyed", async () => {
      routeState.public = true;
      const { component } = mountLayout();
      await flushEffects();
      expect(routeState.public).toBe(true);

      unmount(component);
      await flushEffects();
      expect(routeState.public).toBe(false);
    });

    it("restores the ability to connect after leaving the public group", async () => {
      routeState.public = true;
      const { component } = mountLayout();
      await flushEffects();

      // While the public layout is mounted, connect() is refused.
      const client = new WebsocketManager();
      client.connect();
      expect(FakeWebSocket.instances).toHaveLength(0);

      // Leaving the group (destroy) clears the flag: connect works again.
      unmount(component);
      await flushEffects();
      client.connect();
      expect(FakeWebSocket.instances).toHaveLength(1);
      FakeWebSocket.last!.serverOpen();
      expect(client.connectionState).toBe("open");
    });
  });
});
