"""PB-04's offline acceptance corpus: real SEC payloads through every surface that prints their figures.

EN-BETA-2026-11, workstream PB-04 (Pro data integrity). Each case is a committed SEC companyfacts payload
(``tests/fixtures/companyfacts_fi``, SEC's payloads of 2026-11-01 and 11-02 trimmed to the revenue rule's tags, as
``test_fi_revenue.py`` records; E291's ``companyfacts_partial_years``, trimmed to the items ending from 2024 on), with a
Filing row for each 10-K and 10-Q accession it names, as the app lists filings, synced through the real ingest (its
fetcher seam: no network). Every surface then reads the stored rows, and every figure it prints is held to them:

- the Multi-Period Analysis dataset, annual (the last ten years) and quarterly (the last twelve quarters): each value
  is the stored current row of its period and concept, in that row's unit, at that row's accession; a reported value
  links its own filing (its primary document, else its folder), and every reported input, of a calculated value or of
  a change, at any depth, links its own accession's filing (a calculated input links its row's own filing or nothing,
  and its own inputs carry the links);
- the analysis workbook: each Metrics cell is its point's value (a percent series in hundredths), and the Sources &
  methods sheet lists each value and each of its inputs with its value, unit, accession and link;
- the analysis PDF: under its metric's own heading, each value's item prints it with its unit, its own link and each
  of its inputs' links;
- Financial trends: each 10-K's chart reads that filing's own rows at its accession, the year it reports its own;
- the Sector peers panel: the subject's figure is its stored current row of its industry's concept (net interest
  income for a bank, revenue otherwise) for its latest year.

A case fails when a surface prints a figure no stored current row holds, in another unit, or under another filing's
link. Those checks hold a surface to the stored winner, so ``READ_OFF`` pins the winner itself where a figure was read
off its filing: each such figure is current at that filing, and so is what every surface above prints. Nothing here
fetches, calls a model or writes outside the test's own database. Extend the corpus as payloads land (a filer's
balance sheet and cash flows; a 20-F filer's, in its own currency); retire it with the surfaces it reads.
"""
import asyncio
import io
import json
from html import escape
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from openpyxl import load_workbook
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, SessionLocal
from app.models import Company, Filing, FinancialFact
from app.services import trend_analysis_service
from app.services.analysis_export_metadata import operand_records, period_label, raw_value_text
from app.services.excel_export_service import build_analysis_workbook
from app.services.export_service import ExportService
from app.services.fact_provenance import published_value
from app.services.facts.fundamentals import get_filing_fundamentals
from app.services.facts.ingest import ingest_companyfacts
from app.services.peers_service import default_concept_for, get_peers
from app.utils.sec_urls import build_sec_archive_url

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
# Each case: its payload's folder, its SIC code (the revenue rule reads a financial filer's total; a ``companyfacts_fi``
# payload's is the one test_financial_revenue_preview.py gives it), and what it brings.
CORPUS = {
    "WBHC": ("companyfacts_fi", "6021", "a community bank whose same-day 10-Q/A repeats its original"),
    "PNC": ("companyfacts_fi", "6021", "a bank whose 8-K recast gives prior years another figure"),
    "WFC": ("companyfacts_fi", "6021", "a bank whose payload carries no total for most years"),
    "IBKR": ("companyfacts_fi", "6211", "a broker with 10-Q/As and its net revenue total"),
    "AXP": ("companyfacts_fi", "6199", "a card issuer whose fee line a later filing recasts"),
    "MET": ("companyfacts_fi", "6311", "an insurer read on its total revenue"),
    "AMT": ("companyfacts_fi", "6798", "a tower REIT whose fee element is its total"),
    "TRC": ("companyfacts_fi", "6500", "a land company reporting real estate revenue"),
    "AJG": ("companyfacts_fi", "6411", "an insurance broker"),
    "ARE": ("companyfacts_fi", "6798", "an office REIT"),
    "BLK": ("companyfacts_fi", "6211", "an asset manager filed as a broker"),
    "CBOE": ("companyfacts_fi", "6200", "an exchange operator"),
    "ICE": ("companyfacts_fi", "6200", "an exchange operator whose older 10-K reports a fee tag beside its total"),
    "KKR": ("companyfacts_fi", "6282", "an asset manager"),
    "TROW": ("companyfacts_fi", "6282", "an asset manager"),
    "CLSK": ("companyfacts_fi", "6199", "a bitcoin miner filed under finance services"),
    "HUT": ("companyfacts_fi", "6199", "a bitcoin miner filed under finance services"),
    "BXSL": ("companyfacts_fi", "", "a business development company with no SIC code, read as a non-financial filer"),
    "CBAN": ("companyfacts_partial_years", "6022", "a bank whose 10-Q tags a quarter's figure with its year (E291)"),
    "FIX": ("companyfacts_partial_years", "1700", "a contractor whose 10-Q tags a quarter's figure with its year "
            "(E291), with gross profit, operating income and their margins"),
}
CBAN_10K, FIX_10K = "0000711669-26-000007", "0001104659-26-017530"  # each FY2025 10-K
# Figures read off a filing's own statements, as (value, that filing's accession). A year's figure is its 10-K's (each
# 10-Q above read its first quarter's instead); a Q4 is the 10-K's year less the third quarter's nine months, and a
# margin is the 10-K's own two figures. Every surface prints each at that filing.
READ_OFF = {
    ("FIX", "revenue", 2025, "FY"): (9_101_641_000, FIX_10K),  # the Q1 2026 10-Q's year: 1,831,286,000
    ("FIX", "gross_profit", 2025, "FY"): (2_195_899_000, FIX_10K),
    ("FIX", "operating_income", 2025, "FY"): (1_314_589_000, FIX_10K),
    ("FIX", "net_income", 2025, "FY"): (1_022_558_000, FIX_10K),
    ("FIX", "net_margin", 2025, "FY"): (1_022_558_000 / 9_101_641_000 * 100, FIX_10K),  # 11.23%; not 55.84
    ("FIX", "revenue", 2025, "Q4"): (2_646_067_000, FIX_10K),
    ("CBAN", "net_income", 2025, "FY"): (28_253_000, CBAN_10K),  # the Q1 2026 10-Q's year: 6,613,000
    ("CBAN", "net_interest_income", 2025, "FY"): (91_901_000, CBAN_10K),
    ("CBAN", "noninterest_income", 2025, "FY"): (40_280_000, CBAN_10K),
    ("CBAN", "eps_diluted", 2025, "FY"): (1.59, CBAN_10K),  # the 10-Q's year: 0.38
    ("CBAN", "net_income", 2025, "Q4"): (7_843_000, CBAN_10K),
}
EXPORTED = datetime(2026, 11, 2, 12, tzinfo=timezone.utc)
FILING_FORMS = ("10-K", "10-K/A", "10-Q", "10-Q/A")


def _document(cik: str, accession: str) -> str:
    return f"{build_sec_archive_url(cik, accession)}primary.htm"


@pytest.fixture(scope="module")
def corpus():
    """Each case synced once into its own database: {ticker: (session, company, payload)}."""
    built, engines = {}, []
    for ticker, (folder, sic, _why) in CORPUS.items():
        payload = json.loads((FIXTURES / folder / f"{ticker}.json").read_text())
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        engines.append(engine)
        db = sessionmaker(**{**SessionLocal.kw, "bind": engine})()
        cik = str(int(payload["cik"]))
        company = Company(cik=cik, ticker=ticker, name=payload.get("entityName") or ticker, sic=sic)
        db.add(company)
        db.flush()
        listed: dict[str, tuple[str, str, str]] = {}  # accession -> (filed, form, its latest period end)
        for node in payload["facts"]["us-gaap"].values():
            for items in node["units"].values():
                for item in items:
                    if item.get("form") in FILING_FORMS:
                        filed, _form, end = listed.get(item["accn"], ("", "", ""))
                        listed[item["accn"]] = (max(filed, item["filed"]), item["form"], max(end, item["end"]))
        for accession, (filed, form, end) in listed.items():
            db.add(Filing(company_id=company.id, accession_number=accession, filing_type=form,
                          filing_date=datetime.fromisoformat(filed).replace(tzinfo=timezone.utc),
                          period_end_date=datetime.fromisoformat(end).replace(tzinfo=timezone.utc),
                          document_url=_document(cik, accession), sec_url=build_sec_archive_url(cik, accession),
                          processed_facts_at=EXPORTED))  # its own write ran: the sync's rows stand in for it
        db.commit()

        async def fetch(_cik, payload=payload):
            return payload

        result = asyncio.run(ingest_companyfacts(db, company, force=True, fetcher=fetch))
        assert result["synced"] and result["inserted"], ticker
        built[ticker] = (db, company, payload)
    yield built
    for db, _company, _payload in built.values():
        db.close()
    for engine in engines:
        engine.dispose()


def _current(db, company) -> dict[tuple[str, int, str], FinancialFact]:
    rows = db.query(FinancialFact).filter(
        FinancialFact.company_id == company.id, FinancialFact.is_latest.is_(True),
        FinancialFact.fiscal_period.isnot(None), FinancialFact.fiscal_year.isnot(None))
    return {(row.concept, row.fiscal_year, row.fiscal_period): row for row in rows}


def _datasets(db, company) -> list[dict]:
    """The last ten fiscal years and the last twelve quarters the company stores, as the page builds them."""
    keys = list(_current(db, company))
    years = sorted({year for _concept, year, period in keys if period == "FY"})
    quarters = sorted({(year, period) for _concept, year, period in keys if period in ("Q1", "Q2", "Q3", "Q4")})
    built = []
    if years:
        built.append(trend_analysis_service.build_dataset(db, company, "annual", f"FY{years[-10:][0]}",
                                                          f"FY{years[-1]}"))
    if quarters:
        first, last = quarters[-12:][0], quarters[-1]
        built.append(trend_analysis_service.build_dataset(db, company, "quarterly", f"{first[0]}{first[1]}",
                                                          f"{last[0]}{last[1]}"))
    return built


def _valued(dataset: dict):
    for series in dataset["series"]:
        for point in series["points"]:
            if point.get("value") is not None:
                yield series, point


def _inputs(provenance: dict | None):
    """Every input of a calculation, at any depth: an input's own inputs follow it."""
    for operand in (provenance or {}).get("inputs") or ():
        yield operand
        yield from _inputs(operand.get("provenance"))


def _opens(cik: str, accession: str) -> tuple[str, str]:
    """The links that open an accession's own filing: its folder and its primary document."""
    return build_sec_archive_url(cik, accession), _document(cik, accession)


def _item(html: str, label: str, printed: str) -> str:
    """The PDF's Sources & methods item that opens with ``printed`` under its metric's own heading, its inputs' list
    included, up to the next item of that metric."""
    head = f"<h3>{escape(label)}</h3>"
    start = html.index(head) + len(head)
    end = html.find("<h3>", start)
    section = html[start:end if end != -1 else len(html)]
    begin = section.index(f"<li><strong>{printed}")
    after = section.find("<li><strong>", begin + 1)  # an input's item never opens with a bold label
    return section[begin:after if after != -1 else len(section)]


@pytest.mark.parametrize("ticker", list(CORPUS))
def test_every_analysis_figure_is_its_stored_current_row_and_links_its_own_filing(corpus, ticker):
    db, company, _payload = corpus[ticker]
    current = _current(db, company)
    datasets = _datasets(db, company)
    assert datasets, ticker
    checked = 0
    for dataset in datasets:
        for series, point in _valued(dataset):
            row = current[(series["concept"], point["fiscal_year"], point["fiscal_period"])]
            assert (point["value"], point["unit"], point["accession"]) == (
                published_value(row), row.unit, row.accession), (ticker, series["concept"], point["period"])
            assert point["unit"] in ("USD", "USD/shares", "pure"), (ticker, series["concept"], point["unit"])
            provenance = point.get("provenance") or {}
            assert provenance.get("method") in ("reported", "calculated"), (ticker, series["concept"], point["period"])
            if provenance["method"] == "reported":  # its own filing; a calculated value links its inputs'
                assert point.get("source_url") in _opens(company.cik, point["accession"]), (ticker, point["period"])
                assert provenance.get("source_url") == point["source_url"], (ticker, point["period"])
            else:
                assert list(_inputs(provenance)), (ticker, series["concept"], point["period"])
            for key in ("provenance", "yoy_provenance", "qoq_provenance"):  # the value's inputs, and each change's
                for operand in _inputs(point.get(key)):
                    opens = _opens(company.cik, operand["accession"])
                    if (operand.get("provenance") or {}).get("method") == "reported":
                        assert operand.get("source_url") in opens, (ticker, point["period"], key, operand["concept"])
                    else:  # a calculated input links its row's own filing or nothing: its own inputs carry the links
                        assert operand.get("source_url") in (None, *opens), (ticker, point["period"], key)
                        assert list(_inputs(operand.get("provenance"))), (ticker, point["period"], key)
            checked += 1
    assert checked, ticker


@pytest.mark.parametrize("ticker", list(CORPUS))
def test_the_workbook_and_the_pdf_print_every_figure_the_page_shows(corpus, ticker):
    db, company, _payload = corpus[ticker]
    for dataset in _datasets(db, company):
        workbook = load_workbook(io.BytesIO(build_analysis_workbook(dataset, exported_at=EXPORTED)))
        metrics, sources = workbook["Metrics"], workbook["Sources & methods"]
        columns = {cell.value: cell.column for cell in metrics[1]}
        rows = {metrics.cell(row=index, column=2).value: index for index in range(2, metrics.max_row + 1)}
        listed: dict[tuple, set] = {}  # (metric, period) -> its (entry, concept, value, unit, accession, link) rows
        for row in sources.iter_rows(min_row=2, values_only=True):
            listed.setdefault((row[0], row[1]), set()).add((row[2], row[3], row[4], row[5], row[12], row[15]))
        analysis = SimpleNamespace(mode=dataset["mode"], period_key=dataset["period_key"], dataset_json=dataset,
                                   narrative_md="", citations_json=[])
        html = ExportService().generate_analysis_pdf_html(analysis, SimpleNamespace(
            ticker=company.ticker, name=company.name, cik=company.cik))
        for series, point in _valued(dataset):
            period = period_label(point["period"])
            cell = metrics.cell(row=rows[series["concept"]], column=columns[period])
            expected = point["value"] / 100 if series.get("percent") else point["value"]
            assert cell.value == pytest.approx(expected), (ticker, series["concept"], point["period"])
            unit = "percent" if series.get("percent") else series.get("unit")
            provenance = point.get("provenance") or {}
            entries = {("Value", series["concept"], point["value"], unit, point["accession"],
                        point.get("source_url") or provenance.get("source_url"))}
            entries |= {(entry, operand.get("concept"), operand.get("value"), operand.get("unit"),
                         operand.get("accession"), operand.get("source_url"))
                        for entry, operand in operand_records(provenance)}
            label = series.get("label", series["concept"])
            assert entries <= listed[(label, period)], (ticker, series["concept"], point["period"])
            item = _item(html, label, f"{period} · Value</strong>: {raw_value_text(point['value'])} {escape(unit)}")
            own, inputs = item.split('<ul class="operands">', 1)[0], list(_inputs(provenance))
            for link in ([point["source_url"]] if point.get("source_url") else []):
                assert f'href="{escape(link, quote=True)}"' in own, (ticker, series["concept"], point["period"])
            for operand in inputs:
                assert f'href="{escape(operand["source_url"], quote=True)}"' in item, (ticker, point["period"])


@pytest.mark.parametrize("ticker", list(CORPUS))
def test_each_10ks_financial_trends_read_that_filings_own_rows_as_it_filed_them(corpus, ticker):
    db, company, payload = corpus[ticker]
    filings = db.query(Filing).filter(Filing.company_id == company.id, Filing.filing_type == "10-K").all()
    assert filings, ticker
    checked = 0
    for filing in filings:
        chart = get_filing_fundamentals(db, filing.id)
        own = {(row.concept, row.period_end.isoformat()): row for row in db.query(FinancialFact).filter(
            FinancialFact.company_id == company.id, FinancialFact.accession == filing.accession_number,
            FinancialFact.fiscal_period == "FY")}
        for line in (chart or {}).get("concepts") or ():
            for point in line["points"]:
                if point.get("value") is None:
                    continue
                row = own[(line["concept"], point["period_end"])]
                assert (point["accession"], point["value"]) == (filing.accession_number, published_value(row)), (
                    ticker, filing.accession_number, line["concept"], point["period_end"])
                if row.raw_tag and row.source == "companyfacts":  # a reported figure: the filing's own item
                    assert _filed_value(payload, row) == point["value"], (ticker, row.accession, row.raw_tag)
                checked += 1
    assert checked, ticker


def _filed_value(payload: dict, row: FinancialFact) -> float | None:
    """The value the row's own filing reported for its span under the row's tag, as SEC's companyfacts lists it."""
    tag = row.raw_tag.split(":", 1)[1]
    items = payload["facts"]["us-gaap"].get(tag, {}).get("units", {}).get(row.unit) or []
    values = {item["val"] for item in items
              if item["accn"] == row.accession and item["end"] == row.period_end.isoformat()
              and (row.period_start is None or item.get("start") == row.period_start.isoformat())}
    return values.pop() if len(values) == 1 else None


@pytest.mark.parametrize("ticker", list(CORPUS))
def test_the_peers_panel_ranks_the_stored_current_figure_of_the_latest_year(corpus, ticker):
    # The panel ranks a commercial bank on net interest income and every other company on revenue (D-072), so it
    # reads the subject's industry figure: its current FY row of the latest year, or none.
    db, company, _payload = corpus[ticker]
    answer = get_peers(db, ticker)
    assert answer["concept"] == default_concept_for(company.sic)
    years = {year: row for (concept, year, period), row in _current(db, company).items()
             if concept == answer["concept"] and period == "FY"}
    subject = answer["subject"]
    if not years:
        assert subject["value"] is None, (ticker, answer["concept"])
        return
    latest = years[max(years)]
    assert (subject["value"], subject["fiscal_year"], subject["period_end"]) == (
        published_value(latest), latest.fiscal_year, latest.period_end.isoformat()), (ticker, answer["concept"])


@pytest.mark.parametrize("ticker, concept, year, period", list(READ_OFF))
def test_a_figure_read_off_its_filing_is_current_at_that_filing_and_the_analysis_shows_it(corpus, ticker, concept, year,
                                                                                         period):
    # The checks above hold each surface to the stored winner; this holds the winner to the filing. The workbook, the
    # PDF and the peers panel print the analysis's point and the current row, so they print this figure too.
    db, company, _payload = corpus[ticker]
    value, accession = READ_OFF[(ticker, concept, year, period)]
    row = _current(db, company)[(concept, year, period)]
    expected = (pytest.approx(value, rel=1e-9, abs=0), accession)
    assert (published_value(row), row.accession) == expected, (ticker, concept)
    shown = [(point["value"], point["accession"]) for dataset in _datasets(db, company)
             for series, point in _valued(dataset)
             if series["concept"] == concept and (point["fiscal_year"], point["fiscal_period"]) == (year, period)]
    assert shown == [expected], (ticker, concept, shown)
