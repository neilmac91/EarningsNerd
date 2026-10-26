"""A filing's annual chart shows every figure the filing reported, whichever fact writer stored it.

The fact identity (company, concept, period end, fiscal period, unit, accession) holds the accession,
and both writers skip an identity already stored (``facts/upsert.py``). A companyfacts sync stores
each period's winner under the accession of the filing that reported it last, with no filing owner.
When a sync runs before a filing's own facts are written, the per-filing writer adds no row for those
cells, so a chart read by ``filing_id`` misses them: every year of the newest annual report, the
oldest year and balance of an older one. These tests plant both orders through the real writers
(``_persist_companyfacts_payload`` and ``process_filing_facts``) and read the chart the filing page
reads (``get_filing_fundamentals``).
"""
from __future__ import annotations

import json
import random
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from app.database import SessionLocal
from app.models import Company, Filing, FinancialFact
from app.services import copilot_tools, facts_service, quarterly_fact_repair
from app.utils.sec_urls import build_sec_archive_url

REV = "RevenueFromContractWithCustomerExcludingAssessedTax"
CONCEPTS = {REV: "revenue", "Revenues": "revenue", "NetIncomeLoss": "net_income",
            "GrossProfit": "gross_profit", "Assets": "total_assets",
            "EarningsPerShareBasic": "earnings_per_share", "EarningsPerShareDiluted": "eps_diluted"}


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


def _company(db) -> Company:
    cik = str(random.randrange(10**6, 10**9))
    company = Company(cik=cik, ticker=f"T{uuid.uuid4().hex[:8]}".upper(), name=f"Co {cik}")
    db.add(company)
    db.commit()
    return company


def _accession(company: Company, year: int, serial: int = 10) -> str:
    return f"{int(company.cik):010d}-{year % 100:02d}-{serial:06d}"


def _start(end: str) -> str:
    """The start of the 52-week-or-so year that ends on ``end`` (an FY span to the collector)."""
    return (date.fromisoformat(end) - timedelta(days=364)).isoformat()


def _report(accn: str, fy: int, *, form: str = "10-K", filed: str | None = None, unit: str = "USD",
            year_end: str = "12-31", **lines: dict[int, float]) -> dict[str, list[dict]]:
    """One report's companyfacts items, by tag: ``lines`` maps a tag to its {year: value}. A flow runs
    the year to ``year_end``; ``Assets`` is the balance on that date."""
    items: dict[str, list[dict]] = {}
    for tag, values in lines.items():
        for year, value in values.items():
            end = f"{year}-{year_end}"
            item = {"val": value, "end": end, "accn": accn, "fy": fy, "fp": "FY", "form": form,
                    "filed": filed or f"{fy + 1}-02-15", "unit": unit}
            if tag != "Assets":
                item["start"] = _start(end)
            items.setdefault(tag, []).append(item)
    return items


def _payload(*reports: dict[str, list[dict]]) -> dict:
    """A companyfacts payload holding these reports' items, in filing order, per tag and unit."""
    usgaap: dict[str, dict] = {}
    for report in reports:
        for tag, items in report.items():
            for item in items:
                entry = {key: value for key, value in item.items() if key != "unit"}
                usgaap.setdefault(tag, {"units": {}})["units"].setdefault(item["unit"], []).append(entry)
    return {"cik": 1, "entityName": "TEST CO", "facts": {"us-gaap": usgaap}}


def _standardized(report: dict[str, list[dict]]) -> dict:
    """What the per-filing extractor hands the writer for this report: one series per concept from the
    one revenue tag it reads, and its margins over the report's own revenue (``xbrl_standardized``)."""
    standardized: dict[str, dict] = {}
    for tag in (REV, "NetIncomeLoss", "GrossProfit", "Assets", "EarningsPerShareBasic", "EarningsPerShareDiluted"):
        for item in report.get(tag, []):
            code = item["unit"].partition("/")[0]  # a per-share point carries its currency, as the extractor's does
            point = {"period": item["end"], "value": item["val"], "form": item["form"], "raw_tag": f"us-gaap:{tag}",
                     "currency": None if code == "USD" else code}
            if "start" in item:
                point["period_start"] = item["start"]
            standardized.setdefault(CONCEPTS[tag], {"series": []})["series"].append(point)
    revenue = {p["period"]: p for p in standardized.get("revenue", {}).get("series", [])}
    for margin, numerator in (("net_margin", "net_income"), ("gross_margin", "gross_profit")):
        points = [{"period": p["period"], "value": p["value"] / revenue[p["period"]]["value"] * 100, "form": p["form"]}
                  for p in standardized.get(numerator, {}).get("series", []) if p["period"] in revenue]
        if points:
            standardized[margin] = {"series": points}
    return standardized


def _filing(db, company: Company, report: dict[str, list[dict]]) -> Filing:
    """The Filing row of a report ``_report`` built: its accession, form, filed date and own period end."""
    item = max((item for items in report.values() for item in items), key=lambda item: item["end"])
    url = build_sec_archive_url(company.cik, item["accn"])
    filing = Filing(company_id=company.id, accession_number=item["accn"], filing_type=item["form"],
                    filing_date=datetime.fromisoformat(item["filed"]).replace(tzinfo=timezone.utc),
                    period_end_date=datetime.fromisoformat(item["end"]).replace(tzinfo=timezone.utc),
                    sec_url=url, document_url=f"{url}report.htm")
    db.add(filing)
    db.commit()
    return filing


def _sync(db, company: Company, *reports) -> dict:
    return facts_service._persist_companyfacts_payload(db, company, _payload(*reports))


def _process(db, filing: Filing, report) -> dict:
    return facts_service.process_filing_facts(db, filing, standardized=_standardized(report))


def _chart(db, filing: Filing) -> dict[str, list[tuple]]:
    """The filing page's annual chart: each concept's (period end, value, unit, accession) points."""
    db.expire_all()
    chart = facts_service.get_filing_fundamentals(db, filing.id)
    return {series["concept"]: [(p["period_end"], p["value"], p["unit"], p["accession"]) for p in series["points"]]
            for series in chart["concepts"]}


def _own(report: dict[str, list[dict]], tag: str) -> list[tuple]:
    """A report's own points for one tag, as the chart lists them (oldest first)."""
    return sorted((item["end"], item["val"], item["unit"], item["accn"]) for item in report[tag])


def _margins(filing: Filing, years, value: float) -> list[tuple]:
    return [(f"{year}-12-31", pytest.approx(value), "pure", filing.accession_number) for year in years]


def _calendar(company: Company, year_end: str = "12-31") -> dict[int, dict[str, list[dict]]]:
    """Three timely 10-Ks: each reports three years of revenue and net income, and two balances."""
    def report(fy: int) -> dict[str, list[dict]]:
        years = (fy - 2, fy - 1, fy)
        return _report(_accession(company, fy + 1), fy, year_end=year_end, **{
            REV: {y: 100.0 * (y - 2000) for y in years}, "NetIncomeLoss": {y: 10.0 * (y - 2000) for y in years},
            "Assets": {y: 1000.0 * (y - 2000) for y in years[1:]},
        })
    return {fy: report(fy) for fy in (2022, 2023, 2024)}


# --- The mechanism, in both orders -------------------------------------------------------------------


@pytest.mark.parametrize("fy,skipped", [(2024, 11), (2023, 4)], ids=["newest-report", "older-report"])
def test_a_report_processed_after_a_sync_charts_every_year_it_reported(db, fy, skipped):
    company = _company(db)
    reports = _calendar(company)
    filings = {year: _filing(db, company, report) for year, report in reports.items()}
    _sync(db, company, *reports.values())

    result = _process(db, filings[fy], reports[fy])

    # The cause: the sync already stored the cells this report reported last, under its accession and
    # with no filing owner, so the per-filing writer skips them. The newest report reported all eleven
    # (three years of revenue, net income and net margin, two balances) last; an older one its oldest
    # year's three and its older balance.
    assert (result["skipped"], result["inserted"]) == (skipped, 11 - skipped)
    chart = _chart(db, filings[fy])
    assert chart["revenue"] == _own(reports[fy], REV)
    assert chart["net_income"] == _own(reports[fy], "NetIncomeLoss")
    assert chart["total_assets"] == _own(reports[fy], "Assets")
    assert chart["net_margin"] == _margins(filings[fy], (fy - 2, fy - 1, fy), 10.0)


def test_a_report_processed_before_a_sync_keeps_its_rows_and_its_chart(db):
    company = _company(db)
    reports = _calendar(company)
    filing = _filing(db, company, reports[2024])
    _process(db, filing, reports[2024])
    before = _chart(db, filing)

    # A later 10-K restates 2023 and 2024 revenue; the sync stores it with the reports it supersedes.
    restating = _report(_accession(company, 2026), 2025, **{REV: {2023: 2400.0, 2024: 2500.0, 2025: 2600.0}})
    _filing(db, company, restating)
    result = _sync(db, company, *reports.values(), restating)

    # Every identity the report owns is left as it is: 2022 revenue, net income, both balances, and
    # the 2022 net margin over the report's own operands (2023 and 2024 margins take the new revenue).
    assert result["skipped"] == 7
    rows = db.query(FinancialFact).filter_by(company_id=company.id, accession=filing.accession_number).all()
    assert {row.filing_id for row in rows} == {filing.id}
    assert {(row.concept, row.period_end.year) for row in rows if not row.is_latest} == {
        ("revenue", 2023), ("revenue", 2024), ("net_margin", 2023), ("net_margin", 2024)}
    assert _chart(db, filing) == before  # the sync demotes the report's rows; the chart keeps them
    assert before["revenue"] == _own(reports[2024], REV)


def test_a_later_restatement_never_changes_an_older_reports_chart(db):
    company = _company(db)
    reports = _calendar(company)
    older, newer = _filing(db, company, reports[2023]), _filing(db, company, reports[2024])
    _process(db, older, reports[2023])  # opened before any sync: it owns every cell it reported
    _sync(db, company, *reports.values())
    _process(db, newer, reports[2024])  # opened after it: the sync holds every one of its cells
    charts = {older.id: _chart(db, older), newer.id: _chart(db, newer)}

    restating = _report(_accession(company, 2026), 2025, **{
        REV: {2023: 2400.0, 2024: 2500.0, 2025: 2600.0}, "NetIncomeLoss": {2023: 240.0, 2024: 250.0, 2025: 260.0},
        "Assets": {2024: 25000.0, 2025: 26000.0},
    })
    latest = _filing(db, company, restating)
    _sync(db, company, *reports.values(), restating)
    _process(db, latest, restating)

    assert _chart(db, older) == charts[older.id]
    assert _chart(db, newer) == charts[newer.id]
    assert charts[newer.id]["revenue"] == _own(reports[2024], REV)
    assert _chart(db, latest)["revenue"] == _own(restating, REV)
    current = {(row.accession, row.period_end.year) for row in db.query(FinancialFact).filter_by(
        company_id=company.id, concept="revenue", fiscal_period="FY", is_latest=True)}
    assert (newer.accession_number, 2024) not in current  # demoted, and still on its report's chart


# --- What may stand in for a filing's own row --------------------------------------------------------


def test_a_calculation_stands_in_only_when_this_report_gave_every_operand(db):
    company = _company(db)
    k24 = _report(_accession(company, 2025), 2024, **{
        REV: {2022: 800.0, 2023: 1000.0, 2024: 1200.0}, "NetIncomeLoss": {2022: 80.0, 2023: 100.0, 2024: 120.0},
        "GrossProfit": {2022: 400.0, 2023: 500.0, 2024: 600.0},
    })
    # An 8-K recast restates net income after the 10-K; its items win those years.
    recast = _report(_accession(company, 2025, 50), 2024, form="8-K", filed="2025-06-01",
                     **{"NetIncomeLoss": {2023: 90.0, 2024: 110.0}})
    filing = _filing(db, company, k24)
    _sync(db, company, k24, recast)
    _process(db, filing, k24)

    # The sync's net margin takes revenue's accession, this report's; for 2023 and 2024 its numerator
    # is the recast's. It holds the report's own margin cells, so those years show no margin, and the
    # 2022 margin alone (both operands the report's) is a line short of the report's year: none shows.
    stored = db.query(FinancialFact).filter_by(company_id=company.id, concept="net_margin",
                                               accession=filing.accession_number).all()
    assert sorted((row.period_end.year, row.filing_id) for row in stored) == [(2022, None), (2023, None), (2024, None)]
    chart = _chart(db, filing)
    assert "net_margin" not in chart
    assert chart["gross_margin"] == _margins(filing, (2022, 2023, 2024), 50.0)
    assert chart["net_income"] == _own(k24, "NetIncomeLoss")  # the report's own figures, not the recast's


def test_a_retired_or_unproven_row_never_stands_in_and_a_legacy_reported_one_does(db):
    company = _company(db)
    reports = _calendar(company)
    filing = _filing(db, company, reports[2024])
    _sync(db, company, *reports.values())

    def plant(concept, value, *, end=date(2024, 12, 31), source="companyfacts", raw_tag="us-gaap:Line", start=None):
        row = FinancialFact(company_id=company.id, filing_id=None, concept=concept, raw_tag=raw_tag, unit="USD",
                            period_start=start, period_end=end, fiscal_year=end.year, fiscal_period="FY",
                            value=value, form="10-K", accession=filing.accession_number, source=source,
                            reconciled=True, is_latest=True, provenance=None)
        db.add(row)
        db.flush()
        return row

    # Stored before provenance was recorded: a reported line, and two calculations with no operands.
    plant("cash_and_equivalents", 55.0, raw_tag="us-gaap:CashAndCashEquivalentsAtCarryingValue")
    plant("free_cash_flow", 66.0, source="derived", raw_tag=None)
    plant("operating_margin", 7.0, raw_tag=None)  # an early companyfacts calculation
    # A row the audited repair retired: an FY label on the year's fourth quarter, at the report's own
    # period end, so only its retirement keeps it off the chart.
    retired = plant("operating_income", 77.0, start=date(2024, 10, 1))
    state = quarterly_fact_repair._quarantine(quarterly_fact_repair.snapshot(retired), "legacy_period_label_mismatch")
    retired.provenance, retired.reconciled, retired.is_latest = state["provenance"], False, False
    db.commit()
    _process(db, filing, reports[2024])

    payload = facts_service.get_filing_fundamentals(db, filing.id)
    series = {s["concept"]: s["points"] for s in payload["concepts"]}
    assert not {"free_cash_flow", "operating_margin", "operating_income"} & series.keys()
    [cash] = series["cash_and_equivalents"]
    assert cash["value"] == 55.0
    assert (cash["provenance"]["method"], cash["provenance"]["validation"]) == ("reported", "passed")
    assert cash["provenance"]["source_url"] == build_sec_archive_url(company.cik, filing.accession_number)
    assert series["revenue"][0]["provenance"]["filed_at"] == "2025-02-15"  # the sync's own record


@pytest.mark.parametrize("held", [2021, 2023], ids=["before-the-own-rows", "after-the-own-rows"])
def test_a_stand_in_takes_the_year_the_reports_own_rows_count_to_its_period(db, held):
    """A companyfacts row stored before the fiscal-year-window writer names its year by the calendar year
    of its end. Target names a year by its start: its report for the year to 3 February 2024 is fiscal
    2023, and the year to 29 January 2022 is fiscal 2021, not 2022. A stand-in before the report's own
    rows is counted back from the latest of them, one after them (its own year, held as a year's
    own-report row holds it) forward, and never from a stand-in, whose label would name the anchor."""
    company = _company(db)
    accn = _accession(company, 2024)
    ends = {2021: "2022-01-29", 2022: "2023-01-28", 2023: "2024-02-03"}
    report = {REV: [{"val": 100.0 * (fy - 2000), "start": _start(end), "end": end, "accn": accn, "fy": 2023,
                     "fp": "FY", "form": "10-K", "filed": "2024-03-13", "unit": "USD"} for fy, end in ends.items()]}
    filing = _filing(db, company, report)
    end = date.fromisoformat(ends[held])
    facts_service.upsert_facts_bulk(db, [{
        "company_id": company.id, "filing_id": None, "concept": "revenue", "raw_tag": f"us-gaap:{REV}", "unit": "USD",
        "period_start": date.fromisoformat(_start(ends[held])), "period_end": end, "fiscal_year": end.year,
        "fiscal_period": "FY", "value": 100.0 * (held - 2000), "form": "10-K", "accession": accn,
        "source": "companyfacts", "reconciled": True,
    }])
    standardized = _standardized(report)  # the extractor names each year from the report's own focus
    for point, fy in zip(standardized["revenue"]["series"], ends):
        point["fiscal_year"] = fy
    facts_service.process_filing_facts(db, filing, standardized=standardized)

    db.expire_all()
    [revenue] = [s for s in facts_service.get_filing_fundamentals(db, filing.id)["concepts"] if s["concept"] == "revenue"]
    assert [(p["period_end"], p["fiscal_year"], p["value"]) for p in revenue["points"]] == [
        (ends[2021], 2021, 2100.0), (ends[2022], 2022, 2200.0), (ends[2023], 2023, 2300.0)]
    assert db.query(FinancialFact).filter_by(company_id=company.id, period_end=end).one().fiscal_year == end.year


@pytest.mark.parametrize("fy", [2024, 2023], ids=["newest-report", "older-report"])
def test_an_unprocessed_report_charts_nothing_until_its_own_writer_runs(db, fy):
    company = _company(db)
    reports = _calendar(company)
    filing = _filing(db, company, reports[fy])
    _sync(db, company, *reports.values())
    # The sync holds the cells the report reported last: every one of the newest report's, whose lines
    # reach its own year, and an older one's oldest year and older balance. Until the per-filing writer
    # has run, the lines and years it adds are missing, and a chart without them would read as all the
    # report disclosed.
    assert filing.processed_facts_at is None
    assert _chart(db, filing) == {}

    _process(db, filing, reports[fy])
    assert _chart(db, filing)["revenue"] == _own(reports[fy], REV)


# --- A stand-in shows only in a line that reaches the filing's own period end ------------------------


def test_a_line_short_of_the_reports_own_year_charts_only_the_reports_own_rows(db):
    """For a line the per-filing writer read no current year of, the rows the sync stored under an older
    report's accession are the cells it reported last, its oldest year: alone, or beside the report's
    own comparative, they would read as all it disclosed. Such a line keeps the report's own rows only."""
    company = _company(db)
    reports = _calendar(company)
    filing = _filing(db, company, reports[2023])
    _sync(db, company, *reports.values())
    # The extractor read no net income from this report, and revenue for its two comparative years only.
    read = {REV: reports[2023][REV][:2], "Assets": reports[2023]["Assets"]}
    facts_service.process_filing_facts(db, filing, standardized=_standardized(read))

    rows = db.query(FinancialFact).filter_by(company_id=company.id, accession=filing.accession_number).all()
    assert {(row.concept, row.period_end.year) for row in rows if row.filing_id is None} == {
        ("revenue", 2021), ("net_income", 2021), ("net_margin", 2021), ("total_assets", 2022)}
    chart = _chart(db, filing)
    assert chart.keys() == {"revenue", "total_assets"}
    assert chart["revenue"] == _own(reports[2023], REV)[1:2]  # its own 2022 row, as before any stand-in
    assert chart["total_assets"] == _own(reports[2023], "Assets")  # reaches 2023, so its older balance shows


@pytest.mark.parametrize("sync_first", [True, False], ids=["synced-first", "processed-first"])
@pytest.mark.parametrize("year_end,quarter,filed", [
    ("12-31", ("2025-01-01", "2025-03-31"), ("2025-02-15", "2025-05-01")),
    ("09-28", ("2024-09-29", "2024-12-28"), ("2024-11-01", "2025-01-31")),
], ids=["december-year", "september-year"])
def test_an_interim_report_charts_no_annual_line(db, sync_first, year_end, quarter, filed):
    """A 10-Q's comparative balance is the prior year-end's. The sync labels that instant FY and stores
    it under the 10-Q's accession while the 10-Q filed it last; the per-filing writer stores no FY row
    for an interim report, so that row holds none of its cells, and its line ends a quarter before the
    10-Q's own period: the 10-Q's page shows no annual chart. For a year ending by September (Apple's
    first quarter ends in the December after it) both dates fall in one calendar year: only the
    distance in days keeps the line short of the 10-Q's period."""
    company = _company(db)
    prior = f"2024-{year_end}"  # the year end the 10-K reports and the 10-Q compares with
    annual = _report(_accession(company, 2025), 2024, year_end=year_end, filed=filed[0], **{
        REV: {2022: 2200.0, 2023: 2300.0, 2024: 2400.0}, "Assets": {2023: 23000.0, 2024: 24000.0}})
    common = {"accn": _accession(company, 2025, 40), "fy": 2025, "fp": "Q1", "form": "10-Q", "filed": filed[1],
              "unit": "USD"}
    interim = {REV: [{**common, "val": 330.0, "start": quarter[0], "end": quarter[1]}],
               "Assets": [{**common, "val": 24000.0, "end": prior}, {**common, "val": 24100.0, "end": quarter[1]}]}
    _filing(db, company, annual)
    filing = _filing(db, company, interim)
    steps = [lambda: _sync(db, company, annual, interim), lambda: _process(db, filing, interim)]
    for step in steps if sync_first else steps[::-1]:
        step()

    [held] = db.query(FinancialFact).filter_by(company_id=company.id, accession=filing.accession_number,
                                               fiscal_period="FY").all()
    assert (held.concept, held.period_end, held.filing_id) == ("total_assets", date.fromisoformat(prior), None)
    assert _chart(db, filing) == {}


def test_a_report_with_no_period_end_on_record_charts_only_its_own_rows(db):
    """With no period of report, no line can be shown to reach it, so no stand-in shows: the newest
    report, whose every cell the sync holds, charts nothing; an older one charts the years it owns."""
    company = _company(db)
    reports = _calendar(company)
    older, newest = _filing(db, company, reports[2023]), _filing(db, company, reports[2024])
    older.period_end_date = newest.period_end_date = None
    db.commit()
    _sync(db, company, *reports.values())
    _process(db, older, reports[2023])
    _process(db, newest, reports[2024])

    assert _chart(db, newest) == {}
    chart = _chart(db, older)
    assert chart["revenue"] == _own(reports[2023], REV)[1:]
    assert chart["total_assets"] == _own(reports[2023], "Assets")[1:]


@pytest.mark.parametrize("reported,reaches", [("2025-01-01", True), ("2025-02-15", False)],
                         ids=["a-day-after", "the-filing-date"])
def test_a_line_reaches_a_period_of_report_a_day_off_its_year_end(db, reported, reaches):
    """The period of report is EDGAR's submissions ``reportDate``, not a date read from the XBRL contexts
    the rows came from. The two name the same day in nearly every annual report, 52/53-week calendars
    included. The odd one is a day apart, which still reaches, across a calendar year too: here
    1 January for a year to 31 December. A filer that gave its filing date instead (Tractor Supply's
    2014 and 2015 10-Ks, 53 days on; here 46) falls outside the 18 days, though inside the quarter
    that keeps a 10-Q's prior year-end out: the report keeps its own rows only, as before this reader
    (the newest report owns none)."""
    company = _company(db)
    reports = _calendar(company)
    filing = _filing(db, company, reports[2024])
    filing.period_end_date = datetime.fromisoformat(reported).replace(tzinfo=timezone.utc)
    db.commit()
    _sync(db, company, *reports.values())
    _process(db, filing, reports[2024])

    chart = _chart(db, filing)
    assert chart == ({"revenue": _own(reports[2024], REV), "net_income": _own(reports[2024], "NetIncomeLoss"),
                      "net_margin": _margins(filing, (2022, 2023, 2024), 10.0),
                      "total_assets": _own(reports[2024], "Assets")} if reaches else {})


def test_another_companys_rows_under_the_same_accession_stay_out(db):
    parent, subsidiary = _company(db), _company(db)
    report = _calendar(parent)[2024]
    filing = _filing(db, parent, report)
    # A combined 10-K: the co-registrant's companyfacts names the same accession.
    _sync(db, subsidiary, _report(filing.accession_number, 2024, **{REV: {2022: 1.0, 2023: 2.0, 2024: 3.0}}))
    _sync(db, parent, report)
    _process(db, filing, report)

    assert _chart(db, filing)["revenue"] == _own(report, REV)


def test_quarters_stored_under_an_annual_reports_accession_never_chart(db):
    company = _company(db)
    report = _calendar(company)[2024]
    filing = _filing(db, company, report)
    facts_service.upsert_facts_bulk(db, [{
        "company_id": company.id, "filing_id": None, "concept": "revenue", "raw_tag": f"us-gaap:{REV}",
        "unit": "USD", "period_start": date(2024, 10, 1), "period_end": date(2024, 12, 31), "fiscal_year": 2024,
        "fiscal_period": "Q4", "value": 600.0, "form": "10-K", "accession": filing.accession_number,
        "source": "companyfacts", "reconciled": True,
    }])
    _sync(db, company, report)
    _process(db, filing, report)

    assert _chart(db, filing)["revenue"] == _own(report, REV)


def test_a_second_tag_for_the_same_line_never_adds_a_second_point(db):
    company = _company(db)
    report = _calendar(company)[2024]
    report |= _report(_accession(company, 2025), 2024, Revenues={2022: 1.0, 2023: 2.0, 2024: 3.0})
    filing = _filing(db, company, report)
    _sync(db, company, report)
    _process(db, filing, report)

    assert _chart(db, filing)["revenue"] == _own(report, REV)  # one point a year: the priority tag's


# --- Amendments and foreign filers -------------------------------------------------------------------


def test_an_amendment_charts_its_own_figures_and_leaves_the_original_alone(db):
    company = _company(db)
    original = _report(_accession(company, 2025), 2024, **{REV: {2022: 800.0, 2023: 1000.0, 2024: 1200.0}})
    amendment = _report(_accession(company, 2025, 20), 2024, form="10-K/A", filed="2025-05-01",
                        **{REV: {2023: 1010.0, 2024: 1190.0}})
    filings = {"10-K": _filing(db, company, original), "10-K/A": _filing(db, company, amendment)}
    _sync(db, company, original, amendment)
    _process(db, filings["10-K"], original)
    _process(db, filings["10-K/A"], amendment)

    assert _chart(db, filings["10-K"])["revenue"] == _own(original, REV)
    assert _chart(db, filings["10-K/A"])["revenue"] == _own(amendment, REV)


def _foreign(company: Company, fy: int, form: str, *, net_income: bool = False,
             per_share: bool = False) -> tuple[dict, dict]:
    """A foreign US-GAAP annual report for the year to 31 March: its CNY items, and its own year again
    in USD at that year's rate (a convenience translation)."""
    years = (fy - 2, fy - 1, fy)
    common = {"form": form, "filed": f"{fy}-07-15", "year_end": "03-31"}
    lines = {REV: {y: 1000.0 * (y - 2000) for y in years}, "Assets": {y: 9000.0 * (y - 2000) for y in years[1:]}}
    if net_income:
        lines["NetIncomeLoss"] = {y: 100.0 * (y - 2000) for y in years}
    native = _report(_accession(company, fy), fy, unit="CNY", **common, **lines)
    translated = {tag: {fy: round(values[fy] / 7.0, 2)} for tag, values in lines.items() if tag != "Assets"}
    usd = _report(_accession(company, fy), fy, **common, **translated)
    if per_share:
        eps = {y: 1.0 * (y - 2000) for y in years}
        native |= _report(_accession(company, fy), fy, unit="CNY/shares", **common, EarningsPerShareBasic=eps)
        usd |= _report(_accession(company, fy), fy, unit="USD/shares", **common,
                       EarningsPerShareBasic={fy: round(eps[fy] / 7.0, 2)})
    return native, usd


def _early_usd_sync(db, company: Company, form: str, *translations: tuple[int, dict]) -> None:
    """What a sync from before companyfacts read the reporting currency stored for a foreign filer: each
    report's own year of revenue in USD, its convenience translation, under that report's accession."""
    facts_service.upsert_facts_bulk(db, [{
        "company_id": company.id, "filing_id": None, "concept": "revenue", "raw_tag": f"us-gaap:{REV}",
        "unit": "USD", "period_start": date.fromisoformat(_start(f"{fy}-03-31")), "period_end": date(fy, 3, 31),
        "fiscal_year": fy, "fiscal_period": "FY", "value": usd[REV][0]["val"], "form": form,
        "accession": _accession(company, fy), "source": "companyfacts", "reconciled": True,
    } for fy, usd in translations])


# 40-F as well as 20-F: the reader treats them alike. Production processes no 40-F today (the summary
# pipeline fetches XBRL for 10-K, 10-Q and 20-F only, ``summary_stages/enrichment.py``), so a 40-F's
# processed gate stays shut and its chart empty, as before this reader; the case holds for when it does.
@pytest.mark.parametrize("form", ["20-F", "40-F"])
def test_a_foreign_annual_reports_chart_keeps_one_currency_per_line(db, form):
    company = _company(db)
    (n23, u23), (n24, u24) = _foreign(company, 2023, form), _foreign(company, 2024, form)
    older, newer = _filing(db, company, n23), _filing(db, company, n24)
    _early_usd_sync(db, company, form, (2023, u23), (2024, u24))
    # The native sync demotes those USD rows, storing the CNY history beside them.
    _sync(db, company, n23, u23, n24, u24)
    _process(db, older, n23)  # owns two years, the sync holds its oldest year and older balance
    _process(db, newer, n24)  # the sync holds every cell

    for filing, native in ((older, n23), (newer, n24)):
        assert db.query(FinancialFact).filter_by(company_id=company.id, accession=filing.accession_number,
                                                 unit="USD").count() == 1
        chart = _chart(db, filing)
        assert chart["revenue"] == _own(native, REV)  # CNY only: the USD row under its accession stays out
        assert chart["total_assets"] == _own(native, "Assets")
        payload = facts_service.get_filing_fundamentals(db, filing.id)
        revenue = next(s for s in payload["concepts"] if s["concept"] == "revenue")
        assert revenue["unit"] == "CNY"
        assert {p["fiscal_period"] for s in payload["concepts"] for p in s["points"]} == {"FY"}
        assert len({p["fiscal_year"] for p in revenue["points"]}) == 3  # one bar a year


@pytest.mark.parametrize("which,native_sync,shows", [
    ("older", True, False), ("older", False, False), ("newest", False, False), ("newest", True, True),
], ids=["older-after-the-native-sync", "older-early-sync-only", "newest-early-sync-only",
        "newest-after-the-native-sync"])
def test_a_foreign_reports_line_it_was_never_read_from_counts_only_in_its_own_currency(db, which, native_sync, shows):
    """For a line the per-filing writer read nothing of, a stand-in counts only in the currency of the
    report's own rows, the reporting currency the extractor chose for it. An early sync stored each
    20-F's own year in USD under its accession, a convenience translation only that report gave. Until
    a native sync runs, that row is the line's only stand-in; after one, an older report also holds its
    oldest year in CNY. The USD row reaches the period end and would chart a lone bar beside the CNY
    lines; it never counts, and an older report's oldest year alone falls short, so neither shows. The
    newest report after a native sync owns no row (the sync holds every cell): its stand-ins take the
    currency with the most period ends, CNY, and every year it reported shows."""
    company = _company(db)
    reports = {"older": _foreign(company, 2023, "20-F"), "newest": _foreign(company, 2024, "20-F")}
    filings = {key: _filing(db, company, native) for key, (native, _usd) in reports.items()}
    _early_usd_sync(db, company, "20-F", (2023, reports["older"][1]), (2024, reports["newest"][1]))
    if native_sync:
        _sync(db, company, *(report for pair in reports.values() for report in pair))
    native, filing = reports[which][0], filings[which]
    facts_service.process_filing_facts(db, filing, standardized=_standardized({"Assets": native["Assets"]}))

    own_year = date.fromisoformat(native[REV][-1]["end"])
    rows = db.query(FinancialFact).filter_by(company_id=company.id, accession=filing.accession_number,
                                             concept="revenue").all()
    assert (own_year, "USD") in {(row.period_end, row.unit) for row in rows}  # the convenience row
    chart = _chart(db, filing)
    assert chart.get("revenue") == (_own(native, REV) if shows else None)
    assert chart["total_assets"] == _own(native, "Assets")


def test_a_report_with_no_annual_row_of_its_own_ranks_its_stand_ins_without_presence(db):
    """When the per-filing writer stored no annual row for a report, its stand-ins rank their own
    currency. An older 20-F's revenue line then holds its oldest year in CNY and its own year in USD,
    one period end each: the tie goes to CNY, never to the currency present at the report's own year
    (the USD translation only it gave), and the oldest year alone falls short of the period end."""
    company = _company(db)
    (n23, u23), (n24, u24) = _foreign(company, 2023, "20-F"), _foreign(company, 2024, "20-F")
    n23, n24 = {REV: n23[REV]}, {REV: n24[REV]}  # revenue alone, so no other line breaks the tie
    older, _newer = _filing(db, company, n23), _filing(db, company, n24)
    _early_usd_sync(db, company, "20-F", (2023, u23), (2024, u24))
    _sync(db, company, n23, u23, n24, u24)
    facts_service.process_filing_facts(db, older, standardized={})

    rows = db.query(FinancialFact).filter_by(company_id=company.id, accession=older.accession_number).all()
    assert sorted((row.period_end, row.unit, row.filing_id) for row in rows) == [
        (date(2021, 3, 31), "CNY", None), (date(2023, 3, 31), "USD", None)]
    assert _chart(db, older) == {}


def test_a_switched_filers_line_it_was_never_read_from_shows_no_usd_bar(db):
    """Hello Group, Vipshop and JOYY each reported years in USD alone, then switched to CNY with each
    year again in USD. USD then holds periods CNY lacks, so the sync reads the USD list
    (``currency.series_unit``) and stores under each CNY report's accession only that report's own year
    in USD. For a line the per-filing writer read nothing of, that row is the only stand-in, at the
    newest report as at an older one; their own rows are in CNY, so it never counts. A report from
    the USD years, whose every cell the sync holds, charts in USD."""
    company = _company(db)
    common = {"form": "20-F", "year_end": "12-31"}
    usd_era = _report(_accession(company, 2013), 2012, filed="2013-04-15", **common,
                      **{REV: {2010: 100.0, 2011: 200.0, 2012: 300.0}, "Assets": {2011: 1000.0, 2012: 1100.0}})
    native = {fy: _report(_accession(company, fy + 1), fy, filed=f"{fy + 1}-04-15", unit="CNY", **common, **{
        REV: {y: 700.0 * (y - 2009) for y in (fy - 2, fy - 1, fy)},
        "Assets": {y: 7000.0 * (y - 2001) for y in (fy - 1, fy)}}) for fy in (2013, 2014)}
    translated = {fy: _report(_accession(company, fy + 1), fy, filed=f"{fy + 1}-04-15", **common, **{
        REV: {fy: 100.0 * (fy - 2009)}, "Assets": {fy: 1000.0 * (fy - 2001)}}) for fy in (2013, 2014)}
    filings = {2012: _filing(db, company, usd_era), **{fy: _filing(db, company, native[fy]) for fy in native}}
    _sync(db, company, usd_era, native[2013], translated[2013], native[2014], translated[2014])
    _process(db, filings[2012], usd_era)
    for fy in native:
        facts_service.process_filing_facts(db, filings[fy], standardized=_standardized({"Assets": native[fy]["Assets"]}))

    assert _chart(db, filings[2012]) == {"revenue": _own(usd_era, REV), "total_assets": _own(usd_era, "Assets")}
    for fy in native:
        rows = db.query(FinancialFact).filter_by(company_id=company.id, accession=filings[fy].accession_number,
                                                 concept="revenue").all()
        assert [(row.period_end, row.unit) for row in rows] == [(date(fy, 12, 31), "USD")]
        chart = _chart(db, filings[fy])
        assert chart == {"total_assets": _own(native[fy], "Assets")}


@pytest.mark.parametrize("read_all", [False, True], ids=["assets-only", "the-whole-report"])
def test_a_ratio_counts_by_its_operands_currency_or_by_the_units_of_a_line_the_report_owns(db, read_all):
    """From 2026-10-10, when calculations began to record their operands, until #1365 a sync read the
    USD lists alone: under each 20-F's accession it stored a net margin over that report's own-year
    convenience figures, every operand under that accession, and the own year's EPS in USD. The native
    sync then adds the oldest year's margin over CNY operands, and its EPS in CNY.

    A ratio's unit names no currency, so its operands' does. For a line the per-filing writer read
    nothing of, the USD-derived own-year margin would reach the period end and chart the oldest year
    beside the report's own, the year between missing; in CNY the line falls short, so none shows.
    In a line the report owns rows of, a stand-in counts in their unit: the margin line keeps both
    stand-ins, the oldest year and the own year the USD-derived margin holds (the same ratio), while
    the EPS line, owned in CNY per share, keeps its oldest year and never the USD convenience row."""
    company = _company(db)
    (n23, u23), (n24, u24) = (_foreign(company, fy, "20-F", net_income=True, per_share=True) for fy in (2023, 2024))
    older, _newer = _filing(db, company, n23), _filing(db, company, n24)
    _sync(db, company, u23, u24)  # what a sync read that week: the USD lists alone
    _sync(db, company, n23, u23, n24, u24)
    read = n23 if read_all else {"Assets": n23["Assets"]}
    facts_service.process_filing_facts(db, older, standardized=_standardized(read))

    margins = db.query(FinancialFact).filter_by(company_id=company.id, accession=older.accession_number,
                                                concept="net_margin", filing_id=None).all()
    assert sorted((row.period_end, *{operand["unit"] for operand in row.provenance["inputs"]}) for row in margins) == [
        (date(2021, 3, 31), "CNY"), (date(2023, 3, 31), "USD")]
    chart = _chart(db, older)
    if not read_all:
        assert chart == {"total_assets": _own(n23, "Assets")}
        return
    assert [(end, unit) for end, _value, unit, _accn in chart["net_margin"]] == [
        ("2021-03-31", "pure"), ("2022-03-31", "pure"), ("2023-03-31", "pure")]
    assert chart["earnings_per_share"] == _own(n23, "EarningsPerShareBasic")  # CNY per share, every year
    assert chart["revenue"] == _own(n23, REV)


def test_a_per_share_line_on_the_newest_report_synced_first_counts_in_its_currency(db):
    """The newest annual report synced first owns no row: the sync holds every cell, so its stand-ins
    rank their own currency, USD. A per-share line's unit names that currency before its slash, and
    EPS, basic and diluted, shows every year the report gave."""
    company = _company(db)
    report = _calendar(company)[2024]
    report |= _report(_accession(company, 2025), 2024, unit="USD/shares", EarningsPerShareBasic={
        2022: 2.2, 2023: 2.3, 2024: 2.4}, EarningsPerShareDiluted={2022: 2.1, 2023: 2.2, 2024: 2.3})
    filing = _filing(db, company, report)
    _sync(db, company, report)
    _process(db, filing, report)

    assert db.query(FinancialFact).filter_by(company_id=company.id, accession=filing.accession_number).filter(
        FinancialFact.filing_id.isnot(None)).count() == 0
    chart = _chart(db, filing)
    assert chart["earnings_per_share"] == _own(report, "EarningsPerShareBasic")
    assert chart["eps_diluted"] == _own(report, "EarningsPerShareDiluted")


@pytest.mark.parametrize("shape", ["read-twice", "one-line-in-euros"])
def test_a_report_whose_own_rows_carry_two_currencies_takes_the_one_with_the_most_years(db, shape):
    """The extractor picks a currency per concept, and the writer keeps a row in each unit it was given,
    so a report's own rows can carry two currencies. A line the writer read nothing of takes the one
    the extractor's rule ranks first over those own rows: the most period ends, then a non-USD code.
    Read in USD before the writer read the reporting currency and in CNY when it ran again, a 20-F's
    own rows tie, so CNY, and the net income the sync holds in CNY shows. A USD reporter that gave one
    line in euros alone owns more USD years, so USD, and the net income the sync holds in USD shows."""
    company = _company(db)
    if shape == "read-twice":
        report, usd = _foreign(company, 2024, "20-F", net_income=True)
        filing = _filing(db, company, report)
        read = {REV: report[REV], "Assets": report["Assets"]}
        legacy = {concept: {"series": [{**point, "currency": None} for point in entry["series"]]}
                  for concept, entry in _standardized({tag: [{**item, "unit": "USD"} for item in items]
                                                       for tag, items in read.items()}).items()}
        facts_service.process_filing_facts(db, filing, standardized=legacy)
        facts_service.process_filing_facts(db, filing, standardized=_standardized(read))
        _sync(db, company, report, usd)
        owned = {"USD", "CNY"}
    else:
        report = _report(_accession(company, 2025), 2024, form="20-F", **{
            REV: {2022: 800.0, 2023: 1000.0, 2024: 1200.0}, "Assets": {2023: 5000.0, 2024: 6000.0},
            "NetIncomeLoss": {2022: 80.0, 2023: 100.0, 2024: 120.0}})
        euros = _report(_accession(company, 2025), 2024, form="20-F", unit="EUR", GrossProfit={2024: 450.0})
        filing = _filing(db, company, report)
        _process(db, filing, {REV: report[REV], "Assets": report["Assets"], **euros})
        _sync(db, company, report)
        owned = {"USD"}

    chart = _chart(db, filing)
    assert {unit for _end, _value, unit, _accn in chart["revenue"]} == owned
    assert chart["net_income"] == _own(report, "NetIncomeLoss")


def test_a_reports_own_rows_keep_their_currency_beside_a_later_native_sync(db):
    """The per-filing writer read a foreign report in USD before it read the reporting currency. A later
    native sync stores the CNY figures under the report's accession beside them; the report's own rows
    keep its chart, so a stand-in never takes away a row the chart showed."""
    company = _company(db)
    native, usd = _foreign(company, 2024, "20-F")
    filing = _filing(db, company, native)
    legacy = {concept: {"series": [{**point, "currency": None} for point in entry["series"]]}
              for concept, entry in _standardized(native).items()}
    facts_service.process_filing_facts(db, filing, standardized=legacy)
    before = _chart(db, filing)

    _sync(db, company, native, usd)

    assert {unit for points in before.values() for _end, _value, unit, _accn in points} == {"USD"}
    assert db.query(FinancialFact).filter_by(company_id=company.id, accession=filing.accession_number,
                                             unit="CNY").count() == 5
    assert _chart(db, filing) == before


# --- A year's own-report row (WP5b) -----------------------------------------------------------------
#
# The sync keeps, beside a year's winner from a later report, the value the year's own annual report gave:
# a non-current row at that report's accession, with no filing owner (``facts/own_reports.py``). It is the
# report's own figure, so it stands in like any stored row, and it holds the report's own-year cell,
# which the per-filing writer then skips. REGN is the worked case (docs/mpa-improvements/coherence.md,
# section 1.6).

# Revenue as each REGN 10-K reports it, its own year and the two before: the FY2020 10-K gives FY2018 and
# FY2019 a narrower figure under the same tag, and the FY2021 10-K repeats FY2019's. Total assets: the
# FY2019 10-K gives the 2018 balance another value. No later report changed net income.
_REGN_REVENUE = {2018: {2016: 4_860.4e6, 2017: 5_872.2e6, 2018: 6_710.8e6},
                 2019: {2017: 5_872.2e6, 2018: 6_710.8e6, 2019: 7_863.4e6},
                 2020: {2018: 5_145.6e6, 2019: 6_557.6e6, 2020: 8_497.1e6},
                 2021: {2019: 6_557.6e6, 2020: 8_497.1e6, 2021: 16_071.7e6}}
_REGN_NET_INCOME = {2016: 895.5e6, 2017: 1_198.5e6, 2018: 2_444.4e6, 2019: 2_115.8e6, 2020: 3_513.2e6,
                    2021: 8_075.3e6}
_REGN_ASSETS = {2018: {2017: 11_734.5e6, 2018: 15_163.8e6}, 2019: {2018: 15_200.1e6, 2019: 17_163.4e6},
                2020: {2019: 17_163.4e6, 2020: 19_994.1e6}, 2021: {2020: 19_994.1e6, 2021: 25_434.7e6}}
_REGN_FILED = {2018: "2019-02-07", 2019: "2020-02-07", 2020: "2021-02-08", 2021: "2022-02-07"}


def _regn(company: Company) -> dict[int, dict[str, list[dict]]]:
    """REGN's FY2018 to FY2021 10-Ks, by the fiscal year each reports as its own."""
    return {fy: _report(_accession(company, fy + 1), fy, filed=_REGN_FILED[fy], **{
        REV: revenue, "NetIncomeLoss": {year: _REGN_NET_INCOME[year] for year in revenue},
        "Assets": _REGN_ASSETS[fy]}) for fy, revenue in _REGN_REVENUE.items()}


def _years(db, filing: Filing, concept: str) -> list[tuple[int, float]]:
    """One chart line's (fiscal year, value) points, as the filing page labels them."""
    db.expire_all()
    [series] = [s for s in facts_service.get_filing_fundamentals(db, filing.id)["concepts"] if s["concept"] == concept]
    return [(point["fiscal_year"], point["value"]) for point in series["points"]]


def _own_report_rows(db, company: Company) -> list[tuple]:
    """The own-report rows the sync stored: (accession, concept, year of the period end, value)."""
    rows = db.query(FinancialFact).filter_by(company_id=company.id, source="companyfacts", is_latest=False,
                                             filing_id=None).all()
    return sorted((row.accession, row.concept, row.period_end.year, float(row.value)) for row in rows)


@pytest.mark.parametrize("sync_first", [True, False], ids=["synced-first", "processed-first"])
@pytest.mark.parametrize("fy", [2018, 2019])
def test_an_older_report_a_later_one_restated_charts_its_own_figures_in_either_order(db, fy, sync_first):
    """The FY2018 10-K charts the 6,710.8M its own report gave, never the FY2020 10-K's 5,145.6M, and the
    FY2019 10-K its 7,863.4M, never 6,557.6M, under the years the report names. Synced first, the report's
    own-year cell (and the FY2018 10-K's own balance) is the own-report row, which the writer skips;
    processed first, the writer owns it, the sync demotes it, and no own-report row is stored there."""
    company = _company(db)
    reports = _regn(company)
    filings = {year: _filing(db, company, report) for year, report in reports.items()}
    filing = filings[fy]
    steps = [lambda: _sync(db, company, *reports.values()), lambda: _process(db, filing, reports[fy])]
    sync = [step() for step in (steps if sync_first else steps[::-1])][0 if sync_first else 1]

    assert sync["history"] == (3 if sync_first else {2018: 1, 2019: 2}[fy])
    own_year = db.query(FinancialFact).filter_by(company_id=company.id, accession=filing.accession_number,
                                                 concept="revenue", period_end=date(fy, 12, 31)).one()
    assert (own_year.value, own_year.is_latest, own_year.filing_id) == (
        _REGN_REVENUE[fy][fy], False, None if sync_first else filing.id)
    assert _years(db, filing, "revenue") == list(_REGN_REVENUE[fy].items())
    assert _years(db, filing, "total_assets") == list(_REGN_ASSETS[fy].items())
    assert _chart(db, filing)["net_income"] == _own(reports[fy], "NetIncomeLoss")


def test_a_later_reports_chart_never_shows_an_earlier_reports_own_value(db):
    """The own-report rows sit at the FY2018 and FY2019 10-Ks' accessions, so the FY2020 10-K charts the
    narrower 5,145.6M it gave FY2018, and neither it nor the newest report shows 6,710.8M or 7,863.4M."""
    company = _company(db)
    reports = _regn(company)
    filings = {year: _filing(db, company, report) for year, report in reports.items()}
    _sync(db, company, *reports.values())

    assert _own_report_rows(db, company) == sorted([
        (filings[2018].accession_number, "revenue", 2018, 6_710.8e6),
        (filings[2018].accession_number, "total_assets", 2018, 15_163.8e6),
        (filings[2019].accession_number, "revenue", 2019, 7_863.4e6)])
    for fy in (2020, 2021):
        _process(db, filings[fy], reports[fy])
        assert _chart(db, filings[fy])["revenue"] == _own(reports[fy], REV)
        assert _years(db, filings[fy], "revenue") == list(_REGN_REVENUE[fy].items())


@pytest.mark.parametrize("fy", [2018, 2019])
def test_a_line_the_writer_read_nothing_of_never_charts_with_a_year_missing(db, fy):
    """For a line the per-filing writer read nothing of, an older report holds its oldest year (it reported
    it last) and its own year (the own-report row), while the year between sits under the next report's
    accession. Both reach the period end, and charted they would set the oldest year beside the own year
    on the categorical axis. A line with a year missing keeps the report's own rows only, none here, as a
    line short of the period end does; the lines the writer read chart as before."""
    company = _company(db)
    reports = _regn(company)
    filing = _filing(db, company, reports[fy])
    _sync(db, company, *reports.values())
    read = {"NetIncomeLoss": reports[fy]["NetIncomeLoss"], "Assets": reports[fy]["Assets"]}
    facts_service.process_filing_facts(db, filing, standardized=_standardized(read))

    rows = db.query(FinancialFact).filter_by(company_id=company.id, accession=filing.accession_number,
                                             concept="revenue").all()
    assert sorted((row.period_end.year, row.is_latest, row.filing_id) for row in rows) == [
        (fy - 2, True, None), (fy, False, None)]
    chart = _chart(db, filing)
    assert "revenue" not in chart
    assert chart["net_income"] == _own(reports[fy], "NetIncomeLoss")
    assert chart["total_assets"] == _own(reports[fy], "Assets")


def test_a_balance_line_the_own_report_row_completes_charts_both_balances(db):
    """A 10-K gives two year-end balances. The FY2018 10-K reported its older one last, and the FY2019 10-K
    gave its own another value, so the sync holds both of its balance cells: a winner and the own-report
    row. For a balance line the writer read nothing of, the two stand in with no year missing, and the line
    charts both balances as the report gave them, under the years its own rows count to."""
    company = _company(db)
    reports = _regn(company)
    filing = _filing(db, company, reports[2018])
    _sync(db, company, *reports.values())
    facts_service.process_filing_facts(db, filing, standardized=_standardized({REV: reports[2018][REV]}))

    assert db.query(FinancialFact).filter_by(company_id=company.id, accession=filing.accession_number,
                                             concept="total_assets").filter(FinancialFact.filing_id.isnot(None)).count() == 0
    assert _years(db, filing, "total_assets") == [(2017, 11_734.5e6), (2018, 15_163.8e6)]
    assert _years(db, filing, "revenue") == list(_REGN_REVENUE[2018].items())


@pytest.mark.parametrize("withheld", [False, True], ids=["every-year-reported", "the-year-between-withheld"])
def test_a_line_an_earlier_sync_kept_whole_charts_every_year_unless_the_year_between_is_withheld(db, withheld):
    """A sync run while the FY2018 10-K was the newest stored every cell of it at its accession; a later
    sync moves the winners to later reports and demotes those rows, which stay there, so the report holds
    its own year itself and no own-report row is stored. A line the writer read nothing of is whole and
    charts every year. Where the audited repair withheld the year between, that row no longer counts,
    and the line, its oldest and own years left, has a year missing."""
    company = _company(db)
    reports = _regn(company)
    filing = _filing(db, company, reports[2018])
    _sync(db, company, reports[2018])
    assert _sync(db, company, *reports.values())["history"] == 1  # the FY2019 10-K's own year only
    if withheld:
        between = db.query(FinancialFact).filter_by(company_id=company.id, accession=filing.accession_number,
                                                    concept="revenue", period_end=date(2017, 12, 31)).one()
        state = quarterly_fact_repair._quarantine(quarterly_fact_repair.snapshot(between),
                                                  "legacy_period_label_mismatch")
        between.provenance, between.reconciled = state["provenance"], False
        db.commit()
    facts_service.process_filing_facts(db, filing, standardized=_standardized({"Assets": reports[2018]["Assets"]}))

    if withheld:
        assert "revenue" not in _chart(db, filing)
    else:
        assert _years(db, filing, "revenue") == list(_REGN_REVENUE[2018].items())


def test_a_line_the_writer_read_only_its_own_year_of_keeps_that_year_alone(db):
    """The extractor gave one point of a line (no comparative series): the report's own year, which no
    later report changed, so the writer owns it. The sync holds the line's oldest year, two years before
    it. With the year between missing the line keeps its own row: its own year, alone."""
    company = _company(db)
    reports = _regn(company)
    filing = _filing(db, company, reports[2018])
    _sync(db, company, *reports.values())
    read = {REV: reports[2018][REV], "NetIncomeLoss": reports[2018]["NetIncomeLoss"][-1:]}
    facts_service.process_filing_facts(db, filing, standardized=_standardized(read))

    rows = db.query(FinancialFact).filter_by(company_id=company.id, accession=filing.accession_number,
                                             concept="net_income").all()
    assert sorted((row.period_end.year, row.filing_id) for row in rows) == [(2016, None), (2018, filing.id)]
    assert _years(db, filing, "net_income") == [(2018, 2_444.4e6)]


@pytest.mark.parametrize("read_revenue", [True, False], ids=["a-line-the-writer-read", "a-line-it-read-nothing-of"])
def test_a_line_whose_other_years_later_filings_hold_charts_its_own_year_alone(db, read_revenue):
    """A shape the rule leaves. An 8-K recasts the FY2022 10-K's three years after it, and the FY2023 10-K
    repeats the recast, so later filings hold the report's two earlier years and only its own year, the
    own-report row, stays at its accession. A line the writer read is whole (its own rows hold the two
    earlier years); one it read nothing of reaches the period end with no year missing and charts the
    own year alone, as the report gave it."""
    company = _company(db)
    k22 = _report(_accession(company, 2023), 2022, **{REV: {2020: 600.0, 2021: 700.0, 2022: 800.0},
                                                       "NetIncomeLoss": {2020: 60.0, 2021: 70.0, 2022: 80.0}})
    recast = _report(_accession(company, 2023, 50), 2022, form="8-K", filed="2023-06-01",
                     **{REV: {2020: 590.0, 2021: 690.0, 2022: 790.0}})
    k23 = _report(_accession(company, 2024), 2023, **{REV: {2021: 690.0, 2022: 790.0, 2023: 1000.0}})
    filing = _filing(db, company, k22)
    _sync(db, company, k22, recast, k23)
    read = k22 if read_revenue else {"NetIncomeLoss": k22["NetIncomeLoss"]}
    facts_service.process_filing_facts(db, filing, standardized=_standardized(read))

    assert _own_report_rows(db, company) == [(filing.accession_number, "revenue", 2022, 800.0)]
    assert _years(db, filing, "revenue") == ([(2020, 600.0), (2021, 700.0), (2022, 800.0)] if read_revenue
                                             else [(2022, 800.0)])


# A 52/53-week year ending on the last Saturday of September.
_SEPTEMBER = {2020: "2020-09-26", 2021: "2021-09-25", 2022: "2022-09-24", 2023: "2023-09-30", 2024: "2024-09-28"}


def _september(company: Company) -> dict[int, dict[str, list[dict]]]:
    """Three 10-Ks, filed each November, of three years' revenue and net income: the FY2024 10-K gives
    FY2022 revenue another value (a recast)."""
    revenue = {2022: {2020: 274.5e9, 2021: 365.8e9, 2022: 394.3e9}, 2023: {2021: 365.8e9, 2022: 394.3e9, 2023: 383.3e9},
               2024: {2022: 391.0e9, 2023: 383.3e9, 2024: 391.0e9}}
    net_income = {2020: 57.4e9, 2021: 94.7e9, 2022: 99.8e9, 2023: 97.0e9, 2024: 93.7e9}

    def items(fy: int, tag: str, values: dict[int, float]) -> list[dict]:
        return [{"val": value, "start": _start(_SEPTEMBER[year]), "end": _SEPTEMBER[year], "accn": _accession(company, fy),
                 "fy": fy, "fp": "FY", "form": "10-K", "filed": f"{fy}-11-01", "unit": "USD"} for year, value in values.items()]

    return {fy: {REV: items(fy, REV, values), "NetIncomeLoss": items(fy, "NetIncomeLoss", {
        year: net_income[year] for year in values})} for fy, values in revenue.items()}


@pytest.mark.parametrize("read_revenue", [True, False], ids=["a-line-the-writer-read", "a-line-it-read-nothing-of"])
def test_a_september_year_reports_own_report_row(db, read_revenue):
    """A year ending by September: the FY2022 10-K's own year is the own-report row. In a line the writer
    read it completes the report's three years under their own labels; in one it read nothing of, the
    oldest year (2020-09-26) and the own year (2022-09-24) lie 728 days apart, a year missing. The FY2023
    10-K's own year is a 53-week year, 371 days after the one before: no year missing."""
    company = _company(db)
    reports = _september(company)
    filing, k23 = _filing(db, company, reports[2022]), _filing(db, company, reports[2023])
    _sync(db, company, *reports.values())
    read = reports[2022] if read_revenue else {"NetIncomeLoss": reports[2022]["NetIncomeLoss"]}
    facts_service.process_filing_facts(db, filing, standardized=_standardized(read))
    _process(db, k23, reports[2023])

    assert _own_report_rows(db, company) == [(filing.accession_number, "revenue", 2022, 394.3e9)]
    if read_revenue:
        assert _years(db, filing, "revenue") == [(2020, 274.5e9), (2021, 365.8e9), (2022, 394.3e9)]
    else:
        assert "revenue" not in _chart(db, filing)
    assert _chart(db, filing)["net_income"] == _own(reports[2022], "NetIncomeLoss")
    assert _years(db, k23, "net_income") == [(2021, 94.7e9), (2022, 99.8e9), (2023, 97.0e9)]  # 2021 a stand-in


@pytest.mark.parametrize("read", ["the-whole-report", "assets-only", "nothing-annual"])
def test_a_20f_whose_own_year_a_later_20f_restated(db, read):
    """A CNY 20-F filer, its year to 31 March. The FY2024 20-F gives FY2023 revenue another value, so the
    FY2023 20-F's own year is an own-report row in CNY at its accession, non-current beside the early
    sync's USD convenience row there (which the native sync demoted). In the revenue line the writer read,
    it completes the report's CNY years, and the USD row stays out. In one it read nothing of, and at a
    report it stored no annual row of, whose stand-ins rank CNY first by period ends, the CNY line has a
    year missing and stays off."""
    company = _company(db)
    (n23, u23), (n24, u24) = _foreign(company, 2023, "20-F"), _foreign(company, 2024, "20-F")
    n24[REV] = [{**item, "val": 24_150.0} if item["end"] == "2023-03-31" else item for item in n24[REV]]
    older, _newer = _filing(db, company, n23), _filing(db, company, n24)
    _early_usd_sync(db, company, "20-F", (2023, u23), (2024, u24))
    _sync(db, company, n23, u23, n24, u24)
    standardized = {"the-whole-report": _standardized(n23), "assets-only": _standardized({"Assets": n23["Assets"]}),
                    "nothing-annual": {}}[read]
    facts_service.process_filing_facts(db, older, standardized=standardized)

    own_year = db.query(FinancialFact).filter_by(company_id=company.id, accession=older.accession_number,
                                                 concept="revenue", period_end=date(2023, 3, 31)).all()
    assert sorted((row.unit, float(row.value), row.is_latest, row.filing_id) for row in own_year) == [
        ("CNY", 23_000.0, False, None), ("USD", u23[REV][0]["val"], False, None)]
    chart = _chart(db, older)
    if read == "the-whole-report":
        assert chart["revenue"] == _own(n23, REV)
    else:
        assert "revenue" not in chart


@pytest.mark.parametrize("sync_first", [True, False], ids=["synced-first", "processed-first"])
@pytest.mark.parametrize("year_end,quarter,filed", [
    ("12-31", ("2025-01-01", "2025-03-31"), ("2025-02-15", "2025-05-01")),
    ("09-28", ("2024-09-29", "2024-12-28"), ("2024-11-01", "2025-01-31")),
], ids=["december-year", "september-year"])
def test_an_interim_report_that_gives_the_prior_balance_another_value_charts_no_annual_line(
        db, sync_first, year_end, quarter, filed):
    """A 10-Q gives the prior year-end balance another value than the 10-K did (a recast). The sync's winner
    for that balance is the 10-Q's, labelled FY at the 10-Q's accession, and the 10-K's own value is the
    own-report row at the 10-K's (synced first) or the 10-K's own row (processed first): the 10-Q's page
    still shows no annual chart, and the 10-K's shows the balances it reported."""
    company = _company(db)
    prior = f"2024-{year_end}"
    annual = _report(_accession(company, 2025), 2024, year_end=year_end, filed=filed[0], **{
        REV: {2022: 2200.0, 2023: 2300.0, 2024: 2400.0}, "Assets": {2023: 23000.0, 2024: 24000.0}})
    common = {"accn": _accession(company, 2025, 40), "fy": 2025, "fp": "Q1", "form": "10-Q", "filed": filed[1],
              "unit": "USD"}
    interim = {REV: [{**common, "val": 330.0, "start": quarter[0], "end": quarter[1]}],
               "Assets": [{**common, "val": 24050.0, "end": prior}, {**common, "val": 24100.0, "end": quarter[1]}]}
    k, q = _filing(db, company, annual), _filing(db, company, interim)
    steps = [lambda: _sync(db, company, annual, interim), lambda: _process(db, k, annual), lambda: _process(db, q, interim)]
    for step in steps if sync_first else steps[1:] + steps[:1]:
        step()

    balances = db.query(FinancialFact).filter_by(company_id=company.id, concept="total_assets", fiscal_period="FY",
                                                 period_end=date.fromisoformat(prior)).all()
    assert sorted((row.accession, row.value, row.is_latest, row.filing_id) for row in balances) == sorted([
        (q.accession_number, 24050.0, True, None), (k.accession_number, 24000.0, False, None if sync_first else k.id)])
    assert _chart(db, q) == {}
    assert _chart(db, k)["total_assets"] == _own(annual, "Assets")


def test_the_copilot_reads_a_reports_own_year_and_its_growth_as_first_reported(db):
    """The Copilot reads a filing's rows at its accession too, so the FY2018 10-K's answers come from its
    own figures: revenue of 6,710.8M and growth of 14.3% (from 5,872.2M), where the FY2020 10-K gives
    FY2018 5,145.6M. In a line with a year missing it computes no growth across the gap."""
    company = _company(db)
    reports = _regn(company)
    filings = {year: _filing(db, company, report) for year, report in reports.items()}
    _sync(db, company, *reports.values())
    _process(db, filings[2018], reports[2018])
    _process(db, filings[2020], reports[2020])
    gapped = filings[2019]
    facts_service.process_filing_facts(db, gapped, standardized=_standardized({"Assets": reports[2019]["Assets"]}))

    def ask(filing: Filing, name: str, **args) -> dict:
        return copilot_tools.run_tool(name, args, company.id, accession_number=filing.accession_number,
                                      reporting_currency="USD")

    fact = ask(filings[2018], "get_financial_fact", concept="revenue", fiscal_year=2018)
    assert (fact["value"], fact["accession"]) == (6_710.8e6, filings[2018].accession_number)
    growth = ask(filings[2018], "compute_metric", kind="yoy_growth", concept="revenue", fiscal_year=2018)
    assert growth["value"] == pytest.approx(6_710.8 / 5_872.2 - 1)
    assert ask(filings[2020], "get_financial_fact", concept="revenue", fiscal_year=2018)["value"] == 5_145.6e6
    assert ask(gapped, "compute_metric", kind="yoy_growth", concept="revenue", fiscal_year=2019) == {
        "error": "no_prior_period", "concept": "revenue"}


def test_the_repairs_that_read_every_row_plan_alike_beside_the_own_report_rows(db, monkeypatch):
    """The lineage backfill (WP0) and the quarterly repair read a company's rows current or not. An own-report
    row is a reported row at its report's accession, stored only where no row held its identity, never
    current and never a calculation. The backfill's targets are filing-owned calculations: one the writer
    stored before the sync has its operands at its accession already (the FY2019 10-K's), and where the
    own-report row holds a cell the writer would have stored after it (the FY2018 10-K's own-year revenue),
    it holds the same figure. The quarterly repair relabels current rows and recomputes untagged ones.
    Both plan the same with and without the rows."""
    from app.services import filing_lineage_repair
    from app.services.facts import companyfacts

    def plans(keep_history: bool) -> tuple:
        company = _company(db)
        reports = _regn(company)
        filings = {year: _filing(db, company, report) for year, report in reports.items()}
        names = {filing.accession_number: f"FY{year}" for year, filing in filings.items()}
        _process(db, filings[2019], reports[2019])
        with monkeypatch.context() as patch:
            if not keep_history:
                patch.setattr(companyfacts, "own_report_history", lambda *args: [])
            assert (_sync(db, company, *reports.values())["history"] > 0) is keep_history
        _process(db, filings[2018], reports[2018])
        for row in db.query(FinancialFact).filter(FinancialFact.company_id == company.id,
                                                  FinancialFact.concept == "net_margin",
                                                  FinancialFact.filing_id.isnot(None)):
            row.provenance = None  # as the writer stored a calculation before #1191
        db.commit()

        def norm(state: dict) -> str:  # each accession, nested ones included, by the year its report names
            text = json.dumps({key: value for key, value in state.items()
                               if key not in ("company_id", "filing_id", "fact_id")}, sort_keys=True)
            for accession, name in names.items():
                text = text.replace(accession, name)
            return text

        backfill = filing_lineage_repair.backfill_company(db, company.id, apply=False, run_id="wp5b-probe")
        payload = {**_payload(*reports.values()), "cik": company.cik}
        repair = quarterly_fact_repair.repair_company(db, company.id, payload, dry_run=True)
        db.rollback()
        return ({key: value for key, value in backfill.items() if key not in ("company_id", "ticker", "rows")},
                sorted(norm(row) for row in backfill["rows"]),
                sorted(norm(change["before"]) + norm(change["after"]) for change in repair["changes"]),
                sorted(norm(state) for state in repair["inserts"]), repair["before"])

    without, beside = plans(False), plans(True)
    assert beside == without
    # The FY2019 10-K's three margins and the FY2018 10-K's two it stored (the sync holds its FY2016 one);
    # the FY2018 margin divides by the own-report row where it holds the revenue cell, 6,710.8M either way.
    assert without[0]["outcomes"] == {"passed": 5, "needs_review": 0}
    [fy2018] = [json.loads(row) for row in beside[1] if '"accession": "FY2018"' in row and '"fiscal_year": 2018' in row]
    assert sorted(fy2018["inputs"]) == [["net_income", 2_444.4e6], ["revenue", 6_710.8e6]]


def test_a_years_own_report_row_stands_in_for_that_report_after_a_restatement(db):
    """WP5b keeps, beside a restated winner, the value the year's own annual report gave: a non-current
    companyfacts row under that report's accession, which the sync stores. It holds that report's cell
    like any stored row."""
    company = _company(db)
    k22 = _report(_accession(company, 2023), 2022, **{REV: {2020: 600.0, 2021: 700.0, 2022: 800.0}})
    k23 = _report(_accession(company, 2024), 2023, **{REV: {2021: 700.0, 2022: 800.0, 2023: 1000.0}})
    k24 = _report(_accession(company, 2025), 2024, **{REV: {2022: 750.0, 2023: 1000.0, 2024: 1200.0}})
    filing = _filing(db, company, k22)
    assert _sync(db, company, k22, k23, k24)["history"] == 1
    [history] = db.query(FinancialFact).filter_by(company_id=company.id, accession=filing.accession_number,
                                                  is_latest=False).all()
    assert (history.period_end, history.value, history.filing_id) == (date(2022, 12, 31), 800.0, None)

    result = _process(db, filing, k22)

    assert result["skipped"] == 2  # 2020, which it reported last, and 2022, its own-report row
    assert _chart(db, filing)["revenue"] == _own(k22, REV)  # 800, never the 2024 report's 750
    [revenue] = [s for s in facts_service.get_filing_fundamentals(db, filing.id)["concepts"] if s["concept"] == "revenue"]
    assert [p["fiscal_year"] for p in revenue["points"]] == [2020, 2021, 2022]  # 2022 counted on from 2021
