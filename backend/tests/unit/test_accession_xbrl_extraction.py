"""Unit tests for accession-aware XBRL extraction (issue #240).

The XBRL service previously extracted from Company.get_financials() — built
from the company's LATEST 10-K — regardless of which accession was requested,
so a 10-Q page could show annual figures. These tests pin the new behavior:

- the requested filing's own XBRL instance is the primary source, with
  explicit undimensioned/period-end/duration filters per form,
- the accession-aware companyfacts fallback outranks get_financials(),
- cache keys are versioned so stale wrong-period entries cannot be served.
"""

import pandas as pd
import pytest
from unittest.mock import AsyncMock, patch

from app.services.edgar import xbrl_service as xbrl_module
from app.services.edgar.instance_extractor import (
    DURATION_CONCEPTS,
    duration_in_window,
    duration_series,
    instant_series,
)
from app.services.edgar.xbrl_service import (
    EdgarXBRLService,
    _extract_from_filing_instance_sync,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fakes for the edgartools call chain:
#   xb.facts.query().by_concept("us-gaap:X", exact=True).to_dataframe()
#   company.get_filings(accession_number=...) -> [filing]; filing.xbrl() -> xb
# ---------------------------------------------------------------------------

def _facts_df(rows):
    """rows: (is_dimensioned, period_start, period_end, numeric_value)."""
    return pd.DataFrame(
        rows, columns=["is_dimensioned", "period_start", "period_end", "numeric_value"]
    )


def _facts_df_dec(rows):
    """rows: (is_dimensioned, period_start, period_end, numeric_value, decimals)."""
    return pd.DataFrame(
        rows,
        columns=["is_dimensioned", "period_start", "period_end", "numeric_value", "decimals"],
    )


class FakeQuery:
    def __init__(self, frames):
        self._frames = frames
        self._selected = pd.DataFrame()

    def by_concept(self, concept, exact=True):
        assert concept.startswith("us-gaap:")
        self._selected = self._frames.get(concept.split(":", 1)[1], pd.DataFrame())
        return self

    def to_dataframe(self):
        return self._selected


class FakeFacts:
    def __init__(self, frames):
        self._frames = frames

    def query(self):
        return FakeQuery(self._frames)


class FakeXBRL:
    def __init__(self, frames):
        self.facts = FakeFacts(frames)


class FakeFiling:
    def __init__(self, form="10-Q", period_of_report="2026-03-31", xb=None):
        self.form = form
        self.period_of_report = period_of_report
        self._xb = xb

    def xbrl(self):
        return self._xb


class FakeCompany:
    def __init__(self, filings):
        self._filings = filings

    def get_filings(self, accession_number=None, trigger_full_load=None):
        return list(self._filings)


@pytest.fixture(autouse=True)
def _clean_l1_cache():
    xbrl_module._xbrl_cache.clear()
    yield
    xbrl_module._xbrl_cache.clear()


# ---------------------------------------------------------------------------
# duration_in_window
# ---------------------------------------------------------------------------

def test_duration_window_edges():
    # 52/53-week fiscal years (364 and 371 days) are valid 10-K durations.
    assert duration_in_window("2025-01-01", "2025-12-31", "10-K")
    assert duration_in_window("2025-01-04", "2026-01-09", "10-K")
    # A ~9-month YTD slice is neither a fiscal year nor a quarter.
    assert not duration_in_window("2025-01-01", "2025-10-08", "10-K")
    assert not duration_in_window("2025-01-01", "2025-10-08", "10-Q")
    # Standard quarter.
    assert duration_in_window("2026-01-01", "2026-03-31", "10-Q")
    # Amendments normalize to the base form; unknown forms never match.
    assert duration_in_window("2025-01-01", "2025-12-31", "10-K/A")
    assert not duration_in_window("2025-01-01", "2025-12-31", "8-K")
    # Missing boundaries (instant facts) never satisfy a duration window.
    assert not duration_in_window(None, "2025-12-31", "10-K")
    assert not duration_in_window(float("nan"), "2025-12-31", "10-K")


# ---------------------------------------------------------------------------
# duration_series / instant_series
# ---------------------------------------------------------------------------

def test_10q_selects_quarter_not_ytd_and_keeps_yoy_comparative():
    xb = FakeXBRL({"Revenues": _facts_df([
        (False, "2026-01-01", "2026-03-31", 90_000.0),   # current quarter
        (False, "2025-07-01", "2026-03-31", 270_000.0),  # 9-month YTD, same end
        (False, "2025-01-01", "2025-03-31", 80_000.0),   # prior-year quarter
        (True,  "2026-01-01", "2026-03-31", 55_000.0),   # segment row
    ])})
    series = duration_series(xb, ["Revenues"], "10-Q", "2026-03-31")
    assert series == [("2026-03-31", 90_000.0), ("2025-03-31", 80_000.0)]


def test_10k_selects_full_year_not_q4():
    xb = FakeXBRL({"NetIncomeLoss": _facts_df([
        (False, "2025-10-01", "2025-12-31", 477.0),      # Q4, same end as FY
        (False, "2025-01-01", "2025-12-31", 7_153.0),    # FY
        (False, "2024-01-01", "2024-12-31", 6_000.0),    # prior FY comparative
    ])})
    series = duration_series(xb, ["NetIncomeLoss"], "10-K", "2025-12-31")
    assert series == [("2025-12-31", 7_153.0), ("2024-12-31", 6_000.0)]


def test_concept_without_target_period_fact_is_skipped():
    # Stale concept has only old facts; live concept anchors the target period.
    xb = FakeXBRL({
        "Revenues": _facts_df([(False, "2018-01-01", "2018-12-31", 1.0)]),
        "RevenueFromContractWithCustomerExcludingAssessedTax": _facts_df([
            (False, "2025-01-01", "2025-12-31", 416.0),
        ]),
    })
    series = duration_series(
        xb,
        ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax"],
        "10-K",
        "2025-12-31",
    )
    assert series == [("2025-12-31", 416.0)]


def test_ambiguous_values_for_target_period_fail_the_concept():
    # Two distinct consolidated values for the same period can't be trusted.
    xb = FakeXBRL({"Revenues": _facts_df([
        (False, "2025-01-01", "2025-12-31", 100.0),
        (False, "2025-01-01", "2025-12-31", 200.0),
    ])})
    assert duration_series(xb, ["Revenues"], "10-K", "2025-12-31") == []


def test_ambiguous_comparative_period_is_dropped_not_fatal():
    xb = FakeXBRL({"Revenues": _facts_df([
        (False, "2025-01-01", "2025-12-31", 300.0),
        (False, "2024-01-01", "2024-12-31", 100.0),
        (False, "2024-01-01", "2024-12-31", 150.0),  # restated twice — ambiguous
    ])})
    assert duration_series(xb, ["Revenues"], "10-K", "2025-12-31") == [
        ("2025-12-31", 300.0)
    ]


# ---------------------------------------------------------------------------
# Precision-aware disambiguation of undimensioned duplicates (ASML revenue gap)
# ---------------------------------------------------------------------------

def test_parse_decimals():
    from app.services.edgar.instance_extractor import _parse_decimals
    assert _parse_decimals("-5") == -5.0
    assert _parse_decimals("0") == 0.0
    assert _parse_decimals("INF") == float("inf")
    assert _parse_decimals(None) == float("-inf")   # missing → least precise
    assert _parse_decimals("garbage") == float("-inf")


def test_resolve_period_value_prefers_finest_precision_for_rounded_duplicate():
    # A filer tags the same line twice undimensioned: precise (-5) AND its rounding to -8.
    # They are the same figure → the precise value wins (order-independent), not "ambiguous".
    from app.services.edgar.instance_extractor import _resolve_period_value
    assert _resolve_period_value([(32_667_300_000.0, -5.0), (32_700_000_000.0, -8.0)]) == 32_667_300_000.0
    assert _resolve_period_value([(32_700_000_000.0, -8.0), (32_667_300_000.0, -5.0)]) == 32_667_300_000.0
    assert _resolve_period_value([(100.0, float("-inf"))]) == 100.0  # single value always resolves


def test_resolve_period_value_drops_genuine_conflict():
    # Values that are NOT a clean rounding of the finest one are a real conflict → None (dropped).
    from app.services.edgar.instance_extractor import _resolve_period_value
    assert _resolve_period_value([(32_667_300_000.0, -5.0), (30_000_000_000.0, -8.0)]) is None
    # Unknown precision (decimals missing → -inf) with distinct values stays conservative → None.
    assert _resolve_period_value([(100.0, float("-inf")), (200.0, float("-inf"))]) is None
    # Distinct values at the SAME finite precision are a real conflict (a coarse absolute tolerance
    # would have masked these — 100 vs 101 differ by exactly 1.0; 1.00 vs 1.01 are cents apart).
    assert _resolve_period_value([(100.0, 0.0), (101.0, 0.0)]) is None
    assert _resolve_period_value([(1.00, 2.0), (1.01, 2.0)]) is None


def test_duration_series_recovers_rounded_undimensioned_total():
    # End-to-end (the ASML FY2025 case): revenue tagged precise @ -5 and a rounded restatement @ -8
    # for the same period → the precise consolidated total is recovered instead of dropped.
    xb = FakeXBRL({"RevenueFromContractWithCustomerExcludingAssessedTax": _facts_df_dec([
        (False, "2025-01-01", "2025-12-31", 32_667_300_000.0, "-5"),
        (False, "2025-01-01", "2025-12-31", 32_700_000_000.0, "-8"),  # == round(32.6673B, -8)
        (True,  "2025-01-01", "2025-12-31", 8_193_000_000.0, "-5"),   # a segment row (excluded)
    ])})
    series = duration_series(
        xb, ["RevenueFromContractWithCustomerExcludingAssessedTax"], "10-K", "2025-12-31"
    )
    assert series == [("2025-12-31", 32_667_300_000.0)]


def test_duration_series_still_drops_truly_divergent_undimensioned_values():
    # Two undimensioned values that don't reconcile by precision → still dropped (no false pick).
    xb = FakeXBRL({"Revenues": _facts_df_dec([
        (False, "2025-01-01", "2025-12-31", 32_667_300_000.0, "-5"),
        (False, "2025-01-01", "2025-12-31", 30_000_000_000.0, "-8"),  # != round(32.6673B, -8)
    ])})
    assert duration_series(xb, ["Revenues"], "10-K", "2025-12-31") == []


def test_instant_series_selects_balance_sheet_instants():
    xb = FakeXBRL({"Assets": _facts_df([
        (False, None, "2026-03-31", 500_000.0),          # current instant
        (False, None, "2025-12-31", 480_000.0),          # comparative instant
        (False, None, "2026-06-30", 999_999.0),          # beyond the report period
        (False, "2026-01-01", "2026-03-31", 1.0),        # duration fact — not an instant
        (True,  None, "2026-03-31", 2.0),                # dimensioned
    ])})
    series = instant_series(xb, ["Assets"], "2026-03-31")
    assert series == [("2026-03-31", 500_000.0), ("2025-12-31", 480_000.0)]


def test_instant_series_requires_anchor_at_period_of_report():
    xb = FakeXBRL({"Assets": _facts_df([(False, None, "2025-12-31", 480_000.0)])})
    assert instant_series(xb, ["Assets"], "2026-03-31") == []


# ---------------------------------------------------------------------------
# _extract_from_filing_instance_sync
# ---------------------------------------------------------------------------

def _quarter_frames():
    return {
        "Revenues": _facts_df([
            (False, "2026-01-01", "2026-03-31", 90_000.0),
            (False, "2025-01-01", "2025-03-31", 80_000.0),
        ]),
        "NetIncomeLoss": _facts_df([
            (False, "2026-01-01", "2026-03-31", 9_000.0),
        ]),
        "EarningsPerShareBasic": _facts_df([
            (False, "2026-01-01", "2026-03-31", 1.25),
        ]),
        "Assets": _facts_df([
            (False, None, "2026-03-31", 500_000.0),
        ]),
    }


def _patch_company(filings):
    return patch.object(
        xbrl_module, "EdgarCompany", lambda cik: FakeCompany(filings)
    )


def test_sync_extraction_uses_filings_own_instance():
    filing = FakeFiling("10-Q", "2026-03-31", FakeXBRL(_quarter_frames()))
    with _patch_company([filing]):
        result = _extract_from_filing_instance_sync("0000320193", "0001-26-000001")
    assert result is not None
    assert result["revenue"][0] == {
        "period": "2026-03-31", "value": 90_000.0,
        "form": "10-Q", "accn": "0001-26-000001", "currency": None,
        # Revenue now records the winning XBRL concept (raw_tag) so a concept that flips between
        # filings can be caught downstream. This filer's revenue resolves to us-gaap:Revenues.
        "raw_tag": "us-gaap:Revenues",
    }
    assert result["revenue"][1]["period"] == "2025-03-31"  # YoY quarter
    assert result["net_income"][0]["value"] == 9_000.0
    assert result["earnings_per_share"][0]["value"] == 1.25
    assert result["total_assets"][0]["value"] == 500_000.0
    assert result["total_liabilities"] == []  # not tagged in this instance


def test_sync_extraction_handles_amended_forms():
    filing = FakeFiling("10-Q/A", "2026-03-31", FakeXBRL(_quarter_frames()))
    with _patch_company([filing]):
        result = _extract_from_filing_instance_sync("0000320193", "0001-26-000002")
    assert result is not None
    assert result["revenue"][0]["form"] == "10-Q/A"


@pytest.mark.parametrize("filings", [
    [],                                                      # accession not found
    [FakeFiling("8-K", "2026-03-31", FakeXBRL({}))],         # no standard duration
    [FakeFiling("10-Q", "", FakeXBRL({}))],                  # no period_of_report
    [FakeFiling("10-Q", "2026-03-31", None)],                # no XBRL instance
    [FakeFiling("10-Q", "2026-03-31", FakeXBRL({}))],        # no income anchor
])
def test_sync_extraction_returns_none_when_unusable(filings):
    with _patch_company(filings):
        assert _extract_from_filing_instance_sync("0000320193", "0001-26-000003") is None


def test_richer_financials_extracted_only_behind_the_flag(monkeypatch):
    # Roadmap 2.6 (Phase A): the full cash-flow + working-capital lines are extracted only when
    # RICHER_FINANCIALS_ENABLED is on, so the default concept set stays byte-for-byte unchanged.
    from app.config import settings

    frames = _quarter_frames()
    frames["AssetsCurrent"] = _facts_df([(False, None, "2026-03-31", 300_000.0)])
    frames["LiabilitiesCurrent"] = _facts_df([(False, None, "2026-03-31", 120_000.0)])
    frames["NetCashProvidedByUsedInInvestingActivities"] = _facts_df([
        (False, "2026-01-01", "2026-03-31", -15_000.0),
    ])

    # Flag OFF (default): the richer concepts are absent.
    monkeypatch.setattr(settings, "RICHER_FINANCIALS_ENABLED", False)
    with _patch_company([FakeFiling("10-Q", "2026-03-31", FakeXBRL(frames))]):
        off = _extract_from_filing_instance_sync("0000320193", "0001-26-000010")
    assert off is not None
    assert "current_assets" not in off and "investing_cash_flow" not in off

    # Flag ON: they're extracted from the filing's own instance.
    monkeypatch.setattr(settings, "RICHER_FINANCIALS_ENABLED", True)
    with _patch_company([FakeFiling("10-Q", "2026-03-31", FakeXBRL(frames))]):
        on = _extract_from_filing_instance_sync("0000320193", "0001-26-000011")
    assert on["current_assets"][0]["value"] == 300_000.0
    assert on["current_liabilities"][0]["value"] == 120_000.0
    assert on["investing_cash_flow"][0]["value"] == -15_000.0


# ---------------------------------------------------------------------------
# _fetch_xbrl_data ordering: instance -> companyfacts -> get_financials
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_prefers_filing_instance():
    service = EdgarXBRLService()
    instance_data = {"revenue": [{"period": "2026-03-31", "value": 1.0,
                                  "form": "10-Q", "accn": "a"}]}
    with patch.object(service, "_fetch_from_filing_instance",
                      AsyncMock(return_value=instance_data)) as primary, \
         patch.object(service, "_fallback_to_company_facts", AsyncMock()) as facts, \
         patch.object(service, "_fetch_from_latest_financials", AsyncMock()) as latest:
        result = await service._fetch_xbrl_data("320193", "a")
    assert result == instance_data
    primary.assert_awaited_once_with("0000320193", "a")
    facts.assert_not_awaited()
    latest.assert_not_awaited()


@pytest.mark.asyncio
async def test_fetch_falls_back_to_company_facts_before_latest_financials():
    service = EdgarXBRLService()
    facts_data = {"revenue": [{"period": "2026-03-31", "value": 2.0,
                               "form": "10-Q", "accn": "a"}], "net_income": []}
    with patch.object(service, "_fetch_from_filing_instance",
                      AsyncMock(return_value=None)), \
         patch.object(service, "_fallback_to_company_facts",
                      AsyncMock(return_value=facts_data)) as facts, \
         patch.object(service, "_fetch_from_latest_financials", AsyncMock()) as latest:
        result = await service._fetch_xbrl_data("320193", "a")
    assert result == facts_data
    facts.assert_awaited_once_with("0000320193", "a")
    latest.assert_not_awaited()


@pytest.mark.asyncio
async def test_fetch_uses_latest_financials_as_last_resort():
    service = EdgarXBRLService()
    empty_facts = {key: [] for key in (
        "revenue", "net_income", "total_assets", "total_liabilities",
        "cash_and_equivalents", "earnings_per_share")}
    latest_data = {"revenue": [{"period": "2025-12-31", "value": 3.0,
                                "form": None, "accn": "a"}]}
    with patch.object(service, "_fetch_from_filing_instance",
                      AsyncMock(return_value=None)), \
         patch.object(service, "_fallback_to_company_facts",
                      AsyncMock(return_value=empty_facts)), \
         patch.object(service, "_fetch_from_latest_financials",
                      AsyncMock(return_value=latest_data)) as latest:
        result = await service._fetch_xbrl_data("320193", "a")
    assert result == latest_data
    latest.assert_awaited_once_with("0000320193", "a")


# ---------------------------------------------------------------------------
# Cache key versioning
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cache_keys_are_versioned():
    service = EdgarXBRLService()
    data = {"revenue": [{"period": "2026-03-31", "value": 1.0,
                         "form": "10-Q", "accn": "0001-26-000001"}]}
    with patch.object(service, "_fetch_xbrl_data", AsyncMock(return_value=data)), \
         patch.object(service, "_get_from_redis", AsyncMock(return_value=None)) as get_redis, \
         patch.object(service, "_set_to_redis", AsyncMock(return_value=True)) as set_redis:
        result = await service.get_xbrl_data("0001-26-000001", "320193")

    assert result == data
    version = xbrl_module._XBRL_CACHE_VERSION
    expected_key = f"xbrl:{version}:320193:0001-26-000001"
    assert get_redis.await_args[0][0] == expected_key
    assert set_redis.await_args[0][0] == expected_key
    # L1 keys carry the version too, so a hot process can't serve v1 entries.
    assert list(xbrl_module._xbrl_cache) == [f"{version}:320193:0001-26-000001"]


# ---------------------------------------------------------------------------
# Drift guard: eval golden-set builder and product share concept lists
# ---------------------------------------------------------------------------

def test_golden_set_concepts_match_product_extraction():
    from evals.build_golden_set import METRIC_CONCEPTS

    assert METRIC_CONCEPTS["revenue"][1] == DURATION_CONCEPTS["revenue"]
    assert METRIC_CONCEPTS["net_income"][1] == DURATION_CONCEPTS["net_income"]
    assert METRIC_CONCEPTS["eps"][1] == DURATION_CONCEPTS["earnings_per_share"]


def test_extended_golden_set_concepts_match_product_extraction():
    # The 2.6 extended ground-truth metrics must mirror the product's concept lists so the golden set
    # and production extraction can't drift on which tags count.
    from evals.build_golden_set import EXTENDED_METRIC_CONCEPTS, METRIC_CONCEPTS
    from app.services.edgar.instance_extractor import (
        RICHER_DURATION_CONCEPTS,
        RICHER_INSTANT_CONCEPTS,
    )

    assert EXTENDED_METRIC_CONCEPTS["operating_cash_flow"][1] == DURATION_CONCEPTS["operating_cash_flow"]
    assert EXTENDED_METRIC_CONCEPTS["investing_cash_flow"][1] == RICHER_DURATION_CONCEPTS["investing_cash_flow"]
    assert EXTENDED_METRIC_CONCEPTS["financing_cash_flow"][1] == RICHER_DURATION_CONCEPTS["financing_cash_flow"]
    assert EXTENDED_METRIC_CONCEPTS["current_assets"][1] == RICHER_INSTANT_CONCEPTS["current_assets"]
    assert EXTENDED_METRIC_CONCEPTS["current_liabilities"][1] == RICHER_INSTANT_CONCEPTS["current_liabilities"]
    # `kind` routes the extraction path: balance-sheet lines are instant, flows are duration.
    assert EXTENDED_METRIC_CONCEPTS["current_assets"][2] == "instant"
    assert EXTENDED_METRIC_CONCEPTS["current_liabilities"][2] == "instant"
    assert EXTENDED_METRIC_CONCEPTS["operating_cash_flow"][2] == "duration"
    # Extended metrics must not overlap the core (verified-gating) set.
    assert set(EXTENDED_METRIC_CONCEPTS) & set(METRIC_CONCEPTS) == set()
