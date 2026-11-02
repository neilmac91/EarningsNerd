"""Gate for the complimentary-access operations in `.github/workflows/ops.yml` (PB-02's grant and revoke, wired by
PB-05; CLAUDE.md rule 12).

The founder grants or revokes complimentary Pro for invited private-beta testers with
`backend/scripts/complimentary_access.py` (docs/ops/complimentary-access.md). Production's database is reachable only
from Cloud Run and the Ops proxy, so three Ops operations run it: `complimentary-access-dry-run`,
`complimentary-access-apply` and `complimentary-access-readout`. This gate holds:

- the steps each dispatch runs, in order: all three refuse while a main push is in flight, only the apply waits for
  the founder's approval and checks its confirmation, nothing goes on past a failure, and nothing keeps an artifact;
- the resolve step accepts each operation, and the confirmation step accepts only 64 lowercase hex characters (the
  `manifest_sha256` the dry run printed) and refuses anything else, an injected line or command included;
- the script step as written, run with stand-ins for `psql` and `python` that record their arguments, stdin and
  environment: every operation but the apply runs read-only, the readback runs first and a session that is not the
  step's stops it before the script, the script's own failure fails it, the script gets exactly its subcommand and
  flags (read by the script's own parser), and the manifest reaches it on stdin alone, never in an environment
  variable psql or the script inherits; the step's own output, which GitHub writes to the public log, holds no part of
  the manifest in any run, a refusal included; with the secret empty or unset, the dry run and the apply refuse before
  any database call while the readout still runs;
- the manifest is the founder's private file: its repository secret is named once in every workflow, in that step's
  env, in the text and in the parsed workflow alike (so no YAML alias hands it to a second step), no workflow reads the
  whole secrets context (each expression closed where GitHub closes it, outside a quoted literal), no dispatch input is
  named for a manifest, the step's script moves the manifest only through
  a pipe and redirects nothing, so it writes it to no file, and no file this repository tracks is a manifest.

Out of reach, said so nothing is overclaimed: how GitHub masks the secret in the log (the runner registers each line
of a multi-line secret as a mask; docs/DEPLOYMENT.md says to store the manifest on one line); what the script prints,
which test_complimentary_access_script.py holds free of ids, addresses and the reason; and the step shell's own
initial environment: `unset` keeps the value out of every child's environment, but the shell's /proc/<pid>/environ
still holds it for the step's life, readable by a process of the same user on that runner, as with any env-delivered
secret.
"""
import functools
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import timedelta

import pytest
import yaml

from tests.support.ops_workflow import BY_NAME, COMPLIMENTARY, DEPS, INPUTS, OPS, OPTIONS, PROXY, RESOLVE, ROOT, STEPS, selected
from tests.unit.test_ops_readback_allow_rules import _never_runs_for_a_read
from tests.unit.test_ops_stderr_withheld import _commands, _executable_lines
from tests.unit.test_workflow_dispatch_inputs import _run_resolve

DRY, APPLY, READOUT = "complimentary-access-dry-run", "complimentary-access-apply", "complimentary-access-readout"
OPERATIONS = (DRY, APPLY, READOUT)
CONFIRM = "Validate the complimentary access confirmation"
APPROVAL = "Refuse an apply that no one approved in this run"
PREFLIGHT = "Refuse to run while a main push (deploy) is in flight"
SIGN_IN = ["Authenticate to Google Cloud", "Set up gcloud"]
RUNS = {  # every step each dispatch runs, in order
    DRY: ["actions/checkout@v7", RESOLVE, PREFLIGHT, *SIGN_IN, PROXY, DEPS, COMPLIMENTARY],
    APPLY: ["actions/checkout@v7", RESOLVE, APPROVAL, PREFLIGHT, CONFIRM, *SIGN_IN, PROXY, DEPS, COMPLIMENTARY],
    READOUT: ["actions/checkout@v7", RESOLVE, PREFLIGHT, *SIGN_IN, PROXY, DEPS, COMPLIMENTARY],
}
SECRET = "COMPLIMENTARY_ACCESS_MANIFEST"
SCRIPT = "scripts/complimentary_access.py"
RUN_ID = "39360634523"  # github.run_id: the apply records ops-run:<it> as its runner
DIGEST = hashlib.sha256(b"a synthetic complimentary access manifest").hexdigest()
GUARDS = "-c lock_timeout=10s -c statement_timeout=120s"
STEP_ENV = {  # the script step's env, whole: a name added here changes what the run reads or writes
    "PGOPTIONS": GUARDS, "SEC_RATE_LIMIT_PER_SECOND": "1", "EDGAR_RATE_LIMIT_PER_SEC": "1", "SKIP_REDIS_INIT": "true",
    "SECRET_KEY": "ops-workflow-secret-key-not-used-0123456789", "STRIPE_SECRET_KEY": "sk_test_ops",
    "STRIPE_WEBHOOK_SECRET": "whsec_ops", "PWNED_PASSWORD_CHECK_ENABLED": "false",
    "OP": "${{ steps.request.outputs.operation }}", "CONFIRM_DIGEST": "${{ inputs.confirm_digest }}",
    "MANIFEST": "${{ secrets.COMPLIMENTARY_ACCESS_MANIFEST }}",
}
WORKFLOW_FILES = sorted(path for path in (ROOT / ".github/workflows").iterdir() if path.suffix in (".yml", ".yaml"))
# Records each call of the stand-in it runs as (`psql` or `python`): its arguments, its stdin (`python` only; `psql`
# reads none) and its whole environment. `psql` answers only the readback query, which reads the three settings in
# this order; each exits with its own *_EXIT.
RECORDER = r'''
import json, os, re, sys
tool, argv = sys.argv[1], sys.argv[2:]
stdin = sys.stdin.buffer.read().decode("utf-8") if tool == "python" else ""
with open(os.environ["CALLS"], "a", encoding="utf-8") as calls:
    calls.write(json.dumps({"tool": tool, "argv": argv, "stdin": stdin, "env": dict(os.environ)}) + "\n")
if tool == "psql":
    asked = re.findall(r"current_setting\('(\w+)'\)", " ".join(argv))
    print(os.environ["READBACK"] if asked == ["default_transaction_read_only", "lock_timeout", "statement_timeout"]
          else "unexpected query")
sys.exit(int(os.environ[tool.upper() + "_EXIT"]))
'''


def _manifest_text() -> str:
    """A synthetic grant manifest the script accepts, written as a founder would (indented, a trailing newline), with
    a reason that holds what a careless transport would expand or mangle: a format directive, a quote, a backslash, a
    command substitution and backticks, and an apostrophe, which bash re-quotes when it prints a variable (`set`), so
    a printed copy of the manifest would not be the text the runner masks."""
    from app.services.complimentary_access_manifest import email_fingerprint
    from app.utils.datetimes import utcnow

    return json.dumps({
        "action": "grant",
        "cohort": "private-beta-2026-11",
        "reason": "Private beta: the founder's 100% \"$(id)\" `id` \\ %s",
        "review_on": (utcnow().date() + timedelta(days=30)).isoformat(),
        "operator_account_id": 1,
        "accounts": [{"account_id": 1000 + n, "email_sha256": email_fingerprint(f"tester-{n}@example.invalid")}
                     for n in (1, 2)],
    }, indent=2) + "\n"


def _steps_run(operation: str) -> list[dict]:
    """The steps a dispatch of the operation runs, in order: selected() where it reads the if:, and otherwise every
    step whose if: is not decisively false for it (test_ops_excerpt_cohort_wiring.py reads its operation the same way)."""
    runs, unrun = [], set()
    for step in STEPS:
        try:
            runs_here = operation in selected(step)
        except AssertionError:
            runs_here = not _never_runs_for_a_read(step["if"], unrun, r"steps\.request\.outputs\.operation", (operation,))
        if runs_here:
            runs.append(step)
        elif step.get("id"):
            unrun.add(step["id"])
    return runs


@pytest.mark.parametrize("operation", OPERATIONS)
def test_each_operation_runs_exactly_its_steps(operation):
    """The apply alone waits for the founder (the approval job, then the run's own approval check) and checks its
    confirmation; all three hold for a main push in flight and sign in before the proxy and the dependency install;
    the script step is the last, and no step keeps an artifact. No step a dispatch runs goes on past a failure or runs
    always(), so a refusal anywhere stops the script."""
    assert operation in OPTIONS
    runs = _steps_run(operation)
    assert [step.get("name") or step.get("uses") for step in runs] == RUNS[operation]
    assert [step.get("name") for step in runs if "continue-on-error" in step or "always()" in step.get("if", "")] == []
    jobs = OPS["jobs"]
    assert (operation in selected(jobs["approve-apply"])) is (operation == APPLY)
    for job in ("ops", "refuse-rerun"):  # the lists test_ops_workflow_wiring.py holds equal to the approval job's
        applies = re.search(r"contains\('([^']*)', inputs\.operation\)", jobs[job]["if"]).group(1).split()
        assert (operation in applies) is (operation == APPLY), job


@pytest.mark.parametrize("operation", OPERATIONS)
def test_the_resolve_step_accepts_each_operation(tmp_path, operation):
    code, output = _run_resolve(tmp_path, OP=operation)
    assert code == 0
    assert output.splitlines() == [f"operation={operation}", "tickers=", "revision="]


def test_the_confirmation_is_the_applys_own_input_checked_before_the_sign_in():
    """The digest is a dispatch input of its own, not one the resolve step writes: only the confirmation step and the
    script step read it, each through its env, and the check runs before any cloud sign-in."""
    at, step = BY_NAME[CONFIRM]
    assert set(step) == {"name", "if", "env", "run"}, "no continue-on-error: a refused digest fails the run"
    assert step["if"] == f"steps.request.outputs.operation == '{APPLY}'"
    assert step["env"] == {"CONFIRM_DIGEST": "${{ inputs.confirm_digest }}"}
    request_at = next(index for index, each in enumerate(STEPS) if each.get("id") == "request")
    assert request_at < at < BY_NAME[SIGN_IN[0]][0] < BY_NAME[PROXY][0]
    assert INPUTS["confirm_digest"] == {
        "description": "complimentary-access-apply only: the manifest_sha256 its dry run printed",
        "required": "false", "default": ""}
    assert [each.get("name") for each in STEPS if "inputs.confirm_digest" in json.dumps(each)] == [CONFIRM, COMPLIMENTARY]


def _run_confirmation(tmp_path, digest: str) -> subprocess.CompletedProcess:
    step = BY_NAME[CONFIRM][1]
    return subprocess.run(  # fixed argv; the script under test is repository content
        ["bash", "-e", "-c", step["run"]], cwd=tmp_path, env={"PATH": os.environ["PATH"], "CONFIRM_DIGEST": digest},
        stdin=subprocess.DEVNULL, capture_output=True, text=True, check=False)


def test_the_confirmation_step_accepts_a_sha256_in_lowercase_hex(tmp_path):
    result = _run_confirmation(tmp_path, DIGEST)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("digest", [
    pytest.param("", id="empty"),
    pytest.param(DIGEST.upper(), id="uppercase"),
    pytest.param(DIGEST[:63], id="63-characters"),
    pytest.param(DIGEST + "0", id="65-characters"),
    pytest.param("g" * 64, id="not-hex"),
    pytest.param(" " + DIGEST[1:], id="a-space"),
    pytest.param(DIGEST + "\n", id="a-trailing-line-break"),
    pytest.param(DIGEST + "\noperation=complimentary-access-apply", id="an-injected-line"),
    pytest.param("$(id)", id="a-command-substitution"),
    pytest.param(DIGEST[:59] + "$(id)", id="a-command-substitution-at-length"),
])
def test_the_confirmation_step_refuses_anything_else(tmp_path, digest):
    assert DIGEST != DIGEST.upper(), "the planted digest must hold a letter for the uppercase case to mean anything"
    result = _run_confirmation(tmp_path, digest)
    assert result.returncode == 1
    assert ("::error::complimentary-access-apply needs confirm_digest: the manifest_sha256 its dry run printed"
            in result.stdout), result.stdout
    assert "uid=" not in result.stdout + result.stderr, "the input was run"


def test_the_script_step_runs_for_its_three_operations_as_written():
    """Its if: is pinned as written, with no status function, so GitHub's success() stops it after a refused approval
    check or pre-flight; its keys and env are pinned whole. Its run first sets errexit and checks the script is
    committed, then moves the manifest out of the environment before any command could inherit it, and nothing in it
    can export a variable."""
    step = BY_NAME[COMPLIMENTARY][1]
    assert selected(step) == set(OPERATIONS)
    assert step["if"] == (
        "contains('complimentary-access-dry-run complimentary-access-apply complimentary-access-readout', "
        "steps.request.outputs.operation)"), "no status function: a refused approval check or pre-flight stops it"
    assert set(step) == {"name", "if", "working-directory", "timeout-minutes", "env", "run"}, (
        "no continue-on-error, and no id by which a later step could keep an artifact of it")
    assert (step["working-directory"], step["timeout-minutes"], step["env"]) == ("backend", "15", STEP_ENV)
    lines = [line.strip() for line in _executable_lines(step["run"]) if line.strip()]
    assert lines[:4] == [
        "set -euo pipefail",
        '[ -f scripts/complimentary_access.py ] || { echo "::error::complimentary access script not committed yet"; exit 1; }',
        'MANIFEST_TEXT="${MANIFEST:-}"',
        "unset MANIFEST",
    ]
    assert not [line for line in lines if re.search(r"\bexport\b|\bdeclare\b|\btypeset\b|\bset\s+-\w*a|allexport", line)]


def test_the_script_step_moves_the_manifest_through_a_pipe_and_writes_it_nowhere():
    """The commands that name the manifest are its copy, its unset, the emptiness check and the printf that feeds the
    script's stdin on the same line; the run holds no redirect, here-string, heredoc or process substitution and no
    tee, so it writes no file at all."""
    lines = [line.strip() for line in _executable_lines(BY_NAME[COMPLIMENTARY][1]["run"]) if line.strip()]
    commands = [command for line in lines for command in _commands(line)]
    assert [command for command in commands if "MANIFEST" in command] == [
        'MANIFEST_TEXT="${MANIFEST:-}"', "unset MANIFEST", '[ -z "$MANIFEST_TEXT" ]', "printf '%s' \"$MANIFEST_TEXT\""]
    [feed] = [line for line in lines if "$MANIFEST_TEXT\" |" in line]
    assert re.search(r"""printf '%s' "\$MANIFEST_TEXT" \| python scripts/complimentary_access\.py "\$\{ARGS\[@\]\}";""",
                     feed), feed
    assert not [line for line in lines if re.search(r"[<>]|\btee\b", line)]


def _readback(writes: bool) -> str:
    """The line Postgres prints for the step's own guards, read-write for the apply alone."""
    return f"session read_only={'off' if writes else 'on'} lock_timeout=10s statement_timeout=2min"


def _run_script_step(tmp_path, op, *, manifest, digest=DIGEST, readback=None, psql_exit=0, python_exit=0):
    """The script step's own run, as GitHub runs it (`bash -e`, stdin closed) with the step's env, in which each
    expression GitHub resolves is set here (`manifest=None` leaves the secret's variable unset), and with stand-ins
    for `psql` and `python` that record each call (RECORDER). Returns the result and the calls, in order."""
    step = BY_NAME[COMPLIMENTARY][1]
    bin_dir, scripts = tmp_path / "bin", tmp_path / "scripts"
    bin_dir.mkdir()
    scripts.mkdir()
    (tmp_path / SCRIPT).write_text("")
    recorder = tmp_path / "recorder.py"
    recorder.write_text(RECORDER)
    for tool in ("psql", "python"):
        (bin_dir / tool).write_text(f'#!/bin/sh\nexec "{sys.executable}" -I "{recorder}" {tool} "$@"\n')
        (bin_dir / tool).chmod(0o755)
    resolved = {"OP": op, "CONFIRM_DIGEST": digest, "MANIFEST": manifest}
    assert {name for name, value in step["env"].items() if "${{" in value} == set(resolved), (
        "every value GitHub resolves in the step's env is one this harness sets")
    env = {**step["env"], **resolved}
    if manifest is None:
        del env["MANIFEST"]
    env.update(PATH=f"{bin_dir}{os.pathsep}{os.environ['PATH']}", GITHUB_RUN_ID=RUN_ID, CALLS=str(tmp_path / "calls"),
               READBACK=_readback(op == APPLY) if readback is None else readback,
               PSQL_EXIT=str(psql_exit), PYTHON_EXIT=str(python_exit))
    result = subprocess.run(  # fixed argv; the script under test is repository content
        ["bash", "-e", "-c", step["run"]], cwd=tmp_path, env=env, stdin=subprocess.DEVNULL,
        capture_output=True, text=True, check=False)
    if manifest:
        _assert_the_log_holds_no_manifest(result.stdout + result.stderr, manifest)
    calls = tmp_path / "calls"
    return result, [json.loads(line) for line in calls.read_text().splitlines()] if calls.exists() else []


def _assert_the_log_holds_no_manifest(log: str, manifest: str) -> None:
    """The step's own output, which GitHub writes to the public log, holds no part of the manifest: not its reason,
    an account id or a fingerprint. The runner masks only the secret's exact text, and a printed shell variable
    (`set`) re-quotes the reason's apostrophe, so no mask would hide that copy. The stand-ins print only the readback,
    so every word checked here would come from the step itself."""
    parsed = json.loads(manifest)
    planted = [parsed["reason"].split("'")[0], "account_id", "email_sha256",
               *(entry["email_sha256"] for entry in parsed["accounts"])]
    assert [text for text in planted if text in log] == [], "the step printed part of the manifest"


@pytest.mark.parametrize("op, argv, parsed, fed", [
    (DRY, ["dry-run", "--manifest", "/dev/stdin"], {"command": "dry-run", "manifest": "/dev/stdin"}, True),
    (APPLY, ["apply", "--manifest", "/dev/stdin", "--confirm-digest", DIGEST, "--runner", f"ops-run:{RUN_ID}"],
     {"command": "apply", "manifest": "/dev/stdin", "confirm_digest": DIGEST, "runner": f"ops-run:{RUN_ID}"}, True),
    (READOUT, ["readout"], {"command": "readout"}, False),
    # Any other operation, were the step's if: widened, runs the readout, read-only: it can never write.
    ("relabel-fy-apply", ["readout"], {"command": "readout"}, False),
])
def test_the_script_gets_its_subcommand_and_the_manifest_on_stdin_alone(tmp_path, op, argv, parsed, fed):
    """Only the apply runs read-write. The readback runs first, then the script once, with exactly its subcommand and
    flags, as the script's own parser reads them; the apply records this run as its runner, in the form the service
    accepts. The manifest reaches the script on stdin, byte for byte, and only for the commands that read one; neither
    psql nor the script finds it, or the variable it moved into, in its environment."""
    from app.services.complimentary_access_manifest import check_runner_label
    from scripts.complimentary_access import build_parser

    manifest = _manifest_text()
    result, calls = _run_script_step(tmp_path, op, manifest=manifest)
    assert result.returncode == 0, result.stdout + result.stderr
    assert [call["tool"] for call in calls] == ["psql", "python"], "the readback runs first, then the script once"
    options = GUARDS + ("" if op == APPLY else " -c default_transaction_read_only=on")
    assert [call["env"]["PGOPTIONS"] for call in calls] == [options] * 2
    script = calls[1]
    assert script["argv"] == [SCRIPT, *argv]
    assert vars(build_parser().parse_args(script["argv"][1:])) == parsed
    check_runner_label(parsed.get("runner"))  # raises on a label the service would refuse
    assert script["stdin"] == (manifest if fed else "")
    fingerprint = json.loads(manifest)["accounts"][0]["email_sha256"]
    for call in calls:
        assert not {"MANIFEST", "MANIFEST_TEXT"} & set(call["env"]), f"{call['tool']} inherits the manifest's variable"
        assert not [name for name, value in call["env"].items() if fingerprint in value], call["tool"]


@pytest.mark.parametrize("manifest", [None, ""], ids=["unset", "empty"])
def test_the_readout_runs_without_a_manifest(tmp_path, manifest):
    result, calls = _run_script_step(tmp_path, READOUT, manifest=manifest)
    assert result.returncode == 0, result.stdout + result.stderr
    assert [call["tool"] for call in calls] == ["psql", "python"]
    assert (calls[1]["argv"], calls[1]["stdin"]) == ([SCRIPT, "readout"], "")


@pytest.mark.parametrize("op", [DRY, APPLY])
@pytest.mark.parametrize("manifest", [None, ""], ids=["unset", "empty"])
def test_a_dry_run_or_an_apply_without_a_manifest_refuses_before_any_database_call(tmp_path, op, manifest):
    result, calls = _run_script_step(tmp_path, op, manifest=manifest)
    assert result.returncode == 1
    assert f"::error::{op} reads its manifest from the repository secret, which is empty or unset" in result.stdout
    assert calls == [], "no psql and no script before the refusal"


@pytest.mark.parametrize("op, readback", [
    (DRY, _readback(writes=True)),  # a dry run whose transactions could write
    (READOUT, _readback(writes=True)),
    (APPLY, _readback(writes=False)),  # an apply whose session is not the step's
    (APPLY, "session read_only=off lock_timeout=0 statement_timeout=2min"),  # no lock bound: a later -c 0 won
    (DRY, "session read_only=on lock_timeout=10s statement_timeout=0"),  # no statement bound
    (READOUT, ""),  # psql printed nothing
])
def test_a_session_that_is_not_the_steps_stops_it_before_the_script(tmp_path, op, readback):
    """The readback is a check, not only a log line: a session whose settings are not the step's stops the run before
    the script opens one."""
    result, calls = _run_script_step(tmp_path, op, manifest=_manifest_text(), readback=readback)
    assert result.returncode == 1
    assert "the session's settings are not this step's" in result.stdout
    assert [call["tool"] for call in calls] == ["psql"]


@pytest.mark.parametrize("op", OPERATIONS)
@pytest.mark.parametrize("failure, code, tools", [
    ({"psql_exit": 2}, 2, ["psql"]),  # the session's settings could not be read: no script
    ({"python_exit": 1}, 1, ["psql", "python"]),  # the script refused: a manifest fault, a digest, the cap
    ({"python_exit": 2}, 2, ["psql", "python"]),  # an account's unit failed
])
def test_a_failed_readback_or_script_fails_the_step(tmp_path, op, failure, code, tools):
    result, calls = _run_script_step(tmp_path, op, manifest=_manifest_text(), **failure)
    assert result.returncode == code
    assert [call["tool"] for call in calls] == tools


def test_the_script_reads_a_manifest_piped_to_dev_stdin_as_it_reads_the_file(tmp_path):
    """The step hands the manifest over as `--manifest /dev/stdin` on a pipe. The script's own reader takes it whole
    there, with the digest the file gives: its offline `check`, which needs no settings and no database."""
    from app.services.complimentary_access_manifest import load_manifest

    manifest = _manifest_text()
    _, digest = load_manifest(manifest.encode("utf-8"))
    path = tmp_path / "manifest.json"
    path.write_text(manifest, encoding="utf-8")
    command, env = [sys.executable, "-I", SCRIPT, "check", "--manifest"], {"PATH": os.environ["PATH"]}
    piped = subprocess.run(  # fixed argv; the script under test is repository content
        [*command, "/dev/stdin"], cwd=ROOT / "backend", env=env, input=manifest, capture_output=True, text=True,
        check=False)
    from_file = subprocess.run(  # fixed argv; the script under test is repository content
        [*command, str(path)], cwd=ROOT / "backend", env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True,
        check=False)
    assert (piped.returncode, from_file.returncode) == (0, 0), piped.stdout + piped.stderr + from_file.stderr
    assert json.loads(piped.stdout) == json.loads(from_file.stdout)
    assert json.loads(piped.stdout)["manifest_sha256"] == digest


def test_the_manifest_secret_is_named_once_in_every_workflow_in_the_script_steps_env():
    """GitHub reads a secret's name in any case, so no workflow names it but this step's env, once. A read of the whole
    secrets context would reach it without its name (`toJSON(secrets)`, an index, a reusable workflow's `secrets:
    inherit`), so no workflow reads the context but by a secret's name."""
    named = {path.name: len(re.findall(SECRET, path.read_text(encoding="utf-8"), re.IGNORECASE)) for path in WORKFLOW_FILES}
    assert {name: count for name, count in named.items() if count} == {"ops.yml": 1}
    # A YAML alias repeats a node without repeating its text, so the parsed workflows must name it once too.
    parsed = {path.name: sum(bool(re.search(SECRET, text, re.IGNORECASE)) for _, text in _values(_parsed(path)))
              for path in WORKFLOW_FILES}
    assert {name: count for name, count in parsed.items() if count} == {"ops.yml": 1}
    assert BY_NAME[COMPLIMENTARY][1]["env"]["MANIFEST"] == "${{ secrets." + SECRET + " }}"
    # GitHub reads context names in any case too (`SECRETS[...]`, `toJSON(Secrets)`). An if: is an expression whole.
    whole = [(path.name, expression.strip()) for path in WORKFLOW_FILES for key, text in _values(_parsed(path))
             for expression in ([text] if key == "if" else _expressions(text))
             if re.search(r"\bsecrets\b(?!\.[A-Za-z_])", expression, re.IGNORECASE)]
    assert whole == [], "an expression reads the whole secrets context"
    # Read from the parsed jobs, so a quoted `'inherit'` counts as the bare word does.
    inherits = [f"{path.name}: {name}" for path in WORKFLOW_FILES
                for name, job in (_parsed(path).get("jobs") or {}).items()
                if isinstance(job, dict) and str(job.get("secrets", "")).strip().lower() == "inherit"]
    assert inherits == [], "a reusable workflow call hands on every secret"


@functools.cache
def _parsed(path) -> dict:
    """A workflow as GitHub reads it (BaseLoader expands every YAML alias), parsed once per session."""
    return yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader) or {}


def _values(node, key=None):
    """Every key and scalar of a parsed workflow, each scalar with the key it sits under (a key with none), a node an
    alias repeats once per place it appears."""
    if isinstance(node, dict):
        for name, value in node.items():
            yield None, str(name)
            yield from _values(value, name)
    elif isinstance(node, list):
        for value in node:
            yield from _values(value, key)
    elif node is not None:
        yield key, str(node)


def _expressions(text: str) -> list[str]:
    """Each `${{ }}` expression in a workflow value, closed where GitHub's template reader closes one: at the first
    `}}` outside a single-quoted literal (a literal's `''` escape flips the state twice). The first `}}` alone would
    end `format('{{{0}}}', toJSON(secrets))` inside its literal, before the read of the secrets."""
    found, start = [], text.find("${{")
    while start != -1:
        quoted, end = False, None
        for at in range(start + 3, len(text)):
            if text[at] == "'":
                quoted = not quoted
            elif not quoted and text[at] == "}" and text[at - 1] == "}":
                end = at
                break
        found.append(text[start + 3:] if end is None else text[start + 3:end - 1])
        start = -1 if end is None else text.find("${{", end + 1)
    return found


def test_no_tracked_file_is_a_manifest():
    """A manifest names real accounts and lives in the founder's private store, outside this public repository's
    checkout (docs/DEPLOYMENT.md, "Complimentary access"): no JSON file the repository tracks parses as one."""
    from app.services.complimentary_access_manifest import ManifestError, load_manifest

    listed = subprocess.run(["git", "ls-files", "-z", "--", "*.json"], cwd=ROOT, capture_output=True, check=True)
    names = [name for name in listed.stdout.decode().split("\0") if name]
    assert names, "git ls-files found no JSON file: the scan is not reading this checkout"
    manifests = []
    for name in names:
        raw = (ROOT / name).read_bytes()
        if b"operator_account_id" not in raw:  # every manifest names its operator
            continue
        try:
            load_manifest(raw)
        except ManifestError:
            continue
        manifests.append(name)
    assert manifests == [], "a tracked file is a complimentary-access manifest"


def test_no_dispatch_input_is_named_for_a_manifest():
    """A manifest names real accounts and a dispatch's inputs are shown on its public run page: no workflow takes one
    as an input (the runbook, docs/ops/complimentary-access.md)."""
    offenders = []
    for path in WORKFLOW_FILES:
        triggers = _parsed(path).get("on")
        if not isinstance(triggers, dict):
            continue
        for event in ("workflow_dispatch", "workflow_call"):
            inputs = (triggers.get(event) or {}).get("inputs") or {}
            offenders += [f"{path.name}: {event}.{name}" for name in inputs if "manifest" in name.lower()]
    assert offenders == []
