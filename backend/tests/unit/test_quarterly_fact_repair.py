"""Real persistence controls for explicit quarterly repair and non-destructive rollback."""
from copy import deepcopy
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Company, FinancialFact
from app.models.financial_fact_revision import FinancialFactRevision
from app.services import quarterly_fact_repair as repair
from scripts import repair_quarterly_facts as cli


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        session.add(Company(id=1, ticker="META", cik="1326801", name="Meta"))
        session.commit()
        yield session
    engine.dispose()


def fact(concept="operating_cash_flow", period="Q4", **overrides):
    result = {
        "company_id": 1, "filing_id": None, "concept": concept, "raw_tag": "us-gaap:CashFlow",
        "unit": "USD", "period_start": date(2024, 10, 1), "period_end": date(2024, 12, 31),
        "fiscal_year": 2024, "fiscal_period": period, "value": Decimal("20"), "form": "10-K",
        "accession": "0001326801-25-000010", "source": "derived", "reconciled": False,
        "provenance": None,
    }
    result.update(overrides)
    return result


def candidate(**overrides):
    values = {"value": Decimal("25"), "provenance": {
        "version": 1, "method": "calculated", "validation": "passed", "reasons": [],
        "calculation_version": "quarterly-v2", "formula": "FY - YTD9", "inputs": [],
    }}
    values.update(overrides)
    return fact(**values)


def payload():
    return {"cik": 1326801, "facts": {"us-gaap": {"CashFlow": {}}}}


def normalizer(monkeypatch, candidates=None, meta=None):
    monkeypatch.setattr(repair.facts_service, "normalize_companyfacts", lambda *a, **kw: (
        deepcopy(candidates if candidates is not None else [candidate()]),
        meta or {"unsupported_ifrs": False},
    ))


def seed(db, **kwargs):
    row = FinancialFact(**fact(**kwargs), is_latest=True)
    db.add(row)
    db.commit()
    return row


def test_preview_is_read_only_and_apply_preserves_original_then_is_idempotent(db, monkeypatch):
    old = seed(db)
    eps = seed(db, concept="eps_diluted", value=Decimal("7.95"), unit="USD/shares")
    untouched = seed(db, concept="revenue", source="edgar_xbrl")
    initial = repair.snapshot(old)
    added = candidate(period="Q2", period_start=date(2024, 4, 1), period_end=date(2024, 6, 30))
    normalizer(monkeypatch, [candidate(), added])
    statements = []
    event.listen(db.bind, "before_cursor_execute", lambda c, cu, stmt, *a: statements.append(stmt))
    preview = repair.repair_company(db, 1, payload())
    assert preview["planned_updates"] == 2 and preview["planned_inserts"] == 1
    assert not any(s.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for s in statements)
    assert repair.snapshot(old) == initial
    assert db.query(FinancialFactRevision).count() == 0

    applied = repair.repair_company(db, 1, payload(), dry_run=False, run_id="apply-1")
    db.commit()
    assert old.value == Decimal("25")
    assert eps.provenance["validation"] == "unavailable" and eps.is_latest
    assert untouched.provenance is None and untouched.source == "edgar_xbrl"
    journal = db.query(FinancialFactRevision).filter_by(fact_id=old.id).one()
    assert journal.before_state == initial and journal.after_state["value"] == "25"
    assert applied["revisions"] == 3
    rerun = repair.repair_company(db, 1, payload(), dry_run=False)
    db.commit()
    assert rerun["revisions"] == 0 and rerun["planned_updates"] == 0
    assert db.query(FinancialFact).count() == 4


def test_partial_payload_cannot_quarantine_missing_monetary_history(db, monkeypatch):
    old = seed(db)
    normalizer(monkeypatch, [candidate(concept="revenue")], meta={"quarterly_exclusions": [{
        "concept": "operating_cash_flow", "fiscal_year": 2024, "fiscal_period": "Q4",
        "reason": "missing_compatible_operand",
    }]})
    repair.repair_company(db, 1, payload(), dry_run=False)
    db.commit()
    assert old.value == Decimal("20") and old.provenance is None and old.is_latest


def test_positive_incompatibility_evidence_quarantines_dependent_metric(db, monkeypatch):
    margin = seed(db, concept="operating_margin", unit="pure")
    normalizer(monkeypatch, [candidate(concept="revenue")], meta={"quarterly_exclusions": [{
        "concept": "operating_income", "fiscal_year": 2024, "fiscal_period": "Q4",
        "reason": "incompatible_vintages", "inputs": [{"accession": "old"}, {"accession": "new"}],
    }]})
    repair.repair_company(db, 1, payload(), dry_run=False)
    db.commit()
    assert margin.provenance["validation"] == "unavailable" and margin.is_latest
    assert margin.provenance["exclusion_evidence"][0]["reason"] == "incompatible_vintages"


def test_rollback_restores_original_and_retains_inserted_history(db, monkeypatch):
    old = seed(db)
    initial = repair.snapshot(old)
    normalizer(monkeypatch, [candidate(), candidate(concept="free_cash_flow")])
    repair.repair_company(db, 1, payload(), dry_run=False, run_id="apply-1")
    db.commit()
    preview = repair.rollback_company(db, 1, "apply-1")
    assert preview["dry_run"] and old.value == Decimal("25")
    repair.rollback_company(db, 1, "apply-1", dry_run=False)
    db.commit()
    assert repair.snapshot(old) == initial
    added = db.query(FinancialFact).filter_by(concept="free_cash_flow").one()
    assert not added.is_latest and added.provenance["reasons"] == ["repair_rolled_back"]
    assert db.query(FinancialFactRevision).filter_by(action="rollback").count() == 2
    with pytest.raises(ValueError, match="already been rolled back"):
        repair.rollback_company(db, 1, "apply-1", dry_run=False)
    with pytest.raises(ValueError, match="identity was rolled back"):
        repair.repair_company(db, 1, payload(), dry_run=False)


def test_rollback_compare_and_swap_refuses_all_rows_after_intervening_change(db, monkeypatch):
    old = seed(db)
    normalizer(monkeypatch, [candidate(), candidate(concept="free_cash_flow")])
    repair.repair_company(db, 1, payload(), dry_run=False, run_id="apply-1")
    db.commit()
    old.value = Decimal("99")
    db.commit()
    before = [repair.snapshot(row) for row in db.query(FinancialFact).all()]
    with pytest.raises(ValueError, match="Rollback conflict"):
        repair.rollback_company(db, 1, "apply-1", dry_run=False)
    assert before == [repair.snapshot(row) for row in db.query(FinancialFact).all()]
    assert db.query(FinancialFactRevision).filter_by(action="rollback").count() == 0


def test_failed_transaction_rolls_back_data_and_journal_together(db, monkeypatch):
    old = seed(db)
    normalizer(monkeypatch)
    repair.repair_company(db, 1, payload(), dry_run=False)
    db.rollback()
    assert old.value == Decimal("20")
    assert db.query(FinancialFactRevision).count() == 0


def test_reported_eps_replaces_unsafe_derived_and_restores_on_rollback(db, monkeypatch):
    old = seed(db, concept="eps_diluted", value=Decimal("7.95"), unit="USD/shares")
    normalizer(monkeypatch)
    eps = fact(concept="eps_diluted", value=Decimal("8.02"), unit="USD/shares",
               accession="0001326801-25-000014", source="reported_eps", raw_tag=None,
               provenance={"method": "reported", "validation": "passed", "source_sha256": "a" * 64})
    repair.repair_company(db, 1, payload(), dry_run=False, reported_eps=[eps], run_id="eps")
    db.commit()
    assert not old.is_latest
    current = db.query(FinancialFact).filter_by(concept="eps_diluted", is_latest=True).one()
    assert current.value == Decimal("8.02") and current.source == "reported_eps"
    repair.rollback_company(db, 1, "eps", dry_run=False)
    db.commit()
    assert old.is_latest and old.value == Decimal("7.95") and old.provenance is None


@pytest.mark.parametrize("bad", [{}, {"cik": 9, "facts": {"us-gaap": {}}}])
def test_company_identity_rejected_before_writes(db, monkeypatch, bad):
    normalizer(monkeypatch)
    with pytest.raises(ValueError, match="CIK"):
        repair.repair_company(db, 1, bad, dry_run=False)
    assert db.query(FinancialFactRevision).count() == 0


def test_cli_bounds_before_importing_database():
    args = SimpleNamespace(tickers="META,MSFT", limit=1)
    with pytest.raises(ValueError, match="explicit tickers"):
        cli.run(args)
    assert not cli.build_parser().parse_args(["--tickers", "META"]).apply


def test_real_cli_preview_closes_fetch_read_and_does_not_write(db, monkeypatch, tmp_path):
    import json

    from app import database

    seed(db)
    normalizer(monkeypatch)
    monkeypatch.setattr(database, "SessionLocal", lambda: Session(db.bind))
    (tmp_path / "CIK0001326801.json").write_text(json.dumps(payload()))
    statements = []
    event.listen(db.bind, "before_cursor_execute", lambda c, cu, stmt, *a: statements.append(stmt))
    result = cli.run(cli.build_parser().parse_args([
        "--tickers", "META", "--companyfacts-dir", str(tmp_path),
    ]))
    assert result["failed"] == 0 and result["dry_run"]
    assert result["companies"][0]["planned_updates"] == 1
    assert not any(s.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for s in statements)


@pytest.mark.asyncio
async def test_explicit_eps_adapter_keeps_exact_source_and_typed_dates(monkeypatch):
    from app.services.edgar import reported_quarterly_eps

    calls = []

    async def fetch(**kwargs):
        calls.append(kwargs)
        return {
            "unit": "USD/shares", "period_start": "2024-10-01", "period_end": "2024-12-31",
            "form": "8-K", "source_url": "https://source.invalid/filing",
            "source_sha256": "a" * 64, "source_evidence": {"table_path": "html/body/table[1]"},
            "values": {"eps_basic": Decimal("8.24"), "eps_diluted": Decimal("8.02")},
        }

    monkeypatch.setattr(reported_quarterly_eps, "fetch_reported_quarterly_eps", fetch)
    entry = {"ticker": "META", "cik": "1326801", "accession": "0001326801-25-000014",
             "filename": "meta-12312024xexhibit991.htm", "period_end": "2024-12-31",
             "fiscal_year": 2024, "fiscal_period": "Q4", "currency": "USD", "filed_at": "2025-01-29"}
    company = {"id": 1, "ticker": "META", "cik": "1326801"}
    facts = await cli._reported_eps(company, [entry], {"USD/shares"})
    assert len(calls) == 1 and calls[0]["currency"] == "USD"
    assert facts[0]["concept"] == "earnings_per_share"
    assert facts[1]["value"] == Decimal("8.02")
    assert facts[1]["period_start"] == date(2024, 10, 1)
    assert facts[1]["provenance"]["source_sha256"] == "a" * 64
    assert facts[1]["provenance"]["method"] == "reported"
    with pytest.raises(ValueError, match="CIK/currency"):
        await cli._reported_eps(company, [entry], {"CAD/shares"})


def test_reported_eps_refuses_manifest_fiscal_label_mismatch(db, monkeypatch):
    normalizer(monkeypatch)
    eps = fact(concept="eps_diluted", source="reported_eps", unit="USD/shares", fiscal_year=2023)
    with pytest.raises(ValueError, match="fiscal label"):
        repair.repair_company(db, 1, payload(), dry_run=False, reported_eps=[eps])
    assert db.query(FinancialFactRevision).count() == 0


def test_real_normalizer_repairs_persisted_cash_quarters_and_canonical_basic_eps(db):
    from app.services.facts_service import normalize_companyfacts

    source = {"cik": 1326801, "facts": {"us-gaap": {
        "NetCashProvidedByUsedInOperatingActivities": {"units": {"USD": [
            {"val": value, "start": "2024-01-01", "end": end, "accn": accession,
             "filed": filed, "fy": 2024, "fp": fp, "form": "10-K" if fp == "FY" else "10-Q"}
            for value, end, accession, filed, fp in [
                (19246000000, "2024-03-31", "Q1", "2024-04-25", "Q1"),
                (38616000000, "2024-06-30", "Q2", "2024-08-01", "Q2"),
                (63340000000, "2024-09-30", "Q3", "2024-10-31", "Q3"),
                (91328000000, "2024-12-31", "FY", "2025-01-30", "FY"),
            ]
        ]}},
    }}}
    normalized, _ = normalize_companyfacts(1, source)
    q4 = next(f for f in normalized if f["fiscal_period"] == "Q4")
    stale = FinancialFact(**{**q4, "value": Decimal("20000000000"), "provenance": None,
                             "reconciled": False}, is_latest=True)
    db.add(stale)
    db.commit()
    basic = seed(db, concept="earnings_per_share", value=Decimal("8.24"), unit="USD/shares")
    result = repair.repair_company(db, 1, source, dry_run=False)
    db.commit()
    assert stale.value == Decimal("27988000000") and stale.provenance["validation"] == "passed"
    assert basic.provenance["validation"] == "unavailable"
    quarters = db.query(FinancialFact).filter_by(concept="operating_cash_flow", is_latest=True).all()
    assert {row.fiscal_period: row.value for row in quarters} == {
        "Q2": Decimal("19370000000"), "Q3": Decimal("24724000000"), "Q4": Decimal("27988000000"),
    }
    assert result["revisions"] == 4


def test_existing_noncurrent_reported_eps_is_promoted_without_losing_latest(db, monkeypatch):
    old = seed(db, concept="eps_diluted", value=Decimal("7.95"), unit="USD/shares")
    reported = seed(db, concept="eps_diluted", value=Decimal("8.02"), unit="USD/shares",
                    source="reported_eps", accession="0001326801-25-000014")
    reported.is_latest = False
    db.commit()
    normalizer(monkeypatch)
    exact = {k: getattr(reported, k) for k in fact()}
    result = repair.repair_company(db, 1, payload(), dry_run=False, reported_eps=[exact])
    db.commit()
    assert not old.is_latest and reported.is_latest
    assert db.query(FinancialFact).filter_by(concept="eps_diluted", is_latest=True).one() == reported
    assert result["planned_inserts"] == 1  # only the previously absent operating cash flow


def test_reported_eps_existing_identity_conflict_is_refused_before_any_write(db, monkeypatch):
    old = seed(db, concept="eps_diluted", value=Decimal("7.95"), unit="USD/shares")
    reported = seed(db, concept="eps_diluted", value=Decimal("8.03"), unit="USD/shares",
                    source="reported_eps", accession="0001326801-25-000014")
    normalizer(monkeypatch)
    exact = {k: getattr(reported, k) for k in fact()}
    exact["value"] = Decimal("8.02")
    with pytest.raises(ValueError, match="existing reported identity"):
        repair.repair_company(db, 1, payload(), dry_run=False, reported_eps=[exact])
    assert old.is_latest and old.provenance is None
    assert db.query(FinancialFactRevision).count() == 0


def test_rollback_refreshes_stale_session_identity_before_compare(db, monkeypatch):
    old = seed(db)
    normalizer(monkeypatch)
    repair.repair_company(db, 1, payload(), dry_run=False, run_id="apply-1")
    db.commit()
    with Session(db.bind) as other:
        changed = other.get(FinancialFact, old.id)
        changed.value = Decimal("99")
        other.commit()
    assert old.value == Decimal("25")  # The caller's identity map is deliberately stale.
    with pytest.raises(ValueError, match="Rollback conflict"):
        repair.rollback_company(db, 1, "apply-1", dry_run=False)
    assert old.value == Decimal("99")
    assert db.query(FinancialFactRevision).filter_by(action="rollback").count() == 0


def test_annual_computed_lineage_refresh_preserves_reported_annual_and_filing_owned(db, monkeypatch):
    margin = seed(db, concept="operating_margin", period="FY", raw_tag=None,
                  value=Decimal("25"), unit="pure", period_start=date(2024, 1, 1))
    cash = seed(db, concept="free_cash_flow", period="FY", raw_tag=None,
                value=Decimal("25"), source="companyfacts", period_start=date(2024, 1, 1))
    revenue = seed(db, concept="revenue", period="FY", source="companyfacts",
                   value=Decimal("100"), period_start=date(2024, 1, 1))
    filing_owned = seed(db, concept="net_margin", period="FY", raw_tag=None,
                       filing_id=99, value=Decimal("25"), unit="pure", period_start=date(2024, 1, 1))
    original_revenue, original_owned = repair.snapshot(revenue), repair.snapshot(filing_owned)
    normalizer(monkeypatch, [
        candidate(concept="operating_margin", period="FY", raw_tag=None, unit="pure",
                  period_start=date(2024, 1, 1)),
        candidate(concept="free_cash_flow", period="FY", raw_tag=None, period_start=date(2024, 1, 1)),
        candidate(concept="net_margin", period="FY", raw_tag=None, unit="pure", period_start=date(2024, 1, 1)),
        candidate(concept="revenue", period="FY", value=Decimal("999"), source="companyfacts"),
        candidate(concept="current_ratio", period="FY", raw_tag=None, unit="pure"),
    ])
    result = repair.repair_company(db, 1, payload(), dry_run=False)
    db.commit()
    assert margin.value == cash.value == Decimal("25")
    assert margin.provenance["validation"] == cash.provenance["validation"] == "passed"
    assert repair.snapshot(revenue) == original_revenue
    assert repair.snapshot(filing_owned) == original_owned
    assert result["revisions"] == 2 and result["planned_inserts"] == 0
    assert result["after"]["annual_computed_by_status"] == {"legacy": 1, "passed": 2}


def _calendar_payload():
    observations = [
        {"val": value, "start": start, "end": end, "fp": period, "fy": 2025,
         "filed": filed, "form": "10-K" if period == "FY" else "10-Q", "accn": accession}
        for value, start, end, period, filed, accession in [
            (10, "2025-01-01", "2025-03-31", "Q1", "2025-05-02", "Q1"),
            (20, "2025-04-01", "2025-06-30", "Q2", "2025-08-01", "Q2"),
            (30, "2025-07-01", "2025-09-30", "Q3", "2025-10-31", "Q3"),
            (100, "2025-01-01", "2025-12-31", "FY", "2026-02-06", "FY"),
        ]
    ]
    rolling = {"val": 80, "start": "2024-04-01", "end": "2025-03-31", "fp": "Q1",
               "fy": 2025, "filed": "2025-05-02", "form": "10-Q", "accn": "Q1"}
    return {"cik": 1326801, "facts": {"us-gaap": {
        "RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": observations}},
        "NetCashProvidedByUsedInOperatingActivities": {"units": {"USD": observations + [rolling]}},
    }}}


def test_positive_calendar_proof_relabels_quarter_retires_rolling_fy_and_rolls_back(db):
    from app.services.facts_service import normalize_companyfacts

    source = _calendar_payload()
    canonical, _ = normalize_companyfacts(1, source)
    actual = next(f for f in canonical if f["concept"] == "revenue" and f["fiscal_period"] == "Q1")
    wrong_quarter = FinancialFact(**{**actual, "fiscal_period": "Q4", "provenance": None}, is_latest=True)
    db.add(wrong_quarter)
    db.commit()
    rolling = seed(db, period="FY", source="companyfacts", accession="Q1", value=Decimal("80"),
                   raw_tag="us-gaap:NetCashProvidedByUsedInOperatingActivities", fiscal_year=2025,
                   period_start=date(2024, 4, 1), period_end=date(2025, 3, 31))
    original_quarter, original_rolling = repair.snapshot(wrong_quarter), repair.snapshot(rolling)
    result = repair.repair_company(db, 1, source, dry_run=False, run_id="calendar")
    db.commit()
    assert not wrong_quarter.is_latest and not rolling.is_latest
    assert wrong_quarter.provenance["reasons"] == ["legacy_period_label_mismatch"]
    assert rolling.provenance["reasons"] == ["rolling_duration_not_fiscal_year"]
    rows = db.query(FinancialFact).filter_by(concept="revenue", period_end=date(2025, 3, 31), is_latest=True).all()
    assert len(rows) == 1 and rows[0].fiscal_period == "Q1" and rows[0].value == Decimal("10")
    assert rows[0].provenance["method"] == "reported"
    assert result["revisions"] >= 3
    repair.rollback_company(db, 1, "calendar", dry_run=False)
    db.commit()
    assert repair.snapshot(wrong_quarter) == original_quarter
    assert repair.snapshot(rolling) == original_rolling
    assert not rows[0].is_latest  # The replacement remains as archived history.


def test_calendar_fiscal_year_correction_updates_same_identity_but_skips_filing_owner(db, monkeypatch):
    wrong = seed(db, concept="revenue", period="Q1", fiscal_year=2026, source="companyfacts",
                 period_start=date(2026, 6, 1), period_end=date(2026, 8, 31))
    owned = seed(db, concept="net_income", period="Q1", fiscal_year=2026, source="companyfacts",
                 filing_id=99, period_start=date(2026, 6, 1), period_end=date(2026, 8, 31))
    original = repair.snapshot(owned)
    corrected = [{**{k: getattr(row, k) for k in fact()}, "fiscal_year": 2027} for row in (wrong, owned)]
    normalizer(monkeypatch, corrected)
    result = repair.repair_company(db, 1, payload(), dry_run=False, run_id="fy")
    db.commit()
    assert wrong.fiscal_year == 2027 and result["revisions"] == 1 and result["planned_inserts"] == 0
    assert repair.snapshot(owned) == original
    repair.rollback_company(db, 1, "fy", dry_run=False)
    db.commit()
    assert wrong.fiscal_year == 2026


def test_missing_calendar_evidence_does_not_retire_historical_fy(db):
    source = _calendar_payload()
    root = source["facts"]["us-gaap"]
    del root["RevenueFromContractWithCustomerExcludingAssessedTax"]
    root["NetCashProvidedByUsedInOperatingActivities"]["units"]["USD"] = [
        root["NetCashProvidedByUsedInOperatingActivities"]["units"]["USD"][0],
        root["NetCashProvidedByUsedInOperatingActivities"]["units"]["USD"][-1],
    ]
    old = seed(db, period="FY", source="companyfacts", accession="Q1", value=Decimal("80"),
               raw_tag="us-gaap:NetCashProvidedByUsedInOperatingActivities", fiscal_year=2025,
               period_start=date(2024, 4, 1), period_end=date(2025, 3, 31))
    before = repair.snapshot(old)
    result = repair.repair_company(db, 1, source, dry_run=False)
    db.commit()
    assert repair.snapshot(old) == before and result["revisions"] == 0


def test_calendar_correction_retires_computed_children_of_positive_wrong_parent_scope(db):
    from app.services.facts_service import normalize_companyfacts
    from app.services.trend_analysis_service import build_dataset

    source = _calendar_payload()
    root = source["facts"]["us-gaap"]
    root["PaymentsToAcquirePropertyPlantAndEquipment"] = deepcopy(root["NetCashProvidedByUsedInOperatingActivities"])
    capex = root["PaymentsToAcquirePropertyPlantAndEquipment"]["units"]["USD"]
    capex[:] = [{**item, "val": item["val"] / 2} for item in capex if item["fp"] != "FY"]
    canonical, _ = normalize_companyfacts(1, source)
    reported_annual = next(f for f in canonical if f["concept"] == "revenue" and f["fiscal_period"] == "FY")
    db.add(FinancialFact(**reported_annual, is_latest=True))
    for concept in ("operating_cash_flow", "capital_expenditures"):
        actual = next(f for f in canonical if f["concept"] == concept and f["fiscal_period"] == "Q1")
        db.add(FinancialFact(**{**actual, "fiscal_period": "Q4", "provenance": None}, is_latest=True))
    db.commit()
    for concept, tag, value in (
        ("operating_cash_flow", "NetCashProvidedByUsedInOperatingActivities", 80),
        ("capital_expenditures", "PaymentsToAcquirePropertyPlantAndEquipment", 40),
    ):
        seed(db, concept=concept, period="FY", source="companyfacts", accession="Q1", value=Decimal(value),
             raw_tag=f"us-gaap:{tag}", fiscal_year=2025,
             period_start=date(2024, 4, 1), period_end=date(2025, 3, 31))
    old_annual = seed(db, concept="free_cash_flow", period="FY", raw_tag=None,
                      accession="Q1", value=Decimal("40"), fiscal_year=2025,
                      period_start=date(2024, 4, 1), period_end=date(2025, 3, 31))
    old_quarter = seed(db, concept="free_cash_flow", period="Q4", raw_tag=None,
                       accession="Q1", value=Decimal("5"), fiscal_year=2025,
                       period_start=date(2025, 1, 1), period_end=date(2025, 3, 31))
    repair.repair_company(db, 1, source, dry_run=False, run_id="calendar-children")
    db.commit()
    assert not old_annual.is_latest and not old_quarter.is_latest
    assert old_annual.provenance["reasons"] == ["calculation_parent_period_corrected"]
    assert {item["concept"] for item in old_annual.provenance["exclusion_evidence"]} == {
        "operating_cash_flow", "capital_expenditures",
    }
    annual = build_dataset(db, db.get(Company, 1), "annual", "FY2025", "FY2025")
    assert not any(series["concept"] == "free_cash_flow" and any(
        point["value"] is not None for point in series["points"]
    ) for series in annual["series"])
    current = db.query(FinancialFact).filter_by(concept="free_cash_flow", period_end=date(2025, 3, 31), is_latest=True).all()
    assert len(current) == 1 and current[0].fiscal_period == "Q1" and current[0].value == Decimal("5")
    repair.rollback_company(db, 1, "calendar-children", dry_run=False)
    db.commit()
    assert old_annual.is_latest and old_annual.value == Decimal("40")
    assert old_quarter.is_latest and old_quarter.value == Decimal("5")
