"""Tests for the Copilot's numeric XBRL tool-use (P5).

These exercise :mod:`app.services.copilot_tools` end to end against the app's default SQLite database:
seed a ``Company`` plus a few ``FinancialFact`` rows, then drive ``run_tool`` (which opens its OWN
``SessionLocal`` per call — the same isolation the SSE generator relies on) and assert the exact
values + provenance come back. ``compute_metric`` arithmetic (YoY growth, margin) is checked against
the seeded numbers, and an absent concept is asserted to return the ``not_disclosed`` error shape with
``available_concepts``.

Marked ``requires_db`` and run against the SQLite db where the ``financial_fact`` table already
exists (no new columns are added by P5, so no ALTER is needed).
"""
import datetime
import uuid
from contextlib import contextmanager

import pytest

from app.database import SessionLocal
from app.models import Company
from app.models.financial_fact import FinancialFact
from app.services import copilot_tools


@contextmanager
def _seed_company_with_facts():
    """Insert a Company + two fiscal years of revenue/gross_profit facts; yield the company id."""
    db = SessionLocal()
    suffix = uuid.uuid4().hex[:10]
    company = Company(cik=f"cik{suffix}", ticker=f"T{suffix[:4]}", name="Test Co")
    db.add(company)
    db.commit()
    db.refresh(company)
    cid = company.id

    facts = [
        # FY2024 (current)
        FinancialFact(
            company_id=cid, concept="revenue", raw_tag="us-gaap:Revenues", unit="USD",
            period_end=datetime.date(2024, 9, 28), fiscal_year=2024, fiscal_period="FY",
            value=391035000000, form="10-K", accession=f"acc-{suffix}-2024", is_latest=True,
        ),
        FinancialFact(
            company_id=cid, concept="gross_profit", raw_tag="us-gaap:GrossProfit", unit="USD",
            period_end=datetime.date(2024, 9, 28), fiscal_year=2024, fiscal_period="FY",
            value=180683000000, form="10-K", accession=f"acc-{suffix}-2024", is_latest=True,
        ),
        # FY2023 (prior year — for YoY)
        FinancialFact(
            company_id=cid, concept="revenue", raw_tag="us-gaap:Revenues", unit="USD",
            period_end=datetime.date(2023, 9, 30), fiscal_year=2023, fiscal_period="FY",
            value=383285000000, form="10-K", accession=f"acc-{suffix}-2023", is_latest=True,
        ),
    ]
    db.add_all(facts)
    db.commit()
    db.close()
    try:
        yield cid
    finally:
        db = SessionLocal()
        db.query(FinancialFact).filter(FinancialFact.company_id == cid).delete()
        db.query(Company).filter(Company.id == cid).delete()
        db.commit()
        db.close()


@pytest.mark.requires_db
def test_get_financial_fact_returns_latest_with_provenance():
    """get_financial_fact (no period args) returns the most recent revenue value + raw_tag/accession."""
    with _seed_company_with_facts() as cid:
        result = copilot_tools.run_tool("get_financial_fact", {"concept": "revenue"}, cid)

    assert "error" not in result
    assert result["value"] == pytest.approx(391035000000.0)
    assert result["concept"] == "revenue"
    assert result["unit"] == "USD"
    assert result["raw_tag"] == "us-gaap:Revenues"
    assert result["accession"].endswith("-2024")
    assert result["period_end"] == "2024-09-28"
    assert result["fiscal_year"] == 2024
    assert result["fiscal_period"] == "FY"


@pytest.mark.requires_db
def test_get_financial_fact_specific_year():
    """An explicit fiscal_year selects that period rather than the most recent."""
    with _seed_company_with_facts() as cid:
        result = copilot_tools.run_tool(
            "get_financial_fact", {"concept": "revenue", "fiscal_year": 2023}, cid
        )

    assert "error" not in result
    assert result["value"] == pytest.approx(383285000000.0)
    assert result["fiscal_year"] == 2023


@pytest.mark.requires_db
def test_compute_metric_yoy_growth():
    """yoy_growth computes (current - prior) / |prior| on exact values."""
    with _seed_company_with_facts() as cid:
        result = copilot_tools.run_tool(
            "compute_metric", {"kind": "yoy_growth", "concept": "revenue"}, cid
        )

    assert "error" not in result
    assert result["kind"] == "yoy_growth"
    expected = (391035000000.0 - 383285000000.0) / 383285000000.0
    assert result["value"] == pytest.approx(expected)
    assert result["current_value"] == pytest.approx(391035000000.0)
    assert result["prior_value"] == pytest.approx(383285000000.0)
    assert result["unit"] == "pure"


@pytest.mark.requires_db
def test_compute_metric_margin():
    """margin computes numerator/denominator (gross_profit / revenue) for the matched period."""
    with _seed_company_with_facts() as cid:
        result = copilot_tools.run_tool(
            "compute_metric", {"kind": "margin", "concept": "gross_profit"}, cid
        )

    assert "error" not in result
    assert result["kind"] == "margin"
    expected = 180683000000.0 / 391035000000.0
    assert result["value"] == pytest.approx(expected)
    assert result["denominator_concept"] == "revenue"
    assert result["unit"] == "pure"


@pytest.mark.requires_db
def test_unknown_concept_returns_not_disclosed_with_available():
    """An absent concept returns the not_disclosed error shape listing available concepts."""
    with _seed_company_with_facts() as cid:
        result = copilot_tools.run_tool(
            "get_financial_fact", {"concept": "free_cash_flow"}, cid
        )

    assert result["error"] == "not_disclosed"
    assert "available_concepts" in result
    assert set(result["available_concepts"]) == {"revenue", "gross_profit"}


@pytest.mark.requires_db
def test_list_available_concepts():
    """list_available_concepts reports the distinct concepts + fiscal periods for the company."""
    with _seed_company_with_facts() as cid:
        result = copilot_tools.run_tool("list_available_concepts", {}, cid)

    assert set(result["concepts"]) == {"revenue", "gross_profit"}
    assert result["fiscal_periods"] == ["FY"]


@pytest.mark.requires_db
def test_fact_to_citation_shape():
    """fact_to_citation renders the existing citation shape with an ``XBRL ·`` section_ref."""
    with _seed_company_with_facts() as cid:
        fact = copilot_tools.run_tool("get_financial_fact", {"concept": "revenue"}, cid)

    cite = copilot_tools.fact_to_citation(fact)
    assert cite["verified"] is True
    assert cite["section_ref"] == "XBRL · us-gaap:Revenues"
    assert "Revenue" in cite["excerpt"]
    assert "FY2024/FY" in cite["excerpt"]
    assert cite["fragment_url"] is None
