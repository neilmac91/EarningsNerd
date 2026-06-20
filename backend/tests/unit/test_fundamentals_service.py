"""Unit tests for the SEC company-facts fundamentals timeline service."""

from types import SimpleNamespace

import httpx
import pytest

from app.services import fundamentals_service as fs
from app.services.fundamentals_service import (
    get_fundamentals_timeline,
    parse_company_facts,
)

# A trimmed company-facts payload exercising the tricky cases:
# - a live revenue concept plus a *retired* one (must not shadow the live one)
# - a Q4 stub duration inside the 10-K (must be excluded from the annual series)
# - a 10-Q row (non-annual, excluded)
# - instant balance-sheet facts (no `start`)
# - EPS reported under USD/shares
SAMPLE = {
    "cik": 320193,
    "entityName": "Apple Inc.",
    "facts": {
        "us-gaap": {
            "RevenueFromContractWithCustomerExcludingAssessedTax": {
                "units": {
                    "USD": [
                        {"fy": 2023, "fp": "FY", "form": "10-K", "start": "2022-09-25", "end": "2023-09-30", "val": 383285000000, "filed": "2023-11-03"},
                        {"fy": 2023, "fp": "FY", "form": "10-K", "start": "2023-07-02", "end": "2023-09-30", "val": 89498000000, "filed": "2023-11-03"},  # Q4 stub -> excluded
                        {"fy": 2022, "fp": "FY", "form": "10-K", "start": "2021-09-26", "end": "2022-09-24", "val": 394328000000, "filed": "2022-10-28"},
                        {"fy": 2022, "fp": "Q3", "form": "10-Q", "start": "2022-03-27", "end": "2022-06-25", "val": 82959000000, "filed": "2022-07-29"},  # 10-Q -> excluded
                    ]
                }
            },
            "Revenues": {  # retired tag, only an old year -> must not win over the live concept
                "units": {"USD": [
                    {"fy": 2018, "fp": "FY", "form": "10-K", "start": "2017-10-01", "end": "2018-09-29", "val": 265595000000, "filed": "2018-11-05"},
                ]}
            },
            "GrossProfit": {"units": {"USD": [
                {"fy": 2023, "fp": "FY", "form": "10-K", "start": "2022-09-25", "end": "2023-09-30", "val": 169148000000, "filed": "2023-11-03"},
            ]}},
            "NetIncomeLoss": {"units": {"USD": [
                {"fy": 2023, "fp": "FY", "form": "10-K", "start": "2022-09-25", "end": "2023-09-30", "val": 96995000000, "filed": "2023-11-03"},
                {"fy": 2022, "fp": "FY", "form": "10-K", "start": "2021-09-26", "end": "2022-09-24", "val": 99803000000, "filed": "2022-10-28"},
            ]}},
            "Assets": {"units": {"USD": [
                {"fy": 2023, "fp": "FY", "form": "10-K", "end": "2023-09-30", "val": 352583000000, "filed": "2023-11-03"},  # instant
                {"fy": 2022, "fp": "FY", "form": "10-K", "end": "2022-09-24", "val": 352755000000, "filed": "2022-10-28"},
            ]}},
            "EarningsPerShareDiluted": {"units": {"USD/shares": [
                {"fy": 2023, "fp": "FY", "form": "10-K", "start": "2022-09-25", "end": "2023-09-30", "val": 6.13, "filed": "2023-11-03"},
            ]}},
        }
    },
}


class TestParseCompanyFacts:
    def test_revenue_excludes_stub_and_non_annual_and_retired_tag(self):
        parsed = parse_company_facts(SAMPLE)
        revenue = parsed["revenue"]
        years = [fy for fy, _end, _val in revenue]
        assert years == [2023, 2022]  # descending, Q4 stub + 10-Q + 2018 retired tag excluded
        assert revenue[0] == (2023, "2023-09-30", 383285000000.0)
        assert 2018 not in years

    def test_instant_balance_sheet_facts(self):
        parsed = parse_company_facts(SAMPLE)
        assets = parsed["total_assets"]
        assert [fy for fy, _e, _v in assets] == [2023, 2022]
        assert assets[0][2] == 352583000000.0

    def test_eps_from_usd_shares(self):
        parsed = parse_company_facts(SAMPLE)
        assert parsed["eps_diluted"][0] == (2023, "2023-09-30", 6.13)

    def test_empty_or_malformed(self):
        assert parse_company_facts({}) == {}
        assert parse_company_facts(None) == {}
        assert parse_company_facts({"facts": {"us-gaap": "nope"}}) == {}


class TestBuildTimeline:
    def test_margins_are_year_aligned_percentages(self):
        parsed = parse_company_facts(SAMPLE)
        timeline = fs._build_timeline("aapl", "0000320193", "Apple Inc.", parsed)
        assert timeline.ticker == "AAPL"
        by_metric = {m.metric: m for m in timeline.metrics}

        # Gross margin FY2023 = 169148 / 383285 * 100 ≈ 44.13
        gm = by_metric["gross_margin"]
        assert gm.unit == "percent"
        gm_2023 = next(p for p in gm.points if p.fiscal_year == 2023)
        assert gm_2023.value == pytest.approx(44.13, abs=0.05)

        # Net margin exists for both years
        nm_years = {p.fiscal_year for p in by_metric["net_margin"].points}
        assert nm_years == {2023, 2022}

    def test_metrics_omit_empty_series(self):
        # operating_income/operating_cash_flow/shareholders_equity absent from SAMPLE
        timeline = fs._build_timeline("AAPL", "0000320193", "Apple Inc.", parse_company_facts(SAMPLE))
        present = {m.metric for m in timeline.metrics}
        assert "operating_income" not in present
        assert "revenue" in present and "net_income" in present


class TestGetFundamentalsTimeline:
    @pytest.mark.asyncio
    async def test_resolves_fetches_and_builds(self):
        fs._cache.clear()
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            captured["ua"] = request.headers.get("user-agent")
            return httpx.Response(200, json=SAMPLE)

        async def resolver(ticker):
            return SimpleNamespace(cik="0000320193", name="Apple Inc.")

        timeline = await get_fundamentals_timeline(
            "aapl", transport=httpx.MockTransport(handler), company_resolver=resolver
        )

        assert timeline.ticker == "AAPL"
        assert timeline.cik == "0000320193"
        assert timeline.company_name == "Apple Inc."
        assert "CIK0000320193.json" in captured["url"]
        assert captured["ua"]  # SEC-required descriptive User-Agent present
        metrics = {m.metric for m in timeline.metrics}
        assert {"revenue", "net_income", "total_assets", "gross_margin"} <= metrics

    @pytest.mark.asyncio
    async def test_uses_cache_on_second_call(self):
        fs._cache.clear()
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(200, json=SAMPLE)

        async def resolver(ticker):
            return SimpleNamespace(cik="0000320193", name="Apple Inc.")

        transport = httpx.MockTransport(handler)
        await get_fundamentals_timeline("AAPL", transport=transport, company_resolver=resolver)
        await get_fundamentals_timeline("AAPL", transport=transport, company_resolver=resolver)
        assert calls["n"] == 1  # company-facts fetched once; second call served from cache
