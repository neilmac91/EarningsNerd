"""Filing-derived metrics retain scope, operands, and reconciliation history."""
from datetime import date

import pytest

from app.services import facts_service as svc


def _normalized(*, start="2024-01-01", capex=-30, total=70):
    entries = {}
    for concept, value in (("operating_cash_flow", 100), ("capital_expenditures", capex), ("free_cash_flow", total)):
        entries[concept] = {"current": {"period": "2024-12-31", "period_start": start, "value": value}}
    return svc.normalize_standardized_to_facts(1, 10, "FILING", "10-K", entries)


def test_filing_calculation_preserves_signed_capex_and_exact_operands():
    facts, rejected = svc.reconcile_facts(_normalized())
    assert not rejected
    fcf = next(f for f in facts if f["concept"] == "free_cash_flow")
    assert fcf["source"] == "edgar_xbrl"
    assert fcf["reconciled"] is True
    assert fcf["provenance"]["method"] == "calculated"
    assert fcf["provenance"]["formula"] == "operating_cash_flow - abs(capital_expenditures)"
    assert fcf["provenance"]["validation"] == "passed"
    assert [f["value"] for f in fcf["provenance"]["inputs"]] == [100, -30]
    assert {f["period_start"] for f in fcf["provenance"]["inputs"]} == {"2024-01-01"}


@pytest.mark.parametrize("mutation", ["missing", "duration", "unit", "accession", "unknown_duration"])
def test_filing_calculation_without_compatible_inputs_never_claims_reported(mutation):
    facts = _normalized(start=None if mutation == "unknown_duration" else "2024-01-01")
    if mutation == "missing":
        facts.pop(0)
    elif mutation == "duration":
        facts[0]["period_start"] = date(2024, 10, 1)
    elif mutation == "unit":
        facts[0]["unit"] = "EUR"
    elif mutation == "accession":
        facts[0]["accession"] = "OTHER"
    admitted, _ = svc.reconcile_facts(facts)
    fcf = next(f for f in admitted if f["concept"] == "free_cash_flow")
    assert fcf["provenance"]["method"] == "calculated"
    assert fcf["provenance"]["validation"] == "needs_review"
    assert "missing_calculation_inputs" in fcf["provenance"]["reasons"]


def test_local_reconciliation_reason_propagates_into_calculation():
    admitted, _ = svc.reconcile_facts(_normalized(), prior_values={"operating_cash_flow": 1})
    fcf = next(f for f in admitted if f["concept"] == "free_cash_flow")
    assert fcf["reconciled"] is False
    assert "magnitude_vs_prior" in fcf["provenance"]["reasons"]
    assert fcf["provenance"]["inputs"][0]["provenance"]["checks"]["local_reconciliation"]["reasons"] == ["magnitude_vs_prior"]


def test_authoritative_correction_preserves_resolved_reasons_and_flags_stale_metric():
    entries = {concept: {"current": {"period": "2024-12-31", "period_start": "2024-01-01", "value": value}}
               for concept, value in (("revenue", 1), ("net_income", 0.2), ("net_margin", 20))}
    facts = svc.normalize_standardized_to_facts(1, 10, "FILING", "10-K", entries)
    admitted, _ = svc.reconcile_facts(facts, prior_values={"revenue": 100})
    corrected = svc.cross_check_facts(admitted, {("revenue", date(2024, 12, 31)): 100})
    revenue = next(f for f in corrected if f["concept"] == "revenue")
    margin = next(f for f in corrected if f["concept"] == "net_margin")
    assert revenue["value"] == 100 and revenue["reconciled"] is True
    assert revenue["provenance"]["reasons"] == []
    audit = revenue["provenance"]["checks"]["authoritative"]
    assert audit["original_value"] == 1 and audit["outcome"] == "replaced"
    assert audit["resolved_reasons"] == ["magnitude_vs_prior"]
    assert margin["provenance"]["validation"] == "needs_review"
    assert "calculation_mismatch" in margin["provenance"]["reasons"]
    assert margin["provenance"]["inputs"][1]["value"] == 100


def test_real_tagged_metric_keeps_reported_method_and_instant_calculation_is_valid():
    entries = {concept: {"current": {"period": "2024-12-31", "value": value}}
               for concept, value in (("current_assets", 100), ("current_liabilities", 25), ("current_ratio", 4))}
    entries["net_margin"] = {"current": {"period": "2024-12-31", "value": 20, "raw_tag": "custom:NetMargin"}}
    facts = svc.normalize_standardized_to_facts(1, 10, "FILING", "10-K", entries)
    admitted, _ = svc.reconcile_facts(facts)
    assert next(f for f in admitted if f["concept"] == "net_margin")["provenance"]["method"] == "reported"
    ratio = next(f for f in admitted if f["concept"] == "current_ratio")
    assert ratio["provenance"]["validation"] == "passed"
    assert all(i["period_start"] is None for i in ratio["provenance"]["inputs"])
