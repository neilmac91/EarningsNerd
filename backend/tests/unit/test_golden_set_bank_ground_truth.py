"""P0-4 guardrail (data-quality plan): the bank ground-truth invariant + generator parity.

Two things this locks (CLAUDE.md rule 12 — a rule becomes a machine gate):

1. The COMMITTED golden_set.json JPM 10-K entry's G5 state. Both bank revenue components
   are restored after statement-financials graduated in #690. Their exact filing values and
   absence of a conflated revenue fact remain pinned.
2. The GENERATOR (build_golden_set) reproduces the bank shape: a filer that resolves both interest
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


def test_committed_jpm_entry_components_restored_after_extractor():
    """WS-6 restores the component-presence assertion planned by the earlier #611 guard."""
    entry = _jpm_entry()
    gt = {f["metric"]: f["value"] for f in entry["ground_truth"]}
    assert gt["net_interest_income"] == _JPM_NII
    assert gt["noninterest_income"] == _JPM_NONINTEREST
    # Keep G5 component-oriented: a total must not replace the two income legs.
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
