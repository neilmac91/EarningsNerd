"""How `.github/workflows/ops.yml` wires the figure-impact operation (E184): read-only, its report counts only.

`backend/scripts/figure_check_impact.py` counts what the strict figure check changes over a cohort of stored
summaries. The dispatch names the cohort as a range of summary ids, with no default, which a step bounds before the
sign-in and before the script builds its id list: positive ids of at most nine digits, in order, spanning at most the
script's own MAX_COHORT. The script runs after the proxy and the dependency install, in a session that is read-only and
held to the relabel step's bounds, read back before it runs, with the relabel step's hermetic environment and nothing
else. The steps a dispatch runs are pinned (a shared one as `selected()` reads its condition, past a leading
`always()`), with the validation's and the count's conditions as written, their keys and timeouts, and the retain step
whole, and no shared step a dispatch runs may carry `always()`; none of them may continue past an error, no step of any
workflow but the count names the script, and outside a condition no step of any workflow but the resolve step, the
validation, the count and the upload names the receipt's folder.

The count step is run here as GitHub runs it, for two cohorts, in its working directory under an empty one, with no
stdin, the proxy step's exports, the step's own env (its cohort ids the run's) kept off every other name the run sets,
and a PATH that holds only `mkdir` and stand-ins for `psql`, the script and `gcloud`; any other command it names is
recorded by bash's `command_not_found_handle`, which the step cannot redefine, even one whose failure it hides or a
child bash runs; the run fails unless the step's own bash loaded that handler, or if the step's text opens a connection
of bash's own (`/dev/tcp`, `/dev/udp`), which no stand-in would see, and a host whose bash predates 4.0 and the handler
(a Mac's own /bin/bash) skips the runs. Each `psql` session and the script's call are recorded with each PG* variable
and the DATABASE_URL they see, which must be the proxy step's exports and the step's PGOPTIONS, nothing else. Whatever a
stand-in prints, but the read-back's line, which the step prints to its log, lands in the receipt and nowhere this test
reads, each session's and the script's error output in order in `stderr.txt`: the step's stdout carries the read-back's
line, when the session started, and one line of its own, whose one variable part is a failed count's exit code, its
stderr nothing, and the run's summary, outputs and environment nothing. A session that cannot start, or whose read-back
is not the step's, stops it before the script, as does a failed read of the summaries' range, and a failed count fails
it with the script's own exit code. The last step keeps whatever the count step wrote; a run stopped before that step
has nothing to keep, and the upload then warns.

The receipt is the run's artifact, which any signed-in GitHub user can download while it is kept (this repository is
public). That the script's report holds counts only is its own tests' to hold; `stderr.txt` holds the reads' and the
script's error output, which no test holds to counts (a traceback can carry SQL text and the cohort's summary ids). The
rules every Ops step follows stay with their own gates: test_ops_workflow_wiring.py (the proxy and the install before a
script, the SEC budgets, and the PGOPTIONS-only session settings, whose scripts it reads from this workflow),
test_migration_lock_safety.py (the lock and statement bounds) and test_workflow_dispatch_inputs.py (no input
interpolated into a script). Review-checked, not gated: the script reached through a name or a path the step's text does
not spell (a variable, a glob), a command the step runs by an absolute path (or one a variable holds), by `exec`, by
`command -p` or on a PATH it sets itself, a connection of bash's own whose path its text does not spell (a variable
naming `/dev/tcp`), a file the step sources, and the receipt's folder reached by a glob, a variable or a quoted
spelling.
"""
import ast
import json
import os
import re
import shutil
import subprocess

import pytest
import yaml

from tests.support.ops_workflow import (BY_NAME, DEPS, INPUTS, OPTIONS, PROXY, RESOLVE, ROOT, STEPS, pg_settings,
                                        selected, setting_ms)
from tests.unit.test_ops_readback_allow_rules import _never_runs_for_a_read

OPERATION = "figure-impact"
VALIDATE = "Validate the bounded figure-impact cohort"
COUNT = "Count the strict figure check's impact (E184)"
RETAIN = "Retain the figure-impact receipt"
PREFLIGHT = "Refuse to run while a main push (deploy) is in flight"
SIGN_IN = "Authenticate to Google Cloud"
RELABEL = "Run fiscal-year relabel script"
# Every step a dispatch runs, in order: a step added for the operation is a change to what it reads or prints.
RUNS = ["actions/checkout@v7", RESOLVE, PREFLIGHT, VALIDATE, SIGN_IN, "Set up gcloud", PROXY, DEPS, COUNT, RETAIN]
CONDITION = "steps.request.outputs.operation == 'figure-impact'"
# Each step's keys and timeout.
SHAPES = {VALIDATE: ({"name", "if", "env", "run"}, None),
          COUNT: ({"name", "if", "working-directory", "timeout-minutes", "env", "run"}, "30")}
SCRIPT = ROOT / "backend/scripts/figure_check_impact.py"
IDS = {"FROM_ID": "${{ inputs.summary_from_id }}", "TO_ID": "${{ inputs.summary_to_id }}"}
# The relabel step's hermetic environment, which the count step takes whole beside its own guards and cohort.
HERMETIC = ("SEC_RATE_LIMIT_PER_SECOND", "EDGAR_RATE_LIMIT_PER_SEC", "SKIP_REDIS_INIT", "SECRET_KEY",
            "STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET", "PWNED_PASSWORD_CHECK_ENABLED")
PGOPTIONS = "-c lock_timeout=10s -c statement_timeout=120s -c default_transaction_read_only=on"
EXPECTED = "session read_only=on lock_timeout=10s statement_timeout=2min"
READBACK = ("SELECT 'session read_only=' || current_setting('default_transaction_read_only') || ' lock_timeout=' || "
            "current_setting('lock_timeout') || ' statement_timeout=' || current_setting('statement_timeout')")
POPULATION = "SELECT min(id), max(id), count(*) FROM summaries"
# What the proxy step exports, which every session and the script must see unchanged.
PROXY_URL = "postgresql://ops:placeholder@127.0.0.1:5432/earningsnerd"
PROXY_ENV = {"PGHOST": "127.0.0.1", "PGPORT": "5432", "PGDATABASE": "earningsnerd", "PGUSER": "ops",
             "PGPASSWORD": "placeholder", "DATABASE_URL": PROXY_URL}
# Every PG* variable and the DATABASE_URL each session and the script see: those and the step's guards, nothing
# else (a PGHOSTADDR or a PGSERVICE would reach another server).
SEEN = {**PROXY_ENV, "PGOPTIONS": PGOPTIONS}
SAVED = "Figure-check impact counts saved to figure-impact/impact.json (the run's artifact).\n"
FAILED = "::error::The count failed (exit {}); its report and stderr are in the run's artifact, figure-impact/.\n"
NO_RANGE = "::error::The summaries' range could not be read; see figure-impact/stderr.txt in the run's artifact.\n"
NO_SESSION = "::error::The session's settings could not be read; see figure-impact/stderr.txt in the run's artifact.\n"
MISMATCH = f"::error::the session's settings are not this step's ({EXPECTED})\n"
RECEIPT = ["figure-impact/impact.json", "figure-impact/population.txt", "figure-impact/stderr.txt"]
SENTINEL = "PRIVATE_COUNT_SENTINEL 4242"
BASH = shutil.which("bash")
# The unknown-command record is bash's command_not_found_handle, which bash 4.0 added: under an older bash the step
# would run any command unrecorded, so its runs are skipped there.
BASH_MAJOR = int(subprocess.run([BASH, "-c", 'echo "${BASH_VERSINFO[0]}"'], capture_output=True, text=True).stdout)


def _cap() -> int:
    """The script's MAX_COHORT, read from its source rather than by running the module."""
    [value] = [node.value.value for node in ast.parse(SCRIPT.read_text()).body if isinstance(node, ast.Assign)
               and [getattr(target, "id", None) for target in node.targets] == ["MAX_COHORT"]]
    return value


def _label(step) -> str:
    return step.get("name") or step.get("uses")


def _steps_run(steps=STEPS):
    """The steps a dispatch of the operation runs: selected() where it reads the if:, and otherwise every step
    whose if: is not decisively false for the operation (another operation, or a step the dispatch skipped)."""
    runs, unrun = [], set()
    for step in steps:
        try:
            runs_here = OPERATION in selected(step)
        except AssertionError:
            runs_here = not _never_runs_for_a_read(step["if"], unrun, r"steps\.request\.outputs\.operation",
                                                   (OPERATION,))
        if runs_here:
            runs.append(step)
        elif step.get("id"):
            unrun.add(step["id"])
    return runs


def _record(tool: str) -> str:
    """A stand-in's record of its call: its arguments, then each PG* variable and DATABASE_URL it was given."""
    return ('{ printf "%s\\n" "$@"; echo ==; for name in $(compgen -e); do case $name in PG*|DATABASE_URL) '
            'printf "%s=%s\\n" "$name" "${!name}" ;; esac; done; echo --; } >> "$RECORDS/' + tool + '"\n')


def _calls(records, tool) -> list[tuple[list[str], dict[str, str]]]:
    """Each call a stand-in recorded: its arguments, and each PG* variable and DATABASE_URL it saw."""
    path = records / tool
    calls = []
    for call in path.read_text().split("\n--\n") if path.exists() else []:
        if call:
            lines = call.split("\n")
            at = lines.index("==")
            calls.append((lines[:at], dict(line.split("=", 1) for line in lines[at + 1:])))
    return calls


def _run_count(tmp_path, readback=EXPECTED, exit_code=0, psql_exit=0, range_exit=0, first="1", last="5000"):
    """The count step's own script, run as GitHub runs it (`bash -e`, with the step's env, the cohort `first` to `last`
    and the proxy step's exports) in its working directory, with a PATH that holds only `mkdir` and the stand-ins.
    `psql` records each session with each PG* variable and DATABASE_URL it sees; for the read-back it prints
    `readback` and SENTINEL marked `read-back` on its stderr, exiting `psql_exit`, and for any other query SENTINEL
    many times and, on its stderr, SENTINEL marked `range`, exiting `range_exit`. The script records its call and the
    same variables, writes SENTINEL many times to its stdout and SENTINEL marked `script` to its stderr, and exits
    `exit_code`; a python that is not the script, and `gcloud`, fail; any other command is recorded as unknown."""
    if BASH_MAJOR < 4:
        pytest.skip("the step's runs need bash 4.0 or later (GitHub's Ubuntu runner has 5)")
    bin_dir, records, github, work = (tmp_path / part for part in ("bin", "records", "github", "work"))
    for directory in (bin_dir, records, github, work / "backend"):
        directory.mkdir(parents=True)
    stand_ins = {
        "psql": _record("psql") +
                'case "$*" in *current_setting*) printf "%s\\n" "$READBACK"; printf "%s read-back\\n" "$SENTINEL" >&2\n'
                '  exit "$PSQL_EXIT" ;; esac\n'
                'printf "%s\\n" "$SENTINELS"; printf "%s range\\n" "$SENTINEL" >&2\nexit "$RANGE_EXIT"\n',
        "python": 'if [ "$1" = scripts/figure_check_impact.py ]; then\n  ' + _record("script") +
                  '  printf "%s\\n" "$SENTINELS"; printf "%s script\\n" "$SENTINEL" >&2\n  exit "$EXIT_CODE"\nfi\n'
                  '{ printf "%s\\n" "$@"; echo --; } >> "$RECORDS/python-other"\nexit 97\n',
        "gcloud": '{ printf "%s\\n" "$@"; echo --; } >> "$RECORDS/gcloud"\nexit 1\n',
    }
    for tool, body in stand_ins.items():
        (bin_dir / tool).write_text("#!/bin/bash\n" + body)
        (bin_dir / tool).chmod(0o755)
    (bin_dir / "mkdir").symlink_to(shutil.which("mkdir"))
    # Bash reads BASH_ENV before a non-interactive script: any command not on this PATH is recorded, `|| true` or not.
    # Every bash that loads it marks its parent: the stand-ins are bash too, so the step's own mark is this test's.
    (bin_dir / "unknown.sh").write_text('printf "%s\\n" "$PPID" >> "$RECORDS/bash-env"\n'
                                        'command_not_found_handle() { printf "%s\\n" "$1" >> "$RECORDS/unknown"; '
                                        'return 127; }\nreadonly -f command_not_found_handle\n'
                                        'export -f command_not_found_handle\n')  # a child bash keeps it
    files = {key: github / key.lower() for key in ("GITHUB_STEP_SUMMARY", "GITHUB_OUTPUT", "GITHUB_ENV", "GITHUB_PATH")}
    for path in files.values():
        path.touch()
    step = BY_NAME[COUNT][1]
    # Bash opens a /dev/tcp or /dev/udp path itself, as a connection no stand-in sees.
    assert not re.search(r"/dev/(?:tcp|udp)/", step["run"]), "the step opens a connection of bash's own"
    sandbox = {**{key: str(path) for key, path in files.items()}, **PROXY_ENV, "PATH": str(bin_dir),
               "BASH_ENV": str(bin_dir / "unknown.sh"), "RECORDS": str(records), "SENTINEL": SENTINEL,
               "SENTINELS": "\n".join([SENTINEL] * 50), "READBACK": readback, "EXIT_CODE": str(exit_code),
               "PSQL_EXIT": str(psql_exit), "RANGE_EXIT": str(range_exit),
               "SHLVL": "1"}  # past bash's sshd case, which skips BASH_ENV for a socket stdin or an SSH_CLIENT
    assert not set(step["env"]) & set(sandbox), "the step's env sets a name this run replaces"
    env = {**step["env"], **sandbox, "FROM_ID": first, "TO_ID": last}
    result = subprocess.run([BASH, "-e", "-c", step["run"]], cwd=work / step["working-directory"], env=env,
                            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=10)
    assert [path.name for path in records.iterdir() if path.name in ("python-other", "gcloud", "unknown")] == [], (
        "the step ran a command that is not one of its stand-ins")
    # A bash in POSIX mode, or one that otherwise skipped BASH_ENV, would run any command unrecorded.
    loaded = records / "bash-env"
    assert loaded.exists() and str(os.getpid()) in loaded.read_text().split(), (
        "the step's bash never loaded the unknown-command handler")
    return result, work, github, records


def _holding(work) -> list[str]:
    return sorted(path.relative_to(work).as_posix() for path in work.rglob("*")
                  if path.is_file() and SENTINEL.encode() in path.read_bytes())  # a file it writes need not be text


def test_a_dispatch_runs_the_pinned_steps_and_the_deploy_pre_flight_holds_the_count():
    assert OPERATION in OPTIONS
    # The cohort is the dispatch's to name: no default, so a dispatch that names none is refused.
    for name, description in (("summary_from_id", "figure-impact: the cohort's first summary id (the cohort spans at "
                                                   "most 5,000 ids)"),
                              ("summary_to_id", "figure-impact: the cohort's last summary id")):
        assert INPUTS[name] == {"description": description, "required": "false", "default": ""}, name
    runs = _steps_run()
    assert [_label(step) for step in runs] == RUNS
    # None of them, the pre-flight among them, may let a dispatch go on past its failure, and no step before the
    # upload may run always(): selected() reads past it, and the proxy would then start after a refused cohort.
    assert [_label(step) for step in runs if "continue-on-error" in step] == []
    assert [_label(step) for step in runs if "always()" in step.get("if", "")] == [RETAIN]
    # As written, not as selected() reads it: a leading always() would run the count after the pre-flight refused it.
    for name in (VALIDATE, COUNT):
        assert BY_NAME[name][1]["if"] == CONDITION, name


def test_a_step_whose_condition_selected_cannot_read_still_counts_as_one_the_dispatch_runs():
    show = {"name": "Show the counts", "uses": "actions/github-script@v8",
            "if": "${{ always() && steps.request.outputs.operation == 'figure-impact' && hashFiles('x') != '' }}"}
    at = BY_NAME[RETAIN][0]
    assert [_label(step) for step in _steps_run([*STEPS[:at], show, *STEPS[at:]])] == [*RUNS[:-1], "Show the counts",
                                                                                      RETAIN]


def test_each_step_is_bounded_and_the_count_takes_the_relabel_step_s_environment_whole():
    for name, (keys, minutes) in SHAPES.items():
        step = BY_NAME[name][1]
        assert (set(step), step.get("timeout-minutes")) == (keys, minutes), name
    # A DATABASE_URL or another setting added here could replace the session's guards or reach another database.
    relabel = BY_NAME[RELABEL][1]["env"]
    assert BY_NAME[COUNT][1]["env"] == {**{key: relabel[key] for key in HERMETIC}, "PGOPTIONS": PGOPTIONS, **IDS}


@pytest.mark.parametrize("first, last, accepted", [
    ("1", "5000", True), ("101", "101", True), ("999995001", "999999999", True),
    ("1", "5001", False), ("10", "9", False), ("0", "5", False), ("", "5", False), ("1", "", False),
    ("01", "5", False), ("-1", "5", False), ("1", "1000000000", False), ("1 ", "5", False), ("1\n2", "5", False),
    ("1;id", "5", False), ("$(id)", "5", False),
    # Ten digits are refused by the digit cap alone, and 2^64 + 1 would wrap bash's arithmetic to a span of 1.
    ("1000000000", "1000000001", False), ("1", "18446744073709551617", False),
], ids=["whole-cap", "one", "nine-digits", "over-cap", "reversed", "zero", "no-first", "no-last", "zero-led",
        "negative", "ten-digit-last", "trailing-space", "newline", "command-separator", "substitution",
        "ten-digits-in-span", "wraps-to-a-span-of-one"])
def test_the_cohort_is_bounded_to_the_script_s_own_cap_before_the_sign_in(tmp_path, first, last, accepted):
    step = BY_NAME[VALIDATE][1]
    assert step["env"] == IDS
    assert f'[ "$SPAN" -le {_cap()} ]' in step["run"]
    # No command on its PATH: the step validates with bash alone.
    result = subprocess.run([BASH, "--noprofile", "--norc", "-eo", "pipefail", "-c", step["run"]],
                            env={"PATH": str(tmp_path), "FROM_ID": first, "TO_ID": last},
                            capture_output=True, text=True, timeout=10)
    assert (result.returncode == 0) is accepted, result.stdout + result.stderr


def test_the_count_runs_read_only_and_only_its_step_names_the_script_and_its_receipt():
    step = BY_NAME[COUNT][1]
    assert step["working-directory"] == "backend" and SCRIPT.is_file()
    options = step["env"]["PGOPTIONS"]
    assert (setting_ms(options, "lock_timeout"), setting_ms(options, "statement_timeout")) == (10_000, 120_000)
    # Postgres applies the last setting of a name.
    assert dict(pg_settings(options))["default_transaction_read_only"] == "on"
    every = [(path.name, step) for path in sorted((ROOT / ".github/workflows").glob("*.y*ml"))
             for job in yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader).get("jobs", {}).values()
             for step in job.get("steps", [])]
    assert [step.get("name") for _, step in every if "figure_check_impact" in json.dumps(step)] == [COUNT]
    # Outside a condition, as written and in any workflow (one that downloaded the artifact could print it).
    assert [(workflow, _label(step)) for workflow, step in every if "figure-impact" in json.dumps(
        {key: value for key, value in step.items() if key != "if"})] == [
        ("ops.yml", RESOLVE), ("ops.yml", VALIDATE), ("ops.yml", COUNT), ("ops.yml", RETAIN)]


@pytest.mark.parametrize("first, last", [("1", "5000"), ("7", "9")])
def test_a_count_reaches_the_receipt_alone_after_the_session_is_read_back(tmp_path, first, last):
    result, work, github, records = _run_count(tmp_path, first=first, last=last)
    assert (result.returncode, result.stdout, result.stderr) == (0, f"{EXPECTED}\n{SAVED}", "")
    assert _holding(work) == RECEIPT
    assert [path.name for path in github.iterdir() if path.read_text()] == []
    assert (work / "figure-impact/cohort.json").read_text() == f'{{"from_id": {first}, "to_id": {last}}}\n'
    # Each session's and the script's error output, in order: none truncates the one before it.
    assert (work / "figure-impact/stderr.txt").read_text() == "".join(
        f"{SENTINEL} {stage}\n" for stage in ("read-back", "range", "script"))
    assert BY_NAME[COUNT][1]["run"].startswith("set -euo pipefail\numask 077\n")
    # Two sessions, the read-back's and the range's, then one count, each under the step's own guards, on the database
    # the proxy step exported and with no other PG* setting.
    assert _calls(records, "psql") == [(["-X", "-t", "-A", "-c", READBACK], SEEN),
                                       (["-X", "-t", "-A", "-F", " ", "-c", POPULATION], SEEN)]
    assert _calls(records, "script") == [(["scripts/figure_check_impact.py", "--from-id", first, "--to-id", last],
                                          SEEN)]


@pytest.mark.parametrize("readback, psql_exit, range_exit, exit_code, printed, sessions, counted", [
    ("session read_only=off lock_timeout=10s statement_timeout=2min", 0, 0, 0, MISMATCH, 1, False),
    ("session read_only=on lock_timeout=0 statement_timeout=2min", 0, 0, 0, MISMATCH, 1, False),
    ("session read_only=on lock_timeout=10s statement_timeout=0", 0, 0, 0, MISMATCH, 1, False),
    ("", 0, 0, 0, MISMATCH, 1, False),
    (EXPECTED, 2, 0, 0, NO_SESSION, 1, False),  # a refused login: its error names the database user
    (EXPECTED, 0, 2, 0, NO_RANGE, 2, False),
    (EXPECTED, 0, 0, 1, FAILED.format(1), 2, True),  # a summary it could not read: a partial count never reads whole
    (EXPECTED, 0, 0, 2, FAILED.format(2), 2, True),  # its own exit code, not a fixed one (argparse exits 2)
], ids=["writable-session", "unbounded-lock", "unbounded-statement", "empty-read-back", "read-back-failed",
        "range-failed", "count-failed", "count-failed-2"])
def test_a_session_that_is_not_the_step_s_or_a_failed_read_fails_the_step_and_keeps_its_output(
        tmp_path, readback, psql_exit, range_exit, exit_code, printed, sessions, counted):
    result, work, github, records = _run_count(tmp_path, readback=readback, exit_code=exit_code, psql_exit=psql_exit,
                                               range_exit=range_exit)
    assert (result.returncode, result.stderr) == (exit_code if counted else 1, "")
    # The read-back's line, when the session started, and the step's own error line; never a count or an error.
    assert result.stdout == (printed if psql_exit else f"{readback}\n{printed}")
    assert len(_calls(records, "psql")) == sessions and (len(_calls(records, "script")) == 1) is counted
    assert _holding(work) == (RECEIPT if counted else ["figure-impact/population.txt", "figure-impact/stderr.txt"]
                              if sessions == 2 else ["figure-impact/stderr.txt"])
    assert [path.name for path in github.iterdir() if path.read_text()] == []


def test_the_receipt_is_kept_whatever_the_count_step_wrote():
    # One artifact per attempt: a re-run's upload never meets the first attempt's name.
    assert BY_NAME[RETAIN][1] == {
        "name": RETAIN, "if": f"always() && {CONDITION}", "uses": BY_NAME["Retain capacity readout"][1]["uses"],
        "with": {"name": "figure-impact-${{ github.run_id }}-${{ github.run_attempt }}", "path": "figure-impact/",
                 "retention-days": "14", "if-no-files-found": "warn"}}
