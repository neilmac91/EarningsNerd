"""Workflow hygiene gates for operational workflows (rule 12; structural, no dispatches).

Dispatch inputs are attacker-shaped text. A ``${{ inputs.* }}`` expression inside a ``run:`` block
is substituted into the script before the shell parses it, so the text is executed, not validated.
Inputs must reach a step through ``env:`` and be read as ``$NAME``. The ops workflow runs against
production with the deployer identity, so it also runs only from ``main`` and never persists the
checkout token.
"""
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS = sorted(p.name for p in (ROOT / ".github/workflows").glob("*.yml"))
INPUT_EXPRESSIONS = ("${{ inputs.", "${{ github.event.inputs.")


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
        f"{name}: dispatch inputs must be passed through env: and read as $NAME, never interpolated "
        f"into run: scripts — {offenders}"
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
