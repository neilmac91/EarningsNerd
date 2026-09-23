"""Offline admission and durable stop checks for the E7 acceptance budget."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

from evals.acceptance_budget import BudgetLedger, BudgetStopped


def _pricing(**changes):
    now = datetime.now(timezone.utc)
    value = {
        "model": "deepseek-flash",
        "base_url": "https://api.deepseek.com/v1",
        "official_source": "https://api-docs.deepseek.com/quick_start/pricing",
        "verified_at": (now - timedelta(minutes=1)).isoformat(),
        "valid_until": (now + timedelta(days=1)).isoformat(),
        "uncached_input_per_million": "1",
        "max_output_per_million": "4000000",  # fixture: two tiny requests fit, three do not
    }
    return dict(value, **changes)


def _request(**changes):
    value = {"model": "deepseek-flash", "messages": [
        {"role": "system", "content": "Use only the selected filing."},
        {"role": "user", "content": "Summarize this filing."},
    ], "temperature": 0, "max_tokens": 1, "response_format": {"type": "json_object"}}
    return dict(value, **changes)


def test_concurrent_requests_cannot_exceed_the_persisted_usd_ceiling(tmp_path):
    path = tmp_path / "acceptance.sqlite"
    ledger = BudgetLedger(path, _pricing(), "approved-e7")
    first = ledger.reserve("slot-1", _request(), "summary_primary", "https://api.deepseek.com/v1")
    ledger.settle(first, {"prompt_tokens": 12, "completion_tokens": 1, "total_tokens": 13},
                  "deepseek-flash", "success")

    def attempt(index):
        try:
            return ledger.reserve(f"slot-{index}", _request(), "summary_primary",
                                  "https://api.deepseek.com/v1")
        except BudgetStopped:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, (2, 3)))
    assert sum(result is not None for result in results) == 1
    snap = BudgetLedger(path, ledger.pricing, "approved-e7").snapshot()
    assert snap["requests"] == 2 and float(snap["reserved_usd"]) < 10
    assert snap["known_usage_upper_usd"] != "0"  # recorded, never refunded
    assert snap["stop_reason"] == "acceptance request or USD 10 ceiling exhausted"
    with pytest.raises(BudgetStopped):
        ledger.reserve("slot-4", _request(), "summary_primary", "https://api.deepseek.com/v1")


@pytest.mark.parametrize("changes,operation,base_url", [
    ({"model": "other-model"}, "summary_primary", "https://api.deepseek.com/v1"),
    ({"tools": []}, "summary_primary", "https://api.deepseek.com/v1"),
    ({"messages": [{"role": "user", "content": [{"type": "image_url"}]}]},
     "summary_primary", "https://api.deepseek.com/v1"),
    ({"max_tokens": 501}, "section_recovery", "https://api.deepseek.com/v1"),
    ({"messages": [{"role": "user", "content": "x" * 21_000}]},
     "section_recovery", "https://api.deepseek.com/v1"),
    ({}, "summary_primary", "https://other.example/v1"),
])
def test_unpriced_or_oversize_request_stops_durably(tmp_path, changes, operation, base_url):
    ledger = BudgetLedger(tmp_path / "budget.sqlite", _pricing(), "approved-e7")
    with pytest.raises(BudgetStopped):
        ledger.reserve("slot", _request(**changes), operation, base_url)
    assert ledger.snapshot()["requests"] == 0
    assert ledger.snapshot()["stop_reason"]


def test_usage_over_reservation_stops_without_refund(tmp_path):
    ledger = BudgetLedger(tmp_path / "budget.sqlite", _pricing(), "approved-e7")
    number = ledger.reserve("slot", _request(), "summary_primary", "https://api.deepseek.com/v1")
    with pytest.raises(BudgetStopped):
        ledger.settle(number, {"prompt_tokens": 1, "completion_tokens": 2},
                      "deepseek-flash", "success")
    snap = ledger.snapshot()
    assert snap["pending"] == 1 and snap["requests"] == 1 and snap["stop_reason"]


def test_actual_model_mismatch_stops_without_refund(tmp_path):
    ledger = BudgetLedger(tmp_path / "budget.sqlite", _pricing(), "approved-e7")
    number = ledger.reserve("slot", _request(), "summary_primary", "https://api.deepseek.com/v1")
    with pytest.raises(BudgetStopped):
        ledger.settle(number, None, "unpriced-fallback", "success")
    assert ledger.snapshot()["pending"] == 1 and ledger.snapshot()["stop_reason"]


@pytest.mark.parametrize(("field", "value"), [
    ("model", "deepseek-other"),
    ("base_url", "https://api.deepseek.com/v1/"),
    ("official_source", "https://deepseek.com/pricing"),
    ("uncached_input_per_million", "2"),
    ("max_output_per_million", "2"),
])
def test_reopening_with_changed_pricing_latches_original_programme(tmp_path, field, value):
    path = tmp_path / "budget.sqlite"
    original = BudgetLedger(path, _pricing(), "approved-e7")
    changed = dict(original.pricing, **{field: value})
    with pytest.raises(BudgetStopped):
        BudgetLedger(path, changed, "approved-e7")
    assert original.snapshot()["stop_reason"] == "programme or pricing identity changed"


def test_newer_pricing_observation_preserves_tariff_and_reservations(tmp_path):
    path = tmp_path / "budget.sqlite"
    original = BudgetLedger(path, _pricing(), "approved-e7")
    reservation = original.reserve(
        "slot-1", _request(), "summary_primary", "https://api.deepseek.com/v1")
    original.settle(reservation, {"prompt_tokens": 1, "completion_tokens": 1},
                    "deepseek-flash", "success")
    original_snapshot = original.snapshot()

    now = datetime.now(timezone.utc)
    refreshed = dict(original.pricing, verified_at=now.isoformat(),
                     valid_until=(now + timedelta(days=2)).isoformat())
    reopened = BudgetLedger(path, refreshed, "approved-e7")
    refreshed_snapshot = reopened.snapshot()
    assert refreshed_snapshot["pricing_hash"] == original_snapshot["pricing_hash"]
    assert refreshed_snapshot["requests"] == 1
    assert refreshed_snapshot["reserved_usd"] == original_snapshot["reserved_usd"]
    assert refreshed_snapshot["stop_reason"] is None

    with pytest.raises(BudgetStopped, match="pricing observation moved backwards"):
        BudgetLedger(path, original.pricing, "approved-e7")
    assert reopened.snapshot()["stop_reason"] == "pricing observation moved backwards"
