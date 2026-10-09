"""copilot-eval refuses a re-run (rule 12 for the RUNBOOK triage rule; lessons/ops-copilot-eval-red-is-triaged-never-rerun.md).

The RUNBOOK's triage rule says a red copilot-eval run is never re-run to obtain a green result
outside a predeclared protocol. As prose it did not hold (a red run was re-run on #1148 and the
green re-run merged the PR), so the workflow enforces it: a re-run attempt fails in a step that runs
before the dependencies install or the provider credential is used, so it can never turn green and
spends nothing.
"""
import subprocess
from pathlib import Path

import yaml

WORKFLOW = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "copilot-eval.yml"


def _steps():
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf8"))
    return data["jobs"]["copilot-eval"]["steps"]


def _refusal(steps):
    matches = [step for step in steps if "github.run_attempt" in str(step.get("if", ""))]
    assert len(matches) == 1, "copilot-eval.yml: exactly one step gated on github.run_attempt"
    return matches[0]


def test_a_rerun_attempt_fails_before_any_spend():
    steps = _steps()
    refusal = _refusal(steps)
    assert refusal["if"].replace(" ", "") == "github.run_attempt!='1'"
    install = next(s for s in steps if "pip install" in s.get("run", ""))
    runner = next(s for s in steps if "evals.copilot_runner" in s.get("run", ""))
    assert steps.index(refusal) < steps.index(install) < steps.index(runner)
    assert "OPENAI_API_KEY" not in str(refusal)
    # Nothing between the refusal and the runner may skip it or soften the failure.
    assert "continue-on-error" not in refusal


def test_the_refusal_step_fails_and_names_the_rule(tmp_path):
    script = tmp_path / "refusal.sh"
    script.write_text(_refusal(_steps())["run"])
    result = subprocess.run(["bash", "-e", str(script)], capture_output=True, text=True)  # noqa: S603,S607
    assert result.returncode == 1
    assert "never re-run to obtain a green result" in result.stdout
    assert "backend/evals/RUNBOOK.md" in result.stdout
