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
 *      MIN_EXCERPT_WORDS words, is followed by a capitalised word (or the end) and is not inside a
 *      bracket or quotation. A one-letter word ("U.S.", initials) or a title, label or month
 *      abbreviation ("No.", "Dr.", "Sept.") does not end one; a company suffix does, unless the
 *      company's name goes on ("Acme Co. | Production may stop", "Technology Co. Limited").
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
 *      word, never on a function word, never splitting a figure from its unit, noun, qualifier or
 *      label ("$2.7 | billion", "200 basis | points", "3,200 | employees", "approximately |
 *      3,200", "$5 | per share", "EUR | 2.5", "Item | 1A"), a date ("December | 31", "27 |
 *      September"), a capitalised name ("New | York") or an open bracket or quotation, and keeping
 *      at least MIN_CLAUSE_WORDS words. When no prefix avoids every split (an all-caps run reads
 *      as one long name) it ends on the last content word that leaves nothing open; when there is
 *      none, or fewer than MIN_CLAUSE_WORDS whole words fit (one long token or URL), the card
 *      keeps the fallback.
 *
 * Pure and dependency-free so it can be unit-tested directly (tests/unit/riskHeadline.spec.ts).
 */

export const RISK_HEADLINE_MAX_CHARS = 100
export const RISK_HEADLINE_ELLIPSIS = '…'

const MIN_EXCERPT_WORDS = 3
const MIN_CLAUSE_WORDS = 4

/** The positional title a card keeps when its excerpt cannot give a meaningful headline. */
export const riskHeadlineFallback = (index: number): string => `Filing excerpt ${index + 1}`

// Abbreviations whose trailing period never ends a sentence: a title, label or month always has
// more to come ("ASU No. 2023-07", "Q1 vs. Q2", "Sept. 2025", "Dr. Smith"). Lowercase here; matched
// case-insensitively letter by letter so the surrounding character classes can stay case-sensitive.
const ABBREVIATIONS = [
  'vs', 'approx', 'no', 'nos', 'mr', 'mrs', 'ms', 'dr', 'jr', 'sr', 'st', 'incl', 'est', 'dept',
  'govt', 'fig', 'mfg', 'intl', 'assn', 'bros', 'univ',
  'jan', 'feb', 'mar', 'apr', 'jun', 'jul', 'aug', 'sep', 'sept', 'oct', 'nov', 'dec',
]
// A company suffix or "etc." can end a sentence ("Our sole supplier is Acme Co. Production may
// stop"): its period ends one when a capitalised word follows, as any period does, unless that word
// carries on the company's name ("Contemporary Amperex Technology Co. Limited", "Goldman Sachs &
// Co. LLC"); a lower-case one keeps it mid-sentence ("Apple Inc. faces"). Its period stays with the
// word in the headline.
const TERMINAL_ABBREVIATION = /\b(?:co|inc|corp|ltd|llc|plc|etc)$/i
const NAME_GOES_ON = /^\s+(?:co|inc|incorporated|corp|corporation|ltd|limited|llc|llp|lp|plc|ag|gmbh|sa|nv|bv)\b/i
const caseInsensitive = (word: string): string => word.replace(/[a-z]/g, (c) => `[${c.toUpperCase()}${c}]`)
const ABBREVIATION_ALTERNATION = ABBREVIATIONS.map(caseInsensitive).join('|')

// A sentence end: ".", "!" or "?" (not closing a one-letter word or an abbreviation), any closing
// quotes or brackets (captured, so the headline keeps a quotation it closes), then a capitalised
// word, a figure or an opening quote, or the end of the text.
const SENTENCE_END = new RegExp(
  `(?<!\\b[A-Za-z])(?<!\\b(?:${ABBREVIATION_ALTERNATION}))[.!?](["”’')\\]]*)(?=\\s+["“‘'(\\[$€£]?[A-Z0-9]|\\s*$)`,
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
    'via upon among between about against through during within before after since until whether so up even'
  ).split(' '),
)
const SCALE_WORD = /^(?:million|billion|trillion|thousand|percent|percentage|basis|square|cubic|metric)\b/i
// The first word of a two-word unit ("basis points", "percentage points", "square feet"): a headline
// never ends on it, and never on the figure or scale word just before it ("12.5 million | square feet").
const COMPOUND_UNIT_HEAD = /^(?:basis|percentage|square|cubic|metric)$/i
// A comparative waiting for its complement ("more | than 3,200", "even more | so").
const COMPARATIVE = /^(?:more|less|fewer|greater|larger|smaller|higher|lower|rather|other)$/i
// A currency code or symbol standing before its amount ("EUR 2.5 billion", "$ 4.1").
const CURRENCY = /^(?:USD|EUR|GBP|JPY|CHF|CNY|RMB|US\$|\$|€|£|¥)$/
const STARTS_WITH_FIGURE = /^[(\[]?[$€£¥]?\d/
// A bare figure, not a token that merely ends in digits (a URL, "riskfactors2025", "10-K2025").
const FIGURE = /^[$€£¥]?\d(?:[\d,.]*\d)?%?$/
const QUANTITY_QUALIFIER = /^(?:approximately|approx|nearly|almost|roughly|around|some|least|most|only|just|exactly)$/i
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

const LETTER = /\p{L}/u

const WORD_CHAR = /[\p{L}\p{N}]/u

/**
 * Whether a single quotation, curly or straight, is still open at the end of the text. "’" and "'"
 * are also apostrophes, so the marks are read in order. "‘" opens, and so does "'" at the start of a
 * word (after a space or a bracket, before anything but a space or closing punctuation: "'subject",
 * "'$5"). Any other mark closes only a
 * quotation already open, and never when it reads as an apostrophe: between letters ("Company’s",
 * "Company's") or after an s ("customers’ agreements"). That last case is ambiguous ("‘annual
 * reviews’" closes there), so it errs open: the headline stops before the quotation rather than risk
 * leaving it unclosed.
 */
const singleQuoteOpen = (text: string): boolean => {
  let depth = 0
  for (let i = 0; i < text.length; i++) {
    const mark = text[i]
    if (mark !== '‘' && mark !== '’' && mark !== "'") continue
    const before = text[i - 1] ?? ''
    const after = text[i + 1] ?? ''
    if (mark === '‘' || (mark === "'" && !WORD_CHAR.test(before) && /[^\s.,;:!?)\]]/.test(after))) depth++
    else if (depth > 0) {
      const apostrophe = LETTER.test(before) && (LETTER.test(after) || /[sS]/.test(before))
      if (!apostrophe) depth--
    }
  }
  return depth > 0
}

/** Whether the text leaves a bracket or a quotation open: ( [ “, a single quotation or a straight double quote. */
const leavesOpen = (text: string): boolean =>
  count(text, '(') > count(text, ')') ||
  count(text, '[') > count(text, ']') ||
  count(text, '“') > count(text, '”') ||
  singleQuoteOpen(text) ||
  count(text, '"') % 2 === 1

/** Whether ending a headline after tokens[i] would split something the reader needs whole. */
const isWeakEnd = (tokens: Token[], i: number, prefix: string): boolean => {
  const word = tokens[i].text
  const next = tokens[i + 1]?.text
  const previous = tokens[i - 1]?.text
  if (isFunctionWord(word)) return true
  if (next !== undefined && /\d/.test(word) && SCALE_WORD.test(bare(next))) return true
  // A figure directly before a lower-case content word is counting it ("3,200 | employees", "18 |
  // months"): not when punctuation ends the figure ("in 2027, recognized") or a function word follows
  // ("16% of", "2023 and").
  if (next !== undefined && FIGURE.test(word) && /^\p{Ll}/u.test(next) && !isFunctionWord(next)) return true
  if (next !== undefined && COMPOUND_UNIT_HEAD.test(bare(word))) return true
  if (next !== undefined && COMPARATIVE.test(bare(word)) && /^(?:than|so)$/i.test(bare(next))) return true
  if (next !== undefined && SCALE_WORD.test(bare(word)) && COMPOUND_UNIT_HEAD.test(bare(next))) return true
  if (next !== undefined && /\d/.test(word) && bare(next).toLowerCase() === 'per') return true
  // A qualifier before its figure: "approximately | 3,200", "at least | 10%".
  if (next !== undefined && STARTS_WITH_FIGURE.test(next) && QUANTITY_QUALIFIER.test(bare(word))) return true
  // A label or currency before its figure: "Item | 1A", "Note | 12", "Topic | 842", "EUR | 2.5".
  if (next !== undefined && STARTS_WITH_FIGURE.test(next) && (CURRENCY.test(word) || UPPERCASE_START.test(bare(word)))) return true
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
    const suffix = TERMINAL_ABBREVIATION.test(text.slice(0, at))
    if (suffix && NAME_GOES_ON.test(text.slice(at + match[0].length))) continue
    // A bare terminal period is dropped; one inside a closing quotation, or one that closes a company
    // suffix ("Acme Inc."), stays.
    const keepsPeriod = !match[0].startsWith('.') || suffix
    const sentence = closers ? text.slice(0, at + 1 + closers.length) : text.slice(0, keepsPeriod ? at + 1 : at)
    // A break inside a quotation or bracket ends the quoted sentence, not this one ("warned that
    // “production may stop. Additional delays…”").
    if (leavesOpen(sentence)) continue
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
