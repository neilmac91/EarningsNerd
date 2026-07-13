"""Offline tests for the eval regression gate (B1).

Deterministic, no network/AI: they prove the per-dimension diff and the hard-fail/warn
classification are correct independent of any model run."""
from evals.regression_gate import (
    compare_candidate,
    evaluate_report,
)

# A pinned-baseline stats block matching production: clean gates, ~1.0 precision/coverage.
BASELINE_STATS = {
    "gate_fail_rate": 0.0,
    "mean_numeric_precision": 1.0,
    "mean_coverage": 1.0,
    "mean_numeric_accuracy": 0.9167,
    "pass_rate": 0.75,
    "aggregate_stdev": 0.065,
    "schema_valid_rate": 0.0,
    "mean_financial_depth": 0.8333,
}
BASELINE = {"golden_set_size": 21, "runs_per_candidate": 3, "candidates": {"baseline": BASELINE_STATS}}


def _hard(findings):
    return [f for f in findings if f.severity == "HARD"]


def _warn(findings):
    return [f for f in findings if f.severity == "WARN"]


def test_identical_candidate_is_a_clean_pass():
    findings = compare_candidate(BASELINE_STATS, dict(BASELINE_STATS), "baseline")
    assert findings == []


def test_improvements_never_trip_the_gate():
    better = dict(BASELINE_STATS)
    better.update(mean_numeric_accuracy=1.0, mean_coverage=1.0, pass_rate=0.9,
                  aggregate_stdev=0.01, schema_valid_rate=1.0, mean_financial_depth=1.0)
    findings = compare_candidate(BASELINE_STATS, better, "baseline")
    assert findings == []  # moving the right way is never a regression


def test_gate_fail_rate_increase_is_hard():
    cand = dict(BASELINE_STATS, gate_fail_rate=0.05)
    hard = _hard(compare_candidate(BASELINE_STATS, cand))
    assert len(hard) == 1 and hard[0].metric == "gate_fail_rate"


def test_precision_drop_beyond_tolerance_is_hard():
    cand = dict(BASELINE_STATS, mean_numeric_precision=0.93)  # -0.07 > 0.05 tol
    hard = _hard(compare_candidate(BASELINE_STATS, cand))
    assert any(f.metric == "mean_numeric_precision" for f in hard)


def test_precision_drop_within_tolerance_is_not_a_failure():
    cand = dict(BASELINE_STATS, mean_numeric_precision=0.97)  # -0.03 <= 0.05 tol
    assert _hard(compare_candidate(BASELINE_STATS, cand)) == []


def test_coverage_drop_is_hard():
    cand = dict(BASELINE_STATS, mean_coverage=0.90)  # -0.10 > 0.05 tol
    hard = _hard(compare_candidate(BASELINE_STATS, cand))
    assert any(f.metric == "mean_coverage" for f in hard)


def test_numeric_accuracy_uses_a_looser_band():
    # -0.08 is within the 0.10 recall band (noisy on small subsets) → not hard.
    near = dict(BASELINE_STATS, mean_numeric_accuracy=0.84)
    assert _hard(compare_candidate(BASELINE_STATS, near)) == []
    # -0.12 clears the band → hard.
    far = dict(BASELINE_STATS, mean_numeric_accuracy=0.80)
    assert any(f.metric == "mean_numeric_accuracy" for f in _hard(compare_candidate(BASELINE_STATS, far)))


def test_pass_rate_drop_is_warn_not_hard():
    cand = dict(BASELINE_STATS, pass_rate=0.60)  # -0.15
    findings = compare_candidate(BASELINE_STATS, cand)
    assert _hard(findings) == []
    assert any(f.metric == "pass_rate" for f in _warn(findings))


def test_stdev_increase_is_warn():
    cand = dict(BASELINE_STATS, aggregate_stdev=0.20)  # +0.135
    findings = compare_candidate(BASELINE_STATS, cand)
    assert _hard(findings) == []
    assert any(f.metric == "aggregate_stdev" for f in _warn(findings))


def test_evaluate_report_flags_hard_regression_across_candidates():
    report = {"summary": {"baseline": dict(BASELINE_STATS, mean_coverage=0.80)}}
    findings, notes = evaluate_report(report, BASELINE)
    assert _hard(findings) and notes == []


def test_unknown_candidate_is_noted_not_failed():
    report = {"summary": {"some-new-model": dict(BASELINE_STATS)}}
    findings, notes = evaluate_report(report, BASELINE)
    assert findings == []
    assert any("some-new-model" in n for n in notes)


def test_candidate_filter_scopes_the_diff():
    report = {"summary": {
        "baseline": dict(BASELINE_STATS, mean_coverage=0.80),  # would fail
        "other": dict(BASELINE_STATS),
    }}
    # Only gate 'other' (which has no pinned baseline) → no findings, one note.
    findings, notes = evaluate_report(report, BASELINE, only="other")
    assert findings == []
    assert any("other" in n for n in notes)


def test_missing_metric_in_report_is_skipped_not_crashed():
    # A report summary lacking a metric the baseline has must not raise.
    partial = {"gate_fail_rate": 0.0, "mean_coverage": 1.0}
    findings = compare_candidate(BASELINE_STATS, partial, "baseline")
    assert _hard(findings) == []


def test_citation_checked_collapse_is_warn_not_hard():
    # The companion VOLUME floor (staff review on #626): an evidence-emission collapse would
    # read as IMPROVED fidelity on the one-sided ratio — the checked count must self-announce.
    base = dict(BASELINE_STATS, mean_citation_checked=6.5)
    collapsed = dict(base, mean_citation_checked=4.0)  # -2.5 > 2.0 tol
    findings = compare_candidate(base, collapsed)
    assert _hard(findings) == []
    assert any(f.metric == "mean_citation_checked" for f in _warn(findings))


def test_citation_checked_ordinary_mix_shift_is_clean():
    # A volume signal, not a quality bar: a ~1.5 drop (evidence-mix shift) stays silent.
    base = dict(BASELINE_STATS, mean_citation_checked=6.5)
    assert compare_candidate(base, dict(base, mean_citation_checked=5.0)) == []


def test_citation_checked_unpinned_baseline_stays_inert():
    # Before a re-pin records the count, the gate must skip it entirely (the advisory-until-
    # pinned convention every new dimension ships under).
    cand = dict(BASELINE_STATS, mean_citation_checked=0.5)
    assert compare_candidate(BASELINE_STATS, cand) == []
