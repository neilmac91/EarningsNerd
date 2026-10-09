/**
 * Heading text for one risk card, taken verbatim from the card's own verified filing excerpt.
 *
 * The backend projects every risk to a source-first span (provenance_service.project_risk_list):
 * the model's own label is discarded and `summary` / `source_section_ref` both read "Filing
 * excerpt", so the only text a card may title itself with is that excerpt. The headline is always
 * a PREFIX of the excerpt: never rewritten, recased or reordered. A trailing ellipsis marks a cut
 * inside a clause; the full excerpt still renders under the heading as the evidence.
 *
 * The rule, designed against the production filing-3 spans and the eval-baseline risk spans:
 *   1. An excerpt of fewer than MIN_EXCERPT_WORDS words (or none) gets the positional fallback
 *      "Filing excerpt n".
 *   2. Take the first sentence: up to the first ".", "!" or "?" that leaves at least
 *      MIN_EXCERPT_WORDS words and is followed by a capitalised word (or the end). A one-letter
 *      word ("U.S.", initials) or a known abbreviation ("Inc.", "No.") does not end a sentence.
 *   3. Within it, cut at the first strong clause boundary (";" or ":" before a space, a spaced
 *      dash, an em dash) when it leaves at least MIN_CLAUSE_WORDS words. A comma never cuts: on real
 *      spans it ends on a leading date ("As of September 27"), a leading qualifier ("Regardless of
 *      the merit of particular claims") or a list item ("... located primarily in China mainland").
 *   4. If that fits in RISK_HEADLINE_MAX_CHARS it is the headline, without a bare final period. A
 *      clause that ends on a lead-in word (the "in" of "could result in:") takes an ellipsis.
 *   5. Otherwise the headline is the longest prefix within the cap that ends on a whole content
 *      word, never on a function word, never splitting a figure from its unit ("$2.7 | billion"),
 *      a date ("December | 31"), a capitalised name ("New | York") or an open parenthesis or
 *      quotation, and keeping at least MIN_CLAUSE_WORDS words; then an ellipsis.
 *
 * Pure and dependency-free so it can be unit-tested directly (tests/unit/riskHeadline.spec.ts).
 */

export const RISK_HEADLINE_MAX_CHARS = 100
export const RISK_HEADLINE_ELLIPSIS = '…'

const MIN_EXCERPT_WORDS = 3
const MIN_CLAUSE_WORDS = 4

/** The positional title a card keeps when its excerpt cannot give a meaningful headline. */
export const riskHeadlineFallback = (index: number): string => `Filing excerpt ${index + 1}`

// Abbreviations whose trailing period is not a sentence end ("Apple Inc. faces", "ASU No. 2023-07",
// "Q1 vs. Q2"). Lowercase here; matched case-insensitively letter by letter so the surrounding
// character classes can stay case-sensitive.
const ABBREVIATIONS = [
  'inc', 'co', 'corp', 'ltd', 'llc', 'plc', 'vs', 'approx', 'no', 'nos', 'mr', 'mrs', 'ms', 'dr',
  'jr', 'sr', 'st', 'incl', 'est', 'etc', 'dept', 'govt', 'fig', 'mfg', 'intl', 'assn', 'bros', 'univ',
]
const caseInsensitive = (word: string): string => word.replace(/[a-z]/g, (c) => `[${c.toUpperCase()}${c}]`)
const ABBREVIATION_ALTERNATION = ABBREVIATIONS.map(caseInsensitive).join('|')

// A sentence end: ".", "!" or "?" (not closing a one-letter word or an abbreviation), any closing
// quotes or brackets (captured, so the headline keeps a quotation it closes), then a capitalised
// word, a figure or an opening quote, or the end of the text.
const SENTENCE_END = new RegExp(
  `(?<!\\b[A-Za-z])(?<!\\b(?:${ABBREVIATION_ALTERNATION}))[.!?](["”’)\\]]*)(?=\\s+["“‘(\\[$€£]?[A-Z0-9]|\\s*$)`,
  'g',
)

// ";" or ":" before a space (so "10:30" survives), a spaced em/en dash or hyphen, or an em dash.
// A regex literal, not a string, so the copy-voice em-dash gate never sees the character.
const STRONG_BOUNDARY = /[;:](?=\s|$)|\s[—–-]\s|—/

// Words a headline must not end on: articles, prepositions, conjunctions, auxiliaries, relative
// pronouns and determiners leave the reader mid-phrase ("... manufactured by outsourcing partners
// that").
const FUNCTION_WORDS = new Set(
  (
    'a an the and or but nor of to in on at by for from with without into onto over under as than ' +
    'that which who whom whose where when while if because such including is are was were be been ' +
    'being can could may might will would shall should must has have had do does did its it their ' +
    'our his her your my this these those any each other not no also both either all certain per ' +
    'via upon among between about against through during within before after since until whether so'
  ).split(' '),
)
const SCALE_WORD = /^(?:million|billion|trillion|thousand|percent|basis)\b/i
const MONTH = /^(?:January|February|March|April|May|June|July|August|September|October|November|December)$/
const UPPERCASE_START = /^\p{Lu}/u
const TRAILING_SEPARATORS = /[\s,;:—–-]+$/

interface Token {
  text: string
  end: number
}

const tokensOf = (text: string): Token[] =>
  Array.from(text.matchAll(/\S+/g), (m) => ({ text: m[0], end: (m.index ?? 0) + m[0].length }))

const wordCount = (text: string): number => tokensOf(text).filter((t) => /[\p{L}\p{N}]/u.test(t.text)).length

/** The word without surrounding quotes, brackets or punctuation ("(“U.S." -> "U.S", "2025," -> "2025"). */
const bare = (word: string): string => word.replace(/^[^\p{L}\p{N}$€£]+|[^\p{L}\p{N}%]+$/gu, '')

const count = (text: string, ch: string): number => text.split(ch).length - 1

const isFunctionWord = (word: string): boolean => FUNCTION_WORDS.has(bare(word).toLowerCase())

/** Whether ending a headline after tokens[i] would split something the reader needs whole. */
const isWeakEnd = (tokens: Token[], i: number, prefix: string): boolean => {
  const word = tokens[i].text
  const next = tokens[i + 1]?.text
  const previous = tokens[i - 1]?.text
  if (isFunctionWord(word)) return true
  if (next !== undefined && /\d/.test(word) && SCALE_WORD.test(bare(next))) return true
  if (MONTH.test(bare(word))) return true
  if (previous !== undefined && /^\d{1,2},?$/.test(word) && MONTH.test(bare(previous))) return true
  if (i > 0 && next !== undefined && UPPERCASE_START.test(bare(word)) && UPPERCASE_START.test(next)) return true
  if (count(prefix, '(') > count(prefix, ')') || count(prefix, '“') > count(prefix, '”') || count(prefix, '"') % 2 === 1) {
    return true
  }
  return false
}

/** The first sentence, or the whole text when no break leaves enough words before it. */
const firstSentence = (text: string): string => {
  for (const match of text.matchAll(SENTENCE_END)) {
    const at = match.index ?? 0
    const closers = match[1] ?? ''
    // A bare terminal period is dropped; one inside a closing quotation stays with its quote.
    const sentence = closers ? text.slice(0, at + 1 + closers.length) : text.slice(0, match[0].startsWith('.') ? at : at + 1)
    if (wordCount(sentence) >= MIN_EXCERPT_WORDS) return sentence
  }
  return text
}

/**
 * The sentence up to its first strong clause boundary, when that leaves MIN_CLAUSE_WORDS words.
 * Only the first boundary counts: a later one can close a parenthetical pair of dashes.
 */
const firstClause = (sentence: string): string => {
  const at = sentence.search(STRONG_BOUNDARY)
  if (at === -1) return sentence
  const clause = sentence.slice(0, at)
  return wordCount(clause) >= MIN_CLAUSE_WORDS ? clause : sentence
}

/** The longest prefix within the cap that ends on a whole content word, plus an ellipsis. */
const capped = (clause: string): string => {
  const tokens = tokensOf(clause)
  const within = tokens.filter((t) => t.end <= RISK_HEADLINE_MAX_CHARS)
  // A single token longer than the cap (no space in reach) is cut where the cap falls.
  if (within.length === 0) return `${clause.slice(0, RISK_HEADLINE_MAX_CHARS)}${RISK_HEADLINE_ELLIPSIS}`
  let end = within[within.length - 1].end
  for (let i = within.length - 1; i >= 0; i--) {
    const prefix = clause.slice(0, within[i].end)
    if (wordCount(prefix) < MIN_CLAUSE_WORDS) break
    if (!isWeakEnd(tokens, i, prefix)) {
      end = within[i].end
      break
    }
  }
  return `${clause.slice(0, end).replace(TRAILING_SEPARATORS, '')}${RISK_HEADLINE_ELLIPSIS}`
}

/** Returns the card heading for the risk at `index` (0-based) from its verified excerpt. */
export function deriveRiskHeadline(excerpt: string | null | undefined, index: number): string {
  const text = (excerpt ?? '').trim()
  if (wordCount(text) < MIN_EXCERPT_WORDS) return riskHeadlineFallback(index)

  const sentence = firstSentence(text)
  const clause = firstClause(sentence).replace(TRAILING_SEPARATORS, '')
  if (clause.length > RISK_HEADLINE_MAX_CHARS) return capped(clause)

  // A clause cut at a strong boundary that ends on a lead-in word introduces what follows it.
  const tokens = tokensOf(clause)
  const leadIn = clause.length < sentence.trimEnd().replace(TRAILING_SEPARATORS, '').length && isFunctionWord(tokens[tokens.length - 1].text)
  return leadIn ? `${clause}${RISK_HEADLINE_ELLIPSIS}` : clause
}
