"""The analysis dataset reads each year's own annual report's value as evidence (MPA WP5a-B).

``trend_analysis/first_reports.py`` reads the company's non-current fiscal-year rows once per annual dataset and gives
a reported figure whose own report gave another value the ``first_reported`` the page decodes
(``frontend/features/analysis/lib/laterFilings.ts``). The rows are WP5b's (#1682), built here through its real writer
on its REGN shape (``test_companyfacts_own_report_history.py``): REGN's FY2018 10-K gives FY2018 revenue 6,710.8M, its
FY2020 10-K a narrower 5,145.6M under the same tag (docs/mpa-improvements/coherence.md section 1.6). The own report is
ingest's (``facts/own_reports._own_report``) replayed on stored rows; ``TestOneOwnReport`` holds the two to one answer.
"""
import copy
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import event

from app.services import facts_service as svc
from app.services.trend_analysis.first_reports import (
    BASIS_INPUTS, _CALCULATED, FirstReports, _has_finding, _ratio, basis_changed, differs, disagreement,
    own_period_ends,
)
from app.services.trend_analysis.source_documents import FilingDates
from app.utils.sec_urls import build_sec_archive_url
from tests.unit.test_companyfacts_own_report_history import (
    K18, K19, K20, K21, _K, _NET_INCOME, _REVENUE, _item, _items, _payload, _shapes,
)

FY2018 = date(2018, 12, 31)


@pytest.fixture(scope="module", autouse=True)
def _tables():
    from app.database import engine
    from app.models import Base

    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def db():
    """A session whose test's filing rows leave with it: the REGN shape's accessions are fixed, and a filing's
    accession is unique across companies."""
    from app.database import SessionLocal
    from app.models import Filing

    session = SessionLocal()
    yield session
    session.rollback()
    session.query(Filing).filter(Filing.accession_number.in_([accession for accession, _filed in _K.values()]))\
        .delete(synchronize_session=False)
    session.commit()
    session.close()


def _company(db):
    from app.models import Company

    suffix = uuid.uuid4().hex[:8]
    company = Company(cik=str(uuid.uuid4().int % 10**9), ticker=("F" + suffix[:5]).upper(), name=f"Co {suffix}")
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


def _synced(db, *payloads):
    """A company synced through WP5b's writer, once per payload, in order."""
    company = _company(db)
    for payload in payloads:
        svc._persist_companyfacts_payload(db, company, payload)
    return company


def _build(db, company, start="FY2017", end="FY2021", mode="annual"):
    from app.services import trend_analysis_service

    return trend_analysis_service.build_dataset(db, company, mode, start, end)


def _evidence(dataset):
    return {(series["concept"], point["period"]): point["first_reported"]
            for series in dataset["series"] for point in series["points"] if "first_reported" in point}


def _yoy(dataset, concept):
    series = next(series for series in dataset["series"] if series["concept"] == concept)
    return {point["period"]: (point.get("yoy"), point.get("yoy_first_reported", "absent")) for point in series["points"]
            if point.get("value") is not None}


def _restated(fy2018_own, fy2018_later, fy2019_own, fy2019_later):
    """REGN's revenue shape with FY2018 and FY2019 as their own 10-Ks and the FY2020 10-K give them."""
    return {
        2017: {2015: 4_103.7e6, 2016: 4_860.4e6, 2017: 5_872.2e6},
        2018: {2016: 4_860.4e6, 2017: 5_872.2e6, 2018: fy2018_own},
        2019: {2017: 5_872.2e6, 2018: fy2018_own, 2019: fy2019_own},
        2020: {2018: fy2018_later, 2019: fy2019_later, 2020: 8_497.1e6},
        2021: {2019: fy2019_later, 2020: 8_497.1e6, 2021: 16_071.7e6},
    }


def _point(dataset, concept, period):
    series = next(series for series in dataset["series"] if series["concept"] == concept)
    return next(point for point in series["points"] if point["period"] == period)


def _net_income(later):
    """REGN's net income, each report its own year and the two before, with the FY2020 10-K's comparatives changed."""
    reports = {report: {year: _NET_INCOME[year] for year in range(report - 2, report + 1)} for report in _K}
    reports[2020] = {**reports[2020], **later}
    return {"NetIncomeLoss": {"units": {"USD": _items(reports)}}}


def _up_to(year, revenue=None):
    """WP5b's REGN payload as SEC listed it after the 10-K for ``year``: the reports up to it."""
    reports = {report: values for report, values in (revenue or _REVENUE).items() if report <= year}
    payload = _payload(_items(reports))
    for tag in payload["facts"]["us-gaap"].values():
        tag["units"]["USD"] = [item for item in tag["units"]["USD"] if item["fy"] <= year]
    return payload


def _rows(db, company, **filters):
    from app.models import FinancialFact

    return db.query(FinancialFact).filter_by(company_id=company.id, **filters).all()


def _filing(db, company, accession, filed, *, form="10-K", period_end=None, document=None):
    from app.models import Filing

    folder = build_sec_archive_url(company.cik, accession)
    db.add(Filing(company_id=company.id, accession_number=accession, filing_type=form,
                  filing_date=datetime.fromisoformat(filed).replace(tzinfo=timezone.utc),
                  period_end_date=period_end and datetime.combine(period_end, datetime.min.time(), timezone.utc),
                  document_url=folder + (document or "primary.htm"), sec_url=folder))
    db.commit()


@pytest.mark.requires_db
class TestTheEvidenceOnReportedFigures:
    def test_regn_revenue_and_total_assets_carry_their_own_reports_values(self, db):
        company = _synced(db, _payload())
        evidence = _evidence(_build(db, company))
        folder = lambda accession: build_sec_archive_url(company.cik, accession)  # noqa: E731
        assert evidence == {
            ("revenue", "FY2018"): {
                "value": 6_710.8e6, "unit": "USD", "form": "10-K", "accession": K18, "filed_at": "2019-02-07",
                "source_url": folder(K18), "later_filed_at": "2021-02-08", "disagreement": None},
            ("revenue", "FY2019"): {
                "value": 7_863.4e6, "unit": "USD", "form": "10-K", "accession": K19, "filed_at": "2020-02-07",
                "source_url": folder(K19), "later_filed_at": "2022-02-07", "disagreement": None},
            # A 0.24% gap: over D1's 0.1%.
            ("total_assets", "FY2018"): {
                "value": 15_163.8e6, "unit": "USD", "form": "10-K", "accession": K18, "filed_at": "2019-02-07",
                "source_url": folder(K18), "later_filed_at": "2020-02-07", "disagreement": None},
        }

    @pytest.mark.parametrize("later, carries", [(6_006.0e6, False), (6_006.1e6, True), (5_994.0e6, False),
                                                (5_993.9e6, True)],
                             ids=["exactly-0.1%-above", "just-over-above", "exactly-0.1%-below", "just-over-below"])
    def test_d1_a_gap_carries_evidence_only_past_a_tenth_of_a_percent_of_the_own_value(self, db, later, carries):
        revenue = {**_REVENUE, 2018: {**_REVENUE[2018], 2018: 6_000.0e6}, 2019: {**_REVENUE[2019], 2018: 6_000.0e6},
                   2020: {**_REVENUE[2020], 2018: later}}
        company = _synced(db, _payload(_items(revenue)))
        assert (("revenue", "FY2018") in _evidence(_build(db, company))) is carries
        assert differs(later, 6_000.0e6) is carries

    def test_the_own_report_held_by_a_filing_owned_row_gives_its_evidence_and_its_filing_rows_dates(self, db):
        # The per-filing writer processed the FY2018 10-K before the sync: its row holds the own report's cell, so
        # the sync stores no history row there, and the winner, whose filing is newer, demotes it. Its record carries
        # no filed day: the filing row's is read, from the dataset's one read of the filings, with the document as
        # the link.
        from app.models import FinancialFact
        from app.services.fact_provenance import reported_provenance

        company = _company(db)
        _filing(db, company, K18, "2019-02-07", period_end=FY2018, document="regn-10k2018.htm")
        _filing(db, company, K20, "2021-02-08", period_end=date(2020, 12, 31))
        filing_id = _rows_filing_id(db, K18)
        db.add(FinancialFact(company_id=company.id, filing_id=filing_id, concept="revenue", raw_tag="us-gaap:Revenues",
                             unit="USD", period_start=date(2018, 1, 1), period_end=FY2018, fiscal_year=2018,
                             fiscal_period="FY", value=6_710.8e6, form="10-K", accession=K18, source="edgar_xbrl",
                             reconciled=True, is_latest=True, provenance=reported_provenance({"reconciled": True})))
        db.commit()
        result = svc._persist_companyfacts_payload(db, company, _payload())
        assert result["history"] == 2  # FY2019 revenue and FY2018 total assets; FY2018 revenue's cell was held
        [held] = _rows(db, company, concept="revenue", accession=K18, period_end=FY2018)
        assert (held.filing_id, held.is_latest) == (filing_id, False)
        first = _evidence(_build(db, company))[("revenue", "FY2018")]
        assert (first["value"], first["accession"], first["filed_at"]) == (6_710.8e6, K18, "2019-02-07")
        assert first["source_url"] == build_sec_archive_url(company.cik, K18) + "regn-10k2018.htm"

    def test_a_demoted_former_winner_holds_the_own_report(self, db):
        # Synced after the FY2018 10-K, then after the FY2021 one: the FY2018 10-K's own value won first and was
        # demoted, so its cell is held and the second sync stores no history row there.
        company = _synced(db, _up_to(2018), _payload())
        [held] = _rows(db, company, concept="revenue", accession=K18, period_end=FY2018)
        assert held.is_latest is False
        assert _evidence(_build(db, company))[("revenue", "FY2018")]["accession"] == K18

    def test_a_later_filings_demoted_value_is_never_the_years_own_report(self, db):
        # No FY2018 10-K item under the winning tag. Synced after the FY2019 10-K, its FY2018 comparative won; the
        # FY2020 10-K's then demoted it. That row is the FY2019 10-K's, whose own year is 2019: no evidence.
        revenue = {**_REVENUE, 2018: {}}
        company = _synced(db, _up_to(2019, revenue), _payload(_items(revenue)))
        [demoted] = _rows(db, company, concept="revenue", accession=K19, period_end=FY2018)
        assert (float(demoted.value), demoted.is_latest) == (6_710.8e6, False)
        evidence = _evidence(_build(db, company))
        assert ("revenue", "FY2018") not in evidence
        assert evidence[("revenue", "FY2019")]["accession"] == K19

    def test_a_withheld_own_row_gives_no_evidence(self, db):
        company = _synced(db, _payload())
        [own] = _rows(db, company, concept="revenue", accession=K18, period_end=FY2018)
        own.provenance = {**own.provenance, "validation": "unavailable", "reasons": ["calculation_parent_withdrawn"]}
        db.commit()
        assert ("revenue", "FY2018") not in _evidence(_build(db, company))

    @pytest.mark.parametrize("change", [{"period_start": date(2018, 1, 2)}, {"unit": "EUR"}],
                             ids=["another-span", "another-unit"])
    def test_an_own_row_for_another_span_or_unit_gives_no_evidence(self, db, change):
        company = _synced(db, _payload())
        [own] = _rows(db, company, concept="revenue", accession=K18, period_end=FY2018)
        for name, value in change.items():
            setattr(own, name, value)
        db.commit()
        evidence = _evidence(_build(db, company))
        assert ("revenue", "FY2018") not in evidence and ("revenue", "FY2019") in evidence

    @pytest.mark.parametrize("other, form, filed", [("0001532176-19-000001", "10-K/A", "2019-02-07"),
                                                    ("0001532176-19-000002", "10-K", "2019-03-15")],
                             ids=["an-amendment-filed-the-same-day", "an-original-filed-later"])
    def test_an_original_wins_over_an_amendment_then_the_earliest_filed(self, db, other, form, filed):
        # A second own report of FY2018, stored beside K18's row, whose accession sorts first: the original filed
        # first is the own report, as ingest picks it.
        from app.models import FinancialFact
        from app.services.fact_provenance import reported_provenance

        company = _synced(db, _payload())
        fact = {"reconciled": True}
        db.add(FinancialFact(company_id=company.id, concept="revenue", raw_tag="us-gaap:X", unit="USD",
                             period_start=date(2018, 1, 1), period_end=FY2018, fiscal_year=2018, fiscal_period="FY",
                             value=6_702.5e6, form=form, accession=other, source="companyfacts", reconciled=True,
                             is_latest=False, provenance=reported_provenance(fact, filed)))
        db.commit()
        assert _evidence(_build(db, company))[("revenue", "FY2018")]["accession"] == K18

    @pytest.mark.parametrize("reported, kept", [(date(2019, 12, 31), False), (date(2019, 1, 10), True)],
                             ids=["a-year-later", "within-the-drift"])
    def test_a_filing_whose_own_year_is_not_stored_owns_none_of_its_rows(self, db, reported, kept):
        # The filing row says K18 reports a year ending 2019-12-31, beyond every row stored there: its own year was
        # never stored, so its FY2018 row is a comparative. A period of report within DRIFT_DAYS is the same year.
        company = _synced(db, _payload())
        _filing(db, company, K18, "2019-02-07", period_end=reported)
        evidence = _evidence(_build(db, company))
        assert (("revenue", "FY2018") in evidence) is kept and (("total_assets", "FY2018") in evidence) is kept

    def test_the_figure_shown_ranks_with_the_years_own_reports(self, db):
        # The FY2021 10-K's filing row is stored; a 10-K/A restating its revenue is filed later, and the next sync runs
        # before its filing row lands, so the bulk writer keeps the original current and stores the amendment's value
        # non-current. The original is the year's own report (an original before an amendment) and is the figure
        # shown: no evidence, no n/m, as ingest stores no history row for it.
        company = _company(db)
        _filing(db, company, K21, "2022-02-07", period_end=date(2021, 12, 31))
        svc._persist_companyfacts_payload(db, company, _payload())
        amended = "0001804220-22-000099"
        svc._persist_companyfacts_payload(db, company, _payload(_items(_REVENUE) + [
            _item(16_500.0e6, 2021, 2021, accn=amended, form="10-K/A", filed="2022-05-01")]))
        rows = {(row.accession, row.is_latest) for row in _rows(db, company, concept="revenue", period_end=date(2021, 12, 31))}
        assert rows == {(K21, True), (amended, False)}
        dataset = _build(db, company)
        assert ("revenue", "FY2021") not in _evidence(dataset)
        assert _yoy(dataset, "revenue")["FY2021"] == (pytest.approx(16_071.7 / 8_497.1 - 1), "absent")

    def test_a_flow_of_unknown_duration_matches_nothing(self, db):
        # The per-filing writer stored durations without a start before #831 ("duration unknown"): a flow whose start
        # is missing matches no own row, not even another without one, while a balance has no start by nature.
        from app.models import FinancialFact
        from app.services.fact_provenance import reported_provenance

        company = _company(db)
        for accession, end, value, current in ((K18, FY2018, 6_710.8e6, False), (K20, FY2018, 5_145.6e6, True),
                                               (K19, date(2019, 12, 31), 7_863.4e6, True)):
            for concept, start in (("revenue", None), ("total_assets", None)):
                db.add(FinancialFact(company_id=company.id, concept=concept, raw_tag="us-gaap:X", unit="USD",
                                     period_start=start, period_end=end, fiscal_year=end.year, fiscal_period="FY",
                                     value=value, form="10-K", accession=accession, source="edgar_xbrl",
                                     reconciled=True, is_latest=current, provenance=reported_provenance({"reconciled": True})))
        db.commit()
        evidence = _evidence(_build(db, company, "FY2018", "FY2019"))
        assert set(evidence) == {("total_assets", "FY2018")}

    def test_no_calculated_figure_carries_evidence_of_its_own(self, db):
        company = _synced(db, _payload())
        dataset = _build(db, company)
        margin = next(series for series in dataset["series"] if series["concept"] == "net_margin")
        assert margin["points"] and not [point for point in margin["points"] if "first_reported" in point]

    def test_the_stored_rows_are_not_changed_by_a_build(self, db):
        company = _synced(db, _payload())
        stored = {row.id: (row.provenance, float(row.value), row.is_latest) for row in _rows(db, company)}
        _build(db, company)
        db.expire_all()
        assert {row.id: (row.provenance, float(row.value), row.is_latest) for row in _rows(db, company)} == stored


def _rows_filing_id(db, accession):
    from app.models import Filing

    return db.query(Filing.id).filter_by(accession_number=accession).scalar()


@pytest.mark.requires_db
class TestReads:
    def _statements(self, db, company, mode, start, end):
        statements = []

        def spy(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement)

        engine = db.get_bind()
        event.listen(engine, "before_cursor_execute", spy)
        try:
            dataset = _build(db, company, start, end, mode)
        finally:
            event.remove(engine, "before_cursor_execute", spy)
        return dataset, [statement for statement in statements if "FROM financial_fact" in statement], \
            [statement for statement in statements if "FROM filings" in statement]

    def test_an_annual_dataset_reads_the_facts_twice_and_the_filings_once(self, db):
        company = _synced(db, _payload())
        _filing(db, company, K18, "2019-02-07", period_end=FY2018)
        dataset, facts, filings = self._statements(db, company, "annual", "FY2017", "FY2021")
        assert _evidence(dataset)
        assert (len(facts), len(filings)) == (2, 1)
        assert "is_latest IS 0" in facts[1] or "is_latest = false" in facts[1].lower()

    def test_a_quarterly_dataset_reads_no_more_and_carries_no_later_filing_field(self, db):
        # The own-report rows are stored, and a quarter's balance shares the year-end they cover; a quarterly run
        # still reads the facts once and carries no evidence (D5).
        import json

        from app.models import FinancialFact

        company = _synced(db, _payload())
        for quarter, end in enumerate((date(2018, 3, 31), date(2018, 6, 30), date(2018, 9, 30), FY2018), start=1):
            for concept, value, start in (("revenue", 1_300.0e6 + quarter, date(end.year, end.month - 2, 1)),
                                          ("total_assets", 15_200.1e6, None)):
                db.add(FinancialFact(company_id=company.id, concept=concept, raw_tag="us-gaap:X", unit="USD",
                                     period_start=start, period_end=end, fiscal_year=2018,
                                     fiscal_period=f"Q{quarter}", value=value, form="10-Q", accession=K20,
                                     source="companyfacts", reconciled=True, is_latest=True))
        db.commit()
        dataset, facts, filings = self._statements(db, company, "quarterly", "2018Q1", "2018Q4")
        assert len(facts) == 1 and len(filings) == 1
        text = json.dumps(dataset)
        assert "first_reported" not in text and dataset["series"]


_K18A, _K18B, _K21A = "0001532176-19-000050", "0001532176-19-000060", "0001804220-22-000099"


def _amended(base, amendments):
    """A payload whose revenue gains these items (value, fiscal year, report year, accession, form, filed)."""
    revenue = _items(base) + [_item(value, year, report, accn=accn, form=form, filed=filed)
                              for value, year, report, accn, form, filed in amendments]
    return _payload(revenue)


def _sequences():
    """Sync sequences, each a list of (filing rows to store first, payload): every WP5b own-report shape synced once,
    and the shapes several syncs and partial filing rows leave in the database (demoted former winners, an amendment
    kept non-current, an own report filed again)."""
    later_k18 = (6_750.0e6, 2018, 2018, _K18A, "10-K/A", "2019-05-01")
    refiled = (6_700.0e6, 2018, 2018, _K18B, "10-K", "2019-03-15")
    without_k18 = {**_REVENUE, 2018: {}}
    return {
        **{f"once-{name}": [((), payload)] for name, payload in _shapes().items()},
        "after-each-10-K": [((), _up_to(2018)), ((), _up_to(2019)), ((), _up_to(2020)), ((), _payload())],
        "a-later-filings-demoted-comparative": [((), _up_to(2019, without_k18)), ((), _payload(_items(without_k18)))],
        # The review's shape: the FY2021 10-K's filing row stored, a 10-K/A for FY2021 filed later and synced before
        # its row lands, so the original stays current and the amendment's value is stored non-current.
        "an-amendment-kept-non-current": [((K21,), _payload()), ((), _amended(_REVENUE, [
            (16_500.0e6, 2021, 2021, _K21A, "10-K/A", "2022-05-01")]))],
        # A 10-K/A for FY2018 filed after the original wins FY2018 until the FY2020 10-K: the original, its history,
        # and the demoted amendment all hold FY2018 cells.
        "an-amendment-filed-after-the-original": [
            ((), _amended({year: values for year, values in _REVENUE.items() if year <= 2018}, [later_k18])),
            ((), _amended(_REVENUE, [later_k18]))],
        # The FY2018 10-K filed again five weeks later wins FY2018 at the first sync, the original kept as history,
        # until the FY2020 10-K demotes it: two own reports of FY2018 stored, the earlier filed the year's own.
        "an-own-report-filed-again-with-filing-rows": [
            ((K18, K20), _amended({year: values for year, values in _REVENUE.items() if year <= 2018}, [refiled])),
            ((), _amended(_REVENUE, [refiled]))],
    }


class TestOneOwnReport:
    """Ingest's own report and the reader's are one rule (CLAUDE.md rule 12). Over sync sequences that leave several
    own candidates in one cell, the year's own report the dataset reads is the one ingest's ``_own_report`` picks
    from the last payload (through the census's within-tag lookup, which calls it): the dataset gives evidence exactly
    where that report is another filing than the figure shown and differs from it past D1, with its value and
    accession, and none anywhere else, a year whose own report is the figure shown included."""

    @pytest.mark.requires_db
    @pytest.mark.parametrize("sequence", list(_sequences()))
    def test_the_reader_reads_the_own_report_ingest_picks(self, db, sequence):
        from app.services.facts.concepts import NON_NEGATIVE_CONCEPTS
        from scripts import restatement_census

        steps = _sequences()[sequence]
        company = _company(db)
        for filings, payload in steps:
            for accession in filings:
                year = next(year for year, (number, _filed) in _K.items() if number == accession)
                _filing(db, company, accession, _K[year][1], period_end=date(year, 12, 31))
            svc._persist_companyfacts_payload(db, company, payload)
        cells, _info = restatement_census.measure_company("REGN", steps[-1][1], False, 10)
        ingest = {(cell["concept"], f"FY{cell['fy']}"): cell["within"] for cell in cells}
        dataset = _build(db, company, "FY2015", "FY2021")
        expected, picked = {}, {}
        for series in dataset["series"]:
            for point in series["points"]:
                if point.get("value") is None or (point.get("provenance") or {}).get("method") != "reported":
                    continue
                place = (series["concept"], point["period"])
                own = ingest.get(place)
                if own and not (series["concept"] in NON_NEGATIVE_CONCEPTS and own["value"] < 0) \
                        and own["accession"] != point["accession"] and differs(point["value"], own["value"]):
                    expected[place] = (own["value"], own["accession"])
                if "first_reported" in point:
                    picked[place] = (point["first_reported"]["value"], point["first_reported"]["accession"])
        assert picked == expected
        assert expected

    def test_an_annual_filings_own_end_reads_its_annual_rows_and_its_filing_row(self):
        def row(accession, end, *, form="10-K", start=True, period="FY"):
            return SimpleNamespace(accession=accession, period_end=end, form=form, fiscal_period=period,
                                   period_start=date(end.year, 1, 1) if start else None)

        k18, k19, k20, quarterly = ("0000000001-19-000001", "0000000001-20-000001", "0000000001-21-000001",
                                    "0000000001-19-000002")
        ends = own_period_ends([
            row(k18, date(2016, 12, 31)), row(k18, FY2018, form=None),  # no form, at an annual report's accession
            row(k19, date(2018, 12, 31), start=False), row(k19, date(2017, 12, 31)),  # its own year's balance alone
            row(k20, date(2021, 3, 31), period="Q1"), row(k20, date(2019, 12, 31), form="10-Q"),  # no annual row
            row(quarterly, FY2018, form=None),  # no form, and nothing says the filing is an annual report
        ], {})
        assert ends == {"000000000119000001": FY2018, "000000000120000001": FY2018}
        # The filing row names the form: its no-form row counts.
        assert own_period_ends([row(quarterly, FY2018, form=None)],
                               {"000000000119000002": FilingDates("10-K", "2019-02-07", FY2018)}) == {
            "000000000119000002": FY2018}
        assert own_period_ends([row(quarterly, FY2018, form=None)],
                               {"000000000119000002": FilingDates("10-Q", "2019-02-07", FY2018)}) == {}


@pytest.mark.requires_db
class TestGrowthAcrossAChangeOfBasis:
    def test_regn_revenue_and_net_margin_growth_read_n_m_with_the_growth_their_own_reports_give(self, db):
        dataset = _build(db, _synced(db, _payload()))
        revenue, margin = _yoy(dataset, "revenue"), _yoy(dataset, "net_margin")
        assert {period: value[0] for period, value in revenue.items()} == {
            "FY2017": None, "FY2018": "nm", "FY2019": "nm", "FY2020": "nm", "FY2021": pytest.approx(16_071.7 / 8_497.1 - 1)}
        assert [revenue[period][1] for period in ("FY2018", "FY2019", "FY2020")] == [
            pytest.approx(6_710.8 / 5_872.2 - 1, abs=1e-9), pytest.approx(7_863.4 / 6_710.8 - 1, abs=1e-9),
            pytest.approx(8_497.1 / 7_863.4 - 1, abs=1e-9)]
        assert revenue["FY2021"][1] == "absent"
        # D4: the margin's pp change reads n/m across its revenue input's change, and gives the change in percentage
        # points between the margins the two years' own reports give.
        own = {2017: 1_198.5 / 5_872.2, 2018: 2_444.4 / 6_710.8, 2019: 2_115.8 / 7_863.4, 2020: 3_513.2 / 8_497.1}
        assert [margin[f"FY{year}"] for year in (2018, 2019, 2020)] == [
            ("nm", pytest.approx(100 * (own[year] - own[year - 1]), abs=1e-6)) for year in (2018, 2019, 2020)]
        assert margin["FY2021"][0] == pytest.approx(100 * (8_075.3 / 16_071.7 - 3_513.2 / 8_497.1), abs=1e-6)
        # Net income kept its basis; total assets' 0.24% moves no ratio past 1%.
        assert all(isinstance(value, float) and first == "absent" for period, (value, first)
                   in {**_yoy(dataset, "net_income"), **_yoy(dataset, "total_assets")}.items() if period != "FY2017")

    def test_an_n_m_across_a_change_of_basis_keeps_its_calculation_and_checks(self, db):
        dataset = _build(db, _synced(db, _payload()))
        point = next(series for series in dataset["series"] if series["concept"] == "revenue")["points"][1]
        assert (point["period"], point["yoy"], point["yoy_reconciled"]) == ("FY2018", "nm", True)
        assert point["yoy_provenance"]["validation"] == "passed" and point["yoy_provenance"]["reasons"] == []
        assert point["yoy_provenance"]["formula"] == "year_over_year_growth"

    def test_a_run_restated_at_one_ratio_keeps_its_growth(self, db):
        # FY2018 and FY2019 both later reported at 80% of their own reports: the growth between them is the same on
        # either basis; only the changes across the run's edges read n/m.
        dataset = _build(db, _synced(db, _payload(_items(_restated(1_000.0e6, 800.0e6, 1_250.0e6, 1_000.0e6)))))
        revenue = _yoy(dataset, "revenue")
        assert revenue["FY2019"] == (pytest.approx(0.25), "absent")
        assert revenue["FY2018"][0] == revenue["FY2020"][0] == "nm"

    @pytest.mark.parametrize("fy2019_later, n_m", [(908.1e6, False), (909.0e6, False), (909.9e6, True)],
                             ids=["0.9%", "exactly-1%", "1.1%"])
    def test_d1_growth_reads_n_m_only_past_a_one_percent_move_of_the_ratio(self, db, fy2019_later, n_m):
        # FY2018 later reported at 90% of its own report, FY2019 at 90.81%, 90.9% or 90.99%.
        dataset = _build(db, _synced(db, _payload(_items(_restated(1_000.0e6, 900.0e6, 1_000.0e6, fy2019_later)))))
        assert (_yoy(dataset, "revenue")["FY2019"][0] == "nm") is n_m

    def test_a_change_of_sign_reads_n_m_with_no_growth_as_first_reported(self, db):
        loss = {report: {year: (-500.0e6 if year == 2018 else _NET_INCOME[year]) for year in range(report - 2, report + 1)}
                for report in _K}
        dataset = _build(db, _synced(db, _payload(tags={"NetIncomeLoss": {"units": {"USD": _items(loss)}}})))
        assert _yoy(dataset, "net_income")["FY2018"] == _yoy(dataset, "net_income")["FY2019"] == ("nm", "absent")

    @pytest.mark.parametrize("tag, concept", [("EarningsPerShareBasic", "earnings_per_share"),
                                              ("EarningsPerShareDiluted", "eps_diluted")], ids=["basic", "diluted"])
    def test_d3_eps_keeps_its_evidence_and_its_growth_across_a_split(self, db, tag, concept):
        # A 10-for-1 split before the FY2020 10-K: it restates FY2018 and FY2019 at a tenth.
        eps = {2017: {2015: 5.0, 2016: 6.0, 2017: 10.0}, 2018: {2016: 6.0, 2017: 10.0, 2018: 12.0},
               2019: {2017: 10.0, 2018: 12.0, 2019: 13.0}, 2020: {2018: 1.2, 2019: 1.3, 2020: 1.5},
               2021: {2019: 1.3, 2020: 1.5, 2021: 2.0}}
        dataset = _build(db, _synced(db, _payload(tags={tag: {"units": {"USD/shares": _items(eps)}}})))
        evidence = _evidence(dataset)
        assert (evidence[(concept, "FY2018")]["value"], evidence[(concept, "FY2019")]["value"]) == (12.0, 13.0)
        # The evidence is in the figure's own unit.
        assert evidence[(concept, "FY2018")]["unit"] == _point(dataset, concept, "FY2018")["unit"] == "USD/shares"
        assert all(isinstance(value, float) and first == "absent"
                   for period, (value, first) in _yoy(dataset, concept).items() if period != "FY2017")

    def test_d4_a_calculation_stored_without_its_operands_reads_its_inputs_from_the_dataset(self, db):
        # A margin stored before operands were recorded has none: the revenue the dataset shows for the year stands in.
        from app.models import FinancialFact

        company = _synced(db, _payload())
        db.query(FinancialFact).filter_by(company_id=company.id, concept="net_margin").update(
            {"provenance": None}, synchronize_session=False)
        db.commit()
        margin = _yoy(_build(db, company), "net_margin")
        assert margin["FY2018"] == ("nm", pytest.approx(100 * (2_444.4 / 6_710.8 - 1_198.5 / 5_872.2), abs=1e-6))
        assert isinstance(margin["FY2021"][0], float)

    def test_a_calculation_stored_without_its_operands_reads_n_m_across_its_inputs_finding(self, db):
        # The input's finding sits on the dataset's revenue figure, read in the operands' place: n/m as first reported
        # on that year and the next, never a number.
        from app.models import FinancialFact

        company = _synced(db, _payload(_items({**_REVENUE, 2020: {**_REVENUE[2020], 2018: 6_710.8e3}})))
        db.query(FinancialFact).filter_by(company_id=company.id, concept="net_margin").update(
            {"provenance": None}, synchronize_session=False)
        db.commit()
        margin = _yoy(_build(db, company), "net_margin")
        assert margin["FY2018"] == margin["FY2019"] == ("nm", "nm")

    def test_the_catalogue_leaves_out_growth_across_a_change_of_basis(self, db):
        from app.services.trend_analysis.observations import build_observation_catalogue

        catalogue = build_observation_catalogue(_build(db, _synced(db, _payload())))
        growth = [item for item in catalogue if item.markdown.startswith("Revenue growth in")]
        assert [(item.markdown.split()[3], item.required) for item in growth] == [("FY2021", True)]


@pytest.mark.parametrize("now, before, changed", [
    ((100.0, None), (100.0, None), False),  # no evidence on either year: no change of basis
    ((90.0, {"value": 100.0}), (100.0, None), True),  # 0.9 against 1
    ((-100.0, {"value": 100.0}), (-100.0, {"value": 100.0}), False),  # both years flipped alike: one basis
    ((5.0, {"value": 0.0}), (100.0, None), True),  # an own value of 0 bounds no ratio
    ((5.0, {"value": 0.0}), (7.0, {"value": 0.0}), True),
    ((5.0, {"value": 10.0}), (0.0, {"value": 10.0}), True),  # a ratio of 0 the year before, not now
    ((0.0, {"value": 10.0}), (0.0, {"value": 20.0}), False),  # 0 shown on both years
], ids=["no-evidence", "a-move", "a-run-flipped-alike", "own-zero-now", "own-zero-both", "zero-before",
        "zero-both"])
def test_d1_the_basis_rule_reads_the_two_years_ratios(now, before, changed):
    assert basis_changed(_ratio(now), _ratio(before)) is changed


def _own(concept="revenue", value="6710800000"):
    from app.services.fact_provenance import reported_provenance

    return SimpleNamespace(concept=concept, unit="USD", period_start=date(2018, 1, 1), period_end=FY2018,
                           fiscal_period="FY", form="10-K", accession=K18, value=Decimal(value), raw_tag="us-gaap:X",
                           source="companyfacts", reconciled=True,
                           provenance=reported_provenance({"reconciled": True}, "2019-02-07"))


def _figure(concept="revenue", value=5_145.6e6, method="reported", inputs=()):
    from app.services.fact_provenance import reported_provenance

    return {"concept": concept, "value": value, "unit": "USD", "period_start": "2018-01-01",
            "period_end": "2018-12-31", "accession": K20, "filed_at": "2021-02-08",
            "provenance": {**reported_provenance({"reconciled": True}), "method": method, "inputs": list(inputs)}}


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_an_own_row_whose_stored_value_is_not_finite_gives_no_evidence(value):
    # The per-filing writer admits any float; one such row must not take the whole annual dataset down.
    point = _figure()
    FirstReports({}, {}, None, history=[_own(value=value)]).attach([point])
    assert "first_reported" not in point


@pytest.mark.parametrize("value", [float("nan"), float("inf")], ids=["nan", "inf"])
def test_a_shown_value_that_is_not_finite_carries_no_evidence(value):
    point = _figure(value=value)
    FirstReports({}, {}, None, history=[_own()]).attach([point])
    assert "first_reported" not in point


def test_a_finding_two_inputs_deep_on_the_year_before_holds_the_growth_as_first_reported_to_n_m():
    # A margin's FY2019 revenue input carries evidence, so its change reads n/m; its FY2018 net income input is itself
    # calculated, and the sign flip sits on that one's own reported input. The page reads the finding there too.
    from app.services.trend_analysis.dataset import _growth, _pp_delta

    flipped = {**_figure("net_income", -2_444.4e6), "first_reported": {"value": 2_444.4e6, "disagreement": "opposite_sign"}}
    fy2018 = {**_figure("net_margin", 47.5, "calculated", [_figure("revenue", 5_145.6e6),
                                                          _figure("net_income", -2_444.4e6, "calculated", [flipped])]),
              "period": "FY2018", "yoy": None}
    revenue = {**_figure("revenue", 6_557.6e6), "first_reported": {"value": 7_863.4e6, "disagreement": None}}
    fy2019 = {**_figure("net_margin", 32.3, "calculated", [revenue, _figure("net_income", 2_115.8e6)]),
              "period": "FY2019", "yoy": -15.2}
    series = [{"concept": "net_margin", "percent": True, "points": [fy2018, fy2019]}]
    FirstReports({}, {}, None, history=[_own()]).basis_rule(series, _growth, _pp_delta)
    assert (fy2019["yoy"], fy2019["yoy_first_reported"]) == ("nm", "nm")


def test_a_stored_filed_day_reads_as_a_day():
    # A timestamp in a record (the own row's, or the shown figure's) is sent as its calendar day, never as a timestamp.
    own = _own()
    own.provenance = {**own.provenance, "filed_at": "2019-02-07T00:00:00Z"}
    point = {**_figure(), "filed_at": None}
    point["provenance"] = {**point["provenance"], "filed_at": "2021-02-08T21:15:00+00:00"}
    FirstReports({}, {}, None, history=[own]).attach([point])
    assert (point["first_reported"]["filed_at"], point["first_reported"]["later_filed_at"]) == ("2019-02-07", "2021-02-08")


def test_item_5_an_input_at_any_depth_carries_its_evidence_on_a_copy():
    # A calculated input (one quarter's revenue derived from others, say) whose own reported input changed: the
    # reported operand carries the evidence, the calculated one none, and the records the figure was built from are
    # not written.
    reported = _figure()
    calculated = _figure(method="calculated", inputs=[reported])
    point = _figure("net_margin", 47.5, "calculated", [calculated])
    before = copy.deepcopy(point)
    FirstReports({}, {}, None, history=[_own()]).attach([point])
    outer = point["provenance"]["inputs"][0]
    assert "first_reported" not in outer and "first_reported" not in point
    assert outer["provenance"]["inputs"][0]["first_reported"]["accession"] == K18
    assert reported == before["provenance"]["inputs"][0]["provenance"]["inputs"][0] and "first_reported" not in reported


@pytest.mark.parametrize("figure, own", [(_figure(method="calculated"), _own()),
                                         (_figure("net_margin", 47.5), _own("net_margin", "36.4"))],
                         ids=["a-calculated-revenue", "a-reported-margin"])
def test_only_a_reported_figure_outside_the_calculated_concepts_carries_its_own(figure, own):
    # A calculated figure's evidence sits on its inputs, and a calculated concept's own row is no figure's evidence,
    # whatever its record says (the page refuses first_reported on a calculated figure).
    FirstReports({}, {}, None, history=[own]).attach([figure])
    assert "first_reported" not in figure


def test_d4_each_calculation_is_recomputed_as_ingest_computes_it():
    from app.services.facts.derive import derive_same_period_metrics

    def fact(concept, value):
        return {"company_id": 1, "concept": concept, "value": value, "unit": "USD", "period_start": date(2024, 1, 1),
                "period_end": date(2024, 12, 31), "fiscal_year": 2024, "fiscal_period": "FY", "accession": "a",
                "raw_tag": "us-gaap:X", "source": "companyfacts", "reconciled": True, "form": "10-K"}

    values = {"revenue": 900.0, "net_income": 81.0, "operating_income": 117.0, "gross_profit": 405.0,
              "operating_cash_flow": 150.0, "capital_expenditures": -40.0, "current_assets": 330.0,
              "current_liabilities": 120.0}
    derived = {item["concept"]: item["value"] for item in derive_same_period_metrics(
        [fact(concept, value) for concept, value in values.items()])}
    assert set(_CALCULATED) == set(BASIS_INPUTS) == set(derived)
    for concept, inputs in BASIS_INPUTS.items():
        assert _CALCULATED[concept](*(values[name] for name in inputs)) == derived[concept]


@pytest.mark.requires_db
class TestASignOrScaleFindingMarksTheFigure:
    def test_an_exact_sign_flip_is_a_source_conflict_note_on_the_value_and_its_growth(self, db):
        # The FY2020 10-K gives FY2018 net income with the opposite sign: the value, its growth either side and the
        # data notes carry the existing source_conflict reason; the evidence says what the comparison found.
        dataset = _build(db, _synced(db, _payload(tags=_net_income({2018: -2_444.4e6}))))
        point = _point(dataset, "net_income", "FY2018")
        assert (point["value"], point["first_reported"]["value"], point["first_reported"]["disagreement"]) == (
            -2_444.4e6, 2_444.4e6, "opposite_sign")
        assert (point["provenance"]["validation"], point["provenance"]["reasons"], point["reconciled"]) == (
            "needs_review", ["source_conflict"], False)
        for period in ("FY2018", "FY2019"):
            grown = _point(dataset, "net_income", period)
            # Across the finding the growth as first reported is n/m too, on the year itself and the year after.
            assert (grown["yoy"], grown["yoy_first_reported"], grown["yoy_reconciled"]) == ("nm", "nm", False)
            assert "source_conflict" in grown["yoy_provenance"]["reasons"]
        [note] = [note for note in dataset["data_notes"]["notes"] if note["reasons"] == ["source_conflict"]]
        assert (note["kind"], note["values"]) == ("review", [{"concept": "net_income", "label": "Net income",
                                                              "period": "FY2018"}])
        assert note["letter"]
        # The margin built on it is calculated: no mark of its own, no evidence of its own; its net income input,
        # reported, carries the finding (item 5), so its growth as first reported is n/m on that year and the next.
        margin = _point(dataset, "net_margin", "FY2018")
        assert "source_conflict" not in margin["provenance"]["reasons"] and "first_reported" not in margin
        [income] = [operand for operand in margin["provenance"]["inputs"] if operand["concept"] == "net_income"]
        assert (income["provenance"]["method"], income["first_reported"]["disagreement"]) == ("reported", "opposite_sign")
        assert margin["yoy_first_reported"] == _point(dataset, "net_margin", "FY2019")["yoy_first_reported"] == "nm"

    @pytest.mark.parametrize("factor, finding", [(1e-3, "scale"), (1e3, "scale"), (1e6, "scale"), (1e9, "scale"),
                                                 (999.9, None)],
                             ids=["a-thousandth", "1000x", "1000000x", "1000000000x", "a-near-miss"])
    def test_an_exact_factor_of_a_thousand_to_the_n_marks_the_balance_and_its_window(self, db, factor, finding):
        # The FY2019 10-K gives the FY2018 year-end balance at this multiple of the FY2018 10-K's.
        assets = {2017: {2016: 9_520.2e6, 2017: 11_734.5e6}, 2018: {2017: 11_734.5e6, 2018: 15_163.8e6},
                  2019: {2018: 15_163.8e6 * factor, 2019: 17_163.4e6}, 2020: {2019: 17_163.4e6, 2020: 19_994.1e6},
                  2021: {2020: 19_994.1e6, 2021: 25_434.7e6}}
        dataset = _build(db, _synced(db, _payload(assets=_items(assets, instant=True))), "FY2018", "FY2021")
        point = _point(dataset, "total_assets", "FY2018")
        assert point["first_reported"]["disagreement"] == finding
        assert ("source_conflict" in point["provenance"]["reasons"]) is (finding is not None)
        series = next(series for series in dataset["series"] if series["concept"] == "total_assets")
        assert ("source_conflict" in series["cagr_provenance"]["reasons"]) is (finding is not None)
        assert series["cagr_reconciled"] is (finding is None)
        following = _point(dataset, "total_assets", "FY2019")
        assert following["yoy"] == "nm" and (following["yoy_first_reported"] == "nm") is (finding is not None)

    def test_a_per_share_factor_meets_in_decimal_where_floats_round(self, db):
        # 2.01 x 1,000 is 2009.9999999999998 in floats; the comparison is exact in Decimal.
        assert 2.01 * 1000 != 2010.0
        eps = {2017: {2015: 1.5, 2016: 1.8, 2017: 1.9}, 2018: {2016: 1.8, 2017: 1.9, 2018: 2.01},
               2019: {2017: 1.9, 2018: 2.01, 2019: 2.2}, 2020: {2018: 2010.0, 2019: 2.2, 2020: 2.4},
               2021: {2019: 2.2, 2020: 2.4, 2021: 2.6}}
        dataset = _build(db, _synced(db, _payload(tags={"EarningsPerShareBasic": {"units": {"USD/shares": _items(eps)}}})))
        point = _point(dataset, "earnings_per_share", "FY2018")
        assert (point["first_reported"]["disagreement"], point["provenance"]["reasons"]) == ("scale", ["source_conflict"])

    def test_d2_a_per_share_sign_flip_is_evidence_with_no_finding(self, db):
        eps = {2017: {2015: 0.5, 2016: 0.6, 2017: 0.7}, 2018: {2016: 0.6, 2017: 0.7, 2018: -0.05},
               2019: {2017: 0.7, 2018: -0.05, 2019: 0.8}, 2020: {2018: 0.05, 2019: 0.8, 2020: 0.9},
               2021: {2019: 0.8, 2020: 0.9, 2021: 1.0}}
        dataset = _build(db, _synced(db, _payload(tags={"EarningsPerShareBasic": {"units": {"USD/shares": _items(eps)}}})))
        point = _point(dataset, "earnings_per_share", "FY2018")
        assert (point["first_reported"]["value"], point["first_reported"]["disagreement"]) == (-0.05, None)
        assert point["provenance"]["reasons"] == [] and point["reconciled"] is True

    def test_d6_an_own_row_that_did_not_pass_its_checks_gives_evidence_and_no_mark(self, db):
        company = _synced(db, _payload(tags=_net_income({2018: -2_444.4e6})))
        [own] = _rows(db, company, concept="net_income", accession=K18, period_end=FY2018)
        own.provenance = {**own.provenance, "validation": "needs_review", "reasons": ["source_check_needed"]}
        db.commit()
        point = _point(_build(db, company), "net_income", "FY2018")
        assert point["first_reported"]["disagreement"] == "opposite_sign"
        assert (point["provenance"]["validation"], point["provenance"]["reasons"], point["reconciled"]) == (
            "passed", [], True)

    def test_a_calculated_figure_reads_n_m_as_first_reported_across_its_inputs_finding(self, db):
        # The FY2020 10-K gives FY2018 revenue in thousands: the margin's change reads n/m, and its growth as first
        # reported is n/m on that year and the next, never a number (the input's finding, at any depth).
        revenue = {**_REVENUE, 2020: {**_REVENUE[2020], 2018: 6_710.8e3}}
        dataset = _build(db, _synced(db, _payload(_items(revenue))))
        assert _point(dataset, "revenue", "FY2018")["first_reported"]["disagreement"] == "scale"
        margin = _yoy(dataset, "net_margin")
        assert margin["FY2018"] == margin["FY2019"] == ("nm", "nm")
        assert margin["FY2020"][0] == "nm" and isinstance(margin["FY2020"][1], float)

    def test_a_flip_of_a_non_negative_figure_never_reaches_the_dataset(self, db):
        # Ingest drops a negative revenue (facts/own_reports.py), so FY2018's own report leaves no row: no evidence,
        # no mark, while FY2019's evidence stands.
        revenue = {**_REVENUE, 2018: {**_REVENUE[2018], 2018: -6_710.8e6}}
        dataset = _build(db, _synced(db, _payload(_items(revenue))))
        point = _point(dataset, "revenue", "FY2018")
        assert "first_reported" not in point and point["provenance"]["reasons"] == []
        assert "first_reported" in _point(dataset, "revenue", "FY2019")


class TestTheCensusCountsTheAnalysissNM:
    """``scripts/restatement_census.py`` counts the n/m comparisons by the producer's own rule (D3's measurement):
    over WP5b's shapes, the comparisons it counts are the ones the dataset built from the same payload reads n/m."""

    def test_regn_gives_one_comparison_of_each_kind(self):
        from scripts import restatement_census

        cells, _info = restatement_census.measure_company("REGN", _payload(), False, 10)
        assert [(c["concept"], c["fy"], c["kind"], c["per_share"]) for c in restatement_census.basis_comparisons(cells)] \
            == [("revenue", 2018, "crossing", False), ("revenue", 2019, "inside a run", False),
                ("revenue", 2020, "leading edge", False)]
        table = restatement_census._basis_table(cells)
        assert "| **all** | 3 (1) | 0 (0) | 3 (1) |" in table and "| leading edge | 1 (1) | 0 (0) | 1 (1) |" in table

    @pytest.mark.requires_db
    @pytest.mark.parametrize("shape", [*_shapes(), "a-negative-own-revenue"])
    def test_the_census_counts_the_comparisons_the_dataset_reads_n_m(self, db, shape):
        # Beside WP5b's shapes, an own value ingest drops (a negative revenue) gives the census no evidence either.
        from scripts import restatement_census

        payload = _shapes().get(shape) or _payload(_items({**_REVENUE, 2018: {**_REVENUE[2018], 2018: -6_710.8e6}}))
        cells, _info = restatement_census.measure_company("REGN", payload, False, 10)
        counted = {(c["concept"], f"FY{c['fy']}") for c in restatement_census.basis_comparisons(cells)}
        dataset = _build(db, _synced(db, payload), "FY2015", "FY2021")
        read = {(series["concept"], point["period"]) for series in dataset["series"] for point in series["points"]
                if "yoy_first_reported" in point and series["concept"] not in BASIS_INPUTS}
        assert counted == read


@pytest.mark.requires_db
class TestACalculatedFiguresInputsCarryTheirEvidence:
    def _inputs(self, provenance):
        return {operand["concept"]: operand.get("first_reported") for operand in provenance["inputs"]}

    def test_regn_net_margins_revenue_input_carries_its_own_reports_value(self, db):
        company = _synced(db, _payload())
        dataset = _build(db, company)
        folder = build_sec_archive_url(company.cik, K18)
        inputs = {period: self._inputs(_point(dataset, "net_margin", period)["provenance"])
                  for period in ("FY2017", "FY2018", "FY2019", "FY2020", "FY2021")}
        assert inputs["FY2018"] == {"net_income": None, "revenue": {
            "value": 6_710.8e6, "unit": "USD", "form": "10-K", "accession": K18, "filed_at": "2019-02-07",
            "source_url": folder, "later_filed_at": "2021-02-08", "disagreement": None}}
        assert inputs["FY2019"]["revenue"]["accession"] == K19 and inputs["FY2019"]["net_income"] is None
        assert all(first is None for period in ("FY2017", "FY2020", "FY2021") for first in inputs[period].values())
        # The figure itself carries none: its evidence is its inputs'.
        assert "first_reported" not in _point(dataset, "net_margin", "FY2018")

    def test_the_comparisons_and_window_change_nest_the_inputs_evidence(self, db):
        dataset = _build(db, _synced(db, _payload()), "FY2018", "FY2021")
        fy2019 = _point(dataset, "net_margin", "FY2019")
        current, previous = fy2019["yoy_provenance"]["inputs"]
        assert self._inputs(current["provenance"])["revenue"]["accession"] == K19
        assert self._inputs(previous["provenance"])["revenue"]["accession"] == K18
        series = next(series for series in dataset["series"] if series["concept"] == "net_margin")
        first, _last = series["window_pp_provenance"]["inputs"]
        assert self._inputs(first["provenance"])["revenue"]["value"] == 6_710.8e6


@pytest.mark.parametrize("concept, shown, own, finding", [
    ("net_income", -5.0, 5.0, "opposite_sign"), ("net_income", 5.0, -5.0, "opposite_sign"),
    ("revenue", 5_000.0, 5.0, "scale"), ("revenue", 5.0, 5_000.0, "scale"), ("revenue", 5e9, 5.0, "scale"),
    ("revenue", 5e12, 5.0, None), ("revenue", -5_000.0, 5.0, None), ("revenue", 4_999.5, 5.0, None),
    ("revenue", 0.0, 5.0, None), ("revenue", 5.0, 0.0, None), ("revenue", 5.5, 5.0, None),
    ("earnings_per_share", 2_010.0, 2.01, "scale"), ("earnings_per_share", 2.01, 2_010.0, "scale"),
    ("eps_diluted", 0.05, -0.05, None), ("net_income", 0.05, -0.05, "opposite_sign"),
])
def test_item_4_the_exact_findings(concept, shown, own, finding):
    assert disagreement(concept, shown, own) == finding


def test_a_finding_is_read_in_a_figures_own_evidence_and_its_inputs_at_any_depth():
    finding = {"first_reported": {"disagreement": "scale"}}
    nested = {"provenance": {"inputs": [{"provenance": {"inputs": [{"concept": "revenue"}, finding]}}]}}
    assert _has_finding(finding) and _has_finding(nested)
    assert not _has_finding({"first_reported": {"disagreement": None}, "provenance": {"inputs": [{}]}})
    assert not _has_finding(None)
