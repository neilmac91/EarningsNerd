"""Accession-aware XBRL extraction: core."""

import logging
import math
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("app.services.edgar.instance_extractor")


# Acceptable duration windows in days. 52/53-week fiscal years run 364-371
# days; fiscal quarters run 84-98. Anything outside is the wrong period slice
# (Q4 vs FY, quarter vs YTD) and must not be reported as the filing's figure.
# 20-F / 40-F are foreign ANNUAL reports, so they share the 10-K annual window.
DURATION_WINDOWS: Dict[str, Tuple[int, int]] = {
    "10-K": (320, 390),
    "10-Q": (75, 105),
    "20-F": (320, 390),
    "40-F": (320, 390),
}


def normalize_form(form: Optional[str]) -> str:
    """Normalize a form label to its base type: "10-K/A" -> "10-K"."""
    return str(form or "").split("/")[0].strip().upper()


def _iso_date(value: Any) -> Optional[str]:
    """Coerce a period boundary to an ISO date string, or None.

    Fact-query DataFrames may carry dates as strings, datetimes, NaN (missing
    period_start on instant facts) or NaT; only a YYYY-MM-DD prefix survives.
    """
    if value is None:
        return None
    if isinstance(value, float) and value != value:  # NaN
        return None
    text = str(value)[:10]
    if len(text) == 10 and text[:4].isdigit() and text[4] == "-" and text[7] == "-":
        return text
    return None


def duration_in_window(start: Any, end: Any, form: str) -> bool:
    """True when [start, end] spans the standard duration for the base form."""
    window = DURATION_WINDOWS.get(normalize_form(form))
    start_iso, end_iso = _iso_date(start), _iso_date(end)
    if window is None or not start_iso or not end_iso:
        return False
    try:
        days = (date.fromisoformat(end_iso) - date.fromisoformat(start_iso)).days
    except (ValueError, TypeError):
        return False
    low, high = window
    return low <= days <= high


# Taxonomies tried per concept, in order. US-GAAP first (the common case, incl. Alibaba); IFRS
# only reached when the us-gaap query is empty, so domestic filers pay no extra query.
_CONCEPT_NAMESPACES: Tuple[str, ...] = ("us-gaap", "ifrs-full")


def _fact_records_with_concept(
    xb: Any, concept: str,
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Facts and the exact successful query identity; try us-gaap then ifrs-full.

    A foreign private issuer reporting under IFRS tags the concept in the ``ifrs-full`` namespace;
    a domestic/US-GAAP filer (incl. Alibaba) tags it in ``us-gaap``. The first namespace that
    yields facts wins, so the same candidate name resolves in whichever taxonomy the filer used.
    """
    for namespace in _CONCEPT_NAMESPACES:
        try:
            df = xb.facts.query().by_concept(f"{namespace}:{concept}", exact=True).to_dataframe()
        except Exception as exc:  # noqa: BLE001 - any query failure means "no facts"
            logger.debug(f"Fact query failed for {namespace}:{concept}: {exc}")
            continue
        if df is not None and not getattr(df, "empty", True):
            return df.to_dict("records"), f"{namespace}:{concept}"
    return [], None


def _currency(row: Dict[str, Any]) -> Optional[str]:
    """Reporting currency (ISO-4217) of a fact row, or None when absent/non-monetary.

    edgartools exposes a ``currency`` column per fact; per-share and unitless facts carry no
    currency. Returns an upper-cased code (e.g. "CNY", "USD", "EUR") or None.
    """
    ccy = row.get("currency")
    if ccy is None:
        return None
    if isinstance(ccy, float) and ccy != ccy:  # float NaN — keep this guard: str(nan)=="nan",
        return None                            # which would otherwise pass the 3-alpha check below.
    text = str(ccy).strip().upper()
    # ISO-4217 codes are exactly three letters; this also rejects pandas <NA>, "" and other junk.
    return text if len(text) == 3 and text.isalpha() else None


def _reporting_currency(
    candidates: List[Tuple[str, float, Optional[str], float]],
    period_of_report: str,
) -> Optional[str]:
    """Pick the issuer's reporting currency from candidate facts for one concept.

    Foreign filers (e.g. Alibaba) tag the SAME line in BOTH their reporting currency (all periods)
    AND a USD convenience translation (usually only the latest period). The reporting currency is
    the one covering the most distinct period-ends; ties prefer the currency present at the filing's
    own period_of_report, then alphabetical for determinism. Returns None when no fact carries a
    currency (unit tests, per-share concepts), which disables currency filtering.
    """
    ends_by_ccy: Dict[Optional[str], set] = {}
    for cand in candidates:  # candidates carry (end, value, ccy[, decimals]); only end + ccy are used
        ends_by_ccy.setdefault(cand[2], set()).add(cand[0])
    real = {c: ends for c, ends in ends_by_ccy.items() if c}
    if not real:
        return None
    # Rank by: most distinct period-ends (the native currency spans all presented years; a USD
    # convenience translation is usually only the latest year), then presence at the filing's own
    # period, then prefer a NON-USD code (USD is the convenience-translation convention, so on a tie
    # the native currency wins), then alphabetical for determinism.
    return max(
        real.items(),
        key=lambda item: (
            len(item[1]),
            period_of_report in item[1],
            item[0] != "USD",
            item[0],
        ),
    )[0]


def _numeric(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if number != number else number  # NaN guard


def _parse_decimals(raw: Any) -> float:
    """XBRL ``decimals`` as a precision rank (higher = finer): 'INF' → +inf; missing/junk → -inf."""
    if raw is None:
        return float("-inf")
    text = str(raw).strip().upper()
    if text in ("INF", "+INF"):
        return float("inf")
    try:
        return float(int(text))
    except (TypeError, ValueError):
        return float("-inf")


def _resolve_period_value(facts: List[Tuple[float, float]]) -> Optional[float]:
    """The single consolidated value for one period end, or None when genuinely ambiguous.

    A filer sometimes tags the same line twice undimensioned at different precision — e.g. revenue
    as 32,667,300,000 (``decimals=-5``) AND a rounded 32,700,000,000 (``decimals=-8``). These are
    the same figure, so the finest-precision value wins, PROVIDED every coarser value equals that
    value rounded to the coarser fact's own ``decimals``. Values that are not such a clean rounding
    are genuinely divergent (e.g. an unreconciled restatement) and stay ambiguous → None (dropped) —
    which is also the conservative result when precision is unknown (decimals missing → -inf).
    """
    distinct = {round(v, 4) for v, _ in facts}
    if len(distinct) <= 1:
        return next(iter(distinct)) if distinct else None
    best_value, _best_dec = max(facts, key=lambda vd: vd[1])
    for value, dec in facts:
        if round(value, 4) == round(best_value, 4):
            continue
        # `value` must EQUAL `best_value` rounded to the coarser fact's own (finite) decimals — else
        # it's a genuine conflict. Compare at fixed precision (>= 4 dp) rather than an absolute
        # tolerance, so positive decimals (cents, EPS) and same-precision distinct values (e.g.
        # 100 vs 101 at decimals=0) are not silently collapsed. Guard isfinite BEFORE int(dec)
        # (int(±inf) raises).
        if not math.isfinite(dec):
            return None
        ndigits = max(4, int(dec))
        if round(value, ndigits) != round(round(best_value, int(dec)), ndigits):
            return None
    return best_value


def _series_from_values(
    values_by_end: Dict[str, List[Tuple[float, float]]],
    period_of_report: str,
    max_items: int,
) -> List[Tuple[str, float]]:
    """Resolve one value per period end (genuine ambiguity drops the period), newest first.

    Each period maps to its undimensioned (value, decimals) facts; ``_resolve_period_value`` picks
    the consolidated figure or returns None when the values genuinely conflict. Returns [] unless an
    unambiguous entry exists for the filing's own period_of_report — the anchor that proves the
    concept is the one this filing actually reports.
    """
    series: List[Tuple[str, float]] = []
    for end in sorted(values_by_end, reverse=True):
        resolved = _resolve_period_value(values_by_end[end])
        if resolved is None:
            logger.debug(f"Ambiguous consolidated values for {end}: {sorted(values_by_end[end])}")
            continue
        series.append((end, resolved))
    if not series or series[0][0] != period_of_report:
        return []
    return series[:max_items]


def _unanimous_start(starts: Optional[set]) -> Optional[str]:
    """The one start every equal-valued source fact agreed on, or None when they did not."""
    if not starts or len(starts) != 1:
        return None
    only = next(iter(starts))
    return only if isinstance(only, str) else None


def _text_or_none(value: Any) -> Optional[str]:
    """A non-empty stripped string, or None (pandas NaN / <NA> / "" all collapse to None)."""
    if value is None:
        return None
    if isinstance(value, float) and value != value:  # NaN
        return None
    text = str(value).strip()
    return text or None
