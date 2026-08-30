import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { RenewalCoordinator } from "./renewal.svelte";

/**
 * RenewalCoordinator unit tests (execution plan Phase 7-3): state
 * machine transitions, in-flight throttling, failure paths, and the
 * exact ws submit message structure.
 */

interface Scope {
  coordinator: RenewalCoordinator;
  fetchMock: ReturnType<typeof vi.fn>;
  sendMock: ReturnType<typeof vi.fn>;
  toastMock: ReturnType<typeof vi.fn>;
}

function makeCoordinator(overrides: { fetchImpl?: typeof fetch } = {}): Scope {
  const fetchMock = vi.fn();
  const sendMock = vi.fn();
  const toastMock = vi.fn();
  const coordinator = new RenewalCoordinator({
    fetchImpl: (overrides.fetchImpl ?? fetchMock) as typeof fetch,
    sendRaw: sendMock,
    toastError: toastMock,
  });
  return { coordinator, fetchMock, sendMock, toastMock };
}

function okResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
}

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("TestRenewalStateMachine", () => {
  it("transitions idle → renewing → submitting → success", async () => {
    const { coordinator, fetchMock, sendMock } = makeCoordinator();
    expect(coordinator.state).toBe("idle");

    fetchMock.mockResolvedValue(okResponse({ code: "r-code-123" }));
    const promise = coordinator.renew();
    expect(coordinator.state).toBe("renewing");
    expect(fetchMock).toHaveBeenCalledWith("/api/ws/renew", { method: "POST" });

    const result = await promise;
    expect(result).toBe(true);
    expect(coordinator.state).toBe("success");
    // the one-time code is submitted through the ws 'auth' message
    expect(sendMock).toHaveBeenCalledTimes(1);
    expect(sendMock.mock.calls[0][0]).toEqual({ t: "auth", o: "auth", v: "r-code-123" });
  });

  it("transitions to failed on an http error status", async () => {
    const { coordinator, fetchMock, toastMock } = makeCoordinator();
    fetchMock.mockResolvedValue(new Response(null, { status: 403 }));

    const result = await coordinator.renew();
    expect(result).toBe(false);
    expect(coordinator.state).toBe("failed");
    expect(toastMock).toHaveBeenCalledTimes(1);
  });

  it("transitions to failed when the fetch rejects", async () => {
    const { coordinator, fetchMock, toastMock } = makeCoordinator();
    fetchMock.mockRejectedValue(new Error("network down"));

    const result = await coordinator.renew();
    expect(result).toBe(false);
    expect(coordinator.state).toBe("failed");
    expect(toastMock).toHaveBeenCalledTimes(1);
  });

  it("does not submit a ws message on failure", async () => {
    const { coordinator, fetchMock, sendMock } = makeCoordinator();
    fetchMock.mockResolvedValue(new Response(null, { status: 401 }));

    await coordinator.renew();
    expect(sendMock).not.toHaveBeenCalled();
  });
});

describe("TestRenewalInFlightThrottle", () => {
  it("concurrent calls share the same pending promise", async () => {
    const { coordinator, fetchMock, sendMock } = makeCoordinator();
    let resolveFetch: (r: Response) => void;
    fetchMock.mockImplementation(() => new Promise<Response>((resolve) => (resolveFetch = resolve)));

    const first = coordinator.renew();
    const second = coordinator.renew();
    const third = coordinator.renew();
    // only one fetch started
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(coordinator.isPending).toBe(true);

    resolveFetch!(okResponse({ code: "r1" }));
    const results = await Promise.all([first, second, third]);
    expect(results).toEqual([true, true, true]);
    expect(sendMock).toHaveBeenCalledTimes(1);
    expect(coordinator.isPending).toBe(false);
  });

  it("a new call after a failed renewal starts a fresh attempt", async () => {
    const { coordinator, fetchMock } = makeCoordinator();
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 403 }));

    await coordinator.renew();
    expect(coordinator.state).toBe("failed");

    fetchMock.mockResolvedValueOnce(okResponse({ code: "r2" }));
    const result = await coordinator.renew();
    expect(result).toBe(true);
    expect(coordinator.state).toBe("success");
  });
});

describe("TestRenewalFailureNoRetry", () => {
  it("a failed renewal does not retry by itself", async () => {
    const { coordinator, fetchMock } = makeCoordinator();
    fetchMock.mockResolvedValue(new Response(null, { status: 403 }));

    await coordinator.renew();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    // no timer-based or automatic retry
    await vi.advanceTimersByTimeAsync(60_000);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
