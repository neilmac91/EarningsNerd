"""Companyfacts ingest keeps each fiscal year's own-report value beside its winner (MPA WP5b).

The winner is the latest-filed item of the first tag with data. When a later annual report gives a
year another value, the year's own report's value is kept as a history row: never current, never an
operand of the sync's derivations (``app/services/facts/own_reports.py``). How one filing's chart reads
it is pinned in ``test_filing_fundamentals_by_accession.py``. REGN is the worked case: its
FY2018 10-K reports revenue of 6,710.8M, and the FY2020 10-K's comparative, under the same tag,
5,145.6M (docs/mpa-improvements/coherence.md, section 1.6).
"""
import uuid
from datetime import date, datetime, timezone

import pytest

from app.services import facts_service as svc

REV_TAG = "RevenueFromContractWithCustomerExcludingAssessedTax"
# Each 10-K by the fiscal year it reports as its own: accession and filing date (REGN's).
_K = {2017: ("0000872589-18-000005", "2018-02-08"), 2018: ("0001532176-19-000009", "2019-02-07"),
      2019: ("0001532176-20-000008", "2020-02-07"), 2020: ("0001804220-21-000008", "2021-02-08"),
      2021: ("0001804220-22-000007", "2022-02-07")}
K17, K18, K19, K20, K21 = (_K[year][0] for year in sorted(_K))
# Revenue as each 10-K reports it, its own year and the two before. The FY2020 10-K gives FY2018 and
# FY2019 a narrower figure under the same tag; the FY2021 10-K repeats FY2019's.
_REVENUE = {
    2017: {2015: 4_103.7e6, 2016: 4_860.4e6, 2017: 5_872.2e6},
    2018: {2016: 4_860.4e6, 2017: 5_872.2e6, 2018: 6_710.8e6},
    2019: {2017: 5_872.2e6, 2018: 6_710.8e6, 2019: 7_863.4e6},
    2020: {2018: 5_145.6e6, 2019: 6_557.6e6, 2020: 8_497.1e6},
    2021: {2019: 6_557.6e6, 2020: 8_497.1e6, 2021: 16_071.7e6},
}
_NET_INCOME = {2015: 636.1e6, 2016: 895.5e6, 2017: 1_198.5e6, 2018: 2_444.4e6, 2019: 2_115.8e6,
               2020: 3_513.2e6, 2021: 8_075.3e6}
# Total assets at each year end, as that year's 10-K and the next report it; the FY2019 10-K gives
# the 2018 balance another value.
_ASSETS = {2017: {2016: 9_520.2e6, 2017: 11_734.5e6}, 2018: {2017: 11_734.5e6, 2018: 15_163.8e6},
           2019: {2018: 15_200.1e6, 2019: 17_163.4e6}, 2020: {2019: 17_163.4e6, 2020: 19_994.1e6},
           2021: {2020: 19_994.1e6, 2021: 25_434.7e6}}


def _item(value, year, report, *, instant=False, accn=None, form="10-K", filed=None):
    item = {"val": value, "end": f"{year}-12-31", "accn": accn or _K[report][0], "fy": report, "fp": "FY",
            "form": form, "filed": filed or _K[report][1]}
    if not instant:
        item["start"] = f"{year}-01-01"
    return item


def _items(by_report, *, instant=False):
    return [_item(value, year, report, instant=instant)
            for report, values in by_report.items() for year, value in values.items()]


def _payload(revenue=None, *, assets=None, tags=None):
    """REGN's shape: revenue, net income (which no later report changed) and total assets."""
    net_income = {report: {year: _NET_INCOME[year] for year in range(report - 2, report + 1)} for report in _K}
    usgaap = {
        REV_TAG: {"units": {"USD": revenue if revenue is not None else _items(_REVENUE)}},
        "NetIncomeLoss": {"units": {"USD": _items(net_income)}},
        "Assets": {"units": {"USD": assets if assets is not None else _items(_ASSETS, instant=True)}},
        **(tags or {}),
    }
    return {"cik": 872589, "entityName": "REGENERON SHAPE", "facts": {"us-gaap": usgaap}}


def _winners(facts, concept):
    return {f["fiscal_year"]: (f["value"], f["accession"]) for f in facts
            if (f["concept"], f["fiscal_period"]) == (concept, "FY")}


def _history(meta, concept=None):
    return {(h["concept"], h["fiscal_year"]): (h["value"], h["accession"]) for h in meta["history"]
            if concept in (None, h["concept"])}


class TestOwnReportHistory:
    def test_a_later_comparative_keeps_the_years_own_report_as_a_history_fact(self):
        facts, meta = svc.normalize_companyfacts(1, _payload())
        assert _winners(facts, "revenue") == {
            2015: (4_103.7e6, K17), 2016: (4_860.4e6, K18), 2017: (5_872.2e6, K19),
            2018: (5_145.6e6, K20), 2019: (6_557.6e6, K21), 2020: (8_497.1e6, K21), 2021: (16_071.7e6, K21)}
        assert _history(meta) == {("revenue", 2018): (6_710.8e6, K18), ("revenue", 2019): (7_863.4e6, K19),
                                  ("total_assets", 2018): (15_163.8e6, K18)}
        fy2018 = next(h for h in meta["history"] if (h["concept"], h["fiscal_year"]) == ("revenue", 2018))
        assert {key: fy2018[key] for key in ("company_id", "filing_id", "raw_tag", "unit", "period_start",
                                             "period_end", "fiscal_period", "form", "source", "reconciled")} == {
            "company_id": 1, "filing_id": None, "raw_tag": f"us-gaap:{REV_TAG}", "unit": "USD",
            "period_start": date(2018, 1, 1), "period_end": date(2018, 12, 31), "fiscal_period": "FY",
            "form": "10-K", "source": "companyfacts", "reconciled": True}
        assert fy2018["provenance"]["filed_at"] == "2019-02-07"
        # Kept apart from the facts the derivations read: every row, and every margin's operand, is the
        # winner's, so the FY2018 margin divides by 5,145.6M.
        assert not [f for f in facts if (f["accession"], f["period_end"]) in {(K18, date(2018, 12, 31)),
                                                                                (K19, date(2019, 12, 31))}]
        margin = next(f for f in facts if (f["concept"], f["fiscal_year"]) == ("net_margin", 2018))
        assert margin["value"] == pytest.approx(_NET_INCOME[2018] / 5_145.6e6 * 100)

    def test_no_history_where_a_later_report_repeats_the_own_value(self):
        # FY2017's winner is the FY2019 10-K's comparative, another filing than its own 10-K, and
        # every net income: each repeats what the year's own report said.
        facts, meta = svc.normalize_companyfacts(1, _payload())
        assert _winners(facts, "revenue")[2017] == (5_872.2e6, K19)
        assert _winners(facts, "net_income")[2018] == (_NET_INCOME[2018], K20)
        assert ("revenue", 2017) not in _history(meta)
        assert _history(meta, "net_income") == {}

    def test_the_winners_own_filing_is_never_its_history(self):
        # The FY2021 10-K tags its own year twice; the later-listed item wins, and the other is the
        # same filing's, so it is no other report's value.
        revenue = _items(_REVENUE) + [_item(16_000.0e6, 2021, 2021)]
        facts, meta = svc.normalize_companyfacts(1, _payload(revenue))
        assert _winners(facts, "revenue")[2021] == (16_000.0e6, K21)
        assert ("revenue", 2021) not in _history(meta)

    @pytest.mark.parametrize("original", [True, False], ids=["original-and-amendment", "amendment-alone"])
    def test_an_amendment_loses_to_the_original(self, original):
        # A 10-K/A for FY2018 filed the day of the original and listed first: the original's value is
        # the year's own report; with no original item, the amendment's is.
        k18a = "0001532176-19-000010"
        amended = [_item(value, year, 2018, accn=k18a, form="10-K/A")
                   for year, value in {2016: 4_860.4e6, 2017: 5_872.2e6, 2018: 6_702.5e6}.items()]
        reports = _REVENUE if original else {**_REVENUE, 2018: {}}
        _facts, meta = svc.normalize_companyfacts(1, _payload(amended + _items(reports)))
        assert _history(meta, "revenue")[("revenue", 2018)] == ((6_710.8e6, K18) if original else (6_702.5e6, k18a))

    def test_of_two_amendments_the_earlier_filed_is_the_own_report(self):
        # The FY2018 10-K tagged its revenue under "Revenues" alone; two 10-K/As then gave it under the
        # winning tag, No. 2 listed first. Both are the year's own report, amended: No. 1, filed first.
        k18a1, k18a2 = "0001532176-19-000020", "0001532176-19-000030"
        amendments = [_item(value, year, 2018, accn=accn, form="10-K/A", filed=filed)
                      for accn, filed, own in ((k18a2, "2019-06-03", 6_702.5e6), (k18a1, "2019-04-01", 6_705.0e6))
                      for year, value in {2016: 4_860.4e6, 2017: 5_872.2e6, 2018: own}.items()]
        revenue = amendments + _items({**_REVENUE, 2018: {}})
        _facts, meta = svc.normalize_companyfacts(1, _payload(revenue, tags={"Revenues": {"units": {"USD": _items(
            {2018: _REVENUE[2018]})}}}))
        assert _history(meta, "revenue")[("revenue", 2018)] == (6_705.0e6, k18a1)

    def test_of_two_originals_the_earlier_filed_is_the_own_report(self):
        # The FY2018 10-K filed again under a new accession five weeks later (a re-filing, form 10-K),
        # listed first and with another FY2018 figure: the first filed stays the year's own report.
        k18b = "0001532176-19-000040"
        refiled = [_item(value, year, 2018, accn=k18b, filed="2019-03-15")
                   for year, value in {2016: 4_860.4e6, 2017: 5_872.2e6, 2018: 6_700.0e6}.items()]
        _facts, meta = svc.normalize_companyfacts(1, _payload(refiled + _items(_REVENUE)))
        assert _history(meta, "revenue")[("revenue", 2018)] == (6_710.8e6, K18)

    def test_of_two_own_items_filed_the_same_day_the_first_listed_is_the_own_report(self):
        # The FY2018 10-K tags its own year twice, the later-listed item with another figure: both are the
        # year's own report, originals filed the same day, and companyfacts' filing order breaks the tie.
        revenue = _items(_REVENUE) + [_item(6_700.0e6, 2018, 2018)]
        _facts, meta = svc.normalize_companyfacts(1, _payload(revenue))
        assert _history(meta, "revenue")[("revenue", 2018)] == (6_710.8e6, K18)

    def test_an_item_with_no_form_at_an_annual_reports_accession_is_read_as_its_original(self):
        # One FY2018 10-K item carries no form; the report's other items name it, so its accession is an
        # annual report's own. The item is that report's, read as an original, and the sync goes on.
        revenue = [{key: value for key, value in item.items() if key != "form"}
                   if (item["accn"], item["end"]) == (K18, "2018-12-31") else item for item in _items(_REVENUE)]
        _facts, meta = svc.normalize_companyfacts(1, _payload(revenue))
        [fy2018] = [h for h in meta["history"] if (h["concept"], h["fiscal_year"]) == ("revenue", 2018)]
        assert (fy2018["value"], fy2018["accession"], fy2018["form"]) == (6_710.8e6, K18, None)

    def test_a_proxy_is_never_the_own_report_nor_the_winner(self):
        # A proxy filed after the FY2020 10-K tags FY2018 and FY2019 revenue: it is never a candidate,
        # so it neither wins those years nor stands for their own report.
        proxy = [_item(value, year, 2020, accn="0001193125-21-112233", form="DEF 14A", filed="2021-04-26")
                 for year, value in {2018: 6_700.0e6, 2019: 7_850.0e6}.items()]
        facts, meta = svc.normalize_companyfacts(1, _payload(_items(_REVENUE) + proxy))
        assert {year: _winners(facts, "revenue")[year] for year in (2018, 2019)} == {
            2018: (5_145.6e6, K20), 2019: (6_557.6e6, K21)}
        assert _history(meta, "revenue") == {("revenue", 2018): (6_710.8e6, K18),
                                             ("revenue", 2019): (7_863.4e6, K19)}
        assert not [f for f in facts + meta["history"] if f["form"] == "DEF 14A"]

    def test_a_fiscal_year_end_balance_keeps_its_own_report(self):
        facts, meta = svc.normalize_companyfacts(1, _payload())
        assets = {f["fiscal_year"]: (f["value"], f["accession"], f["period_start"]) for f in facts
                  if (f["concept"], f["fiscal_period"]) == ("total_assets", "FY")}
        assert assets[2018] == (15_200.1e6, K19, None)
        [history] = [h for h in meta["history"] if h["concept"] == "total_assets"]
        assert (history["fiscal_year"], history["fiscal_period"], history["period_start"], history["period_end"],
                history["value"], history["accession"]) == (2018, "FY", None, date(2018, 12, 31), 15_163.8e6, K18)

    def test_the_own_report_under_another_tag_is_not_taken(self):
        # The FY2018 10-K tagged its revenue "Revenues" only; the winning tag's FY2018 items are the
        # later reports', so the lookup, within the winning tag, finds no own report for FY2018.
        revenue = _items({**_REVENUE, 2018: {}})
        facts, meta = svc.normalize_companyfacts(1, _payload(revenue, tags={"Revenues": {"units": {"USD": _items(
            {2018: _REVENUE[2018]})}}}))
        assert _winners(facts, "revenue")[2018] == (5_145.6e6, K20)
        assert ("revenue", 2018) not in _history(meta)

    def test_a_comparative_is_never_the_years_own_report_even_the_first_filed(self):
        # No FY2018 10-K tagged its revenue (a late or missing report): the first filing to report
        # FY2018 revenue is the FY2019 10-K's comparative, which is no report of FY2018 as its own year.
        facts, meta = svc.normalize_companyfacts(1, _payload(_items({**_REVENUE, 2018: {}})))
        assert _winners(facts, "revenue")[2018] == (5_145.6e6, K20)
        assert ("revenue", 2018) not in _history(meta)
        assert _history(meta, "revenue") == {("revenue", 2019): (7_863.4e6, K19)}

    def test_an_own_item_for_another_span_is_not_the_years_own_value(self):
        # The FY2018 10-K's item for its own year starts a day later than the winner's period: another
        # span, so no own value for the winner's period.
        revenue = [{**item, "start": "2018-01-02"} if (item["accn"], item["end"]) == (K18, "2018-12-31") else item
                   for item in _items(_REVENUE)]
        facts, meta = svc.normalize_companyfacts(1, _payload(revenue))
        assert _winners(facts, "revenue")[2018] == (5_145.6e6, K20)
        assert ("revenue", 2018) not in _history(meta)

    def test_a_quarter_ending_on_the_year_end_adds_no_history(self):
        # A discrete fourth quarter shares the year's end; only the FY winner gets the year's own value.
        q4 = {**_item(1_301.0e6, 2018, 2020), "start": "2018-10-01", "fp": "Q4"}
        facts, meta = svc.normalize_companyfacts(1, _payload(_items(_REVENUE) + [q4]))
        assert ("revenue", date(2018, 12, 31), "Q4") in {(f["concept"], f["period_end"], f["fiscal_period"])
                                                          for f in facts}
        assert sorted((h["concept"], h["fiscal_year"], h["fiscal_period"]) for h in meta["history"]) == [
            ("revenue", 2018, "FY"), ("revenue", 2019, "FY"), ("total_assets", 2018, "FY")]

    def test_a_negative_own_value_of_a_non_negative_concept_is_dropped(self):
        revenue = _items({**_REVENUE, 2018: {**_REVENUE[2018], 2018: -6_710.8e6}})
        _facts, meta = svc.normalize_companyfacts(1, _payload(revenue))
        assert ("revenue", 2018) not in _history(meta)
        assert ("revenue", 2019) in _history(meta)

    @pytest.mark.parametrize("payload", [{}, {"facts": {"ifrs-full": {"Revenue": {}}}}], ids=["empty", "ifrs"])
    def test_a_payload_with_no_us_gaap_facts_has_no_history(self, payload):
        assert svc.normalize_companyfacts(1, payload)[1]["history"] == []


def _shapes():
    """Payloads whose own-report selection turns on each of its rules: REGN as filed; an own item of
    another span; two amendments under the winning tag; an original filed again; an item with no form;
    a proxy's items."""
    k18a1, k18a2, k18b = "0001532176-19-000020", "0001532176-19-000030", "0001532176-19-000040"
    regn = _items(_REVENUE)
    return {
        "regn": _payload(),
        "another-span": _payload([{**item, "start": "2018-01-02"} if (item["accn"], item["end"]) == (K18, "2018-12-31")
                                  else item for item in regn]),
        "two-amendments": _payload([_item(value, year, 2018, accn=accn, form="10-K/A", filed=filed)
                                    for accn, filed, own in ((k18a2, "2019-06-03", 6_702.5e6), (k18a1, "2019-04-01", 6_705.0e6))
                                    for year, value in {2016: 4_860.4e6, 2017: 5_872.2e6, 2018: own}.items()]
                                   + _items({**_REVENUE, 2018: {}}),
                                   tags={"Revenues": {"units": {"USD": _items({2018: _REVENUE[2018]})}}}),
        "an-original-filed-again": _payload([_item(value, year, 2018, accn=k18b, filed="2019-03-15")
                                             for year, value in {2016: 4_860.4e6, 2017: 5_872.2e6, 2018: 6_700.0e6}.items()]
                                            + regn),
        "no-form": _payload([{key: value for key, value in item.items() if key != "form"}
                             if (item["accn"], item["end"]) == (K18, "2018-12-31") else item for item in regn]),
        "proxy": _payload(regn + [_item(value, year, 2020, accn="0001193125-21-112233", form="DEF 14A", filed="2021-04-26")
                                  for year, value in {2018: 6_700.0e6, 2019: 7_850.0e6}.items()]),
    }


class TestTheCensusTakesIngestsOwnReport:
    @pytest.mark.parametrize("shape", list(_shapes()))
    def test_the_census_within_the_winning_tag_finds_the_history_rows_ingest_keeps(self, shape):
        # backend/scripts/restatement_census.py reads the own report through own_reports' selection, so
        # its within-tag cells that differ under another accession are the rows a sync stores.
        from scripts import restatement_census

        payload = _shapes()[shape]
        _facts, meta = svc.normalize_companyfacts(1, payload)
        cells, _info = restatement_census.measure_company("REGN", payload, False, 10)
        census = {(cell["concept"], cell["fy"]): (cell["within"]["value"], cell["within"]["accession"])
                  for cell in cells if cell["within_later"] and cell["within"]["value"] != cell["winner"]["value"]}
        assert census == _history(meta)
        assert ("revenue", 2018) in census or shape == "another-span"

    @pytest.mark.parametrize("shape", ["filed-first-under-a-lower-tag", "another-span-wins-the-tag"])
    def test_the_census_across_the_tags_takes_the_winners_span_then_the_earliest_filed_then_the_tags_priority(
            self, shape):
        # The FY2018 10-K gave its revenue under "Revenues" alone. Either the same 10-K, filed again five
        # weeks later, gave it under the winning tag, whose priority is higher: the original, filed first,
        # is the own report across the tags. Or the FY2019 10-K gave FY2018 under "Revenues" for another
        # span, so that tag's latest item starts on another day than the winner: the original is still the
        # own report, for the winner's span.
        from scripts import restatement_census

        k18b = "0001532176-19-000040"
        revenues = _items({2018: _REVENUE[2018]})
        refiled = [_item(value, year, 2018, accn=k18b, filed="2019-03-15")
                   for year, value in {2016: 4_860.4e6, 2017: 5_872.2e6, 2018: 6_700.0e6}.items()]
        if shape == "another-span-wins-the-tag":
            refiled, revenues = [], revenues + [{**_item(6_705.0e6, 2018, 2019), "start": "2018-01-02"}]
        payload = _payload(refiled + _items({**_REVENUE, 2018: {}}), tags={"Revenues": {"units": {"USD": revenues}}})
        cells, _info = restatement_census.measure_company("REGN", payload, False, 10)
        [cell] = [cell for cell in cells if (cell["concept"], cell["fy"]) == ("revenue", 2018)]
        assert (cell["winner"]["value"], cell["winner"]["accession"]) == (5_145.6e6, K20)
        assert (cell["within"] or {}).get("accession") == (k18b if refiled else None)
        assert (cell["across"]["value"], cell["across"]["accession"], cell["across"]["tag"]) == (
            6_710.8e6, K18, "us-gaap:Revenues")


@pytest.fixture(scope="module", autouse=True)
def _tables():
    from app.database import engine
    from app.models import Base

    Base.metadata.create_all(bind=engine)
    yield


def _new_company(db):
    from app.models import Company

    suffix = uuid.uuid4().hex[:8]
    company = Company(cik=str(uuid.uuid4().int % 10**9), ticker=("T" + suffix[:5]).upper(), name=f"Co {suffix}")
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


def _fact(company_id, accession, value, *, year=2018, filed="2021-02-08"):
    from app.services.facts.quarterly import reported_fact

    record = {"raw_tag": f"us-gaap:{REV_TAG}", "period_start": date(year, 1, 1), "period_end": date(year, 12, 31),
              "value": value, "form": "10-K", "accession": accession, "filed": filed}
    return {**reported_fact(company_id, "revenue", "USD", record), "fiscal_year": year, "fiscal_period": "FY"}


def _rows(db, company_id):
    from app.models import FinancialFact

    return {(r.accession, float(r.value), r.is_latest) for r in db.query(FinancialFact).filter_by(
        company_id=company_id, concept="revenue", fiscal_period="FY")}


def _filing(db, company_id, accession, filed):
    from app.models import Filing

    db.add(Filing(company_id=company_id, accession_number=accession, filing_type="10-K",
                  filing_date=datetime.fromisoformat(filed).replace(tzinfo=timezone.utc),
                  document_url="https://example.com/d", sec_url="https://example.com/s"))
    db.commit()


@pytest.mark.requires_db
class TestHistoryRowsInTheBulkWriter:
    def test_a_history_row_is_stored_non_current_beside_the_winner(self):
        from app.database import SessionLocal

        db = SessionLocal()
        cid = _new_company(db).id
        winner, own = _fact(cid, "W20", 5_145.6e6), _fact(cid, "O18", 6_710.8e6, filed="2019-02-07")
        result = svc.upsert_facts_bulk(db, [winner], history=[own])
        assert result == {"inserted": 1, "skipped": 0, "demoted": 0, "history": 1}
        assert _rows(db, cid) == {("W20", 5_145.6e6, True), ("O18", 6_710.8e6, False)}
        db.close()

    @pytest.mark.parametrize("own_filed", [None, "2022-03-01", "2019-02-07"],
                             ids=["no-local-filings", "own-filed-after-the-winner", "own-filed-before-it"])
    def test_a_history_row_never_demotes_the_current_row_whatever_its_filing_date(self, own_filed):
        # With no local filing dates the writer orders a batch's rows as the normalizer listed them, so a
        # history row taken through that ordering would demote the winner; one whose local filing date
        # is later than the winner's would too. The last case is one that ordering also gets right.
        from app.database import SessionLocal

        db = SessionLocal()
        cid = _new_company(db).id
        tag = uuid.uuid4().hex[:8]
        winner, own = _fact(cid, f"W20-{tag}", 5_145.6e6), _fact(cid, f"O18-{tag}", 6_710.8e6)
        if own_filed:
            _filing(db, cid, f"W20-{tag}", "2021-02-08")
            _filing(db, cid, f"O18-{tag}", own_filed)
        svc.upsert_facts_bulk(db, [winner])
        result = svc.upsert_facts_bulk(db, [winner], history=[own])
        assert (result["skipped"], result["demoted"], result["history"]) == (1, 0, 1)
        assert _rows(db, cid) == {(f"W20-{tag}", 5_145.6e6, True), (f"O18-{tag}", 6_710.8e6, False)}
        db.close()

    def test_a_resync_skips_a_stored_history_row(self):
        from app.database import SessionLocal

        db = SessionLocal()
        cid = _new_company(db).id
        batch = ([_fact(cid, "W20", 5_145.6e6)], [_fact(cid, "O18", 6_710.8e6)])
        svc.upsert_facts_bulk(db, batch[0], history=batch[1])
        stored = _rows(db, cid)
        assert svc.upsert_facts_bulk(db, batch[0], history=batch[1]) == {
            "inserted": 0, "skipped": 1, "demoted": 0, "history": 0}
        assert _rows(db, cid) == stored
        db.close()

    def test_no_winner_arriving_later_promotes_a_history_row(self):
        # A later filing's winner demotes the current row and leaves the history row as it is; a winner
        # at the history row's own identity (the later filing gone from companyfacts) is skipped, as the
        # writer skips every stored identity, so nothing makes the history row current.
        from app.database import SessionLocal

        db = SessionLocal()
        cid = _new_company(db).id
        svc.upsert_facts_bulk(db, [_fact(cid, "W20", 5_145.6e6)], history=[_fact(cid, "O18", 6_710.8e6)])
        later = svc.upsert_facts_bulk(db, [_fact(cid, "W23", 5_100.0e6, filed="2024-02-08")])
        assert (later["inserted"], later["demoted"]) == (1, 1)
        assert _rows(db, cid) == {("W20", 5_145.6e6, False), ("O18", 6_710.8e6, False), ("W23", 5_100.0e6, True)}
        own_again = svc.upsert_facts_bulk(db, [_fact(cid, "O18", 6_710.8e6, filed="2019-02-07")])
        assert (own_again["inserted"], own_again["skipped"], own_again["demoted"]) == (0, 1, 0)
        assert ("O18", 6_710.8e6, False) in _rows(db, cid) and ("W23", 5_100.0e6, True) in _rows(db, cid)
        db.close()


@pytest.mark.requires_db
class TestHistoryRowsThroughTheSync:
    def test_a_sync_stores_the_own_values_and_the_analysis_dataset_reads_none_of_them(self, monkeypatch):
        # Before this change a sync stored winners only. The next sync stores each own report's value
        # beside its winner and inserts nothing else; the analysis dataset, its fingerprint and the
        # fiscal years companyfacts names for the per-filing writer are what they were.
        from app.database import SessionLocal
        from app.models import FinancialFact
        from app.services import trend_analysis_service
        from app.services.facts import companyfacts
        from app.services.facts.fiscal_evidence import trusted_fiscal_years

        db = SessionLocal()
        company = _new_company(db)
        ends = [date(year, 12, 31) for year in range(2015, 2022)]

        def dataset():
            built = trend_analysis_service.build_dataset(db, company, "annual", "FY2016", "FY2021")
            return {key: value for key, value in built.items() if key != "data_as_of"}

        with monkeypatch.context() as before_this_change:
            before_this_change.setattr(companyfacts, "own_report_history", lambda *args: [])
            first = svc._persist_companyfacts_payload(db, company, _payload())
        assert first["history"] == 0
        before, years_before = dataset(), trusted_fiscal_years(db, company.id, ends)
        assert next(s for s in before["series"] if s["concept"] == "revenue")["points"][2]["value"] == 5_145.6e6

        resync = svc._persist_companyfacts_payload(db, company, _payload())
        assert (resync["inserted"], resync["skipped"], resync["demoted"], resync["history"]) == (
            0, first["inserted"], 0, 3)
        fy2018 = db.query(FinancialFact).filter_by(company_id=company.id, concept="revenue",
                                                   period_end=date(2018, 12, 31)).all()
        assert {(r.accession, float(r.value), r.is_latest, r.source, r.filing_id) for r in fy2018} == {
            (K20, 5_145.6e6, True, "companyfacts", None), (K18, 6_710.8e6, False, "companyfacts", None)}
        assert dataset() == before  # every key but the sync time, the fingerprint (snapshot_id) included
        assert trusted_fiscal_years(db, company.id, ends) == years_before
        db.close()
