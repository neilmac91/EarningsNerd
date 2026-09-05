"""Offline measurement contracts; model transport is replaced, measurement logic is real."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import yaml

from app.config import settings
from app.services.ai_readout import DIMENSIONS, JUDGE_MODEL, decode_readout, encode_readout
from app.services.openai_service import openai_service
from evals import figure_measurement, judge, regression_gate, runner, weekly_readout
from evals.schema import GoldenFiling
from scripts import pin_baseline

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.asyncio
async def test_runner_measures_actual_raw_prose_and_retains_replay_input(monkeypatch):
    raw = {"sections": {"value_drivers": {"capital_allocation": "A fabricated $9.7B return."}}}
    summary = {"business_overview": "Overview without that field.", "raw_summary": raw}
    monkeypatch.setattr(openai_service, "summarize_filing", AsyncMock(return_value=summary))
    grounding = {"filing_text": "raw", "excerpt": "Revenue $2.2 billion", "xbrl_metrics": {}}
    result = await runner._run_one("baseline", GoldenFiling("FIX", "1", "a", "10-K", "url", "Fixture"), grounding)
    assert result["error"] is None
    assert result["figure_trace"] == {"status": "measured", "reason": "", "count": 1, "figures": ["9.7b"]}
    assert result["raw_sections"] == raw["sections"] and result["grounding_excerpt"] == grounding["excerpt"]
    assert "9.7" not in result["payload"]["executive_summary"]


def test_figure_measurement_preserves_production_rounding_and_machine_exclusions():
    summary = {
        "raw_summary": {
            "sections": {
                "the_print": {"headline": "$2.2B revenue"},
                "results_that_matter": {"table": [{"current_period": "$99B"}]},
            }
        }
    }
    result = figure_measurement.measure_figures(summary, {"revenue": {"current": {"value": 2_241_000_000}}}, "")
    assert result["status"] == "measured" and result["count"] == 0 and result["figures"] == []


@pytest.mark.parametrize(
    "xbrl,excerpt",
    [
        ({}, ""),
        ({"reporting_currency": "USD"}, "words only"),
        ({"revenue": {"current": {"value": True}}}, ""),
        ({"revenue": {"current": {"value": float("inf")}}}, ""),
    ],
)
def test_figure_measurement_missing_numeric_grounding_is_unavailable(xbrl, excerpt):
    result = figure_measurement.measure_figures(
        {"raw_summary": {"sections": {"the_print": {"headline": "$7B"}}}}, xbrl, excerpt
    )
    assert result["status"] == "unavailable" and result["count"] is None


def test_figure_denominators_and_existing_scores_are_independent():
    score = {"schema_valid": True, "repaired": False, "numeric_accuracy": 1, "coverage": 1, "numeric_precision": 1}
    base = {"candidate": "baseline", "score": score, "aggregate": 1, "passed_gates": True, "error": None}
    rows = [
        {**base, "figure_trace": {"status": "measured", "count": 2}},
        {**base, "figure_trace": {"status": "measured", "count": 0}},
        {**base, "figure_trace": {"status": "unavailable", "count": None}},
        {**base, "error": "provider error", "score": None},
    ]
    out = runner._summarize(rows)["baseline"]
    assert (
        out["mean_untraceable_dollar_figures"],
        out["figure_trace_measured"],
        out["figure_trace_unavailable"],
        out["figure_trace_errors"],
    ) == (1, 2, 1, 1)
    old = runner._summarize([{k: v for k, v in row.items() if k != "figure_trace"} for row in rows])["baseline"]
    assert {
        k: v for k, v in out.items() if not k.startswith("figure_trace") and k != "mean_untraceable_dollar_figures"
    } == {k: v for k, v in old.items() if not k.startswith("figure_trace") and k != "mean_untraceable_dollar_figures"}
    assert figure_measurement.summarize_figures(rows[2:])["mean_untraceable_dollar_figures"] is None


def test_advisory_warn_operates_without_pinned_reference_and_never_fails(tmp_path, capsys):
    stats = {
        "n": 3, "scored": 3, "errors": 0,
        "gate_fail_rate": 0,
        "mean_untraceable_dollar_figures": 2,
        "figure_trace_measured": 2,
        "figure_trace_unavailable": 1,
        "figure_trace_errors": 0,
    }
    report = tmp_path / "report.json"
    report.write_text(json.dumps({
        "summary": {"baseline": stats},
        "harness": {"candidates": ["baseline"], "runs_per_candidate": 3,
                    "filings": [{"ticker": "AAPL", "filing_type": "10-K"}]},
        "results": [{"candidate": "baseline", "ticker": "AAPL", "filing_type": "10-K", "run": run,
                     "score": {"coverage": 1}} for run in range(3)],
    }))
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps({"candidates": {"baseline": {"gate_fail_rate": 0}}}))
    assert regression_gate.main([str(report), "--baseline", str(baseline)]) == 0
    output = capsys.readouterr().out
    assert "[WARN]" in output and "absolute advisory" in output and "no pinned reference measurement" in output
    assert "measured=2 unavailable=1 errors=0" in output
    line = next(line for line in output.splitlines() if "[WARN]" in line)
    assert "vs baseline" not in line and "Δ" not in line and "= 2" in line


def test_markdown_reports_unavailable_figure_denominator(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "REPORTS_DIR", tmp_path)
    stats = runner._summarize([{"candidate": "baseline", "score": None, "error": "failed"}])
    report = runner._write_report(stats, [])
    assert "| baseline | unavailable | 0 | 0 | 1 |" in report.read_text()


@pytest.mark.asyncio
async def test_judge_full_summary_tail_and_actual_input_lengths(monkeypatch):
    payload = {"executive_summary": "a" * 22000, "notable_footnotes": [{"supporting_evidence": "TAIL_SOURCE_EVIDENCE"}]}
    captured = []

    async def transport(system, user, model, tokens):
        captured.append(user)
        return judge.JudgeVerdict(dimensions=dict.fromkeys(DIMENSIONS, 5), verdict="PASS")

    monkeypatch.setattr(judge, "_judge_via_anthropic", transport)
    filing = GoldenFiling("FIX", "1", "a", "10-K", "url", "Fixture")
    result = await runner._maybe_judge(JUDGE_MODEL, payload, filing, {"excerpt": "grounding", "xbrl_metrics": {}})
    assert "TAIL_SOURCE_EVIDENCE" in captured[0]
    assert result["input_complete"] is True
    assert result["input_lengths"]["summary_chars"] == len(json.dumps(payload, indent=2))


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", ["summary", "excerpt", "xbrl"])
async def test_oversized_judge_input_is_error_before_transport(monkeypatch, surface):
    transport = AsyncMock()
    monkeypatch.setattr(runner, "judge_summary", transport)
    payload = {"executive_summary": "x" * 100001 if surface == "summary" else "Summary"}
    grounding = {
        "excerpt": "x" * 200001 if surface == "excerpt" else "Grounding",
        "xbrl_metrics": {"raw": "x" * 40001} if surface == "xbrl" else {},
    }
    result = await runner._maybe_judge(JUDGE_MODEL, payload, GoldenFiling("F", "1", "a", "10-K", "u", "F"), grounding)
    assert result["error"] and result["input_complete"] is False
    assert result["dimensions"] == {}
    transport.assert_not_awaited()


@pytest.fixture
def weekly_evidence():
    filings = weekly_readout.load_cohort()
    results = [
        {
            "candidate": "baseline",
            "ticker": f["ticker"],
            "filing_type": f["filing_type"],
            "accession_number": f["accession_number"],
            "run": run,
            "score": {"schema_valid": True},
            "passed_gates": True,
            "error": None,
            "judge": {
                "verdict": "FAIL",
                "passed": False,
                "error": None,
                "input_complete": True,
                "gate_failures": ["Unsupported claim"],
                "dimensions": dict.fromkeys(DIMENSIONS, 2),
            },
        }
        for f in filings
        for run in range(3)
    ]
    harness = {
        "judge": JUDGE_MODEL,
        "source_sha": "a" * 40,
        "model": "deepseek-v4-pro",
        "golden_set_sha256": hashlib.sha256(weekly_readout.GOLDEN_PATH.read_bytes()).hexdigest(),
    }
    return results, filings, harness


def test_fixed_cohort_and_valid_negative_judgments_are_complete(weekly_evidence):
    rows, filings, harness = weekly_evidence
    assert [(f["ticker"], f["filing_type"]) for f in filings] == [
        ("AAPL", "10-K"),
        ("JPM", "10-K"),
        ("NVDA", "10-Q"),
        ("KO", "10-Q"),
        ("BYND", "10-Q"),
        ("ASML", "20-F"),
        ("BABA", "20-F"),
        ("MELI", "10-K"),
    ]
    rows[0]["passed_gates"] = False
    readout = weekly_readout.build_readout(rows, filings, harness)
    assert readout["deterministic_vetoes"] == 1
    assert (
        readout["status"],
        readout["expected"],
        readout["completed"],
        readout["scored"],
        readout["negative_judgments"],
    ) == ("complete", 24, 24, 24, 24)
    assert readout["dimensions"] == dict.fromkeys(DIMENSIONS, 2)
    assert decode_readout(encode_readout(readout)) == readout


@pytest.mark.parametrize("defect", ["missing", "inner-error", "legacy-input", "bad-dimensions", "generation-error"])
def test_weekly_missing_or_failed_judgment_is_not_first_readout(weekly_evidence, defect):
    rows, filings, harness = weekly_evidence
    if defect == "missing":
        rows.pop()
    elif defect == "inner-error":
        rows[0]["judge"]["error"] = "API unavailable"
    elif defect == "legacy-input":
        del rows[0]["judge"]["input_complete"]
    elif defect == "bad-dimensions":
        rows[0]["judge"]["dimensions"]["clarity"] = True
    else:
        rows[0]["error"] = "generation failed"
    r = weekly_readout.build_readout(rows, filings, harness)
    assert r["status"] == "partial" and r["scored"] == 23
    assert r["missing"] == int(defect == "missing") and r["errors"] == int(defect != "missing")


@pytest.mark.parametrize("defect", ["duplicate", "foreign-accession", "golden-hash", "weak-judge"])
def test_weekly_rejects_wrong_provenance_or_duplicate_grid(weekly_evidence, defect):
    rows, filings, harness = weekly_evidence
    if defect == "duplicate":
        rows[0] = deepcopy(rows[1])
    elif defect == "foreign-accession":
        rows[0]["accession_number"] = "wrong"
    elif defect == "golden-hash":
        harness["golden_set_sha256"] = "b" * 64
    else:
        harness["judge"] = "cheap-judge"
    with pytest.raises(ValueError):
        weekly_readout.build_readout(rows, filings, harness)


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", ["OPENAI_API_KEY", "ANTHROPIC_API_KEY"])
async def test_missing_either_credential_prevents_all_generation(monkeypatch, missing):
    monkeypatch.setenv("OPENAI_API_KEY", "fixture-generator")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fixture-judge")
    monkeypatch.delenv(missing)
    monkeypatch.setenv("GITHUB_SHA", "a" * 40)
    monkeypatch.setattr(settings, "STREAM_SECTION_REVEAL", True)
    process = AsyncMock()
    monkeypatch.setattr(runner, "_process_filing", process)
    readout, report = await weekly_readout.measure()
    assert readout["status"] == "unavailable" and readout["missing"] == 24 and report["results"] == []
    process.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_source_provenance_prevents_generation(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "fixture-generator")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fixture-judge")
    monkeypatch.delenv("GITHUB_SHA", raising=False)
    monkeypatch.setattr(settings, "STREAM_SECTION_REVEAL", True)
    process = AsyncMock()
    monkeypatch.setattr(runner, "_process_filing", process)
    readout, _ = await weekly_readout.measure()
    assert readout["status"] == "unavailable" and "provenance" in readout["reason"]
    process.assert_not_awaited()


def test_weekly_cli_emits_unavailable_artifact_without_credentials(monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert weekly_readout.main(["--output-dir", str(tmp_path)]) == 1
    report = json.loads((tmp_path / "report.json").read_text())
    assert report["results"] == [] and report["readout"]["scored"] == 0
    assert decode_readout((tmp_path / "readout.b64").read_text())["status"] == "unavailable"
    assert "missing 24" in (tmp_path / "readout.md").read_text()


def test_weekly_workflow_preserves_failure_evidence_and_operational_report():
    workflow = yaml.load((ROOT / ".github/workflows/data-quality-weekly.yml").read_text(), Loader=yaml.BaseLoader)
    assert workflow["on"]["schedule"][0]["cron"] == "0 13 * * 1"
    jobs = workflow["jobs"]
    measure = jobs["measure"]
    report = jobs["report"]
    assert report["needs"] == "measure" and report["if"] == "always()"
    step = next(s for s in measure["steps"] if s.get("id") == "handoff")
    assert step["if"] == "always()" and "unavailable_readout" in step["run"]
    upload = next(s for s in measure["steps"] if s.get("uses", "").startswith("actions/upload-artifact"))
    assert upload["if"] == "always()"
    generation = next(s for s in measure["steps"] if s.get("run") == "python -m evals.weekly_readout")
    assert generation["env"]["ANTHROPIC_API_KEY"] == "${{ secrets.ANTHROPIC_API_KEY }}"
    production = pin_baseline.production_env()
    for key in pin_baseline.AI_GUARD_ENV:
        assert generation["env"].get(key) == production[key]
    for key in ("AI_FALLBACK_MODEL", "AI_FALLBACK_BASE_URL"):
        assert generation["env"].get(key) == ""
    assert "steps.dependencies.outcome" in generation["if"]
    sender = report["steps"][-1]
    assert sender["env"]["READOUT_B64"] == "${{ needs.measure.outputs.readout }}"
    assert "--weekly-readout-b64,$READOUT_B64" in sender["run"] and '--args="$ARGS"' in sender["run"]


@pytest.mark.asyncio
async def test_validation_failure_preserves_actual_attempt_evidence(monkeypatch, weekly_evidence):
    rows, _, harness = weekly_evidence
    monkeypatch.setenv("OPENAI_API_KEY", "fixture-generator")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fixture-judge")
    harness.update(use_statement_financials=True, stream_section_reveal=True, use_structured_output=False)
    monkeypatch.setattr(runner, "_harness_metadata", lambda _: harness)

    async def process(filing, candidates, runs, judge_model):
        assert candidates == ["baseline"] and runs == 3 and judge_model == JUDGE_MODEL
        selected = deepcopy([r for r in rows if r["ticker"] == filing.ticker])
        for r in selected:
            r["score"]["repaired"] = False
            r["aggregate"] = 1.0
        if filing.ticker == "AAPL":
            selected[0]["ticker"] = "WRONG"
        return selected

    monkeypatch.setattr(runner, "_process_filing", process)
    readout, report = await weekly_readout.measure()
    assert readout["status"] == "unavailable" and "validation failed" in readout["reason"]
    assert len(report["results"]) == 24 and report["results"][0]["ticker"] == "WRONG"
    assert report["harness"] == harness
