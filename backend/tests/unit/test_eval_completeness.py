"""A perfect scored subset cannot certify an operationally incomplete evaluation."""
import copy
import json

import pytest

from evals import regression_gate


@pytest.fixture
def report():
    return {
        "harness": {"candidates": ["baseline"], "runs_per_candidate": 2,
                    "filings": [{"ticker": "AAPL", "filing_type": "10-K"},
                                {"ticker": "BABA", "filing_type": "20-F"}]},
        "summary": {"baseline": {"n": 4, "scored": 4, "errors": 0, "gate_fail_rate": 0,
                                 "mean_coverage": 1, "mean_aggregate": 1}},
        "results": [{"candidate": "baseline", "ticker": ticker, "filing_type": form,
                     "run": run, "score": {"coverage": 1}, "aggregate": 1, "passed_gates": True}
                    for ticker, form in [("AAPL", "10-K"), ("BABA", "20-F")] for run in range(2)],
    }


BASELINE = {"candidates": {"baseline": {"gate_fail_rate": 0, "mean_coverage": 1}}}


def _hard(report, only=None):
    findings, _ = regression_gate.evaluate_report(report, BASELINE, only)
    return {f.metric for f in findings if f.severity == "HARD"}


def test_complete_population_passes_without_mutating_scored_quality(report, tmp_path, capsys):
    before = copy.deepcopy(report)
    path, baseline = tmp_path / "report.json", tmp_path / "baseline.json"
    path.write_text(json.dumps(report))
    baseline.write_text(json.dumps(BASELINE))
    assert regression_gate.main([str(path), "--baseline", str(baseline)]) == 0
    assert "expected=4 attempted=4 scored=4 errors=0; quality means use scored outputs only" in capsys.readouterr().out
    assert report == before


@pytest.mark.parametrize("defect", ["execution", "score_null", "score_empty", "summary_error"])
def test_errors_and_absent_scores_block_even_perfect_scored_means(report, defect):
    row = report["results"][2]
    if defect == "execution":
        row["error"] = "TimeoutError"
        report["summary"]["baseline"]["errors"] = 1
    elif defect == "summary_error":
        report["summary"]["baseline"]["errors"] = 1
    else:
        row["score"] = None if defect == "score_null" else {}
        report["summary"]["baseline"]["scored"] = 3
    before = copy.deepcopy(report)
    assert ("execution_errors" if defect in ("execution", "summary_error") else "missing_scores") in _hard(report)
    assert report == before
    assert report["summary"]["baseline"]["mean_aggregate"] == 1


@pytest.mark.parametrize("defect", ["missing", "whole_filing", "last_repeat", "duplicate", "foreign", "bad_run"])
def test_exact_requested_attempt_identities_are_required(report, defect):
    if defect == "missing":
        report["results"].pop()
    elif defect == "whole_filing":
        report["results"] = report["results"][:2]
    elif defect == "last_repeat":
        report["results"] = [r for r in report["results"] if r["run"] == 0]
    elif defect == "duplicate":
        report["results"].append(copy.deepcopy(report["results"][0]))
    elif defect == "foreign":
        report["results"][0]["ticker"] = "FOREIGN"
    else:
        report["results"][0]["run"] = True
    # Honest observed counts must not conceal divergence from the requested population.
    report["summary"]["baseline"].update(n=len(report["results"]), scored=len(report["results"]))
    assert "incomplete_attempts" in _hard(report)
    if defect == "bad_run":
        assert "attempt_identity" in _hard(report)


@pytest.mark.parametrize("field", ["n", "scored", "errors"])
@pytest.mark.parametrize("value", [None, True, 99])
def test_summary_attempt_denominators_must_match_rows(report, field, value):
    report["summary"]["baseline"][field] = value
    assert "attempt_counts" in _hard(report)


@pytest.mark.parametrize("defect", ["missing", "empty_candidates", "duplicate_candidates", "zero_runs",
                                    "bool_runs", "empty_filings", "duplicate_filings", "bad_filing"])
def test_missing_or_invalid_requested_manifest_never_passes(report, defect):
    harness = report["harness"]
    if defect == "missing":
        del report["harness"]
    elif defect == "empty_candidates":
        harness["candidates"] = []
    elif defect == "duplicate_candidates":
        harness["candidates"] *= 2
    elif defect == "zero_runs":
        harness["runs_per_candidate"] = 0
    elif defect == "bool_runs":
        harness["runs_per_candidate"] = True
    elif defect == "empty_filings":
        harness["filings"] = []
    elif defect == "duplicate_filings":
        harness["filings"] *= 2
    else:
        harness["filings"][0]["ticker"] = None
    assert "attempt_manifest" in _hard(report)


@pytest.mark.parametrize("defect", ["no_summary", "no_results", "malformed_result", "empty_results",
                                    "unplanned_row", "unplanned_summary", "missing_candidate"])
def test_missing_and_unexpected_candidates_cannot_disappear(report, defect):
    if defect == "no_summary":
        del report["summary"]
    elif defect == "no_results":
        del report["results"]
    elif defect == "malformed_result":
        report["results"][0] = None
    elif defect == "empty_results":
        report["results"] = []
    elif defect == "unplanned_row":
        report["results"].append(dict(report["results"][0], candidate="unrequested"))
    elif defect == "unplanned_summary":
        report["summary"]["unrequested"] = dict(report["summary"]["baseline"])
    else:
        report["harness"]["candidates"].append("missing")
    metrics = _hard(report)
    expected = {"no_summary": "attempt_summary", "no_results": "attempt_results",
                "malformed_result": "attempt_results", "empty_results": "missing_scores",
                "unplanned_row": "unexpected_candidates", "unplanned_summary": "unexpected_candidates",
                "missing_candidate": "attempt_summary"}[defect]
    assert expected in metrics


def test_candidate_filter_still_requires_requested_complete_candidate(report):
    report["harness"]["candidates"].append("other")
    report["summary"]["other"] = dict(report["summary"]["baseline"], mean_coverage=0)
    report["results"] += [dict(r, candidate="other") for r in report["results"]]
    assert _hard(report, only="baseline") == set()
    assert "selected_candidate" in _hard(report, only="typo")
    report["results"].pop(0)
    assert "incomplete_attempts" in _hard(report, only="baseline")


def test_failed_cli_reports_counts_without_fabricating_quality_zero(report, tmp_path, capsys):
    report["results"][2].update(error="TimeoutError", score=None)
    report["summary"]["baseline"].update(errors=1, scored=3)
    path, baseline = tmp_path / "report.json", tmp_path / "baseline.json"
    path.write_text(json.dumps(report))
    baseline.write_text(json.dumps(BASELINE))
    before = path.read_bytes()
    assert regression_gate.main([str(path), "--baseline", str(baseline)]) == 1
    output = capsys.readouterr().out
    assert "[HARD] baseline: execution_errors" in output and "[HARD] baseline: missing_scores" in output
    assert "expected=4 attempted=4 scored=3 errors=1" in output and "FAIL" in output
    assert "mean_aggregate" not in output and path.read_bytes() == before
