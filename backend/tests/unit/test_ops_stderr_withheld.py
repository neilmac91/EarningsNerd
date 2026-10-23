"""No gcloud call in the describe-service, describe-jobs, logs-probe or Cloud SQL proxy steps lets its error text
reach the job log, inherited or echoed, and no other ops.yml gcloud call may start letting it through (rule 12).

gcloud's stderr can name the acting principal, a host or a URL, and the Actions log of this public
repository is public. Two leaks were found after #1181: describe-service's shell read inherited
gcloud's stderr, and logs-probe printed the stderr it had captured. Both now print a closed class.
These gates keep it that way: every gcloud call in ops.yml discards or captures its stderr unless INHERITED
lists it (the jobs-channel and rollback actions whose progress output remains operator evidence), a file that
captures stderr is only ever tested with `grep -q`, the logs-probe and proxy-secret classifiers name the class
describe-service's gcloud_json() names, and an ops/ module never lets a child process inherit stderr and
captures or reads one only in gcloud_json(). Python a step runs is a file run by path from ops/ or scripts/,
or a one-line `python3 -c` helper (three today); never a program fed through a heredoc or stdin, nor a step
shell other than bash. The ops/ modules are standard-library only (ops.yml runs them on the runner's bare
python3, 3.12 today, while CI tests on 3.11) and linted with the backend rule set, which CI's `ruff check`
(run inside backend/) does not reach.

Not covered (review concerns): gcloud run through a variable, a function, its full path, a script a step calls
or pipes into a shell, or a `python3 -c` helper; a file a step writes and then runs by path; `|&` after a gcloud
call; a capture file named without its literal path (a relative path, a brace or variable expansion); a step in a
job other than `ops` (only its steps are read); and a dynamic import or lookup (importlib, __import__,
sys.modules) in an ops/ module. The stdin-program check does not recognise an interpreter invoked through a
variable or another name (for example `$INTERPRETER -` or `pypy3 -`).
"""
import ast
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from tests.unit.test_ops_describe_jobs import WITHHELD_TOKENS, _job, _literals

ROOT = Path(__file__).resolve().parents[3]
BASH = shutil.which("bash")
SERVICE_STEP = "Describe service env (values only for known feature flags)"
JOBS_STEP = "Describe expected job release configuration"
PROBE_STEP = "Logs read probe (safeguard-2 alert feasibility)"
PROXY_STEP = "Start Cloud SQL proxy and export connection env"
SERVICE_MODULE = ROOT / "ops/describe/service.py"
JOBS_MODULE = ROOT / "ops/describe/jobs.py"
SENTINEL = "PRIVATE_STDERR_SENTINEL principal@example.invalid"
# The logs-probe step's whole run: block, byte for byte.
PROBE_RUN = """set +e
gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="earningsnerd-backend"' \\
  --freshness=15m --limit=3 --format='value(timestamp)' >/tmp/probe.out 2>/tmp/probe.err
RC=$?
if [ $RC -eq 0 ]; then
  echo "logs-probe: logging.read PERMITTED ($(wc -l < /tmp/probe.out) recent entries visible)"
else
  echo "logs-probe: logging.read DENIED (rc=$RC)"
  # gcloud's error text can name the acting principal: print its closed class, never the text,
  # in the order gcloud_json() in ops/describe/service.py classifies.
  if grep -qsF PERMISSION_DENIED /tmp/probe.err; then CLASS=permission_denied
  elif grep -qsF NOT_FOUND /tmp/probe.err; then CLASS=not_found
  elif grep -qsF -e UNAVAILABLE -e DEADLINE_EXCEEDED /tmp/probe.err; then CLASS=unavailable
  else CLASS="error (gcloud exit $RC)"; fi
  echo "logs-probe: failure class $CLASS (gcloud's error text withheld)"
fi
set +e
gcloud logging read 'jsonPayload.event="company_upsert_conflict" OR textPayload:"company_upsert_conflict"' \\
  --freshness=7d --limit=20 --format=json >/tmp/conflicts.json 2>/dev/null
if [ $? -eq 0 ]; then
  echo "company_upsert_conflict entries in last 7d: $(python3 -c 'import json;print(len(json.load(open("/tmp/conflicts.json"))))' 2>/dev/null || echo 0)"
fi
# Sentry at startup: main.py prints one of four lines as an API-service revision starts (the task worker
# runs task_worker_main.py, which starts no Sentry and prints none). Name the revisions that printed each in
# the last seven days, with a count from the newest 500 entries per kind; never a line itself, which can
# quote an exception. A read that fails prints UNVERIFIED with a closed class, never gcloud's text, and the
# step adds one warning naming those kinds and the remedy (lessons/ops-denied-reads-report-unverified.md).
SCOPE='resource.type="cloud_run_revision" AND resource.labels.service_name="earningsnerd-backend"'
UNVERIFIED=""
for KIND in "initialized:Sentry error tracking initialized" "failed:Sentry initialization failed" \\
    "dsn-unset:SENTRY_DSN not configured" "sdk-missing:Sentry SDK not available"; do
  if gcloud logging read "$SCOPE AND textPayload:\\"${KIND#*:}\\"" --freshness=7d --limit=500 \\
      --format='value(resource.labels.revision_name)' >/tmp/sentry.txt 2>/tmp/sentry.err; then
    echo "sentry startup (7d) ${KIND%%:*}:$(sort /tmp/sentry.txt | uniq -c | awk '{printf " %s x%s", $2, $1} END {if (!NR) printf " none"}')"
  else
    RC=$?
    if grep -qsF PERMISSION_DENIED /tmp/sentry.err; then CLASS=permission_denied
    elif grep -qsF NOT_FOUND /tmp/sentry.err; then CLASS=not_found
    elif grep -qsF -e UNAVAILABLE -e DEADLINE_EXCEEDED /tmp/sentry.err; then CLASS=unavailable
    else CLASS="error (gcloud exit $RC)"; fi
    echo "sentry startup (7d) ${KIND%%:*}: UNVERIFIED ($CLASS; gcloud's error text withheld)"
    UNVERIFIED="$UNVERIFIED ${KIND%%:*}=$CLASS"
  fi
done
if [ -n "$UNVERIFIED" ]; then
  echo "::warning::sentry startup UNVERIFIED:$UNVERIFIED. Not evidence that Sentry started or failed; for permission_denied the Ops identity needs its Logging read role, for not_found check the project and the service, otherwise dispatch logs-probe again."
fi
"""
# The four lines main.py prints as Sentry starts, or does not, by the kind the logs-probe step names for each.
SENTRY_KINDS = (("initialized", "Sentry error tracking initialized"), ("failed", "Sentry initialization failed"),
                ("dsn-unset", "SENTRY_DSN not configured"), ("sdk-missing", "Sentry SDK not available"))
SENTRY_LINES = tuple(line for _, line in SENTRY_KINDS)
# What the fake answers for each Sentry read, in SENTRY_KINDS order, and the lines the step prints for them. Each kind
# names revisions in one fixture and none in the other; only API-service revisions, as the task worker starts no Sentry.
SENTRY_ANSWERS = {
    "permitted": ("earningsnerd-backend-00509-zl7\nearningsnerd-backend-00508-62h\nearningsnerd-backend-00509-zl7\n",
                  "", "", ""),
    "denied": ("", "earningsnerd-backend-00507-dwb\n", "earningsnerd-backend-00506-6wv\nearningsnerd-backend-00506-6wv\n",
               "earningsnerd-backend-00505-q2x\n"),
}
SENTRY_PRINTED = {
    "permitted": ["sentry startup (7d) initialized: earningsnerd-backend-00508-62h x1 earningsnerd-backend-00509-zl7 x2",
                  "sentry startup (7d) failed: none", "sentry startup (7d) dsn-unset: none",
                  "sentry startup (7d) sdk-missing: none"],
    "denied": ["sentry startup (7d) initialized: none", "sentry startup (7d) failed: earningsnerd-backend-00507-dwb x1",
               "sentry startup (7d) dsn-unset: earningsnerd-backend-00506-6wv x2",
               "sentry startup (7d) sdk-missing: earningsnerd-backend-00505-q2x x1"],
}
# (gcloud's stderr, its exit status, the closed class all three classifiers name), precedence cases included.
CORPUS = [
    ("ERROR: (gcloud.logging.read) PERMISSION_DENIED: Permission denied for all log views. " + SENTINEL, 1,
     "permission_denied"),
    ("ERROR: NOT_FOUND: " + SENTINEL, 1, "not_found"),
    ("ERROR: UNAVAILABLE: " + SENTINEL, 1, "unavailable"),
    ("ERROR: DEADLINE_EXCEEDED: " + SENTINEL, 1, "unavailable"),
    ("ERROR: odd " + SENTINEL, 2, "error (gcloud exit 2)"),
    ("ERROR: NOT_FOUND on one line\nand PERMISSION_DENIED on the next " + SENTINEL, 1, "permission_denied"),
    ("ERROR: UNAVAILABLE, then NOT_FOUND " + SENTINEL, 1, "not_found"),
    ("", 1, "error (gcloud exit 1)"),
    ("sh: gcloud: not found " + SENTINEL, 127, "error (gcloud exit 127)"),
]
# gcloud calls that still let stderr reach the log, by (step, command group): actions whose progress
# output remains the operator's evidence. Retain these existing jobs-channel/rollback exceptions explicitly;
# never dispatch a mutating action merely to test this gate.
# A new inheriting call fails; a fixed one must leave this map, which can only shrink.
INHERITED = {
    ("Jobs-channel no-op probe (args override on an existing job)", "run jobs execute"): 1,
    ("Trigger companyfacts resync (internal endpoint; jobs-channel fallback)", "run jobs execute"): 1,
    ("Trigger filing-history backfill (internal endpoint; jobs-channel fallback)", "run jobs execute"): 2,
    ("Run the weekly data-quality report once (P1-9; jobs channel)", "run jobs execute"): 1,
    ("Reset a single filing's summary (per-filing regen; jobs channel)", "run jobs execute"): 2,
    ("Roll service traffic back to a named revision", "run services update-traffic"): 1,
}
SPAWNERS = {"run", "call", "check_call", "check_output", "Popen", "getoutput", "getstatusoutput"}
OS_SPAWNERS = re.compile(r"system|popen|spawn\w*|exec\w*|posix_spawn\w*|fork\w*")
# The one place an ops/ module may capture a child's stderr and read it: the seam that reduces it to a closed class.
SEAM = ("ops/describe/service.py", "gcloud_json")
# Modules that start child processes outside the subprocess/os calls this gate inspects.
CHILD_MODULES = {"pty", "asyncio", "multiprocessing"}
# Public modules in 3.11's sys.stdlib_module_names that 3.12 or 3.13 removed: CI's interpreter still lists them; the
# runner's python3 (3.12 today) lacks the first five, and a 3.13 runner would lack the rest too.
REMOVED_AFTER_311 = {
    "asynchat", "asyncore", "distutils", "imp", "smtpd",  # removed in 3.12
    "aifc", "audioop", "cgi", "cgitb", "chunk", "crypt", "imghdr", "lib2to3", "mailcap", "msilib", "nis", "nntplib",
    "ossaudiodev", "pipes", "sndhdr", "spwd", "sunau", "telnetlib", "uu", "xdrlib",  # removed in 3.13
}
# A python word anywhere in a command (behind any prefix, by any path or version), and the forms a step may run as
# the whole command: a file by path from ops/ or scripts/, or a one-line -c program quoted whole with nothing to expand.
PYTHON = re.compile(r"(?:^|[\s/\"'{])python[0-9.]*(?=[\s\"']|$)")
ALLOWED_PYTHON = re.compile(r"""python3?\s+(?:(?:ops|scripts)/\S+\.py|-c\s+(?:'[^']*'|"(?:[^"\\$`]|\\.)*"))(?=\s|$)""")
FAKE_GCLOUD = '''import json, os, sys
argv = sys.argv[1:]
with open(os.environ["FAKE_GCLOUD_CALLS"], "a") as calls:
    calls.write(json.dumps(argv) + "\\n")
answers = json.load(open(os.environ["FAKE_GCLOUD_ANSWERS"]))
answer = answers.get(json.dumps(argv), answers["*"])
sys.stdout.write(answer.get("stdout", ""))
sys.stderr.write(answer.get("stderr", "") + "\\n" + os.environ["FAKE_GCLOUD_SENTINEL"] + "\\n")
sys.exit(answer.get("rc", 0))
'''


def _steps():
    workflow = yaml.load((ROOT / ".github/workflows/ops.yml").read_text(), Loader=yaml.BaseLoader)
    return workflow, {step.get("name"): step for step in workflow["jobs"]["ops"]["steps"]}


def _fakebin(tmp_path, answers=None, stubs=None):
    """A PATH directory holding python3 (this interpreter) and, when `answers` is given, a fake gcloud: it answers
    each exact argv from `answers` (json.dumps(argv) -> stdout/stderr/rc; "*" for any other), records every call
    and writes a sentinel to stderr on every call, success included. Optional shell stubs replace setup tools."""
    directory = tmp_path / "bin"
    directory.mkdir()
    (directory / "python3").write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n')
    (directory / "python3").chmod(0o755)
    if answers is not None:
        (tmp_path / "fake_gcloud.py").write_text(FAKE_GCLOUD)
        (tmp_path / "answers.json").write_text(json.dumps(answers))
        (directory / "gcloud").write_text(f'#!/bin/sh\nexec "{sys.executable}" "{tmp_path / "fake_gcloud.py"}" "$@"\n')
        (directory / "gcloud").chmod(0o755)
    for name, body in (stubs or {}).items():
        (directory / name).write_text("#!/bin/sh\n" + body)
        (directory / name).chmod(0o755)
    return directory


def _step_shell(run, tmp_path, answers=None, env=None, *, stubs=None, cwd=ROOT):
    """Run a step's script as GitHub runs an unspecified shell (bash -e), with its /tmp/ files moved into tmp_path
    and only the given env; PATH holds the fake bin (no gcloud when `answers` is None) and the system tools.
    Proxy setup runs in a scratch cwd with its install/download/launch tools stubbed, never live."""
    calls = tmp_path / "calls.jsonl"
    calls.write_text("")
    bindir = _fakebin(tmp_path, answers, stubs)
    full_env = {"PATH": f"{bindir}" + ("" if answers is None else ":/usr/bin:/bin"), "HOME": str(tmp_path),
                "FAKE_GCLOUD_CALLS": str(calls), "FAKE_GCLOUD_ANSWERS": str(tmp_path / "answers.json"),
                "FAKE_GCLOUD_SENTINEL": "WARNING: PRIVATE_FAKE_GCLOUD_STDERR_SENTINEL principal@example.invalid",
                **(env or {})}
    result = subprocess.run([BASH, "-e", "-c", run.replace("/tmp/", f"{tmp_path}/")], cwd=cwd, env=full_env,
                            capture_output=True, text=True, timeout=120, check=False)
    return result, [json.loads(line) for line in calls.read_text().splitlines()]


def _service_env(workflow):
    return {"REGION": workflow["env"]["REGION"], "SERVICE": workflow["env"]["SERVICE"]}


def _service_reads(region):
    """The six describe-service reads in order (argv after `gcloud`), answered with minimal passing shapes."""
    pins = [{"name": "SEC_RATE_LIMIT_PER_SECOND", "value": "1"}, {"name": "EDGAR_RATE_LIMIT_PER_SEC", "value": "1"}]

    def status(revision):
        return {"latestReadyRevisionName": revision, "latestCreatedRevisionName": revision,
                "traffic": [{"revisionName": revision, "percent": 100,
                             "url": "https://PRIVATE_TRAFFIC_URL_SENTINEL.example.invalid"}]}

    tail = [f"--region={region}", "--format=json"]
    return [
        (["run", "services", "describe", "earningsnerd-backend", *tail], {"status": status("serving")}),
        (["run", "revisions", "describe", "serving", *tail], {"spec": {"containers": [{"image": "i", "env": pins}]}}),
        (["run", "jobs", "describe", "earningsnerd-pregenerate", *tail],
         {"spec": {"template": {"spec": {"template": {"spec": {"containers": [{"image": "j"}]}}}}}}),
        (["run", "services", "describe", "earningsnerd-task-worker", *tail], {"status": status("worker-serving")}),
        (["run", "revisions", "describe", "worker-serving", *tail],
         {"spec": {"containers": [{"image": "k", "env": pins}]}}),
        (["run", "services", "get-iam-policy", "earningsnerd-task-worker", *tail],
         {"bindings": [{"role": "roles/run.invoker", "members": ["serviceAccount:PRIVATE_INVOKER@example.invalid"]}]}),
    ]


@pytest.mark.parametrize("stderr,code,klass", [
    ("ERROR: (gcloud.run.services.describe) PERMISSION_DENIED: " + SENTINEL, 1, "permission_denied"),
    ("ERROR: NOT_FOUND: " + SENTINEL, 1, "not_found"),
    ("ERROR: UNAVAILABLE: " + SENTINEL, 1, "unavailable"),
    ("ERROR: odd " + SENTINEL, 3, "error (gcloud exit 3)"),
    (None, None, "error (gcloud not executable)"),
])
def test_describe_service_step_prints_a_closed_class_for_a_failed_service_read(tmp_path, stderr, code, klass):
    """The step as GitHub runs it, against a real child gcloud that prints a sentinel on both streams."""
    workflow, steps = _steps()
    run = steps[SERVICE_STEP]["run"]
    assert run == "python3 ops/describe/service.py"
    answers = None if stderr is None else {"*": {"stdout": "PRIVATE_STDOUT_SENTINEL", "stderr": stderr, "rc": code}}
    result, calls = _step_shell(run, tmp_path, answers, _service_env(workflow))
    assert result.returncode == 1 and result.stdout == ""
    assert result.stderr == ("Unresolved production configuration: cannot describe services "
                             f"earningsnerd-backend ({klass}).\n")
    # The service read is the first and only call, with the shell read's exact argv.
    assert calls == ([] if stderr is None else
                     [["run", "services", "describe", "earningsnerd-backend", "--region=us-west1", "--format=json"]])


def test_describe_service_step_keeps_gcloud_stderr_out_of_a_passing_run(tmp_path):
    """Success-path stderr (a warning, an update notice) is captured too: it never reaches the log."""
    workflow, steps = _steps()
    reads = _service_reads(workflow["env"]["REGION"])
    answers = {json.dumps(argv): {"stdout": json.dumps(body), "stderr": "WARNING: " + SENTINEL} for argv, body in reads}
    answers["*"] = {"stderr": "ERROR: unexpected call " + SENTINEL, "rc": 2}
    result, calls = _step_shell(steps[SERVICE_STEP]["run"], tmp_path, answers, _service_env(workflow))
    assert result.returncode == 0 and result.stderr == "", result.stderr
    assert calls == [argv for argv, _ in reads]  # six reads, the service's own first, each with its exact argv
    assert result.stdout.startswith('Serving traffic: [{"percent": 100, "revisionName": "serving"}]\n')
    assert result.stdout.endswith("describe-service: PASS\n")
    assert "PRIVATE_" not in result.stdout and "example.invalid" not in result.stdout


@pytest.mark.parametrize("failing", [None, 3])
def test_describe_jobs_step_never_prints_gcloud_stderr(tmp_path, failing):
    """The step as GitHub runs it: the loop discards gcloud's stderr on every read, success included; a failed read
    stops the loop with its closed line and the module never runs."""
    workflow, steps = _steps()
    run = steps[JOBS_STEP]["run"]
    jobs = re.search(r"jobs=\(\n((?:\s+earningsnerd-[a-z-]+\n)+)\s*\)", run).group(1).split()
    pools = _literals(JOBS_MODULE.read_text())["expected_pools"]
    assert jobs == list(pools)
    reads = [["run", "jobs", "describe", job, f"--region={workflow['env']['REGION']}", "--format=json"] for job in jobs]
    answers = {json.dumps(argv): {"stdout": json.dumps(_job(argv[3], pools[argv[3]])), "stderr": "WARNING: " + SENTINEL}
               for argv in reads}
    if failing is not None:
        answers[json.dumps(reads[failing])] = {"stderr": "ERROR: (gcloud.run.jobs.describe) PERMISSION_DENIED: " + SENTINEL,
                                               "rc": 1}
    answers["*"] = {"stderr": "ERROR: unexpected call " + SENTINEL, "rc": 2}
    result, calls = _step_shell(run, tmp_path, answers, {"REGION": workflow["env"]["REGION"]})
    assert result.stderr == "" and "PRIVATE_" not in result.stdout and "example.invalid" not in result.stdout
    assert not [token for token in WITHHELD_TOKENS if token in result.stdout]  # command values stay withheld
    if failing is None:
        assert result.returncode == 0 and calls == reads
        assert result.stdout.count("== earningsnerd-") == 8 and result.stdout.endswith("describe-jobs: PASS\n")
    else:
        assert result.returncode == 1 and calls == reads[:failing + 1]
        assert result.stdout == f"::error::expected Cloud Run job '{jobs[failing]}' is missing or unreadable\n"


def _sentry_ok(fixture):
    """Each Sentry read answering as a passing gcloud does (a warning on stderr), with this fixture's revisions."""
    return [{"stdout": out, "stderr": "WARNING: " + SENTINEL} for out in SENTRY_ANSWERS[fixture]]


def _probe_answers(stdout, stderr, code, sentry):
    probe = ["logging", "read", 'resource.type="cloud_run_revision" AND resource.labels.service_name="earningsnerd-backend"',
             "--freshness=15m", "--limit=3", "--format=value(timestamp)"]
    conflicts = ["logging", "read", 'jsonPayload.event="company_upsert_conflict" OR textPayload:"company_upsert_conflict"',
                 "--freshness=7d", "--limit=20", "--format=json"]
    scope = 'resource.type="cloud_run_revision" AND resource.labels.service_name="earningsnerd-backend"'
    sentry_reads = [["logging", "read", f'{scope} AND textPayload:"{line}"', "--freshness=7d", "--limit=500",
                     "--format=value(resource.labels.revision_name)"] for line in SENTRY_LINES]
    answers = {json.dumps(probe): {"stdout": stdout, "stderr": stderr, "rc": code},
               json.dumps(conflicts): {"stdout": '[{"x": 1}, {"x": 2}]', "stderr": "WARNING: " + SENTINEL},
               **{json.dumps(read): answer for read, answer in zip(sentry_reads, sentry)},
               "*": {"stderr": "ERROR: unexpected call " + SENTINEL, "rc": 2}}
    return answers, [probe, conflicts, *sentry_reads]


def _probe(tmp_path, stdout, stderr, code, sentry):
    _, steps = _steps()
    run = steps[PROBE_STEP]["run"]
    assert run == PROBE_RUN
    # The step's own /tmp files move into this test's directory; nothing else in the script changes.
    assert run.count("/tmp/") == 14
    answers, reads = _probe_answers(stdout, stderr, code, sentry)
    result, calls = _step_shell(run, tmp_path, answers)
    assert calls == reads and result.returncode == 0 and result.stderr == ""
    assert "PRIVATE_" not in result.stdout and "example.invalid" not in result.stdout
    return result.stdout.splitlines()


def test_logs_probe_prints_permitted_reads_and_conflicts_unchanged(tmp_path):
    lines = _probe(tmp_path, "t1\nt2\nt3\n", "WARNING: " + SENTINEL, 0, _sentry_ok("permitted"))
    # GNU wc (the runner) prints "3"; BSD wc (a Mac's local gate) pads the count with spaces.
    assert len(lines) == 6 and re.fullmatch(r"logs-probe: logging\.read PERMITTED \( *3 recent entries visible\)", lines[0])
    assert lines[1:] == ["company_upsert_conflict entries in last 7d: 2", *SENTRY_PRINTED["permitted"]]


@pytest.mark.parametrize("stderr,code,klass", CORPUS)
def test_logs_probe_reports_a_failed_sentry_read_as_unverified(tmp_path, stderr, code, klass):
    """A Sentry read that fails prints its kind as UNVERIFIED with the closed class, never gcloud's text and never a
    verdict (lessons/ops-denied-reads-report-unverified.md); the other reads still print theirs, and the step passes."""
    # gcloud prints entries page by page, so a read that fails late has already written some: never a verdict.
    failing = {"stdout": "PRIVATE_PARTIAL_REVISION\n", "stderr": stderr, "rc": code}
    unverified = {kind: f"sentry startup (7d) {kind}: UNVERIFIED ({klass}; gcloud's error text withheld)"
                  for kind, _ in SENTRY_KINDS}
    (tmp_path / "all").mkdir()
    lines = _probe(tmp_path / "all", "t1\n", "", 0, [failing] * 4)
    warning = ("::warning::sentry startup UNVERIFIED: " + " ".join(f"{kind}={klass}" for kind, _ in SENTRY_KINDS) +
               ". Not evidence that Sentry started or failed; for permission_denied the Ops identity needs its Logging read"
               " role, for not_found check the project and the service, otherwise dispatch logs-probe again.")
    assert len(lines) == 7 and lines[2:] == [*unverified.values(), warning]
    (tmp_path / "one").mkdir()
    ok = _sentry_ok("denied")
    lines = _probe(tmp_path / "one", "t1\n", "", 0, [ok[0], failing, ok[2], ok[3]])
    printed = SENTRY_PRINTED["denied"]
    assert lines[2:] == [printed[0], unverified["failed"], printed[2], printed[3],
                         warning.replace(" ".join(f"{kind}={klass}" for kind, _ in SENTRY_KINDS), f"failed={klass}")]


def _import_time_prints(tree):
    """The literal text of each one-argument print a module makes as it is imported: its top-level statements and,
    nested to any depth, the bodies of its if, try, with, for and while blocks, never a function, a class or an
    `if __name__ == "__main__"` block; the argument a str constant or an f-string (its literal parts), never a value a
    call builds. It reads the source only (a block under `if False:` or a rebound print still counts)."""
    texts, stack = [], list(tree.body)
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) or (
                isinstance(node, ast.If)
                and ast.unparse(node.test).replace("'", '"') in ('__name__ == "__main__"', '"__main__" == __name__')):
            continue
        call = node.value if isinstance(node, ast.Expr) else None
        if (isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == "print"
                and len(call.args) == 1 and isinstance(call.args[0], (ast.Constant, ast.JoinedStr))):
            parts = call.args[0].values if isinstance(call.args[0], ast.JoinedStr) else [call.args[0]]
            texts += [part.value for part in parts if isinstance(part, ast.Constant) and isinstance(part.value, str)]
        for field in ("body", "handlers", "orelse", "finalbody"):
            stack.extend(getattr(node, field, None) or [])
    return texts


@pytest.mark.parametrize("source,seen", [
    ('print("✓ Sentry error tracking initialized")', True),
    ('try:\n    import x\nexcept ImportError:\n    print("Sentry SDK not available")', True),
    ('if a:\n    print(f"⚠️  Sentry initialization failed ({e})")', True),
    ('def f():\n    print("Sentry SDK not available")', False),
    ('if __name__ == "__main__":\n    print("Sentry SDK not available")', False),
    ('if "__main__" == __name__:\n    print("Sentry SDK not available")', False),
    ('print("Sentry SDK not available".lower())', False),
    ('print(json.dumps({"message": "Sentry SDK not available"}))', False),
])
def test_import_time_prints_sees_only_a_plain_print_that_runs_on_import(source, seen):
    assert any("Sentry" in text for text in _import_time_prints(ast.parse(source))) is seen


def test_logs_probe_counts_the_lines_main_prints_as_sentry_starts():
    # The probe's Sentry reads name the lines main.py prints as Sentry starts or does not, so a reworded line there
    # cannot leave the probe counting nothing. Only a plain print that runs on import counts: a line kept in a
    # function, under `if __name__ == "__main__"`, or built by a call (a JSON line lands in jsonPayload, which the
    # probe's textPayload filter never reads) would leave the probe counting nothing while the text stayed in main.py.
    texts = _import_time_prints(ast.parse((ROOT / "backend/main.py").read_text(encoding="utf-8")))
    missing = [line for line in SENTRY_LINES if not any(line in text for text in texts)]
    assert not missing, f"main.py no longer prints {missing} on import: update the logs-probe step's Sentry reads"
    for kind, line in SENTRY_KINDS:
        assert f'"{kind}:{line}"' in PROBE_RUN


def _policy_class(monkeypatch, capsys, failure, code):
    """The class describe-service's gcloud_json() names for a failed read: run the module with its invoker policy
    read failing as gcloud would (CalledProcessError with this stderr text and exit status)."""
    reads = {tuple(argv[1:4]): body for argv, body in _service_reads("fixture-region")}

    def fake(argv, *, text, stderr, timeout):
        assert text is True and stderr is subprocess.PIPE and timeout == 100
        if tuple(argv[2:5]) == ("services", "get-iam-policy", "earningsnerd-task-worker"):
            raise subprocess.CalledProcessError(code, argv, output="", stderr=failure)
        return json.dumps(reads[tuple(argv[2:5])])

    monkeypatch.setattr(subprocess, "check_output", fake)
    monkeypatch.setenv("REGION", "fixture-region")
    monkeypatch.setenv("SERVICE", "earningsnerd-backend")
    spec = importlib.util.spec_from_file_location("ops_describe_service", SERVICE_MODULE)
    spec.loader.exec_module(importlib.util.module_from_spec(spec))
    output = capsys.readouterr().out
    assert "PRIVATE_" not in output and "principal@" not in output
    return re.search(r"^Worker invoker policy: UNVERIFIED \((.+)\)$", output, re.M).group(1)


@pytest.mark.parametrize("stderr,code,klass", CORPUS)
def test_logs_probe_names_the_class_gcloud_json_names_never_the_text(tmp_path, monkeypatch, capsys, stderr, code, klass):
    """The denied branch prints the class line, never gcloud's text; and the shell chain names the class the
    describe-service seam names for the same stderr and exit status, precedence included."""
    lines = _probe(tmp_path, "", stderr, code, _sentry_ok("denied"))
    assert lines == [f"logs-probe: logging.read DENIED (rc={code})",
                     f"logs-probe: failure class {klass} (gcloud's error text withheld)",
                     "company_upsert_conflict entries in last 7d: 2", *SENTRY_PRINTED["denied"]]
    assert _policy_class(monkeypatch, capsys, stderr, code) == klass


@pytest.mark.parametrize("stderr,code,klass", [("WARNING: " + SENTINEL, 0, None), *CORPUS])
def test_proxy_secret_read_withholds_stderr_and_stops_on_failure(tmp_path, monkeypatch, capsys, stderr, code, klass):
    """Run the whole proxy step with fake setup tools and gcloud; failures must never reach env export or launch."""
    workflow, steps = _steps()
    argv = ["secrets", "versions", "access", "latest", "--secret=DATABASE_URL"]
    database_url = "postgresql://fixture-user:fixture-password@/fixture-db?host=/cloudsql/fixture:region:instance"
    local_url = "postgresql://fixture-user:fixture-password@127.0.0.1:5432/fixture-db"
    answers = {json.dumps(argv): {"stdout": database_url if code == 0 else "PRIVATE_STDOUT_SENTINEL",
                                "stderr": stderr, "rc": code},
               "*": {"stderr": "ERROR: unexpected call " + SENTINEL, "rc": 2}}
    progress = tmp_path / "setup-progress"
    stubs = {name: f"printf '%s\\n' '{name}' >> \"$FAKE_PROXY_PROGRESS\"\n"
             for name in ("sudo", "curl", "chmod", "nohup", "pg_isready")}
    stubs["sha256sum"] = 'cat >/dev/null\n'
    stubs["nohup"] += ': > "$FAKE_PROXY_STARTED"\n'
    stubs["pg_isready"] += 'test -f "$FAKE_PROXY_STARTED"\n'
    env_file = tmp_path / "github-env"
    result, calls = _step_shell(steps[PROXY_STEP]["run"], tmp_path, answers,
                               {"CLOUD_SQL_PROXY_VERSION": workflow["env"]["CLOUD_SQL_PROXY_VERSION"],
                                "CLOUD_SQL_PROXY_SHA256": workflow["env"]["CLOUD_SQL_PROXY_SHA256"],
                                "GITHUB_ENV": str(env_file), "FAKE_PROXY_PROGRESS": str(progress),
                                "FAKE_PROXY_STARTED": str(tmp_path / "proxy-started")},
                               stubs=stubs, cwd=tmp_path)
    assert calls == [argv] and result.returncode == code and result.stderr == ""
    assert "PRIVATE_" not in result.stdout and "example.invalid" not in result.stdout
    reached = progress.read_text().splitlines()
    assert reached[:4] == ["sudo", "sudo", "curl", "chmod"]
    if code:
        assert result.stdout == (f"::error::Cloud SQL proxy: cannot read DATABASE_URL "
                                 f"({klass}; gcloud's error text withheld)\n")
        assert not env_file.exists() and len(reached) == 4
        assert _policy_class(monkeypatch, capsys, stderr, code) == klass
    else:
        assert result.stdout == (f"::add-mask::{database_url}\n::add-mask::fixture-password\n"
                                 f"::add-mask::{local_url}\n")
        assert env_file.read_text() == ("PGUSER=fixture-user\nPGPASSWORD=fixture-password\nPGDATABASE=fixture-db\n"
                                       f"PGHOST=127.0.0.1\nPGPORT=5432\nDATABASE_URL={local_url}\n")
        # A readiness attempt can precede the detached fake launch, just as on the runner.
        assert reached.count("nohup") == 1 and reached.count("pg_isready") >= 2


def _executable_lines(run):
    """A run: block's executable lines: comment lines dropped, backslash continuations joined."""
    lines = [line for line in run.splitlines() if not line.lstrip().startswith("#")]
    return re.sub(r"\\\n[ \t]*", " ", "\n".join(lines)).splitlines()


def _commands(line):
    """The simple commands of one shell line, split at unquoted ; | & ( ) and at $( ... ), with leading
    keywords (if, then, !, ...) dropped. Quoting restarts inside a command substitution."""
    commands, current, quotes, quote, index = [], [], [], None, 0
    while index < len(line):
        char, pair = line[index], line[index:index + 2]
        if quote == "'":
            quote = None if char == "'" else quote
        elif pair == "$(":
            commands.append("".join(current))
            current, index = [], index + 2
            quotes.append(quote)
            quote = None
            continue
        elif quote == '"' and char == "\\":
            current.append(line[index:index + 2])
            index += 2
            continue
        elif quote == '"':
            quote = None if char == '"' else quote
        elif char in "'\"":
            quote = char
        elif char == ")" and quotes:
            commands.append("".join(current))
            current, quote = [], quotes.pop()
            index += 1
            continue
        elif char in ";|()" or (char == "&" and line[index - 1:index] != ">" and line[index + 1:index + 2] != ">"):
            commands.append("".join(current))
            current = []
            index += 1
            continue
        current.append(char)
        index += 1
    commands.append("".join(current))
    keywords = re.compile(r"^\s*(?:(?:if|then|elif|else|do|while|until|!)\s+)*")
    return [keywords.sub("", command).strip() for command in commands if command.strip()]


def _gcloud_calls():
    """(step name, command group, the whole command) for every gcloud call in ops.yml's run: blocks."""
    _, steps = _steps()
    for name, step in steps.items():
        for line in _executable_lines(step.get("run") or ""):
            for command in _commands(line):
                if re.match(r"gcloud\s", command):
                    group = " ".join(re.findall(r"^gcloud((?:\s+[a-z][a-z-]*){1,3})", command)[0].split())
                    yield name, group, command


def _stderr_class(command):
    """Where a command's stderr goes: "inherited" (the job log), "discarded", or the file that captures it. The last
    stderr redirect wins, so `2>/dev/null 2>&1` inherits."""
    targets = re.findall(r"(?<![0-9&>])2>\s*(&?[^\s;|&)]+)", command)
    if not targets or targets[-1].startswith("&"):
        return "inherited"
    return "discarded" if targets[-1] == "/dev/null" else targets[-1]


@pytest.mark.parametrize("command,where", [
    ("gcloud x", "inherited"),
    ("gcloud x 2>&1", "inherited"),
    ("gcloud x 2>/dev/null", "discarded"),
    ("gcloud x 2>/dev/null 2>&1", "inherited"),
    ("gcloud x 2>&1 2>/dev/null", "discarded"),
    ("gcloud x >/tmp/o 2>/tmp/e", "/tmp/e"),
])
def test_stderr_class_takes_the_last_redirect(command, where):
    assert _stderr_class(command) == where


def test_ops_workflow_gcloud_stderr_is_discarded_or_captured_except_listed_actions():
    inherited, captured = {}, []
    calls = list(_gcloud_calls())
    workflow, steps = _steps()
    # The name-keyed map drops a step whose name repeats (or a second unnamed one): every run step must stay visible.
    listed = workflow["jobs"]["ops"]["steps"]
    assert len(steps) == len(listed) and all(step.get("name") for step in listed if "run" in step), (
        "every ops.yml run step needs its own name, or the step map hides it from these scans")
    words = sum(len(re.findall(r"(?:^|[\s;|&!]|\$\()gcloud\s+[a-z]", "\n".join(_executable_lines(step.get("run") or "")),
                               re.M)) for step in steps.values())
    assert len(calls) == words >= 14, "the scanner must see every gcloud call in ops.yml"
    # Neither the scanner nor the count sees into backticks, an eval or a shell started with options (sh -c,
    # bash -e -c, bash -o pipefail -c), nor which file a /tmp/ glob reads: ops.yml uses none, so each fails here.
    opaque = [(name, line) for name, step in steps.items() for line in _executable_lines(step.get("run") or "")
              if re.search(r"`|\beval\b|\b(?:ba|da|k|z)?sh\s+-|/tmp/\S*[*?\[]", line)]
    assert not opaque, f"the scanner cannot see into backticks, eval, sh -c or a /tmp/ glob: {opaque}"
    disguised = [(name, command) for name, step in steps.items() for line in _executable_lines(step.get("run") or "")
                 for command in _commands(line) if re.match(r'[\\"\']+gcloud\b', command)]
    assert not disguised, f"the scanner cannot see a quoted or escaped gcloud: {disguised}"
    for name, group, command in calls:
        where = _stderr_class(command)
        if where == "inherited":
            inherited[(name, group)] = inherited.get((name, group), 0) + 1
        elif where != "discarded":
            captured.append((name, where))
    assert inherited == INHERITED, "a gcloud call lets its stderr reach the job log; discard or classify it"
    assert captured == [(PROBE_STEP, "/tmp/probe.err"), (PROBE_STEP, "/tmp/sentry.err"), (PROXY_STEP, "/tmp/proxy-secret.err")]
    # A file that captured stderr is only tested, never printed: every other command naming it, in any step, is
    # a grep -q.
    for _, path in captured:
        readers = [command for step in steps.values() for line in _executable_lines(step.get("run") or "")
                   for command in _commands(line) if path in command and not command.startswith("gcloud ")]
        assert readers and all(re.match(r"grep\s+-q[A-Za-z]*\s", reader) for reader in readers), readers


def _inline_python(run, shell=None):
    """Whether a step's script runs a Python program no committed file holds: any heredoc (ops.yml has none), a
    step shell other than bash, or a python command other than a file run by path from ops/ or scripts/ or a
    one-line `-c` program (so `python3 <<'PY'`, `python3 -I - <<`, `cat <<'PY' | python3 -`, `printf ... | python3`,
    `printf ... | timeout 60 python3 -`)."""
    if "<<" in run or shell not in (None, "bash"):
        return True
    return any(PYTHON.search(command) and not ALLOWED_PYTHON.match(command)
               for line in _executable_lines(run) for command in _commands(line))


@pytest.mark.parametrize("run,shell,inline", [
    ("python3 - <<'PY'\nprint(1)\nPY\n", None, True),
    ("python3 <<'PY'\nprint(1)\nPY\n", None, True),
    ("python3 -I - <<'PY'\nprint(1)\nPY\n", None, True),
    ("python3 -u - <<PY\nprint(1)\nPY\n", None, True),
    ("python3.12 - <<'PY'\nprint(1)\nPY\n", None, True),
    ("cat <<'PY' | python3 -\nprint(1)\nPY\n", None, True),
    ("python3 ops/describe/jobs.py <<EOF\nx\nEOF\n", None, True),  # no heredoc at all, even into a committed file
    ("printf 'print(1)\\n' | python3\n", None, True),
    ("printf 'print(1)\\n' | /usr/bin/python3 -\n", None, True),
    ("printf 'print(1)\\n' | env python3 /dev/stdin\n", None, True),
    ("python3 -c '\nprint(1)\n'\n", None, True),  # a -c program over several lines
    ('python3 -c "$PROGRAM"\n', None, True),
    ("print(1)\n", "python", True),
    ("printf 'print(1)\\n' | timeout 60 python3 -\n", None, True),
    ("printf 'print(1)\\n' | /usr/bin/env python3 -\n", None, True),
    ("printf 'print(1)\\n' | sudo -E python3\n", None, True),
    ('timeout 60 python3 -c "$PROGRAM"\n', None, True),
    ("python3 ops/describe/service.py", None, False),
    ("python3 ops/describe/service.py", "bash", False),
    ('python3 ops/capacity/readout.py --start "$S" --end "$E" \\\n  --region "$REGION" --output receipt/cloud.json\n',
     None, False),
    ("set -euo pipefail\nexport JOB_DIR\npython3 ops/describe/jobs.py\n", None, False),
    ("python scripts/repair_ticker_by_cik.py --apply\n", None, False),
    ("python3 -c 'print(1)'\n", None, False),
    ('PAYLOAD=$(python3 -c "import json,sys; print(json.dumps(sys.argv[1:]))" "$TICKERS")\n', None, False),
    ("""echo "n: $(python3 -c 'import json;print(len(json.load(open("/tmp/x.json"))))' 2>/dev/null || echo 0)"\n""",
     None, False),
])
def test_inline_python_predicate(run, shell, inline):
    assert _inline_python(run, shell) is inline


def test_no_ops_step_runs_an_inline_python_program():
    """Python a step feeds through a heredoc or stdin is a committed ops/ module run by path instead, so this suite
    loads, lints and gates it; the one-line `python3 -c` helpers stay inline."""
    workflow, steps = _steps()
    # A job- or workflow-level default shell applies to every run step that names none.
    default = next((scope["defaults"]["run"]["shell"] for scope in (workflow["jobs"]["ops"], workflow)
                    if "shell" in ((scope.get("defaults") or {}).get("run") or {})), None)
    inline = [name for name, step in steps.items()
              if "run" in step and _inline_python(step["run"], step.get("shell", default))]
    assert not inline, f"commit the program under ops/ and run it by path: {inline}"


def _ops_modules():
    modules = sorted((ROOT / "ops").rglob("*.py"))
    assert {path.relative_to(ROOT).as_posix() for path in modules} >= {
        "ops/capacity/readout.py", "ops/describe/service.py", "ops/describe/jobs.py"}
    return modules


def _functions(tree):
    """node -> the name of the function that encloses it (None at module level)."""
    owner = {}

    def visit(node, function):
        for child in ast.iter_child_nodes(node):
            name = child.name if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) else function
            owner[child] = name
            visit(child, name)
    visit(tree, None)
    return owner


def test_ops_modules_never_let_a_child_process_inherit_stderr():
    spawns, stderr_reads = 0, []
    for path in _ops_modules():
        tree = ast.parse(path.read_text())
        owner = _functions(tree)
        parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
        module = path.relative_to(ROOT).as_posix()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
                assert not {name.split(".")[0] for name in names} & CHILD_MODULES, (
                    f"{path}:{node.lineno}: {names} starts child processes this gate does not inspect")
            if isinstance(node, ast.ImportFrom) and node.module in ("subprocess", "os", "pty"):
                assert node.module == "os" and not any(OS_SPAWNERS.fullmatch(a.name) for a in node.names), path
            if isinstance(node, ast.Import):  # an alias would hide a call from this gate
                assert all(a.asname is None for a in node.names if a.name in ("os", "subprocess")), path
            # So would the module bound to another name (`sp = subprocess`) or handed to a call (getattr(os, ...)).
            if isinstance(node, ast.Name) and node.id in ("os", "subprocess"):
                assert isinstance(parents.get(node), ast.Attribute), f"{path}:{node.lineno}: bare {node.id}"
            # So would a spawner bound to another name (`run = subprocess.run`, functools.partial(subprocess.run)).
            if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                    and (node.value.id == "subprocess" and node.attr in SPAWNERS
                         or node.value.id == "os" and OS_SPAWNERS.fullmatch(node.attr))):
                assert isinstance(parents.get(node), ast.Call) and parents[node].func is node, (
                    f"{path}:{node.lineno}: {node.value.id}.{node.attr} must be called where it is named")
            if (isinstance(node, ast.Attribute) and node.attr == "stderr"
                    and not (isinstance(node.value, ast.Name) and node.value.id in ("sys", "subprocess"))):
                stderr_reads.append((module, owner.get(node)))
            # communicate() returns the captured stderr too.
            if isinstance(node, ast.Attribute) and node.attr == "communicate" and (module, owner.get(node)) != SEAM:
                stderr_reads.append((module, owner.get(node)))
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)):
                continue
            owner_name, function = node.func.value.id, node.func.attr
            assert not (owner_name == "os" and OS_SPAWNERS.fullmatch(function)), f"{path}:{node.lineno}: os.{function}"
            if owner_name == "subprocess" and function in SPAWNERS:
                spawns += 1
                stderr = [k.value for k in node.keywords if k.arg == "stderr"]
                assert len(stderr) == 1 and isinstance(stderr[0], ast.Attribute) and stderr[0].attr in (
                    "PIPE", "DEVNULL"), f"{path}:{node.lineno}: subprocess.{function} must set stderr=PIPE or DEVNULL"
                # A captured stderr can still print (a CompletedProcess repr carries it), so only the seam captures.
                assert stderr[0].attr == "DEVNULL" or (module, owner.get(node)) == SEAM, (
                    f"{path}:{node.lineno}: only gcloud_json() may capture a child's stderr")
    assert spawns >= 2  # describe-service's gcloud seam and the readout's identity reads
    # A captured stderr is read in one place only, the seam that reduces it to a closed class.
    assert stderr_reads == [SEAM], stderr_reads


def test_ops_modules_import_only_the_standard_library():
    for path in _ops_modules():
        # A script's own directory is sys.path[0], so a file named like a standard module would shadow it.
        assert path.stem not in sys.stdlib_module_names, f"{path} shadows the standard library's {path.stem}"
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                assert node.level == 0, f"{path}: ops.yml runs this file as a script; no relative import"
                names = [node.module]
            else:
                continue
            for name in names:
                assert name.split(".")[0] in sys.stdlib_module_names, f"{path}: {name} is not in the standard library"
                assert name.split(".")[0] not in REMOVED_AFTER_311, f"{path}: {name} is gone from Python 3.12 or 3.13"


def test_ops_python_passes_the_backend_lint_rule_set():
    """CI's ruff runs inside backend/, so it never reaches ops/; this runs the same pinned ruff and rule set here,
    and the local gate's pytest runs it too."""
    result = subprocess.run([sys.executable, "-m", "ruff", "check", "--no-cache", "--config",
                             str(ROOT / "backend/ruff.toml"), *map(str, _ops_modules())],
                            cwd=ROOT, capture_output=True, text=True, timeout=120, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
