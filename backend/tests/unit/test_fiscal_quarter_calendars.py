"""Minimized live-cohort calendar shapes, with illustrative monetary values.

These tests exercise period identity and coverage, not independent issuer value
verification. TTM cash flows and 16/17-week fourth quarters occur in real filings.
"""

from datetime import date

import pytest

from app.services.facts_service import normalize_companyfacts


CFO = "NetCashProvidedByUsedInOperatingActivities"
REVENUE = "RevenueFromContractWithCustomerExcludingAssessedTax"


def _observation(value, start, end, fp, fy, filed, *, form="10-Q"):
    return {
        "val": value, "start": start, "end": end, "fp": fp, "fy": fy,
        "filed": filed, "form": form, "accn": f"{fy}-{fp}-{filed}",
    }


def _payload(**concepts):
    return {"facts": {"us-gaap": {
        tag: {"units": {"USD": observations}}
        for tag, observations in concepts.items()
    }}}


def _concept(facts, concept):
    return [fact for fact in facts if fact["concept"] == concept]


def test_amazon_style_ttm_cash_flows_do_not_replace_fiscal_year_windows():
    """A rolling annual-duration cash flow does not turn March into fiscal Q4."""
    quarters = [
        _observation(10, "2025-01-01", "2025-03-31", "Q1", 2025, "2025-05-02"),
        _observation(20, "2025-04-01", "2025-06-30", "Q2", 2025, "2025-08-01"),
        _observation(30, "2025-07-01", "2025-09-30", "Q3", 2025, "2025-10-31"),
        _observation(100, "2025-01-01", "2025-12-31", "FY", 2025, "2026-02-06", form="10-K"),
    ]
    rolling = [
        _observation(80, "2024-04-01", "2025-03-31", "Q1", 2025, "2025-05-02"),
        _observation(85, "2024-07-01", "2025-06-30", "Q2", 2025, "2025-08-01"),
        _observation(90, "2024-10-01", "2025-09-30", "Q3", 2025, "2025-10-31"),
    ]
    facts, metadata = normalize_companyfacts(1, _payload(**{REVENUE: quarters, CFO: quarters + rolling}))
    exclusions = metadata["calendar_exclusions"]
    assert len(exclusions) == 3
    assert {item["reason"] for item in exclusions} == {"rolling_duration_not_fiscal_year"}
    assert {item["period_end"] for item in exclusions} == {"2025-03-31", "2025-06-30", "2025-09-30"}
    assert all(item["concept"] == "operating_cash_flow" and item["accession"] for item in exclusions)
    for concept in ("revenue", "operating_cash_flow"):
        rows = _concept(facts, concept)
        assert {(fact["fiscal_year"], fact["fiscal_period"]) for fact in rows} == {
            (2025, period) for period in ("Q1", "Q2", "Q3", "Q4", "FY")
        }
        assert len(rows) == 5
        assert {fact["period_end"] for fact in rows if fact["fiscal_period"] == "FY"} == {date(2025, 12, 31)}
        assert {fact["fiscal_period"]: fact["value"] for fact in rows} == {
            "Q1": 10, "Q2": 20, "Q3": 30, "Q4": 40, "FY": 100,
        }


def test_ttm_without_annual_evidence_is_not_published_as_a_fiscal_year():
    facts, metadata = normalize_companyfacts(1, _payload(**{CFO: [
        _observation(10, "2025-01-01", "2025-03-31", "Q1", 2025, "2025-05-02"),
        _observation(80, "2024-04-01", "2025-03-31", "Q1", 2025, "2025-05-02"),
    ]}))
    rows = _concept(facts, "operating_cash_flow")
    assert [(fact["fiscal_year"], fact["fiscal_period"], fact["value"]) for fact in rows] == [(2025, "Q1", 10)]
    # Missing annual evidence can withhold a new value but must not authorize
    # quarantining a historical FY row without positive calendar evidence.
    assert metadata.get("calendar_exclusions", []) == []


@pytest.mark.parametrize("start,q1_end,q2_end,q3_end,end,year,quarter_days", [
    ("2024-12-29", "2025-03-22", "2025-06-14", "2025-09-06", "2025-12-27", 2025, 112),
    ("2024-09-02", "2024-11-24", "2025-02-16", "2025-05-11", "2025-08-31", 2025, 112),
    ("2022-08-29", "2022-11-20", "2023-02-12", "2023-05-07", "2023-09-03", 2023, 119),
])
def test_pepsico_and_costco_style_long_q4_preserves_exact_interval(
    start, q1_end, q2_end, q3_end, end, year, quarter_days,
):
    def filed_after(period_end):
        from datetime import timedelta
        return (date.fromisoformat(period_end) + timedelta(days=30)).isoformat()

    observations = [
        _observation(value, start, period_end, period, year, filed_after(period_end),
                     form="10-K" if period == "FY" else "10-Q")
        for value, period_end, period in [(10, q1_end, "Q1"), (30, q2_end, "Q2"), (60, q3_end, "Q3"), (100, end, "FY")]
    ]
    facts, _ = normalize_companyfacts(1, _payload(**{CFO: observations}))
    rows = {fact["fiscal_period"]: fact for fact in _concept(facts, "operating_cash_flow")}
    assert {period: rows[period]["value"] for period in ("Q1", "Q2", "Q3", "Q4")} == {
        "Q1": 10, "Q2": 20, "Q3": 30, "Q4": 40,
    }
    q4 = rows["Q4"]
    assert (q4["period_end"] - q4["period_start"]).days + 1 == quarter_days
    assert q4["fiscal_year"] == year
    assert q4["provenance"]["validation"] == "passed"
    assert q4["provenance"]["formula"] == "FY - YTD9"
    assert len(q4["provenance"]["inputs"]) == 2


def test_direct_sixteen_week_q4_is_reported_and_takes_precedence():
    observations = [
        _observation(60, "2024-09-02", "2025-05-11", "Q3", 2025, "2025-06-05"),
        _observation(100, "2024-09-02", "2025-08-31", "FY", 2025, "2025-10-08", form="10-K"),
        _observation(41, "2025-05-12", "2025-08-31", "FY", 2025, "2025-10-08", form="10-K"),
    ]
    facts, _ = normalize_companyfacts(1, _payload(**{REVENUE: observations}))
    q4 = next(fact for fact in _concept(facts, "revenue") if fact["fiscal_period"] == "Q4")
    assert q4["value"] == 41
    assert q4["source"] == "companyfacts"
    assert q4["provenance"]["method"] == "reported"


def test_in_progress_oracle_style_year_does_not_reuse_completed_year_q1():
    observations = [
        _observation(10, "2025-06-01", "2025-08-31", "Q1", 2026, "2025-09-11"),
        _observation(100, "2025-06-01", "2026-05-31", "FY", 2026, "2026-06-22", form="10-K"),
        # The original SEC fy hint itself conflicts with the completed FY window.
        _observation(20, "2026-06-01", "2026-08-31", "Q1", 2026, "2026-09-11"),
    ]
    facts, _ = normalize_companyfacts(1, _payload(**{REVENUE: observations}))
    quarters = [fact for fact in _concept(facts, "revenue") if fact["fiscal_period"] == "Q1"]
    assert {(fact["fiscal_year"], fact["period_end"], fact["value"]) for fact in quarters} == {
        (2026, date(2025, 8, 31), 10), (2027, date(2026, 8, 31), 20),
    }


def test_johnson_johnson_style_january_first_year_end_keeps_issuer_fiscal_year():
    """A 52-week year ending January 1 belongs to the issuer's preceding FY."""
    observations = [
        _observation(10, "2022-01-03", "2022-04-03", "Q1", 2022, "2022-05-04"),
        _observation(100, "2022-01-03", "2023-01-01", "FY", 2022, "2023-02-16", form="10-K"),
        _observation(20, "2023-01-02", "2023-04-02", "Q1", 2023, "2023-05-04"),
        _observation(200, "2023-01-02", "2023-12-31", "FY", 2023, "2024-02-16", form="10-K"),
    ]
    facts, _ = normalize_companyfacts(1, _payload(**{REVENUE: observations}))
    rows = _concept(facts, "revenue")
    assert {(fact["fiscal_year"], fact["fiscal_period"], fact["value"]) for fact in rows} == {
        (2022, "Q1", 10), (2022, "FY", 100), (2023, "Q1", 20), (2023, "FY", 200),
    }
    assert len(rows) == 4


def test_salesforce_style_conflicting_annual_hint_cannot_merge_consecutive_years():
    observations = [
        _observation(90, "2023-02-01", "2024-01-31", "FY", 2024, "2024-03-06", form="10-K"),
        _observation(10, "2024-02-01", "2024-04-30", "Q1", 2025, "2024-05-30"),
        _observation(100, "2024-02-01", "2025-01-31", "FY", 2025, "2025-03-05", form="10-K"),
        _observation(20, "2025-02-01", "2025-04-30", "Q1", 2026, "2025-05-30"),
        # A timely original filing still carries a contradictory SEC fy hint.
        _observation(200, "2025-02-01", "2026-01-31", "FY", 2025, "2026-03-02", form="10-K"),
    ]
    facts, _ = normalize_companyfacts(1, _payload(**{REVENUE: observations}))
    rows = _concept(facts, "revenue")
    assert {(fact["fiscal_year"], fact["fiscal_period"], fact["value"]) for fact in rows} == {
        (2024, "FY", 90), (2025, "Q1", 10), (2025, "FY", 100),
        (2026, "Q1", 20), (2026, "FY", 200),
    }
    assert len(rows) == 5
