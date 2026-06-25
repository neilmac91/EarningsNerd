"""Phase 3: reporting-currency capture for foreign private issuers (e.g. Alibaba 20-F).

Pins the behaviour that fixed the silent-USD distortion: a foreign filer tags the same line in BOTH
its reporting currency (all periods) AND a USD convenience translation (latest period only). The
extractor must (a) keep the native currency and all comparatives — not treat the second currency as
an ambiguous duplicate and drop the period — and (b) carry the currency through to the stored unit.
See tasks/fpi-support-roadmap.md (Phase 3).
"""

import pandas as pd
import pytest

from app.services.edgar import xbrl_service as xbrl_module
from app.services.edgar.instance_extractor import (
    _currency,
    _reporting_currency,
    duration_series_with_currency,
    instant_series_with_currency,
)
from app.services.edgar.xbrl_service import _extract_from_filing_instance_sync
from app.services import facts_service

pytestmark = pytest.mark.unit


# --- namespace-agnostic fakes with a currency column ---------------------------------------

def _ccy_df(rows):
    """rows: (is_dimensioned, period_start, period_end, numeric_value, currency)."""
    return pd.DataFrame(
        rows,
        columns=["is_dimensioned", "period_start", "period_end", "numeric_value", "currency"],
    )


class _Query:
    def __init__(self, frames):
        self._frames = frames
        self._sel = pd.DataFrame()

    def by_concept(self, concept, exact=True):
        # Accept either us-gaap: or ifrs-full:; key by the bare concept name.
        self._sel = self._frames.get(concept.split(":", 1)[1], pd.DataFrame())
        return self

    def to_dataframe(self):
        return self._sel


class _Facts:
    def __init__(self, frames):
        self._frames = frames

    def query(self):
        return _Query(self._frames)


class _XBRL:
    def __init__(self, frames):
        self.facts = _Facts(frames)


class _Filing:
    def __init__(self, form, period_of_report, xb):
        self.form = form
        self.period_of_report = period_of_report
        self._xb = xb

    def xbrl(self):
        return self._xb


def _patch_company(filings):
    from unittest.mock import patch

    class _Company:
        def __init__(self, cik):
            pass

        def get_filings(self, accession_number=None):
            return list(filings)

    return patch.object(xbrl_module, "EdgarCompany", _Company)


# --- _currency / _reporting_currency ------------------------------------------------------

def test_currency_normalizes():
    assert _currency({"currency": "cny"}) == "CNY"
    assert _currency({"currency": None}) is None
    assert _currency({"currency": float("nan")}) is None  # str(nan)=="nan" must NOT become "NAN"
    assert _currency({}) is None


def test_currency_rejects_non_iso_codes():
    # Strict ISO-4217: exactly three letters. Junk / pandas-<NA> / wrong-length all → None.
    assert _currency({"currency": "<NA>"}) is None
    assert _currency({"currency": "US"}) is None
    assert _currency({"currency": "USDX"}) is None
    assert _currency({"currency": ""}) is None
    assert _currency({"currency": "eur"}) == "EUR"


def test_reporting_currency_prefers_currency_with_more_periods():
    # CNY covers 3 ends, USD only the latest → CNY is the reporting currency.
    candidates = [
        ("2026-03-31", 1.0, "CNY"), ("2026-03-31", 0.14, "USD"),
        ("2025-03-31", 1.0, "CNY"), ("2024-03-31", 1.0, "CNY"),
    ]
    assert _reporting_currency(candidates, "2026-03-31") == "CNY"


def test_reporting_currency_none_when_absent():
    assert _reporting_currency([("2025-12-31", 1.0, None)], "2025-12-31") is None


# --- duration / instant series ------------------------------------------------------------

def test_duration_series_keeps_native_currency_and_comparatives():
    # Alibaba-style: CNY for 3 years + a USD convenience translation for the latest year.
    frames = {
        "Revenues": _ccy_df([
            (False, "2025-04-01", "2026-03-31", 1_023_670e6, "CNY"),
            (False, "2025-04-01", "2026-03-31", 148_401e6, "USD"),  # convenience translation
            (False, "2024-04-01", "2025-03-31", 996_347e6, "CNY"),
            (False, "2023-04-01", "2024-03-31", 941_168e6, "CNY"),
        ])
    }
    series, currency = duration_series_with_currency(
        _XBRL(frames), ["Revenues"], "20-F", "2026-03-31"
    )
    assert currency == "CNY"
    # The native CNY value wins the anchor (NOT the 148B USD convenience)...
    assert series[0] == ("2026-03-31", 1_023_670e6)
    # ...and all three comparative years survive (the dual-currency anchor is no longer "ambiguous").
    assert [p for p, _ in series] == ["2026-03-31", "2025-03-31", "2024-03-31"]


def test_duration_series_without_currency_is_noop():
    # No currency column → unchanged behaviour, currency None.
    frames = {"Revenues": pd.DataFrame(
        [(False, "2025-01-01", "2025-12-31", 500.0)],
        columns=["is_dimensioned", "period_start", "period_end", "numeric_value"],
    )}
    series, currency = duration_series_with_currency(
        _XBRL(frames), ["Revenues"], "10-K", "2025-12-31"
    )
    assert currency is None
    assert series == [("2025-12-31", 500.0)]


def test_instant_series_keeps_native_currency():
    frames = {
        "Assets": _ccy_df([
            (False, None, "2026-03-31", 1_909_570e6, "CNY"),
            (False, None, "2026-03-31", 276_000e6, "USD"),  # convenience translation
            (False, None, "2025-03-31", 1_800_000e6, "CNY"),
        ])
    }
    series, currency = instant_series_with_currency(_XBRL(frames), ["Assets"], "2026-03-31")
    assert currency == "CNY"
    assert series[0] == ("2026-03-31", 1_909_570e6)


# --- full instance extraction -------------------------------------------------------------

def test_extract_from_instance_sets_reporting_currency():
    frames = {
        "Revenues": _ccy_df([
            (False, "2025-04-01", "2026-03-31", 1_023_670e6, "CNY"),
            (False, "2025-04-01", "2026-03-31", 148_401e6, "USD"),
        ]),
        "NetIncomeLoss": _ccy_df([
            (False, "2025-04-01", "2026-03-31", 103_592e6, "CNY"),
        ]),
        "Assets": _ccy_df([
            (False, None, "2026-03-31", 1_909_570e6, "CNY"),
        ]),
    }
    filing = _Filing("20-F", "2026-03-31", _XBRL(frames))
    with _patch_company([filing]):
        result = _extract_from_filing_instance_sync("0001577552", "0001-26-000001")
    assert result is not None
    assert result["reporting_currency"] == "CNY"
    assert result["revenue"][0]["value"] == 1_023_670e6
    assert result["revenue"][0]["currency"] == "CNY"


# --- facts_service unit/currency handling -------------------------------------------------

def test_unit_for_substitutes_currency():
    assert facts_service._unit_for("revenue", "CNY") == "CNY"
    assert facts_service._unit_for("earnings_per_share", "CNY") == "CNY/shares"
    assert facts_service._unit_for("net_margin", "CNY") == "pure"  # ratios stay pure
    # Domestic (no currency) keeps the USD defaults.
    assert facts_service._unit_for("revenue", None) == "USD"
    assert facts_service._unit_for("earnings_per_share", None) == "USD/shares"


def test_fiscal_period_covers_foreign_annual_forms():
    assert facts_service._fiscal_period("20-F") == "FY"
    assert facts_service._fiscal_period("40-F") == "FY"
    assert facts_service._fiscal_period("10-K") == "FY"
    assert facts_service._fiscal_period("10-Q") is None
    assert facts_service._fiscal_period("6-K") is None


def test_normalize_derived_metric_falls_back_to_reporting_currency():
    # free_cash_flow is derived (OCF − capex) and carries no per-point currency; it must inherit
    # the filing's reporting_currency, not silently default to USD.
    standardized = {
        "reporting_currency": "CNY",
        "free_cash_flow": {"current": {"period": "2026-03-31", "value": 5e10, "form": "20-F"}},
    }
    facts = facts_service.normalize_standardized_to_facts(
        company_id=1, filing_id=2, accession="x", form="20-F", standardized=standardized
    )
    fcf = [f for f in facts if f["concept"] == "free_cash_flow"]
    assert fcf and fcf[0]["unit"] == "CNY"


def test_normalize_uses_currency_unit():
    standardized = {
        "revenue": {"current": {"period": "2026-03-31", "value": 1_023_670e6,
                                "form": "20-F", "currency": "CNY"}},
    }
    facts = facts_service.normalize_standardized_to_facts(
        company_id=1, filing_id=2, accession="x", form="20-F", standardized=standardized
    )
    assert len(facts) == 1
    assert facts[0]["unit"] == "CNY"
    assert facts[0]["fiscal_period"] == "FY"


def test_cross_check_skips_non_usd_facts():
    # Authoritative companyfacts is USD-only; a CNY fact must never be overwritten by it.
    import datetime
    pe = datetime.date(2026, 3, 31)
    facts = [{"concept": "revenue", "period_end": pe, "value": 1_023_670e6, "unit": "CNY"}]
    authoritative = {("revenue", pe): 148_401e6}  # the USD convenience figure
    out = facts_service.cross_check_facts(facts, authoritative)
    assert out[0]["value"] == 1_023_670e6  # unchanged — native CNY preserved
    assert out[0].get("source") != "companyfacts"


# --- eval scorer: currency-agnostic numeric matching --------------------------------------

def test_scorer_matches_native_currency_numbers():
    from evals.scorers import _number_renderings

    # A CNY revenue (RMB 1,023.67B) must match its "billions" rendering — the scorer is
    # number-based, so a "RMB"-prefixed summary value still scores as correct.
    reps = _number_renderings(1_023_670_000_000.0, "CNY")
    assert "1,023.67" in reps or "1023.67" in reps

    # A non-USD per-share figure renders at full precision (not scaled), like USD EPS.
    eps_reps = _number_renderings(6.0, "CNY_per_share")
    assert "6.00" in eps_reps
