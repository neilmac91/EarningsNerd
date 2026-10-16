"""The FY relabel repair (2026-10-15 bug hunt finding 8, plan P6) for stored filing-owned facts.

On main the per-filing writer named every 10-K point by the calendar year of its end
(``facts/upsert.py`` ``point.get("fiscal_year") or period_end.year``) while the companyfacts writer
named the same period by the issuer's fiscal year. The fact identity leaves ``fiscal_year`` out, so
neither writer corrects the other's rows. ``scripts/relabel_filing_fy_facts.py`` copies the
companyfacts year onto filing-owned FY rows, and only a year it can trust: every companyfacts FY row
at that period end names one year, and at least one of them is a duration. The companyfacts writer
names its oldest opening balance (an instant older than every fiscal year it knows) by calendar year
(``facts/companyfacts.py`` ``reported_fiscal_year(record, end) or end.year``), which for a January
year is the next year's label, so an instant-only label is never copied.
"""
import json
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app import database
from app.models import Base, Company, Filing, FinancialFact
from app.models.financial_fact_revision import FinancialFactRevision
from app.services import facts_service, quarterly_fact_repair
from app.utils.sec_urls import build_sec_archive_url
from scripts import relabel_filing_fy_facts as relabel

pytestmark = pytest.mark.unit

# (start, end) of each fiscal year, keyed by the issuer's own name for the year.
CALENDARS = {
    # Target: fiscal 2024 ended 1 February 2025 and is named for the calendar year it starts in.
    "TGT": {2020: ("2020-02-02", "2021-01-30"), 2021: ("2021-01-31", "2022-01-29"),
            2022: ("2022-01-30", "2023-01-28"), 2023: ("2023-01-29", "2024-02-03"),
            2024: ("2024-02-04", "2025-02-01")},
    # Johnson & Johnson: 52-week years; fiscal 2021 and 2022 ended on 2 and 1 January.
    "JNJ": {2021: ("2021-01-04", "2022-01-02"), 2022: ("2022-01-03", "2023-01-01"),
            2023: ("2023-01-02", "2023-12-31")},
    # Apple: a September year; the calendar year of the end already names the year.
    "AAPL": {2022: ("2021-09-26", "2022-09-24"), 2023: ("2022-09-25", "2023-09-30"),
             2024: ("2023-10-01", "2024-09-28")},
}
CIKS = {"TGT": "0000027419", "JNJ": "0000200406", "AAPL": "0000320193"}


@pytest.fixture
def factory(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'relabel.sqlite'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(database, "SessionLocal", sessions)  # the CLI opens its sessions from here
    yield sessions
    engine.dispose()


@pytest.fixture
def db(factory):
    with factory() as session:
        yield session


def _day(text):
    return date.fromisoformat(text)


def _older_10k(company):
    """The accession companyfacts stored the periods under: the 10-K before the one a reader opened."""
    return f"{company.cik}-24-000010"


def _company(db, ticker):
    company = Company(cik=CIKS[ticker], ticker=ticker, name=ticker)
    db.add(company)
    db.flush()
    accession = f"{company.cik}-25-000010"  # the newest 10-K, which a reader opened
    url = build_sec_archive_url(company.cik, accession)
    filing = Filing(
        company_id=company.id, accession_number=accession, filing_type="10-K",
        filing_date=datetime(2025, 3, 12, tzinfo=timezone.utc), sec_url=url, document_url=f"{url}a.htm",
    )
    db.add(filing)
    db.flush()
    return company, filing


def _fact(db, company, *, concept, end, fiscal_year, source="companyfacts", filing=None, start=None,
          accession=None, fiscal_period="FY", value=100.0, raw_tag="us-gaap:Revenues", **extra):
    row = FinancialFact(
        company_id=company.id, filing_id=filing.id if filing else None, concept=concept, raw_tag=raw_tag,
        unit=extra.pop("unit", "USD"), period_start=_day(start) if start else None, period_end=_day(end),
        fiscal_year=fiscal_year, fiscal_period=fiscal_period, value=Decimal(str(value)), form="10-K",
        accession=accession or (filing.accession_number if filing else _older_10k(company)), source=source,
        reconciled=True, is_latest=extra.pop("is_latest", True), **extra,
    )
    db.add(row)
    db.flush()
    return row


def _issuer(db, ticker, *, filing_years=None):
    """Companyfacts FY rows under the issuer's fiscal years; the opened 10-K's rows under calendar years.

    Each year gets a revenue duration and an equity instant from both writers, as on main.
    """
    calendar = CALENDARS[ticker]
    company, filing = _company(db, ticker)
    for fy, (start, end) in calendar.items():
        if fy == min(calendar) and ticker == "TGT":
            continue  # Target's oldest year is only an opening balance (see the trust test)
        _fact(db, company, concept="revenue", end=end, start=start, fiscal_year=fy)
        _fact(db, company, concept="shareholders_equity", end=end, fiscal_year=fy,
              raw_tag="us-gaap:StockholdersEquity", value=50.0)
    for fy in filing_years or list(calendar)[-3:]:
        start, end = calendar[fy]
        _fact(db, company, concept="revenue", end=end, start=start, fiscal_year=_day(end).year,
              source="edgar_xbrl", filing=filing)
        _fact(db, company, concept="shareholders_equity", end=end, fiscal_year=_day(end).year,
              source="edgar_xbrl", filing=filing, raw_tag="us-gaap:StockholdersEquity", value=50.0)
    db.commit()
    return company, filing


def _labels(db, company, source="edgar_xbrl"):
    rows = db.query(FinancialFact).filter_by(company_id=company.id, source=source).all()
    return sorted({(row.concept, row.period_end.isoformat(), row.fiscal_year) for row in rows})


def _states(db):
    db.expire_all()
    return {row.id: quarterly_fact_repair.snapshot(row) for row in db.query(FinancialFact).all()}


def _apply(db, company, run_id="run-1"):
    result = relabel.relabel_company(db, company.id, apply=True, run_id=run_id)
    db.commit()
    return result


def test_target_style_filing_rows_take_the_companyfacts_fiscal_year(db):
    company, _filing = _issuer(db, "TGT")
    assert _labels(db, company) == [
        ("revenue", "2023-01-28", 2023), ("revenue", "2024-02-03", 2024), ("revenue", "2025-02-01", 2025),
        ("shareholders_equity", "2023-01-28", 2023), ("shareholders_equity", "2024-02-03", 2024),
        ("shareholders_equity", "2025-02-01", 2025),
    ]
    before = _states(db)

    result = _apply(db, company)

    assert result["relabels"] == [
        {"period_end": "2023-01-28", "from": 2023, "to": 2022, "rows": 2},
        {"period_end": "2024-02-03", "from": 2024, "to": 2023, "rows": 2},
        {"period_end": "2025-02-01", "from": 2025, "to": 2024, "rows": 2},
    ]
    assert result["scanned"] == result["relabel_rows"] == result["revisions"] == 6
    # Durations and instants alike now carry the year companyfacts names for that period end.
    assert _labels(db, company) == [
        ("revenue", "2023-01-28", 2022), ("revenue", "2024-02-03", 2023), ("revenue", "2025-02-01", 2024),
        ("shareholders_equity", "2023-01-28", 2022), ("shareholders_equity", "2024-02-03", 2023),
        ("shareholders_equity", "2025-02-01", 2024),
    ]
    after = _states(db)
    assert after.keys() == before.keys()  # nothing inserted or deleted
    for row_id, state in before.items():
        changed = {key for key in state if state[key] != after[row_id][key]}
        assert changed <= {"fiscal_year"}  # period_end, value, unit, is_latest, accession all kept
        assert bool(changed) == (state["source"] == "edgar_xbrl")


def test_jnj_style_january_first_year_end_no_longer_draws_two_fy2023_bars(db):
    company, filing = _issuer(db, "JNJ")
    chart = facts_service.get_filing_fundamentals(db, filing.id)
    assert [p["fiscal_year"] for p in chart["concepts"][0]["points"]] == [2022, 2023, 2023]

    result = _apply(db, company)

    assert result["relabels"] == [
        {"period_end": "2022-01-02", "from": 2022, "to": 2021, "rows": 2},
        {"period_end": "2023-01-01", "from": 2023, "to": 2022, "rows": 2},
    ]
    assert result["skipped"]["already_agrees"] == 2  # 2023-12-31 is fiscal 2023 in both writers
    db.expire_all()
    chart = facts_service.get_filing_fundamentals(db, filing.id)
    assert [p["fiscal_year"] for p in chart["concepts"][0]["points"]] == [2021, 2022, 2023]


def test_apple_whose_labels_already_agree_is_untouched_and_never_written(db, factory):
    company, _filing = _issuer(db, "AAPL")
    before = _states(db)
    statements = []
    event.listen(db.bind, "before_cursor_execute", lambda c, cu, stmt, *a: statements.append(stmt))

    result = _apply(db, company)

    assert result["relabel_rows"] == result["revisions"] == 0
    assert result["skipped"] == {"already_agrees": 6, "companyfacts_disagree": 0,
                                 "no_companyfacts_fy": 0, "untrusted_instant_only": 0}
    assert not any(s.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for s in statements)
    assert _states(db) == before


def test_dry_run_reports_the_plan_and_writes_nothing(db):
    company, _filing = _issuer(db, "TGT")
    before = _states(db)
    statements = []
    event.listen(db.bind, "before_cursor_execute", lambda c, cu, stmt, *a: statements.append(stmt))

    preview = relabel.relabel_company(db, company.id, apply=False, run_id="preview")
    db.rollback()

    assert preview["dry_run"] and preview["relabel_rows"] == 6 and preview["revisions"] == 0
    assert not any(s.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for s in statements)
    assert _states(db) == before
    assert db.query(FinancialFactRevision).count() == 0
    applied = _apply(db, company)
    assert {key: applied[key] for key in ("relabels", "skipped", "held")} == {
        key: preview[key] for key in ("relabels", "skipped", "held")
    }


def test_a_second_apply_changes_nothing_and_reports_zero(db):
    company, _filing = _issuer(db, "TGT")
    _apply(db, company)
    settled = _states(db)

    again = _apply(db, company, run_id="run-2")

    assert again["relabel_rows"] == again["revisions"] == 0 and again["relabels"] == []
    assert again["skipped"]["already_agrees"] == 6
    assert _states(db) == settled
    assert db.query(FinancialFactRevision).filter_by(run_id="run-2").count() == 0


def test_an_instant_only_companyfacts_label_is_never_copied(db):
    """Target's opening balance: companyfacts names the fiscal-2020 year-end balance 2021."""
    company, filing = _issuer(db, "TGT")
    opening = CALENDARS["TGT"][2020][1]
    _fact(db, company, concept="shareholders_equity", end=opening, fiscal_year=2021,
          raw_tag="us-gaap:StockholdersEquity")
    # A filing row already naming it fiscal 2020 must keep that label, and one naming it 2021
    # stays as it is: neither can be proved from an instant-only label.
    kept = _fact(db, company, concept="shareholders_equity", end=opening, fiscal_year=2020,
                 source="edgar_xbrl", filing=filing, raw_tag="us-gaap:StockholdersEquity")
    calendar_row = _fact(db, company, concept="cash_and_equivalents", end=opening, fiscal_year=2021,
                         source="edgar_xbrl", filing=filing, raw_tag="us-gaap:Cash")
    db.commit()

    result = _apply(db, company)

    db.refresh(kept)
    db.refresh(calendar_row)
    assert (kept.fiscal_year, calendar_row.fiscal_year) == (2020, 2021)
    assert result["skipped"]["untrusted_instant_only"] == 2
    assert result["held"] == {"untrusted_instant_only": [opening]}
    assert all(r["period_end"] != opening for r in result["relabels"])


def test_disagreeing_or_missing_companyfacts_years_skip_and_never_pick_one(db):
    company, filing = _company(db, "TGT")
    split, missing, quarantined = "2024-02-03", "2025-02-01", "2023-01-28"
    _fact(db, company, concept="revenue", end=split, start="2023-01-29", fiscal_year=2023)
    _fact(db, company, concept="net_income", end=split, start="2023-01-29", fiscal_year=2024,
          raw_tag="us-gaap:NetIncomeLoss")
    # A row a quarterly repair retired as wrong is not evidence; the live duration decides.
    _fact(db, company, concept="revenue", end=quarantined, start="2022-01-30", fiscal_year=2022)
    _fact(db, company, concept="net_income", end=quarantined, start="2022-01-30", fiscal_year=2023,
          raw_tag="us-gaap:NetIncomeLoss", is_latest=False,
          provenance={"validation": "unavailable", "reasons": ["legacy_period_label_mismatch"]})
    for end, start in ((split, "2023-01-29"), (missing, "2024-02-04"), (quarantined, "2022-01-30")):
        _fact(db, company, concept="revenue", end=end, start=start, fiscal_year=_day(end).year,
              source="edgar_xbrl", filing=filing)
    db.commit()

    result = _apply(db, company)

    assert _labels(db, company) == [("revenue", quarantined, 2022), ("revenue", split, 2024),
                                    ("revenue", missing, 2025)]
    assert result["skipped"] == {"already_agrees": 0, "companyfacts_disagree": 1,
                                 "no_companyfacts_fy": 1, "untrusted_instant_only": 0}
    assert result["held"] == {"companyfacts_disagree": [split], "no_companyfacts_fy": [missing]}


def test_only_filing_owned_fy_rows_are_relabelled(db):
    company, filing = _issuer(db, "TGT")
    end, start = CALENDARS["TGT"][2024][1], "2024-11-03"
    quarter = _fact(db, company, concept="revenue", end=end, start=start, fiscal_year=2025,
                    fiscal_period="Q4", source="edgar_xbrl", filing=filing)
    derived = _fact(db, company, concept="free_cash_flow", end=end, start="2024-02-04", fiscal_year=2025,
                    source="derived", raw_tag=None, accession="0000027419-25-000099")
    eps = _fact(db, company, concept="earnings_per_share", end=end, fiscal_year=2025, unit="USD/shares",
                source="reported_eps", raw_tag=None, accession="0000027419-25-000098")
    db.commit()
    untouched = {row.id: quarterly_fact_repair.snapshot(row) for row in (quarter, derived, eps)}
    companyfacts = _labels(db, company, source="companyfacts")

    _apply(db, company)

    db.expire_all()
    assert {row.id: quarterly_fact_repair.snapshot(row) for row in (quarter, derived, eps)} == untouched
    assert _labels(db, company, source="companyfacts") == companyfacts


def test_the_fact_identity_and_indexes_leave_fiscal_year_out():
    """A relabel cannot collide: no unique constraint or index on financial_fact names fiscal_year."""
    table = FinancialFact.__table__
    identity = next(c for c in table.constraints if c.name == "uq_financial_fact_identity")
    assert [c.name for c in identity.columns] == [
        "company_id", "concept", "period_end", "fiscal_period", "unit", "accession",
    ]
    assert all("fiscal_year" not in {c.name for c in getattr(item, "columns", [])}
               for item in [*table.constraints, *table.indexes])


def test_apply_journals_each_relabel_and_the_quarterly_rollback_restores_it(db):
    company, _filing = _issuer(db, "JNJ")
    before = _states(db)

    _apply(db, company, run_id="relabel-run")

    journal = db.query(FinancialFactRevision).filter_by(run_id="relabel-run").all()
    assert len(journal) == 4 and {r.action for r in journal} == {"apply"}
    assert all(r.before_state == before[r.fact_id] for r in journal)
    assert {(r.before_state["fiscal_year"], r.after_state["fiscal_year"]) for r in journal} == {
        (2022, 2021), (2023, 2022),
    }
    quarterly_fact_repair.rollback_company(db, company.id, "relabel-run", dry_run=False)
    db.commit()
    assert _states(db) == before


def test_cli_dry_runs_by_default_scopes_by_ticker_and_prints_json_lines(db, capsys):
    _issuer(db, "TGT")
    _issuer(db, "AAPL")
    before = _states(db)

    assert relabel.main([]) == 0
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert _states(db) == before
    summary = lines[-1]
    assert summary["dry_run"] and summary["companies"] == 2 and summary["failed"] == 0
    assert (summary["scanned"], summary["relabel_rows"], summary["companies_with_relabels"]) == (12, 6, 1)
    assert [(line["ticker"], line["relabel_rows"]) for line in lines[:-1]] == [("TGT", 6), ("AAPL", 0)]

    assert relabel.main(["--apply", "--tickers", "aapl"]) == 0
    applied = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [line["ticker"] for line in applied[:-1]] == ["AAPL"] and not applied[-1]["dry_run"]
    assert _states(db) == before

    assert relabel.main(["--tickers", "NOPE"]) == 1
    assert "NOPE" in json.loads(capsys.readouterr().out)["error"]


def test_writers_on_main_leave_rows_this_repair_fixes(db):
    """Production writers: a stale companyfacts sync, then the newest 10-K opened, then a resync."""
    calendar = CALENDARS["TGT"]
    company, filing = _company(db, "TGT")
    db.commit()
    reports = {2023: (_older_10k(company), "2024-03-13"), 2024: (filing.accession_number, "2025-03-12")}

    def payload(report_years):
        revenue, equity = [], []
        for fy in report_years:
            accn, filed = reports[fy]
            revenue += [{"start": calendar[y][0], "end": calendar[y][1], "val": 10.0 * y, "accn": accn,
                         "fy": fy, "fp": "FY", "form": "10-K", "filed": filed} for y in (fy, fy - 1, fy - 2)]
            equity += [{"end": calendar[y][1], "val": 5.0 * y, "accn": accn, "fy": fy, "fp": "FY",
                        "form": "10-K", "filed": filed} for y in (fy, fy - 1, fy - 2)]
        return {"cik": 27419, "facts": {"us-gaap": {"Revenues": {"units": {"USD": revenue}},
                                                "StockholdersEquity": {"units": {"USD": equity}}}}}

    standardized = {  # the newest 10-K's points: main's extractor gives annual points no fiscal_year
        "revenue": {"series": [{"period": calendar[y][1], "period_start": calendar[y][0], "value": 10.0 * y,
                                "form": "10-K", "raw_tag": "us-gaap:Revenues"} for y in (2024, 2023, 2022)]},
        "shareholders_equity": {"series": [{"period": calendar[y][1], "value": 5.0 * y, "form": "10-K",
                                            "raw_tag": "us-gaap:StockholdersEquity"} for y in (2024, 2023, 2022)]},
    }
    facts_service._persist_companyfacts_payload(db, company, payload([2023]))
    facts_service.process_filing_facts(db, filing, standardized=standardized)
    resync = facts_service._persist_companyfacts_payload(db, company, payload([2023, 2024]))
    assert resync["inserted"] == 0  # every newest-accession identity is already the filing's
    assert _labels(db, company) == [
        ("revenue", "2023-01-28", 2023), ("revenue", "2024-02-03", 2024), ("revenue", "2025-02-01", 2025),
        ("shareholders_equity", "2023-01-28", 2023), ("shareholders_equity", "2024-02-03", 2024),
        ("shareholders_equity", "2025-02-01", 2025),
    ]

    result = _apply(db, company)

    assert _labels(db, company) == [
        ("revenue", "2023-01-28", 2022), ("revenue", "2024-02-03", 2023), ("revenue", "2025-02-01", 2025),
        ("shareholders_equity", "2023-01-28", 2022), ("shareholders_equity", "2024-02-03", 2023),
        ("shareholders_equity", "2025-02-01", 2025),
    ]
    # The newest year exists only under the opened filing's accession, so companyfacts holds no
    # row for it: it is reported, never guessed.
    assert result["held"] == {"no_companyfacts_fy": ["2025-02-01"]}
