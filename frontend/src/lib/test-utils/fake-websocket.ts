/**
 * A minimal in-memory WebSocket implementation used to drive the
 * WebsocketManager in unit tests. Inject it with
 * `vi.stubGlobal("WebSocket", FakeWebSocket)` — no real network is
 * involved, the "server" side is simulated through the server* helpers.
 *
 * The class is registered as the global WebSocket constructor, so it
 * carries the standard readyState constants. It intentionally does not
 * depend on the DOM's WebSocket or CloseEvent classes: callbacks are
 * invoked with plain object literals cast to the event types, which is
 * all the product code reads.
 */
export class FakeWebSocket {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSING = 2;
  static readonly CLOSED = 3;

  /** Every instance created since the last reset, in creation order. */
  static instances: FakeWebSocket[] = [];

  /** Clears the instance registry. Call it in beforeEach. */
  static reset(): void {
    FakeWebSocket.instances = [];
  }

  /** The most recently created instance, or undefined if none. */
  static get last(): FakeWebSocket | undefined {
    return FakeWebSocket.instances[FakeWebSocket.instances.length - 1];
  }

  url: string;
  readyState = FakeWebSocket.CONNECTING;
  binaryType = "blob";
  /** All send() payloads, normalized to string or ArrayBuffer. */
  sent: Array<string | ArrayBuffer> = [];
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;

  constructor(url: string) {
    this.url = url;
    FakeWebSocket.instances.push(this);
  }

  send(data: string | ArrayBuffer | ArrayBufferView): void {
    if (typeof data === "string") {
      this.sent.push(data);
      return;
    }
    if (data instanceof ArrayBuffer) {
      this.sent.push(data.slice(0));
      return;
    }
    // ArrayBufferView (e.g. Uint8Array from TextEncoder): copy the
    // bytes into a buffer allocated by *this* realm's Uint8Array. In the
    // vitest jsdom environment the global ArrayBuffer belongs to the
    // jsdom realm while TextEncoder comes from the Node realm, so a
    // plain buffer.slice() would produce an ArrayBuffer that fails
    // `instanceof ArrayBuffer` in tests.
    const view = new Uint8Array(data.buffer, data.byteOffset, data.byteLength);
    this.sent.push(new Uint8Array(view).buffer);
  }

  close(code = 1000, reason = ""): void {
    if (this.readyState === FakeWebSocket.CLOSED) return;
    this.readyState = FakeWebSocket.CLOSED;
    this.onclose?.({ code, reason } as CloseEvent);
  }

  // --- Test helpers: simulate the server side ---

  /** Simulates the server accepting the connection (fires onopen). */
  serverOpen(): void {
    this.readyState = FakeWebSocket.OPEN;
    this.onopen?.(new Event("open"));
  }

  /**
   * Simulates an incoming server message. The backend sends everything
   * as bytes (send_bytes, including the "ping" heartbeat), so string
   * arguments are encoded to ArrayBuffer first — exactly what the
   * product code observes in the browser.
   */
  serverMessage(data: string | ArrayBuffer): void {
    const payload = typeof data === "string" ? new TextEncoder().encode(data).buffer : data;
    this.onmessage?.({ data: payload } as MessageEvent);
  }

  /** Simulates the server closing the connection (fires onclose). */
  serverClose(code: number, reason = ""): void {
    this.readyState = FakeWebSocket.CLOSED;
    this.onclose?.({ code, reason } as CloseEvent);
  }
}
