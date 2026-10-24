"""Annual per-filing facts carry the issuer's fiscal year, so both fact writers label a period alike.

The fact identity (concept, period_end, fiscal_period, unit, accession) leaves out the fiscal
year, so whichever writer stores an identity first keeps its label and the other is skipped. The
companyfacts writer names a year from SEC's timely original annual reports; the per-filing writer
used to name every 10-K point by the calendar year of its end. For an issuer whose fiscal year is
named for the year it starts in (a retailer's year ending around 1 February) or a 52-week year
that ends on 1 January, the two disagreed, and the label depended on which writer ran first. These
tests drive the production paths end to end: the instance extractor and the companyfacts fallback,
the standardized metrics, the per-filing writer, the companyfacts writer, the Multi-Period
Analysis dataset and coverage, and the filing page's annual chart. Where companyfacts already
names a period's year, the per-filing writer moves the filing's annual years onto that year chain
by one offset, so an issuer that names a January year by its end keeps its names when its 10-K's
focus lags (Salesforce, CrowdStrike, Veeva, Best Buy). Each issuer runs with its annual reports
filed on time and with all of them filed late, whose year chain the companyfacts writer names from the
late reports' own years; and each writer names an equity statement's oldest opening balance by the year
that ends on its date. A lagging focus opened before the first companyfacts sync is repaired by the
stored-row relabel (``lessons/sec-fact-writers-name-a-period-alike.md``).
"""
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Query, sessionmaker

from app.models import Base, Company, Filing, FinancialFact
from app.services import copilot_tools, facts_service, quarterly_fact_repair
from app.services import trend_analysis_service as analysis
from app.services.edgar import fiscal_periods, xbrl_instance
from app.services.facts import fiscal_evidence
from app.services.edgar.xbrl_companyfacts import parse_company_facts
from app.services.edgar.xbrl_standardized import extract_standardized_metrics
from app.utils.sec_urls import build_sec_archive_url

pytestmark = pytest.mark.unit

# (start, end) of four fiscal years, keyed by the issuer's own fiscal-year name.
CALENDARS = {
    # Target: the Saturday nearest 31 January; fiscal 2024 ended 1 February 2025.
    "target": {2021: ("2021-01-31", "2022-01-29"), 2022: ("2022-01-30", "2023-01-28"),
               2023: ("2023-01-29", "2024-02-03"), 2024: ("2024-02-04", "2025-02-01")},
    # Home Depot: the Sunday nearest 31 January; fiscal 2024 was 53 weeks, ending 2 February 2025.
    "home_depot": {2021: ("2021-02-01", "2022-01-30"), 2022: ("2022-01-31", "2023-01-29"),
                   2023: ("2023-01-30", "2024-01-28"), 2024: ("2024-01-29", "2025-02-02")},
    # Johnson & Johnson: the Sunday nearest 31 December; fiscal 2021 and 2022 ended on 2 and 1 January.
    "jnj": {2021: ("2021-01-04", "2022-01-02"), 2022: ("2022-01-03", "2023-01-01"),
            2023: ("2023-01-02", "2023-12-31"), 2024: ("2024-01-01", "2024-12-29")},
    # Apple: the last Saturday of September; the calendar year of the end already names the year.
    "apple": {2021: ("2020-09-27", "2021-09-25"), 2022: ("2021-09-26", "2022-09-24"),
              2023: ("2022-09-25", "2023-09-30"), 2024: ("2023-10-01", "2024-09-28")},
    # A December filer whose newest 10-K's DEI focus lags its year (DEI_FOCUS): its calendar year
    # names the year, and one filing's outlier focus must not move it.
    "december_lagging_focus": {2021: ("2021-01-01", "2021-12-31"), 2022: ("2022-01-01", "2022-12-31"),
                               2023: ("2023-01-01", "2023-12-31"), 2024: ("2024-01-01", "2024-12-31")},
    # Foreign private issuers filing a 20-F for a year ending 31 March: one names the year for the
    # calendar year it starts in (fiscal 2024 ended 31 March 2025), the other for the one it ends in.
    "march_named_by_start": {2021: ("2021-04-01", "2022-03-31"), 2022: ("2022-04-01", "2023-03-31"),
                             2023: ("2023-04-01", "2024-03-31"), 2024: ("2024-04-01", "2025-03-31")},
    "march_named_by_end": {2021: ("2020-04-01", "2021-03-31"), 2022: ("2021-04-01", "2022-03-31"),
                           2023: ("2022-04-01", "2023-03-31"), 2024: ("2023-04-01", "2024-03-31")},
    # Issuers that name a January year by its end, whose newest 10-K's DEI focus names the year before
    # (LAGGING_FOCUS): Salesforce's fiscal 2026 ended 31 January 2026 (focus 2025), and likewise
    # CrowdStrike's fiscal 2025, Veeva's fiscal 2022 and Best Buy's fiscal 2021 (the Saturday nearest
    # 31 January). One filing cannot tell them from Target.
    "crm": {2023: ("2022-02-01", "2023-01-31"), 2024: ("2023-02-01", "2024-01-31"),
            2025: ("2024-02-01", "2025-01-31"), 2026: ("2025-02-01", "2026-01-31")},
    "crwd": {2022: ("2021-02-01", "2022-01-31"), 2023: ("2022-02-01", "2023-01-31"),
             2024: ("2023-02-01", "2024-01-31"), 2025: ("2024-02-01", "2025-01-31")},
    "veev": {2019: ("2018-02-01", "2019-01-31"), 2020: ("2019-02-01", "2020-01-31"),
             2021: ("2020-02-01", "2021-01-31"), 2022: ("2021-02-01", "2022-01-31")},
    "bby": {2018: ("2017-01-29", "2018-02-03"), 2019: ("2018-02-04", "2019-02-02"),
            2020: ("2019-02-03", "2020-02-01"), 2021: ("2020-02-02", "2021-01-30")},
}
# Each annual report: its accession and filing date (within SEC's timely-original window).
ANNUAL_REPORTS = {
    "target": {2023: ("0000027419-24-000010", "2024-03-13"), 2024: ("0000027419-25-000010", "2025-03-12")},
    "home_depot": {2023: ("0000354950-24-000016", "2024-03-13"), 2024: ("0000354950-25-000013", "2025-03-21")},
    "jnj": {2023: ("0000200406-24-000013", "2024-02-16"), 2024: ("0000200406-25-000038", "2025-02-13")},
    "apple": {2023: ("0000320193-23-000106", "2023-11-03"), 2024: ("0000320193-24-000123", "2024-11-01")},
    "december_lagging_focus": {2023: ("0000000102-24-000001", "2024-02-15"),
                               2024: ("0000000102-25-000001", "2025-02-14")},
    "march_named_by_start": {2023: ("0000000103-24-000001", "2024-06-25"),
                             2024: ("0000000103-25-000001", "2025-06-24")},
    "march_named_by_end": {2023: ("0000000104-23-000001", "2023-06-27"),
                           2024: ("0000000104-24-000001", "2024-06-25")},
    # Salesforce's 0001108524-26-000060 is its real fiscal 2026 10-K.
    "crm": {2025: ("0001108524-25-000006", "2025-03-05"), 2026: ("0001108524-26-000060", "2026-03-05")},
    "crwd": {2024: ("0001535527-24-000007", "2024-03-07"), 2025: ("0001535527-25-000009", "2025-03-10")},
    "veev": {2021: ("0001393052-21-000016", "2021-03-31"), 2022: ("0001393052-22-000009", "2022-03-30")},
    "bby": {2020: ("0000764478-20-000011", "2020-03-20"), 2021: ("0000764478-21-000011", "2021-03-19")},
}
# The annual form, where it is not a 10-K, and a DEI focus that differs from the year's own name.
FORMS = {"march_named_by_start": "20-F", "march_named_by_end": "20-F"}
LAGGING_FOCUS = {"bby": 2021, "crm": 2026, "crwd": 2025, "veev": 2022}  # The 10-K whose focus lags a year.
DEI_FOCUS = {("december_lagging_focus", 2024): 2023, **{(issuer, fy): fy - 1 for issuer, fy in LAGGING_FOCUS.items()}}
REVENUE = {fy: 1_000.0 + 100 * (fy - 2021) for fy in range(2018, 2027)}
EQUITY = {fy: 900.0 + 100 * (fy - 2020) for fy in range(2017, 2027)}
NET_INCOME = {fy: 100.0 + 10 * (fy - 2021) for fy in range(2018, 2027)}
ASSETS = {fy: 5_000.0 + 200 * (fy - 2021) for fy in range(2018, 2027)}


@pytest.fixture
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'labels.sqlite'}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _filed(issuer: str, report_fy: int, late: bool = False) -> str:
    """When the annual report was filed: within SEC's timely-original window, or 250 days after its year's end."""
    if not late:
        return ANNUAL_REPORTS[issuer][report_fy][1]
    return (date.fromisoformat(CALENDARS[issuer][report_fy][1]) + timedelta(days=250)).isoformat()


def _company(db, issuer: str, late: bool = False) -> Company:
    company = Company(cik="0000000001", ticker=issuer.upper()[:5], name=issuer)
    db.add(company)
    db.flush()
    for report_fy, (accession, _filed_on_time) in ANNUAL_REPORTS[issuer].items():
        url = build_sec_archive_url(company.cik, accession)
        db.add(Filing(
            company_id=company.id, accession_number=accession, filing_type=FORMS.get(issuer, "10-K"),
            filing_date=datetime.fromisoformat(_filed(issuer, report_fy, late)).replace(tzinfo=timezone.utc),
            period_end_date=datetime.fromisoformat(CALENDARS[issuer][report_fy][1]).replace(tzinfo=timezone.utc),
            sec_url=url, document_url=f"{url}annual.htm",
        ))
    db.commit()
    return company


class _Facts:
    """The edgartools fact query the instance extractor reads: one frame per concept."""

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


def _instance_xbrl(monkeypatch, issuer: str, report_fy: int, form: str | None = None, equity: bool = False) -> dict:
    """The real instance extractor over one annual report's XBRL; DEI as edgartools reads it. With
    ``equity``, its equity statement's four balances, the oldest closing the year before its first."""
    calendar = CALENDARS[issuer]
    years = (report_fy, report_fy - 1, report_fy - 2)

    def duration(fy, value):
        return {"is_dimensioned": False, "period_start": calendar[fy][0], "period_end": calendar[fy][1],
                "numeric_value": value, "decimals": -6, "currency": "USD"}

    frames = {
        "Revenues": pd.DataFrame([duration(fy, REVENUE[fy]) for fy in years]),
        "NetIncomeLoss": pd.DataFrame([duration(fy, NET_INCOME[fy]) for fy in years]),
        "Assets": pd.DataFrame([
            {"is_dimensioned": False, "period_start": None, "period_end": None,
             "period_instant": calendar[fy][1], "numeric_value": ASSETS[fy], "decimals": -6, "currency": "USD"}
            for fy in years[:2]
        ]),
    }
    if equity:
        frames["StockholdersEquity"] = pd.DataFrame([
            {"is_dimensioned": False, "period_start": None, "period_end": None, "period_instant": end,
             "numeric_value": EQUITY[fy], "decimals": -6, "currency": "USD"}
            for fy, end in _equity_ends(issuer, report_fy).items()
        ])
    focus = str(DEI_FOCUS.get((issuer, report_fy), report_fy))
    xb = SimpleNamespace(facts=_Facts(frames), entity_info={"fiscal_year": focus, "fiscal_period": "FY"})
    sec_filing = SimpleNamespace(form=form or FORMS.get(issuer, "10-K"), period_of_report=calendar[report_fy][1],
                                 xbrl=lambda: xb)
    monkeypatch.setattr(xbrl_instance, "resolve_filing_by_accession",
                        lambda *args: (SimpleNamespace(sic=None), [sec_filing]))
    return xbrl_instance._extract_from_filing_instance_sync("0000000001", ANNUAL_REPORTS[issuer][report_fy][0])


def _equity_ends(issuer: str, report_fy: int) -> dict[int, str]:
    """An equity statement's balances: the end of each of the report's three years, and of the year before."""
    calendar = CALENDARS[issuer]
    ends = {fy: calendar[fy][1] for fy in (report_fy, report_fy - 1, report_fy - 2)}
    return {**ends, report_fy - 3: (date.fromisoformat(calendar[report_fy - 2][0]) - timedelta(days=1)).isoformat()}


def _open_annual_report(db, monkeypatch, issuer: str, report_fy: int, equity: bool = False) -> Filing:
    """A reader opens the annual report: the SSE enrichment path writes that filing's own facts."""
    raw = _instance_xbrl(monkeypatch, issuer, report_fy, equity=equity)
    filing = db.query(Filing).filter_by(accession_number=ANNUAL_REPORTS[issuer][report_fy][0]).one()
    facts_service.process_filing_facts(db, filing, standardized=extract_standardized_metrics(raw))
    return filing


def _companyfacts(issuer: str, reports: tuple[int, ...], form: str | None = None, *, late: bool = False,
                  equity: bool = False) -> dict:
    """SEC companyfacts: every item carries the fy/fp and form of the annual report that reported it.
    ``late`` files every report 250 days after its year's end; ``equity`` adds each report's equity statement."""
    calendar = CALENDARS[issuer]
    items: dict[str, list] = {"Revenues": [], "NetIncomeLoss": [], "Assets": [], "StockholdersEquity": []}
    for report_fy in reports:
        accession, _filed_on_time = ANNUAL_REPORTS[issuer][report_fy]
        source = {"fy": DEI_FOCUS.get((issuer, report_fy), report_fy), "fp": "FY",
                  "form": form or FORMS.get(issuer, "10-K"), "accn": accession, "filed": _filed(issuer, report_fy, late)}
        for fy in (report_fy - 2, report_fy - 1, report_fy):
            start, end = calendar[fy]
            items["Revenues"].append({**source, "start": start, "end": end, "val": REVENUE[fy]})
            items["NetIncomeLoss"].append({**source, "start": start, "end": end, "val": NET_INCOME[fy]})
        for fy in (report_fy - 1, report_fy):
            items["Assets"].append({**source, "end": calendar[fy][1], "val": ASSETS[fy]})
        if equity:
            items["StockholdersEquity"] += [{**source, "end": end, "val": EQUITY[fy]}
                                            for fy, end in _equity_ends(issuer, report_fy).items()]
    items = {tag: rows for tag, rows in items.items() if rows}
    return {"cik": 1, "entityName": issuer,
            "facts": {"us-gaap": {tag: {"units": {"USD": rows}} for tag, rows in items.items()}}}


def _latest_fy_labels(db, company: Company, concept: str) -> dict[date, int]:
    rows = db.query(FinancialFact).filter_by(
        company_id=company.id, concept=concept, fiscal_period="FY", is_latest=True,
    ).all()
    return {row.period_end: row.fiscal_year for row in rows}


def _issuer_years(issuer: str, years=(2021, 2022, 2023, 2024)) -> dict[date, int]:
    return {date.fromisoformat(CALENDARS[issuer][fy][1]): fy for fy in years}


ORDERS = ("filing_then_companyfacts", "companyfacts_then_filing", "stale_sync_then_filing_then_resync")


@pytest.mark.parametrize("filed", ["on_time", "late"])
@pytest.mark.parametrize("order", ORDERS)
@pytest.mark.parametrize("issuer", sorted(set(CALENDARS) - set(LAGGING_FOCUS)))
def test_both_fact_writers_name_the_issuers_fiscal_year_in_either_order(db, monkeypatch, issuer, order, filed):
    """Whether the annual reports were filed on time or all of them late. A late report's year chain holds
    no timely original to name it, so the companyfacts writer names it from the late reports' own years,
    trusted as the per-filing writer trusts a focus; before, it fell back to calendar years."""
    late = filed == "late"
    company = _company(db, issuer, late=late)
    if order == "filing_then_companyfacts":
        _open_annual_report(db, monkeypatch, issuer, 2024)
        facts_service._persist_companyfacts_payload(db, company, _companyfacts(issuer, (2023, 2024), late=late))
    elif order == "companyfacts_then_filing":
        facts_service._persist_companyfacts_payload(db, company, _companyfacts(issuer, (2023, 2024), late=late))
        _open_annual_report(db, monkeypatch, issuer, 2024)
    else:  # Synced before the newest annual report existed; a reader opens it; the next sync runs.
        facts_service._persist_companyfacts_payload(db, company, _companyfacts(issuer, (2023,), late=late))
        _open_annual_report(db, monkeypatch, issuer, 2024)
        facts_service._persist_companyfacts_payload(db, company, _companyfacts(issuer, (2023, 2024), late=late))

    assert _latest_fy_labels(db, company, "revenue") == _issuer_years(issuer)
    assert _latest_fy_labels(db, company, "net_income") == _issuer_years(issuer)
    assert _latest_fy_labels(db, company, "total_assets") == _issuer_years(issuer, (2022, 2023, 2024))

    coverage = analysis.available_periods(db, company.id)
    assert [period["key"] for period in coverage["annual"]] == ["FY2021", "FY2022", "FY2023", "FY2024"]
    dataset = analysis.build_dataset(db, company, "annual", "FY2021", "FY2024")
    assert [period["period_end"] for period in dataset["periods"]] == [
        CALENDARS[issuer][fy][1] for fy in (2021, 2022, 2023, 2024)
    ]
    revenue = next(series for series in dataset["series"] if series["concept"] == "revenue")
    assert [point["value"] for point in revenue["points"]] == [REVENUE[fy] for fy in (2021, 2022, 2023, 2024)]
    assert revenue["points"][1]["yoy"] == pytest.approx(0.1)
    assert revenue["cagr_window"] == "FY2021..FY2024"


@pytest.mark.parametrize("order", ORDERS[:2])
@pytest.mark.parametrize("issuer", sorted(set(CALENDARS) - set(LAGGING_FOCUS)))
def test_both_writers_name_the_oldest_opening_balance_by_the_year_ending_on_its_date(db, monkeypatch, issuer, order):
    """The fiscal 2023 report's equity statement opens with the balance that closed fiscal 2020, older than
    every fiscal-year window companyfacts holds. Both writers name it fiscal 2020, whichever stores it
    first: Target's balance of 30 January 2021 and J&J's of 3 January 2021 close fiscal 2020, not 2021."""
    company = _company(db, issuer)
    payload = _companyfacts(issuer, (2023, 2024), equity=True)
    if order == "filing_then_companyfacts":
        _open_annual_report(db, monkeypatch, issuer, 2023, equity=True)
        facts_service._persist_companyfacts_payload(db, company, payload)
    else:
        facts_service._persist_companyfacts_payload(db, company, payload)
        _open_annual_report(db, monkeypatch, issuer, 2023, equity=True)

    opening = date.fromisoformat(_equity_ends(issuer, 2023)[2020])
    assert _latest_fy_labels(db, company, "shareholders_equity") == {opening: 2020, **_issuer_years(issuer)}


def _switched_year_end(reports: tuple[str, ...]) -> dict:
    """Companyfacts for an issuer that left Target's January year for a June one: its 10-K for fiscal 2022
    (ended 28 January 2023), and its 10-K for the year ended 30 June 2025, after a transition period. Each
    reports two years' revenue and its equity statement's balances, the oldest opening it."""
    target = {"fy": 2022, "fp": "FY", "form": "10-K", "accn": "0000000105-23-000010", "filed": "2023-03-15"}
    june = {"fy": 2025, "fp": "FY", "form": "10-K", "accn": "0000000105-25-000020", "filed": "2025-08-20"}
    revenue, equity = [], []
    if "target" in reports:
        revenue += [{**target, "start": "2021-01-31", "end": "2022-01-29", "val": 1_000.0},
                    {**target, "start": "2022-01-30", "end": "2023-01-28", "val": 1_100.0}]
        equity += [{**target, "end": end, "val": 900.0} for end in ("2021-01-30", "2022-01-29", "2023-01-28")]
    if "june" in reports:
        revenue += [{**june, "start": "2023-07-01", "end": "2024-06-30", "val": 1_300.0},
                    {**june, "start": "2024-07-01", "end": "2025-06-30", "val": 1_400.0}]
        equity += [{**june, "end": end, "val": 950.0} for end in ("2023-01-28", "2023-06-30", "2024-06-30", "2025-06-30")]
    return {"cik": 1, "facts": {"us-gaap": {"Revenues": {"units": {"USD": revenue}},
                                            "StockholdersEquity": {"units": {"USD": equity}}}}}


def _equity_years(payload: dict) -> dict[str, int]:
    facts, _meta = facts_service.normalize_companyfacts(1, payload)
    return {f["period_end"].isoformat(): f["fiscal_year"] for f in facts
            if f["concept"] == "shareholders_equity" and f["fiscal_period"] == "FY"}


def test_an_opening_balance_counts_back_from_the_nearest_year_chain_after_it():
    """Target's oldest balance (30 January 2021) counts back from Target's own chain, the nearest after it,
    and closes fiscal 2020; the June chain after the switch is no whole number of years away."""
    assert _equity_years(_switched_year_end(("target", "june")))["2021-01-30"] == 2020


def test_a_balance_no_whole_number_of_years_before_a_chain_keeps_the_calendar_year_of_its_end():
    """Synced without the Target report, the June 10-K's equity statement opens at the old year's end
    (28 January 2023), which no whole number of years puts before the June chain: it keeps the calendar year
    of its end, as the per-filing labeller does. The transition's close (30 June 2023) is a whole year before
    that chain's first, so it closes the year before."""
    assert _equity_years(_switched_year_end(("june",))) == {
        "2023-01-28": 2023, "2023-06-30": 2023, "2024-06-30": 2024, "2025-06-30": 2025,
    }
    assert fiscal_periods.annual_fiscal_label("2023-01-28", "2025-06-30", 2025, "FY") == {}


@pytest.mark.parametrize("issuer,years", [
    # The report's own period (fiscal 2024, ended 1 February 2025) names the chain, never the comparative a
    # year back that the same report also tags fy 2024.
    ("target", [2022, 2023, 2024]),
    ("march_named_by_start", [2022, 2023, 2024]),
    # A lagging focus on a December year is not trusted, here as in the per-filing writer: calendar years.
    ("december_lagging_focus", [2022, 2023, 2024]),
])
def test_a_late_reports_own_period_names_its_year_chain(issuer, years):
    """The only annual report in companyfacts was filed 250 days late and carries two comparative years."""
    facts, _meta = facts_service.normalize_companyfacts(1, _companyfacts(issuer, (2024,), late=True))

    revenue = {f["period_end"]: f["fiscal_year"] for f in facts if f["concept"] == "revenue" and f["fiscal_period"] == "FY"}
    assert revenue == {date.fromisoformat(CALENDARS[issuer][fy][1]): fy for fy in years}


def test_a_chain_a_timely_report_names_keeps_that_naming_beside_late_reports():
    """Late reports' own years name a chain only where no timely original names it, so a chain with one is
    named as before these rules. A December filer's fiscal 2023 report filed late beside its timely fiscal
    2024 10-K, whose focus lags (2023): the timely report's year stands, one low, while the per-filing
    labeller, which trusts no lagging focus on a December year, keeps calendar years (a known limit in
    ``lessons/sec-fact-writers-name-a-period-alike.md``). Taking the late report first would change every
    chain that holds both."""
    payload = _companyfacts("december_lagging_focus", (2023, 2024))
    late_accession = ANNUAL_REPORTS["december_lagging_focus"][2023][0]
    for node in payload["facts"]["us-gaap"].values():
        for item in node["units"]["USD"]:
            if item["accn"] == late_accession:
                item["filed"] = _filed("december_lagging_focus", 2023, late=True)
    facts, _meta = facts_service.normalize_companyfacts(1, payload)

    revenue = {f["period_end"]: f["fiscal_year"] for f in facts if f["concept"] == "revenue" and f["fiscal_period"] == "FY"}
    assert revenue == {date.fromisoformat(CALENDARS["december_lagging_focus"][fy][1]): fy - 1 for fy in (2021, 2022, 2023, 2024)}
    assert fiscal_periods.annual_fiscal_label("2024-12-31", "2024-12-31", 2023, "FY") == {}


def test_a_late_year_chains_quarters_take_its_fiscal_years():
    """Target's first quarter of fiscal 2024 (ended 4 May 2024) lies in a year chain no timely annual report
    names. Its 10-Q labeller names it fiscal 2024 from the 10-Q's focus, and so does the companyfacts writer."""
    payload = _companyfacts("target", (2023, 2024), late=True)
    payload["facts"]["us-gaap"]["Revenues"]["units"]["USD"].append({
        "fy": 2024, "fp": "Q1", "form": "10-Q", "accn": "0000027419-24-000020", "filed": "2024-06-05",
        "start": "2024-02-04", "end": "2024-05-04", "val": 250.0,
    })
    facts, _meta = facts_service.normalize_companyfacts(1, payload)

    quarter = [(f["fiscal_year"], f["fiscal_period"]) for f in facts
               if f["concept"] == "revenue" and f["period_end"] == date(2024, 5, 4)]
    assert quarter == [(2024, "Q1")]
    assert fiscal_periods.filing_point_label("10-Q", "2024-05-04", "2024-05-04", 2024, "Q1") == {
        "fiscal_year": 2024, "fiscal_period": "Q1",
    }


@pytest.mark.parametrize("stored_before", ["opening_balance", "late_chain"])
def test_the_audited_quarterly_repair_relabels_rows_the_writer_named_before(db, stored_before):
    """A sync is insert-only, so the rows the companyfacts writer stored before these rules keep their
    labels: the oldest opening balance under the calendar year of its end, a late chain under calendar
    years. The audited quarterly repair (``scripts/repair_quarterly_facts.py``) re-normalizes the
    payload and relabels them, journaled; nothing else in the company changes."""
    late = stored_before == "late_chain"
    company = _company(db, "target", late=late)
    payload = _companyfacts("target", (2023, 2024), late=late, equity=not late)
    facts_service._persist_companyfacts_payload(db, company, payload)
    rows = db.query(FinancialFact).filter_by(company_id=company.id, fiscal_period="FY").all()
    named = {row.id: row.fiscal_year for row in rows}
    for row in rows:  # the labels the writer gave them before
        if late or row.period_end == date.fromisoformat(_equity_ends("target", 2023)[2020]):
            row.fiscal_year = row.period_end.year
    db.commit()
    stale = sum(row.fiscal_year != named[row.id] for row in rows)

    result = quarterly_fact_repair.repair_company(db, company.id, payload, dry_run=False, run_id="relabel")
    db.commit()

    assert stale == result["revisions"] == (15 if late else 1)
    assert {row.id: row.fiscal_year for row in db.query(FinancialFact).filter_by(
        company_id=company.id, fiscal_period="FY")} == named


def test_the_audited_quarterly_repair_moves_a_late_chain_only_in_part_when_a_reader_opened_its_newer_report(
        db, monkeypatch):
    """The limit ``docs/fiscal-year-label-repair.md`` tells the founder to preview for. A delinquent Target was
    synced through its fiscal 2023 report before these rules (calendar years); a reader then opened its
    fiscal 2024 10-K, which adopted that stored chain; the next sync skipped every identity the filing owns.
    The repair relabels a current row only where the writer still picks that row's report, so it moves each
    concept's years the newer report does not re-report and leaves those it does: revenue's fiscal 2022
    loses its row, and fiscal 2022's end carries 2022 for assets but 2023 for revenue."""
    company = _company(db, "target", late=True)
    facts_service._persist_companyfacts_payload(db, company, _companyfacts("target", (2023,), late=True))
    for row in db.query(FinancialFact).filter_by(company_id=company.id, fiscal_period="FY"):
        row.fiscal_year = row.period_end.year  # the labels the writer gave a late chain before
    db.commit()
    _open_annual_report(db, monkeypatch, "target", 2024)
    payload = _companyfacts("target", (2023, 2024), late=True)
    facts_service._persist_companyfacts_payload(db, company, payload)
    calendar_years = {date.fromisoformat(CALENDARS["target"][fy][1]): fy + 1 for fy in (2021, 2022, 2023, 2024)}
    assert _latest_fy_labels(db, company, "revenue") == calendar_years

    result = quarterly_fact_repair.repair_company(db, company.id, payload, dry_run=False, run_id="partial")
    db.commit()

    assert result["revisions"] == 4  # fiscal 2021's revenue, net income and net margin; fiscal 2022's assets
    assert _latest_fy_labels(db, company, "revenue") == {**calendar_years, date(2022, 1, 29): 2021}
    assert _latest_fy_labels(db, company, "total_assets")[date(2023, 1, 28)] == 2022


@pytest.mark.parametrize("issuer,expected", [
    ("jnj", [2022, 2023, 2024]),
    ("target", [2022, 2023, 2024]),
    ("apple", [2022, 2023, 2024]),
    ("december_lagging_focus", [2022, 2023, 2024]),
    ("march_named_by_start", [2022, 2023, 2024]),
])
def test_filing_chart_names_each_annual_bar_once_by_its_fiscal_year(db, monkeypatch, issuer, expected):
    _company(db, issuer)
    filing = _open_annual_report(db, monkeypatch, issuer, 2024)

    chart = facts_service.get_filing_fundamentals(db, filing.id)

    revenue = next(concept for concept in chart["concepts"] if concept["concept"] == "revenue")
    assert [point["period_end"] for point in revenue["points"]] == [
        CALENDARS[issuer][fy][1] for fy in (2022, 2023, 2024)
    ]
    assert [point["fiscal_year"] for point in revenue["points"]] == expected


def test_companyfacts_fallback_names_the_target_accessions_fiscal_years():
    accession = ANNUAL_REPORTS["target"][2024][0]
    raw = parse_company_facts(_companyfacts("target", (2023, 2024)), accession)

    assert [(point["period"], point.get("fiscal_year"), point.get("fiscal_period")) for point in raw["revenue"]] == [
        ("2025-02-01", 2024, "FY"), ("2024-02-03", 2023, "FY"), ("2023-01-28", 2022, "FY"),
    ]
    assert [(point["period"], point.get("fiscal_year")) for point in raw["total_assets"]] == [
        ("2025-02-01", 2024), ("2024-02-03", 2023),
    ]
    facts = facts_service.normalize_standardized_to_facts(
        1, 1, accession, "10-K", extract_standardized_metrics(raw),
    )
    assert {(f["concept"], f["period_end"].isoformat()): f["fiscal_year"] for f in facts
            if f["concept"] in {"revenue", "net_margin"}} == {
        ("revenue", "2025-02-01"): 2024, ("revenue", "2024-02-03"): 2023, ("revenue", "2023-01-28"): 2022,
        ("net_margin", "2025-02-01"): 2024, ("net_margin", "2024-02-03"): 2023, ("net_margin", "2023-01-28"): 2022,
    }


@pytest.mark.parametrize("issuer", ["apple", "march_named_by_end", "december_lagging_focus"])
def test_a_calendar_aligned_issuers_extracted_points_keep_their_exact_shape(monkeypatch, issuer):
    """The calendar year of each end names the fiscal year, so neither extractor adds a key.

    The persisted snapshot is what Copilot shows the model; it stays byte-identical for every
    issuer whose calendar year of the end already names the fiscal year: a September 10-K, a 20-F
    naming its March year by its end, and a December 10-K whose DEI focus lags a year.
    """
    instance = _instance_xbrl(monkeypatch, issuer, 2024)
    fallback = parse_company_facts(_companyfacts(issuer, (2023, 2024)), ANNUAL_REPORTS[issuer][2024][0])

    for raw in (instance, fallback):
        points = [point for key in ("revenue", "net_income", "total_assets") for point in raw[key]]
        assert points and not any({"fiscal_year", "fiscal_period"} & point.keys() for point in points)


@pytest.mark.parametrize("form", ["10-K/A", "20-F", "20-F/A", "40-F", "40-F/A"])
def test_every_annual_report_form_names_its_points_by_the_fiscal_year(monkeypatch, form):
    """An amended or foreign annual report's points are labelled like a 10-K's, by both extractors."""
    instance = _instance_xbrl(monkeypatch, "target", 2024, form=form)
    fallback = parse_company_facts(_companyfacts("target", (2023, 2024), form=form), ANNUAL_REPORTS["target"][2024][0])

    for raw in (instance, fallback):
        assert [(point["period"], point.get("fiscal_year"), point.get("fiscal_period")) for point in raw["revenue"]] == [
            ("2025-02-01", 2024, "FY"), ("2024-02-03", 2023, "FY"), ("2023-01-28", 2022, "FY"),
        ]


@pytest.mark.parametrize("end,report_end,focus,expected", [
    ("2025-02-01", "2025-02-01", "2024", {"fiscal_year": 2024, "fiscal_period": "FY"}),
    ("2023-01-28", "2025-02-01", 2024, {"fiscal_year": 2022, "fiscal_period": "FY"}),
    ("2023-01-01", "2024-12-29", 2024, {"fiscal_year": 2022, "fiscal_period": "FY"}),
    ("2023-01-01", "2023-01-01", 2022, {"fiscal_year": 2022, "fiscal_period": "FY"}),
    ("2024-03-31", "2025-03-31", 2024, {"fiscal_year": 2023, "fiscal_period": "FY"}),
    # The calendar year of the end already names it: the normalizer's default stands.
    ("2024-12-29", "2024-12-29", 2024, {}),
    ("2023-09-30", "2024-09-28", 2024, {}),
    ("2024-03-31", "2025-03-31", 2025, {}),
    # Not a whole number of years from the anchor (a transition period, a comparative 20 days off a
    # whole year), or after it.
    ("2024-08-03", "2025-02-01", 2024, {}),
    ("2024-01-13", "2025-02-01", 2024, {}),
    ("2026-01-31", "2025-02-01", 2024, {}),
    # A focus year that is neither the anchor's end year nor the one before is not trusted.
    ("2025-02-01", "2025-02-01", 2022, {}),
    ("2025-02-01", "2025-02-01", None, {}),
    ("2025-02-01", "2025-02-01", True, {}),
    ("2025-02-01", None, 2024, {}),
    # The year before only names a year that mostly lies in it: a lagging focus on a December year,
    # a late-December 52-week year or an August year is not trusted.
    ("2024-12-31", "2024-12-31", 2023, {}),
    ("2023-12-31", "2024-12-31", 2023, {}),
    ("2024-12-28", "2024-12-28", 2023, {}),
    ("2024-08-31", "2024-08-31", 2023, {}),
])
def test_annual_label_counts_whole_fiscal_years_back_from_the_filing_focus(end, report_end, focus, expected):
    assert fiscal_periods.annual_fiscal_label(end, report_end, focus, "FY") == expected


@pytest.mark.parametrize("fiscal_period", ["Q4", None])
def test_annual_label_trusts_only_a_full_year_focus(fiscal_period):
    assert fiscal_periods.annual_fiscal_label("2023-01-28", "2025-02-01", 2024, fiscal_period) == {}


def test_dataset_reads_a_balance_at_its_periods_end_whatever_its_label(db):
    """Companyfacts alone names an opening balance older than its first fiscal-year window by the year
    that ends on its date, one before that window's. It used to take the calendar year of its end, for
    a January year the next year's label, and a row it stored then keeps that label until a repair runs.
    The dataset reads rows in period-end order, so a label two period ends carry resolves to the latest,
    the axis bucket's own end, and such a clash never hides the year-end balance.
    """
    company = _company(db, "target")
    payload = _companyfacts("target", (2023,))
    accession, filed = ANNUAL_REPORTS["target"][2023]
    source = {"fy": 2023, "fp": "FY", "form": "10-K", "accn": accession, "filed": filed}
    equity = {"2021-01-30": 900.0, "2022-01-29": 1_000.0, "2023-01-28": 1_100.0, "2024-02-03": 1_200.0}
    payload["facts"]["us-gaap"]["StockholdersEquity"] = {"units": {"USD": [
        {**source, "end": end, "val": value} for end, value in equity.items()
    ]}}
    facts_service._persist_companyfacts_payload(db, company, payload)
    assert sorted(_latest_fy_labels(db, company, "shareholders_equity").items()) == [
        (date(2021, 1, 30), 2020), (date(2022, 1, 29), 2021), (date(2023, 1, 28), 2022), (date(2024, 2, 3), 2023),
    ]
    stored_before = db.query(FinancialFact).filter_by(  # the label the writer gave it before 2026-10-23
        company_id=company.id, concept="shareholders_equity", period_end=date(2021, 1, 30)).one()
    stored_before.fiscal_year = 2021
    db.commit()

    dataset = analysis.build_dataset(db, company, "annual", "FY2021", "FY2023")

    by_concept = {series["concept"]: series["points"] for series in dataset["series"]}
    assert [point["value"] for point in by_concept["shareholders_equity"]] == [1_000.0, 1_100.0, 1_200.0]
    assert [point["value"] for point in by_concept["revenue"]] == [REVENUE[fy] for fy in (2021, 2022, 2023)]


@pytest.mark.parametrize("synced", ["through_the_prior_report", "through_this_report"])
@pytest.mark.parametrize("issuer", [*sorted(LAGGING_FOCUS), "target"])
def test_an_annual_report_takes_the_years_companyfacts_already_names(db, monkeypatch, issuer, synced):
    """One filing cannot tell a January year named by its end, under a lagging focus, from Target's year
    named by its start; companyfacts' year chain can. Opened after a sync, the 10-K's years move onto
    that chain by one offset (Target's is zero), its newest year included, which companyfacts does not
    hold yet when it last synced before this report (the common order)."""
    report_fy = LAGGING_FOCUS.get(issuer, 2024)
    company = _company(db, issuer)
    reports = (report_fy - 1,) if synced == "through_the_prior_report" else (report_fy - 1, report_fy)
    facts_service._persist_companyfacts_payload(db, company, _companyfacts(issuer, reports))
    _open_annual_report(db, monkeypatch, issuer, report_fy)

    names = _issuer_years(issuer, CALENDARS[issuer])
    current = db.query(FinancialFact).filter_by(company_id=company.id, fiscal_period="FY", is_latest=True).all()
    assert {(row.concept, row.period_end): row.fiscal_year for row in current} == {
        (row.concept, row.period_end): names[row.period_end] for row in current
    }
    # Copilot's lookup by year, scoped to the viewed filing, finds the prior year's own value.
    fact = copilot_tools._run_get_financial_fact(
        db, company.id, ANNUAL_REPORTS[issuer][report_fy][0], {"concept": "net_income", "fiscal_year": report_fy - 1}, "USD",
    )
    assert (fact["period_end"], fact["value"]) == (CALENDARS[issuer][report_fy - 1][1], NET_INCOME[report_fy - 1])


# Companyfacts FY rows stored before the 10-K is opened: (concept, the issuer's year of the period, the
# stored label, provenance version or None). None of them yields one offset to trust.
UNTRUSTED = {
    # The first sync has not run: a lagging focus keeps the year before (the known limit).
    "no_sync_yet": ("crm", []),
    # A sync from before the fiscal-year-window writer (NULL provenance) named each year by the
    # calendar year of its end.
    "legacy_rows_only": ("target", [("revenue", 2023, 2024, None), ("revenue", 2022, 2023, None)]),
    # The writer names an opening balance older than its year windows by calendar year.
    "instants_only": ("target", [("total_assets", 2022, 2023, 1)]),
    # Trusted years that move the filing by different offsets name no one year chain.
    "disagreeing_offsets": ("crm", [("revenue", 2025, 2025, 1), ("revenue", 2024, 2023, 1)]),
}


@pytest.mark.parametrize("evidence", sorted(UNTRUSTED))
def test_without_one_trusted_offset_the_filing_keeps_its_own_labels(db, monkeypatch, evidence):
    issuer, rows = UNTRUSTED[evidence]
    report_fy = LAGGING_FOCUS.get(issuer, 2024)
    company = _company(db, issuer)
    for concept, fy, label, version in rows:
        start, end = CALENDARS[issuer][fy]
        db.add(FinancialFact(
            company_id=company.id, concept=concept, raw_tag="us-gaap:X", unit="USD", fiscal_period="FY",
            period_start=None if concept == "total_assets" else date.fromisoformat(start),
            period_end=date.fromisoformat(end), fiscal_year=label, form="10-K",
            value={"revenue": REVENUE, "total_assets": ASSETS}[concept][fy], accession="0000000009-24-000001",
            source="companyfacts", reconciled=True, is_latest=True,
            provenance=None if version is None else {"version": version, "method": "reported", "validation": "passed"},
        ))
    db.commit()
    filing = _open_annual_report(db, monkeypatch, issuer, report_fy)

    lag = 1 if issuer in LAGGING_FOCUS else 0  # Salesforce's own focus names its years one low.
    own = {end: fy - lag for end, fy in _issuer_years(issuer, CALENDARS[issuer]).items()}
    stored = db.query(FinancialFact).filter_by(filing_id=filing.id).all()
    assert stored and {(row.concept, row.period_end): row.fiscal_year for row in stored} == {
        (row.concept, row.period_end): own[row.period_end] for row in stored
    }


def test_a_quarterly_reports_labels_never_move(db, monkeypatch):
    """Only an annual report's years move. A 10-Q keeps the quarter labeller's labels, even for its
    year-end balance, whose period end companyfacts names by another year (this 10-Q's focus lags too)."""
    company = _company(db, "crm")
    facts_service._persist_companyfacts_payload(db, company, _companyfacts("crm", (2025, 2026)))
    accession = "0001108524-26-000100"
    url = build_sec_archive_url(company.cik, accession)
    filing = Filing(
        company_id=company.id, accession_number=accession, filing_type="10-Q", sec_url=url,
        document_url=f"{url}quarter.htm", filing_date=datetime(2026, 6, 1, tzinfo=timezone.utc),
        period_end_date=datetime(2026, 4, 30, tzinfo=timezone.utc),
    )
    db.add(filing)
    db.commit()

    def point(value, end, start=None):
        return {"is_dimensioned": False, "period_start": start, "period_end": None if start is None else end,
                "period_instant": end if start is None else None, "numeric_value": value, "decimals": -6,
                "currency": "USD"}

    frames = {
        "Revenues": pd.DataFrame([point(400.0, "2026-04-30", "2026-02-01"), point(350.0, "2025-04-30", "2025-02-01")]),
        "NetIncomeLoss": pd.DataFrame([point(40.0, "2026-04-30", "2026-02-01"), point(35.0, "2025-04-30", "2025-02-01")]),
        "Assets": pd.DataFrame([point(7_000.0, "2026-04-30"), point(ASSETS[2026], "2026-01-31")]),
    }
    xb = SimpleNamespace(facts=_Facts(frames), entity_info={"fiscal_year": "2026", "fiscal_period": "Q1"})
    sec_filing = SimpleNamespace(form="10-Q", period_of_report="2026-04-30", xbrl=lambda: xb)
    monkeypatch.setattr(xbrl_instance, "resolve_filing_by_accession",
                        lambda *args: (SimpleNamespace(sic=None), [sec_filing]))
    raw = xbrl_instance._extract_from_filing_instance_sync("0000000001", accession)
    facts_service.process_filing_facts(db, filing, standardized=extract_standardized_metrics(raw))

    stored = db.query(FinancialFact).filter_by(filing_id=filing.id).all()
    assert {(row.period_end.isoformat(), row.fiscal_year, row.fiscal_period) for row in stored} == {
        ("2026-04-30", 2026, "Q1"), ("2025-04-30", 2025, "Q1"), ("2026-01-31", 2025, "Q4"),
    }


def test_the_writers_company_lock_comes_before_the_evidence_read(db, monkeypatch):
    """A companyfacts sync that committed between the evidence read and the write would leave the filing
    its own lagging labels beside the sync's rows. On PostgreSQL the fact writers' company lock closes
    that window only when it is taken before the read. SQLite renders ``FOR UPDATE`` as nothing, so the
    order of the two calls is pinned here (``lessons/test-pin-a-row-lock-with-a-statement-spy.md``)."""
    company = _company(db, "crm")
    facts_service._persist_companyfacts_payload(db, company, _companyfacts("crm", (LAGGING_FOCUS["crm"] - 1,)))
    calls: list[str] = []
    real_lock, real_read = Query.with_for_update, fiscal_evidence.trusted_fiscal_years

    def lock(self, *args, **kwargs):
        calls.append(f"lock {self.column_descriptions[0]['entity'].__tablename__}")
        return real_lock(self, *args, **kwargs)

    def read(*args, **kwargs):
        calls.append("evidence read")
        return real_read(*args, **kwargs)

    monkeypatch.setattr(Query, "with_for_update", lock)
    monkeypatch.setattr(fiscal_evidence, "trusted_fiscal_years", read)
    _open_annual_report(db, monkeypatch, "crm", LAGGING_FOCUS["crm"])
    assert calls[:2] == ["lock companies", "evidence read"]


def test_a_late_year_chain_synced_first_gives_each_period_end_one_label(db, monkeypatch):
    """No annual report here was filed within 180 days of its year's end, so companyfacts names Target's
    chain from the late reports' own years. Synced first, those years are trusted evidence and the 10-K
    takes them: one label per period end, one period end per label, each the issuer's fiscal year."""
    company = _company(db, "target")
    payload = _companyfacts("target", (2023, 2024))
    for node in payload["facts"]["us-gaap"].values():
        for item in node["units"]["USD"]:
            item["filed"] = "2025-09-15"
    facts_service._persist_companyfacts_payload(db, company, payload)
    _open_annual_report(db, monkeypatch, "target", 2024)

    current = db.query(FinancialFact).filter_by(company_id=company.id, fiscal_period="FY", is_latest=True).all()
    labels = {(row.period_end, row.fiscal_year) for row in current}
    assert len(labels) == len({end for end, _year in labels}) == len({year for _end, year in labels}) == 4
    assert labels == set(_issuer_years("target").items())
