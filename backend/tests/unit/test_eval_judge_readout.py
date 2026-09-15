"""Offline contracts for the local subscription judge: retained generation inputs are judged through
the harness's own judge path, and only a provenance-matching, contract-judged report becomes a readout."""
import hashlib
import json

import pytest

from app.services.ai_readout import DIMENSIONS, JUDGE_BACKEND, JUDGE_MODEL, decode_readout
from evals import judge, judge_readout, runner, weekly_readout

RUN_URL = "https://github.com/neilmac91/EarningsNerd/actions/runs/34950000001"
STATEMENT = {"operating_income": {"current": {"value": 1, "period_end": "2025-12-31"}}}


def _company(ticker: str) -> str:
    golden = json.loads(weekly_readout.GOLDEN_PATH.read_text())["filings"]
    return next(f["company_name"] for f in golden if f["ticker"] == ticker)


@pytest.fixture
def generation_report():
    rows = []
    for f in weekly_readout.load_cohort():
        for run in range(3):
            rows.append({
                "candidate": "baseline", "ticker": f["ticker"], "filing_type": f["filing_type"],
                "accession_number": f["accession_number"], "run": run,
                "score": {"schema_valid": True, "repaired": False, "numeric_accuracy": 1.0, "numeric_precision": 1.0,
                          "coverage": 1.0},
                "aggregate": 1.0, "passed_gates": True, "error": None,
                "judge": None,
                "payload": {"executive_summary": f"{f['ticker']} retained summary {run}"},
                "grounding_excerpt": f"RETAINED SOURCE {f['ticker']} {run}",
                "xbrl_grounding": {"revenue": {"current": {"value": 10 + run}}, "financial_classification": "internal"},
                "statement_source": STATEMENT if f["ticker"] == "MELI" else None,
            })
    harness = {"judge": False, "source_sha": "a" * 40, "model": "deepseek-flash",
               "golden_set_sha256": hashlib.sha256(weekly_readout.GOLDEN_PATH.read_bytes()).hexdigest(),
               "use_statement_financials": True, "stream_section_reveal": True, "use_structured_output": False}
    return {"phase": "generation", "results": rows, "harness": harness, "run_url": RUN_URL,
            "cohort": json.loads(weekly_readout.COHORT_PATH.read_text())}


@pytest.fixture
def transport(monkeypatch):
    """Replace only the model transport; message construction, bounds and parsing stay real."""
    calls = []

    async def fake(payload, company, filing_type, excerpt, xbrl_text, model_id=None, max_tokens=4096):
        calls.append({"payload": payload, "company": company, "filing_type": filing_type,
                      "excerpt": excerpt, "xbrl_text": xbrl_text, "model_id": model_id})
        failed = "BYND" in payload["executive_summary"]
        return judge.JudgeVerdict(dimensions=dict.fromkeys(DIMENSIONS, 2 if failed else 4),
                                  verdict="FAIL" if failed else "PASS",
                                  gate_failures=["G3 hallucinated_facts: unsupported claim"] if failed else [])

    monkeypatch.setattr(runner, "judge_summary", fake)
    return calls


def _run(report, tmp_path, extra=()):
    path = tmp_path / "report.json"
    path.write_text(json.dumps(report))
    out = tmp_path / "judged"
    code = judge_readout.main([str(path), "--output-dir", str(out), "--concurrency", "3", *extra])
    return code, out


def test_retained_inputs_are_judged_through_the_harness_path_into_a_complete_readout(generation_report, transport, tmp_path):
    code, out = _run(generation_report, tmp_path)
    assert code == 0
    readout = json.loads((out / "readout.json").read_text())
    assert (readout["status"], readout["scored"], readout["completed"], readout["negative_judgments"]) == ("complete", 24, 24, 3)
    assert readout["judge_model"] == JUDGE_MODEL and readout["judge_backend"] == JUDGE_BACKEND == "cli"
    assert readout["run_url"] == RUN_URL and readout["artifact_url"] == RUN_URL + "#artifacts"
    assert readout["source_sha"] == "a" * 40 and readout["generator_model"] == "deepseek-flash"
    assert readout["dimensions"] == {key: round((21 * 4 + 3 * 2) / 24, 4) for key in DIMENSIONS}
    assert decode_readout((out / "readout.b64").read_text()) == readout
    judged = json.loads((out / "report.json").read_text())
    assert judged["phase"] == "judged" and judged["harness"]["judge"] == weekly_readout.JUDGE_ID == f"cli:{JUDGE_MODEL}"
    assert judged["readout"] == readout and judged["run_url"] == RUN_URL
    assert all(r["judge"]["input_complete"] is True and r["judge"]["error"] is None for r in judged["results"])
    # Parity proof: the judge receives exactly the retained excerpt, the retained XBRL grounding without
    # internal classification metadata, and the application-owned statement evidence, via the contract judge.
    assert len(transport) == 24 and {c["model_id"] for c in transport} == {weekly_readout.JUDGE_ID}
    meli = [c for c in transport if c["company"] == _company("MELI")]
    assert len(meli) == 3
    for call in meli:
        assert call["excerpt"].startswith("RETAINED SOURCE MELI ")
        assert json.dumps(STATEMENT, ensure_ascii=False, sort_keys=True) in call["excerpt"]
        assert call["filing_type"] == "10-K"
    assert all("APPLICATION-OWNED" not in c["excerpt"] for c in transport if c["company"] != _company("MELI"))
    assert all(json.loads(c["xbrl_text"]) == {"revenue": {"current": {"value": 10 + c["payload"]["executive_summary"].endswith("1") + 2 * c["payload"]["executive_summary"].endswith("2")}}} for c in transport)
    markdown = (out / "readout.md").read_text()
    assert "judged 24" in markdown and "| BYND | 10-Q | 0 | FAIL |" in markdown and "never automatically arms" in markdown


def test_failed_and_oversized_attempts_stay_errors_without_transport(generation_report, transport, tmp_path):
    rows = generation_report["results"]
    rows[0].update(error="TimeoutError: cold", score=None, payload=None)  # generation failure retained as-is
    rows[1]["grounding_excerpt"] = "x" * (judge._JUDGE_EXCERPT_CHAR_CAP + 1)  # over the full-coverage bound
    del rows[2]["grounding_excerpt"]  # legacy attempt without retained judge inputs ...
    rows[2]["judge"] = {"verdict": "PASS", "passed": True, "error": None, "input_complete": True,
                        "gate_failures": [], "dimensions": dict.fromkeys(DIMENSIONS, 5)}  # ... carrying a stale verdict
    code, out = _run(generation_report, tmp_path)
    assert code == 1
    readout = json.loads((out / "readout.json").read_text())
    assert (readout["status"], readout["scored"], readout["completed"], readout["errors"], readout["missing"]) == ("partial", 21, 23, 3, 0)
    judged = json.loads((out / "report.json").read_text())["results"]
    assert judged[0]["judge"] is None and judged[2]["judge"] is None
    assert judged[1]["judge"]["input_complete"] is False and "full-coverage" in judged[1]["judge"]["error"]
    assert len(transport) == 21 and all(len(c["excerpt"]) <= judge._JUDGE_EXCERPT_CHAR_CAP for c in transport)


@pytest.mark.parametrize("defect", ["golden-hash", "foreign-identity", "duplicate-identity"])
def test_provenance_mismatch_is_refused_before_any_judge_call(generation_report, transport, tmp_path, defect):
    rows = generation_report["results"]
    if defect == "golden-hash":
        generation_report["harness"]["golden_set_sha256"] = "b" * 64
    elif defect == "foreign-identity":
        rows[0]["accession_number"] = "0000000000-00-000000"
    else:
        rows[0] = {**rows[1]}
    code, out = _run(generation_report, tmp_path)
    assert code == 1
    readout = json.loads((out / "readout.json").read_text())
    assert readout["status"] == "unavailable" and readout["scored"] == 0 and readout["missing"] == 24
    assert readout["reason"].startswith("Measurement provenance refused before judging") and "no judge calls" in readout["reason"]
    judged = json.loads((out / "report.json").read_text())
    assert transport == [] and all(r["judge"] is None for r in judged["results"])


def test_non_contract_judge_retains_verdicts_but_yields_no_readout(generation_report, transport, tmp_path):
    # A stale verdict carried by the generation report must not survive into the readout either.
    generation_report["results"][0]["judge"] = {"verdict": "PASS", "passed": True, "error": None, "input_complete": True,
                                                "gate_failures": [], "dimensions": dict.fromkeys(DIMENSIONS, 5)}
    code, out = _run(generation_report, tmp_path, ["--judge", "cli:claude-opus-4-8"])
    assert code == 1
    readout = json.loads((out / "readout.json").read_text())
    assert readout["status"] == "unavailable" and readout["scored"] == 0 and readout["missing"] == 24
    assert readout["reason"].startswith("Measurement validation failed")
    judged = json.loads((out / "report.json").read_text())
    verdicts = [r["judge"] for r in judged["results"] if isinstance(r.get("judge"), dict)]
    assert len(verdicts) == len(transport) == 24 and {c["model_id"] for c in transport} == {"cli:claude-opus-4-8"}
    assert judged["harness"]["judge"] == "cli:claude-opus-4-8"
    assert judged["results"][0]["judge"]["dimensions"] != dict.fromkeys(DIMENSIONS, 5)  # re-judged, not carried over
