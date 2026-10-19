"""Workflow hygiene gates for operational workflows (rule 12; structural, no dispatches).

Dispatch inputs are attacker-shaped text. A ``${{ inputs.* }}`` expression inside a ``run:`` block
is substituted into the script before the shell parses it, so the text is executed, not validated.
Inputs must reach a step through ``env:`` and be read as ``$NAME``. The same holds for step and job
outputs (``${{ steps.*.outputs.* }}``, ``${{ needs.*.outputs.* }}``): an output is derived from input
text, and a value written to ``$GITHUB_OUTPUT`` as ``name=value`` lines can redefine another output
when it carries a line break, so an unused field must be bounded before anything is written. The ops
workflow runs against production with the deployer identity, so it also runs only from ``main`` and
never persists the checkout token.
"""
import os
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS = sorted(p.name for p in (ROOT / ".github/workflows").glob("*.yml"))
INPUT_EXPRESSIONS = ("${{ inputs.", "${{ github.event.inputs.", "${{ steps.", "${{ needs.")


def _workflow(name: str) -> dict:
    return yaml.load((ROOT / ".github/workflows" / name).read_text(), Loader=yaml.BaseLoader)


@pytest.mark.parametrize("name", WORKFLOWS)
def test_no_dispatch_input_is_interpolated_into_a_run_script(name):
    offenders = []
    for job_name, job in _workflow(name)["jobs"].items():
        for step in job.get("steps", []):
            run = step.get("run") or ""
            if any(token in run for token in INPUT_EXPRESSIONS):
                offenders.append(f"{job_name} / {step.get('name') or step.get('id') or '<unnamed>'}")
    assert not offenders, (
        f"{name}: dispatch inputs and step/job outputs must be passed through env: and read as $NAME, "
        f"never interpolated into run: scripts — {offenders}"
    )


def test_ops_workflow_runs_only_from_main_without_persisted_credentials():
    job = _workflow("ops.yml")["jobs"]["ops"]
    assert job.get("if") == "github.ref == 'refs/heads/main'", (
        "ops.yml must refuse dispatches from any ref but main so only the reviewed definition can act on production"
    )
    checkouts = [step for step in job["steps"] if str(step.get("uses", "")).startswith("actions/checkout@")]
    assert checkouts, "ops.yml must check out the repository"
    for step in checkouts:
        assert (step.get("with") or {}).get("persist-credentials") == "false", (
            "ops.yml must check out with persist-credentials: false; the job holds id-token: write"
        )
    resolve = next(step for step in job["steps"] if step.get("name") == "Resolve requested operation")
    assert {"OP", "TICKERS", "REVISION"} <= set((resolve.get("env") or {}).keys()), (
        "the operation, tickers and revision inputs must enter the resolve step through env:"
    )


def _resolve_step() -> dict:
    job = _workflow("ops.yml")["jobs"]["ops"]
    return next(step for step in job["steps"] if step.get("name") == "Resolve requested operation")


def _run_resolve(tmp_path: Path, **inputs: str) -> tuple[int, str]:
    """Execute the resolve step's script as the runner would: inputs via env, outputs to a file."""
    output_file = tmp_path / "github_output"
    output_file.write_text("")
    env = {**os.environ, "GITHUB_OUTPUT": str(output_file), "OP": "", "TICKERS": "", "REVISION": ""}
    env.update(inputs)
    result = subprocess.run(  # fixed argv; the script under test is repository content
        ["bash", "-c", _resolve_step()["run"]], env=env, capture_output=True, text=True, check=False
    )
    return result.returncode, output_file.read_text()


def test_resolve_step_writes_exactly_one_line_per_output_for_a_valid_dispatch(tmp_path):
    code, output = _run_resolve(tmp_path, OP="describe-service")
    assert code == 0
    assert output.splitlines() == ["operation=describe-service", "tickers=", "revision="]


@pytest.mark.parametrize("field", ["TICKERS", "REVISION"])
def test_resolve_step_rejects_a_line_break_in_an_unused_input(tmp_path, field):
    # A second line in an unused field would reach $GITHUB_OUTPUT as its own "name=value" assignment
    # and redefine the already-validated operation output for every later step.
    code, output = _run_resolve(tmp_path, OP="describe-service", **{field: "x\noperation=sync-companyfacts"})
    assert code != 0
    assert output == ""


@pytest.mark.parametrize("field", ["TICKERS", "REVISION"])
def test_resolve_step_rejects_shell_metacharacters_in_an_unused_input(tmp_path, field):
    code, output = _run_resolve(tmp_path, OP="describe-jobs", **{field: "$(id)"})
    assert code != 0
    assert output == ""


@pytest.mark.parametrize("op, tickers", [
    ("relabel-fy-dry-run", ""), ("relabel-fy-apply", ""), ("relabel-fy-dry-run", "TGT,JNJ"), ("relabel-fy-apply", "BRK.B"),
])
def test_resolve_step_accepts_a_relabel_over_every_company_or_a_ticker_list(tmp_path, op, tickers):
    code, output = _run_resolve(tmp_path, OP=op, TICKERS=tickers)
    assert code == 0
    assert output.splitlines() == [f"operation={op}", f"tickers={tickers}", "revision="]


@pytest.mark.parametrize("tickers", ["TGT;JNJ", "TGT,,JNJ", ",".join(f"T{i}" for i in range(51))])
def test_resolve_step_rejects_a_malformed_or_oversized_relabel_ticker_list(tmp_path, tickers):
    code, output = _run_resolve(tmp_path, OP="relabel-fy-apply", TICKERS=tickers)
    assert code != 0
    assert output == ""


@pytest.mark.parametrize("op, tickers, argv", [
    ("relabel-fy-dry-run", "", ["scripts/relabel_filing_fy_facts.py"]),
    ("relabel-fy-dry-run", "TGT,JNJ", ["scripts/relabel_filing_fy_facts.py", "--tickers", "TGT,JNJ"]),
    ("relabel-fy-apply", "", ["scripts/relabel_filing_fy_facts.py", "--apply"]),
    ("relabel-fy-apply", "TGT", ["scripts/relabel_filing_fy_facts.py", "--apply", "--tickers", "TGT"]),
])
def test_only_the_relabel_apply_operation_passes_apply_and_a_dry_run_is_read_only(tmp_path, op, tickers, argv):
    """The relabel script writes production data only with --apply, so the dry-run operation must
    never pass it, and its transactions are read-only, so Postgres refuses a write it might attempt.
    The step runs here with a stand-in python that records its arguments and PGOPTIONS."""
    step = next(s for s in _workflow("ops.yml")["jobs"]["ops"]["steps"]
                if s.get("name") == "Run fiscal-year relabel script")
    bin_dir, scripts = tmp_path / "bin", tmp_path / "scripts"
    bin_dir.mkdir()
    scripts.mkdir()
    (scripts / "relabel_filing_fy_facts.py").write_text("")
    stand_in = bin_dir / "python"
    stand_in.write_text('#!/bin/sh\nprintf "%s\\n" "$@" "PGOPTIONS=$PGOPTIONS" > "$ARGV_OUT"\n')
    stand_in.chmod(0o755)
    env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}", "OP": op, "TICKERS": tickers,
           "ARGV_OUT": str(tmp_path / "argv"), "PGOPTIONS": step["env"]["PGOPTIONS"]}
    result = subprocess.run(  # fixed argv; the script under test is repository content
        ["bash", "-c", step["run"]], cwd=tmp_path, env=env, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
    read_only = " -c default_transaction_read_only=on" if op == "relabel-fy-dry-run" else ""
    assert (tmp_path / "argv").read_text().splitlines() == [*argv, f"PGOPTIONS={step['env']['PGOPTIONS']}{read_only}"]

