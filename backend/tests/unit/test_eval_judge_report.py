"""Offline contracts for the general report judge (the prompt-candidate acceptance gate): retained
attempts of any eval report are judged through the harness path under the current judge contract, only a
provenance-matching report is judged at all, and the written record names the #805 negative controls."""
import hashlib
import json

import pytest

from app.services.ai_readout import DIMENSIONS
from evals import judge, judge_report, runner, weekly_readout

SOURCE_SHA = "b" * 40


def _golden(ticker: str, form: str) -> dict:
    golden = json.loads(weekly_readout.GOLDEN_PATH.read_text())["filings"]
    return next(f for f in golden if f["ticker"] == ticker and f["filing_type"] == form)


def _attempt(filing: dict, candidate: str = "baseline", run: int = 0, accession: bool = False, **extra) -> dict:
    """A row shaped like the runner writes it: ticker, form and run, with a None accession and cik (only
    the weekly readout stamps the cohort accession on; `accession=True` builds that shape)."""
    row = {"candidate": candidate, "ticker": filing["ticker"], "filing_type": filing["filing_type"],
           "accession_number": filing["accession_number"] if accession else None, "cik": None, "run": run,
           "score": {"schema_valid": True}, "aggregate": 1.0, "passed_gates": True, "error": None, "judge": None}
    row.update(extra)
    return row


@pytest.fixture
def eval_report():
    aapl, ba, asml = _golden("AAPL", "10-K"), _golden("BA", "10-K"), _golden("ASML", "6-K")
    retained = {"grounding_excerpt": "RETAINED SOURCE", "xbrl_grounding": {"revenue": {"current": {"value": 10}}},
                "statement_source": None}
    rows = [
        _attempt(aapl, payload={"executive_summary": "AAPL retained"}, **retained),
        # A stale verdict carried from generation must not survive into the judged record.
        _attempt(ba, accession=True, payload={"executive_summary": "BA core profit improved on the disposal"}, **retained,
                 judge={"verdict": "PASS", "passed": True, "error": None, "input_complete": True,
                        "gate_failures": [], "dimensions": dict.fromkeys(DIMENSIONS, 5)}),
        # The A-candidate route retains no payload or excerpt: not judgeable, never re-fetched.
        _attempt(aapl, candidate="A1"),
        _attempt(asml, error="ValueError: provider failure", score=None, aggregate=0.0, passed_gates=False),
    ]
    harness = {"judge": False, "source_sha": SOURCE_SHA, "model": "deepseek-flash",
               "golden_set_sha256": hashlib.sha256(weekly_readout.GOLDEN_PATH.read_bytes()).hexdigest()}
    return {"phase": "generation", "results": rows, "harness": harness}


@pytest.fixture
def transport(monkeypatch):
    """Replace only the model transport; message construction, bounds and parsing stay real."""
    calls = []

    async def fake(payload, company, filing_type, excerpt, xbrl_text, model_id=None, max_tokens=4096):
        calls.append({"payload": payload, "company": company, "excerpt": excerpt, "model_id": model_id})
        if "BA core" in payload["executive_summary"]:
            return judge.JudgeVerdict(dimensions=dict.fromkeys(DIMENSIONS, 2), verdict="FAIL",
                                      gate_failures=["G4 unsupported_cause: 'improved on the disposal' is not stated",
                                                     "G5 basis_mismatch: core profit includes the gain"])
        return judge.JudgeVerdict(dimensions=dict.fromkeys(DIMENSIONS, 4), verdict="PASS")

    monkeypatch.setattr(runner, "judge_summary", fake)
    return calls


def test_retained_attempts_are_judged_under_the_current_contract_and_recorded(eval_report, transport, tmp_path):
    report_path = tmp_path / "eval_x.json"
    report_path.write_text(json.dumps(eval_report))
    out = tmp_path / "out"
    assert judge_report.main([str(report_path), "--output-dir", str(out)]) == 0
    judged = json.loads((out / "judged.json").read_text())
    by_id = {judge_report.identity(r): r for r in judged["results"]}
    aapl = by_id[("baseline", "AAPL", "10-K", None, 0)]  # the runner's row: no accession on the row
    ba = by_id[("baseline", "BA", "10-K", eval_report["results"][1]["accession_number"], 0)]
    assert aapl["judge"]["verdict"] == "PASS" and aapl["judge"]["contract_version"] == judge.JUDGE_CONTRACT_VERSION
    assert ba["judge"]["verdict"] == "FAIL" and ba["judge"]["passed"] is False  # the carried PASS is gone
    assert ba["judge"]["gate_failures"][0].startswith("G4 unsupported_cause")
    assert by_id[("A1", "AAPL", "10-K", None, 0)]["judge"] is None
    assert by_id[("baseline", "ASML", "6-K", None, 0)]["judge"] is None
    assert transport[0]["company"] == _golden("AAPL", "10-K")["company_name"]  # resolved from ticker + form
    assert len(transport) == 2 and all(c["model_id"] == weekly_readout.JUDGE_ID for c in transport)
    assert transport[0]["excerpt"] == "RETAINED SOURCE"  # the retained input, not a re-fetched source
    assert judged["harness"]["judge"] == weekly_readout.JUDGE_ID
    assert judged["harness"]["judge_contract_version"] == judge.JUDGE_CONTRACT_VERSION
    assert judged["judged_summary"] == {
        "attempts": 4, "judgeable": 2, "judged": 2, "errors": 0, "negative": 1, "complete": True,
        "gate_counts": {"G2 fabricated_comparatives": 0, "G3 hallucinated_facts": 0,
                        "G4 unsupported_cause": 1, "G5 basis_mismatch": 1},
    }
    markdown = (out / "judged.md").read_text()
    assert "# Judged eval report: complete" in markdown
    assert f"contract version {judge.JUDGE_CONTRACT_VERSION}" in markdown
    assert "| G4 unsupported_cause | 1 |" in markdown and "| G5 basis_mismatch | 1 |" in markdown
    controls = markdown.split("## #805 negative controls", 1)[1]
    assert "| baseline | AAPL | 10-K | 0 | PASS |" in controls
    assert "| baseline | BA | 10-K | 0 | FAIL |" in controls and "improved on the disposal" in controls
    assert "never automatically arms" in markdown


@pytest.mark.parametrize("defect", ["golden", "duplicate", "foreign_accession", "foreign_form", "empty"])
def test_provenance_mismatch_is_refused_before_any_judge_call(eval_report, transport, tmp_path, defect):
    if defect == "golden":
        eval_report["harness"]["golden_set_sha256"] = "0" * 64
    elif defect == "duplicate":
        eval_report["results"].append(dict(eval_report["results"][0]))
    elif defect == "foreign_accession":
        eval_report["results"][1]["accession_number"] = "0000000000-00-000000"  # row names an accession the golden lacks
    elif defect == "foreign_form":
        eval_report["results"][0]["filing_type"] = "8-K"
    else:
        eval_report["results"] = []
    report_path = tmp_path / "eval_x.json"
    report_path.write_text(json.dumps(eval_report))
    assert judge_report.main([str(report_path), "--output-dir", str(tmp_path / "out")]) == 2
    assert transport == [] and not (tmp_path / "out").exists()


def test_an_attempt_without_a_complete_verdict_makes_the_record_partial(eval_report, monkeypatch, tmp_path):
    async def failing(payload, company, filing_type, excerpt, xbrl_text, model_id=None, max_tokens=4096):
        return judge.JudgeVerdict(verdict="FAIL", error="judge unreachable", gate_failures=["judge response unparseable"])

    monkeypatch.setattr(runner, "judge_summary", failing)
    report_path = tmp_path / "eval_x.json"
    report_path.write_text(json.dumps(eval_report))
    out = tmp_path / "out"
    assert judge_report.main([str(report_path), "--output-dir", str(out)]) == 1
    judged = json.loads((out / "judged.json").read_text())
    assert judged["judged_summary"]["judged"] == 0 and judged["judged_summary"]["errors"] == 2
    assert judged["judged_summary"]["complete"] is False
    assert "# Judged eval report: partial" in (out / "judged.md").read_text()


def test_an_ambiguous_ticker_and_form_is_refused_not_guessed():
    """Two golden entries for one ticker + form cannot be told apart by a runner row (no accession)."""
    aapl = _golden("AAPL", "10-K")
    twin = {**aapl, "accession_number": "0000320193-99-000001"}
    row = _attempt(aapl)
    assert judge_report.resolve_filing(row, [aapl]) == aapl
    assert judge_report.resolve_filing(row, [aapl, twin]) is None
    assert judge_report.resolve_filing(_attempt(aapl, accession=True), [aapl, twin]) == aapl
    report = {"results": [row], "harness": {"golden_set_sha256": hashlib.sha256(weekly_readout.GOLDEN_PATH.read_bytes()).hexdigest()}}
    with pytest.raises(ValueError, match="ambiguous"):
        judge_report.check_provenance(report, [aapl, twin])


def test_the_committed_golden_set_identifies_every_verified_filing_by_ticker_and_form():
    """The identity the runner's rows carry must be unique in the golden set, or judge_report refuses
    a real eval artifact (the September 16 first run was refused for exactly this shape mismatch)."""
    golden = [f for f in json.loads(weekly_readout.GOLDEN_PATH.read_text())["filings"] if f.get("verified")]
    pairs = [(f["ticker"], f["filing_type"]) for f in golden]
    assert len(set(pairs)) == len(pairs)
