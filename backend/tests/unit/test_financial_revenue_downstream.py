"""Downstream wiring for financial-institution revenue (filing 528): facts raw_tag propagation,
the What-Changed component deltas + concept-flip guard, provenance mapping, and summary inference.
All pure functions — no DB, no network."""
import pytest

from app.services.facts_service import normalize_standardized_to_facts
from app.services.dashboard_feed_service import compute_what_changed
from app.services.provenance_service import map_metric_to_xbrl_key
from app.schemas.summary import _infer_xbrl_metric

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
