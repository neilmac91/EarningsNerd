"""P0-3 guardrail (data-quality plan): the tag-migration merge on a JPM-shaped payload.

JPM tagged `CashAndCashEquivalentsAtCarryingValue` through FY2018 and only the ASU 2016-18
restricted-cash total from FY2019 on; the restricted tag also RESTATES FY2016-18 with values
identical to the legacy tag (EDGAR-verified). Appending the new tag LAST + per-period
first-tag-wins must therefore: keep FY2016-18 on the legacy tag (identical values, zero churn)
and fill FY2019+ — previously missing entirely — from the new tag.
"""
from app.services.facts_service import normalize_companyfacts

LEGACY = "CashAndCashEquivalentsAtCarryingValue"
RESTRICTED = "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"

# Real JPM annual values, $ (EDGAR companyconcept, fetched 2026-07-07).
JPM_CASH = {
    2016: 391_200_000_000.0,
    2017: 431_300_000_000.0,
    2018: 278_800_000_000.0,
    2019: 263_600_000_000.0,
    2020: 527_600_000_000.0,
    2021: 740_800_000_000.0,
    2022: 567_200_000_000.0,
    2023: 624_200_000_000.0,
    2024: 469_300_000_000.0,
    2025: 343_300_000_000.0,
}


def _instant_item(year: int, value: float, accn: str) -> dict:
    return {
        "end": f"{year}-12-31",
        "val": value,
        "accn": accn,
        "fy": year,
        "fp": "FY",
        "form": "10-K",
        "filed": f"{year + 1}-02-20",
    }


def _duration_item(year: int, value: float) -> dict:
    return {
        "start": f"{year}-01-01",
        "end": f"{year}-12-31",
        "val": value,
        "accn": f"0000019617-{str(year + 1)[2:]}-000001",
        "fy": year,
        "fp": "FY",
        "form": "10-K",
        "filed": f"{year + 1}-02-20",
    }


def _jpm_payload() -> dict:
    # Legacy tag: FY2016-18 only (JPM stopped tagging it). Restricted tag: FY2016-25 (the
    # restatement overlap + the migrated years). Net income durations establish the FY windows.
    return {
        "facts": {
            "us-gaap": {
                LEGACY: {
                    "units": {
                        "USD": [
                            _instant_item(y, JPM_CASH[y], f"legacy-{y}") for y in (2016, 2017, 2018)
                        ]
                    }
                },
                RESTRICTED: {
                    "units": {
                        "USD": [
                            _instant_item(y, JPM_CASH[y], f"restricted-{y}")
                            for y in range(2016, 2026)
                        ]
                    }
                },
                "NetIncomeLoss": {
                    "units": {
                        "USD": [_duration_item(y, 50_000_000_000.0) for y in range(2016, 2026)]
                    }
                },
            }
        }
    }


def test_fy16_18_keep_legacy_tag_and_fy19_plus_fill_from_restricted():
    facts, meta = normalize_companyfacts(1, _jpm_payload())
    assert meta == {"unsupported_ifrs": False}

    cash = {
        f["fiscal_year"]: f
        for f in facts
        if f["concept"] == "cash_and_equivalents" and f["fiscal_period"] == "FY"
    }
    assert sorted(cash) == list(range(2016, 2026))  # the full ten years — no truncation

    for year in (2016, 2017, 2018):
        assert cash[year]["raw_tag"] == f"us-gaap:{LEGACY}", year  # zero churn pre-migration
        assert cash[year]["value"] == JPM_CASH[year]
    for year in range(2019, 2026):
        assert cash[year]["raw_tag"] == f"us-gaap:{RESTRICTED}", year
        assert cash[year]["value"] == JPM_CASH[year]
