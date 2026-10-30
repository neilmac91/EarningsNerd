"""The analysis dataset reads each year's own annual report's value as evidence (MPA WP5a-B).

``trend_analysis/first_reports.py`` reads the company's non-current fiscal-year rows once per annual dataset and gives
a reported figure whose own report gave another value the ``first_reported`` the page decodes
(``frontend/features/analysis/lib/laterFilings.ts``). The rows are WP5b's (#1682), built here through its real writer
on its REGN shape (``test_companyfacts_own_report_history.py``): REGN's FY2018 10-K gives FY2018 revenue 6,710.8M, its
FY2020 10-K a narrower 5,145.6M under the same tag (docs/mpa-improvements/coherence.md section 1.6). The own report is
ingest's (``facts/own_reports._own_report``) replayed on stored rows; ``TestOneOwnReport`` holds the two to one answer.
"""
import uuid
from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import event

from app.services import facts_service as svc
from app.services.trend_analysis.first_reports import BASIS_INPUTS, _CALCULATED, differs, own_period_ends
from app.services.trend_analysis.source_documents import FilingDates
from app.utils.sec_urls import build_sec_archive_url
from tests.unit.test_companyfacts_own_report_history import (
    K18, K19, K20, _K, _NET_INCOME, _REVENUE, _history, _items, _payload, _shapes,
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


class TestOneOwnReport:
    """Ingest's own report and the reader's are one rule (CLAUDE.md rule 12): over WP5b's own-report shapes, each
    turning on one of its rules, the row the dataset reads as a year's own report is the history row the sync
    stored for it, wherever the two differ past D1's tolerance."""

    @pytest.mark.requires_db
    @pytest.mark.parametrize("shape", list(_shapes()))
    def test_the_reader_picks_the_history_row_ingest_stores(self, db, shape):
        payload = _shapes()[shape]
        facts, meta = svc.normalize_companyfacts(1, payload)
        winners = {(fact["concept"], fact["fiscal_year"]): fact["value"] for fact in facts if fact["fiscal_period"] == "FY"}
        stored = {key: (value, accession) for key, (value, accession) in _history(meta).items()
                  if differs(winners[key], value)}
        company = _synced(db, payload)
        picked = {(concept, int(period[2:])): (first["value"], first["accession"])
                  for (concept, period), first in _evidence(_build(db, company, "FY2015", "FY2021")).items()}
        assert picked == stored
        assert ("total_assets", 2018) in stored and (("revenue", 2018) in stored) is (shape != "another-span")

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

    def test_d3_eps_keeps_its_evidence_and_its_growth_across_a_split(self, db):
        # A 10-for-1 split before the FY2020 10-K: it restates FY2018 and FY2019 at a tenth.
        eps = {2017: {2015: 5.0, 2016: 6.0, 2017: 10.0}, 2018: {2016: 6.0, 2017: 10.0, 2018: 12.0},
               2019: {2017: 10.0, 2018: 12.0, 2019: 13.0}, 2020: {2018: 1.2, 2019: 1.3, 2020: 1.5},
               2021: {2019: 1.3, 2020: 1.5, 2021: 2.0}}
        dataset = _build(db, _synced(db, _payload(tags={"EarningsPerShareBasic": {"units": {"USD/shares": _items(eps)}}})))
        evidence = _evidence(dataset)
        assert (evidence[("earnings_per_share", "FY2018")]["value"], evidence[("earnings_per_share", "FY2019")]["value"]) \
            == (12.0, 13.0)
        assert all(isinstance(value, float) and first == "absent"
                   for period, (value, first) in _yoy(dataset, "earnings_per_share").items() if period != "FY2017")

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

    def test_the_catalogue_leaves_out_growth_across_a_change_of_basis(self, db):
        from app.services.trend_analysis.observations import build_observation_catalogue

        catalogue = build_observation_catalogue(_build(db, _synced(db, _payload())))
        growth = [item for item in catalogue if item.markdown.startswith("Revenue growth in")]
        assert [(item.markdown.split()[3], item.required) for item in growth] == [("FY2021", True)]


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
