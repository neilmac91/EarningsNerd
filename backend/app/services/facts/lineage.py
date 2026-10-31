"""Attach filing-scoped calculation evidence without changing source extraction."""
from __future__ import annotations

from copy import deepcopy
import math

from app.services.fact_provenance import (
    METRIC_FORMULAS, METRIC_INPUTS, calculated_provenance, reported_provenance,
)


def _is_calculated(fact: dict) -> bool:
    tag = fact.get("raw_tag")
    return fact.get("concept") in METRIC_FORMULAS and not (isinstance(tag, str) and ":" in tag)


def _scope(fact: dict) -> tuple:
    return tuple(fact.get(key) for key in (
        "company_id", "accession", "period_end", "fiscal_year", "fiscal_period",
    ))


def _operands(fact: dict, facts: list[dict]) -> list[dict]:
    operands = []
    for concept in METRIC_INPUTS[fact["concept"]]:
        matches = [item for item in facts if item.get("concept") == concept and _scope(item) == _scope(fact)]
        if len(matches) != 1:
            return []
        operands.append(matches[0])
    left, right = operands
    if (not left.get("unit") or left.get("unit") != right.get("unit")
            or left.get("period_start") != right.get("period_start")):
        return []
    start = left.get("period_start")
    if fact["concept"] not in {"working_capital", "current_ratio"} and start is None:
        return []  # The same period end alone does not establish a flow's duration.
    if fact.get("period_start") is not None and fact["period_start"] != start:
        return []
    return operands


def _expected(concept: str, operands: list[dict]) -> float | None:
    left, right = (item.get("value") for item in operands)
    if any(not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value)
           for value in (left, right)):
        return None
    if concept == "free_cash_flow":
        return left - abs(right)
    if concept == "working_capital":
        return left - right
    if right == 0:
        return None
    return left / right * (100 if concept.endswith("_margin") else 1)


def annotate_filing_calculations(facts: list[dict], *, initialize_reported: bool = False) -> list[dict]:
    """Known internal formulas are calculated; unresolved operands remain reviewable."""
    out = [dict(fact) for fact in facts]
    if initialize_reported:
        for fact in out:
            fact["provenance"] = reported_provenance(fact)
    for fact in out:
        if not _is_calculated(fact):
            continue
        prior = fact.get("provenance") or {}
        checks = deepcopy(prior.get("checks", {}))
        reasons = list(checks.get("local_reconciliation", {}).get("reasons", []))
        operands = _operands(fact, out)
        if not operands:
            reasons.append("missing_calculation_inputs")
        else:
            expected = _expected(fact["concept"], operands)
            value = fact.get("value")
            if (expected is None or not isinstance(value, (int, float)) or isinstance(value, bool)
                    or not math.isclose(value, expected, rel_tol=1e-9, abs_tol=1e-9)):
                reasons.append("calculation_mismatch")
        provenance = calculated_provenance(METRIC_FORMULAS[fact["concept"]], operands, reasons=reasons)
        if checks:
            provenance["checks"] = checks
        fact["provenance"] = provenance
        if "reconciled" in fact:
            fact["reconciled"] = provenance["validation"] == "passed"
    return out


def local_reconciliation(fact: dict, reasons: list[str]) -> dict:
    """Record every local reason, including those a later source check resolves."""
    fact = {**fact, "reconciled": not reasons}
    prior = fact.get("provenance") or {}
    provenance = reported_provenance(fact, filed_at=prior.get("filed_at"))
    provenance["reasons"] = list(reasons)
    provenance["checks"] = {**deepcopy(prior.get("checks", {})), "local_reconciliation": {"reasons": list(reasons)}}
    fact["provenance"] = provenance
    return fact


def authoritative_reconciliation(fact: dict, original: dict, authoritative: float) -> dict:
    """Keep the previous numeric value and resolved warnings in the source-check audit."""
    prior = original.get("provenance") or {}
    provenance = reported_provenance(fact, filed_at=prior.get("filed_at"))
    provenance["checks"] = {
        **deepcopy(prior.get("checks", {})),
        "authoritative": {
            "method": "companyfacts", "original_value": original.get("value"),
            "authoritative_value": authoritative, "resolved_reasons": list(prior.get("reasons", [])),
            "outcome": "replaced" if fact.get("value") != original.get("value") else "confirmed",
        },
    }
    return {**fact, "provenance": provenance}
