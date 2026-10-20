"""Workflow hygiene gates for operational workflows (rule 12; structural, no dispatches).

Dispatch inputs are attacker-shaped text. A ``${{ inputs.* }}`` expression inside a ``run:`` block
is substituted into the script before the shell parses it, so the text is executed, not validated.
Inputs must reach a step through ``env:`` and be read as ``$NAME``. The same holds for step and job
outputs (``${{ steps.*.outputs.* }}``, ``${{ needs.*.outputs.* }}``): an output is derived from input
text, and a value written to ``$GITHUB_OUTPUT`` as ``name=value`` lines can redefine another output
when it carries a line break, so an unused field must be bounded before anything is written. The ops
workflow runs against production with the deployer identity, so it also runs only from ``main`` and
never persists the checkout token. Its fiscal-year relabel step passes ``--apply`` only for the apply
operation, runs every other operation read-only, reads the session's settings back and stops unless they
are its own before the script runs, and fails with the script.
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
    jobs = _workflow("ops.yml")["jobs"]
    job = jobs["ops"]
    # Each job opens its if: with the main-ref check as a conjunct no || can bypass; the ops job also
    # runs only once the founder's approval job has passed or been skipped
    # (test_ops_workflow_wiring.py::test_every_apply_operation_waits_for_the_founders_approval).
    assert {name: job.get("if") for name, job in jobs.items()} == {
        "approve-apply": "github.ref == 'refs/heads/main' && contains('relabel-fy-apply repair-ticker-apply "
                         "reset-filing-summary-apply', inputs.operation)",
        "ops": "${{ !cancelled() && github.ref == 'refs/heads/main' && (needs.approve-apply.result == 'success' "
               "|| needs.approve-apply.result == 'skipped') }}",
    }, "ops.yml must refuse dispatches from any ref but main so only the reviewed definition can act on production"
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
    ("relabel-fy-dry-run", ",".join(f"T{i}" for i in range(50))),
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


def _readback(op, lock="10s", statement="2min"):
    """The line Postgres prints for the step's guards, as the relabel step's readback query reads them."""
    return f"session read_only={'off' if op == 'relabel-fy-apply' else 'on'} lock_timeout={lock} statement_timeout={statement}"


def _run_relabel_step(tmp_path, op, tickers, *, python_exit=0, psql_exit=0, readback=None):
    """The relabel step's own script, run as GitHub runs it (`bash -e`) with stand-ins for `psql` and
    `python` that record their arguments and the PGOPTIONS each sees. The `psql` stand-in prints
    ``readback`` as the session's settings: by default, the line Postgres prints for the step's own."""
    step = next(s for s in _workflow("ops.yml")["jobs"]["ops"]["steps"]
                if s.get("name") == "Run fiscal-year relabel script")
    bin_dir, scripts = tmp_path / "bin", tmp_path / "scripts"
    bin_dir.mkdir()
    scripts.mkdir()
    (scripts / "relabel_filing_fy_facts.py").write_text("")
    # psql answers only the readback query, which must read the three settings in this order.
    answer = ('case "$*" in *"current_setting(\'default_transaction_read_only\')"*"current_setting(\'lock_timeout\')"*'
              '"current_setting(\'statement_timeout\')"*) printf "%s\\n" "$READBACK" ;; *) echo "unexpected query" ;; esac\n')
    for tool, code in (("python", python_exit), ("psql", psql_exit)):
        stand_in = bin_dir / tool
        stand_in.write_text(f'#!/bin/sh\nprintf "%s %s\\n" {tool} "$*" >> "$CALLS"\n'
                            f'printf "PGOPTIONS=%s\\n" "$PGOPTIONS" >> "$CALLS"\n{answer if tool == "psql" else ""}exit {code}\n')
        stand_in.chmod(0o755)
    env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}", "OP": op, "TICKERS": tickers,
           "CALLS": str(tmp_path / "calls"), "PGOPTIONS": step["env"]["PGOPTIONS"],
           "READBACK": _readback(op) if readback is None else readback}
    result = subprocess.run(  # fixed argv; the script under test is repository content
        ["bash", "-e", "-c", step["run"]], cwd=tmp_path, env=env, capture_output=True, text=True, check=False
    )
    calls = (tmp_path / "calls").read_text().splitlines() if (tmp_path / "calls").exists() else []
    return step, result, calls


@pytest.mark.parametrize("op, tickers, args", [
    ("relabel-fy-dry-run", "", ""),
    ("relabel-fy-dry-run", "TGT,JNJ", " --tickers TGT,JNJ"),
    ("relabel-fy-apply", "", " --apply"),
    ("relabel-fy-apply", "TGT", " --apply --tickers TGT"),
    # Any operation but the apply runs a read-only dry run, so a widened if: can never write.
    ("repair-ticker-apply", "", ""),
])
def test_only_the_relabel_apply_operation_passes_apply_and_a_dry_run_is_read_only(tmp_path, op, tickers, args):
    """The relabel script writes production data only with --apply, so only the apply operation may
    pass it, and any other run's transactions are read-only, so Postgres refuses a write it might
    attempt. The settings the session gets are read back through psql before the script runs."""
    step, result, calls = _run_relabel_step(tmp_path, op, tickers)
    assert result.returncode == 0, result.stderr
    options = step["env"]["PGOPTIONS"] + ("" if op == "relabel-fy-apply" else " -c default_transaction_read_only=on")
    assert [call for call in calls if call.startswith("python ")] == [f"python scripts/relabel_filing_fy_facts.py{args}"]
    assert [call for call in calls if call.startswith("PGOPTIONS=")] == [f"PGOPTIONS={options}"] * 2
    assert calls[0].startswith("psql "), "the readback runs before the script"


def test_a_failed_relabel_run_fails_the_step(tmp_path):
    """A company that fails makes the script exit non-zero, and the run must fail with it."""
    _, result, _ = _run_relabel_step(tmp_path, "relabel-fy-apply", "", python_exit=3)
    assert result.returncode == 3


def test_no_relabel_runs_when_the_session_settings_cannot_be_read(tmp_path):
    _, result, calls = _run_relabel_step(tmp_path, "relabel-fy-apply", "", psql_exit=2)
    assert result.returncode == 2
    assert not [call for call in calls if call.startswith("python ")]


@pytest.mark.parametrize("op, readback", [
    ("relabel-fy-dry-run", _readback("relabel-fy-apply")),  # a dry run whose transactions could write
    ("relabel-fy-apply", _readback("relabel-fy-apply", lock="0")),  # no lock bound: a later -c 0 won
    ("relabel-fy-apply", _readback("relabel-fy-apply", statement="0")),
    ("relabel-fy-dry-run", ""),  # psql printed nothing
])
def test_no_relabel_runs_when_the_session_reports_other_settings_than_the_steps(tmp_path, op, readback):
    """The readback is a check, not only a log line: a session whose settings are not the step's
    stops the run before the script opens one."""
    _, result, calls = _run_relabel_step(tmp_path, op, "", readback=readback)
    assert result.returncode == 1
    assert "the session's settings are not this step's" in result.stdout
    assert not [call for call in calls if call.startswith("python ")]
