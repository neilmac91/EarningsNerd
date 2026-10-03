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
