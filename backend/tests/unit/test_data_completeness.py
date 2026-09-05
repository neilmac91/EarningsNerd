"""WS-7 periods, amendment identity, persisted XBRL, and complete quality provenance."""
import asyncio
from datetime import date, datetime, timezone
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pandas as pd
import pytest
from openpyxl import load_workbook
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from app import database
from app.models import Base, Company, Filing, FinancialFact
from app.services import facts_service, filing_amendment_service as amendments
from app.services import trend_analysis_service as analysis
from app.services.edgar import xbrl_service as xbrl
from app.services.edgar.fiscal_periods import fiscal_label


@pytest.fixture
def sessions(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'complete.sqlite'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(database, "SessionLocal", factory)
    yield factory
    engine.dispose()


def filing(db, company, acc, form, end, filed):
    row = Filing(company_id=company.id, accession_number=acc, filing_type=form,
                 period_end_date=datetime.fromisoformat(end).replace(tzinfo=timezone.utc) if end else None,
                 filing_date=datetime.fromisoformat(filed).replace(tzinfo=timezone.utc),
                 sec_url=f"https://www.sec.gov/Archives/edgar/data/1/{(acc if acc.isdigit() else '1').zfill(18)}/",
                 document_url=f"https://www.sec.gov/Archives/edgar/data/1/{(acc if acc.isdigit() else '1').zfill(18)}/filing.htm")
    db.add(row)
    db.flush()
    return row


@pytest.mark.parametrize("end,anchor,fy,fp,expected", [
    ("2025-10-31", "2025-10-31", 2026, "Q3", {"fiscal_year": 2026, "fiscal_period": "Q3"}),
    ("2024-10-31", "2025-10-31", 2026, "Q3", {"fiscal_year": 2025, "fiscal_period": "Q3"}),
    ("2025-01-31", "2025-10-31", 2026, "Q3", {"fiscal_year": 2025, "fiscal_period": "Q4"}),
    ("2025-09-01", "2025-10-31", 2026, "Q3", {}),
    ("2025-10-31", "2025-10-31", None, "Q3", {}),
])
def test_fiscal_period_uses_filing_anchor_and_comparative_distance(end, anchor, fy, fp, expected):
    assert fiscal_label(end, anchor, fy, fp) == expected


class Facts:
    def __init__(self, frames):
        self.frames = frames
        self.selected = None

    def query(self):
        return self

    def by_concept(self, concept, exact=True):
        self.selected = self.frames.get(concept.split(":")[-1], pd.DataFrame())
        return self

    def to_dataframe(self):
        return self.selected


def test_instance_to_facts_keeps_quarters_currency_and_raw_precision(monkeypatch):
    rows = [
        {"is_dimensioned": False, "period_start": "2025-08-01", "period_end": "2025-10-31",
         "numeric_value": 28_123_456_789, "decimals": -3, "currency": "CNY"},
        {"is_dimensioned": False, "period_start": "2024-08-01", "period_end": "2024-10-31",
         "numeric_value": 24_123_456_789, "decimals": -3, "currency": "CNY"},
    ]
    xb = SimpleNamespace(facts=Facts({"Revenues": pd.DataFrame(rows),
        "EarningsPerShareBasic": pd.DataFrame([{**r, "numeric_value": 1.2345, "currency": None, "decimals": 4} for r in rows])}),
                         entity_info={"fiscal_year": 2026, "fiscal_period": "Q3"})
    sec_filing = SimpleNamespace(form="10-Q", period_of_report="2025-10-31", xbrl=lambda: xb)
    monkeypatch.setattr(xbrl, "resolve_filing_by_accession", lambda *args: (SimpleNamespace(sic=None), [sec_filing]))
    raw = xbrl._extract_from_filing_instance_sync("0000000001", "acc")
    standardized = xbrl.edgar_xbrl_service.extract_standardized_metrics(raw)
    facts = facts_service.normalize_standardized_to_facts(1, 1, "acc", "10-Q", standardized)
    revenue = [f for f in facts if f["concept"] == "revenue"]
    eps = [f for f in facts if f["concept"] == "earnings_per_share"]
    assert eps and all(f["unit"] == "CNY/shares" and f["value"] == 1.2345 for f in eps)
    assert [(f["fiscal_year"], f["fiscal_period"], f["unit"], f["value"]) for f in revenue] == [
        (2026, "Q3", "CNY", 28_123_456_789), (2025, "Q3", "CNY", 24_123_456_789),
    ]


def test_statement_values_are_raw_units_not_decimals_scaled():
    from app.services.edgar.instance_extractor import extract_financial_statement_metrics
    frame = pd.DataFrame([
        {"concept": "us-gaap_InterestIncomeExpenseNet", "2025-12-31 (FY)": 28_123_456_789,
         "unit": "USD", "decimals": -6},
        {"concept": "us-gaap_NoninterestIncome", "2025-12-31 (FY)": 13_123_456_789,
         "unit": "USD", "decimals": -6},
    ])
    statement = SimpleNamespace(to_dataframe=lambda **kwargs: frame)
    xb = SimpleNamespace(statements=SimpleNamespace(income_statement=lambda: statement))
    profile, metrics, _ = extract_financial_statement_metrics(xb, None, "6021", "10-K", "2025-12-31")
    assert profile == "bank"
    assert metrics["net_interest_income"][0] == [("2025-12-31", 28_123_456_789)]
    assert metrics["noninterest_income"][0] == [("2025-12-31", 13_123_456_789)]


def test_persisted_xbrl_precedes_both_caches_and_is_cik_scoped(sessions, monkeypatch):
    snapshot = {"revenue": [{"period": "2025-12-31", "value": 123}]}
    with sessions() as db:
        co = Company(cik="0000000001", ticker="A", name="A")
        db.add(co)
        db.flush()
        row = filing(db, co, "acc", "10-K", "2025-12-31", "2026-02-01")
        row.xbrl_data = snapshot
        db.commit()
    svc = xbrl.EdgarXBRLService()
    redis = AsyncMock(return_value={"wrong": True})
    live = AsyncMock(return_value={"live": True})
    monkeypatch.setattr(svc, "_get_from_redis", redis)
    monkeypatch.setattr(svc, "_fetch_xbrl_data", live)
    assert asyncio.run(svc.get_xbrl_data("acc", "1")) == snapshot
    redis.assert_not_awaited()
    live.assert_not_awaited()
    assert svc._persisted_xbrl("acc", "2") is None
    assert svc._persisted_xbrl("other", "1") is None
    with sessions() as db:
        db.query(Filing).one().xbrl_data = {"segments": [{"name": "metadata only"}]}
        db.commit()
    assert svc._persisted_xbrl("acc", "1") is None


def test_companyfacts_populates_balance_sheet_and_quarter_metadata():
    def point(value, **more):
        return {"end": "2025-10-31", "val": value, "accn": "acc", "form": "10-Q", "fy": 2026, "fp": "Q3", **more}
    raw = {"facts": {"us-gaap": {
        "Liabilities": {"units": {"USD": [point(200)]}},
        "CashAndCashEquivalentsAtCarryingValue": {"units": {"USD": [point(30)]}},
        "Revenues": {"units": {"USD": [point(90, start="2025-08-01"), point(250, start="2025-02-01")]}}
    }}}
    result = xbrl.edgar_xbrl_service._parse_company_facts(raw, "acc")
    assert result["total_liabilities"][0]["value"] == 200
    assert result["cash_and_equivalents"][0]["value"] == 30
    assert result["revenue"][0]["value"] == 90
    assert result["revenue"][0]["fiscal_period"] == "Q3"
    assert result["revenue"][0]["fiscal_year"] == 2026
    standardized = xbrl.edgar_xbrl_service.extract_standardized_metrics(result)
    assert standardized["total_liabilities"]["current"]["value"] == 200


def test_amendments_link_both_ingestion_orders_and_compare_prior_period(sessions):
    from app.services.change_report_service import build_change_report
    from app.routers.filings import FilingResponse
    with sessions() as db:
        co = Company(cik="1", ticker="A", name="A")
        db.add(co)
        db.flush()
        amended = filing(db, co, "003", "10-K/A", "2024-12-31", "2025-04-01")
        original = filing(db, co, "002", "10-K", "2024-12-31", "2025-02-01")
        old = filing(db, co, "001", "10-K/A", "2023-12-31", "2025-05-01")
        current = filing(db, co, "004", "10-K", "2025-12-31", "2026-02-01")
        unknown = filing(db, co, "005", "10-K/A", None, "2026-03-01")
        amendments.mark_superseded_filings(db, co.id)
        db.commit()
        assert original.superseded_by_accession == amended.accession_number
        assert current.superseded_by_accession is None and unknown.superseded_by_accession is None
        assert FilingResponse.from_orm(original).superseded_by_accession == "003"
        assert build_change_report(db, current)["prior_filing"]["filing_id"] == amended.id
        assert build_change_report(db, amended)["prior_filing"] is None  # older year's late amendment was not yet filed
        newer = filing(db, co, "006", "10-K/A", "2024-12-31", "2025-06-01")
        amendments.mark_superseded_filings(db, co.id)
        db.commit()
        assert original.superseded_by_accession == newer.accession_number
        assert amended.superseded_by_accession == newer.accession_number
        assert old.superseded_by_accession is None
        assert build_change_report(db, current)["prior_filing"]["filing_id"] == newer.id
    assert amendments.expand_amendment_forms(["10-K", "10-Q", "8-K"]) == ["10-K", "10-Q", "8-K", "10-K/A", "10-Q/A"]
    assert amendments.expand_amendment_forms(["10-Q/A"]) == ["10-Q/A"]


def test_amendment_schema_has_guard_and_startup_healing(sessions):
    assert "superseded_by_accession" in {c["name"] for c in inspect(sessions.kw["bind"]).get_columns("filings")}
    assert ("filings", "superseded_by_accession", "TEXT") in database._ADDITIVE_COLUMNS
    sql = (Path(__file__).parents[2] / "migrations/20260905_filing_amendment_relationship.sql").read_text()
    assert "IF NOT EXISTS" in sql and "information_schema.columns" in sql
    assert "ADD COLUMN superseded_by_accession TEXT" in sql


def test_growth_citations_and_excel_keep_input_reconciliation(sessions):
    from app.services.excel_export_service import build_analysis_workbook
    with sessions() as db:
        co = Company(cik="1", ticker="A", name="A")
        db.add(co)
        db.flush()
        for year, value, quality in [(2024, 100, False), (2025, 120, True)]:
            db.add(FinancialFact(company_id=co.id, concept="revenue", raw_tag="us-gaap:Revenues",
                unit="USD", period_end=date(year, 12, 31), fiscal_year=year, fiscal_period="FY",
                value=value, form="10-K", accession=str(year), source="companyfacts",
                reconciled=quality, is_latest=True))
        db.commit()
        dataset = analysis.build_dataset(db, co, "annual", "FY2024", "FY2025")
    series = dataset["series"][0]
    assert series["points"][1]["reconciled"] is True
    assert series["points"][1]["yoy_reconciled"] is False
    assert series["cagr_reconciled"] is False
    index = analysis.marker_index(dataset)
    citations = analysis.resolve_narrative_citations("Revenue [F1]. Growth [F3].", index)[1]
    assert all(c["reconciled"] is False and c["verified"] for c in citations)
    wb = load_workbook(BytesIO(build_analysis_workbook(dataset)))
    assert "Unreconciled" in wb["Metrics"]["D2"].comment.text
    assert "unreconciled" in wb["Metrics"]["F2"].comment.text
    assert "unreconciled" in wb["Revenue & growth"]["C3"].comment.text


def test_universe_seed_previews_then_is_idempotent_without_generation(sessions, monkeypatch):
    from app.services import universe_seed_service as seed
    monkeypatch.setattr(seed, "SessionLocal", sessions)
    monkeypatch.setattr(seed, "member_tickers", lambda: frozenset({"A", "B", "B.B", "MISSING"}))
    ticker_file = {"0": {"cik_str": 1, "ticker": "A", "title": "A"},
                   "1": {"cik_str": 2, "ticker": "B", "title": "B"},
                   "2": {"cik_str": 2, "ticker": "B-B", "title": "B class B"}}
    monkeypatch.setattr(seed.sec_edgar_service, "get_company_tickers", AsyncMock(return_value=ticker_file))
    preview = asyncio.run(seed.seed_universe_companies())
    with sessions() as db:
        assert db.query(Company).count() == 0
    assert preview["would_create"] == 2 and preview["source_errors"] == 1
    applied = asyncio.run(seed.seed_universe_companies(apply=True))
    assert applied["created"] == 2 and applied["unresolved_tickers"] == ["MISSING"]
    again = asyncio.run(seed.seed_universe_companies(apply=True))
    assert again["created"] == 0 and again["existing"] == 3
    with sessions() as db:
        assert {c.ticker for c in db.query(Company)} == {"A", "B"}


@pytest.mark.parametrize("mode,concept,unit,quality_key", [
    ("quarterly", "revenue", "USD", "qoq_reconciled"),
    ("annual", "net_margin", "pure", "window_pp_reconciled"),
])
def test_computed_quality_uses_earlier_input(sessions, mode, concept, unit, quality_key):
    with sessions() as db:
        co = Company(cik="1", ticker="A", name="A")
        db.add(co)
        db.flush()
        for i, quality in enumerate((False, True)):
            year = 2024 + i if mode == "annual" else 2025
            fp = "FY" if mode == "annual" else f"Q{i+1}"
            end = date(year, 12, 31) if mode == "annual" else date(year, 3+3*i, 31 if i == 0 else 30)
            db.add(FinancialFact(company_id=co.id, concept=concept, unit=unit, period_end=end,
                fiscal_year=year, fiscal_period=fp, value=10+2*i, form="10-K" if fp == "FY" else "10-Q",
                accession=str(i), source="companyfacts", reconciled=quality, is_latest=True))
        db.commit()
        keys = ("FY2024", "FY2025") if mode == "annual" else ("2025Q1", "2025Q2")
        series = analysis.build_dataset(db, co, mode, *keys)["series"][0]
        result = series if mode == "annual" else series["points"][-1]
        assert result[quality_key] is False


def test_labelled_quarter_demotes_legacy_null_period(sessions):
    with sessions() as db:
        co = Company(cik="1", ticker="A", name="A")
        db.add(co)
        db.flush()
        common = {"company_id": co.id, "filing_id": None, "concept": "revenue", "unit": "USD",
                  "period_end": date(2025, 10, 31), "fiscal_year": 2026, "value": 123,
                  "form": "10-Q", "accession": "acc", "source": "edgar_xbrl"}
        facts_service.upsert_facts(db, [{**common, "fiscal_period": None}])
        facts_service.upsert_facts(db, [{**common, "fiscal_period": "Q3"}])
        assert [f.fiscal_period for f in db.query(FinancialFact).filter_by(is_latest=True)] == ["Q3"]
        assert db.query(FinancialFact).filter(FinancialFact.fiscal_period.is_(None)).one().is_latest is False


def test_weekly_pregenerate_runs_quarters_and_foreign_annual(sessions, monkeypatch):
    import importlib.util
    from app.models import JobRun
    from app.services import precompute_service, job_run_service
    monkeypatch.setattr(job_run_service, "SessionLocal", sessions)
    core = AsyncMock(return_value={"ticker": "A", "filing_id": 1, "accession": "acc", "status": "generated"})
    monkeypatch.setattr(precompute_service, "precompute_one", core)
    path = Path(__file__).parents[2] / "scripts/pregenerate_examples.py"
    spec = importlib.util.spec_from_file_location("ws7_pregenerate", path)
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    asyncio.run(script.main(["AAPL", "BABA"]))
    assert [call.args for call in core.await_args_list] == [("AAPL", "10-K"), ("AAPL", "10-Q"), ("BABA", "20-F")]
    with sessions() as db:
        attempt = db.query(JobRun).one()
        assert attempt.status == "succeeded" and attempt.counters == {"generated": 3}
    workflow = (Path(__file__).parents[3] / ".github/workflows/ci.yml").read_text()
    step = workflow.split("- name: Update pregenerate job image")[1].split("- name:")[0]
    assert "ENABLE_FPI_FILINGS=true" in step


def test_older_filing_facts_never_replace_newer_amendment_or_untied_companyfacts(sessions):
    with sessions() as db:
        co = Company(cik="1", ticker="A", name="A")
        db.add(co)
        db.flush()
        original = filing(db, co, "001", "10-Q", "2025-09-30", "2025-11-01")
        amended = filing(db, co, "002", "10-Q/A", "2025-09-30", "2025-12-01")
        common = {"company_id": co.id, "concept": "revenue", "unit": "USD", "period_end": date(2025, 9, 30),
                  "fiscal_year": 2025, "fiscal_period": "Q3", "source": "edgar_xbrl"}
        facts_service.upsert_facts(db, [{**common, "filing_id": amended.id, "accession": "002", "form": "10-Q/A", "value": 200}])
        facts_service.upsert_facts(db, [{**common, "filing_id": original.id, "accession": "001", "form": "10-Q", "value": 100}])
        assert [(f.accession, f.value) for f in db.query(FinancialFact).filter_by(is_latest=True)] == [("002", 200)]
        assert db.query(FinancialFact).filter_by(filing_id=original.id).one().value == 100
        # A current companyfacts row may precede creation of its Filing row; preserve its value
        # rather than guessing date order from accession submitter IDs.
        db.add(FinancialFact(**{**common, "concept": "net_income", "source": "companyfacts"},
                            accession="unlisted", value=20, is_latest=True, reconciled=True))
        db.commit()
        facts_service.upsert_facts(db, [{**common, "concept": "net_income", "filing_id": original.id,
                                      "accession": "001", "form": "10-Q", "value": 10}])
        assert [(f.accession, f.value) for f in db.query(FinancialFact).filter_by(concept="net_income", is_latest=True)] == [("unlisted", 20)]


def test_refresh_existing_amendments_repairs_links_and_locks_company(sessions):
    from sqlalchemy import event
    from sqlalchemy.dialects import postgresql
    from app.services.filing_scan_service import upsert_filings
    statements = []
    with sessions() as db:
        event.listen(db, "do_orm_execute", lambda state: statements.append(str(state.statement.compile(dialect=postgresql.dialect()))))
        co = Company(cik="1", ticker="A", name="A")
        db.add(co)
        db.flush()
        old = filing(db, co, "001", "10-K", "2025-12-31", "2026-02-01")
        new = filing(db, co, "002", "10-K/A", "2025-12-31", "2026-03-01")
        db.commit()
        # No new rows: a metadata refresh after the additive migration still establishes links.
        upsert_filings(db, co, [{"accession_number": new.accession_number,
                                "sec_url": new.sec_url, "document_url": new.document_url}])
        assert old.superseded_by_accession == new.accession_number
        assert any("FOR NO KEY UPDATE" in stmt and "companies" in stmt for stmt in statements)
    with sessions() as db:
        assert db.query(Filing).filter_by(accession_number="001").one().superseded_by_accession == "002"


def test_pdf_retains_value_and_citation_quality():
    from app.services.export_service import export_service
    record = SimpleNamespace(mode="annual", period_key="FY2025", narrative_md="Revenue grew [1].",
        dataset_json={"periods": [{"key": "FY2025"}], "series": [{"concept": "revenue", "label": "Revenue",
        "unit": "USD", "points": [{"period": "FY2025", "value": 123, "reconciled": False}]}]},
        citations_json=[{"n": 1, "excerpt": "Revenue = 123", "verified": True, "reconciled": False}])
    html = export_service.generate_analysis_pdf_html(record, SimpleNamespace(name="A", ticker="A"))
    assert "$123 [unreconciled]" in html
    assert "Unreconciled value — check source filing." in html
    assert "Citation verification confirms traceability, not financial reconciliation." in html


def test_precompute_prefers_latest_period_over_late_old_amendment(sessions, monkeypatch):
    from app.services.precompute_service import precompute_one
    from app.services.edgar.compat import sec_edgar_service
    with sessions() as db:
        db.add(Company(cik="1", ticker="AAPL", name="A"))
        db.commit()
    def row(acc, end, filed):
        return {"accession_number": acc, "filing_type": "10-K/A", "report_date": end,
                "filing_date": filed, "sec_url": "https://sec.example/filing/", "document_url": "https://sec.example/filing/a.htm"}
    fetch = AsyncMock(return_value=[row("old", "2024-12-31", "2026-04-01"), row("new", "2025-12-31", "2026-03-01")])
    monkeypatch.setattr(sec_edgar_service, "get_filings", fetch)
    result = asyncio.run(precompute_one("AAPL", "10-K", dry_run=True))
    assert result["accession"] == "new" and result["status"] == "would_generate"
    assert fetch.await_args.kwargs["limit"] == 20
    with sessions() as db:
        assert db.query(Filing).count() == 0


def test_seed_script_records_distinct_dry_and_applied_attempts(sessions, monkeypatch):
    import importlib.util
    from app.models import JobRun
    from app.services import universe_seed_service, job_run_service
    monkeypatch.setattr(job_run_service, "SessionLocal", sessions)
    seed = AsyncMock(return_value={"would_create": 2, "source_errors": 0})
    monkeypatch.setattr(universe_seed_service, "seed_universe_companies", seed)
    path = Path(__file__).parents[2] / "scripts/seed_universe_companies.py"
    spec = importlib.util.spec_from_file_location("ws7_seed", path)
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    asyncio.run(script.main())
    asyncio.run(script.main(apply=True, limit=2))
    assert [call.kwargs for call in seed.await_args_list] == [{"apply": False, "limit": None}, {"apply": True, "limit": 2}]
    with sessions() as db:
        attempts = db.query(JobRun).order_by(JobRun.started_at).all()
        assert [row.job_name for row in attempts] == ["universe-company-seed"] * 2
        assert [row.status for row in attempts] == ["dry_run", "succeeded"]
