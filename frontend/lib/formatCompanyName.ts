/**
 * Display casing for company names.
 *
 * EDGAR stores issuer names in ALL CAPS ("APPLE INC.", "JPMORGAN CHASE & CO"), which reads as
 * shouting in a title, H1, or breadcrumb. This helper title-cases those names for DISPLAY only:
 * the raw name stays the data value everywhere it is sent onward (analytics, cache rows,
 * request payloads), so the backend and search never see a rewritten string.
 *
 * THE RULE (one rule, applied consistently):
 *   1. A name whose BODY already contains a lowercase letter is trusted as-cased and returned
 *      as-is ("Alphabet Inc." stays "Alphabet Inc."). The body is every token before the trailing
 *      run of legal-form tokens (Inc, Corp, Co, Ltd, LLC, PLC, "/DE/" state markers, ...): EDGAR
 *      commonly cases ONLY that suffix ("ELI LILLY & Co", "NIKE, Inc.", "CVS HEALTH Corp"), and
 *      a lowercase suffix must not exempt the shouting body in front of it.
 *   2. Otherwise every whitespace-separated token is title-cased (first letter up, rest down),
 *      EXCEPT:
 *        - tokens with a digit, ampersand, or slash are left untouched ("3M", "AT&T", "S&P", "/DE/");
 *        - tokens in OVERRIDES take their brand casing ("JPMORGAN" -> "JPMorgan", "EBAY" -> "eBay");
 *        - tokens in KEEP_UPPER stay upper (legal-form initialisms "LLC", "PLC"; brand initialisms
 *          "IBM", "NVIDIA", "NIKE" as the company itself styles it; roman numerals);
 *        - short connectives ("of", "the", "and", ...) are lowercased unless they lead the name.
 *      Lookups ignore punctuation glued to a token, so "(IBM)", "IBM," and "CO." resolve like
 *      "IBM" and "CO"; the punctuation is re-attached unchanged.
 *   3. Punctuation is never added or removed. "INC." -> "Inc." and "CORP" -> "Corp" (no period is
 *      invented), so the display form is always the source form with only its letter case changed.
 *      Hyphen/apostrophe/period-joined segments are cased per segment ("COCA-COLA" -> "Coca-Cola",
 *      "O'REILLY" -> "O'Reilly", "U.S." -> "U.S."), with a trailing possessive "'S" -> "'s".
 *
 * Unknown initialisms (a ticker-like "XPO") will come out as "Xpo"; add them to KEEP_UPPER when
 * seen. That is the accepted trade-off of a small, predictable exceptions list over a dictionary.
 */

/** Exact-token brand casings (keys are the upper-cased source token, punctuation stripped). */
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
  // brand initialisms (NIKE and NVIDIA are how those companies style their own names)
  'IBM', 'AMD', 'HP', 'GE', 'UPS', 'CVS', 'CSX', 'KKR', 'TJX', 'HCA', 'ADP', 'ADM', 'AIG', 'AES',
  'AMC', 'NVIDIA', 'NIKE', 'RTX', 'DTE', 'PPG', 'PNC', 'AFLAC', 'CBRE', 'CDW', 'CME', 'CSC', 'DXC',
  'EQT', 'FMC', 'ITT', 'MGM', 'MSCI', 'NRG', 'NXP', 'ONEOK', 'PVH', 'SBA', 'SVB', 'TD', 'UBS', 'VF',
  'WEC', 'WPP',
  // roman numerals
  'II', 'III', 'IV',
])

/**
 * Legal-form / registration tokens that EDGAR often leaves as the ONLY cased part of a name
 * ("PROCTER & GAMBLE Co"). Compared after punctuation stripping and upper-casing; a slash token
 * such as "/DE/" (state of incorporation marker) is treated as a suffix by its shape.
 */
const LEGAL_SUFFIX = new Set([
  'INC', 'INCORPORATED', 'CORP', 'CORPORATION', 'CO', 'COMPANY', 'LTD', 'LIMITED', 'LLC', 'LLP',
  'LP', 'PLC', 'NV', 'SA', 'AG', 'SE', 'AB', 'ASA', 'SPA', 'HOLDINGS', 'GROUP', 'TRUST',
])

/** Connectives lowercased mid-name ("Bank of America", "The Home Depot" keeps its leading "The"). */
const LOWER_MIDWORD = new Set([
  'of', 'the', 'and', 'for', 'in', 'on', 'at', 'by', 'to',
  'de', 'del', 'la', 'da', 'di', 'du', 'van', 'von', 'y', 'et',
])

const hasLowercase = (s: string): boolean => /[a-z]/.test(s)

/** Split "(IBM)," into ["(", "IBM", "),"]: leading / trailing non-alphanumerics vs the core. */
const splitPunctuation = (token: string): [string, string, string] => {
  const m = /^([^A-Za-z0-9]*)(.*?)([^A-Za-z0-9]*)$/.exec(token)
  return m ? [m[1], m[2], m[3]] : ['', token, '']
}

const isSuffixToken = (token: string): boolean => {
  if (token.includes('/')) return true
  const [, core] = splitPunctuation(token)
  return LEGAL_SUFFIX.has(core.toUpperCase())
}

/** Title-case one alphabetic segment; single letters stay upper ("A O Smith"). */
const caseSegment = (segment: string): string => {
  if (segment.length <= 1) return segment.toUpperCase()
  return segment.charAt(0).toUpperCase() + segment.slice(1).toLowerCase()
}

const caseToken = (token: string, isFirst: boolean): string => {
  const upper = token.toUpperCase()
  // Whole-token lookups first (entries such as "U.S." carry their own punctuation).
  if (OVERRIDES[upper]) return OVERRIDES[upper]
  if (KEEP_UPPER.has(upper)) return upper
  // Digits, ampersands, slashes: ticker-like or brand tokens ("3M", "AT&T", "S&P", "/DE/") -> as-is.
  if (/[0-9&/]/.test(token)) return token
  // Then the core with glued punctuation stripped: "(IBM)", "IBM,", "CO." -> lookup "IBM" / "CO".
  const [lead, core, trail] = splitPunctuation(token)
  const coreUpper = core.toUpperCase()
  if (OVERRIDES[coreUpper]) return lead + OVERRIDES[coreUpper] + trail
  if (KEEP_UPPER.has(coreUpper)) return lead + coreUpper + trail
  const lower = core.toLowerCase()
  if (!isFirst && LOWER_MIDWORD.has(lower)) return lead + lower + trail
  // Case each alphabetic run separately so joiners survive: "COCA-COLA", "O'REILLY", "U.S.".
  return token.replace(/[A-Za-z]+/g, caseSegment).replace(/'S(?=[^A-Za-z0-9]*$)/, "'s")
}

/**
 * Returns the display form of a company name (see the module rule above). Null/undefined yield
 * an empty string so call sites can `|| ticker` without a separate null check.
 */
export function formatCompanyName(name: string | null | undefined): string {
  if (!name) return ''
  const trimmed = name.trim()
  if (!trimmed) return ''
  const tokens = trimmed.split(/\s+/)

  // Body = everything before the trailing run of legal-form tokens. Only lowercase IN THE BODY
  // marks a name as already cased; a cased suffix alone ("ELI LILLY & Co") does not.
  let bodyEnd = tokens.length
  while (bodyEnd > 0 && isSuffixToken(tokens[bodyEnd - 1])) bodyEnd -= 1
  if (hasLowercase(tokens.slice(0, bodyEnd).join(' '))) return tokens.join(' ')

  return tokens.map((token, i) => caseToken(token, i === 0)).join(' ')
}
