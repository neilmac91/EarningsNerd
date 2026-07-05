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

logger = logging.getLogger(__name__)

# Bump on ANY change to the narrative prompt or the compact dataset rendering — invalidates every
# cached TrendAnalysis row fleet-wide (they regenerate lazily on next request).
PROMPT_VERSION = "trends-v1"

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


def _growth(current: Optional[float], prior: Optional[float]) -> Optional[float]:
    """Fractional growth with the compute_metric edge discipline: no prior / zero prior → None."""
    if current is None or prior is None or prior == 0:
        return None
    return (current - prior) / abs(prior)


def _cagr(first: float, last: float, years: int) -> Optional[float]:
    """Compound annual growth rate; only defined for positive endpoints over ≥1 year."""
    if years < 1 or first <= 0 or last <= 0:
        return None
    return (last / first) ** (1.0 / years) - 1.0


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
                    "derived": row.source == "derived",
                    "reconciled": bool(row.reconciled),
                    "fiscal_year": row.fiscal_year,
                    "fiscal_period": row.fiscal_period,
                }
            )
        if not any_value:
            continue

        unit = next((p["unit"] for p in points if p.get("unit")), "USD")

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
            point["yoy"] = _growth(point["value"], prior["value"] if prior else None)
        # QoQ: the immediately preceding column (quarterly only).
        if mode == "quarterly":
            previous: Optional[dict[str, Any]] = None
            for point in points:
                if point["value"] is not None:
                    point["qoq"] = _growth(
                        point["value"], previous["value"] if previous else None
                    )
                    previous = point

        # CAGR over the selected window (annual mode, monetary/per-share series only).
        cagr = None
        if mode == "annual" and unit != "pure":
            valued = [
                (bucket["fiscal_year"], point["value"])
                for bucket, point in zip(periods, points)
                if point["value"] is not None
            ]
            if len(valued) >= 2:
                (first_fy, first), (last_fy, last) = valued[0], valued[-1]
                cagr = _cagr(first, last, last_fy - first_fy)

        series_list.append(
            {
                "concept": concept,
                "label": concept_label(concept),
                "unit": unit,
                "percent": concept in _PERCENT_CONCEPTS,
                "cagr": cagr,
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


def _pct(value: float) -> str:
    return f"{value * 100:+.1f}%"


def detect_growth_deceleration(dataset: dict[str, Any]) -> list[dict[str, Any]]:
    """Top-line YoY growth strictly declining across the three most recent measurable periods."""
    flags = []
    series_by = _series_map(dataset)
    for concept in ("revenue", "net_interest_income"):
        points = [p for p in _valued_points(series_by.get(concept)) if p.get("yoy") is not None]
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
                        f"periods: {_pct(yoys[0])} → {_pct(yoys[1])} → {_pct(yoys[2])}."
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
                    f"Long-term debt grew {_pct(growth)} from {first['period']} to "
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
            header += f" — CAGR {_pct_str(series['cagr'])}"
        lines.append(header)
        for point in series["points"]:
            if point["value"] is None:
                lines.append(f"  {point['period']}: not reported")
                continue
            rendered = _format_value(point["value"], series["unit"], series["percent"])
            growth_bits = []
            if point.get("yoy") is not None:
                growth_bits.append(f"YoY {_pct_str(point['yoy'])}")
            if point.get("qoq") is not None:
                growth_bits.append(f"QoQ {_pct_str(point['qoq'])}")
            suffix = f" ({', '.join(growth_bits)})" if growth_bits else ""
            derived = " [derived]" if point.get("derived") else ""
            lines.append(f"  [{point['marker']}] {point['period']}: {rendered}{suffix}{derived}")
        lines.append("")

    if dataset.get("inflections"):
        lines.append("## Signals detected (deterministic, pre-computed)")
        for flag in dataset["inflections"]:
            markers = ", ".join(flag.get("markers") or [])
            lines.append(f"- {flag['kind']}: {flag['detail']}" + (f" [{markers}]" if markers else ""))
        lines.append("")
    return "\n".join(lines)


def _pct_str(value: float) -> str:
    return f"{value * 100:+.1f}%"


def marker_index(dataset: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """F# marker -> its dataset point (augmented with concept/label context) for citation
    resolution in the narrative pipeline."""
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
    return index
