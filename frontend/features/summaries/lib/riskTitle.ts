/**
 * Heading text for one risk factor card.
 *
 * The model emits `title` only sometimes (backend normalize.py passes it through when present),
 * so a filing with untitled risks used to render five identical "Risk Factor" <h4>s: no scan
 * value for sighted readers and an indistinguishable heading list for screen-reader users.
 *
 * Derivation order:
 *   1. an authored `title` wins verbatim;
 *   2. else the first clause of `summary` (then `description`): text up to the first sentence
 *      break (". ", "; ", ": ") or dash separator, trimmed of trailing punctuation, capped at
 *      MAX_TITLE_CHARS on a word boundary with an ellipsis, first letter upper-cased (the rest
 *      is left alone so "FX", "U.S." and product names keep their casing);
 *   3. else a positional "Risk n" so the heading is at least unique.
 *
 * Pure and dependency-free so it can be unit-tested directly.
 */

export const MAX_TITLE_CHARS = 80

interface RiskTitleSource {
  title?: string | null
  summary?: string | null
  description?: string | null
}

// Abbreviations whose trailing period is not a sentence end ("Apple Inc. faces", "Q1 vs. Q2",
// "risks incl. supply"). Lowercase here; the regex below is built case-insensitively per letter
// so the surrounding character classes can stay case-sensitive.
const ABBREVIATIONS = [
  'inc', 'co', 'corp', 'ltd', 'llc', 'plc', 'vs', 'approx', 'no', 'nos', 'mr', 'mrs', 'ms', 'dr',
  'jr', 'sr', 'st', 'incl', 'est', 'etc', 'dept', 'govt', 'fig', 'mfg', 'intl', 'assn', 'bros', 'univ',
]
const caseInsensitive = (word: string): string =>
  word.replace(/[a-z]/g, (c) => `[${c.toUpperCase()}${c}]`)
const ABBREVIATION_ALTERNATION = ABBREVIATIONS.map(caseInsensitive).join('|')

// Spaced em dash / en dash / hyphen. Kept as a regex literal (not a string) so the copy-voice
// em-dash gate, which scans string and template literals, never sees the character.
const DASH_SEPARATOR = /\s[—–-]\s/

// First sentence/clause boundary: a period/semicolon/colon followed by whitespace or end of text
// (so "3.5%" and "Inc.," survive), or a spaced em/en dash or hyphen used as a separator. A period
// is NOT a break when it closes a one-letter word ("U.S.", "e.g.", initials) or a known
// abbreviation, or when the next word starts lowercase (a sentence end starts a capital).
const CLAUSE_BREAK = new RegExp(
  `(?<!\\b[A-Za-z])(?<!\\b(?:${ABBREVIATION_ALTERNATION}))\\.(?=\\s|$)(?!\\s+[a-z])|[;:](?=\\s|$)|${DASH_SEPARATOR.source}`,
)

const firstClause = (text: string): string => {
  const idx = text.search(CLAUSE_BREAK)
  const clause = idx === -1 ? text : text.slice(0, idx)
  return clause.trim().replace(/[\s.,;:—–-]+$/, '')
}

const truncateOnWord = (text: string, max: number): string => {
  if (text.length <= max) return text
  const cut = text.slice(0, max)
  const lastSpace = cut.lastIndexOf(' ')
  // Keep at least half the budget so a single very long token does not collapse to "…".
  const head = lastSpace > max / 2 ? cut.slice(0, lastSpace) : cut
  return `${head.replace(/[\s.,;:]+$/, '')}…`
}

const sentenceCase = (text: string): string => text.charAt(0).toUpperCase() + text.slice(1)

/** Returns a short, unique heading for the risk at `index` (0-based). */
export function deriveRiskTitle(risk: RiskTitleSource, index: number): string {
  const authored = risk.title?.trim()
  if (authored) return authored

  const source = risk.summary?.trim() || risk.description?.trim() || ''
  const clause = firstClause(source.replace(/\s+/g, ' '))
  if (!/[A-Za-z0-9]/.test(clause)) return `Risk ${index + 1}`

  return sentenceCase(truncateOnWord(clause, MAX_TITLE_CHARS))
}
