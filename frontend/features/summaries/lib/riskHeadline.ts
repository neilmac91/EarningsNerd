/**
 * Heading text for one risk card, taken verbatim from the card's own verified filing excerpt.
 *
 * The backend projects every risk to a source-first span (provenance_service.project_risk_list):
 * the model's own label is discarded and `summary` / `source_section_ref` both read "Filing
 * excerpt", so the only text a card may title itself with is that excerpt. The headline is always
 * a PREFIX of the excerpt: never rewritten, recased or reordered. A trailing ellipsis means the
 * excerpt goes on past the headline (a cut, or a later sentence); the full excerpt still renders
 * under the heading as the evidence.
 *
 * The rule, designed against the production filing-3 spans and the eval-baseline risk spans:
 *   1. An excerpt of fewer than MIN_EXCERPT_WORDS words (or none) gets the positional fallback
 *      "Filing excerpt n".
 *   2. Take the first sentence: up to the first ".", "!" or "?" that leaves at least
 *      MIN_EXCERPT_WORDS words and is followed by a capitalised word (or the end). A one-letter
 *      word ("U.S.", initials) or a known abbreviation ("Inc.", "No.", "Sept.") does not end one.
 *   3. If it fits in RISK_HEADLINE_MAX_CHARS it is the headline, whole: a sentence that fits is
 *      never cut, so a hedge or a turn later in it ("; however, coverage may not be adequate")
 *      stays in the heading.
 *   4. A longer sentence is cut at its first ";" or ":" when the clause before it can stand as a
 *      heading: at least MIN_CLAUSE_WORDS words, not opening on a leading date or qualifier ("As of
 *      December 31, 2025:", "In the third quarter:"), not turned by what follows ("; however"), no
 *      bracket or quotation left open, and ending on a content word (a colon lead-in may end on its
 *      function word: "could also result in:"). A comma never cuts: on real spans it ends on a
 *      leading date ("As of September 27"), a qualifier ("Regardless of the merit of particular
 *      claims") or a list item ("... in China mainland"). Nor does a dash: filings use it for ranges
 *      ("2019 – 2022") and asides ("authorities—particularly China—could").
 *   5. Otherwise the headline is the longest prefix within the cap that ends on a whole content
 *      word, never on a function word, never splitting a figure from its unit ("$2.7 | billion"),
 *      a date ("December | 31", "27 | September"), a capitalised name ("New | York") or an open
 *      parenthesis or quotation, and keeping at least MIN_CLAUSE_WORDS words. When no prefix avoids
 *      every split (an all-caps run reads as one long name) it ends on the last content word that
 *      leaves nothing open; when there is none, or fewer than MIN_CLAUSE_WORDS whole words fit (one
 *      long token or URL), the card keeps the fallback.
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
// "Q1 vs. Q2", "Sept. 2025"). Lowercase here; matched case-insensitively letter by letter so the
// surrounding character classes can stay case-sensitive.
const ABBREVIATIONS = [
  'inc', 'co', 'corp', 'ltd', 'llc', 'plc', 'vs', 'approx', 'no', 'nos', 'mr', 'mrs', 'ms', 'dr',
  'jr', 'sr', 'st', 'incl', 'est', 'etc', 'dept', 'govt', 'fig', 'mfg', 'intl', 'assn', 'bros', 'univ',
  'jan', 'feb', 'mar', 'apr', 'jun', 'jul', 'aug', 'sep', 'sept', 'oct', 'nov', 'dec',
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

// ";" or ":" before a space (so "10:30" survives). Never a dash (see step 4 above).
const CLAUSE_BOUNDARY = /[;:](?=\s)/

// A clause opening on one of these is a leading date, qualifier or condition ("As of December 31,
// 2025:", "In the third quarter:"), not a statement a card can stand on.
const LEADING_QUALIFIERS = new Set(
  (
    'as in on at by for from with without during following after before since until upon under ' +
    'regardless despite notwithstanding although though while if because when whereas unless'
  ).split(' '),
)

// What follows the boundary turns or hedges the clause ("; however, such coverage may not be adequate").
const TURN = /^(?:however|but|although|though|yet|except|nevertheless|nonetheless|notwithstanding|unless|while|whereas|provided|still)$/i

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
const MONTH = /^(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sept?|Oct|Nov|Dec)$/
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

/** Whether the text leaves a parenthesis or a quotation open. */
const leavesOpen = (text: string): boolean =>
  count(text, '(') > count(text, ')') || count(text, '“') > count(text, '”') || count(text, '"') % 2 === 1

/** Whether ending a headline after tokens[i] would split something the reader needs whole. */
const isWeakEnd = (tokens: Token[], i: number, prefix: string): boolean => {
  const word = tokens[i].text
  const next = tokens[i + 1]?.text
  const previous = tokens[i - 1]?.text
  if (isFunctionWord(word)) return true
  if (next !== undefined && /\d/.test(word) && SCALE_WORD.test(bare(next))) return true
  if (MONTH.test(bare(word))) return true
  if (previous !== undefined && /^\d{1,2},?$/.test(word) && MONTH.test(bare(previous))) return true
  // A day before its month ("27 | September 2025", the day-first order international filers use).
  if (next !== undefined && /^\d{1,2}$/.test(bare(word)) && MONTH.test(bare(next))) return true
  if (i > 0 && next !== undefined && UPPERCASE_START.test(bare(word)) && UPPERCASE_START.test(next)) return true
  return leavesOpen(prefix)
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

/** The sentence up to its first ";" or ":" when that clause can stand as a heading (step 4), else null. */
const clauseOf = (sentence: string): string | null => {
  const match = CLAUSE_BOUNDARY.exec(sentence)
  if (!match) return null
  const clause = sentence.slice(0, match.index).replace(TRAILING_SEPARATORS, '')
  const tokens = tokensOf(clause)
  if (wordCount(clause) < MIN_CLAUSE_WORDS || clause.length > RISK_HEADLINE_MAX_CHARS) return null
  if (LEADING_QUALIFIERS.has(bare(tokens[0].text).toLowerCase())) return null
  if (TURN.test(bare(sentence.slice(match.index + 1).trimStart().split(/\s/)[0] ?? ''))) return null
  if (leavesOpen(clause)) return null
  // Only a colon introduces what follows, so only a colon lead-in may end on a function word.
  if (match[0] !== ':' && isFunctionWord(tokens[tokens.length - 1].text)) return null
  return clause
}

/**
 * The longest prefix within the cap that ends on a whole content word (step 5); when every candidate
 * splits something, the longest that ends on a content word and leaves no bracket or quotation open.
 * Null when fewer than MIN_CLAUSE_WORDS whole words fit, or when every such prefix is inside one.
 */
const capped = (text: string): string | null => {
  const tokens = tokensOf(text)
  const within = tokens.filter((t) => t.end <= RISK_HEADLINE_MAX_CHARS)
  let lastContentWord: number | null = null
  for (let i = within.length - 1; i >= 0; i--) {
    const prefix = text.slice(0, within[i].end)
    if (wordCount(prefix) < MIN_CLAUSE_WORDS) break
    if (!isWeakEnd(tokens, i, prefix)) return prefix
    // The relaxed end still never leaves a bracket or quotation open: with nothing else, the card
    // keeps its positional title rather than a heading that stops inside a parenthetical.
    if (lastContentWord === null && !isFunctionWord(within[i].text) && !leavesOpen(prefix)) lastContentWord = within[i].end
  }
  return lastContentWord === null ? null : text.slice(0, lastContentWord)
}

/** Returns the card heading for the risk at `index` (0-based) from its verified excerpt. */
export function deriveRiskHeadline(excerpt: string | null | undefined, index: number): string {
  const text = (excerpt ?? '').trim()
  if (wordCount(text) < MIN_EXCERPT_WORDS) return riskHeadlineFallback(index)

  const sentence = firstSentence(text).replace(TRAILING_SEPARATORS, '')
  const prefix =
    sentence.length <= RISK_HEADLINE_MAX_CHARS ? sentence : (clauseOf(sentence) ?? capped(sentence)?.replace(TRAILING_SEPARATORS, ''))
  if (!prefix) return riskHeadlineFallback(index)
  // Anything left of the excerpt beyond whitespace or its final period means it continues below.
  return /[^\s.]/.test(text.slice(prefix.length)) ? `${prefix}${RISK_HEADLINE_ELLIPSIS}` : prefix
}
