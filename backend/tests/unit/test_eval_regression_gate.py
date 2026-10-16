"""Offline tests for the eval regression gate (B1).

Deterministic, no network/AI: they prove the per-dimension diff and the hard-fail/warn
classification are correct independent of any model run."""
import json
from pathlib import Path

import pytest

from evals import regression_gate
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


def _report(summary):
    return {
        "harness": {"candidates": list(summary), "runs_per_candidate": 1,
                    "filings": [{"ticker": "AAPL", "filing_type": "10-K"}]},
        "summary": {c: dict(s, n=1, scored=1, errors=0) for c, s in summary.items()},
        "results": [{"candidate": c, "ticker": "AAPL", "filing_type": "10-K", "run": 0,
                     "score": {"coverage": s["mean_coverage"]}} for c, s in summary.items()],
    }


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
    report = _report({"baseline": dict(BASELINE_STATS, mean_coverage=0.80)})
    findings, notes = evaluate_report(report, BASELINE)
    assert _hard(findings) and notes == [
        "baseline: expected=1 attempted=1 scored=1 errors=0; quality means use scored outputs only",
        "baseline: native-section share unavailable (no coverage_inventory); unavailable is not measured zero",
    ]


def test_unknown_candidate_is_noted_not_failed():
    report = _report({"some-new-model": dict(BASELINE_STATS)})
    findings, notes = evaluate_report(report, BASELINE)
    assert findings == []
    assert any("some-new-model" in n for n in notes)


def test_candidate_filter_scopes_the_diff():
    report = _report({
        "baseline": dict(BASELINE_STATS, mean_coverage=0.80),  # would fail
        "other": dict(BASELINE_STATS),
    })
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


# --- Native-section provenance (E28): absolute floors read from `results` -----------------------

GOLDEN = json.loads((Path(regression_gate.__file__).with_name("golden_set.json")).read_text())["filings"]
PINNED_ON = {**BASELINE, "harness": {"use_edgartools_sections": True}}


def _provenance_report(source_for, *, runs=2, flag=True, inventory=True):
    """A complete report over the golden cohort; ``source_for(filing)`` names each excerpt's source.
    The inventory is what production's ``excerpt_provenance`` writes, not a hand-built shape."""
    from app.services.excerpt_provenance import excerpt_provenance

    rows = []
    for filing in GOLDEN:
        for run in range(runs):
            row = {"candidate": "baseline", "ticker": filing["ticker"], "filing_type": filing["filing_type"],
                   "run": run, "score": {"coverage": 1.0}}
            if inventory:
                source = source_for(filing)
                row["coverage_inventory"] = excerpt_provenance(
                    "x" * 9000, accession=filing["accession_number"], source=source,
                    sections={"mda": "m" * 300} if source == "edgartools" else None,
                )
            rows.append(row)
    return {
        "harness": {"candidates": ["baseline"], "runs_per_candidate": runs, "use_edgartools_sections": flag,
                    "filings": [{"ticker": f["ticker"], "filing_type": f["filing_type"]} for f in GOLDEN]},
        "summary": {"baseline": dict(BASELINE_STATS, n=len(rows), scored=len(rows), errors=0)},
        "results": rows,
    }


def _native_unless(*tickers):
    return lambda f: ("regex_fallback" if f["filing_type"] == "6-K" or f["ticker"] in tickers else "edgartools")


def _native(findings):
    return [f for f in findings if f.metric.startswith(("native_section", "use_edgartools"))]


def test_revived_native_sections_are_clean_and_name_the_known_miss():
    findings, notes = evaluate_report(_provenance_report(_native_unless("ASML")), PINNED_ON)
    assert _native(findings) == []
    assert ("baseline: native-section excerpts 62 of 64 eligible attempts (unavailable=0); "
            "non-native: ASML 20-F x2") in notes


def test_the_e28_collapse_is_a_hard_failure(tmp_path):
    report = _provenance_report(lambda f: "regex_fallback")
    findings, _ = evaluate_report(report, PINNED_ON)
    assert [(f.severity, f.metric, f.candidate_value) for f in _native(findings)] == [("HARD", "native_section_share", 0.0)]
    path = tmp_path / "eval_20261016T000000Z.json"
    path.write_text(json.dumps(report))
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps(PINNED_ON))
    assert regression_gate.main([str(path), "--baseline", str(baseline)]) == 1


@pytest.mark.parametrize(("misses", "severity"), [
    (("ASML", "JPM"), "WARN"),  # one more filing: 60 of 64
    (("ASML", "JPM", "TSM"), "WARN"),  # two more: 58 of 64
    (("ASML", "JPM", "TSM", "PLD"), "HARD"),  # three more: 56 of 64
])
def test_extra_misses_warn_then_fail(misses, severity):
    findings, _ = evaluate_report(_provenance_report(_native_unless(*misses)), PINNED_ON)
    assert [(f.severity, f.metric) for f in _native(findings)] == [(severity, "native_section_share")]


def test_a_broken_form_is_a_hard_failure():
    ten_q_broken = lambda f: "regex_fallback" if f["filing_type"] in ("6-K", "10-Q") or f["ticker"] == "ASML" else "edgartools"  # noqa: E731
    findings, _ = evaluate_report(_provenance_report(ten_q_broken), PINNED_ON)
    assert [f.severity for f in _native(findings)] == ["HARD"]


def test_sections_off_warns_against_a_pin_measured_on_and_fails_if_rows_contradict_it():
    findings, _ = evaluate_report(_provenance_report(lambda f: "regex_fallback", flag=False), PINNED_ON)
    assert [(f.severity, f.metric) for f in _native(findings)] == [("WARN", "use_edgartools_sections")]
    findings, _ = evaluate_report(_provenance_report(_native_unless("ASML"), flag=False), PINNED_ON)
    assert ("HARD", "native_section_share") in [(f.severity, f.metric) for f in _native(findings)]


def test_reports_without_inventory_or_eligible_forms_get_a_note_not_a_finding():
    findings, notes = evaluate_report(_provenance_report(lambda f: "regex_fallback", inventory=False), PINNED_ON)
    assert _native(findings) == []
    assert "baseline: native-section share unavailable (no coverage_inventory); unavailable is not measured zero" in notes
    six_k_only = _provenance_report(_native_unless())
    six_k_only["results"] = [r for r in six_k_only["results"] if r["filing_type"] == "6-K"]
    findings, notes = evaluate_report(six_k_only, PINNED_ON)
    assert _native(findings) == []
    assert "baseline: native sections not applicable (no 10-K/10-Q/20-F attempts)" in notes


def test_a_scored_eligible_attempt_without_inventory_is_malformed_evidence():
    report = _provenance_report(_native_unless("ASML"))
    eligible = next(r for r in report["results"] if r["filing_type"] == "10-K")
    del eligible["coverage_inventory"]
    findings, _ = evaluate_report(report, PINNED_ON)
    assert ("HARD", "native_section_evidence", 1) in [(f.severity, f.metric, f.candidate_value) for f in findings]
    errored = _provenance_report(_native_unless("ASML"))
    failed_grounding = next(r for r in errored["results"] if r["filing_type"] == "10-K")
    del failed_grounding["coverage_inventory"]
    failed_grounding["error"] = "grounding failed"
    assert "native_section_evidence" not in [f.metric for f in evaluate_report(errored, PINNED_ON)[0]]


def test_attempts_without_inventory_are_left_out_of_the_share():
    # Four failed groundings carry no inventory: unavailable, so the share is 58 of 60 (clean), never
    # 58 of 64 (a WARN).
    report = _provenance_report(_native_unless("ASML"))
    for row in [r for r in report["results"] if r["filing_type"] == "10-K"][:4]:
        del row["coverage_inventory"]
        row["error"], row["score"] = "grounding failed", None
    findings, notes = evaluate_report(report, PINNED_ON)
    assert _native(findings) == []
    assert ("baseline: native-section excerpts 58 of 60 eligible attempts (unavailable=4); "
            "non-native: ASML 20-F x2") in notes


def test_amended_forms_are_eligible():
    report = _provenance_report(lambda f: "regex_fallback")
    for row in report["results"]:
        if row["filing_type"] == "10-K":
            row["filing_type"] = "10-K/A"
    assert "native_section_share" in [f.metric for f in _native(evaluate_report(report, PINNED_ON)[0])]


def test_the_gate_reads_the_label_and_forms_the_producers_write():
    """The gate's reference values are themselves pinned to their producers (CLAUDE.md rule 12)."""
    backend = Path(regression_gate.__file__).resolve().parents[1]
    service = (backend / "app/services/summary_generation_service.py").read_text()
    runner = (backend / "evals/runner.py").read_text()
    enrichment = (backend / "app/services/summary_stages/enrichment.py").read_text()
    assert f'source = "{regression_gate._NATIVE_SECTION_SOURCE}"' in service
    assert f'excerpt, source = built, "{regression_gate._NATIVE_SECTION_SOURCE}"' in runner
    assert '{"10-K", "10-Q", "20-F"}' in enrichment
    assert regression_gate._NATIVE_SECTION_FORMS == {"10-K", "10-Q", "20-F"}
