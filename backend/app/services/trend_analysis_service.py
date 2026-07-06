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
from datetime import date
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
PROMPT_VERSION = "trends-v3"

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
    # A Q4 column is a computed-Q4 column iff EVERY row in it came from the Q4 derivation (the
    # picker-chip rule). This is what the "— derived Q4" / † labels mean, and it is deliberately
    # column-level: a rare filer that reports a DISCRETE Q4 has companyfacts rows in the group,
    # so its real Q4 (and the metrics computed from it) must never be labelled an estimate —
    # while metrics computed ON a derived-Q4 column genuinely rest on FY−Q1..Q3 estimates.
    q4_fully_derived: dict[int, bool] = {}
    for row in rows:
        if row.fiscal_year is None:
            continue
        by_fy_fp[(row.fiscal_year, row.fiscal_period, row.concept)] = row
        if row.concept in INSTANT_CONCEPTS:
            instant_by_end[(row.concept, row.period_end)] = row
        if row.fiscal_period == "Q4":
            q4_fully_derived[row.fiscal_year] = (
                q4_fully_derived.get(row.fiscal_year, True) and row.source == "derived"
            )

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
                    # current ratio) "derived" for EVERY period, and the per-filing path writes
                    # the same computations as "edgar_xbrl" — so the raw source flag flickers by
                    # ingest history and would mislabel an FY2016 margin as a "derived Q4".
                    # Column-level rule (see q4_fully_derived above): a point is a computed-Q4
                    # value iff it sits on a Q4 column whose every row came from the derivation.
                    "derived": (
                        row.fiscal_period == "Q4"
                        and q4_fully_derived.get(row.fiscal_year, False)
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
        # QoQ: the immediately preceding column (quarterly only).
        if mode == "quarterly":
            previous: Optional[dict[str, Any]] = None
            for point in points:
                if point["value"] is not None:
                    point["qoq"] = delta_fn(
                        point["value"], previous["value"] if previous else None
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

        series_list.append(
            {
                "concept": concept,
                "label": concept_label(concept),
                "unit": unit,
                "percent": is_percent,
                "tone": _SERIES_TONE.get(concept, "normal"),
                "cagr": cagr,
                "cagr_window": cagr_window,
                "window_pp": window_pp,
                "window_pp_range": window_pp_range,
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
            flags.append(
                {
                    "kind": "growth_deceleration",
                    "concepts": [concept],
                    "periods": [p["period"] for p in last3],
                    "detail": (
                        f"{concept_label(concept)} YoY growth decelerated for three straight "
                        f"periods: {_pct_str(yoys[0])} → {_pct_str(yoys[1])} → {_pct_str(yoys[2])}."
                    ),
                    "markers": [p["marker"] for p in last3],
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
            flags.append(
                {
                    "kind": "margin_compression",
                    "concepts": [concept],
                    "periods": [p["period"] for p in last3],
                    "detail": (
                        f"{concept_label(concept)} compressed {values[0] - values[2]:.1f}pp over "
                        f"three periods: {values[0]:.1f}% → {values[1]:.1f}% → {values[2]:.1f}%."
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
                "markers": [last_fcf["marker"], last_ni["marker"]],
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
        detail = f"Current ratio is below 1.0 ({last['value']:.2f}× in {last['period']})."
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
        value_str = _format_value(
            point["value"], point.get("unit") or "USD", bool(point.get("percent"))
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
# optional %/pp/compact-scale suffix. Linear (single character-class core, no nesting) — this
# scans model output on the event loop.
_FIDELITY_NUM_RE = re.compile(
    r"\$?(\d[\d,]*(?:\.\d+)?)\s*(%|pp|[BTMK]\b|billion|million|trillion|thousand)?",
    re.IGNORECASE,
)
_FIDELITY_SCALES = {
    "k": 1e3, "thousand": 1e3,
    "m": 1e6, "million": 1e6,
    "b": 1e9, "billion": 1e9,
    "t": 1e12, "trillion": 1e12,
}
# How far back from "[n]" the claimed figure may sit — the copilot adjacency window's sibling.
_FIDELITY_WINDOW_CHARS = 48


def _last_number_token(window: str) -> Optional[tuple[float, int, float]]:
    """The last printed figure in a window as (number, decimals, scale) — or None when the
    reference is qualitative. Period identifiers (FY2024, 2026Q3, bare years) are skipped: they
    are labels, not figures."""
    best: Optional[tuple[float, int, float]] = None
    for match in _FIDELITY_NUM_RE.finditer(window):
        raw, suffix = match.group(1), match.group(2)
        start, end = match.start(1), match.end(1)
        if start > 0 and window[start - 1].isalpha():
            continue  # FY2024 / Q3-style token — part of an identifier
        if end < len(window) and window[end] == "Q":
            continue  # 2026Q3
        number = float(raw.replace(",", ""))
        decimals = len(raw.split(".")[1]) if "." in raw else 0
        if suffix is None and decimals == 0 and 1990 <= number <= 2100:
            continue  # a bare year in prose
        scale = _FIDELITY_SCALES.get(suffix.lower(), 1.0) if suffix else 1.0
        best = (number, decimals, scale)
    return best


def _fidelity_candidates(citation: dict[str, Any], point: dict[str, Any]) -> list[float]:
    """Every dataset figure the prompt licenses against this marker: the point's value (raw and
    ×100 — CAGR/growth markers store fractions but print percentages) plus its YoY/QoQ deltas
    (pp form for percent series, ×100 relative form otherwise)."""
    candidates: list[float] = []
    value = citation.get("value")
    if isinstance(value, (int, float)):
        candidates.extend([float(value), float(value) * 100.0])
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
    """Citation numbers whose ADJACENT printed figure matches none of the cited point's dataset
    figures. Deterministic, no model involved. Qualitative references (no number in the window)
    always pass — mirroring the copilot adjacency guard's qualitative-placement rule."""
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
            token = _last_number_token(text[max(0, position - _FIDELITY_WINDOW_CHARS):position])
            if token is not None and not _token_matches_any(token, candidates):
                clean = False
        if not clean:
            mismatched.append(int(n))
    return mismatched


def _retry_instruction(illegal: list[str], mismatched: list[int]) -> str:
    """The corrective turn for the one-shot regenerate-on-strip retry."""
    problems: list[str] = []
    if illegal:
        problems.append(
            "- These references do not exist in the dataset and must not appear: "
            + " ".join(f"[{ref}]" for ref in illegal)
            + ". Use ONLY marker IDs printed in the dataset."
        )
    if mismatched:
        problems.append(
            "- Some figures do not match the dataset value carried by the marker cited next to "
            "them. Every number must be copied EXACTLY as printed on the dataset line whose "
            "marker you cite — never computed or approximated."
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
            yield {
                "type": "complete",
                "kind": "analysis",
                "analysis_id": cached.id,
                "narrative": cached.narrative_md,
                "citations": cached.citations_json or [],
                "grounded": cached.grounded,
                "unverified": cached.unverified,
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

    prompt = get_named_prompt("trends-analyst-agent")
    base_messages = [
        {"role": "system", "content": prompt.raw},
        {
            "role": "user",
            "content": (
                compact_dataset_for_prompt(dataset)
                + "\nWrite the multi-period trend analysis now, following the Output Format exactly."
            ),
        },
    ]

    index = marker_index(dataset)
    model_name = openai_service.model
    total_usage: dict[str, Any] = {}
    # Best attempt so far: (defect_count, narrative, citations, grounded, unverified, mismatched).
    best: Optional[tuple[int, str, list[dict[str, Any]], int, int, list[int]]] = None
    draft_text = ""

    # One-shot regenerate-on-strip (audit D2): when the first draft cites markers the dataset
    # never issued, or prints figures that don't match the cited values, retry ONCE with the
    # defect list. The client keeps showing draft 1 (attempt-2 token yields are suppressed; the
    # authoritative `complete` replaces buffered tokens), so the retry degrades gracefully to a
    # longer "writing" phase. Exactly one complete event + one persisted row either way — the
    # router's meter sees a single fresh completion, and `usage` sums both model calls.
    for attempt in range(2):
        messages = list(base_messages)
        if attempt:
            _, _, _, _, prior_unverified, prior_mismatched = best  # type: ignore[misc]
            messages.append({"role": "assistant", "content": draft_text})
            messages.append(
                {
                    "role": "user",
                    "content": _retry_instruction(
                        _illegal_refs(draft_text, index) if prior_unverified else [],
                        prior_mismatched,
                    ),
                }
            )
            yield {
                "type": "progress",
                "stage": "verifying",
                "message": "Re-checking citations…",
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
                logger.warning("trend narrative stream failed for %s: %s", ticker, detail)
                if attempt == 0:
                    yield {"type": "error", "message": "The analysis could not be generated. Please try again."}
                    return
                stream_failed = True  # retry failed — draft 1's resolution stands
                break
            parts.append(chunk)
            if attempt == 0:
                yield {"type": "token", "text": chunk}
        _merge_usage(total_usage, usage_sink)
        if stream_failed:
            break

        candidate_text = "".join(parts).strip()
        if not candidate_text:
            if attempt == 0:
                yield {"type": "error", "message": "The analysis could not be generated. Please try again."}
                return
            break
        if NOT_ENOUGH_DATA_SENTINEL in candidate_text:
            if attempt == 0:
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
                    "usage": {**total_usage, "model": model_name},
                }
                return
            break  # a retry that suddenly claims no-data is noise — draft 1 stands

        resolved, cites, grounded_c, unverified_c = resolve_narrative_citations(
            candidate_text, index
        )
        mismatched_c = scan_numeric_fidelity(resolved, cites, index)
        defects = unverified_c + len(mismatched_c)
        if best is None or defects < best[0]:
            best = (defects, resolved, cites, grounded_c, unverified_c, mismatched_c)
        if defects == 0:
            break
        draft_text = candidate_text

    if best is None:  # unreachable: attempt 0 either returned early or recorded a result
        yield {"type": "error", "message": "The analysis could not be generated. Please try again."}
        return
    _, narrative, citations, grounded, unverified, mismatched = best
    if unverified:
        logger.warning(
            "trend narrative for %s (%s %s) carried %d unresolvable citation reference(s) after retry",
            ticker, mode, key, unverified,
        )
    if mismatched:
        logger.warning(
            "trend narrative for %s (%s %s) has %d citation(s) whose adjacent figure does not "
            "match the cited dataset value after retry: %s",
            ticker, mode, key, len(mismatched), mismatched,
        )
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
        "cached": False,
        "invalidated": invalidated,
        "n_periods": len(dataset["periods"]),
        "usage": {**total_usage, "model": model_name},
    }
