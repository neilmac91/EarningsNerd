"""Deterministic quarterization of compatible, additive companyfacts amounts.

EPS, shares and ratios are not additive. This module never derives them. Reported
quarters take precedence; unavailable or incompatible operands leave a gap.
"""
from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Any

from app.services.fact_provenance import METRIC_FORMULAS, calculated_provenance, fact_operand, reported_provenance

QUARTER_WINDOW = (75, 105)
FINAL_QUARTER_WINDOW = (75, 120)
MAX_FILING_GAP_DAYS = 150


def reported_fact(company_id: int, concept: str, unit: str, record: dict) -> dict:
    fact = {
        "company_id": company_id, "filing_id": None, "concept": concept,
        "raw_tag": record["raw_tag"], "unit": unit,
        "period_start": record["period_start"], "period_end": record["period_end"],
        "value": record["value"], "form": record.get("form"),
        "accession": record.get("accession") or "companyfacts",
        "source": "companyfacts", "reconciled": True,
    }
    fact["provenance"] = reported_provenance(fact, record.get("filed") or None)
    return fact


def _filed(record: dict) -> date | None:
    raw = record.get("filed") or (record.get("provenance") or {}).get("filed_at")
    try:
        return date.fromisoformat(str(raw)[:10]) if raw else None
    except ValueError:
        return None


def _same_value(a: dict, b: dict) -> bool:
    return math.isclose(a["value"], b["value"], rel_tol=1e-12, abs_tol=1e-9)


def _candidates(record: dict) -> list[dict]:
    return record.get("candidates") or [record]


def _selected_candidates(record: dict) -> list[dict]:
    return [candidate for candidate in _candidates(record)
            if _same_value(candidate, record)
            and candidate["period_start"] == record["period_start"]
            and candidate["period_end"] == record["period_end"]
            and candidate.get("raw_tag") == record.get("raw_tag")
            and candidate.get("unit", "USD") == record.get("unit", "USD")]


def _has_revision(record: dict) -> bool:
    return any(not _same_value(candidate, record) for candidate in _candidates(record))


def compatible_vintages(later: dict, earlier: dict) -> tuple[dict, dict] | None:
    """Choose evidence for the selected values, never an obsolete numeric value.

    Same-accession observations supply their own coherent vintage. Cross-filing
    subtraction requires unchanged histories and nearby, chronological filings.
    An independently restated operand cannot acquire a passing calculation flag.
    """
    late = sorted(_selected_candidates(later), key=lambda r: _filed(r) or date.min, reverse=True)
    early = sorted(_selected_candidates(earlier), key=lambda r: _filed(r) or date.min, reverse=True)
    for current in late:
        for previous in early:
            accession = current.get("accession")
            if accession and accession != "companyfacts" and accession == previous.get("accession"):
                return current, previous
    if _has_revision(later) or _has_revision(earlier):
        return None
    for current in late:
        current_filed = _filed(current)
        if current_filed is None or current_filed < current["period_end"]:
            continue
        for previous in early:
            previous_filed = _filed(previous)
            if previous_filed is None or previous_filed < previous["period_end"]:
                continue
            if 0 <= (current_filed - previous_filed).days <= MAX_FILING_GAP_DAYS:
                return current, previous
    return None


def _matching_interval(later: dict, earlier: dict, *, final_quarter: bool = False) -> bool:
    start = later.get("period_start")
    window = FINAL_QUARTER_WINDOW if final_quarter else QUARTER_WINDOW
    return bool(
        start is not None and start == earlier.get("period_start")
        and later.get("raw_tag") and later["raw_tag"] == earlier.get("raw_tag")
        and later.get("unit", "USD") == earlier.get("unit", "USD") == "USD"
        and window[0] <= (later["period_end"] - earlier["period_end"]).days <= window[1]
    )


def _calculated_quarter(template: dict, fiscal_year: int, quarter: str,
                        value: float, start: date, formula: str, inputs: list[dict]) -> dict:
    provenance = calculated_provenance(formula, inputs)
    provenance["period_calculation"] = True
    return {
        **template, "value": value, "period_start": start,
        "fiscal_year": fiscal_year, "fiscal_period": quarter,
        "source": "derived", "raw_tag": None,
        "reconciled": provenance["validation"] == "passed", "provenance": provenance,
    }


def derive_cumulative_quarters(
    company_id: int, facts: list[dict], duration_values: dict,
    quarter_labels: dict[date, tuple[str, int]],
) -> tuple[list[dict], list[dict]]:
    """Q2 = six months − Q1; Q3 = nine months − six; Q4 = FY − nine.

    Cumulative slices are inputs only, never quarter facts. Each missing output
    has a bounded reason for ingestion diagnostics, rather than 'not reported'.
    """
    existing = {(f["concept"], f.get("fiscal_year"), f["fiscal_period"]) for f in facts}
    annual_years = {f["period_end"]: f["fiscal_year"] for f in facts if f["fiscal_period"] == "FY"}
    derived, excluded = [], []
    rules = {"YTD6": ("Q2", "Q", "YTD6 - Q1"),
             "YTD9": ("Q3", "YTD6", "YTD9 - YTD6"),
             "FY": ("Q4", "YTD9", "FY - YTD9")}
    for concept, values in duration_values.items():
        for (end, kind), current in values.items():
            if kind not in rules or current.get("unit", "USD") != "USD":
                continue
            quarter, prior_kind, formula = rules[kind]
            label = ("Q4", annual_years.get(end, end.year)) if kind == "FY" else quarter_labels.get(end)
            if label is None or label[0] != quarter:
                continue
            fiscal_year = label[1]
            if (concept, fiscal_year, quarter) in existing:
                continue
            priors = [r for (_pe, klass), r in values.items()
                      if klass == prior_kind and _matching_interval(current, r, final_quarter=kind == "FY")]
            pair = next((chosen for prior in priors
                         if (chosen := compatible_vintages(current, prior)) is not None), None)
            if pair is None:
                excluded.append({"concept": concept, "fiscal_year": fiscal_year,
                                 "fiscal_period": quarter,
                                 "reason": "incompatible_vintages" if priors else "missing_compatible_operand",
                                 "inputs": [fact_operand(reported_fact(company_id, concept, "USD", r))
                                            for r in [current, *priors]]})
                continue
            high, low = (reported_fact(company_id, concept, "USD", r) for r in pair)
            derived.append(_calculated_quarter(
                reported_fact(company_id, concept, "USD", current),
                fiscal_year, quarter, high["value"] - low["value"],
                low["period_end"] + timedelta(days=1), formula, [high, low],
            ))
            existing.add((concept, fiscal_year, quarter))
    return derived, excluded


def _record_for_fact(fact: dict, values: dict) -> dict:
    kind = "FY" if fact["fiscal_period"] == "FY" else "Q"
    record = values.get((fact["period_end"], kind))
    return record if record is not None and _same_value(record, fact) else fact


def _compatible_quarter_sum(fy: dict, quarters: list[dict], values: dict) -> bool:
    """Fallback only for three contiguous reported quarters in the same scope."""
    cursor = fy["period_start"]
    records = [_record_for_fact(q, values) for q in [*quarters, fy]]
    for quarter in quarters:
        if (quarter.get("source") == "derived" or not quarter.get("reconciled")
                or quarter.get("raw_tag") != fy.get("raw_tag")
                or quarter.get("unit") != fy.get("unit")
                or quarter.get("period_start") != cursor
                or not QUARTER_WINDOW[0] <= (quarter["period_end"] - cursor).days <= QUARTER_WINDOW[1]):
            return False
        cursor = quarter["period_end"] + timedelta(days=1)
    if not FINAL_QUARTER_WINDOW[0] <= (fy["period_end"] - cursor).days <= FINAL_QUARTER_WINDOW[1]:
        return False
    return all(compatible_vintages(later, earlier) is not None
               for earlier, later in zip(records, records[1:]))


def derive_quarter_sum_fallback(facts: list[dict], duration_values: dict | None = None) -> list[dict]:
    groups: dict[tuple[str, Any], dict[str, dict]] = {}
    for fact in facts:
        if fact.get("unit") == "USD" and fact.get("period_start") is not None:
            groups.setdefault((fact["concept"], fact.get("fiscal_year")), {})[fact["fiscal_period"]] = fact
    derived = []
    for (concept, fiscal_year), periods in groups.items():
        fy = periods.get("FY")
        if fy is None or not fy.get("reconciled") or "Q4" in periods:
            continue
        values = (duration_values or {}).get(concept, {})
        # A matching cumulative operand that failed vintage validation must not be
        # bypassed through a less informative sum of separately reported quarters.
        if any(klass == "YTD9" and _matching_interval(_record_for_fact(fy, values), record, final_quarter=True)
               for (_end, klass), record in values.items()):
            continue
        quarters = [periods.get(q) for q in ("Q1", "Q2", "Q3")]
        if any(q is None for q in quarters):
            continue
        if not _compatible_quarter_sum(fy, quarters, values):
            continue
        derived.append(_calculated_quarter(
            fy, fiscal_year, "Q4", fy["value"] - sum(q["value"] for q in quarters),
            quarters[-1]["period_end"] + timedelta(days=1), "FY - (Q1 + Q2 + Q3)", [fy, *quarters],
        ))
    return derived


def same_period_provenance(concept: str, inputs: list[dict]) -> dict:
    return calculated_provenance(METRIC_FORMULAS[concept], inputs)


def same_scope(a: dict, b: dict) -> bool:
    """Metrics require the same reporting duration and currency, including instants."""
    return (a.get("period_start") == b.get("period_start")
            and a.get("period_end") == b.get("period_end")
            and a.get("unit") == b.get("unit"))
