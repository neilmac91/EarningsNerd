"""copilot-eval's source check is the preparation step's last act, so a refused source spends no draw (E80).

The founder decided on 31 October 2026 (option (c)) that a prepared source other than its golden case declares costs
a pull request no draw: ``evals.copilot_source_check`` runs the runner's own preflight,
``copilot_runner.validate_preparation``, as the last command of "Prepare actual SEC sources in a new scratch
database". A refusal then fails that step, the runner step is skipped, and the draw gate, which counts only a runner
step that ran, counts nothing: a re-run draws once the source is back. The runner keeps the same call before any
provider call, so a check skipped or removed refuses there instead, at the cost of the head's draw (fail closed).
These tests pin both placements, that the check refuses what the runner's preflight refuses, and that its failure
fails the step under Actions' bash. No provider call is made.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

from evals import copilot_runner as runner
from evals import copilot_source_check as check
from scripts import copilot_eval_draw_gate as gate
from tests.unit.test_copilot_gate import preparation

WORKFLOW = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "copilot-eval.yml"
PREPARATION = "evals/reports/copilot/preparation.json"


def _written(tmp_path, data) -> Path:
    path = tmp_path / "preparation.json"
    path.write_text(json.dumps(data))
    return path


def test_a_preparation_on_its_declared_sources_passes_the_check(tmp_path, capsys):
    _, data = preparation(tmp_path)
    path = _written(tmp_path, data)
    assert check.refusal(path) is None
    assert check.main(["--preparation", str(path)]) == 0
    assert capsys.readouterr().out == "source check: every prepared source is the one its golden case declares\n"


def _stub_first_declared_section(data, cases):
    record = data["sources"][0]["excerpt_provenance"]
    declared = next(c for c in cases if c.accession_number == data["sources"][0]["accession_number"])
    key = declared.excerpt_source["sections"][0]
    entry = next(e for e in record["supplied_sections"] if e["key"] == key)
    entry["supplied_chars"] = runner.NATIVE_SECTION_FLOORS[key] - 1


# A damage of each kind the preflight refuses: the preparation as a whole, an artifact, the builder's record of the
# excerpt source, and a declared section under its floor.
DAMAGES = {
    "incomplete": lambda data, cases: data.update(status="unavailable"),
    "database": lambda data, cases: data.update(database_sha256="0" * 64),
    "artifact": lambda data, cases: data["sources"][0]["artifacts"]["excerpt"].update(sha256="0" * 64),
    "fallback": lambda data, cases: data["sources"][0]["excerpt_provenance"].update(source="regex_fallback"),
    "stub": _stub_first_declared_section,
}


@pytest.mark.parametrize("damage", DAMAGES, ids=DAMAGES)
def test_the_check_refuses_exactly_what_the_runners_preflight_refuses(damage, tmp_path, capsys):
    cases, data = preparation(tmp_path)
    DAMAGES[damage](data, cases)
    path = _written(tmp_path, data)
    with pytest.raises(ValueError) as refused:
        runner.validate_preparation(path, cases)
    reason = str(refused.value)[:200]
    assert check.refusal(path) == reason
    assert check.main(["--preparation", str(path)]) == 1
    printed = capsys.readouterr().out
    assert printed.startswith("::error title=Source refused::" + check._command_value(reason) + ". No draw was spent")
    assert printed.count("\n") == 1  # one workflow command: nothing in it can start a second


@pytest.mark.parametrize("damage,named", [
    ("missing", "FileNotFoundError"), ("unreadable", "JSONDecodeError"),
], ids=["missing", "unreadable"])
def test_any_other_failure_refuses_by_its_type_alone(damage, named, tmp_path, capsys):
    path = tmp_path / "preparation.json"
    if damage == "unreadable":
        path.write_text("{not json")
    assert check.refusal(path) == named
    assert check.main(["--preparation", str(path)]) == 1
    assert capsys.readouterr().out.startswith(f"::error title=Source refused::{named}. ")


def test_the_check_run_as_the_step_runs_it_fails_the_step_on_a_refusal(tmp_path):
    # The step reads the program's exit status, not main()'s return value: run the module as the step does, with no
    # setting or credential in its environment and stdout piped, as in CI.
    cases, data = preparation(tmp_path)
    path = _written(tmp_path, data)
    env = {"PATH": os.environ.get("PATH", os.defpath), "HOME": str(tmp_path)}
    if os.environ.get("LD_LIBRARY_PATH"):  # setup-python's shared libpython on CI runners
        env["LD_LIBRARY_PATH"] = os.environ["LD_LIBRARY_PATH"]

    def run():
        return subprocess.run([sys.executable, "-m", "evals.copilot_source_check", "--preparation", str(path)],
                              cwd=Path(check.__file__).resolve().parents[1], env=env, capture_output=True, text=True,
                              timeout=60)

    passed = run()
    assert (passed.returncode, passed.stdout) == (
        0, "source check: every prepared source is the one its golden case declares\n"), passed.stderr
    DAMAGES["fallback"](data, cases)
    path.write_text(json.dumps(data))
    refused = run()
    assert refused.returncode == 1, refused.stdout + refused.stderr
    assert refused.stdout.startswith(f"::error title=Source refused::{check._command_value(check.refusal(path))}. ")


def test_a_long_reason_is_cut_as_the_runner_cuts_it(tmp_path, monkeypatch):
    def refuse(preparation, cases):
        raise ValueError("x" * 300)
    monkeypatch.setattr(check, "validate_preparation", refuse)
    assert check.refusal(tmp_path / "preparation.json") == "x" * 200


def test_a_reason_is_written_as_one_workflow_command_value(monkeypatch, capsys):
    monkeypatch.setattr(check, "refusal", lambda preparation: "100% of\nmda\r::warning::x")
    assert check.main(["--preparation", "unused.json"]) == 1
    printed = capsys.readouterr().out
    assert printed.startswith("::error title=Source refused::100%25 of%0Amda%0D::warning::x. ")
    assert printed.count("\n") == 1


def _steps():
    return yaml.safe_load(WORKFLOW.read_text())["jobs"]["copilot-eval"]["steps"]


def _commands(step) -> list[str]:
    return [line.strip() for line in step["run"].splitlines() if line.strip() and not line.strip().startswith("#")]


def test_the_source_check_is_the_preparation_steps_last_act_and_the_runner_keeps_its_own():
    steps = _steps()
    prepare = next(s for s in steps if s.get("name", "").startswith("Prepare actual"))
    counted = next(s for s in steps if s.get("name") == gate.RUNNER_STEP)
    # The check fails the step just before the one the draw gate counts, under bash's -eo pipefail, so its exit
    # status reaches the step through tee.
    assert steps.index(counted) == steps.index(prepare) + 1
    assert prepare.get("shell") == "bash" and counted.get("shell") == "bash"
    assert prepare["if"] == counted["if"] == "steps.draw.outputs.draw == 'true'"
    bootstrap, source_check = _commands(prepare)[-2:]
    assert bootstrap.startswith("python -m evals.copilot_bootstrap ") and "--output evals/reports/copilot " in bootstrap
    assert source_check == (f"python -m evals.copilot_source_check --preparation {PREPARATION} 2>&1 "
                            "| tee evals/reports/copilot/source-check.log")
    # The runner reads the same preparation and refuses it again before any provider call (the next test).
    assert f"--preparation {PREPARATION}" in _commands(counted)[-1]
    assert check.validate_preparation is runner.validate_preparation


@pytest.mark.parametrize("damage", DAMAGES, ids=DAMAGES)
def test_the_runner_still_refuses_a_source_the_check_would_refuse_before_any_provider_call(damage, tmp_path,
                                                                                          monkeypatch):
    # The backstop: with the check skipped or removed, the runner's own preflight refuses each damage before its run
    # starts, so no provider is called (and the head's draw is spent, the cost the check avoids).
    import sys
    from app.config import settings
    cases, data = preparation(tmp_path)
    DAMAGES[damage](data, cases)
    path = _written(tmp_path, data)
    monkeypatch.setenv("GITHUB_SHA", "1" * 40)
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "offline-test")
    called = []

    async def run(**kwargs):
        called.append(True)
        return {"accepted": True}
    monkeypatch.setattr(runner, "run", run)
    monkeypatch.setattr(sys, "argv", ["copilot_runner", "--preparation", str(path), "--output", str(tmp_path / "out")])
    assert runner.main() == 1 and called == []
    report = json.loads((tmp_path / "out" / "copilot-eval.json").read_text())
    assert report["failures"] == ["preflight failed: " + check.refusal(path)]


def test_a_refused_source_fails_the_preparation_step_and_spends_no_draw(tmp_path):
    prepare = next(s for s in _steps() if s.get("name", "").startswith("Prepare actual"))
    # The exact step under Actions' bash (shell: bash), with Python stubbed: real bash and tee must fail the step on
    # the check's exit, keep both logs, and never run the check after a bootstrap that failed (an outage is not a
    # refusal).
    executable = tmp_path / "python"
    executable.write_text('#!/bin/sh\ncase "$*" in\n  *copilot_source_check*) echo check-evidence; exit "$CHECK_EXIT";;\n'
                          '  *) echo preparation-evidence; exit "$PREP_EXIT";;\nesac\n')
    executable.chmod(0o755)
    script = tmp_path / "step.sh"
    script.write_text(prepare["run"])
    reports = tmp_path / "evals/reports/copilot"
    for prep_exit, check_exit, status in ((0, 0, 0), (0, 19, 19), (17, 0, 17)):
        for log in reports.glob("*.log"):
            log.unlink()
        env = {**os.environ, "PATH": str(tmp_path) + os.pathsep + os.environ["PATH"], "RUNNER_TEMP": str(tmp_path),
               "PREP_EXIT": str(prep_exit), "CHECK_EXIT": str(check_exit)}
        result = subprocess.run(["bash", "--noprofile", "--norc", "-eo", "pipefail", str(script)], cwd=tmp_path,
                                env=env, capture_output=True, text=True, timeout=5)
        assert result.returncode == status, (prep_exit, check_exit, result.stdout, result.stderr)
        assert (reports / "preparation.log").read_text() == "preparation-evidence\n"
        checked = reports / "source-check.log"
        assert (checked.read_text() if checked.exists() else None) == (None if prep_exit else "check-evidence\n")
    # The runner step after a failed preparation step is skipped, and the draw gate counts no draw for it.
    def fetch(path):
        return {"jobs": [{"name": "copilot-eval", "html_url": "https://github.com/o/r/actions/runs/1/job/1", "steps": [
            {"name": prepare["name"], "status": "completed", "conclusion": "failure"},
            {"name": gate.RUNNER_STEP, "status": "completed", "conclusion": "skipped"},
        ]}]}
    assert gate.attempt_draw(fetch, "o/r", 1, 1) is None
