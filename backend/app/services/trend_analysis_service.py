"""Multi-Period Analysis — the deterministic engine (M2).

Assembles a company's N-period dataset from ``financial_fact`` (one indexed read), computes every
number the product shows or the AI narrates — YoY/QoQ deltas, CAGR, margin/liquidity series, and
deterministic "inflection" signals — and assigns each value a stable ``F#`` citation marker. The
LLM (M3) receives this dataset verbatim and may only cite markers it was given; it NEVER does
arithmetic. That split (server math, model prose) is the same grounding contract Copilot uses.

Readers filter ``fiscal_period == "FY"`` (annual) / ``IN Q1..Q4`` (quarterly), so legacy
NULL-fiscal_period rows can never surface here (D1). Quarterly balance-sheet columns select
instant concepts by ``period_end`` — the fiscal-year-end balance sheet IS the Q4 instant, stored
once under its FY label (D2c).
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Company, FinancialFact
from app.services import citation_markers

logger = logging.getLogger(__name__)

# Bump on ANY change to the narrative prompt or the compact dataset rendering — invalidates every
# cached TrendAnalysis row fleet-wide (they regenerate lazily on next request).
# v2: derived flag narrowed to true computed-Q4 points, CAGR markers, per-marker signal brackets,
# multi-reference resolver, pp-vs-relative guardrail.
# v3: percent-unit series (margins) report YoY/QoQ as percentage-point deltas (not relative %);
# sign-flip growth renders "n/m" instead of a nonsensical percentage.
# v4: a/an-with-numerals voice guard; rule 5 reworded for the YTD9/shares-based Q4 derivations.
PROMPT_VERSION = "trends-v7-observations"

MODES = ("annual", "quarterly")
_QUARTERS = ("Q1", "Q2", "Q3", "Q4")

# Balance-sheet (point-in-time) concepts + their derived metrics: matched by period_end in
# quarterly mode; everything else is a flow/duration concept matched by (fiscal_year, fiscal_period).
INSTANT_CONCEPTS: frozenset[str] = frozenset(
    {
        "total_assets", "cash_and_equivalents", "shareholders_equity", "long_term_debt",
        "current_assets", "current_liabilities", "working_capital", "current_ratio",
    }
)

# Margin concepts are stored ×100 (percent); current_ratio is a plain ratio.
_PERCENT_CONCEPTS: frozenset[str] = frozenset({"net_margin", "gross_margin", "operating_margin"})

# Display valence per concept, shipped on each series as `tone` — the same dataset-as-source-of-
# truth pattern as `percent`, so the frontend never re-derives which concepts read inverted or
# neutral. "inverted": an increase is a cost/risk signal (the same judgment detect_debt_build
# encodes); "neutral": the direction is a strategic choice (a capex ramp, an investing/financing
# swing), not inherently good or bad. Everything else defaults to "normal" (up = good).
_SERIES_TONE: dict[str, str] = {
    "long_term_debt": "inverted",
    "current_liabilities": "inverted",
    "capital_expenditures": "neutral",
    "investing_cash_flow": "neutral",
    "financing_cash_flow": "neutral",
}

# Display order for the dataset grid (missing concepts are simply omitted).
DATASET_CONCEPT_ORDER: tuple[str, ...] = (
    "revenue",
    "net_interest_income", "noninterest_income", "premiums_earned", "net_investment_income",
    "gross_profit", "gross_margin",
    "operating_income", "operating_margin",
    "net_income", "net_margin",
    "earnings_per_share", "eps_diluted",
    "operating_cash_flow", "capital_expenditures", "free_cash_flow",
    "investing_cash_flow", "financing_cash_flow",
    "total_assets", "cash_and_equivalents",
    "current_assets", "current_liabilities", "working_capital", "current_ratio",
    "long_term_debt", "shareholders_equity",
)

_CONCEPT_LABELS: dict[str, str] = {
    "revenue": "Revenue",
    "net_interest_income": "Net interest income",
    "noninterest_income": "Noninterest income",
    "premiums_earned": "Premiums earned",
    "net_investment_income": "Net investment income",
    "gross_profit": "Gross profit",
    "gross_margin": "Gross margin",
    "operating_income": "Operating income",
    "operating_margin": "Operating margin",
    "net_income": "Net income",
    "net_margin": "Net margin",
    "earnings_per_share": "EPS (basic)",
    "eps_diluted": "EPS (diluted)",
    "operating_cash_flow": "Operating cash flow",
    "capital_expenditures": "Capital expenditures",
    "free_cash_flow": "Free cash flow",
    "investing_cash_flow": "Investing cash flow",
    "financing_cash_flow": "Financing cash flow",
    "total_assets": "Total assets",
    "cash_and_equivalents": "Cash & equivalents",
    "current_assets": "Current assets",
    "current_liabilities": "Current liabilities",
    "working_capital": "Working capital",
    "current_ratio": "Current ratio",
    "long_term_debt": "Long-term debt",
    "shareholders_equity": "Shareholders' equity",
}


def concept_label(concept: str) -> str:
    return _CONCEPT_LABELS.get(concept, concept.replace("_", " ").title())


# --- period keys -------------------------------------------------------------------------------

_ANNUAL_KEY_RE = re.compile(r"^FY(\d{4})$")
_QUARTER_KEY_RE = re.compile(r"^(\d{4})(Q[1-4])$")


def parse_period_key(mode: str, key: str) -> tuple[int, Optional[str]]:
    """"FY2024" -> (2024, None); "2024Q2" -> (2024, "Q2"). Raises ValueError on a bad key."""
    if mode == "annual":
        match = _ANNUAL_KEY_RE.match(key or "")
        if not match:
            raise ValueError(f"Invalid annual period key: {key!r} (expected e.g. 'FY2024')")
        return int(match.group(1)), None
    match = _QUARTER_KEY_RE.match(key or "")
    if not match:
        raise ValueError(f"Invalid quarterly period key: {key!r} (expected e.g. '2024Q2')")
    return int(match.group(1)), match.group(2)


def _period_sort_key(bucket: dict[str, Any]) -> tuple:
    return (bucket["period_end"], bucket["fiscal_period"] or "")


# --- coverage ----------------------------------------------------------------------------------

_CORE_REVENUE_CONCEPTS = ("revenue", "net_interest_income")  # generic top line OR the FI one


def available_periods(db: Session, company_id: int) -> dict[str, Any]:
    """Selectable periods per mode, oldest → newest (one indexed read on the series index)."""
    rows = (
        db.query(
            FinancialFact.concept,
            FinancialFact.fiscal_year,
            FinancialFact.fiscal_period,
            FinancialFact.period_end,
            FinancialFact.source,
        )
        .filter(
            FinancialFact.company_id == company_id,
            FinancialFact.is_latest.is_(True),
            FinancialFact.fiscal_period.isnot(None),
        )
        .all()
    )

    annual: dict[int, dict[str, Any]] = {}
    quarterly: dict[tuple[int, str], dict[str, Any]] = {}
    for concept, fiscal_year, fiscal_period, period_end, source in rows:
        if fiscal_year is None or period_end is None:
            continue
        if fiscal_period == "FY":
            entry = annual.setdefault(
                fiscal_year,
                {"fiscal_year": fiscal_year, "period_end": period_end, "concepts": set()},
            )
            entry["period_end"] = max(entry["period_end"], period_end)
            entry["concepts"].add(concept)
        elif fiscal_period in _QUARTERS:
            entry = quarterly.setdefault(
                (fiscal_year, fiscal_period),
                {
                    "fiscal_year": fiscal_year,
                    "fiscal_period": fiscal_period,
                    "period_end": period_end,
                    "derived": True,
                },
            )
            entry["period_end"] = max(entry["period_end"], period_end)
            # A quarter column is "derived" only if EVERY row in it came from the Q4 derivation.
            if source != "derived":
                entry["derived"] = False

    annual_out = [
        {
            "key": f"FY{entry['fiscal_year']}",
            "fiscal_year": entry["fiscal_year"],
            "period_end": entry["period_end"].isoformat(),
            "has_core": (
                any(c in entry["concepts"] for c in _CORE_REVENUE_CONCEPTS)
                and "net_income" in entry["concepts"]
            ),
        }
        for entry in sorted(annual.values(), key=lambda e: e["period_end"])
    ]
    quarterly_out = [
        {
            "key": f"{entry['fiscal_year']}{entry['fiscal_period']}",
            "fiscal_year": entry["fiscal_year"],
            "fiscal_period": entry["fiscal_period"],
            "period_end": entry["period_end"].isoformat(),
            "derived": entry["derived"],
        }
        for entry in sorted(quarterly.values(), key=lambda e: e["period_end"])
    ]
    return {"annual": annual_out, "quarterly": quarterly_out}


# --- dataset assembly --------------------------------------------------------------------------


# Sentinel for `_growth`: a comparison was attempted but crossing zero makes a percentage
# meaningless (finance convention "n/m" — not meaningful), e.g. investing cash flow swinging from
# +$503M to -$71.9B renders "-14,399.2%" under plain division. Distinct from None (no prior at
# all), so the UI/prompt can say "n/m" instead of rendering nothing.
NOT_MEANINGFUL = "nm"


def _growth(current: Optional[float], prior: Optional[float]) -> Optional[float] | str:
    """Fractional growth with the compute_metric edge discipline: no prior / zero prior → None.
    Opposite-signed current/prior → NOT_MEANINGFUL (a swing through zero, not a real up/down
    move — same-sign moves of any magnitude, even a large one off a small base, stay real growth)."""
    if current is None or prior is None or prior == 0:
        return None
    if current != 0 and (current > 0) != (prior > 0):
        return NOT_MEANINGFUL
    return (current - prior) / abs(prior)


def _pp_delta(current: Optional[float], prior: Optional[float]) -> Optional[float]:
    """Percentage-POINT delta for percent-unit series (margins, stored ×100): current − prior.
    Never divides, so it never "explodes" the way relative growth can — a 47.3% → 38.3% move is
    simply -9.0pp, always sane — and needs no NOT_MEANINGFUL guard."""
    if current is None or prior is None:
        return None
    return current - prior


def _cagr(first: float, last: float, years: int) -> Optional[float]:
    """Compound annual growth rate; only defined for positive endpoints over ≥1 year."""
    if years < 1 or first <= 0 or last <= 0:
        return None
    return (last / first) ** (1.0 / years) - 1.0


def _valued_endpoints(
    periods: list[dict[str, Any]], points: list[dict[str, Any]]
) -> Optional[tuple[tuple[int, float], tuple[int, float]]]:
    """First/last ``(fiscal_year, value)`` over a series' non-null points — the ONE endpoint-
    selection rule for every annual window figure (CAGR and window_pp), so the two can't drift.
    Returns ``None`` when fewer than two valued points exist (no window to measure)."""
    valued = [
        (bucket["fiscal_year"], point["value"])
        for bucket, point in zip(periods, points)
        if point["value"] is not None
    ]
    if len(valued) < 2:
        return None
    return valued[0], valued[-1]


def build_dataset(
    db: Session,
    company: Company,
    mode: str,
    start_period: str,
    end_period: str,
) -> dict[str, Any]:
    """Assemble the aligned N-period dataset for one company (pure DB read + arithmetic).

    Raises ``ValueError`` for a bad mode/range (the router maps it to 400). Every value point gets
    a stable ``F#`` marker (series order × period order over non-null values) — the only citation
    currency the AI narrative is allowed to spend.
    """
    if mode not in MODES:
        raise ValueError(f"Invalid mode: {mode!r} (expected 'annual' or 'quarterly')")
    start_fy, start_fp = parse_period_key(mode, start_period)
    end_fy, end_fp = parse_period_key(mode, end_period)

    rows = (
        db.query(FinancialFact)
        .filter(
            FinancialFact.company_id == company.id,
            FinancialFact.is_latest.is_(True),
            FinancialFact.fiscal_period.isnot(None),
        )
        .order_by(FinancialFact.period_end.asc())
        .all()
    )

    # Indexes: flows by (fiscal_year, fiscal_period); instants ALSO by period_end (D2c).
    by_fy_fp: dict[tuple[int, str, str], FinancialFact] = {}
    instant_by_end: dict[tuple[str, date], FinancialFact] = {}
    for row in rows:
        if row.fiscal_year is None:
            continue
        by_fy_fp[(row.fiscal_year, row.fiscal_period, row.concept)] = row
        if row.concept in INSTANT_CONCEPTS:
            instant_by_end[(row.concept, row.period_end)] = row

    # Period axis (oldest → newest), range-filtered and capped.
    if mode == "annual":
        buckets = [
            {"key": f"FY{fy}", "fiscal_year": fy, "fiscal_period": "FY", "period_end": end}
            for fy, end in sorted(
                {
                    (row.fiscal_year, row.period_end)
                    for row in rows
                    if row.fiscal_period == "FY" and row.fiscal_year is not None
                    and start_fy <= row.fiscal_year <= end_fy
                },
                key=lambda pair: pair[1],
            )
        ]
        # A fiscal year may appear with several period_ends across concepts; keep the latest.
        deduped: dict[int, dict[str, Any]] = {}
        for bucket in buckets:
            existing = deduped.get(bucket["fiscal_year"])
            if existing is None or bucket["period_end"] > existing["period_end"]:
                deduped[bucket["fiscal_year"]] = bucket
        periods = sorted(deduped.values(), key=lambda b: b["period_end"])
        cap = settings.ANALYSIS_MAX_ANNUAL_PERIODS
    else:
        seen: dict[tuple[int, str], dict[str, Any]] = {}
        for row in rows:
            if row.fiscal_period not in _QUARTERS or row.fiscal_year is None:
                continue
            bucket = seen.setdefault(
                (row.fiscal_year, row.fiscal_period),
                {
                    "key": f"{row.fiscal_year}{row.fiscal_period}",
                    "fiscal_year": row.fiscal_year,
                    "fiscal_period": row.fiscal_period,
                    "period_end": row.period_end,
                },
            )
            bucket["period_end"] = max(bucket["period_end"], row.period_end)
        ordered = sorted(seen.values(), key=_period_sort_key)
        start_key = (start_fy, start_fp)
        end_key = (end_fy, end_fp)
        started = False
        periods = []
        for bucket in ordered:
            if (bucket["fiscal_year"], bucket["fiscal_period"]) == start_key:
                started = True
            if started:
                periods.append(bucket)
            if (bucket["fiscal_year"], bucket["fiscal_period"]) == end_key and started:
                break
        cap = settings.ANALYSIS_MAX_QUARTERLY_PERIODS

    if not periods:
        raise ValueError("No data available for the selected period range.")
    if len(periods) > cap:
        raise ValueError(f"Too many periods selected: {len(periods)} (max {cap} for {mode} mode).")

    def _row_for(concept: str, bucket: dict[str, Any]) -> Optional[FinancialFact]:
        if mode == "quarterly" and concept in INSTANT_CONCEPTS:
            return instant_by_end.get((concept, bucket["period_end"]))
        return by_fy_fp.get((bucket["fiscal_year"], bucket["fiscal_period"], concept))

    series_list: list[dict[str, Any]] = []
    for concept in DATASET_CONCEPT_ORDER:
        points: list[dict[str, Any]] = []
        any_value = False
        for bucket in periods:
            row = _row_for(concept, bucket)
            if row is None:
                points.append({"period": bucket["key"], "value": None})
                continue
            any_value = True
            points.append(
                {
                    "period": bucket["key"],
                    "value": float(row.value),
                    "unit": row.unit,
                    "period_end": row.period_end.isoformat(),
                    "form": row.form,
                    "accession": row.accession,
                    "raw_tag": row.raw_tag,
                    # True computed-Q4 only. `source == "derived"` alone is NOT it: the ingest
                    # also stamps same-period computed metrics (margins, FCF, working capital,
                    # current ratio) "derived" for EVERY period — an FY2016 margin must never be
                    # labelled a "derived Q4". The discriminator is `reconciled`: every row in
                    # the Q4 DERIVATION CHAIN (FY−YTD9/ΣQ flows, shares-based EPS, and metrics
                    # computed from those estimates) is reconciled=False, while a computed
                    # metric on REAL same-period values is reconciled=True. Point-level (not
                    # column-level) so a filer with SOME discrete Q4 rows still badges the rows
                    # that genuinely rest on estimates (e.g. a derived Q4 EPS next to a real
                    # discrete Q4 net income) instead of presenting them as reported values.
                    "derived": (
                        row.fiscal_period == "Q4"
                        and row.source == "derived"
                        and not row.reconciled
                    ),
                    "reconciled": bool(row.reconciled),
                    "fiscal_year": row.fiscal_year,
                    "fiscal_period": row.fiscal_period,
                }
            )
        if not any_value:
            continue

        unit = next((p["unit"] for p in points if p.get("unit")), "USD")
        is_percent = concept in _PERCENT_CONCEPTS
        # Percent-unit series (margins) report YoY/QoQ as percentage-POINT deltas — the
        # convention finance readers expect for a ratio already expressed as a percentage — never
        # the relative change of the percentage value itself. Everything else keeps relative
        # growth (with the n/m sign-flip guard baked into `_growth`).
        delta_fn = _pp_delta if is_percent else _growth

        # YoY: prior fiscal year (annual) / same quarter one fiscal year earlier (quarterly).
        by_period_key = {p["period"]: p for p in points}
        for bucket, point in zip(periods, points):
            if point["value"] is None:
                continue
            if mode == "annual":
                prior_key = f"FY{bucket['fiscal_year'] - 1}"
            else:
                prior_key = f"{bucket['fiscal_year'] - 1}{bucket['fiscal_period']}"
            prior = by_period_key.get(prior_key)
            point["yoy"] = delta_fn(point["value"], prior["value"] if prior else None)
            point["yoy_reconciled"] = (
                point.get("reconciled") is not False and prior.get("reconciled") is not False
                if point["yoy"] is not None and prior else None
            )
        # QoQ: the immediately preceding column (quarterly only).
        if mode == "quarterly":
            previous: Optional[dict[str, Any]] = None
            for point in points:
                if point["value"] is not None:
                    point["qoq"] = delta_fn(
                        point["value"], previous["value"] if previous else None
                    )
                    point["qoq_reconciled"] = (
                        point.get("reconciled") is not False and previous.get("reconciled") is not False
                        if point["qoq"] is not None and previous else None
                    )
                    previous = point

        # CAGR over the series' VALUED endpoints (annual mode, monetary/per-share series only).
        # The basis window is recorded because it can be narrower than the selected range (a
        # concept first reported mid-window) — citations must state the window the figure was
        # actually computed over, not the range the user picked.
        cagr = None
        cagr_window = None
        if mode == "annual" and unit != "pure":
            endpoints = _valued_endpoints(periods, points)
            if endpoints:
                (first_fy, first), (last_fy, last) = endpoints
                cagr = _cagr(first, last, last_fy - first_fy)
                if cagr is not None:
                    cagr_window = f"FY{first_fy}..FY{last_fy}"

        # Window pp change over the same valued endpoints — the percent-series counterpart to
        # CAGR (compounding doesn't apply to a percentage), so the annual KPI strip/table has a
        # window figure for margin concepts even though CAGR itself is always null for them
        # (unit == "pure" excludes them from the CAGR block above).
        window_pp = None
        window_pp_range = None
        if mode == "annual" and is_percent:
            endpoints = _valued_endpoints(periods, points)
            if endpoints:
                (first_fy, first_v), (last_fy, last_v) = endpoints
                window_pp = last_v - first_v
                window_pp_range = f"FY{first_fy}..FY{last_fy}"

        valued_points = [p for p in points if p["value"] is not None]
        endpoints_reconciled = bool(valued_points) and all(
            p.get("reconciled") is not False for p in (valued_points[0], valued_points[-1])
        )
        series_list.append(
            {
                "concept": concept,
                "label": concept_label(concept),
                "unit": unit,
                "percent": is_percent,
                "tone": _SERIES_TONE.get(concept, "normal"),
                "cagr": cagr,
                "cagr_window": cagr_window,
                "cagr_reconciled": endpoints_reconciled if cagr is not None else None,
                "window_pp": window_pp,
                "window_pp_range": window_pp_range,
                "window_pp_reconciled": endpoints_reconciled if window_pp is not None else None,
                "points": points,
            }
        )

    # Stable citation markers over non-null values, in display order.
    marker = 0
    for series in series_list:
        for point in series["points"]:
            if point["value"] is not None:
                marker += 1
                point["marker"] = f"F{marker}"
    # Series-level CAGR gets its own marker (after every point marker, so point numbering is
    # unchanged): it is a server-computed figure the narrative is told to anchor on, and a figure
    # without a marker forces the model to improvise illegal range citations like [F1..F10].
    for series in series_list:
        if series.get("cagr") is not None:
            marker += 1
            series["cagr_marker"] = f"F{marker}"

    dataset: dict[str, Any] = {
        "ticker": company.ticker,
        "company_name": company.name,
        "mode": mode,
        "period_key": f"{periods[0]['key']}..{periods[-1]['key']}",
        "periods": [
            {
                "key": bucket["key"],
                "fiscal_year": bucket["fiscal_year"],
                "fiscal_period": bucket["fiscal_period"],
                "period_end": bucket["period_end"].isoformat(),
            }
            for bucket in periods
        ],
        "series": series_list,
    }
    dataset["inflections"] = detect_inflections(dataset)
    return dataset


# --- deterministic inflection signals ----------------------------------------------------------


def _series_map(dataset: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {series["concept"]: series for series in dataset["series"]}


def _valued_points(series: Optional[dict[str, Any]]) -> list[dict[str, Any]]:
    if not series:
        return []
    return [p for p in series["points"] if p["value"] is not None]


def detect_growth_deceleration(dataset: dict[str, Any]) -> list[dict[str, Any]]:
    """Top-line YoY growth strictly declining across the three most recent measurable periods."""
    flags = []
    series_by = _series_map(dataset)
    for concept in ("revenue", "net_interest_income"):
        # Exclude NOT_MEANINGFUL ("nm") explicitly — it's a string sentinel, not a float, and
        # `yoys[0] > yoys[1]` below would raise TypeError if one slipped through.
        points = [
            p for p in _valued_points(series_by.get(concept)) if isinstance(p.get("yoy"), float)
        ]
        if len(points) < 3:
            continue
        last3 = points[-3:]
        yoys = [p["yoy"] for p in last3]
        if yoys[0] > yoys[1] > yoys[2]:
            displays, display_is_distinct = _ordered_percentage_values(yoys)
            sequence = (" → " if display_is_distinct else ", ").join(displays)
            display_qualifier = (
                ""
                if display_is_distinct
                else " (effectively equal where values match at four-decimal precision)"
            )
            markers = [
                marker
                for point in last3
                for marker in _growth_operand_markers(dataset, series_by[concept], point)
            ]
            flags.append(
                {
                    "kind": "growth_deceleration",
                    "concepts": [concept],
                    "periods": [p["period"] for p in last3],
                    "detail": (
                        f"{concept_label(concept)} YoY growth decelerated across its three most "
                        f"recent measurable observations: {sequence}{display_qualifier}."
                    ),
                    "markers": list(dict.fromkeys(markers)),
                }
            )
        # Only flag the primary top line the company actually has.
        if points:
            break
    return flags


def detect_margin_compression(dataset: dict[str, Any]) -> list[dict[str, Any]]:
    """A margin strictly declining over the three most recent periods by ≥2 percentage points."""
    flags = []
    series_by = _series_map(dataset)
    for concept in ("operating_margin", "net_margin"):
        points = _valued_points(series_by.get(concept))
        if len(points) < 3:
            continue
        last3 = points[-3:]
        values = [p["value"] for p in last3]  # stored ×100 (percent)
        if values[0] > values[1] > values[2] and (values[0] - values[2]) >= 2.0:
            displays, display_is_distinct = _ordered_percentage_values(
                values, already_percent=True, signed=False
            )
            sequence = (" → " if display_is_distinct else ", ").join(displays)
            display_qualifier = (
                ""
                if display_is_distinct
                else " (effectively equal where values match at four-decimal precision)"
            )
            flags.append(
                {
                    "kind": "margin_compression",
                    "concepts": [concept],
                    "periods": [p["period"] for p in last3],
                    "detail": (
                        f"{concept_label(concept)} compressed {values[0] - values[2]:.1f}pp over "
                        f"three periods: {sequence}{display_qualifier}."
                    ),
                    "markers": [p["marker"] for p in last3],
                }
            )
    return flags


def detect_fcf_ni_divergence(dataset: dict[str, Any]) -> list[dict[str, Any]]:
    """Free cash flow conversion collapsing vs its own history (earnings-quality signal)."""
    series_by = _series_map(dataset)
    fcf_by_period = {p["period"]: p for p in _valued_points(series_by.get("free_cash_flow"))}
    ratios: list[tuple[dict[str, Any], dict[str, Any], float]] = []
    for ni_point in _valued_points(series_by.get("net_income")):
        fcf_point = fcf_by_period.get(ni_point["period"])
        if fcf_point is not None and ni_point["value"] > 0:
            ratios.append((fcf_point, ni_point, fcf_point["value"] / ni_point["value"]))
    if len(ratios) < 3:
        return []
    *prior, (last_fcf, last_ni, last_ratio) = ratios
    prior_avg = sum(r for _, _, r in prior) / len(prior)
    if last_ratio < 0.6 and prior_avg >= 0.9:
        # The historical-average claim depends on every prior FCF/NI pair, so its observation
        # must carry those operands as well as the latest pair.  A marker for only the latest
        # period would make the displayed average look source-bound when its constituents were
        # invisible.
        operand_markers = [
            marker
            for fcf_point, ni_point, _ in ratios
            for marker in (fcf_point["marker"], ni_point["marker"])
        ]
        return [
            {
                "kind": "fcf_ni_divergence",
                "concepts": ["free_cash_flow", "net_income"],
                "periods": [last_fcf["period"]],
                "detail": (
                    f"Free-cash-flow conversion fell to {last_ratio:.2f}× net income in "
                    f"{last_fcf['period']} vs a {prior_avg:.2f}× historical average — earnings and "
                    f"cash are diverging."
                ),
                "markers": list(dict.fromkeys(operand_markers)),
            }
        ]
    return []


def detect_debt_build(dataset: dict[str, Any]) -> list[dict[str, Any]]:
    """Long-term debt grew ≥50% across the selected window."""
    points = _valued_points(_series_map(dataset).get("long_term_debt"))
    if len(points) < 2:
        return []
    first, last = points[0], points[-1]
    if first["value"] > 0 and last["value"] >= 1.5 * first["value"]:
        growth = (last["value"] - first["value"]) / first["value"]
        return [
            {
                "kind": "debt_build",
                "concepts": ["long_term_debt"],
                "periods": [first["period"], last["period"]],
                "detail": (
                    f"Long-term debt grew {_pct_str(growth)} from {first['period']} to "
                    f"{last['period']}."
                ),
                "markers": [first["marker"], last["marker"]],
            }
        ]
    return []


def detect_liquidity_squeeze(dataset: dict[str, Any]) -> list[dict[str, Any]]:
    """Current ratio below 1.0, or down ≥0.5 across the window to below 1.5."""
    points = _valued_points(_series_map(dataset).get("current_ratio"))
    if not points:
        return []
    first, last = points[0], points[-1]
    if last["value"] < 1.0:
        detail = (
            f"Current ratio is below 1.0 "
            f"({_ratio_threshold_value(last['value'])} in {last['period']})."
        )
    elif len(points) >= 2 and (first["value"] - last["value"]) >= 0.5 and last["value"] < 1.5:
        detail = (
            f"Current ratio declined from {first['value']:.2f}× ({first['period']}) to "
            f"{last['value']:.2f}× ({last['period']})."
        )
    else:
        return []
    return [
        {
            "kind": "liquidity_squeeze",
            "concepts": ["current_ratio"],
            "periods": [first["period"], last["period"]],
            "detail": detail,
            "markers": sorted({first["marker"], last["marker"]}),
        }
    ]


_DETECTORS = (
    detect_growth_deceleration,
    detect_margin_compression,
    detect_fcf_ni_divergence,
    detect_debt_build,
    detect_liquidity_squeeze,
)


def detect_inflections(dataset: dict[str, Any]) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []
    for detector in _DETECTORS:
        try:
            flags.extend(detector(dataset))
        except Exception:  # noqa: BLE001 - a detector bug must never break dataset assembly
            logger.exception("inflection detector %s failed", detector.__name__)
    return flags


# --- fingerprint + prompt rendering ------------------------------------------------------------


def dataset_fingerprint(dataset: dict[str, Any]) -> str:
    """sha256 of the canonical dataset JSON — new facts (or a changed range) change it, which
    invalidates the cached narrative for that key (D4)."""
    canonical = json.dumps(dataset, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _format_value(value: float, unit: str, percent: bool) -> str:
    if percent:
        return f"{value:.1f}%"
    if unit == "pure":
        return f"{value:.2f}x"
    if unit.endswith("/shares"):
        return f"{value:,.2f}"
    return f"{value:,.0f}"


def compact_dataset_for_prompt(dataset: dict[str, Any]) -> str:
    """Line-based rendering of the dataset for the model: every value prefixed with its [F#]
    marker, growth pre-computed, signals appended. ~5-8k tokens for 26 series × 12 periods."""
    lines: list[str] = [
        f"Company: {dataset['company_name']} ({dataset['ticker']})",
        f"Mode: {dataset['mode']} | Periods: {dataset['period_key']}",
        "",
    ]
    for series in dataset["series"]:
        unit_note = "%" if series["percent"] else series["unit"]
        header = f"## {series['label']} ({unit_note})"
        if series.get("cagr") is not None:
            cagr_marker = f"[{series['cagr_marker']}] " if series.get("cagr_marker") else ""
            window = f" ({series['cagr_window']})" if series.get("cagr_window") else ""
            header += f" — {cagr_marker}CAGR {_pct_str(series['cagr'])}{window}"
        lines.append(header)
        for point in series["points"]:
            if point["value"] is None:
                lines.append(f"  {point['period']}: not reported")
                continue
            rendered = _format_value(point["value"], series["unit"], series["percent"])
            growth_bits = []
            if point.get("yoy") is not None:
                growth_bits.append(f"YoY {_fmt_growth(point['yoy'], series['percent'])}")
            if point.get("qoq") is not None:
                growth_bits.append(f"QoQ {_fmt_growth(point['qoq'], series['percent'])}")
            suffix = f" ({', '.join(growth_bits)})" if growth_bits else ""
            derived = " [derived]" if point.get("derived") else ""
            lines.append(f"  [{point['marker']}] {point['period']}: {rendered}{suffix}{derived}")
        lines.append("")

    if dataset.get("inflections"):
        lines.append("## Signals detected (deterministic, pre-computed)")
        for flag in dataset["inflections"]:
            # One marker per bracket pair. The old comma-joined form ("[F58, F59, F60]") taught
            # the model the exact multi-reference notation the resolver cannot parse — the prompt
            # must only ever model the legal form.
            markers = " ".join(f"[{m}]" for m in (flag.get("markers") or []))
            lines.append(f"- {flag['kind']}: {flag['detail']}" + (f" {markers}" if markers else ""))
        lines.append("")
    return "\n".join(lines)


def _pct_str(value: float) -> str:
    return f"{value * 100:+.1f}%"


def _fmt_growth(value: float | str, is_percent: bool) -> str:
    """Render a YoY/QoQ delta for the prompt: NOT_MEANINGFUL as "n/m"; a percent-unit series'
    delta (already a percentage-POINT number, no ×100) as "+X.Xpp"; everything else as the usual
    signed relative percentage."""
    if value == NOT_MEANINGFUL:
        return "n/m"
    if is_percent:
        return f"{value:+.1f}pp"
    return _pct_str(value)


# --- code-owned narrative observations ---------------------------------------------------------

ANALYSIS_SECTIONS: tuple[tuple[str, str], ...] = (
    ("trajectory", "The trajectory"),
    ("growth_quality", "Growth quality"),
    ("margins", "Margins"),
    ("cash_balance_sheet", "Cash & balance sheet"),
    ("red_flags", "Red flags"),
    ("watch_next", "What to watch next"),
)
_SECTION_KEYS = frozenset(key for key, _ in ANALYSIS_SECTIONS)
_OPTIONAL_PER_SECTION = 3
_SELECTION_TOTAL_LIMIT = len(ANALYSIS_SECTIONS) * _OPTIONAL_PER_SECTION


@dataclass(frozen=True)
class TrendObservation:
    """One immutable, request-local sentence the model may select only by ID."""

    id: str
    section: str
    markdown: str
    required: bool = False


def _observation_id(section: str, kind: str, *parts: str) -> str:
    clean = [re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") for value in parts]
    return ".".join((section, kind, *filter(None, clean)))


def _ratio_threshold_value(value: float) -> str:
    """Expose enough ratio precision to preserve its exact relation to 1.00x."""
    decimals = 4
    while value != 1.0 and decimals < 16 and f"{value:.{decimals}f}" == f"{1.0:.{decimals}f}":
        decimals += 1
    return f"{value:.{decimals}f}x"


def _point_value(series: dict[str, Any], point: dict[str, Any], *, ratio_precision: bool = False) -> str:
    value = point["value"]
    if ratio_precision:
        # The ordinary two-decimal grid display remains untouched.  The same helper also renders
        # the current-ratio Sources excerpt so the cited evidence and threshold cue agree.
        return _ratio_threshold_value(value)
    rendered = _format_value(value, series["unit"], series["percent"])
    if series["percent"] or series["unit"] == "pure":
        return rendered
    if series["unit"].endswith("/shares"):
        currency = series["unit"].removesuffix("/shares")
        return f"{currency} {rendered} per share"
    return f"{series['unit']} {rendered}"


def _same_dimension(first: dict[str, Any], second: dict[str, Any]) -> bool:
    return first.get("unit") == second.get("unit") and bool(first.get("percent")) == bool(
        second.get("percent")
    )


def _ordered_percentage_values(
    values: list[float], *, already_percent: bool = False, signed: bool = True
) -> tuple[list[str], bool]:
    """Render an ordered percentage sequence without hiding strict changes through rounding."""
    scale = Decimal(1) if already_percent else Decimal(100)
    scaled = [Decimal(str(value)) * scale for value in values]
    sign = "+" if signed else ""
    for decimals in range(1, 5):
        rendered = [f"{value:{sign}.{decimals}f}%" for value in scaled]
        if all(first != second for first, second in zip(rendered, rendered[1:])):
            return rendered, True
    rendered = [f"{value:{sign}.4f}%" for value in scaled]
    return rendered, False


def _growth_comparison_values(first: float, second: float) -> tuple[str, str, str]:
    """Return the raw-value ordering with displays that make a non-equal ordering visible."""
    if first == second:
        rendered = _pct_str(first)
        return "equal to", rendered, rendered
    relation = "above" if first > second else "below"
    (first_text, second_text), display_is_distinct = _ordered_percentage_values([first, second])
    if display_is_distinct:
        return relation, first_text, second_text
    # Beyond four percentage decimals the values are immaterially different for this product
    # surface. Avoid asserting a direction that the intentionally bounded display cannot show.
    return "effectively equal to", _pct_str(first), _pct_str(second)


def _growth_operand_points(
    dataset: dict[str, Any], series: dict[str, Any], point: dict[str, Any]
) -> list[dict[str, Any]]:
    """Current/prior points that own a displayed YoY/pp change, in that order."""
    period = point["period"]
    try:
        mode = dataset.get("mode") or ("annual" if period.startswith("FY") else "quarterly")
        year, quarter = parse_period_key(mode, period)
    except ValueError:
        return [point]
    prior_period = f"FY{year - 1}" if quarter is None else f"{year - 1}{quarter}"
    prior = next((candidate for candidate in series["points"] if candidate["period"] == prior_period), None)
    points = [point]
    if prior and prior.get("marker"):
        points.append(prior)
    return points


def _growth_operand_markers(
    dataset: dict[str, Any], series: dict[str, Any], point: dict[str, Any]
) -> list[str]:
    return [operand["marker"] for operand in _growth_operand_points(dataset, series, point)]


def _marker_chain(markers: list[str]) -> str:
    return " ".join(f"[{marker}]" for marker in dict.fromkeys(markers))


def _derived_qualifier(*points: dict[str, Any]) -> str:
    """Label an observation whose stated value or comparison uses a computed Q4 point."""
    return " (derived Q4)" if any(point.get("derived") for point in points) else ""


def build_observation_catalogue(dataset: dict[str, Any]) -> list[TrendObservation]:
    """Build a bounded catalogue of code-rendered claims from the trusted dataset shape.

    The model never supplies text, numbers, periods, markers or a replacement catalogue.  Every
    comparison here binds same-period operands with compatible dimensions.  Missingness is only
    emitted for a null point in the selected latest period.
    """
    by = _series_map(dataset)
    observations: list[TrendObservation] = []
    seen: set[str] = set()

    def add(
        section: str,
        kind: str,
        markdown: str,
        *parts: str,
        required: bool = False,
    ) -> None:
        obs_id = _observation_id(section, kind, *parts)
        if obs_id in seen:
            return
        seen.add(obs_id)
        observations.append(TrendObservation(obs_id, section, markdown, required))

    top = next((by.get(name) for name in ("revenue", "net_interest_income") if by.get(name)), None)
    top_points = _valued_points(top)
    if top and top_points:
        first, latest = top_points[0], top_points[-1]
        add(
            "trajectory", "latest", (
                f"{top['label']} was {_point_value(top, latest)} in {latest['period']} "
                f"[{latest['marker']}]{_derived_qualifier(latest)}."
            ), top["concept"], latest["period"], required=True,
        )
        if first is not latest:
            add(
                "trajectory", "first", (
                    f"The earliest available {top['label'].lower()} observation was "
                    f"{_point_value(top, first)} in {first['period']} [{first['marker']}]"
                    f"{_derived_qualifier(first)}."
                ), top["concept"], first["period"],
            )
        if top.get("cagr") is not None and top.get("cagr_marker"):
            add(
                "trajectory", "cagr", (
                    f"{top['label']} CAGR was {_pct_str(top['cagr'])} over "
                    f"{top.get('cagr_window') or dataset['period_key']} [{top['cagr_marker']}]"
                    f"{_derived_qualifier(first, latest)}."
                ), top["concept"], top.get("cagr_window") or dataset["period_key"], required=True,
            )

        growth_points = [p for p in top_points if isinstance(p.get("yoy"), float)][-3:]
        for point in growth_points:
            add(
                "growth_quality", "growth", (
                    f"{top['label']} growth in {point['period']} was "
                    f"{_fmt_growth(point['yoy'], top['percent'])} "
                    f"{_marker_chain(_growth_operand_markers(dataset, top, point))}"
                    f"{_derived_qualifier(*_growth_operand_points(dataset, top, point))}."
                ), top["concept"], point["period"], required=point is growth_points[-1],
            )

    net_income = by.get("net_income")
    ni_points = _valued_points(net_income)
    if net_income and ni_points:
        latest_ni = ni_points[-1]
        add(
            "trajectory", "latest", (
                f"Net income was {_point_value(net_income, latest_ni)} in {latest_ni['period']} "
                f"[{latest_ni['marker']}]{_derived_qualifier(latest_ni)}."
            ), "net_income", latest_ni["period"], required=True,
        )
        ni_growth = [p for p in ni_points if isinstance(p.get("yoy"), float)][-3:]
        for point in ni_growth:
            add(
                "growth_quality", "growth", (
                    f"Net income growth in {point['period']} was "
                    f"{_fmt_growth(point['yoy'], net_income['percent'])} "
                    f"{_marker_chain(_growth_operand_markers(dataset, net_income, point))}"
                    f"{_derived_qualifier(*_growth_operand_points(dataset, net_income, point))}."
                ), "net_income", point["period"], required=point is ni_growth[-1],
            )

    growth_pairs = [
        ("net_income", comparison)
        for comparison in ("revenue", "net_interest_income", "noninterest_income")
    ] + [("operating_cash_flow", "net_income")]
    for first_concept, second_concept in growth_pairs:
        first_series, second_series = by.get(first_concept), by.get(second_concept)
        if not first_series or not second_series or not _same_dimension(first_series, second_series):
            continue
        second_by_period = {p["period"]: p for p in _valued_points(second_series)}
        first_growth = [
            p for p in _valued_points(first_series) if isinstance(p.get("yoy"), float)
        ][-3:]
        for first_point in first_growth:
            second_point = second_by_period.get(first_point["period"])
            if second_point is None or not isinstance(second_point.get("yoy"), float):
                continue
            relation, first_growth_text, second_growth_text = _growth_comparison_values(
                first_point["yoy"], second_point["yoy"]
            )
            comparison_operands = (
                _growth_operand_points(dataset, first_series, first_point)
                + _growth_operand_points(dataset, second_series, second_point)
            )
            add(
                "growth_quality", "comparison", (
                    f"In {first_point['period']}, {first_series['label'].lower()} growth of "
                    f"{first_growth_text} "
                    f"{_marker_chain(_growth_operand_markers(dataset, first_series, first_point))} "
                    f"was {relation} "
                    f"{second_series['label'].lower()} growth of "
                    f"{second_growth_text} "
                    f"{_marker_chain(_growth_operand_markers(dataset, second_series, second_point))}"
                    f"{_derived_qualifier(*comparison_operands)}."
                ), first_concept, second_concept, first_point["period"],
            )

    for concept in ("gross_margin", "operating_margin", "net_margin"):
        series = by.get(concept)
        points = _valued_points(series)
        if not series or not points:
            continue
        latest = points[-1]
        add(
            "margins", "latest", (
                f"{series['label']} was {_point_value(series, latest)} in {latest['period']} "
                f"[{latest['marker']}]{_derived_qualifier(latest)}."
            ), concept, latest["period"], required=not any(
                item.section == "margins" and item.required for item in observations
            ),
        )
        for point in [p for p in points if isinstance(p.get("yoy"), float)][-3:]:
            add(
                "margins", "change", (
                    f"{series['label']} changed {_fmt_growth(point['yoy'], True)} in "
                    f"{point['period']} "
                    f"{_marker_chain(_growth_operand_markers(dataset, series, point))}"
                    f"{_derived_qualifier(*_growth_operand_points(dataset, series, point))}."
                ), concept, point["period"],
            )

    # Same-period cash/earnings level comparisons.  No conversion rate or causal conclusion is
    # synthesized: the code states only the two supplied levels and their ordering.
    for cash_concept in ("free_cash_flow", "operating_cash_flow"):
        cash = by.get(cash_concept)
        if not cash or not net_income or not _same_dimension(cash, net_income):
            continue
        cash_by_period = {p["period"]: p for p in _valued_points(cash)}
        ni_by_period = {p["period"]: p for p in ni_points}
        shared = [period for period in cash_by_period if period in ni_by_period]
        if not shared:
            continue
        period = shared[-1]
        cash_point, ni_point = cash_by_period[period], ni_by_period[period]
        cash_value = _point_value(cash, cash_point)
        income_value = _point_value(net_income, ni_point)
        if cash_value == income_value:
            relation = (
                "equal to"
                if cash_point["value"] == ni_point["value"]
                else "effectively equal to"
            )
        else:
            relation = "above" if cash_point["value"] > ni_point["value"] else "below"
        add(
            "cash_balance_sheet", "level-comparison", (
                f"In {period}, {cash['label'].lower()} of {cash_value} "
                f"[{cash_point['marker']}] was {relation} net income of "
                f"{income_value} [{ni_point['marker']}]"
                f"{_derived_qualifier(cash_point, ni_point)}."
            ), cash_concept, "net-income", period, required=cash_concept == "free_cash_flow",
        )

    for concept in (
        "cash_and_equivalents", "working_capital", "long_term_debt", "shareholders_equity",
    ):
        series = by.get(concept)
        points = _valued_points(series)
        if series and points:
            point = points[-1]
            add(
                "cash_balance_sheet", "latest", (
                    f"{series['label']} was {_point_value(series, point)} in {point['period']} "
                    f"[{point['marker']}]{_derived_qualifier(point)}."
                ), concept, point["period"],
            )

    current_ratio = by.get("current_ratio")
    ratio_points = _valued_points(current_ratio)
    if current_ratio and ratio_points:
        point = ratio_points[-1]
        raw = point["value"]
        if raw > 1.0:
            relation = "above"
        elif raw < 1.0:
            relation = "below"
        else:
            relation = "equal to"
        add(
            "cash_balance_sheet", "ratio-threshold", (
                f"The current ratio was {_point_value(current_ratio, point, ratio_precision=True)} "
                f"in {point['period']} [{point['marker']}]{_derived_qualifier(point)}, "
                f"{relation} 1.00x."
            ), "current-ratio", point["period"], required=True,
        )

    eps = next((by.get(name) for name in ("earnings_per_share", "eps_diluted") if by.get(name)), None)
    eps_points = _valued_points(eps)
    if eps and eps_points:
        point = eps_points[-1]
        add(
            "growth_quality", "latest-eps", (
                f"{eps['label']} was {_point_value(eps, point)} in {point['period']} "
                f"[{point['marker']}]{_derived_qualifier(point)}."
            ), eps["concept"], point["period"], required=not any(
                item.section == "growth_quality" and item.required for item in observations
            ),
        )

    latest_period = dataset["periods"][-1]["key"] if dataset.get("periods") else None
    if latest_period:
        missing_sections = {
            "gross_margin": "margins", "operating_margin": "margins", "net_margin": "margins",
            "free_cash_flow": "cash_balance_sheet", "operating_cash_flow": "cash_balance_sheet",
            "earnings_per_share": "growth_quality", "eps_diluted": "growth_quality",
        }
        for concept, section in missing_sections.items():
            series = by.get(concept)
            point = next((p for p in (series or {}).get("points", []) if p["period"] == latest_period), None)
            if series and point is not None and point.get("value") is None:
                add(
                    section, "selected-gap", (
                        f"{series['label']} is not available in this selected dataset for "
                        f"{latest_period}."
                    ), concept, latest_period,
                )

    signals = dataset.get("inflections") or []
    if signals:
        point_index = marker_index(dataset)
        for position, signal in enumerate(signals, start=1):
            operand_bits = []
            for marker in signal.get("markers") or []:
                point = point_index.get(marker)
                if not point or point.get("kind") == "cagr":
                    continue
                ratio_precision = (
                    point.get("concept") == "current_ratio" and point.get("unit") == "pure"
                )
                operand_bits.append(
                    f"{point['label']} "
                    f"{_point_value(point, point, ratio_precision=ratio_precision)} "
                    f"in {point['period']} [{marker}]"
                    f"{_derived_qualifier(point)}"
                )
            detail = signal["detail"].strip()
            operands = "; ".join(operand_bits)
            add(
                "red_flags", "signal", detail + (f" Source operands: {operands}." if operands else ""),
                signal.get("kind", "signal"), str(position), required=True,
            )
    else:
        add(
            "red_flags", "no-signals", "No trend flags detected in the selected data.",
            "none", required=True,
        )

    if top and top_points:
        latest = top_points[-1]
        if isinstance(latest.get("yoy"), float):
            add(
                "watch_next", "growth", (
                    f"Watch whether {top['label'].lower()} growth in the next reporting update "
                    f"improves from {_fmt_growth(latest['yoy'], top['percent'])} in "
                    f"{latest['period']} "
                    f"{_marker_chain(_growth_operand_markers(dataset, top, latest))}"
                    f"{_derived_qualifier(*_growth_operand_points(dataset, top, latest))}."
                ), top["concept"], latest["period"], required=True,
            )
        else:
            add(
                "watch_next", "level", (
                    f"Watch how {top['label'].lower()} in the next reporting update compares with "
                    f"{_point_value(top, latest)} in {latest['period']} [{latest['marker']}]"
                    f"{_derived_qualifier(latest)}."
                ), top["concept"], latest["period"], required=True,
            )
    for series in (net_income, by.get("operating_margin"), by.get("free_cash_flow")):
        points = _valued_points(series)
        if not series or not points:
            continue
        point = points[-1]
        add(
            "watch_next", "metric", (
                f"Watch how {series['label'].lower()} in the next reporting update compares with "
                f"{_point_value(series, point)} in {point['period']} [{point['marker']}]"
                f"{_derived_qualifier(point)}."
            ), series["concept"], point["period"],
        )

    return observations


def compact_observation_catalogue(catalogue: list[TrendObservation]) -> str:
    lines = ["Allowed observations (select IDs only; text is immutable):"]
    lines.extend(f"- {item.id} | {item.section} | {item.markdown}" for item in catalogue)
    return "\n".join(lines)


def _strict_json(raw: str) -> Any:
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def reject_constant(_value: str) -> Any:
        raise ValueError("non-JSON number")

    try:
        return json.loads(raw.strip(), object_pairs_hook=unique_object, parse_constant=reject_constant)
    except (TypeError, ValueError):
        return None


def parse_observation_selection(
    raw: str, catalogue: list[TrendObservation]
) -> Optional[dict[str, list[str]]]:
    """Validate the complete model reply once, at the external boundary."""
    payload = _strict_json(raw)
    if not isinstance(payload, dict) or set(payload) != _SECTION_KEYS:
        return None
    by_id = {item.id: item for item in catalogue}
    total = 0
    selection: dict[str, list[str]] = {}
    for section, _ in ANALYSIS_SECTIONS:
        ids = payload.get(section)
        if not isinstance(ids, list) or len(ids) > _OPTIONAL_PER_SECTION:
            return None
        if any(not isinstance(item_id, str) for item_id in ids) or len(set(ids)) != len(ids):
            return None
        if any(item_id not in by_id or by_id[item_id].section != section for item_id in ids):
            return None
        total += len(ids)
        selection[section] = ids
    return selection if total <= _SELECTION_TOTAL_LIMIT else None


def render_observation_selection(
    catalogue: list[TrendObservation], selection: dict[str, list[str]]
) -> str:
    by_id = {item.id: item for item in catalogue}
    required = {
        section: [item for item in catalogue if item.section == section and item.required]
        for section, _ in ANALYSIS_SECTIONS
    }
    rendered: list[str] = []
    for section, title in ANALYSIS_SECTIONS:
        rendered.append(f"## {title}")
        section_items = [item for item in catalogue if item.section == section]
        chosen: list[TrendObservation] = list(required[section])
        chosen_ids = {item.id for item in chosen}
        chosen.extend(by_id[item_id] for item_id in selection[section] if item_id not in chosen_ids)
        if not chosen and section_items:
            # An empty valid selection cannot make available evidence look absent.  The catalogue
            # order is deterministic and starts with the section's most useful observation.
            chosen.append(section_items[0])
        if chosen:
            rendered.extend(item.markdown for item in chosen)
        else:
            rendered.append("Not enough data is available for this section in the selected periods.")
        rendered.append("")
    return "\n".join(rendered).rstrip()


def _has_minimum_analysis_data(dataset: dict[str, Any]) -> bool:
    by = _series_map(dataset)
    top = next((by.get(name) for name in ("revenue", "net_interest_income") if by.get(name)), None)
    top_periods = {point["period"] for point in _valued_points(top)}
    income_periods = {point["period"] for point in _valued_points(by.get("net_income"))}
    return len(top_periods & income_periods) >= 2


def marker_index(dataset: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """F# marker -> its dataset point (augmented with concept/label context) for citation
    resolution in the narrative pipeline. Series-level CAGR markers resolve too (kind="cagr")."""
    index: dict[str, dict[str, Any]] = {}
    for series in dataset["series"]:
        for point in series["points"]:
            marker = point.get("marker")
            if marker:
                index[marker] = {
                    **point,
                    "concept": series["concept"],
                    "label": series["label"],
                    "unit": series["unit"],
                    "percent": series["percent"],
                }
        if series.get("cagr_marker"):
            index[series["cagr_marker"]] = {
                "kind": "cagr",
                "value": series["cagr"],
                # The window the CAGR was actually computed over (valued endpoints), which can
                # be narrower than the selected range — never claim the wider one.
                "period": series.get("cagr_window") or dataset["period_key"],
                "concept": series["concept"],
                "label": series["label"],
                "unit": series["unit"],
                "percent": series["percent"],
                "derived": False,
                "reconciled": series.get("cagr_reconciled"),
            }
    return index


# --- AI narrative pipeline (M3) ----------------------------------------------------------------

NOT_ENOUGH_DATA_SENTINEL = "===NOT_ENOUGH_DATA==="

# Citation-group classification (what makes a bracket group a citation vs prose, and the
# linear-regex discipline behind it) lives in the shared citation_markers module — the copilot
# resolver's multi-ref pre-pass consumes the same knowledge.
_MARKER_GROUP_RE = citation_markers.MARKER_GROUP_RE
_MARKER_REF_RE = citation_markers.MARKER_REF_RE
_is_citation_group = citation_markers.is_citation_group


def _point_citation(n: int, point: dict[str, Any]) -> dict[str, Any]:
    """Render a dataset point as a citation dict in the Copilot citation shape ({n, excerpt,
    section_ref, verified, fragment_url}) so the existing frontend citation UI renders it as-is.

    ``kind == "cagr"`` entries are series-level CAGR markers: the value is a growth fraction over
    the selected window, not an XBRL level, so only their excerpt/attribution differ — the dict
    shape is ONE literal so the citation contract with the frontend can't fork per kind."""
    if point.get("kind") == "cagr":
        excerpt = f"{point['label']} CAGR = {_pct_str(point['value'])} ({point['period']})"
        section_ref = "Computed · CAGR"
    else:
        value_str = (
            _ratio_threshold_value(point["value"])
            if point.get("concept") == "current_ratio" and point.get("unit") == "pure"
            else _format_value(
                point["value"], point.get("unit") or "USD", bool(point.get("percent"))
            )
        )
        excerpt = f"{point['label']} = {value_str} ({point['period']})"
        if point.get("derived"):
            excerpt += " — derived Q4"
        section_ref = f"XBRL · {point.get('raw_tag') or point['concept']}"
    return {
        "n": n,
        "excerpt": excerpt,
        "section_ref": section_ref,
        "verified": True,
        "fragment_url": None,
        "concept": point["concept"],
        "value": point["value"],
        "period": point["period"],
        "derived": bool(point.get("derived")),
        "reconciled": point.get("reconciled"),
    }


def resolve_narrative_citations(
    text: str, index: dict[str, dict[str, Any]]
) -> tuple[str, list[dict[str, Any]], int, int]:
    """One left-to-right pass over the narrative: every ``[F#]`` reference resolves against the
    dataset's marker index and is renumbered ``[1]``, ``[2]``, ... in first-appearance order
    (repeat mentions reuse their number). Multi-reference groups a model may emit despite the
    prompt contract — ``[F1, F2]``, ``[F1..F10]``, ``[F1 vs F2]`` — resolve as a chain
    (``[1][2]``; ranges resolve their written endpoints). A reference the dataset never issued
    can ONLY be a model artifact — it is dropped (a group that loses every reference is stripped,
    swallowing the space before it, the ``_resolve_citations`` contract from Copilot) and counted
    in ``unverified`` so callers can surface how many references could not be verified.
    Returns (final_text, citations, grounded, unverified).
    """
    citations: list[dict[str, Any]] = []
    assigned: dict[str, int] = {}
    unverified = 0
    pieces: list[str] = []
    cursor = 0
    for match in _MARKER_GROUP_RE.finditer(text):
        content = match.group(1)
        if not _MARKER_REF_RE.search(content):
            continue  # no F-reference at all — ordinary prose brackets / markdown link labels
        if not _is_citation_group(content):
            continue  # prose that happens to contain an F-token — not a citation group
        numbers: list[int] = []
        for ref in _MARKER_REF_RE.findall(content):
            key = f"F{int(ref)}"
            point = index.get(key)
            if point is None:
                unverified += 1
                continue
            n = assigned.get(key)
            if n is None:
                n = len(citations) + 1
                assigned[key] = n
                citations.append(_point_citation(n, point))
            if n not in numbers:
                numbers.append(n)
        if numbers:
            pieces.append(text[cursor:match.start()])
            pieces.append("".join(f"[{n}]" for n in numbers))
        else:
            pieces.append(text[cursor:match.start()].rstrip(" "))
        cursor = match.end()
    pieces.append(text[cursor:])
    return "".join(pieces), citations, len(citations), unverified


def _illegal_refs(text: str, index: dict[str, dict[str, Any]]) -> list[str]:
    """F-references in a draft that the dataset never issued — the defect list fed back to the
    model on the regenerate-on-strip retry (audit D2). Over-approximate on purpose (any F-token
    inside brackets counts, prose or citation): a retry hint, not a resolution pass."""
    illegal: list[str] = []
    for match in _MARKER_GROUP_RE.finditer(text):
        for ref in _MARKER_REF_RE.findall(match.group(1)):
            key = f"F{int(ref)}"
            if key not in index and key not in illegal:
                illegal.append(key)
    return illegal


# --- numeric-fidelity scan (audit D2: the deterministic backstop behind "every cited figure") --

# A printed figure near a citation: optional $, digits with thousands commas, optional decimals,
# optional %/pp/compact-scale suffix (incl. the "bn"/"mn"/"tn" style). Linear (single
# character-class core, no nesting) — this scans model output on the event loop.
_FIDELITY_NUM_RE = re.compile(
    r"(\$)?(\d[\d,]*(?:\.\d+)?)\s*(%|pp|[bmt]n\b|[BTMK]\b|billion|million|trillion|thousand)?",
    re.IGNORECASE,
)
_FIDELITY_SCALES = {
    "k": 1e3, "thousand": 1e3,
    "m": 1e6, "mn": 1e6, "million": 1e6,
    "b": 1e9, "bn": 1e9, "billion": 1e9,
    "t": 1e12, "tn": 1e12, "trillion": 1e12,
}
# How far back from "[n]" the claimed figure may sit — the copilot adjacency window's sibling.
_FIDELITY_WINDOW_CHARS = 48
# A resolved citation marker inside the window ("[1]"): both a scrub target (its digits are NOT
# figures) and the window's hard left bound — the claim before an earlier marker belongs to THAT
# marker, not this one (the copilot _claim_span_start rule). Bounded digit run keeps it linear.
_FIDELITY_MARKER_RE = re.compile(r"\[\d{1,4}\]")


def _window_number_tokens(window: str) -> list[tuple[float, int, float]]:
    """Every printed figure in a window as (number, decimals, scale). Skips tokens that are not
    financial figures: period identifiers (FY2024, 2026Q3), bare years, and small bare counts
    ("over the past 5 years", "3rd consecutive quarter" — no $, no suffix, no decimals)."""
    tokens: list[tuple[float, int, float]] = []
    for match in _FIDELITY_NUM_RE.finditer(window):
        dollar, raw, suffix = match.group(1), match.group(2), match.group(3)
        start, end = match.start(2), match.end(2)
        if start > 0 and window[start - 1].isalpha():
            continue  # FY2024 / Q3-style token — part of an identifier
        if end < len(window) and window[end] == "Q":
            continue  # 2026Q3
        number = float(raw.replace(",", ""))
        decimals = len(raw.split(".")[1]) if "." in raw else 0
        if not dollar and suffix is None and decimals == 0:
            if 1900 <= number <= 2100:
                continue  # a bare year in prose
            if number < 1000:
                continue  # a small bare count, not a financial figure (the copilot rule)
        scale = _FIDELITY_SCALES.get(suffix.lower(), 1.0) if suffix else 1.0
        tokens.append((number, decimals, scale))
    return tokens


def _fidelity_candidates(citation: dict[str, Any], point: dict[str, Any]) -> list[float]:
    """Every dataset figure the prompt licenses against this marker: the point's value (plus its
    ×100 form for CAGR markers ONLY — growth fractions print as percentages, but licensing ×100
    for monetary values would wave through exactly the scale-slip errors the scan exists to
    catch) and the point's YoY/QoQ deltas (pp form for percent series, ×100 relative form
    otherwise)."""
    candidates: list[float] = []
    value = citation.get("value")
    if isinstance(value, (int, float)):
        candidates.append(float(value))
        if point.get("kind") == "cagr":
            candidates.append(float(value) * 100.0)
    for key in ("yoy", "qoq"):
        growth = point.get(key)
        if isinstance(growth, (int, float)):
            candidates.extend([float(growth), float(growth) * 100.0])
    return candidates


def _token_matches_any(token: tuple[float, int, float], candidates: list[float]) -> bool:
    """Half-ULP-of-the-printed-precision comparison: '391.0B' (1 decimal at 1e9 scale) accepts
    anything the display formatter would round to 391.0B. Signs compare absolutely — prose sign
    conventions vary ('outflow of $71.9B' cites a negative value)."""
    number, decimals, scale = token
    target = abs(number) * scale
    tolerance = max(0.55 * scale * 10.0 ** (-decimals), 1e-9)
    return any(abs(target - abs(c)) <= tolerance for c in candidates)


def scan_numeric_fidelity(
    text: str, citations: list[dict[str, Any]], index: dict[str, dict[str, Any]]
) -> list[int]:
    """Citation numbers whose adjacent claim contains figures and NONE of them matches the cited
    point's dataset figures. Deterministic, no model involved. The window is bounded at the
    previous citation marker (an earlier claim's figure belongs to ITS marker) — so in a chain
    "[1][2]" the second marker's window is empty and it passes as qualitative, the same rule the
    copilot adjacency guard applies. Qualitative references (no figure in the window) always
    pass; a claim citing several figures passes if ANY of them matches ("from $X to $Y [a][b]").
    """
    by_concept_period = {
        (entry.get("concept"), entry.get("period")): entry for entry in index.values()
    }
    mismatched: list[int] = []
    for citation in citations:
        n = citation.get("n")
        point = by_concept_period.get((citation.get("concept"), citation.get("period")), {})
        candidates = _fidelity_candidates(citation, point)
        if not candidates:
            continue
        marker = f"[{n}]"
        cursor = 0
        clean = True
        while clean:
            position = text.find(marker, cursor)
            if position == -1:
                break
            cursor = position + len(marker)
            window = text[max(0, position - _FIDELITY_WINDOW_CHARS):position]
            # Bound at the previous resolved marker — everything before it was that marker's claim.
            previous_marker = None
            for marker_match in _FIDELITY_MARKER_RE.finditer(window):
                previous_marker = marker_match
            if previous_marker is not None:
                window = window[previous_marker.end():]
            tokens = _window_number_tokens(window)
            if tokens and not any(_token_matches_any(t, candidates) for t in tokens):
                clean = False
        if not clean:
            mismatched.append(int(n))
    return mismatched


def _mismatch_details(mismatched: list[int], citations: list[dict[str, Any]]) -> list[str]:
    """Human-readable defect lines for the retry instruction. Named by concept/period, NOT by
    the renumbered [n] — the retry model sees its own raw [F#] draft, where [n] means nothing."""
    by_n = {c.get("n"): c for c in citations}
    details: list[str] = []
    for n in mismatched:
        c = by_n.get(n) or {}
        details.append(f"{c.get('concept')} {c.get('period')} (dataset value: {c.get('value')})")
    return details


def _retry_instruction(illegal: list[str], mismatched_details: list[str]) -> str:
    """The corrective turn for the one-shot regenerate-on-strip retry."""
    problems: list[str] = []
    if illegal:
        problems.append(
            "- These references do not exist in the dataset and must not appear: "
            + " ".join(f"[{ref}]" for ref in illegal)
            + ". Use ONLY marker IDs printed in the dataset."
        )
    if mismatched_details:
        problems.append(
            "- The figure you printed next to your citation of these dataset lines does not "
            "match the value they carry: " + "; ".join(mismatched_details) + ". Every number "
            "must be copied EXACTLY as printed on the dataset line whose marker you cite — "
            "never computed or approximated."
        )
    return (
        "Your draft was rejected for citation defects:\n"
        + "\n".join(problems)
        + "\nRewrite the FULL analysis now, following the Output Format exactly."
    )


def _merge_usage(total: dict[str, Any], attempt: dict[str, Any]) -> None:
    """Sum per-attempt token usage so cost telemetry reflects every model call of a retried run."""
    for key, value in attempt.items():
        if isinstance(value, (int, float)):
            total[key] = total.get(key, 0) + value
        else:
            total.setdefault(key, value)


def _load_cached_analysis(db: Session, company_id: int, mode: str, key: str):
    from app.models import TrendAnalysis

    return (
        db.query(TrendAnalysis)
        .filter(
            TrendAnalysis.company_id == company_id,
            TrendAnalysis.mode == mode,
            TrendAnalysis.period_key == key,
        )
        .first()
    )


def has_cached_analysis(
    db: Session, company_id: int, mode: str, start_period: str, end_period: str
) -> bool:
    """Whether a cached row exists for the naive ``start..end`` key — the router's cheap
    pre-flight probe: over-cap requests with a cached row can only resolve FREE (a cache
    re-serve or a system-invalidated regeneration), so they may proceed past the 429 gate.

    Conservative on purpose: ``build_dataset`` canonicalizes the period key from the actual data
    buckets, which can differ from the raw request range (e.g. the requested start year has no
    data) — a miss here just means the gate stays closed, never that quota leaks."""
    return _load_cached_analysis(db, company_id, mode, f"{start_period}..{end_period}") is not None


def _persist_analysis(
    *,
    company_id: int,
    mode: str,
    key: str,
    fingerprint: str,
    dataset: dict[str, Any],
    narrative: str,
    citations: list[dict[str, Any]],
    model: Optional[str],
    grounded: int,
    unverified: int,
    user_id: Optional[int],
) -> Optional[int]:
    """Upsert the cached analysis row on (company, mode, period_key) in a fresh session (the SSE
    generator outlives the request session). Best-effort: a persistence failure must never break
    the stream the user already received — it only costs the next request a regeneration."""
    from sqlalchemy.exc import IntegrityError

    from app.database import SessionLocal
    from app.models import TrendAnalysis

    db = SessionLocal()
    try:
        def _apply(row: "TrendAnalysis") -> None:
            row.prompt_version = PROMPT_VERSION
            row.dataset_fingerprint = fingerprint
            row.dataset_json = dataset
            row.narrative_md = narrative
            row.citations_json = citations
            row.model = model
            row.grounded = grounded
            row.unverified = unverified
            row.created_by_user_id = user_id

        row = _load_cached_analysis(db, company_id, mode, key)
        if row is None:
            row = TrendAnalysis(company_id=company_id, mode=mode, period_key=key)
            _apply(row)
            db.add(row)
            try:
                db.commit()
            except IntegrityError:
                # A concurrent generation won the unique key — update its row instead.
                db.rollback()
                row = _load_cached_analysis(db, company_id, mode, key)
                if row is None:
                    return None
                _apply(row)
                db.commit()
        else:
            _apply(row)
            db.commit()
        return row.id
    except Exception:  # noqa: BLE001 - cache write is best-effort
        logger.exception("failed to persist trend analysis for company %s", company_id)
        return None
    finally:
        db.close()


async def stream_trend_narrative(
    *,
    company_id: int,
    mode: str,
    start_period: str,
    end_period: str,
    force: bool = False,
    user_id: Optional[int] = None,
):
    """Transport-agnostic narrative pipeline: yields plain event dicts for the SSE route.

    Event contract (the Copilot shapes, so frontend consumers share plumbing):
      {"type": "progress", "stage", "message", "percent"}
      {"type": "token", "text"}                              (fresh generations only)
      {"type": "complete", "kind": "analysis" | "not_enough_data", "analysis_id", "narrative",
       "citations", "grounded", "cached", "n_periods", "usage"}
      {"type": "error", "message"}

    Cache-first (D4): if a row matches (company, mode, period_key) with the same prompt_version
    AND dataset_fingerprint, its narrative is re-served instantly — no model call, no meter (the
    router meters only non-cached "analysis" completions). ``force`` always regenerates.
    Opens its own sessions: the request's session is gone by the time this generator runs.
    """
    from app.database import SessionLocal
    from app.services.openai_service import STREAM_ERROR_SENTINEL, openai_service
    from app.services.prompt_loader import get_named_prompt

    yield {"type": "progress", "stage": "assembling", "message": "Assembling the numbers…", "percent": 10}

    db = SessionLocal()
    try:
        company = db.get(Company, company_id)
        if company is None:
            yield {"type": "error", "message": "Company not found."}
            return
        ticker = company.ticker
        try:
            dataset = build_dataset(db, company, mode, start_period, end_period)
        except ValueError as exc:
            yield {"type": "error", "message": str(exc)}
            return
        fingerprint = dataset_fingerprint(dataset)
        key = dataset["period_key"]
        cached = _load_cached_analysis(db, company_id, mode, key)
        if (
            not force
            and cached is not None
            and cached.narrative_md
            and cached.prompt_version == PROMPT_VERSION
            and cached.dataset_fingerprint == fingerprint
        ):
            cached_citations = cached.citations_json or []
            cached_mismatched = scan_numeric_fidelity(
                cached.narrative_md,
                cached_citations,
                marker_index(dataset),
            )
            yield {
                "type": "complete",
                "kind": "analysis",
                "analysis_id": cached.id,
                "narrative": cached.narrative_md,
                "citations": cached_citations,
                "grounded": cached.grounded,
                "unverified": cached.unverified,
                "mismatched": len(cached_mismatched),
                "cached": True,
                "invalidated": False,
                "n_periods": len(dataset["periods"]),
                "usage": {},
            }
            return
        # A cached row existed but no longer matches (prompt bump or new facts): this regeneration
        # is system-triggered, not user-triggered — the router exempts it from the fair-use meter.
        # A `force` refresh is user-initiated and stays metered.
        invalidated = cached is not None and not force
    finally:
        # Never hold a DB connection through the model call.
        db.close()

    yield {"type": "progress", "stage": "writing", "message": "Writing the analysis…", "percent": 30}

    if not _has_minimum_analysis_data(dataset):
        yield {
            "type": "complete",
            "kind": "not_enough_data",
            "analysis_id": None,
            "narrative": "",
            "citations": [],
            "grounded": 0,
            "unverified": 0,
            "cached": False,
            "invalidated": invalidated,
            "n_periods": len(dataset["periods"]),
            "usage": {},
        }
        return

    prompt = get_named_prompt("trends-analyst-agent")
    catalogue = build_observation_catalogue(dataset)
    selection_shape = json.dumps({key: [] for key, _ in ANALYSIS_SECTIONS}, separators=(",", ":"))
    base_messages = [
        {"role": "system", "content": prompt.raw},
        {
            "role": "user",
            "content": (
                compact_observation_catalogue(catalogue)
                + "\n\nReturn exactly one JSON object with this shape and no other text:\n"
                + selection_shape
            ),
        },
    ]

    index = marker_index(dataset)
    model_name = openai_service.model
    total_usage: dict[str, Any] = {}
    selection: Optional[dict[str, list[str]]] = None

    # The model may rank only catalogue IDs.  Its raw chunks are never user-visible.  One retry is
    # retained for malformed selection JSON; usage still sums every physical model call.
    for attempt in range(2):
        messages = list(base_messages)
        if attempt:
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "The prior reply was rejected. Return only the complete JSON object with "
                        "all six required keys. Every value must be a list of at most three IDs "
                        "from that key's section; do not add prose, fields, or replacement text."
                    ),
                }
            )
            yield {
                "type": "progress",
                "stage": "verifying",
                "message": "Re-checking the selection…",
                "percent": 80,
            }

        usage_sink: dict[str, int] = {}
        parts: list[str] = []
        stream_failed = False
        async for chunk in openai_service.stream_chat(
            messages,
            max_tokens=settings.ANALYSIS_MAX_TOKENS,
            temperature=0.2,
            usage_sink=usage_sink,
        ):
            if chunk.startswith(STREAM_ERROR_SENTINEL):
                detail = chunk[len(STREAM_ERROR_SENTINEL):]
                logger.warning("trend observation selection stream failed for %s: %s", ticker, detail)
                stream_failed = True
                break
            parts.append(chunk)
            if len(parts) % 40 == 0:
                yield {
                    "type": "progress",
                    "stage": "writing" if attempt == 0 else "verifying",
                    "message": "Selecting grounded observations…",
                    "percent": 60 if attempt == 0 else 85,
                }
        _merge_usage(total_usage, usage_sink)
        if stream_failed:
            yield {"type": "error", "message": "The analysis could not be generated. Please try again."}
            return

        candidate_text = "".join(parts).strip()
        selection = parse_observation_selection(candidate_text, catalogue)
        if selection is not None:
            break
    if selection is None:
        yield {"type": "error", "message": "The analysis could not be generated. Please try again."}
        return

    code_narrative = render_observation_selection(catalogue, selection)
    narrative, citations, grounded, unverified = resolve_narrative_citations(code_narrative, index)
    mismatched = scan_numeric_fidelity(narrative, citations, index)
    if unverified or mismatched:
        logger.error(
            "code-owned trend observations failed citation fidelity for %s (%s %s): "
            "unverified=%d mismatched=%s",
            ticker, mode, key, unverified, mismatched,
        )
        yield {"type": "error", "message": "The analysis could not be generated. Please try again."}
        return

    # The sole token payload is emitted only after strict selection validation and code rendering.
    yield {"type": "token", "text": narrative}
    analysis_id = _persist_analysis(
        company_id=company_id,
        mode=mode,
        key=key,
        fingerprint=fingerprint,
        dataset=dataset,
        narrative=narrative,
        citations=citations,
        model=model_name,
        grounded=grounded,
        unverified=unverified,
        user_id=user_id,
    )
    yield {
        "type": "complete",
        "kind": "analysis",
        "analysis_id": analysis_id,
        "narrative": narrative,
        "citations": citations,
        "grounded": grounded,
        "unverified": unverified,
        # Figures the deterministic fidelity scan could not reconcile in the code-rendered output.
        # Surfaced in the badge tooltip so "verified" never silently overclaims. Not persisted
        # (no column; cache hits recompute them from the saved narrative and citations against the
        # fingerprint-matched dataset).
        "mismatched": len(mismatched),
        "cached": False,
        "invalidated": invalidated,
        "n_periods": len(dataset["periods"]),
        "usage": {**total_usage, "model": model_name},
    }
