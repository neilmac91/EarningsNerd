"""Display casing for company names: the backend's copy of ``frontend/lib/formatCompanyName.ts``.

EDGAR stores issuer names in capitals ("REGENERON PHARMACEUTICALS, INC."), which reads as shouting in an
export's title. ``display_company_name`` gives a name the casing the page, the chart PNG and the browser
tab print, for DISPLAY only: the raw name stays the data value (a dataset's ``company_name`` feeds its
fingerprint), so nothing downstream of an export reads a rewritten string.

The rule is the TypeScript module's, line for line (its docstring states it in full):

1. A name whose body (every token before the trailing run of legal-form tokens) already holds a lowercase
   letter, in any script, is returned as served.
2. Otherwise each token is title-cased, except: a token with a digit or an ampersand stays as served; a
   token with a slash cases the word before the first slash and keeps each marker after it ("INC/DE" ->
   "Inc/DE"); OVERRIDES take their brand casing; KEEP_UPPER stays upper; LOWER_MIDWORD is lowercased
   unless it leads. Lookups ignore punctuation glued to a token.
3. A trailing group of tickers in parentheses ("BOEING CO (BA, BA-PA)") stays as served.
4. Punctuation is never added or removed; joined segments are cased one by one, with a trailing "'S" -> "'s".
5. A letter is any script's, with its accents: a word is lowercased whole (a Greek final sigma keeps its
   form) and its first letter takes its own capital; a script without case is left as served.

The port keeps JavaScript's semantics where Python's differ: whitespace is the set JavaScript's ``\\s`` and
``trim()`` read (``_SPACE``), a lowercase letter is general category Ll as ``\\p{Ll}`` reads it (Python's
``islower`` also counts Other_Lowercase, such as "ª"), and an anchor at the end is ``\\Z`` (Python's ``$``
also matches before a final newline). ``backend/tests/fixtures/company_display_names.json`` is the one case
table both copies run (``tests/unit/test_company_names.py`` and ``formatCompanyName.spec.ts``), and the
Python test holds the four word lists below equal to the TypeScript module's.
"""
from __future__ import annotations

import re
import unicodedata
from itertools import groupby

# Exact-token brand casings (keys are the upper-cased source token, punctuation stripped).
OVERRIDES: dict[str, str] = {
    "JPMORGAN": "JPMorgan",
    "EBAY": "eBay",
    "PAYPAL": "PayPal",
    "PEPSICO": "PepsiCo",
    "EXXONMOBIL": "ExxonMobil",
    "CONOCOPHILLIPS": "ConocoPhillips",
    "GLAXOSMITHKLINE": "GlaxoSmithKline",
    "ASTRAZENECA": "AstraZeneca",
    "BIONTECH": "BioNTech",
    "NETAPP": "NetApp",
    "DOORDASH": "DoorDash",
    "LINKEDIN": "LinkedIn",
    "YOUTUBE": "YouTube",
    "MCDONALD'S": "McDonald's",
    "MCDONALDS": "McDonalds",
    "MCKESSON": "McKesson",
    "MCCORMICK": "McCormick",
    "IPHONE": "iPhone",
}

# Tokens that stay upper-case: legal-form initialisms, brand initialisms, roman numerals.
KEEP_UPPER: frozenset[str] = frozenset({
    # legal forms / structures
    "LLC", "LP", "LLP", "PLC", "NV", "N.V.", "SA", "S.A.", "SE", "AG", "AB", "ASA", "SPA", "S.P.A.",
    "ADR", "ADS", "ETF", "REIT", "USA", "US", "U.S.", "UK", "U.K.",
    # brand initialisms (NIKE and NVIDIA are how those companies style their own names)
    "IBM", "AMD", "HP", "GE", "UPS", "CVS", "CSX", "KKR", "TJX", "HCA", "ADP", "ADM", "AIG", "AES",
    "AMC", "NVIDIA", "NIKE", "RTX", "DTE", "PPG", "PNC", "AFLAC", "CBRE", "CDW", "CME", "CSC", "DXC",
    "EQT", "FMC", "ITT", "MGM", "MSCI", "NRG", "NXP", "ONEOK", "PVH", "SBA", "SVB", "TD", "UBS", "VF",
    "WEC", "WPP",
    # roman numerals
    "II", "III", "IV",
})

# Legal-form / registration tokens EDGAR often leaves as the ONLY cased part of a name ("PROCTER & GAMBLE
# Co"), compared after punctuation stripping and upper-casing; a slash token ("/DE/") is a suffix by shape.
LEGAL_SUFFIX: frozenset[str] = frozenset({
    "INC", "INCORPORATED", "CORP", "CORPORATION", "CO", "COMPANY", "LTD", "LIMITED", "LLC", "LLP",
    "LP", "PLC", "NV", "SA", "AG", "SE", "AB", "ASA", "SPA", "HOLDINGS", "GROUP", "TRUST",
})

# Connectives lowercased mid-name ("Bank of America"; "The Home Depot" keeps its leading "The").
LOWER_MIDWORD: frozenset[str] = frozenset({
    "of", "the", "and", "for", "in", "on", "at", "by", "to",
    "de", "del", "la", "da", "di", "du", "van", "von", "y", "et",
})

# JavaScript's WhiteSpace and LineTerminator, the set its \s, split(/\s+/) and trim() read, written as
# escapes for re to read: a raw U+2028 in the source would split this line for str.splitlines().
_SPACE = r"[\t\n\v\f\r \u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff]"
_TRIM = re.compile(rf"\A{_SPACE}+|{_SPACE}+\Z")
_SPLIT = re.compile(rf"{_SPACE}+")

# A trailing group of tickers in parentheses, as EDGAR's full-text search folds a filer's tickers into its
# display name ("BOEING CO (BA, BA-PA)"): each a ticker's shape in capitals, comma-separated.
TICKER_GROUP = re.compile(
    rf"(?:^|{_SPACE}+)(\((?:[A-Z0-9][A-Z0-9.-]{{0,9}})(?:,{_SPACE}*[A-Z0-9][A-Z0-9.-]{{0,9}})*\))\Z"
)

_PUNCTUATION = re.compile(r"\A([^A-Za-z0-9]*)(.*?)([^A-Za-z0-9]*)\Z")
_DIGIT_OR_AMPERSAND = re.compile(r"[0-9&]")
_POSSESSIVE = re.compile(r"'S(?=[^A-Za-z0-9]*\Z)")


def _is_letter(char: str) -> bool:
    """A letter of any script or a mark on one (JavaScript's [\\p{L}\\p{M}])."""
    return unicodedata.category(char)[0] in "LM"


def _has_lowercase(text: str) -> bool:
    """JavaScript's /\\p{Ll}/u: a character of general category Ll."""
    return any(unicodedata.category(char) == "Ll" for char in text)


def _split_punctuation(token: str) -> tuple[str, str, str]:
    """Split "(IBM)," into ("(", "IBM", "),"): leading and trailing non-alphanumerics around the core."""
    match = _PUNCTUATION.match(token)
    return (match[1], match[2], match[3]) if match else ("", token, "")


def _is_suffix_token(token: str) -> bool:
    if "/" in token:
        return True
    return _split_punctuation(token)[1].upper() in LEGAL_SUFFIX


def _case_segment(segment: str) -> str:
    """Title-case one run of letters; a single letter stays upper ("A O Smith"). The run is lowercased whole,
    so a letter whose lowercase depends on its neighbours takes it there (a Greek final sigma), and its first
    letter takes its own capital ("İSTANBUL" -> "İstanbul")."""
    if len(segment) <= 1:
        return segment.upper()
    first = segment[0]
    return first.upper() + segment.lower()[len(first.lower()):]


def _case_letter_runs(token: str) -> str:
    """JavaScript's token.replace(/[\\p{L}\\p{M}]+/gu, caseSegment): each run of letters cased, the rest kept."""
    runs = ("".join(run) for _, run in groupby(token, _is_letter))
    return "".join(_case_segment(run) if _is_letter(run[0]) else run for run in runs)


def _case_token(token: str, is_first: bool) -> str:
    upper = token.upper()
    # Whole-token lookups first (entries such as "U.S." carry their own punctuation).
    if upper in OVERRIDES:
        return OVERRIDES[upper]
    if upper in KEEP_UPPER:
        return upper
    # Digits, ampersands: ticker-like or brand tokens ("3M", "AT&T", "S&P") stay as served.
    if _DIGIT_OR_AMPERSAND.search(token):
        return token
    # A legal form with EDGAR's marker glued on: the word before the first slash cased on its own, each
    # marker as served ("INC/DE" -> "Inc/DE"); a marker alone ("/DE/") as served.
    slash = token.find("/")
    if slash == 0:
        return token
    if slash > 0:
        return _case_token(token[:slash], is_first) + token[slash:]
    # Then the core with glued punctuation stripped: "(IBM)", "IBM,", "CO." -> lookup "IBM" / "CO".
    lead, core, trail = _split_punctuation(token)
    core_upper = core.upper()
    if core_upper in OVERRIDES:
        return lead + OVERRIDES[core_upper] + trail
    if core_upper in KEEP_UPPER:
        return lead + core_upper + trail
    lower = core.lower()
    if not is_first and lower in LOWER_MIDWORD:
        return lead + lower + trail
    # Each run of letters is cased on its own, so joiners survive: "COCA-COLA", "O'REILLY", "U.S.".
    return _POSSESSIVE.sub("'s", _case_letter_runs(token), count=1)


def display_company_name(name: str | None) -> str:
    """The display form of a company name (the module's rule). None and an empty or blank name give "",
    so a call site can write ``display_company_name(name) or ticker``."""
    if not name:
        return ""
    trimmed = _TRIM.sub("", name)
    if not trimmed:
        return ""
    # Rule 3: a trailing group of tickers stays as served; the name before it takes the casing rules.
    group = TICKER_GROUP.search(trimmed)
    if group:
        head = display_company_name(trimmed[:group.start()])
        return f"{head} {group[1]}" if head else group[1]
    tokens = _SPLIT.split(trimmed)

    # The body is every token before the trailing run of legal-form tokens. Only lowercase IN THE BODY marks
    # a name as already cased; a cased suffix alone ("ELI LILLY & Co") does not.
    body_end = len(tokens)
    while body_end > 0 and _is_suffix_token(tokens[body_end - 1]):
        body_end -= 1
    if _has_lowercase(" ".join(tokens[:body_end])):
        return " ".join(tokens)
    return " ".join(_case_token(token, index == 0) for index, token in enumerate(tokens))
