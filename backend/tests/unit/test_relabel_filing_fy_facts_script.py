"""The FY relabel repair (2026-10-15 bug hunt finding 8, plan P6) for stored filing-owned facts.

Before P5 the per-filing writer named every 10-K point by the calendar year of its end
(``facts/upsert.py`` ``point.get("fiscal_year") or period_end.year``) while the companyfacts writer
named the same period by the issuer's fiscal year. The fact identity leaves ``fiscal_year`` out, so
neither writer corrects the other's rows. ``scripts/relabel_filing_fy_facts.py`` copies the
companyfacts year onto filing-owned FY rows that still carry the calendar default, and only a year
it can trust: every companyfacts FY row the fiscal-year-window writer stored at that period end
(provenance version 1, since #1191) names one year, and at least one of them is a duration. Rows
stored before #1191 (NULL provenance) carry the calendar year of their end and are no evidence. An
instant-only label is never copied: the companyfacts writer names its oldest opening balance by one
report's fy or by calendar year (``facts/companyfacts.py``
``reported_fiscal_year(record, end) or end.year``). A relabel that would give a label another
period end of the same filing and concept, or of the concept's current rows, already carries is
held.
"""
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Query, sessionmaker

from app import database
from app.models import Base, Company, Filing, FinancialFact
from app.models.financial_fact_revision import FinancialFactRevision
from app.services import facts_service, quarterly_fact_repair
from app.services.facts import fiscal_evidence
from app.services.fact_provenance import reported_provenance
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
CIKS = {"TGT": "0000027419", "JNJ": "0000200406", "AAPL": "0000320193", "DEC": "0000000777"}  # DEC: synthetic
LEGACY = None  # provenance of a row the companyfacts writer stored before #1191


@pytest.fixture(autouse=True)
def sec(monkeypatch):
    """The companyfacts read the CLI makes from SEC for each company, faked (tests reach no network):
    a payload with no facts unless a case gives the CIK one (None is the transport's failed read)."""
    payloads, reads = {}, []

    def read(cik):
        reads.append(cik)
        return payloads.get(cik, {"cik": int(cik), "facts": {}})

    monkeypatch.setattr(facts_service, "_fetch_companyfacts_sync", read)
    return SimpleNamespace(payloads=payloads, reads=reads)


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


@pytest.fixture
def writer_before_1364(monkeypatch):
    """The per-filing writer as it stored rows before #1364: it kept each annual fact's own label rather
    than adopting the year companyfacts already names. Those stored rows are what this script repairs."""
    from app.services.facts import upsert
    monkeypatch.setattr(upsert, "adopt_trusted_fiscal_years", lambda db, form, facts: None)


def _day(text):
    return date.fromisoformat(text)


def _accession(company, year):
    return f"{company.cik}-{year}-000010"


def _companyfacts_accession(company, end):
    """The 10-K whose column companyfacts stored a period under: the 2024 one, or for a period
    ending after it was filed, the 2026 one's comparative (the state after a later resync)."""
    return _accession(company, 24 if _day(end) < date(2024, 3, 1) else 26)


def _company(db, ticker, year=25):
    company = Company(cik=CIKS[ticker], ticker=ticker, name=ticker)
    db.add(company)
    db.flush()
    accession = _accession(company, year)  # the 10-K a reader opened (by default the 2025 one)
    url = build_sec_archive_url(company.cik, accession)
    filing = Filing(
        company_id=company.id, accession_number=accession, filing_type="10-K",
        filing_date=datetime(2000 + year, 3, 12, tzinfo=timezone.utc), sec_url=url, document_url=f"{url}a.htm",
    )
    db.add(filing)
    db.flush()
    return company, filing


def _fact(db, company, *, concept, end, fiscal_year, source="companyfacts", filing=None, start=None,
          accession=None, fiscal_period="FY", value=100.0, raw_tag="us-gaap:Revenues", **extra):
    """A stored row; provenance defaults to the version-1 shape both writers have stored since #1191."""
    row = FinancialFact(
        company_id=company.id, filing_id=filing.id if filing else None, concept=concept, raw_tag=raw_tag,
        unit=extra.pop("unit", "USD"), period_start=_day(start) if start else None, period_end=_day(end),
        fiscal_year=fiscal_year, fiscal_period=fiscal_period, value=Decimal(str(value)), form="10-K",
        accession=accession or (filing.accession_number if filing else _companyfacts_accession(company, end)),
        source=source, reconciled=True, is_latest=extra.pop("is_latest", True),
        provenance=extra.pop("provenance", reported_provenance({"reconciled": True})), **extra,
    )
    db.add(row)
    db.flush()
    return row


def _issuer(db, ticker, *, filing_years=None):
    """Companyfacts FY rows under the issuer's fiscal years; the opened 10-K's rows under calendar years.

    Each year gets a revenue duration and an equity instant from both writers, as on main before P5.
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


def _chart(db, filing):
    """The filing page's annual chart: each concept's (period end, fiscal year) points."""
    db.expire_all()
    chart = facts_service.get_filing_fundamentals(db, filing.id)
    return {c["concept"]: [(p["period_end"], p["fiscal_year"]) for p in c["points"]] for c in chart["concepts"]}


def _states(db):
    db.expire_all()
    return {row.id: quarterly_fact_repair.snapshot(row) for row in db.query(FinancialFact).all()}


def _apply(db, company, run_id="run-1"):
    result = relabel.relabel_company(db, company.id, apply=True, run_id=run_id)
    db.commit()
    return result


def _writes(statements):
    return [s for s in statements if s.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))]


def _payload(company, reports, report_years):
    """A companyfacts payload: each 10-K reports its year and two comparatives (revenue, equity)."""
    calendar = CALENDARS[company.ticker]
    revenue, equity = [], []
    for fy in report_years:
        accn, filed = reports[fy]
        revenue += [{"start": calendar[y][0], "end": calendar[y][1], "val": 10.0 * y, "accn": accn,
                     "fy": fy, "fp": "FY", "form": "10-K", "filed": filed} for y in (fy, fy - 1, fy - 2)]
        equity += [{"end": calendar[y][1], "val": 5.0 * y, "accn": accn, "fy": fy, "fp": "FY",
                    "form": "10-K", "filed": filed} for y in (fy, fy - 1, fy - 2)]
    return {"cik": int(company.cik), "facts": {"us-gaap": {"Revenues": {"units": {"USD": revenue}},
                                                           "StockholdersEquity": {"units": {"USD": equity}}}}}


def _unlabelled_annual_points(company, years):
    """A 10-K's points as pre-P5 extractions (and Filing.xbrl_data snapshots taken before P5) give
    them: annual points carry no fiscal_year, so the per-filing writer stores the calendar year."""
    calendar = CALENDARS[company.ticker]
    return {
        "revenue": {"series": [{"period": calendar[y][1], "period_start": calendar[y][0], "value": 10.0 * y,
                                "form": "10-K", "raw_tag": "us-gaap:Revenues"} for y in years]},
        "shareholders_equity": {"series": [{"period": calendar[y][1], "value": 5.0 * y, "form": "10-K",
                                            "raw_tag": "us-gaap:StockholdersEquity"} for y in years]},
    }


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
    assert result["partial_filings"] == []
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
    assert [year for _end, year in _chart(db, filing)["revenue"]] == [2022, 2023, 2023]

    result = _apply(db, company)

    assert result["relabels"] == [
        {"period_end": "2022-01-02", "from": 2022, "to": 2021, "rows": 2},
        {"period_end": "2023-01-01", "from": 2023, "to": 2022, "rows": 2},
    ]
    assert result["skipped"]["already_agrees"] == 2  # 2023-12-31 is fiscal 2023 in both writers
    assert [year for _end, year in _chart(db, filing)["revenue"]] == [2021, 2022, 2023]


def test_apple_whose_labels_already_agree_is_untouched_and_never_written(db, factory):
    company, _filing = _issuer(db, "AAPL")
    before = _states(db)
    statements = []
    event.listen(db.bind, "before_cursor_execute", lambda c, cu, stmt, *a: statements.append(stmt))

    result = _apply(db, company)

    assert result["relabel_rows"] == result["revisions"] == 0
    assert result["skipped"] == dict.fromkeys(relabel.SKIP_REASONS, 0) | {"already_agrees": 6}
    assert not _writes(statements)
    assert _states(db) == before


def test_dry_run_reports_the_plan_and_writes_nothing(db):
    company, _filing = _issuer(db, "TGT")
    before = _states(db)
    statements = []
    event.listen(db.bind, "before_cursor_execute", lambda c, cu, stmt, *a: statements.append(stmt))

    preview = relabel.relabel_company(db, company.id, apply=False, run_id="preview")
    db.rollback()

    assert preview["dry_run"] and preview["relabel_rows"] == 6 and preview["revisions"] == 0
    assert not _writes(statements)
    assert _states(db) == before
    assert db.query(FinancialFactRevision).count() == 0
    applied = _apply(db, company)
    assert {key: applied[key] for key in ("relabels", "skipped", "held", "partial_filings")} == {
        key: preview[key] for key in ("relabels", "skipped", "held", "partial_filings")
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


def test_legacy_companyfacts_rows_are_neither_evidence_nor_agreement(db):
    """Rows the companyfacts writer stored before #1191 name every FY period by the calendar year of
    its end and carry NULL provenance, so they prove nothing about a fiscal year."""
    # After P5 a reader opens J&J's 2025 10-K: its annual points carry the fiscal year where the
    # calendar year of the end does not name it (fiscal 2022 ended 1 January 2023).
    jnj, jnj_filing = _company(db, "JNJ")
    for fy, label in ((2022, 2022), (2023, 2023)):
        start, end = CALENDARS["JNJ"][fy]
        _fact(db, jnj, concept="revenue", end=end, start=start, fiscal_year=_day(end).year, provenance=LEGACY)
        _fact(db, jnj, concept="revenue", end=end, start=start, fiscal_year=label, source="edgar_xbrl",
              filing=jnj_filing)
    # Before P5 a reader opened Target's 2025 10-K: calendar labels. Companyfacts holds a legacy row
    # at fiscal 2023's end and, at fiscal 2022's end, a legacy comparative beside the original report
    # the fiscal-year-window writer stored after #1191.
    tgt, tgt_filing = _company(db, "TGT")
    for fy in (2022, 2023):
        start, end = CALENDARS["TGT"][fy]
        _fact(db, tgt, concept="revenue", end=end, start=start, fiscal_year=_day(end).year,
              provenance=LEGACY, is_latest=False)
        _fact(db, tgt, concept="revenue", end=end, start=start, fiscal_year=_day(end).year, source="edgar_xbrl",
              filing=tgt_filing)
    start, end = CALENDARS["TGT"][2022]
    _fact(db, tgt, concept="revenue", end=end, start=start, fiscal_year=2022, accession=_accession(tgt, 23),
          is_latest=False)
    db.commit()
    jnj_before = _states(db)

    jnj_result = _apply(db, jnj)
    tgt_result = _apply(db, tgt)

    # P5's label is never rewritten to the legacy calendar year, and a calendar row is never
    # reported as agreeing with a legacy row.
    assert {k: v for k, v in _states(db).items() if v["company_id"] == jnj.id} == {
        k: v for k, v in jnj_before.items() if v["company_id"] == jnj.id
    }
    assert (jnj_result["relabel_rows"], jnj_result["skipped"]["already_agrees"]) == (0, 0)
    assert jnj_result["skipped"]["legacy_companyfacts_only"] == 2
    assert jnj_result["held"] == {"legacy_companyfacts_only": ["2023-01-01", "2023-12-31"]}
    # Beside a current-writer row a legacy one is ignored, never a disagreement.
    assert tgt_result["relabels"] == [{"period_end": "2023-01-28", "from": 2023, "to": 2022, "rows": 1}]
    assert tgt_result["skipped"] == dict.fromkeys(relabel.SKIP_REASONS, 0) | {"legacy_companyfacts_only": 1}
    assert _labels(db, tgt) == [("revenue", "2023-01-28", 2022), ("revenue", "2024-02-03", 2024)]


def test_a_label_that_is_not_the_calendar_default_is_never_overwritten(db):
    """Only the per-filing writer's calendar default is the defect; any other label was set by a
    labeller (P5's annual label), and a weaker stored source never overwrites it."""
    company, filing = _company(db, "TGT")
    # The fiscal-year-window writer falls back to calendar years for a chain with no timely
    # original annual report (facts/calendar.py), so a current-writer row can name 2023 here.
    for fy in (2022, 2023):
        start, end = CALENDARS["TGT"][fy]
        _fact(db, company, concept="revenue", end=end, start=start, fiscal_year=_day(end).year)
        _fact(db, company, concept="revenue", end=end, start=start, fiscal_year=fy, source="edgar_xbrl",
              filing=filing)
    start, end = CALENDARS["TGT"][2024]
    _fact(db, company, concept="revenue", end=end, start=start, fiscal_year=2025)
    unlabelled = _fact(db, company, concept="revenue", end=end, start=start, fiscal_year=None,
                       source="edgar_xbrl", filing=filing)
    db.commit()
    before = _states(db)

    result = _apply(db, company)

    assert _states(db) == before and unlabelled.fiscal_year is None
    assert result["skipped"]["not_calendar_default"] == 3
    assert result["held"] == {"not_calendar_default": ["2023-01-28", "2024-02-03", "2025-02-01"]}


def test_an_instant_only_companyfacts_label_is_never_copied(db):
    """An instant-only label may be the oldest opening balance's calendar fallback, or one report's
    fy with no window chain to outvote a lagging focus; neither is copied."""
    company, filing = _issuer(db, "TGT")
    opening = CALENDARS["TGT"][2020][1]
    # Target's opening balance: companyfacts names the fiscal-2020 year-end balance 2021.
    _fact(db, company, concept="shareholders_equity", end=opening, fiscal_year=2021,
          raw_tag="us-gaap:StockholdersEquity")
    kept = _fact(db, company, concept="shareholders_equity", end=opening, fiscal_year=2020,
                 source="edgar_xbrl", filing=filing, raw_tag="us-gaap:StockholdersEquity")
    calendar_row = _fact(db, company, concept="cash_and_equivalents", end=opening, fiscal_year=2021,
                         source="edgar_xbrl", filing=filing, raw_tag="us-gaap:Cash")
    # A December issuer's oldest balance labelled from its original 10-K's lagging focus (fy 2018 for
    # the year ending 31 December 2019): copying it would make the correct calendar label wrong.
    dec, dec_filing = _company(db, "DEC", year=21)
    _fact(db, dec, concept="shareholders_equity", end="2019-12-31", fiscal_year=2018,
          raw_tag="us-gaap:StockholdersEquity", accession=_accession(dec, 20))
    lagged = _fact(db, dec, concept="shareholders_equity", end="2019-12-31", fiscal_year=2019,
                   source="edgar_xbrl", filing=dec_filing, raw_tag="us-gaap:StockholdersEquity")
    db.commit()

    result = _apply(db, company)
    dec_result = _apply(db, dec)

    db.refresh(kept)
    db.refresh(calendar_row)
    db.refresh(lagged)
    assert (kept.fiscal_year, calendar_row.fiscal_year, lagged.fiscal_year) == (2020, 2021, 2019)
    assert result["skipped"]["untrusted_instant_only"] == 2
    assert result["held"] == {"untrusted_instant_only": [opening]}
    assert all(r["period_end"] != opening for r in result["relabels"])
    assert dec_result["relabel_rows"] == 0 and dec_result["held"] == {"untrusted_instant_only": ["2019-12-31"]}


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
          provenance={"version": 1, "method": "reported", "validation": "unavailable",
                      "reasons": ["legacy_period_label_mismatch"]})
    for end, start in ((split, "2023-01-29"), (missing, "2024-02-04"), (quarantined, "2022-01-30")):
        _fact(db, company, concept="revenue", end=end, start=start, fiscal_year=_day(end).year,
              source="edgar_xbrl", filing=filing)
    db.commit()

    result = _apply(db, company)

    assert _labels(db, company) == [("revenue", quarantined, 2022), ("revenue", split, 2024),
                                    ("revenue", missing, 2025)]
    assert result["scanned"] == 3
    assert result["relabels"] == [{"period_end": quarantined, "from": 2023, "to": 2022, "rows": 1}]
    assert result["skipped"] == dict.fromkeys(relabel.SKIP_REASONS, 0) | {
        "companyfacts_disagree": 1, "no_companyfacts_fy": 1,
    }
    assert result["held"] == {"companyfacts_disagree": [split], "no_companyfacts_fy": [missing]}
    # The filing keeps two calendar years beside a repaired one: reported so the founder sees it.
    assert result["partial_filings"] == [filing.accession_number]


def test_only_filing_owned_fy_rows_are_relabelled(db):
    company, filing = _issuer(db, "TGT")
    end, start = CALENDARS["TGT"][2024][1], "2024-11-03"
    quarter = _fact(db, company, concept="revenue", end=end, start=start, fiscal_year=2025,
                    fiscal_period="Q4", source="edgar_xbrl", filing=filing)
    derived = _fact(db, company, concept="free_cash_flow", end=end, start="2024-02-04", fiscal_year=2025,
                    source="derived", raw_tag=None, accession="0000027419-25-000099")
    eps = _fact(db, company, concept="earnings_per_share", end=end, fiscal_year=2025, unit="USD/shares",
                source="reported_eps", raw_tag=None, accession="0000027419-25-000098")
    # Companyfacts FY rows that are no evidence and disagree with the trusted year: one a quarterly
    # repair retired, and an annual computed metric (no XBRL tag). Neither is a target either.
    retired = _fact(db, company, concept="net_income", end=end, start="2024-02-04", fiscal_year=2025,
                    raw_tag="us-gaap:NetIncomeLoss", is_latest=False,
                    provenance={"version": 1, "method": "reported", "validation": "unavailable",
                                "reasons": ["legacy_period_label_mismatch"]})
    computed = _fact(db, company, concept="net_margin", end=end, start="2024-02-04", fiscal_year=2025,
                     raw_tag=None)
    db.commit()
    others = (quarter, derived, eps, retired, computed)
    untouched = {row.id: quarterly_fact_repair.snapshot(row) for row in others}
    companyfacts = _labels(db, company, source="companyfacts")

    result = _apply(db, company)

    db.expire_all()
    assert {row.id: quarterly_fact_repair.snapshot(row) for row in others} == untouched
    assert _labels(db, company, source="companyfacts") == companyfacts
    assert result["scanned"] == 6
    assert result["relabels"][-1] == {"period_end": end, "from": 2025, "to": 2024, "rows": 2}


def test_a_filing_row_the_cross_check_sourced_from_companyfacts_is_relabelled_and_is_no_evidence(db, capsys, writer_before_1364):
    """``backfill_facts`` cross-checks headline values against companyfacts: a corrected value is
    stored with source ``companyfacts`` but keeps its filing owner and calendar label."""
    company, filing = _company(db, "TGT")
    db.commit()
    reports = {2023: (_accession(company, 24), "2024-03-13")}
    facts_service._persist_companyfacts_payload(db, company, _payload(company, reports, [2023]))
    calendar = CALENDARS["TGT"]
    standardized = {"revenue": {"series": [
        {"period": calendar[y][1], "period_start": calendar[y][0], "value": 999.0, "form": "10-K",
         "raw_tag": "us-gaap:Revenues"} for y in (2023, 2022)]}}
    authoritative = {("revenue", _day(calendar[y][1])): 10.0 * y for y in (2023, 2022)}
    facts_service.process_filing_facts(db, filing, standardized=standardized, authoritative=authoritative)
    owned = db.query(FinancialFact).filter_by(filing_id=filing.id).all()
    assert sorted((r.source, r.period_end.isoformat(), r.fiscal_year) for r in owned) == [
        ("companyfacts", "2023-01-28", 2023), ("companyfacts", "2024-02-03", 2024),
    ]

    assert relabel.main([]) == 0
    assert json.loads(capsys.readouterr().out.splitlines()[-1])["companies"] == 1
    result = _apply(db, company)

    assert result["scanned"] == 2
    assert result["relabels"] == [
        {"period_end": "2023-01-28", "from": 2023, "to": 2022, "rows": 1},
        {"period_end": "2024-02-03", "from": 2024, "to": 2023, "rows": 1},
    ]
    assert sorted((r.period_end.isoformat(), r.fiscal_year) for r in owned) == [
        ("2023-01-28", 2022), ("2024-02-03", 2023),
    ]


def test_the_trust_rule_is_the_one_the_per_filing_writer_applies(db, monkeypatch):
    """The relabel reads ``facts/fiscal_evidence``, the rule #1364's writer adopts years by, so the two
    cannot drift: a shared rule that trusts nothing holds every target here."""
    company, _filing = _issuer(db, "JNJ")
    monkeypatch.setattr(fiscal_evidence, "trusted_year", lambda evidence, legacy: (None, "companyfacts_disagree"))

    result = relabel.relabel_company(db, company.id, apply=False, run_id="shared-rule")

    assert result["relabel_rows"] == 0
    assert result["skipped"]["companyfacts_disagree"] == result["scanned"] > 0


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


def test_cli_dry_run_reads_only_scopes_by_ticker_and_limit_and_apply_commits(db, factory, capsys, monkeypatch):
    target, _filing = _issuer(db, "TGT")
    _issuer(db, "AAPL")
    db.add(Company(cik="0000000999", ticker="BARE", name="BARE"))  # a company with no filing FY rows
    db.commit()
    before = _states(db)
    locks, row_locks = [], []
    lock = facts_service._lock_fact_companies
    for_update = Query.with_for_update
    monkeypatch.setattr(facts_service, "_lock_fact_companies",
                        lambda session, facts: locks.append([f["company_id"] for f in facts]) or lock(session, facts))
    monkeypatch.setattr(Query, "with_for_update",
                        lambda query, *a, **k: row_locks.append(query.column_descriptions[0]["entity"].__name__)
                        or for_update(query, *a, **k))
    statements = []
    record = lambda c, cu, stmt, *a: statements.append(stmt)  # noqa: E731
    event.listen(db.bind, "before_cursor_execute", record)

    def run(argv):
        code = relabel.main(argv)
        return code, [json.loads(line) for line in capsys.readouterr().out.splitlines()]

    code, lines = run([])
    *companies, summary = lines
    assert code == 0 and not _writes(statements) and _states(db) == before
    assert (locks, row_locks) == ([], [])  # a dry run takes no lock
    assert all(line["dry_run"] and line["revisions"] == 0 for line in lines)
    assert [(line["ticker"], line["relabel_rows"]) for line in companies] == [("TGT", 6), ("AAPL", 0)]
    assert {k: summary[k] for k in ("companies", "companies_with_relabels", "scanned", "relabel_rows",
                                    "revisions", "failed", "partial_filings", "skipped")} == {
        "companies": 2, "companies_with_relabels": 1, "scanned": 12, "relabel_rows": 6, "revisions": 0,
        "failed": 0, "partial_filings": 0,
        "skipped": dict.fromkeys(relabel.SKIP_REASONS, 0) | {"already_agrees": 6},
    }
    code, lines = run(["--limit", "1"])
    assert code == 0 and [line.get("ticker") for line in lines] == ["TGT", None]
    code, lines = run(["--tickers", "bare,aapl"])  # a named company is reported even with nothing to scan
    assert code == 0 and [(line.get("ticker"), line["scanned"]) for line in lines[:-1]] == [("AAPL", 6), ("BARE", 0)]
    assert not _writes(statements) and _states(db) == before
    event.remove(db.bind, "before_cursor_execute", record)

    code, lines = run(["--apply", "--tickers", "TGT"])

    assert code == 0 and not lines[-1]["dry_run"] and lines[-1]["revisions"] == 6
    assert locks == [[target.id]] and "FinancialFact" in row_locks  # the writers' lock, then its rows
    with factory() as fresh:  # committed: a new session sees the labels and the journal
        assert _labels(fresh, target) == [
            ("revenue", "2023-01-28", 2022), ("revenue", "2024-02-03", 2023), ("revenue", "2025-02-01", 2024),
            ("shareholders_equity", "2023-01-28", 2022), ("shareholders_equity", "2024-02-03", 2023),
            ("shareholders_equity", "2025-02-01", 2024),
        ]
        assert fresh.query(FinancialFactRevision).filter_by(run_id=lines[0]["run_id"]).count() == 6
    code, lines = run(["--tickers", "NOPE"])
    assert code == 1 and "NOPE" in lines[0]["error"]


def test_a_failing_company_rolls_back_alone_and_fails_the_exit_code(db, factory, capsys, monkeypatch):
    target, _filing = _issuer(db, "TGT")
    jnj, _filing = _issuer(db, "JNJ")
    before = _states(db)
    plan = relabel.relabel_company

    def failing_for_target(session, company_id, **kwargs):
        result = plan(session, company_id, **kwargs)  # its relabels are flushed before it fails
        if company_id == target.id:
            raise RuntimeError("simulated failure")
        return result

    monkeypatch.setattr(relabel, "relabel_company", failing_for_target)

    assert relabel.main(["--apply"]) == 1

    *lines, summary = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert lines[0] == {"company_id": target.id, "ticker": "TGT", "error": "simulated failure"}
    assert lines[1]["ticker"] == "JNJ" and lines[1]["revisions"] == 4
    assert (summary["failed"], summary["companies"], summary["revisions"]) == (1, 2, 4)
    with factory() as fresh:
        states = {row.id: quarterly_fact_repair.snapshot(row) for row in fresh.query(FinancialFact)}
        assert {k: v for k, v in states.items() if v["company_id"] == target.id} == {
            k: v for k, v in before.items() if v["company_id"] == target.id
        }
        assert {r.company_id for r in fresh.query(FinancialFactRevision)} == {jnj.id}


def test_unlabelled_annual_points_from_the_production_writers_are_repaired(db, writer_before_1364):
    """Production writers: a stale companyfacts sync, then the newest 10-K opened, then a resync."""
    company, filing = _company(db, "TGT")
    db.commit()
    reports = {2023: (_accession(company, 24), "2024-03-13"), 2024: (filing.accession_number, "2025-03-12")}
    facts_service._persist_companyfacts_payload(db, company, _payload(company, reports, [2023]))
    facts_service.process_filing_facts(db, filing, standardized=_unlabelled_annual_points(company, (2024, 2023, 2022)))
    resync = facts_service._persist_companyfacts_payload(db, company, _payload(company, reports, [2023, 2024]))
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
    # row for it: it is reported, never guessed, and the filing is listed as partly repaired, on
    # this run and on every later one.
    assert result["held"] == {"no_companyfacts_fy": ["2025-02-01"]}
    assert result["partial_filings"] == [filing.accession_number]
    again = relabel.relabel_company(db, company.id, apply=False, run_id="again")
    assert (again["relabel_rows"], again["partial_filings"]) == (0, [filing.accession_number])


def test_a_relabel_that_would_give_two_period_ends_of_a_filing_one_year_is_held(db):
    """Production writers: the 2024 10-K opened before the first companyfacts sync, the 2025 one never.

    The sync skips the identities the filing already owns, so the filing's oldest year has no
    companyfacts row; relabelling the newer years alone would give two of its period ends one year.
    """
    company, filing = _company(db, "TGT", year=24)
    db.commit()
    reports = {2023: (filing.accession_number, "2024-03-13"), 2024: (_accession(company, 25), "2025-03-12")}
    facts_service.process_filing_facts(db, filing, standardized=_unlabelled_annual_points(company, (2023, 2022, 2021)))
    sync = facts_service._persist_companyfacts_payload(db, company, _payload(company, reports, [2023, 2024]))
    assert (sync["inserted"], sync["skipped"]) == (6, 2)
    chart = _chart(db, filing)
    assert chart["revenue"] == [("2022-01-29", 2022), ("2023-01-28", 2023), ("2024-02-03", 2024)]
    before = _states(db)

    result = _apply(db, company)

    assert result["relabels"] == [] and result["revisions"] == 0 and _states(db) == before
    assert _chart(db, filing) == chart
    assert result["skipped"] == dict.fromkeys(relabel.SKIP_REASONS, 0) | {
        "label_collision": 4, "no_companyfacts_fy": 2,
    }
    assert result["held"] == {"label_collision": ["2023-01-28", "2024-02-03"], "no_companyfacts_fy": ["2022-01-29"]}
    # Once a later filing supersedes the rows they are no longer current, but this filing's chart
    # still reads them: the hold does not depend on the current rows.
    for row in db.query(FinancialFact).filter_by(filing_id=filing.id):
        row.is_latest = False
    db.commit()
    again = relabel.relabel_company(db, company.id, apply=False, run_id="superseded")
    assert again["relabels"] == [] and again["skipped"]["label_collision"] == 4


def test_a_relabel_that_would_give_two_current_rows_of_a_concept_one_year_is_held(db):
    """Annual readers index current rows by (fiscal year, concept): a relabel must not duplicate one."""
    company, filing = _company(db, "TGT")
    calendar = CALENDARS["TGT"]
    # A current legacy companyfacts row names fiscal 2021's end by its calendar year, 2022.
    _fact(db, company, concept="revenue", end=calendar[2021][1], start=calendar[2021][0], fiscal_year=2022,
          provenance=LEGACY)
    start, end = calendar[2022]
    _fact(db, company, concept="revenue", end=end, start=start, fiscal_year=2022, is_latest=False)
    row = _fact(db, company, concept="revenue", end=end, start=start, fiscal_year=2023, source="edgar_xbrl",
                filing=filing)
    db.commit()

    result = _apply(db, company)

    db.refresh(row)
    assert row.fiscal_year == 2023 and result["relabel_rows"] == 0
    assert result["held"] == {"label_collision": [end]}


def _jnj_before_any_sync(db):
    """J&J's 2023 10-K as the per-filing writer stored it before P5, and no companyfacts row anywhere:
    the state the first dry run found (``no_companyfacts_fy`` at every J&J year end)."""
    company, filing = _company(db, "JNJ", year=24)
    for start, end in CALENDARS["JNJ"].values():
        _fact(db, company, concept="revenue", end=end, start=start, fiscal_year=_day(end).year,
              source="edgar_xbrl", filing=filing)
        _fact(db, company, concept="shareholders_equity", end=end, fiscal_year=_day(end).year,
              source="edgar_xbrl", filing=filing, raw_tag="us-gaap:StockholdersEquity", value=50.0)
    db.commit()
    return company, filing


def test_a_year_end_no_stored_row_vouches_for_takes_the_year_the_sec_read_names(db, capsys, sec):
    company, filing = _jnj_before_any_sync(db)
    assert [year for _end, year in _chart(db, filing)["revenue"]] == [2022, 2023, 2023]
    sec.payloads[company.cik] = _payload(company, {2023: (filing.accession_number, "2024-02-16")}, [2023])

    assert relabel.main([]) == 0
    preview, summary = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert relabel.main(["--apply"]) == 0
    applied, _summary = [json.loads(line) for line in capsys.readouterr().out.splitlines()]

    for line in (preview, applied):
        assert line["relabels"] == [
            {"period_end": "2022-01-02", "from": 2022, "to": 2021, "rows": 2},
            {"period_end": "2023-01-01", "from": 2023, "to": 2022, "rows": 2},
        ]
        assert line["sec_evidence"] == 6 and line["skipped"]["already_agrees"] == 2
    assert summary["sec_evidence"] == 6 and preview["revisions"] == 0 and applied["revisions"] == 4
    assert [year for _end, year in _chart(db, filing)["revenue"]] == [2021, 2022, 2023]
    assert sec.reads == [company.cik, company.cik]  # one read per company per run
    assert db.query(FinancialFact).filter_by(company_id=company.id, source="companyfacts").count() == 0


def test_stored_evidence_outranks_the_sec_read(db):
    company, _filing = _issuer(db, "TGT")
    rows = db.query(FinancialFact).filter_by(company_id=company.id).all()
    # A read naming every stored companyfacts year one later changes nothing where stored rows vouch.
    read = [SimpleNamespace(source="companyfacts", filing_id=None, raw_tag=row.raw_tag, fiscal_period="FY",
                            fiscal_year=row.fiscal_year + 1, provenance=row.provenance,
                            period_start=row.period_start, period_end=row.period_end)
            for row in rows if row.filing_id is None]

    plan = relabel.plan_company(rows, read)

    assert plan == relabel.plan_company(rows) and plan["sec_evidence"] == 0 and len(plan["relabel"]) == 6


def test_the_sec_read_vouches_for_the_year_the_filing_owns_so_its_newer_years_relabel_too(db, sec):
    """The production state behind the label-collision case above: the 2024 10-K opened before the first
    companyfacts sync, which then skipped the identities the filing owns, so no stored row vouches for
    the filing's oldest year. The SEC read names it, and the filing's three years relabel together."""
    company, filing = _company(db, "TGT", year=24)
    db.commit()
    reports = {2023: (filing.accession_number, "2024-03-13"), 2024: (_accession(company, 25), "2025-03-12")}
    facts_service.process_filing_facts(db, filing, standardized=_unlabelled_annual_points(company, (2023, 2022, 2021)))
    sec.payloads[company.cik] = payload = _payload(company, reports, [2023, 2024])
    facts_service._persist_companyfacts_payload(db, company, payload)

    result = relabel.relabel_company(db, company.id, apply=True, run_id="read",
                                     read=relabel.companyfacts_read(company.id, company.cik, company.sic))
    db.commit()

    assert result["relabels"] == [
        {"period_end": "2022-01-29", "from": 2022, "to": 2021, "rows": 2},
        {"period_end": "2023-01-28", "from": 2023, "to": 2022, "rows": 2},
        {"period_end": "2024-02-03", "from": 2024, "to": 2023, "rows": 2},
    ]
    assert result["sec_evidence"] == 2 and result["skipped"] == dict.fromkeys(relabel.SKIP_REASONS, 0)
    assert _chart(db, filing)["revenue"] == [("2022-01-29", 2021), ("2023-01-28", 2022), ("2024-02-03", 2023)]


def test_a_failed_sec_read_fails_its_company_alone_before_its_session_opens(db, factory, capsys, monkeypatch, sec):
    target, _filing = _issuer(db, "TGT")
    jnj, _filing = _issuer(db, "JNJ")
    before = _states(db)
    sec.payloads[target.cik] = None
    events = []
    read = facts_service._fetch_companyfacts_sync
    monkeypatch.setattr(facts_service, "_fetch_companyfacts_sync", lambda cik: events.append(cik) or read(cik))
    monkeypatch.setattr(database, "SessionLocal", lambda: events.append("session") or factory())

    assert relabel.main(["--apply"]) == 1

    *lines, summary = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert lines[0] == {"company_id": target.id, "ticker": "TGT",
                        "error": "companyfacts read from SEC failed; company unchanged"}
    assert lines[1]["ticker"] == "JNJ" and lines[1]["revisions"] == 4
    assert (summary["failed"], summary["revisions"]) == (1, 4)
    assert events == ["session", target.cik, jnj.cik, "session"]  # the cohort read, then read before session
    with factory() as fresh:
        states = {row.id: quarterly_fact_repair.snapshot(row) for row in fresh.query(FinancialFact)}
        assert {k: v for k, v in states.items() if v["company_id"] == target.id} == {
            k: v for k, v in before.items() if v["company_id"] == target.id
        }


def test_a_read_row_the_stored_rule_rejects_is_no_evidence(db):
    company, _filing = _jnj_before_any_sync(db)
    rows = db.query(FinancialFact).filter_by(company_id=company.id).all()
    start, end = CALENDARS["JNJ"][2021]
    fact = {"filing_id": None, "raw_tag": "us-gaap:Revenues", "fiscal_period": "FY", "fiscal_year": 2021,
            "period_start": _day(start), "period_end": _day(end)}
    read = [SimpleNamespace(**fact, source="derived", provenance=reported_provenance({"reconciled": True})),
            SimpleNamespace(**fact, source="companyfacts",
                            provenance=reported_provenance({"reconciled": True}) | {"validation": "unavailable"})]

    plan = relabel.plan_company(rows, read)

    assert plan["relabel"] == [] and plan["sec_evidence"] == 0
    assert plan["held"] == {"no_companyfacts_fy": ["2022-01-02", "2023-01-01", "2023-12-31"]}
