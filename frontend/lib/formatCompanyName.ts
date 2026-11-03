/**
 * Display casing for company names.
 *
 * EDGAR stores issuer names in ALL CAPS ("APPLE INC.", "JPMORGAN CHASE & CO"), which reads as
 * shouting in a title, H1, or breadcrumb. This helper title-cases those names for DISPLAY only:
 * the raw name stays the data value everywhere it is sent onward (analytics, cache rows,
 * request payloads), so the backend and search never see a rewritten string.
 *
 * The backend's analysis exports print through a Python port, backend/app/utils/company_names.py; both run
 * backend/tests/fixtures/company_display_names.json, and its test holds the five word lists below equal.
 *
 * THE RULE (one rule, applied consistently):
 *   1. A name whose BODY already contains a lowercase letter, in any script, is trusted as-cased and
 *      returned as-is ("Alphabet Inc." stays "Alphabet Inc."). The body is every token before the trailing
 *      run of legal-form tokens (Inc, Corp, Co, Ltd, LLC, PLC, "/DE/" state markers, ...): EDGAR
 *      commonly cases ONLY that suffix ("ELI LILLY & Co", "NIKE, Inc.", "CVS HEALTH Corp"), and
 *      a lowercase suffix must not exempt the shouting body in front of it.
 *   2. Otherwise every whitespace-separated token is title-cased (first letter up, rest down),
 *      EXCEPT:
 *        - tokens with a digit or an ampersand are left untouched ("3M", "AT&T", "S&P"), unless OVERRIDES names
 *          them ("L3HARRIS" -> "L3Harris");
 *        - a token with a slash is EDGAR's legal form with a marker glued on: the part before the first slash is
 *          cased as that word on its own, and each marker after a slash (a state code, NEW) keeps its capitals
 *          ("INC/DE" -> "Inc/DE", "CO/VA/" -> "Co/VA/"); a marker alone ("/DE/") stays as served (chief design on
 *          #1491, comment 6347648492);
 *        - tokens in OVERRIDES take their brand casing ("JPMORGAN" -> "JPMorgan", "EBAY" -> "eBay");
 *        - tokens in KEEP_UPPER stay upper (legal-form initialisms "LLC", "PLC"; brand initialisms
 *          "IBM", "NVIDIA", "NIKE" as the company itself styles it; roman numerals);
 *        - short connectives ("of", "the", "and", ...) are lowercased unless they lead the name;
 *        - a name's first token in LEADING_INITIALISMS stays upper before its partner token
 *          ("ON SEMICONDUCTOR CORP" -> "ON Semiconductor Corp"), and is a word anywhere else.
 *      Lookups ignore punctuation glued to a token, so "(IBM)", "IBM," and "CO." resolve like
 *      "IBM" and "CO"; the punctuation is re-attached unchanged.
 *   3. A trailing group of tickers in parentheses, which EDGAR's full-text search folds into a filer's display name
 *      ("BOEING CO (BA, BA-PA)"), is data and stays as served; the name before it takes rules 1 and 2.
 *   4. Punctuation is never added or removed. "INC." -> "Inc." and "CORP" -> "Corp" (no period is
 *      invented), so the display form is always the source form with only its letter case changed.
 *      Hyphen/apostrophe/period-joined segments are cased per segment ("COCA-COLA" -> "Coca-Cola",
 *      "O'REILLY" -> "O'Reilly", "U.S." -> "U.S."), with a trailing possessive "'S" -> "'s".
 *   5. A letter is any script's, with its accents, so an accented capital stays inside its word
 *      ("SOCIÉTÉ GÉNÉRALE" -> "Société Générale", "L'ORÉAL" -> "L'Oréal") and a Cyrillic or Greek
 *      name takes the same rules, a word lowercased whole so a Greek final sigma keeps its form
 *      ("ΤΗΣ" -> "Της"); a script without case (Japanese, Chinese, Arabic) is left as served.
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
  // E307: brands that case their own name inside a word, as their own filings write it (a 10-K or 20-F
  // certification, the XBRL cover, or the EDGAR name), for issuers EDGAR files, or once filed, in capitals. A brand EDGAR has
  // only ever filed in its own casing needs none ("AbbVie Inc." is served as written).
  AUTOZONE: 'AutoZone',
  BLACKROCK: 'BlackRock',
  CENTERPOINT: 'CenterPoint',
  COSTAR: 'CoStar',
  DAVITA: 'DaVita',
  FACTSET: 'FactSet',
  FEDEX: 'FedEx',
  FIRSTENERGY: 'FirstEnergy',
  'FREEPORT-MCMORAN': 'Freeport-McMoRan',
  KEYCORP: 'KeyCorp',
  L3HARRIS: 'L3Harris',
  MCLENNAN: 'McLennan',
  MERCADOLIBRE: 'MercadoLibre',
  METLIFE: 'MetLife',
  MICROSTRATEGY: 'MicroStrategy',
  NEXTERA: 'NextEra',
  NISOURCE: 'NiSource',
  PULTEGROUP: 'PulteGroup',
  RESMED: 'ResMed',
  UNITEDHEALTH: 'UnitedHealth',
  XPENG: 'XPeng',
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
  // E304: the initialisms a sweep of the served names found the rule title-casing. "ON" stays out: mid-name
  // "on" is a connective, and LEADING_INITIALISMS keeps ON Semiconductor's.
  'APA', 'ASML', 'BNY', 'BRT', 'BXP', 'CF', 'CMS', 'CRH', 'EOG', 'FIGS', 'HSBC', 'IDEX', 'IQVIA', 'KLA',
  'NIO', 'NVR', 'PDD', 'PPL', 'PTC', 'SAP', 'TE', 'TKO', 'UDR',
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

/**
 * Initialisms that are also words, kept upper only as a name's first token and only before their partner token:
 * "ON SEMICONDUCTOR CORP" -> "ON Semiconductor Corp". Mid-name "on" is a connective, and 36 other names EDGAR lists in
 * capitals lead with it, most as the word ("ON TRACK INNOVATIONS LTD" -> "On Track Innovations Ltd"). Keys and partners
 * are upper-cased tokens, punctuation stripped.
 */
const LEADING_INITIALISMS: Record<string, string> = {
  ON: 'SEMICONDUCTOR',
}

const hasLowercase = (s: string): boolean => /\p{Ll}/u.test(s)

/** A trailing group of tickers in parentheses, as EDGAR's full-text search folds a filer's tickers into its display name
    ("BOEING CO (BA, BA-PA)", "FLYEXCLUSIVE INC. (FLYX, FLYX-WT)"): each a ticker's shape in capitals, comma-separated. */
const TICKER_GROUP = /(?:^|\s+)(\((?:[A-Z0-9][A-Z0-9.-]{0,9})(?:,\s*[A-Z0-9][A-Z0-9.-]{0,9})*\))$/

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

/** Title-case one run of letters; single letters stay upper ("A O Smith"). The run is lowercased whole, so a letter
    whose lowercase depends on its neighbours takes it there (a Greek word's final sigma: "ΟΣ" -> "Ος"), and its first
    letter, a whole code point, takes its own capital ("İSTANBUL" -> "İstanbul"). */
const caseSegment = (segment: string): string => {
  if (segment.length <= 1) return segment.toUpperCase()
  const first = String.fromCodePoint(segment.codePointAt(0) ?? 0)
  return first.toUpperCase() + segment.toLowerCase().slice(first.toLowerCase().length)
}

const caseToken = (token: string, isFirst: boolean): string => {
  const upper = token.toUpperCase()
  // Whole-token lookups first (entries such as "U.S." carry their own punctuation).
  if (OVERRIDES[upper]) return OVERRIDES[upper]
  if (KEEP_UPPER.has(upper)) return upper
  // Then the core with glued punctuation stripped: "(IBM)", "IBM,", "CO." -> lookup "IBM" / "CO". It comes before the
  // digit rule, so an override holding a digit keeps its casing with punctuation glued on ("L3HARRIS,").
  const [lead, core, trail] = splitPunctuation(token)
  const coreUpper = core.toUpperCase()
  if (OVERRIDES[coreUpper]) return lead + OVERRIDES[coreUpper] + trail
  if (KEEP_UPPER.has(coreUpper)) return lead + coreUpper + trail
  // Digits, ampersands: ticker-like or brand tokens ("3M", "AT&T", "S&P") -> as-is.
  if (/[0-9&]/.test(token)) return token
  // A legal form with EDGAR's marker glued on: the word before the first slash cased on its own, each marker as served
  // ("INC/DE" -> "Inc/DE"); a marker alone ("/DE/") as served. A marker never takes the word rules ("DE" is a connective).
  const slash = token.indexOf('/')
  if (slash === 0) return token
  if (slash > 0) return caseToken(token.slice(0, slash), isFirst) + token.slice(slash)
  const lower = core.toLowerCase()
  if (!isFirst && LOWER_MIDWORD.has(lower)) return lead + lower + trail
  // Case each run of letters separately so joiners survive: "COCA-COLA", "O'REILLY", "U.S.". A letter is any script's,
  // its accents with it (rule 5), so "SOCIÉTÉ" is one run.
  return token.replace(/[\p{L}\p{M}]+/gu, caseSegment).replace(/'S(?=[^A-Za-z0-9]*$)/, "'s")
}

/**
 * Returns the display form of a company name (see the module rule above). Null/undefined yield
 * an empty string so call sites can `|| ticker` without a separate null check.
 */
export function formatCompanyName(name: string | null | undefined): string {
  if (!name) return ''
  const trimmed = name.trim()
  if (!trimmed) return ''
  // Rule 3: a trailing group of tickers stays as served, and the name before it takes the casing rules.
  const group = TICKER_GROUP.exec(trimmed)
  if (group) {
    const head = formatCompanyName(trimmed.slice(0, group.index))
    return head ? `${head} ${group[1]}` : group[1]
  }
  const tokens = trimmed.split(/\s+/)

  // Body = everything before the trailing run of legal-form tokens. Only lowercase IN THE BODY
  // marks a name as already cased; a cased suffix alone ("ELI LILLY & Co") does not.
  let bodyEnd = tokens.length
  while (bodyEnd > 0 && isSuffixToken(tokens[bodyEnd - 1])) bodyEnd -= 1
  if (hasLowercase(tokens.slice(0, bodyEnd).join(' '))) return tokens.join(' ')

  const cased = tokens.map((token, i) => caseToken(token, i === 0))
  // A leading initialism that is also a word stays upper only before its partner (LEADING_INITIALISMS).
  if (tokens.length > 1) {
    const [lead, core, trail] = splitPunctuation(tokens[0])
    const partner = LEADING_INITIALISMS[core.toUpperCase()]
    if (partner !== undefined && partner === splitPunctuation(tokens[1])[1].toUpperCase()) {
      cased[0] = lead + core.toUpperCase() + trail
    }
  }
  return cased.join(' ')
}
