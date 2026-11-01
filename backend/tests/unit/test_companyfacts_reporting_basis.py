"""A filer whose latest annual report is IFRS reads as an IFRS filer (``facts/reporting_basis.py``).

F61, founder decision of 2026-11-01: a filer that moved from US GAAP to IFRS (Toyota from the year ended
2021-03-31, Itau after 2010) must not read its last US-GAAP year as its latest figures. Its companyfacts
sync stores nothing, as an IFRS-only filer's does, and retires the series earlier syncs stored from
current use. Multi-Period Analysis then reads no periods, the coverage route names it an IFRS filer,
and the peers endpoint serves no figure for it. A payload with no ifrs-full data never reaches the
count, so every domestic filer's sync is unchanged.
"""
import uuid
from datetime import date

import pytest

from app.services import facts_service as svc
from app.services.facts.reporting_basis import latest_annual_report, reports_under_ifrs

REV_TAG = "RevenueFromContractWithCustomerExcludingAssessedTax"


def _item(val, end, *, start=None, accn, form="20-F", filed, fy=None, fp="FY"):
    item = {"val": val, "end": end, "accn": accn, "fy": fy or int(end[:4]), "fp": fp, "form": form, "filed": filed}
    if start is not None:
        item["start"] = start
    return item


def _usgaap_years(unit="JPY"):
    """Three US-GAAP 20-Fs (FY2018-20, each with a comparative), revenue and net income: the pre-switch series."""
    revenue, income = [], []
    for year, accn, filed in ((2018, "U18", "2018-06-20"), (2019, "U19", "2019-06-20"), (2020, "U20", "2020-06-24")):
        for shown in (year - 1, year):
            span = {"start": f"{shown - 1}-04-01", "end": f"{shown}-03-31"}
            revenue.append(_item(1000.0 + shown, span["end"], start=span["start"], accn=accn, filed=filed, fy=year))
            income.append(_item(100.0 + shown, span["end"], start=span["start"], accn=accn, filed=filed, fy=year))
    return {REV_TAG: {"units": {unit: revenue}}, "NetIncomeLoss": {"units": {unit: income}}}


def _ifrs_years(accns=(("I21", "2021-06-24"), ("I26", "2026-06-10")), form="20-F", unit="JPY"):
    """IFRS 20-Fs after the switch: ifrs-full revenue and profit, each report presenting two years."""
    revenue, profit = [], []
    for accn, filed in accns:
        year = int(filed[:4])
        for shown in (year - 1, year):
            end = f"{shown}-03-31"
            revenue.append(_item(2000.0 + shown, end, start=f"{shown - 1}-04-01", accn=accn, filed=filed, form=form))
            profit.append(_item(200.0 + shown, end, start=f"{shown - 1}-04-01", accn=accn, filed=filed, form=form))
    return {"Revenue": {"units": {unit: revenue}}, "ProfitLoss": {"units": {unit: profit}}}


def _payload(usgaap=None, ifrs=None):
    facts = {}
    if usgaap is not None:
        facts["us-gaap"] = usgaap
    if ifrs is not None:
        facts["ifrs-full"] = ifrs
    return {"cik": 1094517, "entityName": "SWITCHER CO", "facts": facts}


class TestReportsUnderIfrs:
    def test_a_payload_without_ifrs_full_data_is_never_an_ifrs_filers(self):
        assert reports_under_ifrs(_payload(_usgaap_years())["facts"]) is False
        assert reports_under_ifrs({}) is False
        assert reports_under_ifrs(None) is False

    def test_ifrs_full_data_and_no_us_gaap_data_is_an_ifrs_filers(self):
        assert reports_under_ifrs(_payload(ifrs=_ifrs_years())["facts"]) is True
        assert reports_under_ifrs(_payload({}, _ifrs_years())["facts"]) is True
        assert reports_under_ifrs({"ifrs-full": {"Revenue": {"units": {"EUR": []}}}}) is True  # main's own case

    def test_a_filer_whose_latest_annual_report_is_ifrs_is_an_ifrs_filers(self):
        root = _payload(_usgaap_years(), _ifrs_years())["facts"]
        assert latest_annual_report(root) == ("2026-06-10", "I26")
        assert reports_under_ifrs(root) is True

    def test_a_filer_whose_latest_annual_report_is_us_gaap_is_not(self):
        # Reported under IFRS once (2015-16), US GAAP since: the latest report decides.
        root = _payload(_usgaap_years(), _ifrs_years((("I15", "2015-06-20"), ("I16", "2016-06-20"))))["facts"]
        assert latest_annual_report(root) == ("2020-06-24", "U20")
        assert reports_under_ifrs(root) is False

    def test_stray_us_gaap_items_in_an_ifrs_report_leave_it_an_ifrs_filers(self):
        # E and KOF: IFRS 20-Fs that tag three us-gaap facts.
        ifrs = _ifrs_years((("X26", "2026-04-01"),))
        stray = {"Revenues": {"units": {"EUR": [_item(5.0, "2025-12-31", start="2025-01-01", accn="X26",
                                                      filed="2026-04-01")]}}}
        assert reports_under_ifrs(_payload(stray, ifrs)["facts"]) is True

    def test_a_us_gaap_report_with_a_few_ifrs_items_is_not(self):
        usgaap = _usgaap_years()
        ifrs = {"Revenue": {"units": {"JPY": [_item(1.0, "2020-03-31", start="2019-04-01", accn="U20",
                                                    filed="2020-06-24")]}}}
        assert reports_under_ifrs(_payload(usgaap, ifrs)["facts"]) is False

    def test_a_report_tagging_as_many_items_under_each_stays_us_gaap(self):
        # A tie decides nothing, so the sync keeps reading the us-gaap series it can store.
        usgaap = {REV_TAG: {"units": {"JPY": [_item(1.0, "2020-03-31", start="2019-04-01", accn="U20",
                                                    filed="2020-06-24")]}}}
        ifrs = {"Revenue": {"units": {"JPY": [_item(1.0, "2020-03-31", start="2019-04-01", accn="U20",
                                                    filed="2020-06-24")]}}}
        assert reports_under_ifrs(_payload(usgaap, ifrs)["facts"]) is False

    def test_an_ifrs_amendment_after_a_us_gaap_report_decides_nothing(self):
        # A 20-F/A may tag only its cover or one note: the latest original report decides.
        amendment = _ifrs_years((("IA21", "2021-09-01"),), form="20-F/A")
        root = _payload(_usgaap_years(), amendment)["facts"]
        assert latest_annual_report(root) == ("2020-06-24", "U20")
        assert reports_under_ifrs(root) is False

    def test_a_same_day_tie_goes_to_the_higher_accession(self):
        usgaap = {REV_TAG: {"units": {"JPY": [_item(1.0, "2020-03-31", start="2019-04-01", accn="A1",
                                                    filed="2020-06-24")]}}}
        ifrs = {"Revenue": {"units": {"JPY": [_item(1.0, "2020-03-31", start="2019-04-01", accn="B2",
                                                    filed="2020-06-24")]}}}
        assert latest_annual_report(_payload(usgaap, ifrs)["facts"]) == ("2020-06-24", "B2")

    def test_malformed_parts_are_skipped(self):
        root = {
            "us-gaap": {
                "Bad": "x", "AlsoBad": {"units": "x"}, "Worse": {"units": {"JPY": ["x", None]}}, **_usgaap_years(),
            },
            "ifrs-full": {"Revenue": {"units": {"JPY": [{"form": "20-F", "filed": 2026, "accn": "N"}]}}},
        }
        assert reports_under_ifrs(root) is False


class TestNormalize:
    def test_an_ifrs_filers_payload_normalizes_to_nothing(self):
        facts, meta = svc.normalize_companyfacts(1, _payload(_usgaap_years(), _ifrs_years()))
        assert facts == []
        assert meta == {"unsupported_ifrs": True, "history": []}

    def test_a_us_gaap_filers_payload_normalizes_as_without_its_old_ifrs_items(self):
        old_ifrs = _ifrs_years((("I15", "2015-06-20"), ("I16", "2016-06-20")))
        with_ifrs, meta = svc.normalize_companyfacts(1, _payload(_usgaap_years(), old_ifrs))
        without, _ = svc.normalize_companyfacts(1, _payload(_usgaap_years()))
        assert meta["unsupported_ifrs"] is False
        assert with_ifrs and with_ifrs == without


@pytest.fixture(scope="module", autouse=True)
def _tables():
    from app.database import engine
    from app.models import Base

    Base.metadata.create_all(bind=engine)
    yield


def _new_company(db):
    from app.models import Company

    suffix = uuid.uuid4().hex[:8]
    company = Company(cik=suffix, ticker=("R" + suffix[:4]).upper(), name=f"Switcher {suffix}")
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


def _sync(db, company, payload):
    async def fetch(cik):
        return payload

    import asyncio

    return asyncio.run(svc.ingest_companyfacts(db, company, force=True, fetcher=fetch))


def _rows(db, company_id):
    from app.models import FinancialFact

    return db.query(FinancialFact).filter(FinancialFact.company_id == company_id).all()


@pytest.mark.requires_db
class TestTheSyncRetiresTheSeries:
    def _planted(self):
        """A company an earlier sync read before the switch, plus a filing's own row and a legacy row."""
        from app.database import SessionLocal
        from app.models import Filing, FinancialFact

        db = SessionLocal()
        company = _new_company(db)
        first = _sync(db, company, _payload(_usgaap_years()))
        assert first["unsupported_ifrs"] is False and first["inserted"] > 0
        filing = Filing(company_id=company.id, accession_number=f"I26-{company.id}", filing_type="20-F",
                        filing_date=date(2026, 6, 10), document_url="https://example.com/d",
                        sec_url="https://example.com/s")
        db.add(filing)
        db.flush()
        common = {"company_id": company.id, "period_start": date(2025, 4, 1), "period_end": date(2026, 3, 31),
                  "fiscal_year": 2026, "fiscal_period": "FY", "unit": "JPY", "form": "20-F", "is_latest": True,
                  "reconciled": True}
        db.add(FinancialFact(concept="revenue", value=4026.0, accession=f"I26-{company.id}", filing_id=filing.id,
                             source="edgar_xbrl", raw_tag="ifrs-full:Revenue", **common))
        # The filing's own calculation: a derived row with a filing owner, which no companyfacts sync stored.
        db.add(FinancialFact(concept="net_margin", value=10.6, accession=f"I26-{company.id}", filing_id=filing.id,
                             source="derived", raw_tag=None, **{**common, "unit": "pure"}))
        db.add(FinancialFact(concept="net_income", value=426.0, accession="LEGACY", filing_id=None,
                             source="frames", raw_tag="us-gaap:NetIncomeLoss", **common))
        db.commit()
        return db, company

    def test_an_ifrs_filers_sync_retires_its_companyfacts_series_and_keeps_every_row(self):
        db, company = self._planted()
        before = {row.id: (row.source, row.filing_id, row.is_latest) for row in _rows(db, company.id)}
        series = {rid for rid, (source, owner, current) in before.items()
                  if current and owner is None and source in ("companyfacts", "derived")}
        assert any(before[rid][0] == "derived" for rid in series)  # the margins the earlier sync computed

        result = _sync(db, company, _payload(_usgaap_years(), _ifrs_years()))
        assert result["unsupported_ifrs"] is True
        assert result["inserted"] == 0 and result["demoted"] == len(series)
        db.expire_all()
        after = {row.id: row.is_latest for row in _rows(db, company.id)}
        assert set(after) == set(before)  # nothing deleted, nothing inserted
        assert {rid for rid, current in after.items() if current} == {
            rid for rid, (_, _, current) in before.items() if current and rid not in series
        }  # the filing's own rows (reported and calculated) and the legacy row stay current; the series is retired
        assert company.facts_synced_at is not None
        db.close()

    def test_a_second_ifrs_sync_retires_nothing_more(self):
        db, company = self._planted()
        _sync(db, company, _payload(_usgaap_years(), _ifrs_years()))
        again = _sync(db, company, _payload(_usgaap_years(), _ifrs_years()))
        assert again["unsupported_ifrs"] is True and again["demoted"] == 0
        db.close()

    def test_a_us_gaap_filers_sync_with_old_ifrs_items_retires_nothing(self):
        db, company = self._planted()
        current = {row.id for row in _rows(db, company.id) if row.is_latest}
        result = _sync(db, company, _payload(_usgaap_years(), _ifrs_years((("I15", "2015-06-20"),))))
        assert result["unsupported_ifrs"] is False and result["demoted"] == 0
        db.expire_all()
        assert {row.id for row in _rows(db, company.id) if row.is_latest} == current
        db.close()

    def test_multi_period_analysis_and_the_peers_endpoint_then_read_no_companyfacts_figure(self):
        from app.services import peers_service, trend_analysis_service

        db, company = self._planted()
        assert trend_analysis_service.available_periods(db, company.id)["annual"]  # the old series, before
        _sync(db, company, _payload(_usgaap_years(), _ifrs_years()))
        db.expire_all()
        periods = trend_analysis_service.available_periods(db, company.id)
        assert {p["fiscal_year"] for p in periods["annual"]} <= {2026}  # only the filing's own year, if any
        subject = peers_service.get_peers(db, company.ticker, "revenue")["subject"]
        assert subject["fiscal_year"] in (None, 2026)  # never a US-GAAP year the sync stored
        db.close()


@pytest.mark.requires_db
def test_a_us_gaap_filer_that_later_reports_under_ifrs_keeps_its_ifrs_reports_own_figure():
    # test_companyfacts_ingest.py's ifrs-full-named 20-F before this rule: two US-GAAP 10-Ks in USD, then
    # an IFRS 20-F in EUR whose FY2023 revenue the per-filing writer stored. The sync used to store the
    # 10-Ks' USD years and demote the 20-F's EUR row, so FY2023 read as the last US-GAAP report's USD
    # figure. The filer reports under IFRS now: the sync stores nothing, and the 20-F's own row stays.
    from app.database import SessionLocal
    from app.models import Filing, FinancialFact

    db = SessionLocal()
    company = _new_company(db)
    tag = f"-{uuid.uuid4().hex[:8]}"
    payload = _payload({REV_TAG: {"units": {"USD": [
        _item(800.0, "2022-12-31", start="2022-01-01", accn=f"K22{tag}", form="10-K", filed="2023-02-15"),
        _item(1000.0, "2023-12-31", start="2023-01-01", accn=f"K23{tag}", form="10-K", filed="2024-02-15"),
    ]}}}, {"Revenue": {"units": {"EUR": [
        _item(900.0, end, start=start, accn=f"IFRS24{tag}", filed="2025-03-01")
        for start, end in (("2023-01-01", "2023-12-31"), ("2024-01-01", "2024-12-31"))]}}})
    filing = Filing(company_id=company.id, accession_number=f"IFRS24{tag}", filing_type="20-F",
                    filing_date=date(2025, 3, 1), document_url="https://example.com/d", sec_url="https://example.com/s")
    db.add(filing)
    db.flush()
    db.add(FinancialFact(company_id=company.id, filing_id=filing.id, concept="revenue", raw_tag="ifrs-full:Revenue",
                         unit="EUR", period_start=date(2023, 1, 1), period_end=date(2023, 12, 31), fiscal_year=2023,
                         fiscal_period="FY", value=900.0, form="20-F", accession=filing.accession_number,
                         source="edgar_xbrl", reconciled=True, is_latest=True))
    db.commit()

    result = _sync(db, company, payload)
    assert result["unsupported_ifrs"] is True and (result["inserted"], result["demoted"]) == (0, 0)
    db.expire_all()
    assert [(row.unit, row.accession.removesuffix(tag), row.is_latest) for row in _rows(db, company.id)] == [
        ("EUR", "IFRS24", True)]
    db.close()
