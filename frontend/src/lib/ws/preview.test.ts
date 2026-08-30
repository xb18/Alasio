import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { authState } from "$lib/auth/state.svelte";
import { FakeWebSocket } from "$lib/test-utils/fake-websocket";
import { PreviewManager } from "./preview.svelte";

vi.stubGlobal("WebSocket", FakeWebSocket);

/** Exposes the protected members for assertions. */
class TestPreviewManager extends PreviewManager {
  handleMessage(event: MessageEvent): void {
    this.onMessage(event);
  }
  getUrl(): string {
    return this.getWsUrl();
  }
}

/** Builds a binary message: "Preview" header + payload bytes. */
function previewBuffer(payload: Uint8Array): ArrayBuffer {
  const header = new TextEncoder().encode("Preview");
  const buffer = new Uint8Array(header.length + payload.length);
  buffer.set(header);
  buffer.set(payload, header.length);
  return buffer.buffer;
}

describe("TestPreviewManager", () => {
  beforeEach(() => {
    FakeWebSocket.reset();
    vi.clearAllMocks();
    // PreviewManager inherits the logged-out connect guard; the tests
    // below drive the connection machinery directly.
    authState.loggedIn = true;
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("connects to the /api/preview endpoint", () => {
    expect(new TestPreviewManager().getUrl()).toBe("ws://localhost:3000/api/preview");
  });

  it("sets the Preview topic directly for binary messages with the Preview header", () => {
    const pm = new TestPreviewManager();
    const payload = new Uint8Array([0x01, 0x02, 0x03]);
    const buffer = previewBuffer(payload);

    pm.handleMessage({ data: buffer } as MessageEvent);
    expect(pm.topics["Preview"]).toBe(buffer);
  });

  it("accepts an empty payload after the header", () => {
    const pm = new TestPreviewManager();
    const buffer = previewBuffer(new Uint8Array(0));

    pm.handleMessage({ data: buffer } as MessageEvent);
    expect(pm.topics["Preview"]).toBe(buffer);
  });

  it("delegates binary messages that are too short for the header", () => {
    const pm = new TestPreviewManager();
    const error = vi.spyOn(console, "error").mockImplementation(() => {});

    pm.handleMessage({ data: new TextEncoder().encode("abc").buffer } as MessageEvent);
    expect(pm.topics).not.toHaveProperty("Preview");
    expect(error).toHaveBeenCalled(); // base handler failed to parse json
    error.mockRestore();
  });

  it("delegates binary messages with a different header to the base handler", () => {
    const pm = new TestPreviewManager();
    const error = vi.spyOn(console, "error").mockImplementation(() => {});
    const buffer = new TextEncoder().encode("notpreview").buffer;

    pm.handleMessage({ data: buffer } as MessageEvent);
    expect(pm.topics).not.toHaveProperty("Preview");
    error.mockRestore();
  });

  it("delegates ping text messages to the base handler", () => {
    const pm = new TestPreviewManager();
    pm.connect();
    FakeWebSocket.last!.serverOpen();

    pm.handleMessage({ data: new TextEncoder().encode("ping").buffer } as MessageEvent);
    const pong = FakeWebSocket.last!.sent[FakeWebSocket.last!.sent.length - 1];
    expect(pong).toBeInstanceOf(ArrayBuffer);
    expect(new TextDecoder().decode(pong as ArrayBuffer)).toBe("pong");
  });

  it("delegates json topic events to the base handler", () => {
    const pm = new TestPreviewManager();
    pm.connect();
    FakeWebSocket.last!.serverOpen();

    pm.handleMessage({
      data: new TextEncoder().encode(JSON.stringify({ t: "ConnState", o: "full", v: { lang: "en-US" } })).buffer,
    } as MessageEvent);
    expect(pm.topics.ConnState).toEqual({ lang: "en-US" });
  });
});
