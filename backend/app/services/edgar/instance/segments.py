"""Accession-aware XBRL extraction: segments."""

from typing import Any, Dict, List, Optional, Tuple

from .core import (
    _CONCEPT_NAMESPACES,
    _currency,
    _iso_date,
    _numeric,
    _parse_decimals,
    _reporting_currency,
    _series_from_values,
    duration_in_window,
    logger,
)

# ---------------------------------------------------------------------------
# Reportable-SEGMENT disaggregation (roadmap T5.2). The consolidated series paths deliberately DROP
# every dimensional fact (`if row.get("is_dimensioned"): continue`); segment revenue/operating-income
# live ONLY on those dimensional facts, under the ASC-280 operating-segments axis. These helpers keep
# them — filtered to that axis, to the filing's own reporting period, and to real reportable segments
# (corporate/elimination/total roll-ups dropped) — reusing the same period/currency/resolution
# discipline as the consolidated series so a segment figure is grounded exactly like a headline one.

# ASC-280 reportable-operating-segments axis. edgartools matches this namespace/underscore-agnostically
# ("us-gaap:StatementBusinessSegmentsAxis" / "…_StatementBusinessSegmentsAxis" all resolve). Members are
# filer-defined — geographic for some filers (AAPL: Americas/Europe/…), product for others (MSFT:
# Intelligent Cloud/…); both are the correct ASC-280 operating segments.
SEGMENT_AXIS = "StatementBusinessSegmentsAxis"


# Members that ride the segment axis but are NOT reportable segments: corporate/unallocated buckets,
# intersegment eliminations, reconciling items, and roll-up totals. Counting them double-counts the
# consolidated total, so they are dropped (case-insensitive substring match on the member label).
_SEGMENT_MEMBER_SKIP: Tuple[str, ...] = (
    "corporate", "elimination", "intersegment", "reconcil", "consolidat",
    "total", "all other", "unalloc", "adjustment",
)


def _segment_member_label(row: Dict[str, Any]) -> Optional[str]:
    """Clean display label for a segment-member fact row ('Americas'), or None.

    Prefers edgartools' ``dimension_member_label`` (from the element catalog, with the "[Member]"
    suffix stripped), then ``label``, then the raw ``member`` QName's local part with the
    ``SegmentMember``/``Member`` suffix trimmed.
    """
    for key in ("dimension_member_label", "label"):
        val = row.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    member = row.get("member")
    if isinstance(member, str) and member.strip():
        local = member.split(":")[-1]
        for suffix in ("SegmentMember", "Member"):
            if local.endswith(suffix):
                local = local[: -len(suffix)]
                break
        return local or None
    return None


def _is_reportable_segment(label: str) -> bool:
    """False for corporate/elimination/reconciliation/total members that ride the same axis."""
    low = label.lower()
    return not any(skip in low for skip in _SEGMENT_MEMBER_SKIP)


def _passes_consolidation_axis(row: Dict[str, Any]) -> bool:
    """Phantom-segment guard for cross-tabbed facts. ``by_dimension(SEGMENT_AXIS)`` matches any fact
    carrying that axis, INCLUDING facts also tagged with ``srt:ConsolidationItemsAxis`` — where a
    reconciling member (intersegment elimination, corporate-non-segment) can ride the segment axis and
    slip past the label filter. When that co-axis is present on the fact, require its member to be
    ``OperatingSegments`` (the ASC-280 reportable marker); filers that do not tag it (e.g. MSFT) pass
    unconstrained. Verified: AAPL/KO tag it as OperatingSegmentsMember (kept); an elimination member
    is dropped."""
    for key, val in row.items():
        if not (isinstance(key, str) and key.lower().startswith("dim_") and "consolidationitems" in key.lower()):
            continue
        # Robust missing-value check: the cell is None / float-NaN / pandas NA / NaT when a fact does not
        # carry this co-axis (mixed-tagging filers). A string compare keeps pd.NA away from a `!= self`
        # test and treats a missing cell as "unconstrained → keep" rather than silently dropping the
        # segment. Only a PRESENT, non-OperatingSegments member drops the row.
        text = "" if val is None else str(val).strip().lower()
        if text in ("", "nan", "<na>", "none", "nat"):
            return True
        return "operatingsegments" in text
    return True


def _segment_fact_records(xb: Any, concept: str, axis: str) -> List[Dict[str, Any]]:
    """Dimensional facts for a concept on a specific axis (us-gaap then ifrs-full).

    ``by_dimension(axis)`` filters to that axis AND auto-enables the ``member`` /
    ``dimension_member_label`` columns (edgartools GH-574/607), so a single query yields exactly the
    per-segment rows with their labels. Empty DataFrame (never None) when the filer tagged no such
    dimension — the single-segment / undimensioned case.
    """
    for namespace in _CONCEPT_NAMESPACES:
        try:
            df = (
                xb.facts.query()
                .by_concept(f"{namespace}:{concept}", exact=True)
                .by_dimension(axis)
                .to_dataframe()
            )
        except Exception as exc:  # noqa: BLE001 - any query failure means "no facts"
            logger.debug(f"Segment fact query failed for {namespace}:{concept} on {axis}: {exc}")
            continue
        if df is not None and not getattr(df, "empty", True):
            return df.to_dict("records")
    return []


def segment_series_by_member(
    xb: Any,
    concepts: List[str],
    form: str,
    period_of_report: str,
    axis: str = SEGMENT_AXIS,
    max_items: int = 2,
) -> Tuple[Dict[str, List[Tuple[str, float]]], Optional[str]]:
    """Per-reportable-segment duration series for the first candidate concept that yields segment facts.

    The dimensional analogue of :func:`duration_series_currency_concept`, grouped by segment member:
    keeps ``is_dimensioned`` rows on ``axis``, drops non-reportable members, constrains to the form's
    standard duration ending at (or before) ``period_of_report``, filters to the issuer's reporting
    currency, resolves one value per (member, period-end) via the same ``_resolve_period_value``
    rounding logic, and requires the winning concept to carry a fact at the filing's OWN
    period_of_report (the anchor — a member with only prior-period facts is a dropped segment and is
    excluded). Returns ({member_label: [(end, value), …] newest-first}, currency); **({}, None)** when
    no reportable segment is tagged — single-segment, undimensioned, or (per the concept-list ordering,
    which skips generic revenue tags for banks) financial-institution filers. Concepts are never mixed.
    """
    for concept in concepts:
        candidates: List[Tuple[str, str, float, Optional[str], float]] = []  # (label,end,value,ccy,dec)
        for row in _segment_fact_records(xb, concept, axis):
            if not row.get("is_dimensioned"):
                continue
            if not _passes_consolidation_axis(row):
                continue  # reconciling/elimination member riding the segment axis (cross-tab)
            label = _segment_member_label(row)
            if not label or not _is_reportable_segment(label):
                continue
            end = _iso_date(row.get("period_end"))
            value = _numeric(row.get("numeric_value"))
            if end is None or value is None or end > period_of_report:
                continue
            if not duration_in_window(row.get("period_start"), end, form):
                continue
            candidates.append((label, end, value, _currency(row), _parse_decimals(row.get("decimals"))))
        if not candidates:
            continue
        currency = _reporting_currency([(c[1], c[2], c[3], c[4]) for c in candidates], period_of_report)
        per_member: Dict[str, Dict[str, List[Tuple[float, float]]]] = {}
        for label, end, value, ccy, dec in candidates:
            if currency is not None and ccy != currency:
                continue
            per_member.setdefault(label, {}).setdefault(end, []).append((round(value, 4), dec))
        out: Dict[str, List[Tuple[str, float]]] = {}
        for label, values_by_end in per_member.items():
            series = _series_from_values(values_by_end, period_of_report, max_items)
            if series:
                out[label] = series
        if out:
            return out, currency
    return {}, None
