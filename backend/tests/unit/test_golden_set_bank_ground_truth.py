"""P0-4 guardrail (data-quality plan): the bank ground-truth invariant + generator parity.

Two things this locks (CLAUDE.md rule 12 — a rule becomes a machine gate):

1. The COMMITTED golden_set.json JPM 10-K entry carries the two bank revenue components
   (net_interest_income / noninterest_income) and NO conflated `revenue` fact — so gate G5
   (score_bank_revenue_integrity) stays active for JPM and a hand-edit that reverts it fails CI.
2. The GENERATOR (build_golden_set) reproduces that shape: a filer that resolves both interest
   components is a bank, whose conflated revenue total is suppressed and which verifies on the
   components — mirroring the product's FINANCIAL_PROFILES "bank" profile. Without this, a
   `python -m evals.build_golden_set` regen would silently re-add revenue, drop the components,
   and deactivate G5 for JPM with no signal.
"""
import json

from evals.build_golden_set import (
    GOLDEN_PATH,
    _apply_bank_revenue_suppression,
    _is_bank_profile,
    _required_core_metrics,
    METRIC_CONCEPTS,
)

_JPM_NII = 95443000000.0
_JPM_NONINTEREST = 87004000000.0


def _jpm_entry():
    data = json.loads(GOLDEN_PATH.read_text())
    return next(f for f in data["filings"] if f["ticker"] == "JPM" and f["filing_type"] == "10-K")


def test_committed_jpm_entry_has_components_and_no_conflated_revenue():
    gt = {f["metric"]: f["value"] for f in _jpm_entry()["ground_truth"]}
    assert gt.get("net_interest_income") == _JPM_NII
    assert gt.get("noninterest_income") == _JPM_NONINTEREST
    # The conflated total (= NII + noninterest) must NOT be present — banks report components.
    assert "revenue" not in gt


def test_committed_jpm_entry_stays_verified():
    assert _jpm_entry()["verified"] is True


def _facts(*metrics):
    return [{"metric": m, "value": 1.0, "unit": "USD"} for m in metrics]


def test_is_bank_profile_requires_both_components():
    assert _is_bank_profile(_facts("net_interest_income", "noninterest_income", "net_income"))
    assert not _is_bank_profile(_facts("net_interest_income", "net_income"))  # only one → not a bank
    assert not _is_bank_profile(_facts("revenue", "net_income", "eps"))


def test_bank_revenue_suppression_drops_only_for_banks():
    bank = _facts("revenue", "net_income", "eps", "net_interest_income", "noninterest_income")
    kept = {f["metric"] for f in _apply_bank_revenue_suppression(bank)}
    assert "revenue" not in kept
    assert {"net_interest_income", "noninterest_income", "net_income", "eps"} <= kept
    # Non-bank: revenue is retained untouched.
    non_bank = _facts("revenue", "net_income", "eps")
    assert {f["metric"] for f in _apply_bank_revenue_suppression(non_bank)} == {"revenue", "net_income", "eps"}


def test_required_core_metrics_swaps_revenue_for_components_on_banks():
    bank = _facts("net_income", "eps", "net_interest_income", "noninterest_income")
    req = _required_core_metrics(bank)
    assert "revenue" not in req
    assert {"net_income", "eps", "net_interest_income", "noninterest_income"} == req
    # Non-bank keeps the original core set.
    assert _required_core_metrics(_facts("revenue", "net_income", "eps")) == set(METRIC_CONCEPTS)
