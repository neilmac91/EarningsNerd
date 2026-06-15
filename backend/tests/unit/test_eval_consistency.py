"""Offline test for the runner's consistency aggregation (Artifact 3).

`_summarize` is pure given result dicts, so the pass-rate / variance logic that quantifies the
"hit and miss" problem is provable without any model run."""
from evals.runner import _summarize


def _result(candidate, aggregate, passed_gates, run):
    return {
        "candidate": candidate, "ticker": "AAPL", "filing_type": "10-K", "run": run,
        "score": {"schema_valid": True, "repaired": False, "numeric_accuracy": aggregate,
                  "numeric_precision": 1.0, "coverage": 1.0, "financial_depth": 1.0},
        "aggregate": aggregate, "passed_gates": passed_gates, "judge": None,
        "latency_seconds": 1.0, "cost_usd": 0.0, "error": None,
    }


def test_consistency_pass_rate_and_variance():
    # Same mean, very different consistency: a steady candidate vs. a "hit and miss" one.
    steady = [_result("steady", 0.8, True, i) for i in range(4)]
    swingy = [_result("swingy", v, True, i) for i, v in enumerate([0.4, 1.0, 0.5, 1.0])]
    summary = _summarize(steady + swingy, pass_threshold=0.7)

    assert summary["steady"]["pass_rate"] == 1.0  # all 4 clear 0.7
    assert summary["steady"]["aggregate_stdev"] == 0.0
    # swingy has the same-ish mean but only the two >=0.7 runs pass, and high variance
    assert summary["swingy"]["pass_rate"] == 0.5
    assert summary["swingy"]["aggregate_stdev"] > summary["steady"]["aggregate_stdev"]


def test_gate_failure_blocks_pass_even_above_threshold():
    # A high aggregate that fails a hard gate must NOT count as a PASS (the veto).
    results = [_result("c", 0.95, passed_gates=False, run=0)]
    summary = _summarize(results, pass_threshold=0.7)
    assert summary["c"]["pass_rate"] == 0.0
    assert summary["c"]["gate_fail_rate"] == 1.0
