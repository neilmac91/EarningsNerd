"""Calculation lineage and publication policy shared by financial-data consumers.

Source method is independent of validation. Old derived rows have no operand evidence and
remain reviewable until re-normalized; the retired quarterly EPS estimate is never published.
This module is deliberately pure so every reader uses the same policy without another fetch.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Mapping

from app.utils.sec_urls import build_sec_archive_url

CALCULATION_VERSION = "quarterly-v2"
PROVENANCE_VERSION = 1
EPS_CONCEPTS = frozenset({"eps_basic", "eps_diluted", "earnings_per_share"})
METRIC_FORMULAS = {
    "net_margin": "100 * net_income / revenue",
    "operating_margin": "100 * operating_income / revenue",
    "gross_margin": "100 * gross_profit / revenue",
    "free_cash_flow": "operating_cash_flow - abs(capital_expenditures)",
    "working_capital": "current_assets - current_liabilities",
    "current_ratio": "current_assets / current_liabilities",
}
METRIC_INPUTS = {
    "net_margin": ("net_income", "revenue"),
    "operating_margin": ("operating_income", "revenue"),
    "gross_margin": ("gross_profit", "revenue"),
    "free_cash_flow": ("operating_cash_flow", "capital_expenditures"),
    "working_capital": ("current_assets", "current_liabilities"),
    "current_ratio": ("current_assets", "current_liabilities"),
}


def _get(fact: Any, name: str, default: Any = None) -> Any:
    return fact.get(name, default) if isinstance(fact, Mapping) else getattr(fact, name, default)


def _json_value(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def reported_provenance(fact: Any, filed_at: str | None = None) -> dict[str, Any]:
    """Describe an admitted reported fact without promising independent certification."""
    return {
        "version": PROVENANCE_VERSION,
        "method": "reported",
        "validation": "passed" if _get(fact, "reconciled") is True else "needs_review",
        "reasons": [] if _get(fact, "reconciled") is True else ["source_check_needed"],
        "formula": None,
        "inputs": [],
        "calculation_version": CALCULATION_VERSION,
        "filed_at": _json_value(filed_at or _get(fact, "filed_at")),
    }


def provenance_for_fact(fact: Any, cik: str | None = None) -> dict[str, Any]:
    """Project stored lineage, keeping absent legacy evidence explicitly unknown.

The synthetic EPS exclusion also covers stored pre-migration rows. It is a publication policy,
not another financial validation pass; ingestion alone owns admission of new source data.
"""
    stored = _get(fact, "provenance")
    if isinstance(stored, dict) and stored.get("version") == PROVENANCE_VERSION:
        provenance = deepcopy(stored)
        # Full statement HTML and transport receipts belong in the durable repair journal,
        # not every chart point, derived operand, model context and exported cell.
        provenance.pop("source_evidence", None)
    else:
        concept, raw_tag = _get(fact, "concept"), _get(fact, "raw_tag")
        calculated = _get(fact, "source") == "derived" or (
            concept in METRIC_FORMULAS and (not raw_tag or raw_tag == concept)
        )
        provenance = {
            "version": PROVENANCE_VERSION,
            "method": "calculated" if calculated else "reported" if _get(fact, "source") else "unknown",
            "validation": "needs_review" if calculated or _get(fact, "reconciled") is not True else "passed",
            "reasons": ["legacy_calculation"] if calculated else (
                [] if _get(fact, "reconciled") is True else ["source_check_needed"]
            ),
            "formula": None,
            "inputs": [],
            "calculation_version": None,
            "filed_at": None,
        }
    if _get(fact, "concept") in EPS_CONCEPTS and _get(fact, "source") == "derived":
        provenance.update(validation="unavailable", reasons=["unsupported_eps_calculation"])
    if cik:
        _attach_sources(provenance, cik, _get(fact, "accession"))
    return provenance


def _attach_sources(provenance: dict[str, Any], cik: str, accession: str | None) -> None:
    if not provenance.get("source_url") and provenance.get("method") == "reported":
        try:
            provenance["source_url"] = build_sec_archive_url(cik, accession)
        except ValueError:
            pass  # Legacy/synthetic identity: never invent a source link.
    for operand in provenance.get("inputs", []):
        try:
            operand["source_url"] = operand.get("source_url") or build_sec_archive_url(cik, operand.get("accession"))
        except ValueError:
            pass
        nested = operand.get("provenance")
        if isinstance(nested, dict):
            _attach_sources(nested, cik, operand.get("accession"))


def fact_operand(fact: Any) -> dict[str, Any]:
    """Retain exact immediate operands and their lineage, including units and period bounds."""
    operand = {
        name: _json_value(_get(fact, name))
        for name in ("concept", "value", "unit", "period_start", "period_end", "accession", "raw_tag", "filed_at")
    }
    provenance = provenance_for_fact(fact)
    operand["filed_at"] = operand["filed_at"] or provenance.get("filed_at")
    operand["provenance"] = provenance
    if provenance.get("source_url"):
        operand["source_url"] = provenance["source_url"]
    return operand


def calculated_provenance(
    formula: str, inputs: list[Any], *, reasons: list[str] | None = None,
) -> dict[str, Any]:
    """Carry operand eligibility forward without equating calculation with failure."""
    operands = [fact_operand(fact) for fact in inputs]
    validations = [operand["provenance"]["validation"] for operand in operands]
    issues = list(dict.fromkeys([
        *(reasons or []),
        *(reason for operand in operands for reason in operand["provenance"].get("reasons", [])),
    ]))
    validation = "unavailable" if "unavailable" in validations else (
        "needs_review" if issues or not operands or any(state != "passed" for state in validations) else "passed"
    )
    return {
        "version": PROVENANCE_VERSION,
        "method": "calculated",
        "validation": validation,
        "reasons": issues,
        "formula": formula,
        "inputs": operands,
        "calculation_version": CALCULATION_VERSION,
        "filed_at": max((operand["filed_at"] for operand in operands if operand.get("filed_at")), default=None),
        "period_calculation": any(operand["provenance"].get("period_calculation") for operand in operands),
    }


def published_value(fact: Any) -> float | None:
    """One withholding policy for analysis, fundamentals, peers and financial tools."""
    value = _get(fact, "value")
    if value is None or provenance_for_fact(fact)["validation"] == "unavailable":
        return None
    return float(value)
