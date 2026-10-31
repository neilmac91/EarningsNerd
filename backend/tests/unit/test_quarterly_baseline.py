"""The historical baseline runs only its immutable source/cohort, with closed failure output."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess

import pytest

from tests.support.ops_workflow import BASELINE, BY_NAME, OPS, PROXY, selected

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("quarterly_baseline", ROOT / "ops/quarterly_baseline/run.py")
BASELINE_MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BASELINE_MODULE)
OPERATION = "repair-quarterly-baseline-80fa90d-dry-run"
SOURCE_SHA = "80fa90d48ed1546e7770d88fd3b1b0aa05b1f89d"
COHORT = ["BIIB", "BMRN", "CRM", "FTNT", "JPM", "META", "NVDA", "RDDT", "REGN"]


def test_fixed_baseline_workflow_selects_complete_old_source_before_install_and_execution():
    checkout_at, checkout = BY_NAME["Check out fixed quarterly baseline source"]
    verify_at, verify = BY_NAME["Verify fixed quarterly baseline source"]
    deps_at, deps = BY_NAME["Install quarterly baseline dependencies"]
    run_at, step = BY_NAME[BASELINE]
    retain_at, retain = BY_NAME["Retain quarterly baseline report"]
    assert checkout["with"] == {"repository": "neilmac91/EarningsNerd", "ref": SOURCE_SHA,
                                "path": ".ops-quarterly-baseline", "persist-credentials": "false"}
    assert BASELINE_MODULE.SOURCE_SHA == SOURCE_SHA
    assert list(BASELINE_MODULE.COHORT) == COHORT
    assert BASELINE_MODULE.SOURCE == ROOT / checkout["with"]["path"]
    for item in (checkout, verify, deps, step):
        assert item["if"] == f"steps.request.outputs.operation == '{OPERATION}'"
        assert "continue-on-error" not in item
    assert verify["run"] == "python3 ops/quarterly_baseline/run.py --verify-source"
    assert deps["run"] == "pip install -q -r .ops-quarterly-baseline/backend/requirements.txt"
    assert checkout_at < verify_at < deps_at < BY_NAME[PROXY][0] < run_at < retain_at
    assert OPERATION not in selected(BY_NAME["Install backend dependencies"][1])
    assert OPERATION in selected(BY_NAME["Refuse to run while a main push (deploy) is in flight"][1])
    assert "python3 ops/quarterly_baseline/run.py --output \"$RUNNER_TEMP/quarterly-baseline\"" in step["run"]
    assert retain["if"] == "always() && steps.quarterly_baseline.outcome != 'skipped'"
    assert retain["with"]["path"] == "${{ runner.temp }}/quarterly-baseline/"
    assert "github.ref == 'refs/heads/main'" in OPS["jobs"]["ops"]["if"]


@pytest.mark.parametrize("tickers,revision,code", [("", "", 0), (",".join(COHORT), "", 1), ("", "old", 1)])
def test_fixed_baseline_refuses_inputs_instead_of_silently_ignoring_them(tickers, revision, code):
    step = BY_NAME["Validate fixed quarterly baseline request"][1]
    assert step["if"] == f"steps.request.outputs.operation == '{OPERATION}'"
    result = subprocess.run(["bash", "-c", step["run"]], capture_output=True, text=True,
                            env={**os.environ, "TICKERS": tickers, "REVISION": revision})
    assert result.returncode == code


@pytest.fixture
def execution(tmp_path, monkeypatch):
    source = tmp_path / "source"
    for name in BASELINE_MODULE.FILES:
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(name)
    monkeypatch.setattr(BASELINE_MODULE, "SOURCE", source)
    monkeypatch.setenv("GITHUB_SHA", "1" * 40)
    monkeypatch.setenv("PGOPTIONS", BASELINE_MODULE.PGOPTIONS)
    monkeypatch.setenv("SEC_RATE_LIMIT_PER_SECOND", "1")
    monkeypatch.setenv("EDGAR_RATE_LIMIT_PER_SEC", "1")
    state = {"head": SOURCE_SHA, "dirty": "", "calls": [], "exit": 0,
             "report": {"run_id": "baseline-fixture", "dry_run": True, "failed": 0,
                        "companies": [{"ticker": ticker} for ticker in COHORT]}}

    def invoke(argv, **kwargs):
        if argv[0] == "git":
            assert kwargs["stdout"] == subprocess.PIPE and kwargs["stderr"] == subprocess.DEVNULL
            answer = state["dirty"] if "status" in argv else "2" * 40 if "HEAD^{tree}" in argv else state["head"]
            return subprocess.CompletedProcess(argv, 0, answer, "")
        state["calls"].append((argv, kwargs))
        assert kwargs["cwd"] == source / "backend"
        assert argv[1:4] == ["-I", str(source / "backend/scripts/repair_quarterly_facts.py"), "--tickers"]
        assert argv[4:8] == [",".join(COHORT), "--limit", "50", "--output"]
        assert len(argv) == 9
        Path(argv[-1]).write_text(json.dumps(state["report"]))
        assert kwargs["stdout"] == kwargs["stderr"] == subprocess.DEVNULL
        return subprocess.CompletedProcess(argv, state["exit"])

    monkeypatch.setattr(BASELINE_MODULE.subprocess, "run", invoke)
    return state, tmp_path / "artifact"


def test_baseline_receipt_binds_old_source_to_new_workflow_and_exact_cohort(execution):
    state, output = execution
    assert BASELINE_MODULE.run(output) == 0
    receipt = json.loads((output / "source-receipt.json").read_text())
    assert receipt["source_commit"] == SOURCE_SHA and receipt["workflow_commit"] == "1" * 40
    assert receipt["production_image_used"] is False
    assert receipt["status"] == "complete" and receipt["report_complete"] is True
    assert receipt["cohort"] == COHORT and receipt["run_id"] == "baseline-fixture"
    assert len(state["calls"]) == 1
    assert sorted(path.name for path in output.iterdir()) == ["report.json", "source-receipt.json"]


@pytest.mark.parametrize("change", ["wrong_source", "dirty_source", "writable_session"])
def test_baseline_refuses_before_script_for_unverified_source_or_guards(execution, monkeypatch, change):
    state, output = execution
    if change == "wrong_source":
        state["head"] = "3" * 40
    elif change == "dirty_source":
        state["dirty"] = " M backend/app/database.py"
    else:
        monkeypatch.setenv("PGOPTIONS", "-c default_transaction_read_only=off")
    with pytest.raises(ValueError):
        BASELINE_MODULE.run(output)
    assert state["calls"] == []


def test_failed_company_diagnostics_are_withheld_and_failure_is_not_success(execution, capsys):
    state, output = execution
    state["exit"] = 1
    state["report"]["failed"] = 1
    state["report"]["companies"][0]["error"] = "private database diagnostic"
    assert BASELINE_MODULE.run(output) == 1
    artifact = "".join(path.read_text() for path in output.iterdir())
    assert "private" not in artifact + capsys.readouterr().out
    assert "details withheld" in artifact
    assert json.loads((output / "source-receipt.json").read_text())["status"] == "failed"


def test_incomplete_or_wrong_cohort_report_is_not_retained(execution):
    state, output = execution
    state["report"]["companies"].pop()
    assert BASELINE_MODULE.run(output) == 1
    assert not (output / "report.json").exists()
    assert json.loads((output / "source-receipt.json").read_text())["report_complete"] is False
