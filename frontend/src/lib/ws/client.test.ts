import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { goto, invalidateAll } from "$app/navigation";
import { FakeWebSocket } from "$lib/test-utils/fake-websocket";
import { WebsocketManager } from "./client.svelte";

// The product code uses the global WebSocket constructor; tests drive
// the "server" side through the FakeWebSocket helpers.
vi.stubGlobal("WebSocket", FakeWebSocket);

const decodeText = (payload: string | ArrayBuffer): string =>
  typeof payload === "string" ? payload : new TextDecoder().decode(payload);

const parseSent = (payload: string | ArrayBuffer): any => JSON.parse(decodeText(payload));

/** Returns the JSON of the last message the client sent. */
function lastSent(ws: FakeWebSocket): any {
  return parseSent(ws.sent[ws.sent.length - 1]);
}

/** Exposes the protected members for assertions. */
class TestClient extends WebsocketManager {
  getUrl(): string {
    return this.getWsUrl();
  }
  handleMessage(event: MessageEvent): void {
    this.onMessage(event);
  }
}

/**
 * Simulates the server dropping the current connection and the client
 * reconnecting after `delayMs` of backoff. Returns the new socket.
 */
function dropAndReconnect(delayMs: number): FakeWebSocket {
  FakeWebSocket.last!.serverClose(1006);
  vi.advanceTimersByTime(delayMs);
  return FakeWebSocket.last!;
}

describe("TestGetWsUrl", () => {
  it("converts http to ws and appends /api/ws", () => {
    const client = new TestClient();
    expect(client.getUrl()).toBe("ws://localhost:3000/api/ws");
  });

  it("derives the ws protocol from the current page protocol", () => {
    const url = new TestClient().getUrl();
    expect(url.startsWith("ws://")).toBe(true);
    expect(url).not.toContain("http://");
  });
});

describe("TestConnect", () => {
  it("creates a websocket and transitions to open", () => {
    const client = new WebsocketManager();
    expect(client.connectionState).toBe("closed");

    client.connect();
    expect(FakeWebSocket.instances).toHaveLength(1);
    expect(FakeWebSocket.last!.url).toBe("ws://localhost:3000/api/ws");
    expect(FakeWebSocket.last!.binaryType).toBe("arraybuffer");
    expect(client.connectionState).toBe("connecting");

    FakeWebSocket.last!.serverOpen();
    expect(client.connectionState).toBe("open");
    expect(client.connectionGeneration).toBe(1);
  });

  it("is a no-op while connecting", () => {
    const client = new WebsocketManager();
    client.connect();
    client.connect();
    expect(FakeWebSocket.instances).toHaveLength(1);
  });

  it("is a no-op while open", () => {
    const client = new WebsocketManager();
    client.connect();
    FakeWebSocket.last!.serverOpen();
    client.connect();
    expect(FakeWebSocket.instances).toHaveLength(1);
  });

  it("uses the reconnecting state after a previous failed attempt", () => {
    const client = new WebsocketManager();
    client.connect();
    FakeWebSocket.last!.serverOpen();
    FakeWebSocket.last!.serverClose(1006);
    vi.advanceTimersByTime(1000);

    expect(FakeWebSocket.instances).toHaveLength(2);
    expect(client.connectionState).toBe("reconnecting");

    FakeWebSocket.last!.serverOpen();
    expect(client.connectionState).toBe("open");
  });
});

describe("TestConnectionGeneration", () => {
  it("increments on every successful open", () => {
    const client = new WebsocketManager();
    client.connect();
    FakeWebSocket.last!.serverOpen();
    expect(client.connectionGeneration).toBe(1);

    dropAndReconnect(1000).serverOpen();
    expect(client.connectionGeneration).toBe(2);

    dropAndReconnect(1000).serverOpen();
    expect(client.connectionGeneration).toBe(3);
  });
});

describe("TestTopicReady", () => {
  it("marks default subscriptions ready on open and clears them on close", () => {
    const client = new WebsocketManager();
    expect(client.topicReady).toEqual({});

    client.connect();
    FakeWebSocket.last!.serverOpen();
    expect(client.topicReady).toEqual({ ConnState: true });

    FakeWebSocket.last!.serverClose(1006);
    expect(client.topicReady).toEqual({});
  });

  it("tracks ready state per topic after subscription", () => {
    const client = new WebsocketManager();
    client.connect();
    FakeWebSocket.last!.serverOpen();
    client.sub("ConfigScan");
    FakeWebSocket.last!.serverMessage(JSON.stringify({ t: "ConfigScan", o: "full", v: [] }));

    expect(client.topicReady).toEqual({ ConnState: true });

    client.unsub("ConfigScan");
    expect(client.topicReady).toEqual({ ConnState: true });
    expect(client.topics).not.toHaveProperty("ConfigScan");
  });
});

describe("TestSubscriptionCount", () => {
  it("counts reference increments on repeated sub", () => {
    const client = new WebsocketManager();
    client.sub("ConfigScan");
    client.sub("ConfigScan");
    expect(client.subscriptions).toEqual({ ConfigScan: 2 });
  });

  it("does not send the sub message before the connection opens, but resubscribes on open", () => {
    const client = new WebsocketManager();
    client.sub("ConfigScan");
    expect(FakeWebSocket.last!.sent).toHaveLength(0);

    FakeWebSocket.last!.serverOpen();
    expect(FakeWebSocket.last!.sent).toHaveLength(1);
    expect(lastSent(FakeWebSocket.last!)).toEqual({ t: "ConfigScan" });
  });

  it("sends the sub message immediately when the connection is already open", () => {
    const client = new WebsocketManager();
    client.connect();
    FakeWebSocket.last!.serverOpen();

    client.sub("ConfigScan");
    expect(lastSent(FakeWebSocket.last!)).toEqual({ t: "ConfigScan" });
  });

  it("does not send sub for default subscriptions (already subscribed server-side)", () => {
    const client = new WebsocketManager();
    client.connect();
    FakeWebSocket.last!.serverOpen();

    client.sub("ConnState");
    expect(FakeWebSocket.last!.sent).toHaveLength(0);
    expect(client.subscriptions).toEqual({ ConnState: 1 });
  });

  it("decrements on unsub and sends unsub only when the count reaches zero", () => {
    const client = new WebsocketManager();
    client.connect();
    FakeWebSocket.last!.serverOpen();
    client.sub("ConfigScan");
    client.sub("ConfigScan");
    FakeWebSocket.last!.sent.length = 0;

    client.unsub("ConfigScan");
    expect(client.subscriptions).toEqual({ ConfigScan: 1 });
    expect(FakeWebSocket.last!.sent).toHaveLength(0);

    client.unsub("ConfigScan");
    expect(client.subscriptions).not.toHaveProperty("ConfigScan");
    expect(FakeWebSocket.last!.sent).toHaveLength(1);
    expect(lastSent(FakeWebSocket.last!)).toEqual({ t: "ConfigScan", o: "unsub" });
  });

  it("cleans up topic data when the last reference unsubscribes", () => {
    const client = new WebsocketManager();
    client.connect();
    FakeWebSocket.last!.serverOpen();
    client.sub("ConfigScan");
    FakeWebSocket.last!.serverMessage(JSON.stringify({ t: "ConfigScan", o: "full", v: ["a"] }));
    expect(client.topics.ConfigScan).toEqual(["a"]);

    client.unsub("ConfigScan");
    expect(client.topics).not.toHaveProperty("ConfigScan");
  });

  it("ignores unsub for default subscriptions", () => {
    const client = new WebsocketManager();
    client.connect();
    FakeWebSocket.last!.serverOpen();
    client.sub("ConnState");
    FakeWebSocket.last!.sent.length = 0;

    client.unsub("ConnState");
    expect(client.subscriptions).toEqual({ ConnState: 1 });
    expect(FakeWebSocket.last!.sent).toHaveLength(0);
  });

  it("sends unsub with forceSend even when other references remain", () => {
    const client = new WebsocketManager();
    client.connect();
    FakeWebSocket.last!.serverOpen();
    client.sub("ConfigScan");
    client.sub("ConfigScan");
    FakeWebSocket.last!.sent.length = 0;

    client.unsub("ConfigScan", true);
    expect(FakeWebSocket.last!.sent).toHaveLength(1);
    expect(lastSent(FakeWebSocket.last!)).toEqual({ t: "ConfigScan", o: "unsub" });
    // count kept, data kept: only the message was forced
    expect(client.subscriptions).toEqual({ ConfigScan: 1 });
  });

  it("unsubAll unsubscribes every topic", () => {
    const client = new WebsocketManager();
    client.connect();
    FakeWebSocket.last!.serverOpen();
    client.sub("ConfigScan");
    client.sub("Worker");

    FakeWebSocket.last!.sent.length = 0;
    client.unsubAll();
    expect(client.subscriptions).toEqual({});
    expect(FakeWebSocket.last!.sent).toHaveLength(2);
  });
});

describe("TestMessageDispatch", () => {
  it("answers server ping with a binary pong", () => {
    const client = new WebsocketManager();
    client.connect();
    FakeWebSocket.last!.serverOpen();

    FakeWebSocket.last!.serverMessage("ping");
    const pong = FakeWebSocket.last!.sent[FakeWebSocket.last!.sent.length - 1];
    expect(pong).toBeInstanceOf(ArrayBuffer);
    expect(decodeText(pong)).toBe("pong");
  });

  it("dispatches a successful rpc response to the registered callback", () => {
    const client = new WebsocketManager();
    client.connect();
    FakeWebSocket.last!.serverOpen();
    const onSuccess = vi.fn();
    const onError = vi.fn();
    client.registerRpcCall("id-1", { onSuccess, onError });

    FakeWebSocket.last!.serverMessage(JSON.stringify({ t: "ConnState", i: "id-1" }));
    expect(onSuccess).toHaveBeenCalledWith("id-1");
    expect(onError).not.toHaveBeenCalled();
  });

  it("dispatches an rpc error response to onError with the value as string", () => {
    const client = new WebsocketManager();
    client.connect();
    FakeWebSocket.last!.serverOpen();
    const onSuccess = vi.fn();
    const onError = vi.fn();
    client.registerRpcCall("id-2", { onSuccess, onError });

    FakeWebSocket.last!.serverMessage(JSON.stringify({ t: "ConnState", i: "id-2", v: "boom" }));
    expect(onError).toHaveBeenCalledWith("boom");
    expect(onSuccess).not.toHaveBeenCalled();
  });

  it("discards rpc responses without a registered callback", () => {
    const client = new WebsocketManager();
    client.connect();
    FakeWebSocket.last!.serverOpen();
    expect(() => {
      FakeWebSocket.last!.serverMessage(JSON.stringify({ t: "ConnState", i: "unknown-id" }));
    }).not.toThrow();
  });

  it("handles a batch of events in one message", () => {
    const client = new WebsocketManager();
    client.connect();
    FakeWebSocket.last!.serverOpen();

    FakeWebSocket.last!.serverMessage(
      JSON.stringify([
        { t: "ConnState", o: "full", v: { lang: "en-US" } },
        { t: "ConnState", o: "set", k: ["lang"], v: "zh-CN" },
      ]),
    );
    expect(client.topics.ConnState).toEqual({ lang: "zh-CN" });
  });

  it("does not throw on invalid json, logs it instead", () => {
    const client = new WebsocketManager();
    client.connect();
    FakeWebSocket.last!.serverOpen();
    const error = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => {
      FakeWebSocket.last!.serverMessage("this is not json");
    }).not.toThrow();
    expect(error).toHaveBeenCalled();
    error.mockRestore();
  });

  it("throws on non-binary text messages: decode runs outside the try block", () => {
    // Known limitation pinned as current behavior (see doc §8.5.3):
    // event.data is assumed to be an ArrayBuffer (the backend always
    // send_bytes, including the ping heartbeat), so a text frame
    // reaches TextDecoder.decode and throws out of the event callback.
    const client = new TestClient();
    client.connect();
    FakeWebSocket.last!.serverOpen();

    expect(() => {
      client.handleMessage({ data: "ping" } as MessageEvent);
    }).toThrow(TypeError);
  });
});

describe("TestTopicDataEvents", () => {
  it("replaces the whole topic on full", () => {
    const client = new WebsocketManager();
    client.connect();
    FakeWebSocket.last!.serverOpen();

    const value = { lang: "en-US", config_name: "", mod_name: "", nav_name: "" };
    FakeWebSocket.last!.serverMessage(JSON.stringify({ t: "ConnState", o: "full", v: value }));
    expect(client.topics.ConnState).toEqual(value);
  });

  it("applies set with a key path via deepSet", () => {
    const client = new WebsocketManager();
    client.connect();
    FakeWebSocket.last!.serverOpen();
    FakeWebSocket.last!.serverMessage(JSON.stringify({ t: "ConnState", o: "full", v: { lang: "en-US" } }));

    FakeWebSocket.last!.serverMessage(JSON.stringify({ t: "ConnState", o: "set", k: ["lang"], v: "zh-CN" }));
    expect(client.topics.ConnState.lang).toBe("zh-CN");
  });

  it("creates intermediate objects when the topic data is undefined", () => {
    const client = new WebsocketManager();
    client.connect();
    FakeWebSocket.last!.serverOpen();

    FakeWebSocket.last!.serverMessage(JSON.stringify({ t: "ConnState", o: "set", k: ["a", "b"], v: 1 }));
    expect(client.topics.ConnState).toEqual({ a: { b: 1 } });
  });

  it("applies del with a key path via deepDel", () => {
    const client = new WebsocketManager();
    client.connect();
    FakeWebSocket.last!.serverOpen();
    FakeWebSocket.last!.serverMessage(
      JSON.stringify({ t: "ConnState", o: "full", v: { lang: "en-US", nav_name: "overview" } }),
    );

    FakeWebSocket.last!.serverMessage(JSON.stringify({ t: "ConnState", o: "del", k: ["nav_name"] }));
    expect(client.topics.ConnState).toEqual({ lang: "en-US" });
  });

  it("defaults the operation to add and replaces the topic when keys are empty", () => {
    const client = new WebsocketManager();
    client.connect();
    FakeWebSocket.last!.serverOpen();

    FakeWebSocket.last!.serverMessage(JSON.stringify({ t: "ConnState", v: { lang: "ja-JP" } }));
    expect(client.topics.ConnState).toEqual({ lang: "ja-JP" });
  });

  it("discards events for topics the client is not subscribed to", () => {
    const client = new WebsocketManager();
    client.connect();
    FakeWebSocket.last!.serverOpen();

    FakeWebSocket.last!.serverMessage(JSON.stringify({ t: "NoSuchTopic", o: "full", v: 1 }));
    expect(client.topics).not.toHaveProperty("NoSuchTopic");
  });

  it("drops path events when the topic data is null: deepSet throws and onMessage swallows it", () => {
    // Known limitation pinned as current behavior (see doc §8.5.1): a
    // root set to null makes every later path set/add silently fail —
    // deepSet(null, ...) throws TypeError, onMessage catches and logs.
    const client = new WebsocketManager();
    client.connect();
    FakeWebSocket.last!.serverOpen();
    const error = vi.spyOn(console, "error").mockImplementation(() => {});

    FakeWebSocket.last!.serverMessage(JSON.stringify({ t: "ConnState", o: "set", k: [], v: null }));
    expect(client.topics.ConnState).toBeNull();

    FakeWebSocket.last!.serverMessage(JSON.stringify({ t: "ConnState", o: "set", k: ["lang"], v: "zh-CN" }));
    expect(client.topics.ConnState).toBeNull();
    expect(error).toHaveBeenCalled();
    error.mockRestore();
  });
});

describe("TestScrollTopic", () => {
  it("initializes the scroll topic cache on sub", () => {
    const client = new WebsocketManager();
    expect(client.topics).not.toHaveProperty("Log");
    client.sub("Log");
    expect(client.topics.Log).toEqual([]);
  });

  it("buffers add events and flushes them", () => {
    const client = new WebsocketManager();
    client.connect();
    FakeWebSocket.last!.serverOpen();
    client.sub("Log");

    FakeWebSocket.last!.serverMessage(JSON.stringify({ t: "Log", o: "add", v: { line: 1 } }));
    // buffered, not yet applied
    expect(client.topics.Log).toEqual([]);

    vi.advanceTimersByTime(0);
    expect(client.topics.Log).toEqual([{ line: 1 }]);
  });

  it("flushes immediately when the buffer exceeds 50 events", () => {
    const client = new WebsocketManager();
    client.connect();
    FakeWebSocket.last!.serverOpen();
    client.sub("Log");

    const events = Array.from({ length: 51 }, (_, i) => ({ t: "Log", o: "add", v: { line: i } }));
    FakeWebSocket.last!.serverMessage(JSON.stringify(events));
    expect(client.topics.Log).toHaveLength(51);
  });

  it("truncates to the max length of 500, keeping the newest lines", () => {
    const client = new WebsocketManager();
    client.connect();
    FakeWebSocket.last!.serverOpen();
    client.sub("Log");

    const full = Array.from({ length: 500 }, (_, i) => ({ t: "Log", o: "add", v: { line: i } }));
    FakeWebSocket.last!.serverMessage(JSON.stringify(full));
    expect(client.topics.Log).toHaveLength(500);

    const tail = Array.from({ length: 10 }, (_, i) => ({ t: "Log", o: "add", v: { line: 500 + i } }));
    FakeWebSocket.last!.serverMessage(JSON.stringify(tail));
    vi.advanceTimersByTime(0);

    expect(client.topics.Log).toHaveLength(500);
    expect(client.topics.Log[0]).toEqual({ line: 10 });
    expect(client.topics.Log[499]).toEqual({ line: 509 });
  });

  it("replaces the whole log on full", () => {
    const client = new WebsocketManager();
    client.connect();
    FakeWebSocket.last!.serverOpen();
    client.sub("Log");

    FakeWebSocket.last!.serverMessage(
      JSON.stringify({ t: "Log", o: "full", v: [{ line: "fresh" }, { line: "history" }] }),
    );
    vi.advanceTimersByTime(0);
    expect(client.topics.Log).toEqual([{ line: "fresh" }, { line: "history" }]);
  });

  it("resets to an empty array when full carries a non-array value", () => {
    const client = new WebsocketManager();
    client.connect();
    FakeWebSocket.last!.serverOpen();
    client.sub("Log");
    FakeWebSocket.last!.serverMessage(JSON.stringify({ t: "Log", o: "add", v: { line: 1 } }));
    vi.advanceTimersByTime(0);
    expect(client.topics.Log).toHaveLength(1);

    FakeWebSocket.last!.serverMessage(JSON.stringify({ t: "Log", o: "full", v: null }));
    vi.advanceTimersByTime(0);
    expect(client.topics.Log).toEqual([]);
  });
});

describe("TestReconnect", () => {
  it("backs off exponentially on consecutive failures: 1s, 2s, 4s, 8s, 16s", () => {
    const client = new WebsocketManager();
    client.connect();
    FakeWebSocket.last!.serverOpen();

    // Each reconnect attempt is created but never opens, so the backoff
    // counter keeps growing across the five attempts.
    let expectedInstances = 1;
    for (const delay of [1000, 2000, 4000, 8000, 16000]) {
      FakeWebSocket.last!.serverClose(1006);
      vi.advanceTimersByTime(delay - 1);
      expect(FakeWebSocket.instances).toHaveLength(expectedInstances); // not reconnected yet
      vi.advanceTimersByTime(1);
      expectedInstances += 1;
      expect(FakeWebSocket.instances).toHaveLength(expectedInstances);
    }
  });

  it("stops after 5 failed attempts and invalidates all data", () => {
    const client = new WebsocketManager();
    client.connect();
    FakeWebSocket.last!.serverOpen();

    // 5 consecutive failures without a successful open: each reconnect
    // is created but never opens, so the backoff counter keeps growing.
    for (const [index, delay] of [1000, 2000, 4000, 8000, 16000].entries()) {
      FakeWebSocket.last!.serverClose(1006);
      vi.advanceTimersByTime(delay);
      expect(FakeWebSocket.instances).toHaveLength(index + 2);
    }

    expect(invalidateAll).not.toHaveBeenCalled();
    const count = FakeWebSocket.instances.length;
    // The 6th failure hits the attempt cap: no new socket, data invalidated.
    FakeWebSocket.last!.serverClose(1006);
    vi.advanceTimersByTime(60000);

    expect(FakeWebSocket.instances).toHaveLength(count);
    expect(invalidateAll).toHaveBeenCalledTimes(1);
  });

  it("resets the backoff sequence after a successful reconnect", () => {
    const client = new WebsocketManager();
    client.connect();
    FakeWebSocket.last!.serverOpen();

    FakeWebSocket.last!.serverClose(1006);
    vi.advanceTimersByTime(1000);
    FakeWebSocket.last!.serverOpen();

    // The next backoff restarts at 1s instead of continuing at 2s.
    FakeWebSocket.last!.serverClose(1006);
    vi.advanceTimersByTime(1000);
    expect(FakeWebSocket.instances).toHaveLength(3);
  });

  it("keeps topic data on a normal close and clears topicReady", () => {
    const client = new WebsocketManager();
    client.connect();
    FakeWebSocket.last!.serverOpen();
    FakeWebSocket.last!.serverMessage(JSON.stringify({ t: "ConnState", o: "full", v: { lang: "en-US" } }));

    FakeWebSocket.last!.serverClose(1000);
    expect(client.topics.ConnState).toEqual({ lang: "en-US" });
    expect(client.topicReady).toEqual({});
  });

  it("redirects to login and clears data on close code 4001", () => {
    const client = new WebsocketManager();
    client.connect();
    FakeWebSocket.last!.serverOpen();
    FakeWebSocket.last!.serverMessage(JSON.stringify({ t: "ConnState", o: "full", v: { lang: "en-US" } }));

    FakeWebSocket.last!.serverClose(4001);
    expect(goto).toHaveBeenCalledWith("/auth/login");
    expect(client.topics).toEqual({});
    expect(client.topicReady).toEqual({});
  });

  it("invalidates all data on other 4xxx close codes", () => {
    const client = new WebsocketManager();
    client.connect();
    FakeWebSocket.last!.serverOpen();
    FakeWebSocket.last!.serverMessage(JSON.stringify({ t: "ConnState", o: "full", v: { lang: "en-US" } }));

    FakeWebSocket.last!.serverClose(4002);
    expect(invalidateAll).toHaveBeenCalledTimes(1);
    expect(client.topics).toEqual({});
  });
});

describe("TestMessageQueue", () => {
  it("queues messages sent while disconnected and replays them on open", () => {
    const client = new WebsocketManager();
    client.sendRaw({ t: "ConfigScan" });
    expect(FakeWebSocket.last!.sent).toHaveLength(0);

    FakeWebSocket.last!.serverOpen();
    expect(FakeWebSocket.last!.sent).toHaveLength(1);
    expect(lastSent(FakeWebSocket.last!)).toEqual({ t: "ConfigScan" });
  });

  it("resubscribes active subscriptions after reconnect", () => {
    const client = new WebsocketManager();
    client.connect();
    FakeWebSocket.last!.serverOpen();
    client.sub("ConfigScan");
    expect(lastSent(FakeWebSocket.last!)).toEqual({ t: "ConfigScan" });

    dropAndReconnect(1000).serverOpen();
    expect(lastSent(FakeWebSocket.last!)).toEqual({ t: "ConfigScan" });
  });

  it("serializes the payload with the exact protocol shape", () => {
    const client = new WebsocketManager();
    client.sendRaw({ t: "ConfigScan", o: "rpc", f: "config_add", v: { name: "a" }, i: "rpc-1" });
    FakeWebSocket.last!.serverOpen();
    expect(decodeText(FakeWebSocket.last!.sent[0] as ArrayBuffer)).toBe(
      '{"t":"ConfigScan","o":"rpc","f":"config_add","v":{"name":"a"},"i":"rpc-1"}',
    );
  });
});

beforeEach(() => {
  vi.useFakeTimers();
  // Route the animation-frame flush of scroll topics through a fake
  // timer so vi.advanceTimersByTime controls it.
  vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => {
    setTimeout(() => cb(0), 0);
    return 0;
  });
  FakeWebSocket.reset();
  vi.clearAllMocks();
});

afterEach(() => {
  vi.useRealTimers();
});
