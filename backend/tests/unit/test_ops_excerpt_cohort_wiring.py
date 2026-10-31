"""How `.github/workflows/ops.yml` wires excerpt-cohort (E28): two reads, read-only, their output files counts only.

`ops/excerpts/provenance_count.py` reads Cloud Logging with the gcloud identity alone, so its step runs after the deploy
pre-flight and the sign-in and before the Cloud SQL proxy, within a step timeout its own time budget fits. Its window
ends at the top of the hour before the dispatch's and starts on 1 October, or 45 days before that end once 1 October is
further back, and the reader's own window check accepts it at each instant tested. `ops/excerpts/source_cohort.sql` runs
in a session that is read-only, in a step of its own: detection-sql's loop keeps its read scope and its error isolation.
The steps a dispatch runs are pinned (a shared one as `selected()` reads its condition, past a leading `always()`), with
the two reads' conditions as written, their keys, timeouts and env, and the retain step whole, and no shared step a
dispatch runs may carry `always()`; none of them may continue past an error, no step of any workflow but these two names
the readers, and outside a condition no step of any workflow but the resolve step, the reads and the upload names the
receipt's folder.

Each read step is run here as GitHub runs it, in a directory holding a copy of `ops/` (and, for the stored count, the
log read's counts in the receipt's folder, as on the runner), in which the step must leave
no file outside its receipt folder added, removed or changed, with a PATH that holds only `mkdir` and stand-ins for the
reader, `psql`, `date` and `gcloud` (bash scripts that import no function and read no BASH_ENV), with no stdin, a HOME
as the runner exports one, the stored count with the proxy step's exports, and the step's own env kept off the names the
run sets; any other command it names is recorded by bash's `command_not_found_handle`, which the step cannot redefine,
even one whose failure it hides or a child bash runs, and the run fails unless the step's own bash loaded it, or if the
step's text, read without its quotes and backslashes, names `/dev/tcp` or `/dev/udp`, a connection bash opens itself,
which no stand-in would see. Every reader call and `psql` session is recorded with each PG* variable it sees, the
DATABASE_URL in any letter case, HOME, and any PYTHON* or LD_* variable, which for the session must be the proxy step's
exports, the step's own PGOPTIONS and that HOME, and for the reader that HOME alone, one a read and none of the other
read's, whether it succeeds or fails. What a stand-in writes to its output file (the reader's `--output`, `psql`'s
stdout) lands in the receipt alone (`logged.json`; `stored.txt`), the reader's own stdout line is dropped, and its error
output lands nowhere this test reads: the step's stdout carries one line of its own, whose variable parts are a failed
read's exit code (three are run) and the closed class of its error text (unavailable, permission_denied, timeout or
other, each planted), its stderr nothing, and the run's summary, outputs and environment nothing, each code run both
as a first run and as a re-run with debug logs (RUNNER_DEBUG=1), which anyone who can re-run it may ask for. The log read's step
calls GNU date, as the runner has it, so a host without one (a Mac without coreutils) skips its runs, and a host whose
bash predates 4.0 and its handler (a Mac's own /bin/bash) skips every run. The last step keeps whatever the reads
wrote; a run stopped before either starts has nothing to keep, and the upload then warns.

The receipt is the run's artifact, which any signed-in GitHub user can download while it is kept, and the Actions log is
public too (this repository is public). That what the readers write to their output files is counts only is #1747's
contract and its tests'; a read's error text, which can name the database's user or host or carry whatever the reader
was reading, reaches neither: the step prints its closed class instead, as the gcloud steps do
(test_ops_stderr_withheld.py).
The rules every Ops step follows (a database command after the proxy, the lock and statement bounds, which
test_migration_lock_safety.py pins for this step, gcloud's stderr, and no bash trace, which would print the captured
text) stay with test_ops_workflow_wiring.py, test_migration_lock_safety.py and test_ops_stderr_withheld.py. Review-checked, not gated: a reader a step reaches
through a name or a path its text does not spell (`ops/exc*`, a variable), a command it runs by an absolute path (or one
a variable holds, `$BASH`), by `exec`, by `command -p` or on a PATH it sets itself, a connection of bash's own whose
`/dev/tcp` or `/dev/udp` its text does not hold whole, or that a file it sources opens, a file it sources from outside
`ops/`, the receipt's folder reached by a glob, a variable or a quoted spelling, a file it writes outside the step's
directory (a copy of the receipt, a module the reader imports), a renamed or edited copy of the SQL among
detection-sql's files, and a dump of the shell's variables (`set`, `declare -p`) on a condition no run here meets (an
exit code, an error text no run plants).
"""
import importlib.util
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timedelta, timezone

import pytest
import yaml

from tests.support.ops_workflow import BY_NAME, OPTIONS, PROXY, RESOLVE, ROOT, STEPS, pg_settings, selected
from tests.unit.test_ops_readback_allow_rules import _never_runs_for_a_read

OPERATION = "excerpt-cohort"
LOGGED = "Count the logged excerpt builds (E28)"
STORED = "Count the stored excerpts by builder (E28)"
RETAIN = "Retain the excerpt cohort receipt"
PREFLIGHT = "Refuse to run while a main push (deploy) is in flight"
SIGN_IN = "Set up gcloud"
# Every step a dispatch runs, in order: a step added for the operation is a change to what it reads or prints.
RUNS = ["actions/checkout@v7", RESOLVE, PREFLIGHT, "Authenticate to Google Cloud", SIGN_IN, LOGGED, PROXY, STORED,
        RETAIN]
CONDITION = "steps.request.outputs.operation == 'excerpt-cohort'"
# Each read step's keys and timeout.
SHAPES = {LOGGED: ({"name", "if", "timeout-minutes", "run"}, "30"),
          STORED: ({"name", "if", "timeout-minutes", "env", "run"}, "5")}
MARGIN_SECONDS = 300  # the two gcloud calls before the reader's budget starts, and the request in flight at its end
FIRST_DAY = datetime(2026, 10, 1, tzinfo=timezone.utc)  # before E28 (b)'s window opens (the last native eval report)
SENTINEL = "PRIVATE_COUNT_SENTINEL 4242"
SENTINELS = "\n".join([SENTINEL] * 50)  # what a stand-in writes where its counts go
COUNTS = (SENTINELS + "\n").encode()  # each receipt file, whole
# What the stored count meets in the receipt's folder: the log read's counts, bytes no stand-in of the stored count's
# writes, so a step that overwrites them fails.
SEED = (f"{SENTINEL} the log read's counts\n" * 3).encode()
# What each read step writes to the receipt (its counts alone), and the one line it prints when the read succeeds and
# when it fails.
RECEIPTS = {LOGGED: ["excerpt-cohort/logged.json"], STORED: ["excerpt-cohort/stored.txt"]}
# What the receipt's folder already holds when each read starts: the stored count runs after the log read's counts.
SEEDED = {LOGGED: [], STORED: ["excerpt-cohort/logged.json"]}
# The one line each read step prints on a failure, as its source spells it: its exit code and class, nothing else.
FAILURE_LINES = {
    LOGGED: 'echo "::error::The log read failed (exit $rc, $(failure "$ERR")); its error text is withheld."',
    STORED: 'echo "::error::The stored count failed (exit $rc, $(failure "$ERR")); its error text is withheld."',
}
# Each read step's classifier, byte for byte, so a new arm, a class or a drift between the two copies fails here.
CLASSIFIER = (
    "failure() {  # the closed class of a read's error text, which is printed nowhere\n"
    '  case "${1,,}" in\n'
    '    *"could not connect"*|*"connection refused"*|*"no route to host"*|*unreachable*|*"name or service not known"*'
    '|*"could not translate host name"*) echo unavailable ;;\n'
    '    *"permission denied"*|*permission_denied*|*forbidden*) echo permission_denied ;;\n'
    '    *"statement timeout"*|*"lock timeout"*|*"timeout expired"*|*"timed out"*|*timeouterror*) echo timeout ;;\n'
    "    *) echo other ;;\n"
    "  esac\n"
    "}\n"
)
# What each read's stand-ins record, beside the marker every bash that loaded the unknown-command handler leaves.
RECORDED = {LOGGED: ["bash-env", "python3"], STORED: ["bash-env", "psql"]}
PRINTED = {
    LOGGED: ("Logged excerpt counts saved to excerpt-cohort/logged.json (the run's artifact).\n",
             "::error::The log read failed (exit {}, {}); its error text is withheld.\n"),
    STORED: ("Stored excerpt counts saved to excerpt-cohort/stored.txt (the run's artifact).\n",
             "::error::The stored count failed (exit {}, {}); its error text is withheld.\n"),
}
# A failed reader's traceback as Python 3.12 prints it when gcloud cannot mint a token, abridged (its gcloud frame and
# caret lines left out): check_output's own frame spells `timeout=timeout`, which is no timeout.
TRACEBACK = (
    "Traceback (most recent call last):\n"
    '  File "/home/runner/work/EarningsNerd/EarningsNerd/ops/excerpts/provenance_count.py", line 544, in <module>\n'
    "    raise SystemExit(main())\n"
    '  File "/home/runner/work/EarningsNerd/EarningsNerd/ops/excerpts/provenance_count.py", line 530, in main\n'
    '    result = collect(Logging(gcloud("auth", "print-access-token")), gcloud("config", "get-value", "project"),\n'
    '  File "/usr/lib/python3.12/subprocess.py", line 466, in check_output\n'
    "    return run(*popenargs, stdout=PIPE, timeout=timeout, check=True,\n"
    '  File "/usr/lib/python3.12/subprocess.py", line 571, in run\n'
    "    raise CalledProcessError(retcode, process.args,\n"
    "subprocess.CalledProcessError: Command '['gcloud', 'auth', 'print-access-token']' returned non-zero exit status 1."
)
# Error texts the classifier may meet, each with the closed class its step prints in their place: one text for each
# pattern, two for the arms' order (the first arm that matches names the class), and psql 16's own wording for the
# failures a review measured. Some reach neither step today: gcloud's stderr goes to DEVNULL, the reader catches its
# own network errors, and libpq 14 and later no longer prints "could not connect"; they are planted to pin their
# patterns. Lower and upper case alike.
CLASSES = [
    ('psql: error: connection to server at "127.0.0.1", port 5432 failed: server closed the connection unexpectedly',
     "other"),
    ('psql: error: connection to server at "127.0.0.1", port 5432 failed: FATAL:  password authentication failed for '
     'user "ops"', "other"),
    ('psql: error: connection to server at "127.0.0.1", port 5432 failed: Connection refused', "unavailable"),
    ("psql: could not connect to server: No such file or directory", "unavailable"),
    ("OSError: [Errno 113] No route to host", "unavailable"),
    ("OSError: [Errno 101] Network is unreachable", "unavailable"),
    ('psql: error: could not translate host name "db.internal" to address: Temporary failure in name resolution',
     "unavailable"),
    ("socket.gaierror: [Errno -2] Name or service not known", "unavailable"),
    ("psql: could not connect to server: Connection timed out", "unavailable"),  # before timeout
    ("psql: could not connect to server: Permission denied", "unavailable"),  # before permission_denied
    ("ERROR:  permission denied for table filing_content_cache", "permission_denied"),
    ("PERMISSION_DENIED: Permission 'logging.logEntries.list' denied for principal ops@example.invalid",
     "permission_denied"),
    ("HTTP Error 403: Forbidden", "permission_denied"),
    ("ERROR:  canceling statement due to statement timeout", "timeout"),
    ("ERROR:  canceling statement due to lock timeout", "timeout"),
    ('psql: error: connection to server at "10.1.2.3", port 5432 failed: timeout expired', "timeout"),
    ("subprocess.TimeoutExpired: Command '['gcloud', 'logging', 'read']' timed out after 30 seconds", "timeout"),
    ("TimeoutError", "timeout"),
    (TRACEBACK, "other"),
    (f"{SENTINEL} stderr", "other"),
]
PGOPTIONS = "-c lock_timeout=10s -c statement_timeout=120s -c default_transaction_read_only=on"
# What the proxy step exports before the stored count: its session must see these and PGOPTIONS, and no other PG*
# name (a PGHOSTADDR or a PGSERVICE can reach another server).
PROXY_ENV = {"PGHOST": "127.0.0.1", "PGPORT": "5432", "PGDATABASE": "earningsnerd", "PGUSER": "ops",
             "PGPASSWORD": "placeholder", "DATABASE_URL": "postgresql://ops:placeholder@127.0.0.1:5432/earningsnerd"}
HOME = "/home/runner"  # the runner exports a HOME, so the sandbox does: an assignment to it reaches what runs


def _gnu_date():
    """GNU date, which the log read's step runs on GitHub's Ubuntu runner: `date` there, `gdate` on a Mac with GNU
    coreutils. A Mac's own date has no -d, so the steps that call it are skipped where no GNU date is found."""
    for name in ("date", "gdate"):
        path = shutil.which(name)
        if path and subprocess.run([path, "-u", "-d", "@0", "+%s"], capture_output=True, text=True).stdout == "0\n":
            return path
    return None


DATE = _gnu_date()
BASH = shutil.which("bash")
# The unknown-command record is bash's command_not_found_handle, which bash 4.0 added: under an older bash a step
# would run any command unrecorded, so its runs are skipped there.
BASH_MAJOR = int(subprocess.run([BASH, "-c", 'echo "${BASH_VERSINFO[0]}"'], capture_output=True, text=True).stdout)
GNU_DATE = pytest.mark.skipif(DATE is None, reason="the log read's step needs GNU date (GitHub's Ubuntu runner)")


def _reader():
    spec = importlib.util.spec_from_file_location("provenance_count", ROOT / "ops/excerpts/provenance_count.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
    """A stand-in's record of its call: its arguments, then each PG* variable it was given, DATABASE_URL in any
    letter case (the backend's settings read it so), HOME (python's user site follows it), and any PYTHON* or LD_*
    variable."""
    return ('{ printf "%s\\n" "$@"; echo ==; for name in $(compgen -e); do case $name in '
            'PG*|[Dd][Aa][Tt][Aa][Bb][Aa][Ss][Ee]_[Uu][Rr][Ll]|HOME|PYTHON*|LD_*) '
            'printf "%s=%s\\n" "$name" "${!name}" ;; esac; done; echo --; } >> "$RECORDS/' + tool + '"\n')


def _calls(records, tool) -> list[tuple[list[str], dict[str, str]]]:
    """Each call a stand-in recorded: its arguments, and each variable of those `_record` names that it saw."""
    path = records / tool
    calls = []
    for call in path.read_text().split("\n--\n") if path.exists() else []:
        if call:
            lines = call.split("\n")
            at = lines.index("==")
            calls.append((lines[:at], dict(line.split("=", 1) for line in lines[at + 1:])))
    return calls


def _files(root) -> dict[str, bytes]:
    """Every file under root, by its path from root, with its bytes."""
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def _run(tmp_path, name, now="2026-10-29T02:37:00Z", exit_code=0, stderr_text=f"{SENTINEL} stderr", debug=False):
    """A read step's own script, run as GitHub runs it (`bash -e`, with the step's env, and for the stored count the
    proxy step's exports) in a directory holding a copy of `ops/` and SEEDED's files, with a PATH that holds only `mkdir` and the
    stand-ins, and with `debug` as a re-run with debug logging on (RUNNER_DEBUG=1). `date` reads `now`; the reader and
    `psql` record each call with the variables `_record` names that it sees, write SENTINEL many times where their
    output goes and `stderr_text` once to their stderr, and exit `exit_code`; a python3 that is not the reader, and
    `gcloud`, fail; any other command is recorded as unknown."""
    if BASH_MAJOR < 4:
        pytest.skip("the step's runs need bash 4.0 or later (GitHub's Ubuntu runner has 5)")
    bin_dir, records, github, work = (tmp_path / part for part in ("bin", "records", "github", "work"))
    for directory in (bin_dir, records, github, work):
        directory.mkdir(parents=True)
    stand_ins = {
        "date": f'if [ "$3" = "1 hour ago" ]; then exec "{DATE}" -u -d "{now} 1 hour ago" "$4"; fi\n'
                f'exec "{DATE}" "$@"\n',
        "python3": 'if [ "$1" = ops/excerpts/provenance_count.py ]; then\n'
                   '  ' + _record("python3") +
                   '  while [ $# -gt 1 ]; do [ "$1" != --output ] || printf "%s\\n" "$SENTINELS" > "$2"; shift; done\n'
                   '  printf "%s\\n" "$SENTINEL"; printf "%s\\n" "$STDERR_TEXT" >&2\n  exit "$EXIT_CODE"\nfi\n'
                   '{ printf "%s\\n" "$@"; echo --; } >> "$RECORDS/python3-other"\nexit 97\n',
        "psql": _record("psql") +
                'printf "%s\\n" "$SENTINELS"; printf "%s\\n" "$STDERR_TEXT" >&2\nexit "$EXIT_CODE"\n',
        "gcloud": '{ printf "%s\\n" "$@"; echo --; } >> "$RECORDS/gcloud"\nexit 1\n',
    }
    for tool, body in stand_ins.items():
        # Privileged mode: a stand-in imports no function and reads no BASH_ENV, so the step cannot change its record.
        (bin_dir / tool).write_text("#!/bin/bash -p\n" + body)
        (bin_dir / tool).chmod(0o755)
    (bin_dir / "mkdir").symlink_to(shutil.which("mkdir"))
    # Bash reads BASH_ENV before a non-interactive script: any command not on this PATH is recorded, `|| true` or not.
    # Every bash that loads it marks its parent (a child bash the step runs does too), so the step's own mark is
    # this test's. It stays off the PATH.
    handler = tmp_path / "unknown.sh"
    handler.write_text('printf "%s\\n" "$PPID" >> "$RECORDS/bash-env"\n'
                       'command_not_found_handle() { printf "%s\\n" "$1" >> "$RECORDS/unknown"; '
                       'return 127; }\nreadonly -f command_not_found_handle\n'
                       'export -f command_not_found_handle\n')  # a child bash keeps it
    files = {key: github / key.lower() for key in ("GITHUB_STEP_SUMMARY", "GITHUB_OUTPUT", "GITHUB_ENV", "GITHUB_PATH")}
    for path in files.values():
        path.touch()
    shutil.copytree(ROOT / "ops", work / "ops", ignore=shutil.ignore_patterns("__pycache__"),
                    ignore_dangling_symlinks=True)  # a sourced file runs; an editor's lock link is no file
    before = _files(work)
    for path in SEEDED[name]:  # the receipt's folder as the read meets it, outside what `before` holds
        (work / path).parent.mkdir(parents=True, exist_ok=True)
        (work / path).write_bytes(SEED)
    step = BY_NAME[name][1]
    # Bash opens a /dev/tcp or /dev/udp path itself, as a connection no stand-in sees; it reads past quotes.
    assert not re.search(r"/dev/(?:tcp|udp)\b", re.sub(r"[\"'\\]", "", step["run"])), (
        "the step opens a connection of bash's own")
    sandbox = {**{key: str(path) for key, path in files.items()}, "PATH": str(bin_dir),
               "BASH_ENV": str(handler), "RECORDS": str(records), "SENTINEL": SENTINEL,
               "SENTINELS": SENTINELS, "EXIT_CODE": str(exit_code), "STDERR_TEXT": stderr_text,
               "HOME": HOME,
               **({"RUNNER_DEBUG": "1"} if debug else {}),  # GitHub sets it, to 1, when a run asks for debug logs
               **(PROXY_ENV if name == STORED else {}),  # the proxy step runs between the reads
               "SHLVL": "1"}  # past bash's sshd case, which skips BASH_ENV for a socket stdin or an SSH_CLIENT
    assert not set(step.get("env", {})) & set(sandbox), "the step's env sets a name this run replaces"
    env = {**step.get("env", {}), **sandbox}
    result = subprocess.run([BASH, "-e", "-c", step["run"]], cwd=work, env=env, stdin=subprocess.DEVNULL,
                            capture_output=True, text=True, timeout=10)
    assert [path.name for path in records.iterdir() if path.name in ("python3-other", "gcloud", "unknown")] == [], (
        "the step ran a command that is not one of its stand-ins")
    # A bash in POSIX mode, or one that otherwise skipped BASH_ENV, would run any command unrecorded.
    loaded = records / "bash-env"
    assert loaded.exists() and str(os.getpid()) in loaded.read_text().split(), (
        "the step's bash never loaded the unknown-command handler")
    # It leaves no file outside its receipt folder added, removed or changed: not what it runs, which would run as
    # left on the runner.
    assert {path: data for path, data in _files(work).items() if not path.startswith("excerpt-cohort/")} == before, (
        "the step wrote outside its receipt folder")
    return result, work, github, records


def test_a_dispatch_runs_the_pinned_steps_and_the_deploy_pre_flight_holds_the_reads():
    assert OPERATION in OPTIONS
    runs = _steps_run()
    assert [_label(step) for step in runs] == RUNS
    # None of them, the pre-flight among them, may let a dispatch go on past its failure, and no step before the
    # upload may run always(): selected() reads past it, and the proxy would then start after a refused pre-flight.
    assert [_label(step) for step in runs if "continue-on-error" in step] == []
    assert [_label(step) for step in runs if "always()" in step.get("if", "")] == [RETAIN]
    # As written, not as selected() reads it: a leading always() would run a read after the pre-flight refused it.
    for name in (LOGGED, STORED):
        assert BY_NAME[name][1]["if"] == CONDITION, name
    # The log read needs no database, so a failure on the database side never costs the evidence that expires.
    assert BY_NAME[SIGN_IN][0] < BY_NAME[LOGGED][0] < BY_NAME[PROXY][0] < BY_NAME[STORED][0]


def test_a_step_whose_condition_selected_cannot_read_still_counts_as_one_the_dispatch_runs():
    show = {"name": "Show the counts", "uses": "actions/github-script@v8",
            "if": "${{ always() && steps.request.outputs.operation == 'excerpt-cohort' && hashFiles('x') != '' }}"}
    at = BY_NAME[RETAIN][0]
    assert [_label(step) for step in _steps_run([*STEPS[:at], show, *STEPS[at:]])] == [*RUNS[:-1], "Show the counts",
                                                                                      RETAIN]


def test_each_read_is_bounded_and_its_failure_fails_the_run():
    for name, (keys, minutes) in SHAPES.items():
        step = BY_NAME[name][1]
        assert (set(step), step["timeout-minutes"]) == (keys, minutes), name
    # Each read's env whole: a name added here (POSIXLY_CORRECT, BASH_ENV, a PGHOST) could change what runs or where
    # it connects.
    assert "env" not in BY_NAME[LOGGED][1]
    assert BY_NAME[STORED][1]["env"] == {"PGOPTIONS": PGOPTIONS}
    # The reader stops at its own budget and still writes the receipt, before the step's timeout cuts it.
    assert _reader().BUDGET_SECONDS + MARGIN_SECONDS <= int(SHAPES[LOGGED][1]) * 60


@GNU_DATE
@pytest.mark.parametrize("now, start, end", [
    ("2026-10-29T02:37:00Z", "2026-10-01T00:00:00Z", "2026-10-29T01:00:00Z"),
    ("2026-11-15T01:59:59Z", "2026-10-01T00:00:00Z", "2026-11-15T00:00:00Z"),
    ("2026-11-15T02:00:00Z", "2026-10-01T01:00:00Z", "2026-11-15T01:00:00Z"),
    ("2026-12-25T10:15:00Z", "2026-11-10T09:00:00Z", "2026-12-25T09:00:00Z"),
], ids=["today", "last-whole-window", "first-rolling-window", "december"])
def test_the_log_read_s_window_is_one_the_reader_accepts(tmp_path, now, start, end):
    result, _, _, records = _run(tmp_path, LOGGED, now=now)
    assert result.returncode == 0, result.stderr
    # One reader call, before the proxy step's exports (it sees the runner's HOME alone): no other window is read.
    assert _calls(records, "python3") == [(["ops/excerpts/provenance_count.py", "--start", start, "--end", end,
                                            "--output", "excerpt-cohort/logged.json"], {"HOME": HOME})]
    first, last = (datetime.fromisoformat(value.replace("Z", "+00:00")) for value in (start, end))
    reader, dispatched = _reader(), datetime.fromisoformat(now.replace("Z", "+00:00"))

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return dispatched

    reader.datetime = Clock
    reader.days(start, end)  # the reader's own refusal at the dispatch's instant, not a copy of it
    assert first >= FIRST_DAY and (first == FIRST_DAY or last - first == timedelta(days=reader.MAX_DAYS))


def test_the_stored_count_runs_read_only_and_only_these_steps_name_the_readers_and_their_receipt():
    # Postgres applies the last setting of a name.
    assert dict(pg_settings(BY_NAME[STORED][1]["env"]["PGOPTIONS"]))["default_transaction_read_only"] == "on"
    every = [(path.name, step) for path in sorted((ROOT / ".github/workflows").glob("*.y*ml"))
             for job in yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader).get("jobs", {}).values()
             for step in job.get("steps", [])]
    assert [step.get("name") for _, step in every if "ops/excerpts" in json.dumps(step)] == [LOGGED, STORED]
    # Outside a condition, as written and in any workflow (one that downloaded the artifact could print it).
    assert [(workflow, _label(step)) for workflow, step in every if "excerpt-cohort" in json.dumps(
        {key: value for key, value in step.items() if key != "if"})] == [
        ("ops.yml", RESOLVE), ("ops.yml", LOGGED), ("ops.yml", STORED), ("ops.yml", RETAIN)]
    # detection-sql runs every file in ops/detection: a copy there would print the counts in its public log.
    assert not (ROOT / "ops/detection/source_cohort.sql").exists()


@pytest.mark.parametrize("name", [pytest.param(LOGGED, marks=GNU_DATE), STORED], ids=["logged", "stored"])
# Three failing codes, so the line the step prints and its exit are the read's own code, not a fixed one; 1 among
# them, the code a reader's own failure exits with.
@pytest.mark.parametrize("exit_code", [0, 1, 2, 3], ids=["read", "failed-1", "failed-2", "failed-3"])
# Each code twice: what a step prints may not hang on whether the run asked for debug logs, which any re-run may.
@pytest.mark.parametrize("debug", [False, True], ids=["first-run", "debug-re-run"])
def test_a_read_s_counts_reach_the_receipt_alone_its_error_text_nowhere_and_a_failure_fails_its_step(tmp_path, name,
                                                                                                      exit_code, debug):
    result, work, github, records = _run(tmp_path, name, exit_code=exit_code, debug=debug)
    printed = PRINTED[name][1].format(exit_code, "other") if exit_code else PRINTED[name][0]
    assert (result.returncode, result.stdout, result.stderr) == (exit_code, printed, "")
    holding = sorted(path.relative_to(work).as_posix() for path in work.rglob("*")
                     if path.is_file() and SENTINEL.encode() in path.read_bytes())  # ops/ may hold a binary file
    assert holding == sorted(RECEIPTS[name] + SEEDED[name])
    # The receipt's folder holds the counts as the reads wrote them and nothing else, and the error text reaches no
    # file the step leaves, read or failed.
    assert _files(work / "excerpt-cohort") == _folder(name)
    assert [path for path in work.rglob("*") if path.is_file() and f"{SENTINEL} stderr".encode() in path.read_bytes()] == []
    assert sorted(path.name for path in records.iterdir()) == RECORDED[name]  # its own tools, no other read's
    assert [path.name for path in github.iterdir() if path.read_text()] == []
    assert BY_NAME[name][1]["run"].startswith("set -euo pipefail\numask 077\n")
    if name == LOGGED:
        # One call, no retry or other window, read or failed, and it sees the runner's HOME alone.
        assert [seen for _, seen in _calls(records, "python3")] == [{"HOME": HOME}]
    if name == STORED:
        # One session, read-only by the step's own PGOPTIONS, on the database the proxy step exported and no other.
        assert _calls(records, "psql") == [(["-X", "-v", "ON_ERROR_STOP=1", "-P", "pager=off", "-f",
                                             "ops/excerpts/source_cohort.sql"],
                                            {**PROXY_ENV, "PGOPTIONS": PGOPTIONS, "HOME": HOME})]


@pytest.mark.parametrize("name", [pytest.param(LOGGED, marks=GNU_DATE), STORED], ids=["logged", "stored"])
@pytest.mark.parametrize("text, klass", CLASSES, ids=[f"{number}-{klass}" for number, (_, klass) in enumerate(CLASSES)])
def test_a_failed_read_prints_the_closed_class_of_its_error_text_never_the_text(tmp_path, name, text, klass):
    result, work, github, _ = _run(tmp_path, name, exit_code=2, stderr_text=text)
    assert (result.returncode, result.stdout, result.stderr) == (2, PRINTED[name][1].format(2, klass), "")
    # The receipt's folder holds the counts alone, and _run holds every other file to what it was.
    assert _files(work / "excerpt-cohort") == _folder(name)
    assert [path.name for path in github.iterdir() if path.read_text()] == []


def _folder(name) -> dict[str, bytes]:
    """The receipt's folder after a read: its own counts, and the log read's that the stored count met, each whole."""
    return {**{path.split("/", 1)[1]: SEED for path in SEEDED[name]},
            **{path.split("/", 1)[1]: COUNTS for path in RECEIPTS[name]}}


def test_each_read_classifies_its_error_text_with_the_one_classifier():
    # Planted texts pin each pattern; this pins the rest: no arm that prints the text, no fifth class, no drift, no
    # second classifier however spelled, and the one line that prints the class.
    # Each pin reads the script's text, its comments included: a respelling is a change to the pin too.
    for name in (LOGGED, STORED):
        run = BY_NAME[name][1]["run"]
        assert run.count(CLASSIFIER) == 1 and len(re.findall(r"\bfailure\b", run)) == 2, (
            f"{name}: the one classifier, defined once and called once, in its failure line")
        assert run.count(FAILURE_LINES[name]) == 1, f"{name}: the failure line, as FAILURE_LINES spells it"
        assert 'if ERR="$(' in run and len(re.findall(r"\bERR\b", run)) == 2, (
            f"{name}: the error text captured into ERR and named there and where it is classified, nowhere else")


def test_the_receipt_is_kept_whatever_the_reads_wrote():
    # One artifact per attempt: a re-run's upload never meets the first attempt's name.
    assert BY_NAME[RETAIN][1] == {
        "name": RETAIN, "if": f"always() && {CONDITION}", "uses": BY_NAME["Retain capacity readout"][1]["uses"],
        "with": {"name": "excerpt-cohort-${{ github.run_id }}-${{ github.run_attempt }}", "path": "excerpt-cohort/",
                 "retention-days": "14", "if-no-files-found": "warn"}}
