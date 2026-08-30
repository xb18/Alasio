/**
 * Token announcement parsing and chained validation.
 *
 * The supervisor announces tokens to stdout as `[Supervisor] token_set:...`
 * lines. The announcement stream is chained: the first announcement uses
 * the sentinel `begin` as the old token, every rotation announcement must
 * reference the currently accepted token. A forged announcement can match
 * the format, but the attacker (worker/subprocess print + newline
 * injection) does not know the current token — it only lives in the
 * supervisor / backend / Electron memory — so a forgery can never match
 * the chain. This is defense against intentional forgery, the regex is
 * only the first filter.
 */

// begin | <old 64-hex> : <new 64-hex>
export const ANNOUNCEMENT_RE = /^\[Supervisor\] token_set:(begin|[0-9a-f]{64}):([0-9a-f]{64})$/;

/**
 * Parse one stdout line into an announcement.
 *
 * Args:
 *     line (string): One complete line without the trailing newline
 *
 * Returns:
 *     { old: string; next: string } | null: The announcement, or null
 *     when the line is not a valid announcement
 */
export function parseAnnouncement(line: string): { old: string; next: string } | null {
  const match = ANNOUNCEMENT_RE.exec(line);
  if (!match) return null;
  return { old: match[1], next: match[2] };
}

/**
 * Accept an announcement only when it continues the chain.
 *
 * Args:
 *     current (string | null): The currently accepted token, null before
 *         the first announcement
 *     old (string): The old token claimed by the announcement
 *     next (string): The new token carried by the announcement
 *
 * Returns:
 *     string | null: The new token to accept, or null to ignore the
 *     announcement (forged / out-of-chain)
 */
export function acceptAnnouncement(current: string | null, old: string, next: string): string | null {
  if (current === null) {
    // initial announcement: only the begin sentinel matches
    return old === "begin" ? next : null;
  }
  // rotation announcement: old must equal the currently accepted token.
  // Once a begin announcement was accepted, a later begin:<fake> can
  // never match (current is non-null).
  return old === current ? next : null;
}
