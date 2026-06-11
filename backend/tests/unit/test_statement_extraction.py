"""Unit tests for EdgarTools statement parsing and the company-facts fallback.

Covers the PR #239 review findings:
- statement DataFrames in edgartools 5.x carry concepts in a `concept` COLUMN
  (the old index-based lookup silently extracted nothing),
- duplicate period columns must not silently drop values,
- the company-facts fallback must not let a stale concept (e.g. AAPL `Revenues`,
  last reported FY2018) shadow the live one, and must pick the standard duration
  (12-month for 10-K, 3-month for 10-Q) when several share a period end.
"""

import pandas as pd
import pytest

from app.services.edgar.statement_parser import (
    extract_metric_values,
    normalize_concept,
    statement_dataframe,
)
from app.services.edgar.xbrl_service import EdgarXBRLService


pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# statement_parser
# ---------------------------------------------------------------------------

def _modern_df():
    """Shape produced by edgartools 5.x Statement.to_dataframe()."""
    return pd.DataFrame({
        "concept": [
            "us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax",
            "us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax",  # segment row
            "us-gaap_EarningsPerShareAbstract",
            "us-gaap_NetIncomeLoss",
        ],
        "label": ["Revenue", "Product", "EPS:", "Net income"],
        "2025-06-30 (FY)": [281_724_000_000.0, 63_946_000_000.0, None, 101_832_000_000.0],
        "2024-06-30 (FY)": [245_122_000_000.0, 64_773_000_000.0, None, 88_136_000_000.0],
        "abstract": [False, False, True, False],
        "dimension": [False, True, False, False],
    })


def test_modern_schema_extracts_consolidated_rows_only():
    concept, values = extract_metric_values(
        _modern_df(),
        ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues"],
    )
    assert concept == "RevenueFromContractWithCustomerExcludingAssessedTax"
    # Segment (dimension=True) row must not shadow the consolidated total.
    assert values == [
        ("2025-06-30", 281_724_000_000.0),
        ("2024-06-30", 245_122_000_000.0),
    ]


def test_modern_schema_skips_abstract_rows():
    concept, values = extract_metric_values(_modern_df(), ["EarningsPerShareAbstract"])
    assert concept is None
    assert values == []


def test_candidate_order_respected():
    concept, _ = extract_metric_values(
        _modern_df(), ["NetIncomeLoss", "RevenueFromContractWithCustomerExcludingAssessedTax"]
    )
    assert concept == "NetIncomeLoss"


def test_duplicate_period_end_prefers_full_year_duration():
    # Same period end under Q4 and FY markers: the FY figure is the statement value.
    df = pd.DataFrame({
        "concept": ["us-gaap_NetIncomeLoss"],
        "2025-12-31 (Q4)": [1_000_000.0],
        "2025-12-31 (FY)": [4_000_000.0],
        "abstract": [False],
        "dimension": [False],
    })
    _, values = extract_metric_values(df, ["NetIncomeLoss"])
    assert values == [("2025-12-31", 4_000_000.0)]


def test_duplicate_column_labels_do_not_drop_values():
    # Two columns with the IDENTICAL label: row[col] returns a Series, which the
    # old code float()-ed, raised, and silently skipped. Positional iteration
    # must still surface a value.
    df = pd.DataFrame(
        [["us-gaap_NetIncomeLoss", False, False, 5.0, 7.0]],
        columns=["concept", "abstract", "dimension", "2025-12-31", "2025-12-31"],
    )
    _, values = extract_metric_values(df, ["NetIncomeLoss"])
    assert values == [("2025-12-31", 5.0)]


def test_legacy_schema_concepts_as_index():
    df = pd.DataFrame(
        {"2024-09-28": [391_035_000_000.0], "2023-09-30": [383_285_000_000.0]},
        index=["Revenues"],
    )
    concept, values = extract_metric_values(df, ["Revenues"])
    assert concept == "Revenues"
    assert values == [
        ("2024-09-28", 391_035_000_000.0),
        ("2023-09-30", 383_285_000_000.0),
    ]


def test_normalize_concept_variants():
    assert normalize_concept("us-gaap_NetIncomeLoss") == "NetIncomeLoss"
    assert normalize_concept("us-gaap:NetIncomeLoss") == "NetIncomeLoss"
    assert normalize_concept("NetIncomeLoss") == "NetIncomeLoss"
    assert normalize_concept("aapl_CustomTag") == "CustomTag"


def test_statement_dataframe_handles_method_and_property():
    sentinel = pd.DataFrame({"concept": []})

    class Statement:
        def to_dataframe(self):
            return sentinel

    class MethodStyle:  # edgartools 5.x
        def income_statement(self):
            return Statement()

    class PropertyStyle:  # legacy
        income_statement = Statement()

    class MissingStyle:
        income_statement = None

    assert statement_dataframe(MethodStyle(), "income_statement") is sentinel
    assert statement_dataframe(PropertyStyle(), "income_statement") is sentinel
    assert statement_dataframe(MissingStyle(), "income_statement") is None


# ---------------------------------------------------------------------------
# company-facts fallback (_parse_company_facts)
# ---------------------------------------------------------------------------

def _usd_fact(items):
    return {"units": {"USD": items}}


def test_company_facts_stale_concept_does_not_shadow_live_one():
    # AAPL pattern: `Revenues` retired after FY2018, live data under the
    # contract-revenue tag. First-present-wins picked the stale tag and
    # reported FY2018 revenue as current.
    service = EdgarXBRLService()
    facts_data = {"facts": {"us-gaap": {
        "Revenues": _usd_fact([
            {"end": "2018-09-29", "start": "2017-10-01", "val": 265_595_000_000,
             "form": "10-K", "accn": "0000320193-18-000145", "filed": "2018-11-05"},
        ]),
        "RevenueFromContractWithCustomerExcludingAssessedTax": _usd_fact([
            {"end": "2025-09-27", "start": "2024-09-29", "val": 416_161_000_000,
             "form": "10-K", "accn": "0000320193-25-000079", "filed": "2025-11-01"},
        ]),
    }}}
    result = service._parse_company_facts(facts_data, "0000320193-25-000079")
    assert result["revenue"][0]["value"] == 416_161_000_000
    assert result["revenue"][0]["period"] == "2025-09-27"


def test_company_facts_prefers_target_accession_facts():
    service = EdgarXBRLService()
    facts_data = {"facts": {"us-gaap": {
        "NetIncomeLoss": _usd_fact([
            {"end": "2025-12-31", "start": "2025-01-01", "val": 999,  # later filing
             "form": "10-K", "accn": "0000000000-26-000001", "filed": "2026-02-01"},
            {"end": "2024-12-31", "start": "2024-01-01", "val": 111,
             "form": "10-K", "accn": "0000000000-25-000001", "filed": "2025-02-01"},
        ]),
    }}}
    result = service._parse_company_facts(facts_data, "0000000000-25-000001")
    # Restricted to the target filing's facts: the newer filing's value is excluded.
    assert [item["value"] for item in result["net_income"]] == [111]


def test_company_facts_same_end_prefers_standard_duration_for_10k():
    # 10-K facts: Q4 (3-month) and FY (12-month) share the fiscal-year end.
    service = EdgarXBRLService()
    accn = "0000000000-26-000002"
    facts_data = {"facts": {"us-gaap": {
        "NetIncomeLoss": _usd_fact([
            {"end": "2025-12-31", "start": "2025-10-01", "val": 477_000_000,
             "form": "10-K", "accn": accn, "filed": "2026-02-01"},
            {"end": "2025-12-31", "start": "2025-01-01", "val": 7_153_000_000,
             "form": "10-K", "accn": accn, "filed": "2026-02-01"},
        ]),
    }}}
    result = service._parse_company_facts(facts_data, accn)
    assert [item["value"] for item in result["net_income"]] == [7_153_000_000]


def test_company_facts_same_end_prefers_quarter_duration_for_10q():
    # 10-Q facts: 3-month quarter and 9-month YTD share the quarter end.
    service = EdgarXBRLService()
    accn = "0000000000-26-000003"
    facts_data = {"facts": {"us-gaap": {
        "NetIncomeLoss": _usd_fact([
            {"end": "2026-09-30", "start": "2026-01-01", "val": 9_000_000,  # 9-month YTD
             "form": "10-Q", "accn": accn, "filed": "2026-11-01"},
            {"end": "2026-09-30", "start": "2026-07-01", "val": 3_000_000,  # quarter
             "form": "10-Q", "accn": accn, "filed": "2026-11-01"},
        ]),
    }}}
    result = service._parse_company_facts(facts_data, accn)
    assert [item["value"] for item in result["net_income"]] == [3_000_000]


def test_company_facts_eps_uses_per_share_units():
    service = EdgarXBRLService()
    accn = "0000000000-26-000004"
    facts_data = {"facts": {"us-gaap": {
        "EarningsPerShareBasic": {"units": {"USD/shares": [
            {"end": "2025-12-31", "start": "2025-01-01", "val": 7.49,
             "form": "10-K", "accn": accn, "filed": "2026-02-01"},
        ]}},
    }}}
    result = service._parse_company_facts(facts_data, accn)
    assert result["earnings_per_share"][0]["value"] == 7.49
