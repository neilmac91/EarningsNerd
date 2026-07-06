"""Unit tests for the Multi-Period Analysis deterministic engine (M2).

Pure pieces (period keys, growth/CAGR math, inflection detectors, prompt rendering) are tested
without a DB; dataset assembly and coverage run against seeded ``financial_fact`` rows.
"""

import uuid
from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.dependencies import require_entitlement
from app.services import trend_analysis_service as svc


class TestPeriodKeys:
    def test_parse_annual(self):
        assert svc.parse_period_key("annual", "FY2024") == (2024, None)

    def test_parse_quarterly(self):
        assert svc.parse_period_key("quarterly", "2024Q2") == (2024, "Q2")

    @pytest.mark.parametrize("mode,key", [
        ("annual", "2024"), ("annual", "2024Q2"), ("annual", ""),
        ("quarterly", "FY2024"), ("quarterly", "2024Q5"), ("quarterly", None),
    ])
    def test_parse_rejects_bad_keys(self, mode, key):
        with pytest.raises(ValueError):
            svc.parse_period_key(mode, key)


class TestMath:
    def test_growth_edges(self):
        assert svc._growth(110.0, 100.0) == pytest.approx(0.10)
        assert svc._growth(-50.0, -100.0) == pytest.approx(0.5)  # loss narrowing = positive
        assert svc._growth(100.0, 0.0) is None
        assert svc._growth(100.0, None) is None
        assert svc._growth(None, 100.0) is None

    def test_growth_sign_flip_is_not_meaningful(self):
        # +$503M -> -$71.9B: a swing through zero renders as "-14,399.2%" under plain division —
        # finance convention calls this "n/m" rather than a real up/down move.
        assert svc._growth(-71_925_000_000.0, 503_000_000.0) == svc.NOT_MEANINGFUL
        assert svc._growth(50.0, -10.0) == svc.NOT_MEANINGFUL
        # current == 0 with a nonzero prior is a real (if extreme) move, not a sign flip: a full
        # decline to zero is -100%, a loss narrowing to breakeven is +100%.
        assert svc._growth(0.0, 100.0) == pytest.approx(-1.0)
        assert svc._growth(0.0, -100.0) == pytest.approx(1.0)
        # Same-sign moves of ANY magnitude off a small base stay real growth (not "nm") — only
        # an actual sign crossing is guarded.
        assert svc._growth(31.0, 10.0) == pytest.approx(2.1)

    def test_pp_delta_never_explodes_and_needs_no_nm_guard(self):
        assert svc._pp_delta(38.3, 47.3) == pytest.approx(-9.0)
        assert svc._pp_delta(47.3, 38.3) == pytest.approx(9.0)
        assert svc._pp_delta(100.0, None) is None
        assert svc._pp_delta(None, 100.0) is None

    def test_fmt_growth(self):
        assert svc._fmt_growth(svc.NOT_MEANINGFUL, False) == "n/m"
        assert svc._fmt_growth(svc.NOT_MEANINGFUL, True) == "n/m"
        assert svc._fmt_growth(-9.0, True) == "-9.0pp"  # percent series: no ×100
        assert svc._fmt_growth(4.97, True) == "+5.0pp"
        assert svc._fmt_growth(0.183, False) == "+18.3%"  # everything else: relative, ×100

    def test_cagr_edges(self):
        assert svc._cagr(100.0, 200.0, 5) == pytest.approx(2 ** 0.2 - 1)
        assert svc._cagr(-100.0, 200.0, 5) is None  # negative endpoint → undefined
        assert svc._cagr(100.0, -200.0, 5) is None
        assert svc._cagr(100.0, 200.0, 0) is None


def _point(period, value, marker, *, yoy=None, qoq=None):
    return {"period": period, "value": value, "marker": marker, "yoy": yoy, "qoq": qoq}


def _dataset(series):
    return {"series": series}


class TestInflectionDetectors:
    def test_growth_deceleration_fires_on_three_declining_yoy(self):
        ds = _dataset([{
            "concept": "revenue", "unit": "USD", "percent": False,
            "points": [
                _point("FY2021", 100, "F1"),
                _point("FY2022", 130, "F2", yoy=0.30),
                _point("FY2023", 150, "F3", yoy=0.15),
                _point("FY2024", 157, "F4", yoy=0.05),
            ],
        }])
        flags = svc.detect_growth_deceleration(ds)
        assert len(flags) == 1
        assert flags[0]["kind"] == "growth_deceleration"
        assert flags[0]["markers"] == ["F2", "F3", "F4"]

    def test_growth_deceleration_quiet_when_growth_reaccelerates(self):
        ds = _dataset([{
            "concept": "revenue", "unit": "USD", "percent": False,
            "points": [
                _point("FY2022", 130, "F1", yoy=0.30),
                _point("FY2023", 140, "F2", yoy=0.08),
                _point("FY2024", 170, "F3", yoy=0.21),
            ],
        }])
        assert svc.detect_growth_deceleration(ds) == []

    def test_margin_compression_needs_two_pp_drop(self):
        base = {"concept": "operating_margin", "unit": "pure", "percent": True}
        compressed = _dataset([{**base, "points": [
            _point("FY2022", 30.0, "F1"), _point("FY2023", 28.0, "F2"),
            _point("FY2024", 25.0, "F3"),
        ]}])
        assert svc.detect_margin_compression(compressed)[0]["kind"] == "margin_compression"

        shallow = _dataset([{**base, "points": [
            _point("FY2022", 30.0, "F1"), _point("FY2023", 29.5, "F2"),
            _point("FY2024", 29.0, "F3"),
        ]}])
        assert svc.detect_margin_compression(shallow) == []

    def test_fcf_divergence(self):
        ds = _dataset([
            {"concept": "net_income", "unit": "USD", "percent": False, "points": [
                _point("FY2021", 100, "F1"), _point("FY2022", 110, "F2"),
                _point("FY2023", 120, "F3"), _point("FY2024", 130, "F4"),
            ]},
            {"concept": "free_cash_flow", "unit": "USD", "percent": False, "points": [
                _point("FY2021", 95, "F5"), _point("FY2022", 105, "F6"),
                _point("FY2023", 115, "F7"), _point("FY2024", 40, "F8"),  # collapse
            ]},
        ])
        flags = svc.detect_fcf_ni_divergence(ds)
        assert len(flags) == 1
        assert set(flags[0]["markers"]) == {"F8", "F4"}

    def test_debt_build_and_liquidity(self):
        ds = _dataset([
            {"concept": "long_term_debt", "unit": "USD", "percent": False, "points": [
                _point("FY2020", 100, "F1"), _point("FY2024", 180, "F2"),
            ]},
            {"concept": "current_ratio", "unit": "pure", "percent": False, "points": [
                _point("FY2020", 1.8, "F3"), _point("FY2024", 0.9, "F4"),
            ]},
        ])
        assert svc.detect_debt_build(ds)[0]["kind"] == "debt_build"
        liquidity = svc.detect_liquidity_squeeze(ds)
        assert liquidity[0]["kind"] == "liquidity_squeeze"
        assert "below 1.0" in liquidity[0]["detail"]


class TestEntitlementGate:
    def test_free_user_blocked(self):
        dep = require_entitlement("can_analyze_trends", "Multi-Period Analysis")
        with pytest.raises(HTTPException) as exc:
            dep(current_user=SimpleNamespace(is_pro=False, subscription=None))
        assert exc.value.status_code == 403
        assert "Multi-Period Analysis" in exc.value.detail

    def test_pro_user_allowed(self):
        dep = require_entitlement("can_analyze_trends", "Multi-Period Analysis")
        pro = SimpleNamespace(is_pro=True, subscription=None)
        assert dep(current_user=pro) is pro


@pytest.fixture(scope="module", autouse=True)
def _tables():
    from app.database import engine
    from app.models import Base

    Base.metadata.create_all(bind=engine)
    yield


def _seed_company(db):
    from app.models import Company

    suffix = uuid.uuid4().hex[:8]
    company = Company(cik=suffix, ticker=("A" + suffix[:4]).upper(), name=f"Analysis Co {suffix}")
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


def _seed_fact(db, company_id, concept, value, *, fy, fp, end, unit="USD", start=None,
               source="companyfacts", reconciled=True, accession=None, is_latest=True):
    from app.models import FinancialFact

    db.add(FinancialFact(
        company_id=company_id, filing_id=None, concept=concept, raw_tag=f"us-gaap:{concept}",
        unit=unit, period_start=start, period_end=end, fiscal_year=fy, fiscal_period=fp,
        value=value, form="10-K", accession=accession or f"A-{uuid.uuid4().hex[:10]}",
        source=source, reconciled=reconciled, is_latest=is_latest,
    ))


def _seed_annual_history(db, cid):
    for fy, revenue, net_income, assets in [
        (2021, 1000.0, 100.0, 5000.0),
        (2022, 1200.0, 130.0, 5500.0),
        (2023, 1500.0, 180.0, 6000.0),
    ]:
        end = date(fy, 12, 31)
        _seed_fact(db, cid, "revenue", revenue, fy=fy, fp="FY", end=end, start=date(fy, 1, 1))
        _seed_fact(db, cid, "net_income", net_income, fy=fy, fp="FY", end=end, start=date(fy, 1, 1))
        _seed_fact(db, cid, "total_assets", assets, fy=fy, fp="FY", end=end)
    db.commit()


@pytest.mark.requires_db
class TestAvailablePeriods:
    def test_coverage_shape(self):
        from app.database import SessionLocal

        db = SessionLocal()
        company = _seed_company(db)
        _seed_annual_history(db, company.id)
        _seed_fact(db, company.id, "revenue", 400.0, fy=2023, fp="Q2",
                   end=date(2023, 6, 30), start=date(2023, 4, 1), source="companyfacts")
        _seed_fact(db, company.id, "revenue", 380.0, fy=2023, fp="Q4",
                   end=date(2023, 12, 31), start=date(2023, 10, 1), source="derived",
                   reconciled=False)
        # A legacy NULL-fiscal_period row must never surface.
        _seed_fact(db, company.id, "revenue", 999.0, fy=2023, fp=None,
                   end=date(2023, 3, 31), start=date(2023, 1, 1), source="edgar_xbrl")
        db.commit()

        coverage = svc.available_periods(db, company.id)
        assert [entry["key"] for entry in coverage["annual"]] == ["FY2021", "FY2022", "FY2023"]
        assert all(entry["has_core"] for entry in coverage["annual"])
        assert [entry["key"] for entry in coverage["quarterly"]] == ["2023Q2", "2023Q4"]
        derived_by_key = {entry["key"]: entry["derived"] for entry in coverage["quarterly"]}
        assert derived_by_key == {"2023Q2": False, "2023Q4": True}
        db.close()

    def test_has_core_false_without_top_line(self):
        from app.database import SessionLocal

        db = SessionLocal()
        company = _seed_company(db)
        _seed_fact(db, company.id, "total_assets", 5000.0, fy=2023, fp="FY",
                   end=date(2023, 12, 31))
        db.commit()
        coverage = svc.available_periods(db, company.id)
        assert coverage["annual"][0]["has_core"] is False
        db.close()


@pytest.mark.requires_db
class TestBuildDataset:
    def test_annual_grid_yoy_cagr_and_markers(self):
        from app.database import SessionLocal

        db = SessionLocal()
        company = _seed_company(db)
        _seed_annual_history(db, company.id)
        dataset = svc.build_dataset(db, company, "annual", "FY2021", "FY2023")

        assert dataset["period_key"] == "FY2021..FY2023"
        assert [p["key"] for p in dataset["periods"]] == ["FY2021", "FY2022", "FY2023"]

        by_concept = {series["concept"]: series for series in dataset["series"]}
        revenue = by_concept["revenue"]
        assert [p["value"] for p in revenue["points"]] == [1000.0, 1200.0, 1500.0]
        assert revenue["points"][1]["yoy"] == pytest.approx(0.20)
        assert revenue["points"][0].get("yoy") is None  # no prior in range
        assert revenue["cagr"] == pytest.approx((1500.0 / 1000.0) ** 0.5 - 1)
        assert by_concept["total_assets"]["points"][2]["value"] == 6000.0

        markers = [p["marker"] for s in dataset["series"] for p in s["points"] if p["value"] is not None]
        assert markers == [f"F{i}" for i in range(1, len(markers) + 1)]  # stable + sequential
        db.close()

    def test_quarterly_instants_match_by_period_end(self):
        from app.database import SessionLocal

        db = SessionLocal()
        company = _seed_company(db)
        for fy, fp, end, start, value in [
            (2023, "Q2", date(2023, 6, 30), date(2023, 4, 1), 300.0),
            (2023, "Q3", date(2023, 9, 30), date(2023, 7, 1), 310.0),
            (2023, "Q4", date(2023, 12, 31), date(2023, 10, 1), 330.0),
            (2024, "Q2", date(2024, 6, 30), date(2024, 4, 1), 360.0),
        ]:
            _seed_fact(db, company.id, "revenue", value, fy=fy, fp=fp, end=end, start=start)
        # The Q4 balance sheet is stored ONCE as the FY-end instant (D2c).
        _seed_fact(db, company.id, "total_assets", 6000.0, fy=2023, fp="FY", end=date(2023, 12, 31))
        db.commit()

        dataset = svc.build_dataset(db, company, "quarterly", "2023Q2", "2024Q2")
        assert [p["key"] for p in dataset["periods"]] == ["2023Q2", "2023Q3", "2023Q4", "2024Q2"]
        by_concept = {series["concept"]: series for series in dataset["series"]}

        assets = {p["period"]: p["value"] for p in by_concept["total_assets"]["points"]}
        assert assets["2023Q4"] == 6000.0  # FY-labelled instant surfaced in the Q4 column
        assert assets["2023Q2"] is None

        revenue = {p["period"]: p for p in by_concept["revenue"]["points"]}
        assert revenue["2024Q2"]["yoy"] == pytest.approx((360.0 - 300.0) / 300.0)  # same Q, prior FY
        assert revenue["2023Q3"]["qoq"] == pytest.approx((310.0 - 300.0) / 300.0)
        assert by_concept["revenue"]["cagr"] is None  # CAGR is annual-mode only
        db.close()

    def test_percent_series_yoy_qoq_are_pp_deltas_not_relative(self):
        from app.database import SessionLocal

        db = SessionLocal()
        company = _seed_company(db)
        for fy, fp, end, start, value in [
            (2023, "Q3", date(2023, 9, 30), date(2023, 7, 1), 47.3),
            (2023, "Q4", date(2023, 12, 31), date(2023, 10, 1), 38.3),
        ]:
            _seed_fact(db, company.id, "net_margin", value, fy=fy, fp=fp, end=end, start=start,
                       unit="pure")
        db.commit()

        dataset = svc.build_dataset(db, company, "quarterly", "2023Q3", "2023Q4")
        margin = {p["period"]: p for p in
                  next(s for s in dataset["series"] if s["concept"] == "net_margin")["points"]}
        # 47.3% -> 38.3% is a -9.0pp move, never the relative "-19.0%".
        assert margin["2023Q4"]["qoq"] == pytest.approx(-9.0)
        db.close()

    def test_sign_flip_growth_renders_nm_at_dataset_level(self):
        from app.database import SessionLocal

        db = SessionLocal()
        company = _seed_company(db)
        for fy, fp, end, start, value in [
            (2023, "Q3", date(2023, 9, 30), date(2023, 7, 1), 503_000_000.0),
            (2023, "Q4", date(2023, 12, 31), date(2023, 10, 1), -71_925_000_000.0),
        ]:
            _seed_fact(db, company.id, "investing_cash_flow", value, fy=fy, fp=fp, end=end,
                       start=start)
        db.commit()

        dataset = svc.build_dataset(db, company, "quarterly", "2023Q3", "2023Q4")
        icf = {p["period"]: p for p in
               next(s for s in dataset["series"] if s["concept"] == "investing_cash_flow")["points"]}
        assert icf["2023Q4"]["qoq"] == svc.NOT_MEANINGFUL
        db.close()

    def test_mixed_q4_column_badges_only_the_derivation_chain(self):
        """Review finding: a filer with a DISCRETE Q4 row (pre-2021 Item 302 tagging) plus a
        derived Q4 EPS in the same column — the estimate must carry the † badge even though the
        column isn't fully derived, and the real row must not."""
        from app.database import SessionLocal

        db = SessionLocal()
        company = _seed_company(db)
        for fp, end, start in [("Q1", date(2024, 3, 31), date(2024, 1, 1)),
                               ("Q2", date(2024, 6, 30), date(2024, 4, 1)),
                               ("Q3", date(2024, 9, 30), date(2024, 7, 1))]:
            _seed_fact(db, company.id, "revenue", 300.0, fy=2024, fp=fp, end=end, start=start)
        # Discrete, REAL Q4 revenue (companyfacts, reconciled).
        _seed_fact(db, company.id, "revenue", 320.0, fy=2024, fp="Q4",
                   end=date(2024, 12, 31), start=date(2024, 10, 1))
        # Derived (shares-based) Q4 EPS — the estimate.
        _seed_fact(db, company.id, "eps_diluted", 1.01, fy=2024, fp="Q4",
                   end=date(2024, 12, 31), start=date(2024, 10, 1), unit="USD/shares",
                   source="derived", reconciled=False)
        db.commit()

        dataset = svc.build_dataset(db, company, "quarterly", "2024Q1", "2024Q4")
        by_concept = {s["concept"]: s for s in dataset["series"]}
        revenue_q4 = next(p for p in by_concept["revenue"]["points"] if p["period"] == "2024Q4")
        eps_q4 = next(p for p in by_concept["eps_diluted"]["points"] if p["period"] == "2024Q4")
        assert revenue_q4["derived"] is False  # real reported value — never badged
        assert eps_q4["derived"] is True  # shares-based estimate — always badged
        db.close()

    def test_series_tone_is_shipped_from_the_dataset(self):
        """The display valence (inverted for debt, neutral for capex/investing/financing swings)
        ships on each series as `tone` — like `percent`, the dataset is the single source of
        truth so the frontend never hardcodes concept lists."""
        from app.database import SessionLocal

        db = SessionLocal()
        company = _seed_company(db)
        for fy, revenue, debt, capex in [(2022, 1000.0, 500.0, 50.0), (2023, 1200.0, 800.0, 90.0)]:
            end = date(fy, 12, 31)
            _seed_fact(db, company.id, "revenue", revenue, fy=fy, fp="FY", end=end,
                       start=date(fy, 1, 1))
            _seed_fact(db, company.id, "capital_expenditures", capex, fy=fy, fp="FY", end=end,
                       start=date(fy, 1, 1))
            _seed_fact(db, company.id, "long_term_debt", debt, fy=fy, fp="FY", end=end)
        db.commit()

        dataset = svc.build_dataset(db, company, "annual", "FY2022", "FY2023")
        tones = {s["concept"]: s["tone"] for s in dataset["series"]}
        assert tones["revenue"] == "normal"
        assert tones["long_term_debt"] == "inverted"
        assert tones["capital_expenditures"] == "neutral"
        db.close()

    def test_window_pp_is_the_cagr_counterpart_for_percent_series(self):
        """Annual mode, percent-unit series: CAGR is always null (unit == "pure" excludes it),
        so the KPI strip needs a window pp change instead (F1 fix)."""
        from app.database import SessionLocal

        db = SessionLocal()
        company = _seed_company(db)
        for fy, value in [(2021, 22.5), (2022, 30.0), (2023, 36.1)]:
            _seed_fact(db, company.id, "net_margin", value, fy=fy, fp="FY",
                       end=date(fy, 12, 31), start=date(fy, 1, 1), unit="pure")
        db.commit()

        dataset = svc.build_dataset(db, company, "annual", "FY2021", "FY2023")
        margin = next(s for s in dataset["series"] if s["concept"] == "net_margin")
        assert margin["cagr"] is None  # unit == "pure" — CAGR never applies
        assert margin["window_pp"] == pytest.approx(36.1 - 22.5)
        assert margin["window_pp_range"] == "FY2021..FY2023"
        db.close()

    def test_range_and_mode_validation(self):
        from app.database import SessionLocal
        from app.config import settings

        db = SessionLocal()
        company = _seed_company(db)
        _seed_annual_history(db, company.id)

        with pytest.raises(ValueError):
            svc.build_dataset(db, company, "weekly", "FY2021", "FY2023")
        with pytest.raises(ValueError):
            svc.build_dataset(db, company, "annual", "FY2016", "FY2017")  # no data in range

        # Over-cap range: seed more years than the cap allows.
        for fy in range(2005, 2021):
            _seed_fact(db, company.id, "revenue", 100.0 + fy, fy=fy, fp="FY",
                       end=date(fy, 12, 31), start=date(fy, 1, 1))
        db.commit()
        span = settings.ANALYSIS_MAX_ANNUAL_PERIODS
        with pytest.raises(ValueError, match="Too many periods"):
            svc.build_dataset(db, company, "annual", "FY2005", "FY2023")
        assert span >= 2  # sanity: the cap itself stays usable
        db.close()

    def test_derived_flag_marks_only_computed_q4(self):
        """The dataset's `derived` flag (→ "— derived Q4" / † / [derived]) is source=="derived"
        AND fiscal_period=="Q4" — a computed metric on a real quarter or an FY row must never
        carry it (audit finding A1)."""
        from app.database import SessionLocal

        db = SessionLocal()
        company = _seed_company(db)
        # Real quarters Q1-Q3 + a derived Q4 flow, plus computed metrics stamped source="derived"
        # on a REAL quarter (Q2) — exactly what derive_same_period_metrics produces.
        for fp, end, start, value in [
            ("Q1", date(2023, 3, 31), date(2023, 1, 1), 100.0),
            ("Q2", date(2023, 6, 30), date(2023, 4, 1), 110.0),
            ("Q3", date(2023, 9, 30), date(2023, 7, 1), 120.0),
        ]:
            _seed_fact(db, company.id, "revenue", value, fy=2023, fp=fp, end=end, start=start)
        _seed_fact(db, company.id, "revenue", 130.0, fy=2023, fp="Q4",
                   end=date(2023, 12, 31), start=date(2023, 10, 1),
                   source="derived", reconciled=False)
        _seed_fact(db, company.id, "net_margin", 12.5, fy=2023, fp="Q2",
                   end=date(2023, 6, 30), start=date(2023, 4, 1), unit="pure",
                   source="derived", reconciled=True)
        db.commit()

        dataset = svc.build_dataset(db, company, "quarterly", "2023Q1", "2023Q4")
        by_concept = {series["concept"]: series for series in dataset["series"]}
        revenue = {p["period"]: p for p in by_concept["revenue"]["points"]}
        margin = {p["period"]: p for p in by_concept["net_margin"]["points"]}

        assert revenue["2023Q4"]["derived"] is True  # true FY − Q1..Q3 estimate
        assert revenue["2023Q2"]["derived"] is False
        assert margin["2023Q2"]["derived"] is False  # computed metric on a REAL quarter

        # And the Sources-list excerpt follows the flag: no "derived Q4" on the real quarter.
        index = svc.marker_index(dataset)
        excerpts = {index[m]["period"]: svc._point_citation(1, index[m])["excerpt"]
                    for m in index if index[m].get("kind") != "cagr"
                    and index[m]["concept"] == "net_margin"}
        assert "derived Q4" not in excerpts["2023Q2"]
        q4_excerpt = svc._point_citation(1, index[revenue["2023Q4"]["marker"]])["excerpt"]
        assert q4_excerpt.endswith("— derived Q4")
        db.close()

    def test_discrete_q4_filer_metrics_not_flagged(self):
        """A rare filer that REPORTS a discrete Q4 has companyfacts rows in the Q4 group, so the
        column is not a computed-Q4 column — metrics computed on it must not carry the flag."""
        from app.database import SessionLocal

        db = SessionLocal()
        company = _seed_company(db)
        for fp, end, start in [
            ("Q1", date(2023, 3, 31), date(2023, 1, 1)),
            ("Q2", date(2023, 6, 30), date(2023, 4, 1)),
            ("Q3", date(2023, 9, 30), date(2023, 7, 1)),
        ]:
            _seed_fact(db, company.id, "revenue", 100.0, fy=2023, fp=fp, end=end, start=start)
        # Discrete (reported) Q4 revenue + a computed metric stamped "derived" on that quarter.
        _seed_fact(db, company.id, "revenue", 130.0, fy=2023, fp="Q4",
                   end=date(2023, 12, 31), start=date(2023, 10, 1), source="companyfacts")
        _seed_fact(db, company.id, "net_margin", 12.5, fy=2023, fp="Q4",
                   end=date(2023, 12, 31), start=date(2023, 10, 1), unit="pure",
                   source="derived", reconciled=True)
        db.commit()

        dataset = svc.build_dataset(db, company, "quarterly", "2023Q1", "2023Q4")
        by_concept = {series["concept"]: series for series in dataset["series"]}
        revenue_q4 = next(p for p in by_concept["revenue"]["points"] if p["period"] == "2023Q4")
        margin_q4 = next(p for p in by_concept["net_margin"]["points"] if p["period"] == "2023Q4")
        assert revenue_q4["derived"] is False
        assert margin_q4["derived"] is False  # real Q4 → nothing on the column is an estimate
        db.close()

    def test_annual_computed_metric_never_flagged_derived_q4(self):
        from app.database import SessionLocal

        db = SessionLocal()
        company = _seed_company(db)
        _seed_annual_history(db, company.id)
        # Annual computed metric: derive_same_period_metrics stamps FY margins source="derived".
        _seed_fact(db, company.id, "net_margin", 10.0, fy=2023, fp="FY",
                   end=date(2023, 12, 31), start=date(2023, 1, 1), unit="pure",
                   source="derived", reconciled=True)
        db.commit()

        dataset = svc.build_dataset(db, company, "annual", "FY2021", "FY2023")
        margin = next(s for s in dataset["series"] if s["concept"] == "net_margin")
        point = next(p for p in margin["points"] if p["value"] is not None)
        assert point["derived"] is False
        excerpt = svc._point_citation(1, {**point, "label": margin["label"],
                                          "unit": margin["unit"], "percent": margin["percent"],
                                          "concept": "net_margin"})["excerpt"]
        assert "derived" not in excerpt
        db.close()

    def test_cagr_markers_follow_point_markers_and_resolve(self):
        from app.database import SessionLocal

        db = SessionLocal()
        company = _seed_company(db)
        _seed_annual_history(db, company.id)
        dataset = svc.build_dataset(db, company, "annual", "FY2021", "FY2023")

        point_markers = [p["marker"] for s in dataset["series"] for p in s["points"]
                         if p["value"] is not None]
        cagr_markers = [s["cagr_marker"] for s in dataset["series"] if s.get("cagr_marker")]
        # Every series with a CAGR carries a marker; numbering continues after the point markers
        # so point numbering is unchanged by the feature.
        assert cagr_markers, "expected at least one CAGR marker"
        all_markers = point_markers + cagr_markers
        assert all_markers == [f"F{i}" for i in range(1, len(all_markers) + 1)]

        index = svc.marker_index(dataset)
        cagr_entry = index[cagr_markers[0]]
        assert cagr_entry["kind"] == "cagr"
        assert cagr_entry["period"] == dataset["period_key"]  # full-coverage series

        # The prompt header carries the marker next to the CAGR figure.
        text = svc.compact_dataset_for_prompt(dataset)
        assert f"[{cagr_markers[0]}] CAGR" in text
        db.close()

    def test_cagr_window_is_valued_endpoints_not_selected_range(self):
        """A series first reported mid-window computes CAGR over its VALUED endpoints; the
        citation and prompt must state that basis window, never the wider selected range."""
        from app.database import SessionLocal

        db = SessionLocal()
        company = _seed_company(db)
        _seed_annual_history(db, company.id)  # revenue/net_income FY2021-FY2023
        # A concept that only exists for the last two years of the window.
        for fy, value in [(2022, 50.0), (2023, 60.0)]:
            _seed_fact(db, company.id, "operating_cash_flow", value, fy=fy, fp="FY",
                       end=date(fy, 12, 31), start=date(fy, 1, 1))
        db.commit()

        dataset = svc.build_dataset(db, company, "annual", "FY2021", "FY2023")
        ocf = next(s for s in dataset["series"] if s["concept"] == "operating_cash_flow")
        assert ocf["cagr_window"] == "FY2022..FY2023"
        assert dataset["period_key"] == "FY2021..FY2023"

        index = svc.marker_index(dataset)
        entry = index[ocf["cagr_marker"]]
        assert entry["period"] == "FY2022..FY2023"
        citation = svc._point_citation(1, entry)
        assert "(FY2022..FY2023)" in citation["excerpt"]

        text = svc.compact_dataset_for_prompt(dataset)
        assert f"[{ocf['cagr_marker']}] CAGR" in text and "(FY2022..FY2023)" in text
        db.close()

    def test_dataset_flags_and_values_are_ingest_order_independent(self):
        """A2/D4 guard: the per-filing path (source="edgar_xbrl") and the companyfacts path
        (computed metrics source="derived") write the same concepts; whichever ran last, the
        dataset the user sees — values and derived flags — must be identical."""
        from app.database import SessionLocal
        from app.services import facts_service as fs

        def _facts(company_id):
            filing_row = {
                "company_id": company_id, "filing_id": None, "concept": "net_margin",
                "raw_tag": None, "unit": "pure", "period_start": date(2023, 1, 1),
                "period_end": date(2023, 12, 31), "fiscal_year": 2023, "fiscal_period": "FY",
                "value": 10.0, "form": "10-K", "accession": "ACC-10K", "source": "edgar_xbrl",
                "reconciled": False,
            }
            companyfacts_row = {**filing_row, "accession": "ACC-CF", "source": "derived",
                                "reconciled": True}
            base = {
                "company_id": company_id, "filing_id": None, "raw_tag": "us-gaap:Revenues",
                "unit": "USD", "period_start": date(2023, 1, 1),
                "period_end": date(2023, 12, 31), "fiscal_year": 2023, "fiscal_period": "FY",
                "form": "10-K", "accession": "ACC-CF", "source": "companyfacts",
                "reconciled": True,
            }
            core = [
                {**base, "concept": "revenue", "value": 100.0},
                {**base, "concept": "net_income", "value": 10.0},
            ]
            return core, filing_row, companyfacts_row

        def _dataset_for(order):
            db = SessionLocal()
            company = _seed_company(db)
            core, filing_row, cf_row = _facts(company.id)
            fs.upsert_facts(db, core, reconcile=False)
            for row in (filing_row, cf_row) if order == "filing_first" else (cf_row, filing_row):
                fs.upsert_facts(db, [dict(row)], reconcile=False)
            dataset = svc.build_dataset(db, company, "annual", "FY2023", "FY2023")
            db.close()
            return {
                (s["concept"], p["period"]): (p["value"], p["derived"])
                for s in dataset["series"] for p in s["points"] if p["value"] is not None
            }

        assert _dataset_for("filing_first") == _dataset_for("companyfacts_first")

    def test_fingerprint_changes_when_a_value_changes(self):
        from app.database import SessionLocal

        db = SessionLocal()
        company = _seed_company(db)
        _seed_annual_history(db, company.id)
        first = svc.build_dataset(db, company, "annual", "FY2021", "FY2023")
        fp_before = svc.dataset_fingerprint(first)
        assert fp_before == svc.dataset_fingerprint(first)  # deterministic

        # A restatement arrives: same period, new accession, new value.
        _seed_fact(db, company.id, "revenue", 1510.0, fy=2023, fp="FY",
                   end=date(2023, 12, 31), start=date(2023, 1, 1), accession="RESTATED")
        # Demote the old row so is_latest semantics hold (what upsert_facts_bulk does).
        from app.models import FinancialFact
        (db.query(FinancialFact)
           .filter_by(company_id=company.id, concept="revenue", fiscal_period="FY")
           .filter(FinancialFact.period_end == date(2023, 12, 31),
                   FinancialFact.accession != "RESTATED")
           .update({"is_latest": False}, synchronize_session=False))
        db.commit()

        second = svc.build_dataset(db, company, "annual", "FY2021", "FY2023")
        assert svc.dataset_fingerprint(second) != fp_before
        db.close()


class TestPromptRendering:
    def test_compact_rendering_carries_markers_and_signals(self):
        dataset = {
            "ticker": "TST", "company_name": "Test Co", "mode": "annual",
            "period_key": "FY2022..FY2024",
            "periods": [],
            "series": [{
                "concept": "revenue", "label": "Revenue", "unit": "USD", "percent": False,
                "cagr": 0.10,
                "points": [
                    {"period": "FY2022", "value": 1000.0, "marker": "F1"},
                    {"period": "FY2023", "value": 1200.0, "marker": "F2", "yoy": 0.20},
                    {"period": "FY2024", "value": None},
                ],
            }],
            "inflections": [{"kind": "debt_build", "detail": "Debt grew.", "markers": ["F9"]}],
        }
        text = svc.compact_dataset_for_prompt(dataset)
        assert "[F1] FY2022: 1,000" in text
        assert "YoY +20.0%" in text
        assert "CAGR +10.0%" in text
        assert "FY2024: not reported" in text
        assert "debt_build" in text and "[F9]" in text

    def test_signal_markers_render_one_per_bracket(self):
        """A comma-joined signal line ("[F1, F2, F3]") modeled the exact multi-reference form the
        resolver cannot parse — the prompt must only ever show separate single brackets."""
        dataset = {
            "ticker": "TST", "company_name": "Test Co", "mode": "quarterly",
            "period_key": "2025Q1..2025Q3", "periods": [],
            "series": [{
                "concept": "operating_margin", "label": "Operating margin", "unit": "pure",
                "percent": True, "cagr": None,
                "points": [{"period": "2025Q1", "value": 48.9, "marker": "F1"}],
            }],
            "inflections": [{
                "kind": "margin_compression", "detail": "Operating margin compressed 2.5pp.",
                "markers": ["F1", "F2", "F3"],
            }],
        }
        text = svc.compact_dataset_for_prompt(dataset)
        assert "[F1] [F2] [F3]" in text
        assert "[F1, F2" not in text

    def test_marker_index_resolves_points(self):
        dataset = {
            "series": [{
                "concept": "revenue", "label": "Revenue", "unit": "USD", "percent": False,
                "points": [{"period": "FY2023", "value": 1.0, "marker": "F1"}],
            }],
        }
        index = svc.marker_index(dataset)
        assert index["F1"]["concept"] == "revenue"
        assert index["F1"]["period"] == "FY2023"


@pytest.mark.requires_db
class TestAnalysisUsageCap:
    def test_check_and_increment_trio(self):
        from app.database import SessionLocal
        from app.models import User
        from app.services import subscription_service as subs

        db = SessionLocal()
        email = f"cap-{uuid.uuid4().hex[:8]}@example.com"
        user = User(email=email, hashed_password="x", is_pro=True)
        db.add(user)
        db.commit()
        db.refresh(user)

        month = subs.get_current_month()
        allowed, count, cap = subs.check_analysis_limit(user, db)
        assert (allowed, count) == (True, 0)

        subs.increment_user_analysis(user.id, month, db)
        subs.increment_user_analysis(user.id, month, db)
        assert subs.get_user_analysis_count(user.id, month, db) == 2

        allowed, count, _cap = subs.check_analysis_limit(user, db)
        assert (allowed, count) == (True, 2)
        db.close()
