"""Downstream wiring for financial-institution revenue (filing 528): facts raw_tag propagation,
the What-Changed component deltas + concept-flip guard, provenance mapping, and summary inference.
All pure functions — no DB, no network."""
import pytest

from app.services.facts_service import normalize_standardized_to_facts
from app.services.dashboard_feed_service import compute_what_changed
from app.services.provenance_service import map_metric_to_xbrl_key, enrich_financial_highlights
from app.schemas.summary import _infer_xbrl_metric
from app.services.openai_service import _sanitize_bank_financial_highlights, _is_no_total_bank

pytestmark = pytest.mark.unit


def test_normalize_propagates_raw_tag_and_unit():
    standardized = {
        "net_interest_income": {
            "series": [
                {"period": "2025-12-31", "value": 303235000.0, "form": "10-K",
                 "raw_tag": "us-gaap:InterestIncomeExpenseNet"},
            ]
        },
    }
    facts = normalize_standardized_to_facts(1, 10, "0000-1", "10-K", standardized)
    assert len(facts) == 1
    f = facts[0]
    assert f["concept"] == "net_interest_income"
    assert f["raw_tag"] == "us-gaap:InterestIncomeExpenseNet"
    assert f["unit"] == "USD"
    assert f["fiscal_period"] == "FY"
    assert f["value"] == 303235000.0


def test_what_changed_emits_bank_component_chips():
    current = {
        "net_interest_income": [{"period": "2025-12-31", "value": 303.0, "raw_tag": "t_nii"}],
        "noninterest_income": [{"period": "2025-12-31", "value": 11.0, "raw_tag": "t_non"}],
    }
    prior = {
        "net_interest_income": [{"period": "2024-12-31", "value": 253.0, "raw_tag": "t_nii"}],
        "noninterest_income": [{"period": "2024-12-31", "value": 23.0, "raw_tag": "t_non"}],
    }
    out = compute_what_changed(current, prior)
    assert out is not None
    metrics = {it["metric"]: it for it in out["items"]}
    assert "net_interest_income" in metrics and "noninterest_income" in metrics
    assert "revenue" not in metrics  # a bank has no single revenue
    assert metrics["net_interest_income"]["direction"] == "up"
    assert metrics["noninterest_income"]["direction"] == "down"


def test_what_changed_flip_guard_drops_mismatched_concept():
    # Current revenue came from a different XBRL concept than prior → apples-to-oranges → dropped.
    current = {
        "revenue": [{"period": "2025-12-31", "value": 11.1, "raw_tag": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"}],
        "net_income": [{"period": "2025-12-31", "value": 71.0, "raw_tag": None}],
    }
    prior = {
        "revenue": [{"period": "2024-12-31", "value": 24.0, "raw_tag": "us-gaap:Revenues"}],
        "net_income": [{"period": "2024-12-31", "value": 66.0, "raw_tag": None}],
    }
    out = compute_what_changed(current, prior)
    assert out is not None
    assert out["data_quality"] == "partial"
    assert all(it["metric"] != "revenue" for it in out["items"])
    assert any(it["metric"] == "net_income" for it in out["items"])  # net income still reported


def test_what_changed_flip_guard_inert_without_tags():
    # Legacy series (no raw_tag on either side) must NOT be suppressed.
    current = {"revenue": [{"period": "2025-12-31", "value": 120.0}]}
    prior = {"revenue": [{"period": "2024-12-31", "value": 100.0}]}
    out = compute_what_changed(current, prior)
    assert out is not None
    assert out["data_quality"] == "ok"
    assert any(it["metric"] == "revenue" and it["direction"] == "up" for it in out["items"])


def test_what_changed_flip_guard_inert_when_tags_match():
    current = {"revenue": [{"period": "2025-12-31", "value": 120.0, "raw_tag": "us-gaap:Revenues"}]}
    prior = {"revenue": [{"period": "2024-12-31", "value": 100.0, "raw_tag": "us-gaap:Revenues"}]}
    out = compute_what_changed(current, prior)
    assert out is not None and out["data_quality"] == "ok"
    assert any(it["metric"] == "revenue" for it in out["items"])


@pytest.mark.parametrize("name,expected_key", [
    ("Net Interest Income", "net_interest_income"),
    ("Net interest income", "net_interest_income"),
    ("Non-Interest Income", "noninterest_income"),
    ("Noninterest income", "noninterest_income"),
    ("Net Investment Income", "net_investment_income"),
    ("Premiums Earned (Net)", "premiums_earned"),
    ("Net income", "net_income"),          # not shadowed by the new patterns
    ("Revenue", "revenue"),
])
def test_provenance_metric_mapping(name, expected_key):
    mapped = map_metric_to_xbrl_key(name)
    assert mapped is not None and mapped[0] == expected_key


@pytest.mark.parametrize("name,expected", [
    ("Net Interest Income", "net_interest_income"),
    ("Non-Interest Income", "noninterest_income"),
    ("Noninterest Income", "noninterest_income"),
    ("Net Investment Income", "net_investment_income"),
    ("Premiums Earned", "premiums_earned"),
    ("Net income", "net_income"),
    ("Total Revenue", "revenue"),
])
def test_summary_infer_xbrl_metric(name, expected):
    assert _infer_xbrl_metric(name) == expected


# --------------------------------------------------------------------------- bank-revenue guards (#4)

_NO_TOTAL_BANK = {
    "net_interest_income": {"current": {"value": 303_000_000.0}},
    "noninterest_income": {"current": {"value": 11_000_000.0}},
}
_TOTAL_BANK = {**_NO_TOTAL_BANK, "revenue": {"current": {"value": 182_000_000_000.0}}}
_NON_FINANCIAL = {"revenue": {"current": {"value": 50_000_000_000.0}}}


def _highlights():
    return {"table": [
        {"metric": "Revenue", "current_period": "$527.1M"},
        {"metric": "Net Interest Income", "current_period": "$303.2M"},
        {"metric": "Net Income", "current_period": "$71.1M"},
    ]}


def test_is_no_total_bank():
    assert _is_no_total_bank(_NO_TOTAL_BANK) is True
    assert _is_no_total_bank(_TOTAL_BANK) is False        # has a reported revenue total (JPM)
    assert _is_no_total_bank(_NON_FINANCIAL) is False     # no components
    assert _is_no_total_bank(None) is False


def test_sanitizer_drops_revenue_row_only_for_no_total_bank():
    metrics = {m["metric"] for m in _sanitize_bank_financial_highlights(_highlights(), _NO_TOTAL_BANK)["table"]}
    assert metrics == {"Net Interest Income", "Net Income"}  # conflated Revenue row dropped


def test_sanitizer_keeps_revenue_for_total_bank_and_non_financial():
    for metrics in (_TOTAL_BANK, _NON_FINANCIAL):
        rows = {m["metric"] for m in _sanitize_bank_financial_highlights(_highlights(), metrics)["table"]}
        assert "Revenue" in rows and len(rows) == 3


def test_provenance_net_drops_conflated_bank_revenue_at_read_time():
    class _Filing:
        document_url = "https://sec.gov/x"
        sec_url = "https://sec.gov/x"
    out = enrich_financial_highlights(_highlights(), _Filing(), _NO_TOTAL_BANK)
    assert {r["metric"] for r in out["table"]} == {"Net Interest Income", "Net Income"}
    # A bank WITH a reported total keeps its (verifiable) revenue row.
    out2 = enrich_financial_highlights(_highlights(), _Filing(), _TOTAL_BANK)
    assert "Revenue" in {r["metric"] for r in out2["table"]}
