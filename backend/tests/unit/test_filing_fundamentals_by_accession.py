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

import random
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from app.database import SessionLocal
from app.models import Company, Filing, FinancialFact
from app.services import facts_service, quarterly_fact_repair
from app.utils.sec_urls import build_sec_archive_url

REV = "RevenueFromContractWithCustomerExcludingAssessedTax"
CONCEPTS = {REV: "revenue", "Revenues": "revenue", "NetIncomeLoss": "net_income",
            "GrossProfit": "gross_profit", "Assets": "total_assets"}
REPORTED_PROVENANCE = {"version": 1, "method": "reported", "validation": "passed", "reasons": [], "formula": None,
                       "inputs": [], "calculation_version": "quarterly-v2", "filed_at": None}


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
    for tag in (REV, "NetIncomeLoss", "GrossProfit", "Assets"):
        for item in report.get(tag, []):
            point = {"period": item["end"], "value": item["val"], "form": item["form"], "raw_tag": f"us-gaap:{tag}",
                     "currency": None if item["unit"] == "USD" else item["unit"]}
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
    1 January for a year to 31 December. A filer that gave its filing date instead, weeks later, is
    beyond any tolerance that keeps a 10-Q's prior year-end out: the report keeps its own rows only, as
    before this reader (the newest report owns none)."""
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


# --- Amendments, foreign filers, a year's own-report row ---------------------------------------------


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


def _foreign(company: Company, fy: int, form: str) -> tuple[dict, dict]:
    """A foreign US-GAAP annual report for the year to 31 March: its CNY items, and its own year again
    in USD at that year's rate (a convenience translation)."""
    years = (fy - 2, fy - 1, fy)
    common = {"form": form, "filed": f"{fy}-07-15", "year_end": "03-31"}
    native = _report(_accession(company, fy), fy, unit="CNY", **common, **{
        REV: {y: 1000.0 * (y - 2000) for y in years}, "Assets": {y: 9000.0 * (y - 2000) for y in years[1:]}})
    return native, _report(_accession(company, fy), fy, **common, **{REV: {fy: round(1000.0 * (fy - 2000) / 7.0)}})


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


def test_an_older_foreign_reports_line_it_was_never_read_from_shows_no_convenience_bar(db):
    """For a line the per-filing writer read nothing of, an older 20-F holds two stand-ins: its oldest
    year in CNY (the native sync's) and its own year in USD (an early sync's convenience translation,
    which only this report gave). One period end each: the native currency takes the line, since the
    native row for the report's own year sits under the later report that re-reported it. Taken by
    presence at that year, the USD row alone would reach the period end and chart a lone bar beside the
    CNY lines; in CNY the line falls short of it (reach is read in the line's one currency), so none
    shows."""
    company = _company(db)
    (n23, u23), (n24, u24) = _foreign(company, 2023, "20-F"), _foreign(company, 2024, "20-F")
    older, _newer = _filing(db, company, n23), _filing(db, company, n24)
    _early_usd_sync(db, company, "20-F", (2023, u23), (2024, u24))
    _sync(db, company, n23, u23, n24, u24)
    facts_service.process_filing_facts(db, older, standardized=_standardized({"Assets": n23["Assets"]}))

    rows = db.query(FinancialFact).filter_by(company_id=company.id, accession=older.accession_number,
                                             concept="revenue").all()
    assert sorted((row.period_end, row.unit, row.filing_id) for row in rows) == [
        (date(2021, 3, 31), "CNY", None), (date(2023, 3, 31), "USD", None)]
    chart = _chart(db, older)
    assert "revenue" not in chart
    assert chart["total_assets"] == _own(n23, "Assets")


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


def test_a_years_own_report_row_stands_in_for_that_report_after_a_restatement(db):
    """WP5b keeps, beside a restated winner, the value the year's own annual report gave: a non-current
    companyfacts row under that report's accession. It holds that report's cell like any stored row."""
    company = _company(db)
    k22 = _report(_accession(company, 2023), 2022, **{REV: {2020: 600.0, 2021: 700.0, 2022: 800.0}})
    k23 = _report(_accession(company, 2024), 2023, **{REV: {2021: 700.0, 2022: 800.0, 2023: 1000.0}})
    k24 = _report(_accession(company, 2025), 2024, **{REV: {2022: 750.0, 2023: 1000.0, 2024: 1200.0}})
    filing = _filing(db, company, k22)
    _sync(db, company, k22, k23, k24)
    db.add(FinancialFact(
        company_id=company.id, filing_id=None, concept="revenue", raw_tag=f"us-gaap:{REV}", unit="USD",
        period_start=date.fromisoformat(_start("2022-12-31")), period_end=date(2022, 12, 31), fiscal_year=2022,
        fiscal_period="FY", value=800.0, form="10-K", accession=filing.accession_number, source="companyfacts",
        reconciled=True, is_latest=False, provenance={**REPORTED_PROVENANCE, "filed_at": "2023-02-15"},
    ))
    db.commit()

    result = _process(db, filing, k22)

    assert result["skipped"] == 2  # 2020, which it reported last, and 2022, its own-report row
    assert _chart(db, filing)["revenue"] == _own(k22, REV)  # 800, never the 2024 report's 750
    [revenue] = [s for s in facts_service.get_filing_fundamentals(db, filing.id)["concepts"] if s["concept"] == "revenue"]
    assert [p["fiscal_year"] for p in revenue["points"]] == [2020, 2021, 2022]  # 2022 counted on from 2021
