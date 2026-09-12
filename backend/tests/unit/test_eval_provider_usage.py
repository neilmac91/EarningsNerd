"""Per-attempt provider usage on the baseline eval route (model-migration measurement).

The baseline route runs the production pipeline, whose ``cost_usd`` is not metered; before this the
report carried no token counts for it, so a Pro-vs-Flash output-length ratio could not be measured.
"""
from __future__ import annotations

import asyncio
import json

import pytest

from app.config import settings
from app.services import ai_metrics
from app.services.openai_service import openai_service
from evals import compare_reports, runner
from evals.schema import GoldenFiling


def _usage(prompt=None, completion=None, hit=None, miss=None, reasoning=None):
    return {"prompt_tokens": prompt, "completion_tokens": completion, "total_tokens": None,
            "cache_hit_tokens": hit, "cache_miss_tokens": miss, "reasoning_tokens": reasoning}


def test_observer_collects_only_records_made_under_its_own_task():
    async def scenario():
        async def worker(name, count):
            records, token = ai_metrics.observe_ai_calls()
            try:
                for _ in range(count):
                    await asyncio.sleep(0)
                    ai_metrics.record_ai_call(operation="summary_primary", provider="primary",
                                              actual_model=name, usage={"prompt_tokens": 1, "completion_tokens": 2},
                                              outcome="success")
            finally:
                ai_metrics.stop_observing(token)
            return records

        a, b = await asyncio.gather(worker("model-a", 2), worker("model-b", 3))
        return a, b

    a, b = asyncio.run(scenario())
    assert [r["actual_model"] for r in a] == ["model-a", "model-a"]
    assert [r["actual_model"] for r in b] == ["model-b"] * 3
    # Outside any observer, records are still logged/counted but not collected anywhere.
    ai_metrics.record_ai_call(operation="chat_stream", provider="primary", actual_model="model-c",
                              usage=None, outcome="error")
    assert all(r["actual_model"] != "model-c" for r in a + b)


def test_summarize_provider_calls_sums_reported_counters_and_keeps_unknowns_unknown():
    records = [
        {"operation": "summary_primary", "actual_model": "deepseek-v4-pro", "usage": _usage(40000, 2600, 39000, 1000)},
        {"operation": "section_recovery", "actual_model": "deepseek-v4-pro", "usage": _usage(9000, 400, None, None)},
        {"operation": "section_recovery", "actual_model": None, "usage": _usage()},
    ]
    folded = runner.summarize_provider_calls(records)
    assert folded["calls"] == 3 and folded["unknown_calls"] == 1
    assert folded["operations"] == {"summary_primary": 1, "section_recovery": 2}
    assert folded["prompt_tokens"] == 49000 and folded["completion_tokens"] == 3000
    # Cache split is summed only where reported — never padded with zeros for the unknown call.
    assert folded["cache_hit_tokens"] == 39000 and folded["cache_miss_tokens"] == 1000
    assert folded["actual_models"] == ["deepseek-v4-pro"]
    assert runner.summarize_provider_calls([]) == {
        "calls": 0, "unknown_calls": 0, "operations": {}, "actual_models": [],
        "prompt_tokens": None, "completion_tokens": None, "cache_hit_tokens": None, "cache_miss_tokens": None,
        "reasoning_tokens": None,
    }


def test_usage_stats_report_how_many_attempts_carried_usage():
    rows = [
        {"provider_usage": {"calls": 1, "prompt_tokens": 40000, "completion_tokens": 2000, "cache_hit_tokens": 100,
                            "cache_miss_tokens": 39900, "actual_models": ["deepseek-v4-pro"]}},
        {"provider_usage": {"calls": 2, "prompt_tokens": 50000, "completion_tokens": 3000, "cache_hit_tokens": None,
                            "cache_miss_tokens": None, "actual_models": ["deepseek-flash"]}},
        {"error": "TimeoutError"},   # legacy / failed row: no usage at all
    ]
    stats = runner._usage_stats(rows)
    assert stats["usage_attempts"] == 2 and stats["provider_calls"] == 3
    assert stats["mean_completion_tokens"] == 2500.0 and stats["total_completion_tokens"] == 5000
    assert stats["total_cache_hit_tokens"] == 100 and stats["total_cache_miss_tokens"] == 39900
    assert stats["actual_models"] == ["deepseek-v4-pro", "deepseek-flash"]
    empty = runner._usage_stats([{"error": "x"}])
    assert empty["usage_attempts"] == 0 and empty["mean_completion_tokens"] is None
    assert empty["total_cache_hit_tokens"] is None


@pytest.mark.asyncio
async def test_baseline_attempt_carries_the_pipelines_provider_usage(monkeypatch):
    monkeypatch.setattr(settings, "STREAM_SECTION_REVEAL", False)

    async def fake_summary(*args, **kwargs):
        # The pipeline records one provider attempt per call; the runner must see it.
        ai_metrics.record_ai_call(operation="summary_primary", provider="primary", actual_model="deepseek-flash",
                                  usage={"prompt_tokens": 41000, "completion_tokens": 2700,
                                         "prompt_cache_hit_tokens": 40000, "prompt_cache_miss_tokens": 1000},
                                  outcome="success")
        return {"status": "complete", "raw_summary": {"sections": {}}, "summary": "ok"}

    monkeypatch.setattr(openai_service, "summarize_filing", fake_summary)
    monkeypatch.setattr(runner, "_baseline_to_canonical", lambda summary: {"executive_summary": "ok"})
    class Score:
        schema_valid = True
        repaired = False
        passed_gates = True

        def aggregate(self):
            return 1.0

    monkeypatch.setattr(runner, "score_summary", lambda *a, **k: Score())
    monkeypatch.setattr(runner, "measure_figures", lambda *a, **k: {})
    filing = GoldenFiling("AAPL", "1", "accession", "10-K", "https://example.test", "Fixture")
    result = await runner._attempt("baseline", filing,
                                   {"filing_text": "raw", "excerpt": "chosen", "xbrl_metrics": {}},
                                   run_index=0, judge_model=None)
    assert result["error"] is None
    assert result["provider_usage"] == {
        "calls": 1, "unknown_calls": 0, "operations": {"summary_primary": 1},
        "actual_models": ["deepseek-flash"], "prompt_tokens": 41000, "completion_tokens": 2700,
        "cache_hit_tokens": 40000, "cache_miss_tokens": 1000, "reasoning_tokens": None,
    }
    # The observer binding does not leak past the attempt.
    assert ai_metrics._observer.get() is None
    stats = runner._summarize([{**result, "candidate": "baseline"}])["baseline"]
    assert stats["mean_completion_tokens"] == 2700.0 and stats["usage_attempts"] == 1
    assert stats["actual_models"] == ["deepseek-flash"]


def _row(ticker, run, agg, cite, tokens=None, error=None, gates=True, candidate="baseline"):
    row = {"candidate": candidate, "ticker": ticker, "filing_type": "10-K", "run": run, "aggregate": agg,
           "score": {"citation_fidelity": cite, "numeric_precision": 1.0, "coverage": 1.0},
           "latency_seconds": 30.0, "passed_gates": gates, "error": error}
    if tokens is not None:
        row["provider_usage"] = {"completion_tokens": tokens, "prompt_tokens": 40000}
    return row


def test_compare_reports_pairs_by_identity_and_excludes_errors_from_means(tmp_path, capsys):
    a = {"results": [_row("AAPL", 0, 1.0, 0.7), _row("AAPL", 1, 1.0, 0.7), _row("MSFT", 0, 0.9, 0.5),
                     _row("TSLA", 0, 1.0, 0.8)], "harness": {"model": "deepseek-v4-pro"}}
    b = {"results": [_row("AAPL", 0, 0.95, 0.75, tokens=3000), _row("AAPL", 1, 1.0, 0.7, tokens=2500),
                     _row("MSFT", 0, None, None, error="TimeoutError", gates=False),
                     _row("NVDA", 0, 1.0, 0.8, tokens=2000)], "harness": {"model": "deepseek-flash"}}
    comparison = compare_reports.pair_reports(a, b)
    assert [(e["ticker"], e["run"]) for e in comparison["paired"]] == [("AAPL", 0), ("AAPL", 1)]
    assert [(e["ticker"], e["run"]) for e in comparison["errored"]] == [("MSFT", 0)]
    assert comparison["only_in_a"] == [("baseline", "TSLA", "10-K", 0)]
    assert comparison["only_in_b"] == [("baseline", "NVDA", "10-K", 0)]
    totals = comparison["candidates"]["baseline"]
    assert totals["aggregate"]["mean_delta"] == -0.025 and totals["aggregate"]["worsened"] == 1
    assert totals["citation_fidelity"]["mean_delta"] == 0.025
    # Legacy report A has no usage: token deltas are n/a, means on B still reported.
    assert totals["completion_tokens"]["n"] == 0 and totals["completion_tokens"]["mean_b"] == 2750.0
    (tmp_path / "a.json").write_text(json.dumps(a))
    (tmp_path / "b.json").write_text(json.dumps(b))
    assert compare_reports.main([str(tmp_path / "a.json"), str(tmp_path / "b.json"),
                                 "--json", str(tmp_path / "out.json")]) == 0
    out = capsys.readouterr().out
    assert "2 paired attempts, gates lost 0" in out and "TimeoutError" in out and "n/a" in out
    assert json.loads((tmp_path / "out.json").read_text())["harness"]["b"] == {"model": "deepseek-flash"}
