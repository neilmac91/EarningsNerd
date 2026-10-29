"""Workflow hygiene gates for operational workflows (rule 12; structural, no dispatches).

Dispatch inputs are attacker-shaped text. A ``${{ inputs.* }}`` expression inside a ``run:`` block
is substituted into the script before the shell parses it, so the text is executed, not validated.
Inputs must reach a step through ``env:`` and be read as ``$NAME``. The same holds for step and job
outputs (``${{ steps.*.outputs.* }}``, ``${{ needs.*.outputs.* }}``): an output is derived from input
text, and a value written to ``$GITHUB_OUTPUT`` as ``name=value`` lines can redefine another output
when it carries a line break, so an unused field must be bounded before anything is written. The ops
workflow runs against production with the deployer identity, so it also runs only from ``main`` and
never persists the checkout token. Its fiscal-year relabel, quarterly fact repair and lineage backfill
steps each pass ``--apply`` only for their own apply operation, run every other operation read-only,
read the session's settings back and stop unless they are their own before the script runs, and fail
with the script. The quarterly repair also needs an explicit list of at most 50 tickers and writes its
report where the next step keeps it; the relabel and the lineage backfill take an optional list of at
most 50, and none means every company. The workflow's approval check lets an apply through only when the run's own review
history records an approval of ``ops-apply``, and reads any other answer, an unreadable one included,
as none.
"""
import json
import os
import shutil
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


def _conjuncts(condition: str) -> tuple[list[str], bool]:
    """An if:'s top-level `&&` terms, and whether a top-level `||` could bypass them."""
    condition = condition.strip()
    if condition.startswith("${{") and condition.endswith("}}"):
        condition = condition[3:-2].strip()
    terms, depth, start, bypass = [], 0, 0, False
    for at, char in enumerate(condition):
        depth += {"(": 1, ")": -1}.get(char, 0)
        if depth == 0 and condition.startswith("&&", at):
            terms.append(condition[start:at].strip())
            start = at + 2
        bypass = bypass or (depth == 0 and condition.startswith("||", at))
    return [*terms, condition[start:].strip()], bypass


def test_ops_workflow_runs_only_from_main_without_persisted_credentials():
    jobs = _workflow("ops.yml")["jobs"]
    job = jobs["ops"]
    # Every job's if: holds the main-ref check as a top-level term that no top-level || can bypass. What
    # else each holds is the approval wiring's gate (test_ops_workflow_wiring.py).
    for name, each in jobs.items():
        terms, bypass = _conjuncts(each.get("if") or "")
        assert "github.ref == 'refs/heads/main'" in terms and not bypass, (
            f"ops.yml job {name!r} must refuse dispatches from any ref but main so only the reviewed "
            f"definition can act on production: {each.get('if')!r}")
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


def _readback(op, lock="10s", statement="2min", apply_op="relabel-fy-apply"):
    """The line Postgres prints for the step's guards, as a script step's readback query reads them."""
    return f"session read_only={'off' if op == apply_op else 'on'} lock_timeout={lock} statement_timeout={statement}"


def _run_relabel_step(tmp_path, op, tickers, **kwargs):
    return _run_script_step(tmp_path, "Run fiscal-year relabel script", "relabel_filing_fy_facts.py", op, tickers,
                            apply_op="relabel-fy-apply", **kwargs)


def _run_script_step(tmp_path, name, script, op, tickers, *, apply_op, python_exit=0, psql_exit=0, readback=None):
    """A script step's own script, run as GitHub runs it (`bash -e`) with stand-ins for `psql` and
    `python` that record their arguments and the PGOPTIONS each sees. The `psql` stand-in prints
    ``readback`` as the session's settings: by default, the line Postgres prints for the step's own."""
    step = next(s for s in _workflow("ops.yml")["jobs"]["ops"]["steps"] if s.get("name") == name)
    bin_dir, scripts = tmp_path / "bin", tmp_path / "scripts"
    bin_dir.mkdir()
    scripts.mkdir()
    (scripts / script).write_text("")
    # psql answers only the readback query, which must read the three settings in this order.
    answer = ('case "$*" in *"current_setting(\'default_transaction_read_only\')"*"current_setting(\'lock_timeout\')"*'
              '"current_setting(\'statement_timeout\')"*) printf "%s\\n" "$READBACK" ;; *) echo "unexpected query" ;; esac\n')
    for tool, code in (("python", python_exit), ("psql", psql_exit)):
        stand_in = bin_dir / tool
        stand_in.write_text(f'#!/bin/sh\nprintf "%s %s\\n" {tool} "$*" >> "$CALLS"\n'
                            f'printf "PGOPTIONS=%s\\n" "$PGOPTIONS" >> "$CALLS"\n{answer if tool == "psql" else ""}exit {code}\n')
        stand_in.chmod(0o755)
    env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}", "OP": op, "TICKERS": tickers,
           "CALLS": str(tmp_path / "calls"), "PGOPTIONS": step["env"]["PGOPTIONS"], "RUNNER_TEMP": str(tmp_path / "temp"),
           "READBACK": _readback(op, apply_op=apply_op) if readback is None else readback}
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


QUARTERLY, QUARTERLY_APPLY = "Run quarterly fact repair script", "repair-quarterly-apply"


def _run_quarterly_step(tmp_path, op, tickers, **kwargs):
    return _run_script_step(tmp_path, QUARTERLY, "repair_quarterly_facts.py", op, tickers, apply_op=QUARTERLY_APPLY, **kwargs)


@pytest.mark.parametrize("op, tickers", [
    ("repair-quarterly-dry-run", "TGT,JNJ"), ("repair-quarterly-apply", "BRK.B"),
    ("repair-quarterly-dry-run", ",".join(f"T{i}" for i in range(50))),
])
def test_resolve_step_accepts_a_quarterly_repair_over_an_explicit_ticker_list(tmp_path, op, tickers):
    code, output = _run_resolve(tmp_path, OP=op, TICKERS=tickers)
    assert code == 0
    assert output.splitlines() == [f"operation={op}", f"tickers={tickers}", "revision="]


@pytest.mark.parametrize("op", ["repair-quarterly-dry-run", "repair-quarterly-apply"])
@pytest.mark.parametrize("tickers", ["", "TGT;JNJ", "TGT,,JNJ", ",".join(f"T{i}" for i in range(51))])
def test_resolve_step_refuses_a_quarterly_repair_without_an_explicit_bounded_ticker_list(tmp_path, op, tickers):
    """The repair takes explicit tickers only (docs/quarterly-data-repair.md): never every company."""
    code, output = _run_resolve(tmp_path, OP=op, TICKERS=tickers)
    assert code != 0
    assert output == ""


@pytest.mark.parametrize("op, tickers, apply", [
    ("repair-quarterly-dry-run", "TGT,JNJ", False),
    ("repair-quarterly-apply", "TGT", True),
    # Any operation but the apply runs a read-only preview, so a widened if: can never write.
    ("relabel-fy-apply", "TGT", False),
])
def test_only_the_quarterly_apply_passes_apply_and_a_preview_is_read_only(tmp_path, op, tickers, apply):
    """The repair writes production data only with --apply, so only its apply operation passes it, and
    any other run's transactions are read-only. The report goes to the file the next step keeps."""
    step, result, calls = _run_quarterly_step(tmp_path, op, tickers)
    assert result.returncode == 0, result.stderr
    report = tmp_path / "temp" / "quarterly-repair" / "report.json"
    expected = f"python scripts/repair_quarterly_facts.py --tickers {tickers} --limit 50 --output {report}"
    assert [call for call in calls if call.startswith("python ")] == [expected + (" --apply" if apply else "")]
    options = step["env"]["PGOPTIONS"] + ("" if apply else " -c default_transaction_read_only=on")
    assert [call for call in calls if call.startswith("PGOPTIONS=")] == [f"PGOPTIONS={options}"] * 2
    assert calls[0].startswith("psql "), "the readback runs before the script"
    assert report.parent.is_dir(), "the report's directory exists before the script writes it"


@pytest.mark.parametrize("kwargs, code", [
    ({"python_exit": 3}, 3),  # a failed company fails the step
    ({"psql_exit": 2}, 2),  # the session settings could not be read: no script
    ({"readback": _readback("repair-quarterly-apply", apply_op=QUARTERLY_APPLY)}, 1),  # a preview that could write
    ({"readback": _readback("repair-quarterly-dry-run", lock="0", apply_op=QUARTERLY_APPLY)}, 1),
])
def test_a_quarterly_repair_stops_on_a_failed_company_or_a_session_that_is_not_the_steps(tmp_path, kwargs, code):
    _, result, calls = _run_quarterly_step(tmp_path, "repair-quarterly-dry-run", "TGT", **kwargs)
    assert result.returncode == code
    ran = [call for call in calls if call.startswith("python ")]
    assert bool(ran) == ("python_exit" in kwargs)


def test_a_quarterly_repair_with_no_tickers_runs_nothing(tmp_path):
    _, result, calls = _run_quarterly_step(tmp_path, "repair-quarterly-apply", "")
    assert result.returncode == 1 and "tickers input required" in result.stdout
    assert calls == []


REPO, RUN_ID = "neilmac91/EarningsNerd", "39360634523"


OWNER = "neilmac91"  # github.repository_owner, the founder's account


def _review(state: str, *environments: str, login: str = OWNER) -> dict:
    """One entry of a run's review history, as GitHub's approvals endpoint returns it."""
    return {"state": state, "comment": "", "environments": [{"id": 1, "name": name} for name in environments],
            "user": {"login": login}}


def _run_approval_check(tmp_path, body: str, *, gh_exit=0, owner=OWNER):
    """The approval check's own script, run as GitHub runs it (`bash -e`) with a stand-in `gh` that records
    its arguments, one per line, and answers with ``body``: through the real `jq` with the `--jq` filter it
    was given (gh's own --jq is gojq; the filter uses nothing where the two differ), or, when it exits
    non-zero, unfiltered, as gh prints the body of an HTTP error."""
    if shutil.which("jq") is None:
        if os.environ.get("GITHUB_ACTIONS") == "true":
            pytest.fail("jq is missing, though CI's ubuntu-latest image carries it")
        pytest.skip("jq is not installed; CI runs this")
    step = next(s for s in _workflow("ops.yml")["jobs"]["ops"]["steps"]
                if s.get("name") == "Refuse an apply that no one approved in this run")
    assert step["env"]["OWNER"] == "${{ github.repository_owner }}"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "gh").write_text(
        '#!/bin/sh\nprintf "%s\\n" "$@" >> "$CALLS"\n'
        'if [ "$GH_EXIT" != 0 ]; then printf "%s" "$GH_BODY"; echo "gh: Not Found (HTTP 404)" >&2; exit "$GH_EXIT"; fi\n'
        'while [ $# -gt 1 ] && [ "$1" != --jq ] && [ "$1" != -q ]; do shift; done\n'
        '[ $# -gt 1 ] || { echo "stand-in gh: no --jq filter" >&2; exit 64; }\n'
        'printf "%s" "$GH_BODY" | jq -r "$2"\n')
    (bin_dir / "gh").chmod(0o755)
    env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}", "CALLS": str(tmp_path / "calls"),
           "GH_BODY": body, "GH_EXIT": str(gh_exit), "GITHUB_REPOSITORY": REPO, "GITHUB_RUN_ID": RUN_ID,
           "OWNER": owner}
    result = subprocess.run(  # fixed argv; the script under test is repository content
        ["bash", "-e", "-c", step["run"]], cwd=tmp_path, env=env, capture_output=True, text=True, check=False
    )
    calls = (tmp_path / "calls").read_text().splitlines() if (tmp_path / "calls").exists() else []
    return result, calls


@pytest.mark.parametrize("body, gh_exit, code", [
    pytest.param(json.dumps([_review("approved", "ops-apply")]), 0, 0, id="approved"),
    pytest.param(json.dumps([_review("approved", "ops-apply")] * 2), 0, 0, id="approved-twice"),
    pytest.param("[]", 0, 1, id="no-review"),
    pytest.param(json.dumps([_review("rejected", "ops-apply")]), 0, 1, id="rejected"),
    pytest.param(json.dumps([_review("approved", "github-pages")]), 0, 1, id="another-environment"),
    pytest.param(json.dumps([_review("pending", "ops-apply")]), 0, 1, id="pending"),
    # Only the repository owner's approval counts: a reviewer added to ops-apply later cannot approve.
    pytest.param(json.dumps([_review("approved", "ops-apply", login="another-reviewer")]), 0, 1, id="not-the-owner"),
    pytest.param("<html>Unicorn!</html>", 0, 1, id="not-json"),
    pytest.param(json.dumps({"message": "Not Found", "status": "404"}), 1, 1, id="http-404"),
])
def test_an_apply_runs_only_when_this_run_records_an_approval_of_ops_apply(tmp_path, body, gh_exit, code):
    """approve-apply passes at once while the environment requires no reviewer, so the check reads this
    run's review history: an apply runs only when it records an approval of ops-apply, and any other
    answer, one gh could not read included, counts as none."""
    result, calls = _run_approval_check(tmp_path, body, gh_exit=gh_exit)
    assert result.returncode == code, result.stdout + result.stderr
    assert calls[:3] == ["api", f"repos/{REPO}/actions/runs/{RUN_ID}/approvals", "--jq"] and len(calls) == 4, calls
    refused = "::error::no approval of ops-apply is recorded for this run" in result.stdout
    assert refused == (code == 1), result.stdout


# The second would widen the filter to every approval if it were spliced in unchecked.
@pytest.mark.parametrize("owner", ["", 'x" or "a" == "a', "neil mac"])
def test_an_owner_that_is_not_a_github_login_matches_no_approval(tmp_path, owner):
    """The owner's login is spliced into the filter, so anything that is not a login matches nothing."""
    approvals = [_review("approved", "ops-apply"), _review("approved", "ops-apply", login="another-reviewer")]
    result, _ = _run_approval_check(tmp_path, json.dumps(approvals), owner=owner)
    assert result.returncode == 1 and "::error::no approval of ops-apply" in result.stdout, result.stdout


LINEAGE, LINEAGE_APPLY = "Run filing lineage backfill script", "repair-lineage-apply"


@pytest.mark.parametrize("op", ["repair-lineage-dry-run", LINEAGE_APPLY])
@pytest.mark.parametrize("tickers", ["", "REGN,JNJ", "BRK.B", ",".join(f"T{i}" for i in range(50))])
def test_resolve_step_accepts_a_lineage_backfill_over_every_company_or_a_ticker_list(tmp_path, op, tickers):
    code, output = _run_resolve(tmp_path, OP=op, TICKERS=tickers)
    assert code == 0
    assert output.splitlines() == [f"operation={op}", f"tickers={tickers}", "revision="]


@pytest.mark.parametrize("op", ["repair-lineage-dry-run", LINEAGE_APPLY])
@pytest.mark.parametrize("tickers", ["REGN;JNJ", "REGN,,JNJ", ",".join(f"T{i}" for i in range(51))])
def test_resolve_step_rejects_a_malformed_or_oversized_lineage_ticker_list(tmp_path, op, tickers):
    code, output = _run_resolve(tmp_path, OP=op, TICKERS=tickers)
    assert code != 0
    assert output == ""


def _run_lineage_step(tmp_path, op, tickers, **kwargs):
    return _run_script_step(tmp_path, LINEAGE, "repair_filing_lineage.py", op, tickers, apply_op=LINEAGE_APPLY, **kwargs)


@pytest.mark.parametrize("op, tickers, args", [
    ("repair-lineage-dry-run", "", ""),
    ("repair-lineage-dry-run", "REGN,JNJ", " --tickers REGN,JNJ"),
    (LINEAGE_APPLY, "", " --apply"),
    (LINEAGE_APPLY, "REGN", " --apply --tickers REGN"),
    # Any operation but the apply runs a read-only dry run, so a widened if: can never write.
    ("relabel-fy-apply", "", ""),
])
def test_only_the_lineage_apply_passes_apply_and_a_dry_run_is_read_only(tmp_path, op, tickers, args):
    """The backfill writes production data only with --apply, so only its apply operation passes it, and
    any other run's transactions are read-only, so Postgres refuses a write it might attempt. The
    settings the session gets are read back through psql before the script runs."""
    step, result, calls = _run_lineage_step(tmp_path, op, tickers)
    assert result.returncode == 0, result.stderr
    options = step["env"]["PGOPTIONS"] + ("" if op == LINEAGE_APPLY else " -c default_transaction_read_only=on")
    assert [call for call in calls if call.startswith("python ")] == [f"python scripts/repair_filing_lineage.py{args}"]
    assert [call for call in calls if call.startswith("PGOPTIONS=")] == [f"PGOPTIONS={options}"] * 2
    assert calls[0].startswith("psql "), "the readback runs before the script"


@pytest.mark.parametrize("kwargs, code", [
    ({"python_exit": 3}, 3),  # a failed company fails the step
    ({"psql_exit": 2}, 2),  # the session settings could not be read: no script
    ({"readback": _readback(LINEAGE_APPLY, apply_op=LINEAGE_APPLY)}, 1),  # a dry run whose transactions could write
    ({"readback": _readback("repair-lineage-dry-run", lock="0", apply_op=LINEAGE_APPLY)}, 1),  # no lock bound
    ({"readback": _readback("repair-lineage-dry-run", statement="0", apply_op=LINEAGE_APPLY)}, 1),
    ({"readback": ""}, 1),  # psql printed nothing
])
def test_a_lineage_backfill_stops_on_a_failed_company_or_a_session_that_is_not_the_steps(tmp_path, kwargs, code):
    """The readback is a check, not only a log line: a session whose settings are not the step's stops the
    run before the script opens one, and a failed company fails the step."""
    _, result, calls = _run_lineage_step(tmp_path, "repair-lineage-dry-run", "", **kwargs)
    assert result.returncode == code
    assert ("the session's settings are not this step's" in result.stdout) == (code == 1)
    ran = [call for call in calls if call.startswith("python ")]
    assert bool(ran) == ("python_exit" in kwargs)
