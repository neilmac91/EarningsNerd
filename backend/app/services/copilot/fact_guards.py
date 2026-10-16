"""Copilot fact guards: the provenance, value, currency and concept checks a fact marker must pass."""
from __future__ import annotations

import json
import math
import re
from datetime import date
from typing import Any, Optional

from app.services import copilot_tools
from app.services.copilot.figures import _figure_extent, _figure_matches_value, _figure_sign_agrees, _is_year


def _reporting_currency(filing: Any) -> Optional[str]:
    data = getattr(filing, "xbrl_data", None)
    unit = copilot_tools.canonical_unit(data.get("reporting_currency")) if isinstance(data, dict) else None
    return unit if unit and re.fullmatch(r"[A-Z]{3}", unit) else None


def _valid_fact_provenance(fact: dict, accession: Optional[str], currency: Optional[str] = None) -> bool:
    """The tool boundary must attest the trusted filing before a result earns a verified marker."""
    if not isinstance(accession, str) or not re.fullmatch(r"\d{10}-\d{2}-\d{6}", accession):
        return False
    if not isinstance(fact, dict) or fact.get("accession") != accession:
        return False
    if not isinstance(fact.get("concept"), str) or not fact["concept"].strip():
        return False
    raw_tag = fact.get("raw_tag")
    if raw_tag is not None and (not isinstance(raw_tag, str) or not raw_tag.strip()):
        return False
    value = fact.get("value")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return False
    unit = copilot_tools.canonical_unit(fact.get("unit"))
    if unit is None or (currency and unit not in {"pure", "shares", currency, f"{currency}/shares"}):
        return False
    try:
        end = date.fromisoformat(fact["period_end"])
        start = date.fromisoformat(fact["period_start"]) if fact.get("period_start") else None
        if start and start > end:
            return False
    except (KeyError, TypeError, ValueError):
        return False
    kind = fact.get("kind") or fact.get("value_kind")
    if kind is not None and kind not in {"margin", "yoy_growth"}:
        return False
    if kind in {"margin", "yoy_growth"}:
        operands = fact.get("source_facts")
        if unit != "pure" or not isinstance(operands, list) or len(operands) != 2:
            return False
        if any(not _valid_fact_provenance(item, accession, currency) or item.get("kind") or item.get("value_kind")
               for item in operands):
            return False
    return True


def _fact_identity(fact: dict) -> str:
    """One marker per exact fact/expression; different operands cannot alias a result."""
    keys = ("concept", "raw_tag", "accession", "unit", "period_start", "period_end", "fiscal_year",
            "fiscal_period", "kind", "value", "denominator_concept", "source_facts")
    return json.dumps({key: fact.get(key) for key in keys}, sort_keys=True, separators=(",", ":"))


# How far back (chars) to look for the figure a fact marker claims to support.
_ADJACENCY_WINDOW_CHARS = 64

_NUMBER_TOKEN = re.compile(
    r"(\$)?\s*([0-9][\d,]*(?:\.\d+)?)\s*(billion|million|thousand|bn|[bmk%])?",
    re.IGNORECASE,
)


def _claim_span_start(marker_start: int, prev_marker_end: int) -> int:
    """Where a marker's claim span begins: up to ``_ADJACENCY_WINDOW_CHARS`` back, bounded by the
    previous citation marker (a marker vouches for the claim SINCE the last citation). THE single
    window rule — shared by the adjacency guards, the coverage counter, and the eval scorer."""
    return max(0, marker_start - _ADJACENCY_WINDOW_CHARS, prev_marker_end)


def _adjacency_window(text: str, marker_start: int, prev_marker_end: int) -> str:
    """The claim span a fact marker vouches for (see :func:`_claim_span_start`)."""
    return text[_claim_span_start(marker_start, prev_marker_end):marker_start]


def _fact_matches_adjacent_number(fact: dict, window: str) -> bool:
    """True when a figure stated just before the fact's marker plausibly IS the fact's value.

    The trust guard for TOOL citations (field report: the model reused revenue fact markers
    [F1]/[F2]/[F3] as year markers on gross-profit/operating-income/net-income figures, so
    chips opened provenance for a DIFFERENT metric than the claim). Text citations verify by
    excerpt matching; fact citations verify by VALUE ADJACENCY: some number in the preceding
    window must match the fact's magnitude at display-rounding tolerance ("$81.46B" / "81.46" /
    "$2.04"; a scale word or $ is read at face value) and must not state the opposite sign
    ("net income was $1.2B" on a loss, "grew 15.3%" on a decline). See ``copilot.figures``.

    Falsification-only: a window with NO number tokens can't be checked — the marker is kept
    (qualitative placements like "margins compressed [F1]" exist). Bare 4-digit integers that
    read as years (1900-2100, no $, no scale suffix) are ignored as context, not figures.

    The caller bounds ``window`` at the previous citation marker: a marker vouches for the
    claim SINCE the last citation, so a matching figure from the preceding, already-cited
    claim must not vouch for a reused marker sitting on a different number.
    """
    try:
        float(fact.get("value"))
    except (TypeError, ValueError):
        return True
    # Prior markers in the window ([2], [F1]) are citations, not figures — scrub them.
    scrubbed = re.sub(r"\[\s*F?\s*\d+\s*\]", " ", window, flags=re.IGNORECASE)
    figures = [m for m in _NUMBER_TOKEN.finditer(scrubbed) if not _is_year(m)]
    if not figures:
        return True
    for m in figures:
        # The figure's own clause (see ``_CLAUSE_BOUNDARY``), read through parentheses around the
        # figure alone, carries its growth-direction wording ("revenue declined (15.3%)").
        start, end = _figure_extent(m)
        clause = (_CLAUSE_BOUNDARY.split(scrubbed[:start])[-1] + scrubbed[start:end]
                  + _CLAUSE_BOUNDARY.split(scrubbed[end:])[0])
        if _figure_matches_value(fact, m) and _figure_sign_agrees(fact, m, clause):
            return True
    return False


# Explicit currency labels attached to a financial figure; absent labels remain unknown.
_CURRENCY_TOKEN = r"(?:U\.S\. dollars?|US dollars?|euros?|pounds sterling|Chinese yuan|renminbi|US\$|NT\$|HK\$|RMB|CNY|USD|TWD|EUR|GBP|JPY|CAD|AUD|HKD|DKK|CHF|€|£|\$)"
_CURRENCY_BEFORE = re.compile(r"(?<![A-Za-z])(" + _CURRENCY_TOKEN + r")\s*$", re.I)
_CURRENCY_AFTER = re.compile(r"^\s*(" + _CURRENCY_TOKEN + r")(?![A-Za-z])", re.I)
_CURRENCY_ALIASES = {"US$": "USD", "$": "USD", "NT$": "TWD", "HK$": "HKD", "€": "EUR", "£": "GBP", "RMB": "CNY", "U.S. DOLLAR": "USD", "U.S. DOLLARS": "USD", "US DOLLAR": "USD", "US DOLLARS": "USD", "EURO": "EUR", "EUROS": "EUR", "POUNDS STERLING": "GBP", "CHINESE YUAN": "CNY", "RENMINBI": "CNY"}


def _fact_matches_adjacent_currency(fact: dict, window: str) -> bool:
    """Falsify explicit wrong currency on a matching figure, without guessing absent currency."""
    unit = copilot_tools.canonical_unit(fact.get("unit"))
    if unit is None or unit in {"pure", "shares"}:
        return True
    expected = unit.split("/", 1)[0]
    # Supported inline emphasis/code delimiters do not separate currency from its figure.
    window = re.sub(r"[*_`]+", "", window)
    scrubbed = re.sub(r"\[\s*F?\s*\d+\s*\]", " ", window, flags=re.I)
    for match in _NUMBER_TOKEN.finditer(scrubbed):
        # Magnitude alone picks out the fact's figure; its sign is the value guard's question.
        if not (_is_year(match) or _figure_matches_value(fact, match)):
            continue
        before = _CURRENCY_BEFORE.search(scrubbed[:match.start()].rstrip())
        # The number token owns an optional bare $, so inspect the currency prefix including it.
        if match[1]:
            before = _CURRENCY_BEFORE.search(scrubbed[:match.start(1) + 1].rstrip())
        after = _CURRENCY_AFTER.match(scrubbed[match.end():])
        for declared in (before, after):
            if declared:
                label = declared[1].upper()
                if _CURRENCY_ALIASES.get(label, label) != expected:
                    return False
    return True


# How prose names each standardized concept — the vocabulary for the CONCEPT adjacency check.
# Phrase-containment, lowercase. Deliberately curated and conservative: a paraphrase missing from
# a fact's own list can only cause a KEPT marker (the check is falsification-only), never a strip.
# Margin phrasings live under their numerator concept (compute_metric results carry the numerator
# as ``concept``). Unknown concepts aren't checkable and always keep their marker.
_CONCEPT_SYNONYMS: dict[str, tuple[str, ...]] = {
    "revenue": ("revenue", "net sales", "total sales", "sales", "top line", "top-line", "turnover"),
    "net_income": (
        "net income", "net earnings", "net profit", "net loss", "bottom line", "bottom-line",
        "net margin", "profit margin",
    ),
    "gross_profit": ("gross profit", "gross margin", "gross income", "gross loss"),
    "operating_income": (
        "operating income", "operating profit", "operating loss", "income from operations",
        "operating margin", "ebit",
    ),
    "total_assets": ("total assets",),
    "total_liabilities": ("total liabilities",),
    "stockholders_equity": (
        "stockholders' equity", "stockholders equity", "shareholders' equity",
        "shareholders equity", "total equity", "book value",
    ),
    "cash_and_equivalents": (
        "cash and cash equivalents", "cash and equivalents", "cash & equivalents",
        "cash position", "cash balance",
    ),
    "eps_basic": ("earnings per share", "eps", "per share", "loss per share"),
    "eps_diluted": ("earnings per share", "eps", "per share", "per diluted share", "loss per share"),
    "shares_outstanding": (
        "shares outstanding", "share count", "outstanding shares", "weighted average shares",
    ),
}


# Word-boundary alternations per concept — bare substring containment false-matches constantly in
# earnings prose ("ebit" in EBITDA/debit, "eps" in steps/keeps, "sales" in Salesforce).
_CONCEPT_PATTERNS: dict[str, re.Pattern] = {
    concept: re.compile(r"\b(?:" + "|".join(re.escape(p) for p in phrases) + r")\b")
    for concept, phrases in _CONCEPT_SYNONYMS.items()
}
# Clause boundaries: only the FINAL clause of the claim span names the figure the marker sits on;
# earlier clauses are context ("Driven by strong sales, the company earned $7.09B [F1]" — "sales"
# is a driver mention, not the figure's label). A period/comma followed by a digit is inside a
# number ("$96.77B", "1,023"), not a boundary.
_CLAUSE_BOUNDARY = re.compile(r"[;:()—–]|[.,](?![0-9])")


def _fact_matches_adjacent_concept(fact: dict, window: str) -> bool:
    """True unless the figure's own clause names a DIFFERENT known metric and the span never
    names the fact's own.

    The companion to the VALUE check: value adjacency can't catch a chip whose value matches but
    whose claim mislabels the metric ("operating income was $96.77B [F2]" where [F2] is the
    same-valued REVENUE fact) — right number, wrong label, and the chip would still open the wrong
    provenance. Falsification-only, doubly conservative: the fact's own concept must be absent
    from the WHOLE span, and another curated concept must be named (word-boundary match) in the
    figure's own final clause. Ambiguous or paraphrased claims keep their marker.
    """
    concept = str(fact.get("concept") or "").lower()
    own = _CONCEPT_PATTERNS.get(concept)
    if own is None:
        return True  # unknown concept — not checkable
    # Curly apostrophes are common in model prose ("stockholders’ equity") — normalize so the
    # straight-quote synonyms match; a missed OWN match is a false-strip vector.
    low = window.lower().replace("’", "'")
    if own.search(low):
        return True
    clause = _CLAUSE_BOUNDARY.split(low)[-1]
    for other, pattern in _CONCEPT_PATTERNS.items():
        if other != concept and pattern.search(clause):
            return False
    return True
