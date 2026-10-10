"""Accession-aware XBRL extraction: series."""

from typing import Any, Dict, List, Optional, Tuple

from .concepts import DIVIDEND_COMPONENT_CONCEPTS
from .core import (
    _currency,
    _fact_records_with_concept,
    _iso_date,
    _numeric,
    _parse_decimals,
    _reporting_currency,
    _series_from_values,
    _unanimous_start,
    duration_in_window,
)


def duration_series_with_starts(
    xb: Any,
    concepts: List[str],
    form: str,
    period_of_report: str,
    max_items: int = 5,
    *,
    qualified_concept: bool = False,
    selected_sources: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[List[Tuple[str, float, Optional[str]]], Optional[str], Optional[str]]:
    """As :func:`duration_series_currency_concept`, but each entry also carries the SOURCE start.

    The duration is what proves a figure covers the year (or quarter) a claim names, and this is
    the only place that knows it: every candidate here already passed ``duration_in_window``, and
    that proof used to be discarded at the tuple boundary — leaving downstream consumers unable to
    tell an annual figure from a quarterly one sharing its period end.

    The start is taken from the exact source fact(s) the value was resolved from — never inferred
    from the form, the fiscal label, the period end, comparative cadence or value matching. When
    the equal-valued facts behind one period disagree on their start, or carry none, the start is
    ``None``: the uncertainty is preserved rather than resolved to a convenient date.

    The optional ``selected_sources`` collector retains the original rows inside this same
    winning resolution for financing source certification; it never changes the returned series.
    """
    if selected_sources is not None:
        selected_sources.clear()
    for concept in concepts:
        candidates: List[Tuple[str, float, Optional[str], float, Optional[str], Dict[str, Any]]] = []
        records, queried_concept = _fact_records_with_concept(xb, concept)
        for row in records:
            if row.get("is_dimensioned"):
                continue
            end = _iso_date(row.get("period_end"))
            value = _numeric(row.get("numeric_value"))
            if end is None or value is None or end > period_of_report:
                continue
            if not duration_in_window(row.get("period_start"), end, form):
                continue
            candidates.append((end, value, _currency(row), _parse_decimals(row.get("decimals")),
                               _iso_date(row.get("period_start")), row))
        currency = _reporting_currency([(e, v, c, d) for e, v, c, d, _s, _r in candidates],
                                       period_of_report)
        values_by_end: Dict[str, List[Tuple[float, float]]] = {}
        # Every start seen for a given (period end, resolved-precision value). One unanimous
        # non-null start is the selected fact's; anything else stays unknown.
        starts_by_entry: Dict[Tuple[str, float], set] = {}
        rows_by_end: Dict[str, List[Dict[str, Any]]] = {}
        for end, value, ccy, dec, start, row in candidates:
            if currency is not None and ccy != currency:
                continue
            rows_by_end.setdefault(end, []).append(row)
            rounded = round(value, 4)
            values_by_end.setdefault(end, []).append((rounded, dec))
            starts_by_entry.setdefault((end, rounded), set()).add(start)
        series = _series_from_values(values_by_end, period_of_report, max_items)
        if series:
            dated = [(end, value, _unanimous_start(starts_by_entry.get((end, round(value, 4)))))
                     for end, value in series]
            if selected_sources is not None:
                # Keep provenance inside the winning resolution, including coarser duplicate
                # facts accepted by the precision resolver. Never re-query by amount afterward.
                selected_sources.extend(
                    {"value": value, "period_end": end, "period_start": start,
                     "currency": currency, "raw_tag": queried_concept, "rows": rows_by_end[end]}
                    for end, value, start in dated
                )
            return dated, currency, queried_concept if qualified_concept else concept
    return [], None, None


def duration_series_currency_concept(
    xb: Any,
    concepts: List[str],
    form: str,
    period_of_report: str,
    max_items: int = 5,
    *,
    qualified_concept: bool = False,
) -> Tuple[List[Tuple[str, float]], Optional[str], Optional[str]]:
    """Income-statement series + reporting currency + the winning concept.

    The first candidate concept with an unambiguous, undimensioned fact of the form's standard
    duration ending on period_of_report wins; its facts for earlier period ends (the filing's own
    comparatives) follow, newest first. Facts are filtered to the issuer's reporting currency
    (so a USD convenience translation alongside a CNY/EUR figure for the same period is NOT treated
    as an ambiguous duplicate, which previously dropped the whole period). Concepts are never mixed
    within one series. Returns (series, currency, concept); currency is None when facts carry no
    currency, and concept is the winning us-gaap/ifrs candidate (recorded as a ``raw_tag`` so
    downstream can detect a concept that flips between filings). Set qualified_concept to retain
    the exact successful namespace query; the default preserves the historical bare-name API.
    Both are None when nothing resolves. Selection, currency filtering and precedence live in
    :func:`duration_series_with_starts`; this drops the per-entry source start so the long-standing
    ``(end, value)`` shape every existing consumer reads is unchanged.
    """
    dated, currency, concept = duration_series_with_starts(
        xb, concepts, form, period_of_report, max_items, qualified_concept=qualified_concept,
    )
    return [(end, value) for end, value, _start in dated], currency, concept


def duration_series_with_currency(
    xb: Any,
    concepts: List[str],
    form: str,
    period_of_report: str,
    max_items: int = 5,
) -> Tuple[List[Tuple[str, float]], Optional[str]]:
    """Back-compat wrapper: income-statement series + currency (drops the winning concept)."""
    series, currency, _concept = duration_series_currency_concept(
        xb, concepts, form, period_of_report, max_items
    )
    return series, currency


def dividend_component_sum_series(
    xb: Any, form: str, period_of_report: str
) -> Tuple[List[Tuple[str, float]], Optional[str]]:
    """Second-tier dividends resolution (T5.3 review, the WFC class): when no TOTAL dividends tag
    exists, resolve each per-class payment component independently and SUM per period — summing only
    what is explicitly tagged. Each component individually passes the full anchoring/window/currency
    discipline of :func:`duration_series_currency_concept`; a currency-mismatched component is never
    summed (apples to oranges — the first-resolved component's currency wins and the mismatch is
    dropped). Returns (series newest-first, currency), empty when no component resolves."""
    totals: Dict[str, float] = {}
    currency: Optional[str] = None
    for concept in DIVIDEND_COMPONENT_CONCEPTS:
        series, ccy, _concept = duration_series_currency_concept(xb, [concept], form, period_of_report)
        if not series:
            continue
        if not totals:
            currency = ccy  # first summed component locks the currency label (may itself be None)
        elif ccy != currency:
            # EXACT match required (Gemini review): an unlabeled (None) component must never sum
            # into a labeled total — or vice versa — any more than a differently-labeled one.
            continue
        for end, value in series:
            totals[end] = totals.get(end, 0.0) + value
    return sorted(totals.items(), key=lambda kv: kv[0], reverse=True), currency


def instant_series_currency_concept(
    xb: Any,
    concepts: List[str],
    period_of_report: str,
    max_items: int = 5,
) -> Tuple[List[Tuple[str, float]], Optional[str], Optional[str]]:
    """Balance-sheet series, reporting currency and selected qualified concept.

    Undimensioned instant facts (no period_start),
    anchored at period_of_report, plus the filing's comparative instants. Facts are filtered to the
    issuer's reporting currency (see ``duration_series_with_currency``)."""
    for concept in concepts:
        candidates: List[Tuple[str, float, Optional[str], float]] = []
        records, qualified_concept = _fact_records_with_concept(xb, concept)
        for row in records:
            if row.get("is_dimensioned"):
                continue
            if _iso_date(row.get("period_start")) is not None:
                continue  # duration fact, not an instant
            # Instant (balance-sheet) facts carry their date in `period_instant`; `period_end` is
            # None for them. Keying only on period_end silently dropped EVERY balance-sheet fact
            # (total assets, equity, debt, cash), so balance-sheet XBRL was always empty and ROE/ROA
            # never derived. Fall back to period_instant.
            end = _iso_date(row.get("period_end")) or _iso_date(row.get("period_instant"))
            value = _numeric(row.get("numeric_value"))
            if end is None or value is None or end > period_of_report:
                continue
            candidates.append((end, value, _currency(row), _parse_decimals(row.get("decimals"))))
        currency = _reporting_currency(candidates, period_of_report)
        values_by_end: Dict[str, List[Tuple[float, float]]] = {}
        for end, value, ccy, dec in candidates:
            if currency is not None and ccy != currency:
                continue
            values_by_end.setdefault(end, []).append((round(value, 4), dec))
        series = _series_from_values(values_by_end, period_of_report, max_items)
        if series:
            return series, currency, qualified_concept
    return [], None, None


def instant_series_with_currency(
    xb: Any,
    concepts: List[str],
    period_of_report: str,
    max_items: int = 5,
) -> Tuple[List[Tuple[str, float]], Optional[str]]:
    """Compatibility pair; preserve selection and queries while hiding concept metadata."""
    series, currency, _concept = instant_series_currency_concept(
        xb, concepts, period_of_report, max_items,
    )
    return series, currency


def duration_series(
    xb: Any,
    concepts: List[str],
    form: str,
    period_of_report: str,
    max_items: int = 5,
) -> List[Tuple[str, float]]:
    """Back-compat wrapper returning only the value series (drops the currency)."""
    return duration_series_with_currency(xb, concepts, form, period_of_report, max_items)[0]


def instant_series(
    xb: Any,
    concepts: List[str],
    period_of_report: str,
    max_items: int = 5,
) -> List[Tuple[str, float]]:
    """Back-compat wrapper returning only the value series (drops the currency)."""
    return instant_series_with_currency(xb, concepts, period_of_report, max_items)[0]
