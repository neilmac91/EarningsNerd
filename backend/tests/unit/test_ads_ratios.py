"""Unit tests for the ADS-ratio correctness layer (item A).

Two layers:
  1. The dependency-light helpers in ``app.services.edgar.ads_ratios`` (pure, offline).
  2. The additive wiring through ``EdgarXBRLService.extract_standardized_metrics`` — proving the
     per-ADS block is ADDED without touching the as-filed per-ordinary-share EPS (so the eval
     baseline can't regress), and is ABSENT for non-ADR filings.
"""

import pytest

from app.services.edgar.ads_ratios import (
    ADSRatio,
    ads_ratio_for_cik,
    build_per_ads_eps,
)
from app.services.edgar.xbrl_service import edgar_xbrl_service


# --- the locked table mirrors the eval golden set (ratio != 1 ADRs only) ---

@pytest.mark.parametrize(
    "cik, expected_ratio, expected_ticker",
    [
        ("1577552", 8, "BABA"),
        ("1046179", 5, "TSM"),
        ("1549802", 2, "JD"),
        ("1737806", 4, "PDD"),
    ],
)
def test_known_adrs_match_golden_set_ratios(cik, expected_ratio, expected_ticker):
    ratio = ads_ratio_for_cik(cik)
    assert ratio is not None
    assert ratio.ordinary_per_ads == expected_ratio
    assert ratio.ticker == expected_ticker
    assert ratio.as_of  # dated (source-and-locked)
    assert ratio.source


def test_cik_lookup_normalizes_padding_and_type():
    # zero-padded (as xbrl_service passes it), unpadded, and int all resolve to the same entry.
    assert ads_ratio_for_cik("0001577552").ticker == "BABA"
    assert ads_ratio_for_cik("1577552").ticker == "BABA"
    assert ads_ratio_for_cik(1577552).ticker == "BABA"


@pytest.mark.parametrize("cik", ["1703399", "320193", "0000320193", None, "", "not-a-cik"])
def test_one_to_one_or_domestic_or_junk_ciks_return_none(cik):
    # SE (1703399) is a 1:1 ADR, AAPL (320193) is domestic — neither is normalized.
    assert ads_ratio_for_cik(cik) is None


# --- per-ADS arithmetic ---

def test_build_per_ads_eps_alibaba():
    info = ads_ratio_for_cik("1577552").as_dict()
    per_ads = build_per_ads_eps(5.7, info, "CNY")
    assert per_ads is not None
    assert per_ads["value"] == 45.6  # 5.7 x 8, float noise rounded away
    assert per_ads["ordinary_per_ads"] == 8
    assert per_ads["currency"] == "CNY"
    # auditable arithmetic: shows the inputs, the ratio, the result, and the unit
    arith = per_ads["arithmetic"]
    for token in ("5.7", "8", "45.6", "CNY", "per ADS"):
        assert token in arith


def test_build_per_ads_eps_tsmc_high_value():
    info = ads_ratio_for_cik("1046179").as_dict()
    per_ads = build_per_ads_eps(65.47, info, "TWD")
    assert per_ads["value"] == 327.35  # 65.47 x 5


def test_build_per_ads_eps_without_currency_still_computes():
    info = ads_ratio_for_cik("1737806").as_dict()  # PDD, ratio 4
    per_ads = build_per_ads_eps(17.5, info, None)
    assert per_ads["value"] == 70.0
    assert per_ads["currency"] is None
    assert "per ADS" in per_ads["arithmetic"]


def test_build_per_ads_eps_returns_none_on_missing_or_bad_inputs():
    info = ADSRatio(8, "2026-06-28", "src", "BABA").as_dict()
    assert build_per_ads_eps(None, info, "CNY") is None  # no per-share value
    assert build_per_ads_eps(5.7, {"ordinary_per_ads": None}, "CNY") is None
    assert build_per_ads_eps(5.7, {"ordinary_per_ads": 0}, "CNY") is None
    assert build_per_ads_eps(5.7, {}, "CNY") is None


# --- additive integration through extract_standardized_metrics ---

def _xbrl_data_with_eps(eps_value, *, ads_ratio=None, reporting_currency="CNY"):
    data = {
        "earnings_per_share": [
            {"period": "2026-03-31", "value": eps_value, "form": "20-F", "currency": None},
        ],
        "reporting_currency": reporting_currency,
    }
    if ads_ratio is not None:
        data["ads_ratio"] = ads_ratio
    return data


def test_extract_metrics_adds_per_ads_without_touching_per_share():
    info = ads_ratio_for_cik("1577552").as_dict()  # BABA, ratio 8
    metrics = edgar_xbrl_service.extract_standardized_metrics(
        _xbrl_data_with_eps(5.7, ads_ratio=info, reporting_currency="CNY")
    )
    eps = metrics["earnings_per_share"]
    # the as-filed per-ordinary-share figure is UNCHANGED (eval baseline safety)
    assert eps["current"]["value"] == 5.7
    # a per-ADS block is ADDED
    assert eps["per_ads"]["value"] == 45.6
    assert eps["per_ads"]["ordinary_per_ads"] == 8
    assert eps["per_ads"]["currency"] == "CNY"


def test_extract_metrics_no_per_ads_when_not_an_adr():
    metrics = edgar_xbrl_service.extract_standardized_metrics(
        _xbrl_data_with_eps(6.13, ads_ratio=None, reporting_currency="USD")
    )
    assert "per_ads" not in metrics["earnings_per_share"]
