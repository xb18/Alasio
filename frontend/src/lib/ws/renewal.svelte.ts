import { toast } from "svelte-sonner";
import type { RequestEvent } from "./event";

/**
 * Electron token renewal coordinator.
 *
 * Triggered by two events:
 * 1. the server's "renew" control message (rotation event), and
 * 2. an ElectronOnlyError from a restricted rpc (failure fallback).
 *
 * The flow: POST /api/ws/renew (the same-origin request automatically
 * carries the JWT cookie, and under Electron the webRequest injection
 * attaches the current X-Alasio-Token) → submit the one-time code through
 * the ws 'auth' message → success is silent, failure shows a toast.
 *
 * Red lines:
 * - in-flight throttling: concurrent renew() calls share one pending
 *   promise (never two parallel renewals);
 * - a failed renewal never retries by itself (the caller decides, and the
 *   rpc retry path only retries exactly once).
 */

export type RenewalState = "idle" | "renewing" | "submitting" | "success" | "failed";

export interface RenewalCoordinatorOptions {
  /** Fetch implementation, injectable for tests. Defaults to global fetch. */
  fetchImpl?: typeof fetch;
  /** ws payload sender, injectable for tests. */
  sendRaw?: (payload: RequestEvent) => void;
  /** Toast implementation, injectable for tests. */
  toastError?: (message: string, options?: { description?: string }) => void;
}

export class RenewalCoordinator {
  state = $state<RenewalState>("idle");

  #fetchImpl: typeof fetch;
  #sendRaw: (payload: RequestEvent) => void;
  #toastError: (message: string, options?: { description?: string }) => void;
  #pending: Promise<boolean> | null = null;

  constructor(options: RenewalCoordinatorOptions = {}) {
    this.#fetchImpl = options.fetchImpl ?? ((input, init) => fetch(input, init));
    this.#sendRaw = options.sendRaw ?? (() => {});
    this.#toastError = options.toastError ?? ((message, options) => toast.error(message, options));
  }

  /** True while a renewal is in flight (shared by concurrent callers). */
  get isPending(): boolean {
    return this.#pending !== null;
  }

  /**
   * Renew the connection's electron token.
   *
   * In-flight throttling: concurrent calls share the same pending promise
   * and resolve with its result, no second renewal starts.
   *
   * Returns:
   *     Promise<boolean>: True when the renewal succeeded
   */
  renew(): Promise<boolean> {
    if (this.#pending) return this.#pending;
    this.state = "renewing";
    const promise = this.#doRenew();
    this.#pending = promise;
    // clear the pending slot when the renewal settles
    promise.then(
      () => {
        if (this.#pending === promise) this.#pending = null;
      },
      () => {
        if (this.#pending === promise) this.#pending = null;
      },
    );
    return promise;
  }

  async #doRenew(): Promise<boolean> {
    try {
      const response = await this.#fetchImpl("/api/ws/renew", { method: "POST" });
      if (!response.ok) {
        // 401 (not logged in) / 403 (no electron token) / 429 (code table
        // at capacity): a remote or broken session cannot renew. Show the
        // failure and stop (no retry loop).
        this.state = "failed";
        this.#toastError("Token renewal failed", {
          description: `HTTP ${response.status}: unable to renew the electron token`,
        });
        return false;
      }
      const data = await response.json();
      this.state = "submitting";
      this.#sendRaw({ t: "auth", o: "auth", v: data.code });
      this.state = "success";
      return true;
    } catch (err) {
      this.state = "failed";
      this.#toastError("Token renewal failed", {
        description: err instanceof Error ? err.message : String(err),
      });
      return false;
    }
  }
}
