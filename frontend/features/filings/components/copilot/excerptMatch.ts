/**
 * Locate a citation excerpt within filing text for the in-app viewer (P7).
 *
 * The challenge: a citation `excerpt` is verbatim-ish text the model copied from the filing's raw
 * markdown, but the viewer renders that markdown (ReactMarkdown), so the on-screen text has dropped
 * syntax (`**bold**` → "bold", `## Head` → "Head", `| a | b |` → "a b") and collapsed whitespace.
 * A naive substring search therefore fails. We match on an **alphanumeric-only, lowercased
 * projection** of both strings (which is invariant to markdown punctuation and whitespace) while
 * keeping an index map so the match maps back to offsets in the *original* text the caller rendered.
 *
 * The caller (FilingViewer) builds a flat text string from the rendered DOM's text nodes plus a
 * parallel offset→node map, runs {@link findExcerptMatch} on that flat text, and turns the returned
 * `[start, end)` offsets into a DOM Range to scroll to and flash-highlight.
 */

// Minimum normalized (alphanumeric) length we'll attempt to match — mirrors the backend's
// verification floor so we don't highlight on a too-short, ambiguous fragment.
export const MIN_MATCH_LEN = 16

export interface ExcerptMatch {
  /** Start offset (inclusive) in the original haystack string. */
  start: number
  /** End offset (exclusive) in the original haystack string. */
  end: number
}

interface Normalized {
  norm: string
  /** map[i] = index in the original string of the i-th normalized character. */
  map: number[]
}

const ALNUM = /[a-z0-9]/

function normalizeWithMap(text: string): Normalized {
  let norm = ''
  const map: number[] = []
  for (let i = 0; i < text.length; i++) {
    const ch = text[i].toLowerCase()
    if (ALNUM.test(ch)) {
      norm += ch
      map.push(i)
    }
  }
  return { norm, map }
}

// If the excerpt wraps the real quote in quotation marks (e.g. `Item 7: "Revenue rose 8%."`),
// match on the quoted span only — mirrors the backend's extract_quoted_span intent.
function stripToQuoted(excerpt: string): string {
  const m = excerpt.match(/["“”']{1}([^"“”']{8,})["“”']{1}/)
  return m ? m[1] : excerpt
}

/**
 * Find `excerpt` within `haystack`, tolerant of markdown punctuation and whitespace differences.
 * Returns original-string `[start, end)` offsets, or null if no confident match.
 */
export function findExcerptMatch(haystack: string, excerpt: string): ExcerptMatch | null {
  if (!haystack || !excerpt) return null

  const needle = normalizeWithMap(stripToQuoted(excerpt)).norm
  if (needle.length < MIN_MATCH_LEN) return null

  const { norm, map } = normalizeWithMap(haystack)
  if (!norm) return null

  const exact = norm.indexOf(needle)
  if (exact !== -1) {
    return { start: map[exact], end: map[exact + needle.length - 1] + 1 }
  }

  // Fallback: the model sometimes appends/edits a trailing clause not present verbatim in the
  // source. Try a leading slice (>=60%, but at least MIN_MATCH_LEN) so we can still anchor the
  // highlight to the passage's beginning.
  const prefixLen = Math.max(MIN_MATCH_LEN, Math.floor(needle.length * 0.6))
  if (prefixLen < needle.length) {
    const prefix = needle.slice(0, prefixLen)
    const at = norm.indexOf(prefix)
    if (at !== -1) {
      return { start: map[at], end: map[at + prefix.length - 1] + 1 }
    }
  }

  return null
}
