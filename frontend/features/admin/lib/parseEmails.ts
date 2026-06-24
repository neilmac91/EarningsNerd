/**
 * Pure, dependency-free email tokenizer for the bulk-invite field. Splits a raw blob on
 * commas / whitespace / newlines / semicolons, trims, lowercases, dedupes (on the normalized
 * form), and partitions into valid vs invalid addresses. Deterministic and unit-testable —
 * no side effects, no I/O.
 */

// A pragmatic, sane email regex: a local part (no spaces/@), an @, a dotted domain, and a
// final TLD of 2+ letters. Intentionally not RFC 5322-exhaustive — it rejects the common typos
// (missing @, no TLD, trailing dot, internal spaces) without false-rejecting normal addresses.
const EMAIL_RE = /^[^\s@]+@[^\s@.]+(?:\.[^\s@.]+)*\.[A-Za-z]{2,}$/

/** True when `email` looks like a syntactically valid address. Case-insensitive. */
export function classifyEmail(email: string): boolean {
  return EMAIL_RE.test(email.trim().toLowerCase())
}

export interface ParseEmailsResult {
  valid: string[]
  invalid: string[]
}

/**
 * Tokenize a raw string into valid + invalid email lists. Both lists are deduped on the
 * normalized (trimmed + lowercased) value, preserving first-seen order. Empty tokens are
 * dropped silently.
 */
export function parseEmails(raw: string): ParseEmailsResult {
  const valid: string[] = []
  const invalid: string[] = []
  const seen = new Set<string>()

  for (const token of raw.split(/[\s,;]+/)) {
    const normalized = token.trim().toLowerCase()
    if (!normalized) continue
    if (seen.has(normalized)) continue
    seen.add(normalized)

    if (classifyEmail(normalized)) {
      valid.push(normalized)
    } else {
      invalid.push(normalized)
    }
  }

  return { valid, invalid }
}
