/**
 * Unit tests for the token announcement parsing and chained validation.
 *
 * Run with: npx tsx --test webapp/main/announcement.test.ts
 */
import assert from "node:assert/strict";
import { test } from "node:test";
import { acceptAnnouncement, parseAnnouncement } from "./announcement";

const T1 = "a".repeat(64);
const T2 = "b".repeat(64);
const T3 = "c".repeat(64);

test("parseAnnouncement: accepts the initial begin announcement", () => {
  assert.deepEqual(parseAnnouncement(`[Supervisor] token_set:begin:${T1}`), { old: "begin", next: T1 });
});

test("parseAnnouncement: accepts a rotation announcement", () => {
  assert.deepEqual(parseAnnouncement(`[Supervisor] token_set:${T1}:${T2}`), { old: T1, next: T2 });
});

test("parseAnnouncement: rejects malformed lines", () => {
  assert.equal(parseAnnouncement(""), null);
  assert.equal(parseAnnouncement("[Supervisor] token_set:"), null);
  assert.equal(parseAnnouncement("[Supervisor] token_set:begin"), null);
  assert.equal(parseAnnouncement("[Supervisor] token_set:begin:"), null);
  // wrong prefix
  assert.equal(parseAnnouncement(`[Backend] token_set:begin:${T1}`), null);
  // non-hex token
  assert.equal(parseAnnouncement(`[Supervisor] token_set:begin:xyz${T1.slice(3)}`), null);
  // trailing content
  assert.equal(parseAnnouncement(`[Supervisor] token_set:begin:${T1} extra`), null);
  // uppercase hex rejected (regex is lowercase only)
  assert.equal(parseAnnouncement(`[Supervisor] token_set:begin:${T1.toUpperCase()}`), null);
});

test("acceptAnnouncement: accepts begin when current is null", () => {
  assert.equal(acceptAnnouncement(null, "begin", T1), T1);
});

test("acceptAnnouncement: ignores a forged begin after the chain started", () => {
  // once authToken is non-null, begin:<fake> can never match
  assert.equal(acceptAnnouncement(T1, "begin", T2), null);
});

test("acceptAnnouncement: accepts a rotation when old matches current", () => {
  assert.equal(acceptAnnouncement(T1, T1, T2), T2);
});

test("acceptAnnouncement: ignores a rotation when old mismatches", () => {
  // forged / out-of-chain announcement: old != current
  assert.equal(acceptAnnouncement(T1, T2, T3), null);
  assert.equal(acceptAnnouncement(T1, "begin", T3), null);
});

test("acceptAnnouncement: a forged announcement cannot collide with the chain", () => {
  // the attacker does not know the current token; a begin sentinel after
  // the chain started and a random old token are both rejected
  let current: string | null = null;
  const step = (line: string) => {
    const parsed = parseAnnouncement(line);
    if (!parsed) return null;
    const next = acceptAnnouncement(current, parsed.old, parsed.next);
    if (next) current = next;
    return next;
  };

  // legitimate chain
  assert.equal(step(`[Supervisor] token_set:begin:${T1}`), T1);
  assert.equal(step(`[Supervisor] token_set:${T1}:${T2}`), T2);
  // forged attempts after the chain started
  assert.equal(step(`[Supervisor] token_set:begin:${T3}`), null);
  assert.equal(step(`[Supervisor] token_set:${T1}:${T3}`), null);
  // current unchanged
  assert.equal(current, T2);
});
