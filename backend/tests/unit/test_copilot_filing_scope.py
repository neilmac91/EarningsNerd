"""Actual ORM tool queries must retain the viewed filing, native unit and source basis."""
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Company
from app.models.financial_fact import FinancialFact
from app.services import copilot_tools as tools

OLD = "0001577552-25-000001"
NEW = "0001577552-26-000002"


@pytest.fixture
def facts(monkeypatch):
    engine = create_engine("sqlite://", poolclass=StaticPool)
    Company.__table__.create(engine)
    FinancialFact.__table__.create(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(tools, "SessionLocal", factory)
    with factory() as db:
        db.add_all([Company(id=1, cik="1577552", ticker="BABA", name="Viewed"), Company(id=2, cik="7", ticker="OTHER", name="Other")])
        db.commit()

    def seed(concept="revenue", value=100, **overrides):
        values = dict(company_id=1, concept=concept, value=value, unit="CNY", accession=OLD,
                      raw_tag=f"ifrs:{concept}", period_start=date(2024, 4, 1),
                      period_end=date(2025, 3, 31), fiscal_year=2025, fiscal_period="FY", is_latest=False)
        values.update(overrides)
        with factory() as db:
            db.add(FinancialFact(**values))
            db.commit()
    yield seed
    engine.dispose()


def call(name="get_financial_fact", currency="CNY", **args):
    return tools.run_tool(name, args, 1, accession_number=OLD, reporting_currency=currency)


def test_all_discovery_and_direct_paths_stay_in_viewed_company_accession(facts):
    facts()
    facts(value=999, accession=NEW, is_latest=True)
    facts(value=888, company_id=2, is_latest=True)
    facts("future_only", accession=NEW, fiscal_period="Q1")
    facts("other_only", company_id=2, fiscal_period="Q2")
    facts(value=80, period_start=date(2023, 4, 1), period_end=date(2024, 3, 31), fiscal_year=2024)
    result = call(concept="revenue", accession_number=NEW, reporting_currency="USD")
    assert result["value"] == 100
    assert result["accession"] == OLD
    assert result["period_start"] == "2024-04-01"
    assert call(concept="revenue", fiscal_year=2024, fiscal_period="FY")["value"] == 80
    assert call("list_available_concepts") == {"concepts": ["revenue"], "fiscal_periods": ["FY"]}
    assert call(concept="absent") == {"error": "not_disclosed", "available_concepts": ["revenue"]}
    assert call() == {"error": "missing_concept", "available_concepts": ["revenue"]}


@pytest.mark.parametrize("scope", [None, "", "not-an-accession", "000157755225000001"])
def test_missing_scope_never_opens_db(monkeypatch, scope):
    opened = []
    monkeypatch.setattr(tools, "SessionLocal", lambda: opened.append(True))
    assert tools.run_tool("list_available_concepts", {}, 1, accession_number=scope) == {"error": "filing_scope_unavailable"}
    assert opened == []


@pytest.mark.parametrize("unit,canonical", [("RMB", "CNY"), ("USD_per_share", "USD/shares"),
                                           ("EUR/share", "EUR/shares"), ("shares", "shares"), ("pure", "pure")])
def test_unit_aliases_preserve_dimensions_and_direct_provenance(facts, unit, canonical):
    facts(unit=unit, period_start=None)
    result = call(currency=None, concept="revenue")
    assert result["unit"] == canonical
    assert result["value"] == 100
    cite = tools.fact_to_citation(result)
    assert cite["unit"] == canonical
    assert canonical in cite["excerpt"]
    assert {k: cite[k] for k in ("accession", "period_start", "period_end", "fiscal_year", "fiscal_period", "raw_tag")} == {
        "accession": OLD, "period_start": None, "period_end": "2025-03-31", "fiscal_year": 2025,
        "fiscal_period": "FY", "raw_tag": "ifrs:revenue",
    }


def test_native_currency_selects_source_not_convenience_translation(facts):
    facts(unit="USD", value=14)
    facts(unit="RMB", value=100)
    assert call(concept="revenue")["value"] == 100
    assert call(concept="revenue")["unit"] == "CNY"
    assert call(currency=None, concept="revenue") == {"error": "ambiguous_fact"}
    assert call(currency="EUR", concept="revenue")["error"] == "not_disclosed"


def test_multiple_period_bases_are_ambiguous_even_in_one_currency(facts):
    facts()
    facts(value=30, fiscal_period="Q4", period_start=date(2025, 1, 1))
    assert call(concept="revenue") == {"error": "ambiguous_fact"}
    assert call(concept="revenue", fiscal_period="Q4")["value"] == 30


@pytest.mark.parametrize("kind", ["margin", "yoy_growth"])
def test_no_invented_duration_from_fy_label(facts, kind):
    facts("gross_profit", 40, period_start=None)
    facts(period_start=None)
    assert call("compute_metric", kind=kind, concept="gross_profit") == {"error": "basis_unavailable", "concept": "gross_profit"}
    assert call(concept="revenue")["value"] == 100


def test_margin_scope_compatible_basis_and_full_operand_citation(facts):
    facts("gross_profit", 40)
    facts()
    facts(value=999, accession=NEW, is_latest=True)
    facts(value=888, company_id=2)
    result = call("compute_metric", kind="margin", concept="gross_profit")
    assert result["value"] == .4
    assert result["denominator_concept"] == "revenue"
    assert result["unit"] == "pure"
    assert [(r["concept"], r["value"], r["accession"], r["unit"], r["period_start"], r["period_end"])
            for r in result["source_facts"]] == [
        ("gross_profit", 40, OLD, "CNY", "2024-04-01", "2025-03-31"),
        ("revenue", 100, OLD, "CNY", "2024-04-01", "2025-03-31"),
    ]
    cite = tools.fact_to_citation(result)
    assert cite["source_facts"] == result["source_facts"]
    assert cite["denominator_concept"] == "revenue"
    assert "40.0%" in cite["excerpt"]


@pytest.mark.parametrize("denominator,error", [
    ({"accession": NEW}, "denominator_not_disclosed"),
    ({"company_id": 2}, "denominator_not_disclosed"),
    ({"period_end": date(2024, 3, 31)}, "denominator_not_disclosed"),
    ({"period_start": None}, "basis_unavailable"),
    ({"period_start": date(2025, 1, 1)}, "basis_unavailable"),
    ({"unit": "USD"}, "incompatible_units"),
    ({"value": 0}, "denominator_zero"),
])
def test_margin_rejects_missing_or_incompatible_operand(facts, denominator, error):
    facts("gross_profit", 40)
    facts(**denominator)
    assert call("compute_metric", currency=None, kind="margin", concept="gross_profit")["error"] == error


def test_yoy_uses_own_comparative_not_latest_or_quarter(facts):
    facts(value=100)
    facts(value=80, period_start=date(2023, 4, 1), period_end=date(2024, 3, 31), fiscal_year=2024)
    facts(value=20, period_start=date(2024, 4, 1), period_end=date(2024, 6, 30), fiscal_year=2024, fiscal_period="Q1")
    facts(value=999, period_start=date(2023, 4, 1), period_end=date(2024, 3, 31), fiscal_year=2024, accession=NEW)
    result = call("compute_metric", kind="yoy_growth", concept="revenue")
    assert result["value"] == .25
    assert result["prior_value"] == 80
    assert result["prior_period_end"] == "2024-03-31"
    assert [r["accession"] for r in result["source_facts"]] == [OLD, OLD]
    assert tools.fact_to_citation(result)["source_facts"] == result["source_facts"]
    assert "25.0%" in tools.fact_to_citation(result)["excerpt"]


@pytest.mark.parametrize("prior,error", [
    ({"accession": NEW}, "no_prior_period"),
    ({"company_id": 2}, "no_prior_period"),
    ({"period_start": None}, "basis_unavailable"),
    ({"period_start": date(2024, 1, 1)}, "no_prior_period"),
    ({"period_start": date(2024, 4, 1), "period_end": date(2024, 6, 30)}, "no_prior_period"),
    ({"unit": "USD"}, "incompatible_units"),
    ({"value": 0}, "prior_period_zero"),
])
def test_yoy_rejects_unproven_or_foreign_prior(facts, prior, error):
    facts()
    row = dict(value=80, period_start=date(2023, 4, 1), period_end=date(2024, 3, 31), fiscal_year=2024)
    row.update(prior)
    facts(**row)
    assert call("compute_metric", currency=None, kind="yoy_growth", concept="revenue")["error"] == error


def test_yoy_52_53_week_source_windows_work_with_negative_prior(facts):
    facts(value=-50, period_start=date(2023, 10, 1), period_end=date(2024, 9, 28), fiscal_year=None)
    facts(value=-100, period_start=date(2022, 9, 25), period_end=date(2023, 9, 30), fiscal_year=None)
    assert call("compute_metric", kind="yoy_growth", concept="revenue")["value"] == .5


def test_session_failure_is_sanitized_and_success_session_closes(monkeypatch):
    class Broken:
        closed = False

        def query(self, *_):
            raise RuntimeError("secret database endpoint")

        def close(self):
            self.closed = True

    db = Broken()
    monkeypatch.setattr(tools, "SessionLocal", lambda: db)
    assert call(concept="revenue") == {"error": "tool_failed"}
    assert db.closed
