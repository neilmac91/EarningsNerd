"""Derive compatible quarterly and same-period facts with operand provenance."""
from __future__ import annotations

from datetime import date
from typing import Any, Optional

from app.services.facts.concepts import _unit_for
from app.services.facts.quarterly import (
    derive_cumulative_quarters, derive_quarter_sum_fallback, same_period_provenance, same_scope,
)


def derive_q4_facts(
    facts: list[dict[str, Any]],
    duration_values: Optional[dict[str, dict[tuple[date, str], dict[str, Any]]]] = None,
) -> list[dict[str, Any]]:
    """Reported-only EPS; additive Q4 from compatible cumulative or discrete inputs."""
    if not facts:
        return []
    values = {concept: dict(records) for concept, records in (duration_values or {}).items()}
    for fact in facts:
        if fact["fiscal_period"] == "FY" and fact.get("reconciled") and fact.get("period_start"):
            values.setdefault(fact["concept"], {}).setdefault((fact["period_end"], "FY"), fact)
    derived, _ = derive_cumulative_quarters(facts[0]["company_id"], facts, values, {})
    q4 = [fact for fact in derived if fact["fiscal_period"] == "Q4"]
    return q4 + derive_quarter_sum_fallback([*facts, *q4], duration_values)


def derive_same_period_metrics(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Same-period derived metrics per (fiscal_year, fiscal_period) group.

    Margins ×100 (unit "pure"), free_cash_flow = OCF − |capex|, working_capital = CA − CL,
    current_ratio = CA ÷ CL — the exact formulas the per-filing extractor uses
    (xbrl_service.extract_standardized_metrics), so companyfacts- and filing-sourced rows agree.
    Identical periods and units are required. Operand provenance carries validation and
    calculation method independently; an unsupported operand cannot gain passing quality
    through a margin, cash-flow or liquidity calculation. Existing concepts are preserved.
    """
    groups: dict[tuple[Any, Any], dict[str, dict[str, Any]]] = {}
    for fact in facts:
        key = (fact.get("fiscal_year"), fact.get("fiscal_period"))
        groups.setdefault(key, {})[fact["concept"]] = fact

    def _make(
        concept: str, value: float, template: dict[str, Any], inputs: list[dict[str, Any]]
    ) -> dict[str, Any]:
        provenance = same_period_provenance(concept, inputs)
        return {
            **template, "concept": concept, "raw_tag": None,
            "unit": _unit_for(concept, template.get("unit")), "value": value, "source": "derived",
            "reconciled": provenance["validation"] == "passed", "provenance": provenance,
        }

    derived: list[dict[str, Any]] = []
    for by_concept in groups.values():
        revenue = by_concept.get("revenue")
        if revenue and revenue["value"]:
            for margin_key, numerator_key in (
                ("net_margin", "net_income"),
                ("gross_margin", "gross_profit"),
                ("operating_margin", "operating_income"),
            ):
                numerator = by_concept.get(numerator_key)
                if (
                    margin_key not in by_concept
                    and numerator is not None
                    and same_scope(numerator, revenue)
                ):
                    derived.append(
                        _make(
                            margin_key,
                            (numerator["value"] / revenue["value"]) * 100,
                            revenue,
                            [revenue, numerator],
                        )
                    )

        ocf, capex = by_concept.get("operating_cash_flow"), by_concept.get("capital_expenditures")
        if (
            "free_cash_flow" not in by_concept
            and ocf is not None
            and capex is not None
            and same_scope(ocf, capex)
        ):
            derived.append(
                _make("free_cash_flow", ocf["value"] - abs(capex["value"]), ocf, [ocf, capex])
            )

        ca, cl = by_concept.get("current_assets"), by_concept.get("current_liabilities")
        if (
            ca is not None
            and cl is not None
            and same_scope(ca, cl)
            and ca["value"] >= 0
            and cl["value"] >= 0
        ):
            if "working_capital" not in by_concept:
                derived.append(_make("working_capital", ca["value"] - cl["value"], ca, [ca, cl]))
            if "current_ratio" not in by_concept and cl["value"] > 0:
                derived.append(_make("current_ratio", ca["value"] / cl["value"], ca, [ca, cl]))
    return derived

