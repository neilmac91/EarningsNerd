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
    accession = "0000320193-24-000079"

    facts = [
        # FY2024 (current)
        FinancialFact(
            company_id=cid, concept="revenue", raw_tag="us-gaap:Revenues", unit="USD",
            period_start=datetime.date(2023, 10, 1), period_end=datetime.date(2024, 9, 28), fiscal_year=2024, fiscal_period="FY",
            value=391035000000, form="10-K", accession=accession, is_latest=True,
        ),
        FinancialFact(
            company_id=cid, concept="gross_profit", raw_tag="us-gaap:GrossProfit", unit="USD",
            period_start=datetime.date(2023, 10, 1), period_end=datetime.date(2024, 9, 28), fiscal_year=2024, fiscal_period="FY",
            value=180683000000, form="10-K", accession=accession, is_latest=True,
        ),
        # FY2023 (own-filing comparative — for YoY)
        FinancialFact(
            company_id=cid, concept="revenue", raw_tag="us-gaap:Revenues", unit="USD",
            period_start=datetime.date(2022, 9, 25), period_end=datetime.date(2023, 9, 30), fiscal_year=2023, fiscal_period="FY",
            value=383285000000, form="10-K", accession=accession, is_latest=True,
        ),
    ]
    db.add_all(facts)
    db.commit()
    db.close()
    try:
        yield cid, accession
    finally:
        db = SessionLocal()
        db.query(FinancialFact).filter(FinancialFact.company_id == cid).delete()
        db.query(Company).filter(Company.id == cid).delete()
        db.commit()
        db.close()


@contextmanager
def _seed_rows(rows):
    """Insert a Company plus exactly `rows` (concept, start, end, value, fiscal_period) facts."""
    db = SessionLocal()
    suffix = uuid.uuid4().hex[:10]
    company = Company(cik=f"cik{suffix}", ticker=f"T{suffix[:4]}", name="Scope Co")
    db.add(company)
    db.commit()
    db.refresh(company)
    cid = company.id
    accession = "0000320193-25-000079"
    db.add_all([
        FinancialFact(
            company_id=cid, concept=concept, raw_tag=f"us-gaap:{concept}", unit="USD",
            period_start=datetime.date.fromisoformat(start),
            period_end=datetime.date.fromisoformat(end),
            fiscal_year=int(end[:4]), fiscal_period=fiscal_period, value=value,
            form="10-K", accession=accession, is_latest=True,
        )
        for concept, start, end, value, fiscal_period in rows
    ])
    db.commit()
    db.close()
    try:
        yield cid, accession
    finally:
        db = SessionLocal()
        db.query(FinancialFact).filter(FinancialFact.company_id == cid).delete()
        db.query(Company).filter(Company.id == cid).delete()
        db.commit()
        db.close()


# A three-month figure disclosed inside a 10-K: the writer derives "FY" from the FORM, so the row
# carries an annual label over a 90-day duration. Now that durations survive ingestion, a derived
# metric must refuse it rather than return an annual-looking growth rate.
_QUARTERS_LABELLED_FY = [
    ("revenue", "2024-12-29", "2025-03-29", 100.0, "FY"),
    ("revenue", "2023-12-30", "2024-03-30", 80.0, "FY"),
]


@pytest.mark.requires_db
def test_quarterly_pair_labelled_fy_never_computes_an_annual_growth_rate():
    """The blocker: two quarters wearing FY labels must not become a 25% FY growth rate."""
    with _seed_rows(_QUARTERS_LABELLED_FY) as (cid, accession):
        result = copilot_tools.run_tool(
            "compute_metric", {"kind": "yoy_growth", "concept": "revenue", "fiscal_period": "FY"},
            cid, accession_number=accession,
        )
    assert result == {"error": "basis_unavailable", "concept": "revenue"}


@pytest.mark.requires_db
def test_margin_refuses_a_quarterly_pair_labelled_fy():
    """Same contradiction on the other computed metric."""
    with _seed_rows([("net_income", "2024-12-29", "2025-03-29", 20.0, "FY"),
                     ("revenue", "2024-12-29", "2025-03-29", 100.0, "FY")]) as (cid, accession):
        result = copilot_tools.run_tool(
            "compute_metric", {"kind": "margin", "concept": "net_income"},
            cid, accession_number=accession,
        )
    assert result == {"error": "basis_unavailable", "concept": "net_income"}


@pytest.mark.requires_db
def test_legitimately_quarterly_facts_still_compute():
    """Quarterly source facts are kept and computed — they are simply not called annual."""
    with _seed_rows([("revenue", "2024-10-01", "2024-12-31", 100.0, "Q4"),
                     ("revenue", "2023-10-01", "2023-12-31", 80.0, "Q4")]) as (cid, accession):
        result = copilot_tools.run_tool(
            "compute_metric", {"kind": "yoy_growth", "concept": "revenue"},
            cid, accession_number=accession,
        )
    assert "error" not in result
    assert result["value"] == pytest.approx(0.25) and result["fiscal_period"] == "Q4"


@pytest.mark.requires_db
def test_an_operand_whose_label_contradicts_its_duration_is_refused():
    """Both operands must be self-consistent — an annual prior mislabelled Q4 backs nothing."""
    with _seed_rows([("revenue", "2024-01-01", "2024-12-31", 100.0, "FY"),
                     ("revenue", "2023-01-01", "2023-12-31", 80.0, "Q4")]) as (cid, accession):
        result = copilot_tools.run_tool(
            "compute_metric", {"kind": "yoy_growth", "concept": "revenue"},
            cid, accession_number=accession,
        )
    assert result == {"error": "basis_unavailable", "concept": "revenue"}


@pytest.mark.requires_db
def test_an_unlabelled_duration_pair_is_unaffected():
    """No label means nothing to contradict; `_has_duration` still governs, as before."""
    with _seed_rows([("revenue", "2024-01-01", "2024-12-31", 100.0, None),
                     ("revenue", "2023-01-01", "2023-12-31", 80.0, None)]) as (cid, accession):
        result = copilot_tools.run_tool(
            "compute_metric", {"kind": "yoy_growth", "concept": "revenue"},
            cid, accession_number=accession,
        )
    assert "error" not in result and result["value"] == pytest.approx(0.25)


@pytest.mark.requires_db
def test_a_direct_lookup_of_a_mislabelled_fact_is_unchanged():
    """Only COMPUTED claims are refused: the stored row is not relabelled, hidden or re-selected.

    The citation layer already refuses this fact for an annual sentence on its own duration; the
    tool still reports exactly what the filing stored, provenance intact.
    """
    with _seed_rows(_QUARTERS_LABELLED_FY) as (cid, accession):
        result = copilot_tools.run_tool(
            "get_financial_fact", {"concept": "revenue"}, cid, accession_number=accession,
        )
    assert "error" not in result
    assert result["value"] == pytest.approx(100.0)
    assert result["fiscal_period"] == "FY" and result["period_start"] == "2024-12-29"


def test_scope_windows_match_the_modules_that_own_them():
    """One annual and one quarter window repo-wide; drift in either owner must fail here."""
    from app.services.edgar.instance_extractor import DURATION_WINDOWS
    from app.services.facts_service import _CF_ANNUAL_WINDOW, _CF_QUARTER_WINDOW

    assert copilot_tools._SCOPE_DURATION_DAYS["FY"] == _CF_ANNUAL_WINDOW
    assert all(copilot_tools._SCOPE_DURATION_DAYS[q] == _CF_QUARTER_WINDOW
               for q in ("Q1", "Q2", "Q3", "Q4"))
    assert DURATION_WINDOWS["10-K"] == _CF_ANNUAL_WINDOW
    assert DURATION_WINDOWS["10-Q"] == _CF_QUARTER_WINDOW


@pytest.mark.requires_db
def test_get_financial_fact_returns_latest_with_provenance():
    """get_financial_fact (no period args) returns the most recent revenue value + raw_tag/accession."""
    with _seed_company_with_facts() as (cid, accession):
        result = copilot_tools.run_tool("get_financial_fact", {"concept": "revenue"}, cid, accession_number=accession)

    assert "error" not in result
    assert result["value"] == pytest.approx(391035000000.0)
    assert result["concept"] == "revenue"
    assert result["unit"] == "USD"
    assert result["raw_tag"] == "us-gaap:Revenues"
    assert result["accession"] == accession
    assert result["period_end"] == "2024-09-28"
    assert result["fiscal_year"] == 2024
    assert result["fiscal_period"] == "FY"


@pytest.mark.requires_db
def test_get_financial_fact_specific_year():
    """An explicit fiscal_year selects that period rather than the most recent."""
    with _seed_company_with_facts() as (cid, accession):
        result = copilot_tools.run_tool(
            "get_financial_fact", {"concept": "revenue", "fiscal_year": 2023}, cid, accession_number=accession
        )

    assert "error" not in result
    assert result["value"] == pytest.approx(383285000000.0)
    assert result["fiscal_year"] == 2023


@pytest.mark.requires_db
def test_compute_metric_yoy_growth():
    """yoy_growth computes (current - prior) / |prior| on exact values."""
    with _seed_company_with_facts() as (cid, accession):
        result = copilot_tools.run_tool(
            "compute_metric", {"kind": "yoy_growth", "concept": "revenue"}, cid, accession_number=accession
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
    with _seed_company_with_facts() as (cid, accession):
        result = copilot_tools.run_tool(
            "compute_metric", {"kind": "margin", "concept": "gross_profit"}, cid, accession_number=accession
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
    with _seed_company_with_facts() as (cid, accession):
        result = copilot_tools.run_tool(
            "get_financial_fact", {"concept": "free_cash_flow"}, cid, accession_number=accession
        )

    assert result["error"] == "not_disclosed"
    assert "available_concepts" in result
    assert set(result["available_concepts"]) == {"revenue", "gross_profit"}


@pytest.mark.requires_db
def test_list_available_concepts():
    """list_available_concepts reports the distinct concepts + fiscal periods for the company."""
    with _seed_company_with_facts() as (cid, accession):
        result = copilot_tools.run_tool("list_available_concepts", {}, cid, accession_number=accession)

    assert set(result["concepts"]) == {"revenue", "gross_profit"}
    assert result["fiscal_periods"] == ["FY"]


@pytest.mark.requires_db
def test_fact_to_citation_shape():
    """fact_to_citation renders the existing citation shape with an ``XBRL ·`` section_ref."""
    with _seed_company_with_facts() as (cid, accession):
        fact = copilot_tools.run_tool("get_financial_fact", {"concept": "revenue"}, cid, accession_number=accession)

    cite = copilot_tools.fact_to_citation(fact)
    assert cite["verified"] is True
    assert cite["section_ref"] == "XBRL · us-gaap:Revenues"
    assert "Revenue" in cite["excerpt"]
    assert "FY2024/FY" in cite["excerpt"]
    assert cite["fragment_url"] is None
