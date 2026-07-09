"""P0-4 guardrail (data-quality plan): the bank ground-truth invariant + generator parity.

Two things this locks (CLAUDE.md rule 12 — a rule becomes a machine gate):

1. The COMMITTED golden_set.json JPM 10-K entry's G5 state. The two bank revenue components
   (net_interest_income / noninterest_income) are TEMPORARILY removed — the production extractor
   doesn't emit them, so G5 fired as noise (PR #611). This gate now pins the dormant decision
   (components absent, values in `notes`, no conflated `revenue`); A7/A8 restores them and flips it.
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


def test_committed_jpm_entry_components_dormant_pending_extractor():
    """JPM's two bank-component facts are TEMPORARILY removed → G5 (score_bank_revenue_integrity) is
    dormant for JPM. Reason: the production standardized-metrics extractor doesn't emit net/non-interest
    income, so leaving them in made G5 fire as pure noise that hard-failed the epsilon-zero
    gate_fail gate (PR #611; see RUNBOOK "Dormant G5 bank-component facts"). This gate encodes that
    decision: the components are ABSENT, no conflated `revenue` total sneaks in either, and the values
    live in `notes` for verbatim restoration. **A7/A8 (XBRL metric expansion) restores the two facts and
    flips this test back to asserting their presence.**"""
    entry = _jpm_entry()
    gt = {f["metric"]: f["value"] for f in entry["ground_truth"]}
    assert "net_interest_income" not in gt and "noninterest_income" not in gt
    # Still no conflated total — a bank reports components, so `revenue` must never appear.
    assert "revenue" not in gt
    # Removed values preserved in notes so A7/A8 can restore them verbatim.
    assert str(int(_JPM_NII)) in entry["notes"] and str(int(_JPM_NONINTEREST)) in entry["notes"]


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
