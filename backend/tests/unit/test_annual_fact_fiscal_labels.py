"""Annual per-filing facts carry the issuer's fiscal year, so both fact writers label a period alike.

The fact identity (concept, period_end, fiscal_period, unit, accession) leaves out the fiscal
year, so whichever writer stores an identity first keeps its label and the other is skipped. The
companyfacts writer names a year from SEC's original annual reports; the per-filing writer used to
name every 10-K point by the calendar year of its end. For an issuer whose fiscal year is named
for the year it starts in (a retailer's year ending around 1 February) or a 52-week year that ends
on 1 January, the two disagreed, and the label depended on which writer ran first. These tests
drive the production paths end to end: the instance extractor and the companyfacts fallback, the
standardized metrics, the per-filing writer, the companyfacts writer, the Multi-Period Analysis
dataset and coverage, and the filing page's annual chart.
"""
from datetime import date, datetime, timezone
from types import SimpleNamespace

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Company, Filing, FinancialFact
from app.services import facts_service
from app.services import trend_analysis_service as analysis
from app.services.edgar import fiscal_periods, xbrl_instance
from app.services.edgar.xbrl_companyfacts import parse_company_facts
from app.services.edgar.xbrl_standardized import extract_standardized_metrics
from app.utils.sec_urls import build_sec_archive_url

pytestmark = pytest.mark.unit

# (start, end) of fiscal years 2021-2024, keyed by the issuer's own fiscal-year name.
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
}
# Each 10-K: its accession and filing date (within SEC's timely-original window).
TEN_KS = {
    "target": {2023: ("0000027419-24-000010", "2024-03-13"), 2024: ("0000027419-25-000010", "2025-03-12")},
    "home_depot": {2023: ("0000354950-24-000016", "2024-03-13"), 2024: ("0000354950-25-000013", "2025-03-21")},
    "jnj": {2023: ("0000200406-24-000013", "2024-02-16"), 2024: ("0000200406-25-000038", "2025-02-13")},
    "apple": {2023: ("0000320193-23-000106", "2023-11-03"), 2024: ("0000320193-24-000123", "2024-11-01")},
}
REVENUE = {2021: 1_000.0, 2022: 1_100.0, 2023: 1_200.0, 2024: 1_300.0}
NET_INCOME = {2021: 100.0, 2022: 110.0, 2023: 120.0, 2024: 130.0}
ASSETS = {2021: 5_000.0, 2022: 5_200.0, 2023: 5_400.0, 2024: 5_600.0}


@pytest.fixture
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'labels.sqlite'}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _company(db, issuer: str) -> Company:
    company = Company(cik="0000000001", ticker=issuer.upper()[:5], name=issuer)
    db.add(company)
    db.flush()
    for report_fy, (accession, filed) in TEN_KS[issuer].items():
        url = build_sec_archive_url(company.cik, accession)
        db.add(Filing(
            company_id=company.id, accession_number=accession, filing_type="10-K",
            filing_date=datetime.fromisoformat(filed).replace(tzinfo=timezone.utc),
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


def _instance_xbrl(monkeypatch, issuer: str, report_fy: int) -> dict:
    """The real instance extractor over one 10-K's XBRL; DEI names the year as edgartools reads it."""
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
    xb = SimpleNamespace(facts=_Facts(frames), entity_info={"fiscal_year": str(report_fy), "fiscal_period": "FY"})
    sec_filing = SimpleNamespace(form="10-K", period_of_report=calendar[report_fy][1], xbrl=lambda: xb)
    monkeypatch.setattr(xbrl_instance, "resolve_filing_by_accession",
                        lambda *args: (SimpleNamespace(sic=None), [sec_filing]))
    return xbrl_instance._extract_from_filing_instance_sync("0000000001", TEN_KS[issuer][report_fy][0])


def _open_10k(db, monkeypatch, issuer: str, report_fy: int) -> Filing:
    """A reader opens the 10-K: the SSE enrichment path writes that filing's own facts."""
    raw = _instance_xbrl(monkeypatch, issuer, report_fy)
    filing = db.query(Filing).filter_by(accession_number=TEN_KS[issuer][report_fy][0]).one()
    facts_service.process_filing_facts(db, filing, standardized=extract_standardized_metrics(raw))
    return filing


def _companyfacts(issuer: str, reports: tuple[int, ...]) -> dict:
    """SEC companyfacts: every item carries the fy/fp of the 10-K that reported it."""
    calendar = CALENDARS[issuer]
    items: dict[str, list] = {"Revenues": [], "NetIncomeLoss": [], "Assets": []}
    for report_fy in reports:
        accession, filed = TEN_KS[issuer][report_fy]
        source = {"fy": report_fy, "fp": "FY", "form": "10-K", "accn": accession, "filed": filed}
        for fy in (report_fy - 2, report_fy - 1, report_fy):
            start, end = calendar[fy]
            items["Revenues"].append({**source, "start": start, "end": end, "val": REVENUE[fy]})
            items["NetIncomeLoss"].append({**source, "start": start, "end": end, "val": NET_INCOME[fy]})
        for fy in (report_fy - 1, report_fy):
            items["Assets"].append({**source, "end": calendar[fy][1], "val": ASSETS[fy]})
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


@pytest.mark.parametrize("order", ORDERS)
@pytest.mark.parametrize("issuer", sorted(CALENDARS))
def test_both_fact_writers_name_the_issuers_fiscal_year_in_either_order(db, monkeypatch, issuer, order):
    company = _company(db, issuer)
    if order == "filing_then_companyfacts":
        _open_10k(db, monkeypatch, issuer, 2024)
        facts_service._persist_companyfacts_payload(db, company, _companyfacts(issuer, (2023, 2024)))
    elif order == "companyfacts_then_filing":
        facts_service._persist_companyfacts_payload(db, company, _companyfacts(issuer, (2023, 2024)))
        _open_10k(db, monkeypatch, issuer, 2024)
    else:  # Synced before the newest 10-K existed; a reader opens it; the next sync runs.
        facts_service._persist_companyfacts_payload(db, company, _companyfacts(issuer, (2023,)))
        _open_10k(db, monkeypatch, issuer, 2024)
        facts_service._persist_companyfacts_payload(db, company, _companyfacts(issuer, (2023, 2024)))

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


@pytest.mark.parametrize("issuer,expected", [
    ("jnj", [2022, 2023, 2024]),
    ("target", [2022, 2023, 2024]),
    ("apple", [2022, 2023, 2024]),
])
def test_filing_chart_names_each_annual_bar_once_by_its_fiscal_year(db, monkeypatch, issuer, expected):
    _company(db, issuer)
    filing = _open_10k(db, monkeypatch, issuer, 2024)

    chart = facts_service.get_filing_fundamentals(db, filing.id)

    revenue = next(concept for concept in chart["concepts"] if concept["concept"] == "revenue")
    assert [point["period_end"] for point in revenue["points"]] == [
        CALENDARS[issuer][fy][1] for fy in (2022, 2023, 2024)
    ]
    assert [point["fiscal_year"] for point in revenue["points"]] == expected


def test_companyfacts_fallback_names_the_target_accessions_fiscal_years():
    accession = TEN_KS["target"][2024][0]
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


def test_a_calendar_aligned_issuers_extracted_points_keep_their_exact_shape(monkeypatch):
    """Apple's fiscal year is the calendar year of its end, so neither extractor adds a key.

    The persisted snapshot is what Copilot shows the model; it stays byte-identical for every
    issuer whose calendar year of the end already names the fiscal year.
    """
    instance = _instance_xbrl(monkeypatch, "apple", 2024)
    fallback = parse_company_facts(_companyfacts("apple", (2023, 2024)), TEN_KS["apple"][2024][0])

    for raw in (instance, fallback):
        points = [point for key in ("revenue", "net_income", "total_assets") for point in raw[key]]
        assert points and not any({"fiscal_year", "fiscal_period"} & point.keys() for point in points)


@pytest.mark.parametrize("end,report_end,focus,expected", [
    ("2025-02-01", "2025-02-01", "2024", {"fiscal_year": 2024, "fiscal_period": "FY"}),
    ("2023-01-28", "2025-02-01", 2024, {"fiscal_year": 2022, "fiscal_period": "FY"}),
    ("2023-01-01", "2024-12-29", 2024, {"fiscal_year": 2022, "fiscal_period": "FY"}),
    # The calendar year of the end already names it: the normalizer's default stands.
    ("2024-12-29", "2024-12-29", 2024, {}),
    ("2023-09-30", "2024-09-28", 2024, {}),
    # Not a whole number of years from the anchor (a transition period), or after it.
    ("2024-08-03", "2025-02-01", 2024, {}),
    ("2026-01-31", "2025-02-01", 2024, {}),
    # A focus year that is neither the anchor's end year nor the one before is not trusted.
    ("2025-02-01", "2025-02-01", 2022, {}),
    ("2025-02-01", "2025-02-01", None, {}),
    ("2025-02-01", "2025-02-01", True, {}),
    ("2025-02-01", None, 2024, {}),
])
def test_annual_label_counts_whole_fiscal_years_back_from_the_filing_focus(end, report_end, focus, expected):
    assert fiscal_periods.annual_fiscal_label(end, report_end, focus) == expected


def test_dataset_refuses_a_fiscal_label_two_current_rows_give_to_different_periods(db):
    """Stored before this fix: two current rows both claim FY2023 revenue for different years.

    Neither row proves which period FY2023 means, and a growth figure built on a guess would
    span two years, so the column is withheld for that concept rather than won by query order.
    """
    company = _company(db, "jnj")
    rows = [
        ("revenue", "2022-01-02", 2022, 93.8), ("revenue", "2023-01-01", 2023, 94.9),
        ("revenue", "2023-12-31", 2023, 85.2),
        ("net_income", "2022-01-02", 2022, 20.9), ("net_income", "2023-12-31", 2023, 35.2),
    ]
    for concept, end, fiscal_year, value in rows:
        db.add(FinancialFact(
            company_id=company.id, concept=concept, unit="USD", period_end=date.fromisoformat(end),
            fiscal_year=fiscal_year, fiscal_period="FY", value=value, form="10-K",
            accession=TEN_KS["jnj"][2023][0], source="edgar_xbrl", reconciled=True, is_latest=True,
        ))
    db.commit()

    dataset = analysis.build_dataset(db, company, "annual", "FY2022", "FY2023")

    by_concept = {series["concept"]: series["points"] for series in dataset["series"]}
    assert [point["value"] for point in by_concept["revenue"]] == [93.8, None]
    assert [point["value"] for point in by_concept["net_income"]] == [20.9, 35.2]
