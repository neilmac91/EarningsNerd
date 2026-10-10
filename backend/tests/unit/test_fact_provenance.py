"""Publication policy and source lineage survive legacy and calculated facts."""

from copy import deepcopy
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.services import copilot_tools
from app.services.fact_provenance import (
    calculated_provenance,
    provenance_for_fact,
    published_value,
)
from app.utils.sec_urls import build_sec_archive_url


def _fact(**changes):
    return {
        "concept": "revenue", "value": Decimal("42000000000"), "unit": "USD",
        "period_start": date(2024, 1, 1), "period_end": date(2024, 12, 31),
        "accession": "0001326801-25-000010", "raw_tag": "us-gaap:Revenues",
        "fiscal_year": 2024, "fiscal_period": "FY",
        "filed_at": "2025-01-30", "source": "companyfacts", "reconciled": True,
        "provenance": None, **changes,
    }


@pytest.mark.parametrize("concept", ["eps_basic", "earnings_per_share", "eps_diluted"])
@pytest.mark.parametrize("stored_pass", [False, True])
def test_legacy_derived_eps_never_becomes_publishable_from_a_pass_flag(concept, stored_pass):
    fact = _fact(concept=concept, unit="USD/shares", value=Decimal("7.95"), source="derived")
    if stored_pass:
        fact["provenance"] = {
            "version": 1, "method": "calculated", "validation": "passed",
            "formula": "legacy weighted-share estimate", "inputs": [], "reasons": [],
        }
    assert published_value(fact) is None
    provenance = provenance_for_fact(fact)
    assert provenance["validation"] == "unavailable"
    assert provenance["reasons"] == ["unsupported_eps_calculation"]


@pytest.mark.parametrize("concept", ["eps_basic", "earnings_per_share", "eps_diluted"])
def test_reported_eps_remains_available(concept):
    fact = _fact(concept=concept, unit="USD/shares", value=Decimal("8.02"))
    assert published_value(fact) == 8.02
    assert provenance_for_fact(fact)["method"] == "reported"


@pytest.mark.parametrize("fields", [
    {"source": "derived"},
    {"source": "edgar_xbrl", "concept": "free_cash_flow", "raw_tag": None},
    {"source": "edgar_xbrl", "concept": "net_margin", "raw_tag": "net_margin"},
])
def test_legacy_calculation_needs_evidence_even_if_old_boolean_passed(fields):
    fact = _fact(reconciled=True, **fields)
    provenance = provenance_for_fact(fact)
    assert provenance["method"] == "calculated"
    assert provenance["validation"] == "needs_review"
    assert provenance["reasons"] == ["legacy_calculation"]
    assert provenance["inputs"] == []


def test_calculation_lineage_links_each_real_operand_without_mutating_storage():
    annual = _fact()
    nine_months = _fact(
        value=Decimal("30000000000"), period_end=date(2024, 9, 30),
        accession="0001326801-24-000091", filed_at="2024-10-31",
    )
    quarter = _fact(
        source="derived", value=Decimal("12000000000"),
        period_start=date(2024, 10, 1),
        provenance=calculated_provenance("FY - YTD9", [annual, nine_months]),
    )
    quarter["provenance"]["period_calculation"] = True
    nested = _fact(
        concept="free_cash_flow", source="derived",
        provenance=calculated_provenance("operating_cash_flow - capex", [quarter, _fact(value=5)]),
    )
    before = deepcopy(nested)
    projected = provenance_for_fact(nested, "0001326801")
    assert projected["validation"] == "passed"
    assert projected["method"] == "calculated"
    assert projected["period_calculation"] is True
    assert "source_url" not in projected  # A computed value is not a reported filing row.
    inputs = projected["inputs"][0]["provenance"]["inputs"]
    assert [item["value"] for item in inputs] == [42_000_000_000, 30_000_000_000]
    assert [item["period_end"] for item in inputs] == ["2024-12-31", "2024-09-30"]
    assert [item["source_url"] for item in inputs] == [
        build_sec_archive_url("1326801", item["accession"]) for item in inputs
    ]
    assert projected["filed_at"] == "2025-01-30"
    assert nested == before


@pytest.mark.parametrize("state", ["needs_review", "unavailable"])
def test_operand_status_and_reason_survive_calculation(state):
    prior = _fact(provenance={
        "version": 1, "method": "reported", "validation": state,
        "reasons": ["incompatible_vintages"], "inputs": [],
    })
    result = calculated_provenance("current - prior", [_fact(), prior])
    assert result["validation"] == state
    assert result["reasons"] == ["incompatible_vintages"]
    assert result["inputs"][1]["provenance"]["validation"] == state


def test_invalid_legacy_identity_does_not_fabricate_a_filing_link():
    result = provenance_for_fact(_fact(accession="synthetic-quarter"), "1326801")
    assert "source_url" not in result


def test_copilot_reported_fact_preserves_review_status_for_its_consumer():
    admitted = SimpleNamespace(**_fact())
    assert copilot_tools._select_fact([admitted], "USD") is admitted
    ambiguous = SimpleNamespace(**_fact(reconciled=False))
    assert copilot_tools._select_fact([ambiguous], "USD") is ambiguous
    result = copilot_tools._fact_provenance(ambiguous)
    assert result["provenance"]["validation"] == "needs_review"
    assert result["provenance"]["reasons"] == ["source_check_needed"]


def test_copilot_rejects_legacy_eps_before_it_can_become_a_numeric_citation():
    fact = SimpleNamespace(**_fact(concept="eps_basic", source="derived", unit="USD/shares"))
    with pytest.raises(copilot_tools._Unavailable, match="unsupported_calculation"):
        copilot_tools._select_fact([fact], "USD")


@pytest.mark.parametrize("same_accession", [False, True])
def test_copilot_calculation_operands_must_belong_to_the_viewed_filing(same_accession):
    annual = _fact()
    earlier = _fact(value=30_000_000_000, accession=(
        annual["accession"] if same_accession else "0001326801-24-000091"
    ))
    quarter = _fact(source="derived", provenance=calculated_provenance("FY - YTD9", [annual, earlier]))
    nested = SimpleNamespace(**_fact(
        concept="free_cash_flow", source="derived",
        provenance=calculated_provenance("operating_cash_flow - capex", [quarter, _fact(value=5)]),
    ))
    if same_accession:
        assert copilot_tools._select_fact([nested], "USD") is nested
    else:
        with pytest.raises(copilot_tools._Unavailable, match="cross_filing_calculation"):
            copilot_tools._select_fact([nested], "USD")
