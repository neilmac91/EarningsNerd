/**
 * Display casing for company names.
 *
 * EDGAR stores issuer names in ALL CAPS ("APPLE INC.", "JPMORGAN CHASE & CO"), which reads as
 * shouting in a title, H1, or breadcrumb. This helper title-cases those names for DISPLAY only:
 * the raw name stays the data value everywhere it is sent onward (analytics, cache rows,
 * request payloads), so the backend and search never see a rewritten string.
 *
 * THE RULE (one rule, applied consistently):
 *   1. A name that already contains a lowercase letter is trusted as-cased and returned as-is
 *      ("Alphabet Inc." stays "Alphabet Inc.").
 *   2. Otherwise every whitespace-separated token is title-cased (first letter up, rest down),
 *      EXCEPT:
 *        - tokens with a digit, ampersand, or slash are left untouched ("3M", "AT&T", "S&P");
 *        - tokens in OVERRIDES take their brand casing ("JPMORGAN" -> "JPMorgan", "EBAY" -> "eBay");
 *        - tokens in KEEP_UPPER stay upper (legal-form initialisms "LLC", "PLC"; brand initialisms
 *          "IBM", "NVIDIA"; roman numerals);
 *        - short connectives ("of", "the", "and", ...) are lowercased unless they lead the name.
 *   3. Punctuation is never added or removed. "INC." -> "Inc." and "CORP" -> "Corp" (no period is
 *      invented), so the display form is always the source form with only its letter case changed.
 *      Hyphen/apostrophe/period-joined segments are cased per segment ("COCA-COLA" -> "Coca-Cola",
 *      "O'REILLY" -> "O'Reilly", "U.S." -> "U.S."), with a trailing possessive "'S" -> "'s".
 *
 * Unknown initialisms (a ticker-like "TJX") will come out as "Tjx"; add them to KEEP_UPPER when
 * seen. That is the accepted trade-off of a small, predictable exceptions list over a dictionary.
 */

/** Exact-token brand casings (keys are the upper-cased source token). */
const OVERRIDES: Record<string, string> = {
  JPMORGAN: 'JPMorgan',
  EBAY: 'eBay',
  PAYPAL: 'PayPal',
  PEPSICO: 'PepsiCo',
  EXXONMOBIL: 'ExxonMobil',
  CONOCOPHILLIPS: 'ConocoPhillips',
  GLAXOSMITHKLINE: 'GlaxoSmithKline',
  ASTRAZENECA: 'AstraZeneca',
  BIONTECH: 'BioNTech',
  NETAPP: 'NetApp',
  DOORDASH: 'DoorDash',
  LINKEDIN: 'LinkedIn',
  YOUTUBE: 'YouTube',
  "MCDONALD'S": "McDonald's",
  MCDONALDS: 'McDonalds',
  MCKESSON: 'McKesson',
  MCCORMICK: 'McCormick',
  IPHONE: 'iPhone',
}

/** Tokens that stay upper-case: legal-form initialisms, brand initialisms, roman numerals. */
const KEEP_UPPER = new Set([
  // legal forms / structures
  'LLC', 'LP', 'LLP', 'PLC', 'NV', 'N.V.', 'SA', 'S.A.', 'SE', 'AG', 'AB', 'ASA', 'SPA', 'S.P.A.',
  'ADR', 'ADS', 'ETF', 'REIT', 'USA', 'US', 'U.S.', 'UK', 'U.K.',
  // brand initialisms
  'IBM', 'AMD', 'HP', 'GE', 'UPS', 'CVS', 'CSX', 'KKR', 'TJX', 'HCA', 'ADP', 'ADM', 'AIG', 'AES',
  'AMC', 'NVIDIA', 'DTE', 'PPG', 'PNC', 'AFLAC', 'CBRE', 'CDW', 'CME', 'CSC', 'DXC', 'EQT', 'FMC',
  'ITT', 'MGM', 'MSCI', 'NRG', 'NXP', 'ONEOK', 'PVH', 'SBA', 'SVB', 'TD', 'UBS', 'VF', 'WEC', 'WPP',
  // roman numerals
  'II', 'III', 'IV',
])

/** Connectives lowercased mid-name ("Bank of America", "The Home Depot" keeps its leading "The"). */
const LOWER_MIDWORD = new Set([
  'of', 'the', 'and', 'for', 'in', 'on', 'at', 'by', 'to',
  'de', 'del', 'la', 'da', 'di', 'du', 'van', 'von', 'y', 'et',
])

const hasLowercase = (s: string): boolean => /[a-z]/.test(s)

/** Title-case one alphabetic segment; single letters stay upper ("A O Smith"). */
const caseSegment = (segment: string): string => {
  if (segment.length <= 1) return segment.toUpperCase()
  return segment.charAt(0).toUpperCase() + segment.slice(1).toLowerCase()
}

const caseToken = (token: string, isFirst: boolean): string => {
  const upper = token.toUpperCase()
  if (OVERRIDES[upper]) return OVERRIDES[upper]
  if (KEEP_UPPER.has(upper)) return upper
  // Digits, ampersands, slashes: ticker-like or brand tokens ("3M", "AT&T", "S&P", "/DE/") -> as-is.
  if (/[0-9&/]/.test(token)) return token
  const lower = token.toLowerCase()
  if (!isFirst && LOWER_MIDWORD.has(lower)) return lower
  // Case each alphabetic run separately so joiners survive: "COCA-COLA", "O'REILLY", "U.S.".
  return token.replace(/[A-Za-z]+/g, caseSegment).replace(/'S$/, "'s")
}

/**
 * Returns the display form of a company name (see the module rule above). Null/undefined yield
 * an empty string so call sites can `|| ticker` without a separate null check.
 */
export function formatCompanyName(name: string | null | undefined): string {
  if (!name) return ''
  const trimmed = name.trim()
  if (!trimmed || hasLowercase(trimmed)) return trimmed
  return trimmed
    .split(/\s+/)
    .map((token, i) => caseToken(token, i === 0))
    .join(' ')
}
