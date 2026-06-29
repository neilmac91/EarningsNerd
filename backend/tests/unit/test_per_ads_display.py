"""Unit tests for surfacing per-ADS EPS to the frontend (roadmap item 1.5).

The ADS-ratio correctness layer (item A / #461) attaches a ``per_ads`` block to the standardized
EPS metric. These tests prove ``attach_normalized_facts`` MERGES that block onto the EPS row of the
financial-highlights ``table`` (which is what the API serializes to the frontend) — additively, so
the as-filed per-ordinary-share value is never altered, and only for ratio != 1 ADRs.
"""

from app.schemas.summary import attach_normalized_facts


# Mirrors the shape build_per_ads_eps returns (value, ratio, currency, dated source, arithmetic).
PER_ADS = {
    "value": 45.6,
    "ordinary_per_ads": 8,
    "currency": "CNY",
    "as_of": "2026-06-28",
    "source": "Alibaba 20-F cover / deposit agreement — 1 ADS = 8 ordinary shares",
    "arithmetic": "CNY 5.7 per ordinary share × 8 = CNY 45.6 per ADS",
}


def _rows_by_metric(section):
    return {row["metric"]: row for row in section["table"]}


def test_per_ads_merged_onto_eps_row_without_touching_as_filed_value():
    section = {
        "table": [
            {"metric": "Diluted EPS", "current_period": "CN¥5.70", "prior_period": "CN¥5.50"},
            {"metric": "Revenue", "current_period": "CN¥1,023.7B", "prior_period": "CN¥941.2B"},
        ],
        "notes": "n",
    }
    # "Diluted EPS" infers the xbrl key earnings_per_share, which carries per_ads for ADRs.
    out = attach_normalized_facts(section, {"earnings_per_share": {"per_ads": PER_ADS}})
    rows = _rows_by_metric(out)

    eps = rows["Diluted EPS"]
    assert eps["per_ads"] == PER_ADS  # surfaced onto the row the frontend reads
    assert eps["current_period"] == "CN¥5.70"  # as-filed per-ordinary-share value UNCHANGED
    assert "per_ads" not in rows["Revenue"]  # only the EPS row carries it


def test_no_per_ads_for_domestic_filer():
    section = {"table": [{"metric": "Diluted EPS", "current_period": "$7.46", "prior_period": "$6.11"}]}
    # Domestic issuer: the standardized EPS metric has no per_ads block.
    out = attach_normalized_facts(section, {"earnings_per_share": {}})
    assert "per_ads" not in out["table"][0]


def test_no_per_ads_when_no_xbrl_metrics():
    section = {"table": [{"metric": "Diluted EPS", "current_period": "$7.46"}]}
    out = attach_normalized_facts(section, None)
    assert "per_ads" not in out["table"][0]


def test_non_dict_per_ads_is_ignored_fail_safe():
    section = {"table": [{"metric": "Diluted EPS", "current_period": "CN¥5.70"}]}
    # A corrupted/deserialized cache could carry a non-dict; it must be ignored, not propagated.
    out = attach_normalized_facts(section, {"earnings_per_share": {"per_ads": "not-a-dict"}})
    assert "per_ads" not in out["table"][0]
