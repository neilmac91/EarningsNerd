"""gcloud's error text never reaches an Ops read's job log, inherited or echoed (rule 12).

gcloud's stderr can name the acting principal, a host or a URL, and the Actions log of this public
repository is public. Two leaks were found after #1181: describe-service's shell read inherited
gcloud's stderr, and logs-probe printed the stderr it had captured. Both now print a closed class.
These gates keep it that way: every gcloud call in ops.yml discards or captures its stderr unless it
is one of the listed actions, a file that captures stderr is only ever tested with `grep -q`, the
logs-probe classifier names the class describe-service's gcloud_json() names, and an ops/ module never
lets a child process inherit stderr nor reads a captured stderr outside gcloud_json(). Python an ops.yml
step runs is a committed ops/ module (no inline heredoc program), standard-library only (ops.yml runs it
on the runner's bare python3) and linted with the backend rule set, which CI's `ruff check` (run inside
backend/) does not reach.

Not covered (review concerns): gcloud reached through a variable, a function or a script a step calls,
and a dynamic call (getattr, importlib) in an ops/ module.
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

from tests.unit.test_ops_describe_jobs import WITHHELD_TOKENS, _job

ROOT = Path(__file__).resolve().parents[3]
BASH = shutil.which("bash")
SERVICE_STEP = "Describe service env (values only for known feature flags)"
JOBS_STEP = "Describe expected job release configuration"
PROBE_STEP = "Logs read probe (safeguard-2 alert feasibility)"
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
"""
# (gcloud's stderr, its exit status, the closed class both classifiers name), precedence cases included.
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
# output is the operator's evidence, and the Cloud SQL proxy step's secret read (a recorded follow-up).
# A new inheriting call fails; a fixed one must leave this map, which can only shrink.
INHERITED = {
    ("Jobs-channel no-op probe (args override on an existing job)", "run jobs execute"): 1,
    ("Start Cloud SQL proxy and export connection env", "secrets versions access"): 1,
    ("Trigger companyfacts resync (internal endpoint; jobs-channel fallback)", "run jobs execute"): 1,
    ("Trigger filing-history backfill (internal endpoint; jobs-channel fallback)", "run jobs execute"): 2,
    ("Run the weekly data-quality report once (P1-9; jobs channel)", "run jobs execute"): 1,
    ("Reset a single filing's summary (per-filing regen; jobs channel)", "run jobs execute"): 2,
    ("Roll service traffic back to a named revision", "run services update-traffic"): 1,
}
SPAWNERS = {"run", "call", "check_call", "check_output", "Popen", "getoutput", "getstatusoutput"}
OS_SPAWNERS = re.compile(r"system|popen|spawn\w*|exec\w*|posix_spawn\w*|fork\w*")
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


def _fakebin(tmp_path, answers=None):
    """A PATH directory holding python3 (this interpreter) and, when `answers` is given, a fake gcloud: it answers
    each exact argv from `answers` (json.dumps(argv) -> stdout/stderr/rc; "*" for any other), records every call
    and writes a sentinel to stderr on every call, success included."""
    directory = tmp_path / "bin"
    directory.mkdir()
    (directory / "python3").write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n')
    (directory / "python3").chmod(0o755)
    if answers is not None:
        (tmp_path / "fake_gcloud.py").write_text(FAKE_GCLOUD)
        (tmp_path / "answers.json").write_text(json.dumps(answers))
        (directory / "gcloud").write_text(f'#!/bin/sh\nexec "{sys.executable}" "{tmp_path / "fake_gcloud.py"}" "$@"\n')
        (directory / "gcloud").chmod(0o755)
    return directory


def _step_shell(run, tmp_path, answers=None, env=None):
    """Run a step's script as GitHub runs an unspecified shell (bash -e), with its /tmp/ files moved into tmp_path
    and only the given env; PATH holds the fake bin (no gcloud when `answers` is None) and the system tools."""
    calls = tmp_path / "calls.jsonl"
    calls.write_text("")
    bindir = _fakebin(tmp_path, answers)
    full_env = {"PATH": f"{bindir}" + ("" if answers is None else ":/usr/bin:/bin"), "HOME": str(tmp_path),
                "FAKE_GCLOUD_CALLS": str(calls), "FAKE_GCLOUD_ANSWERS": str(tmp_path / "answers.json"),
                "FAKE_GCLOUD_SENTINEL": "WARNING: PRIVATE_FAKE_GCLOUD_STDERR_SENTINEL principal@example.invalid",
                **(env or {})}
    result = subprocess.run([BASH, "-e", "-c", run.replace("/tmp/", f"{tmp_path}/")], cwd=ROOT, env=full_env,
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
    pools = {node.targets[0].id: ast.literal_eval(node.value) for node in ast.parse(JOBS_MODULE.read_text()).body
             if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)}["expected_pools"]
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


def _probe_answers(stdout, stderr, code):
    probe = ["logging", "read", 'resource.type="cloud_run_revision" AND resource.labels.service_name="earningsnerd-backend"',
             "--freshness=15m", "--limit=3", "--format=value(timestamp)"]
    conflicts = ["logging", "read", 'jsonPayload.event="company_upsert_conflict" OR textPayload:"company_upsert_conflict"',
                 "--freshness=7d", "--limit=20", "--format=json"]
    answers = {json.dumps(probe): {"stdout": stdout, "stderr": stderr, "rc": code},
               json.dumps(conflicts): {"stdout": '[{"x": 1}, {"x": 2}]', "stderr": "WARNING: " + SENTINEL},
               "*": {"stderr": "ERROR: unexpected call " + SENTINEL, "rc": 2}}
    return answers, [probe, conflicts]


def _probe(tmp_path, stdout, stderr, code):
    _, steps = _steps()
    run = steps[PROBE_STEP]["run"]
    assert run == PROBE_RUN
    # The step's own /tmp files move into this test's directory; nothing else in the script changes.
    assert run.count("/tmp/") == 8
    answers, reads = _probe_answers(stdout, stderr, code)
    result, calls = _step_shell(run, tmp_path, answers)
    assert calls == reads and result.returncode == 0 and result.stderr == ""
    assert "PRIVATE_" not in result.stdout and "example.invalid" not in result.stdout
    return result.stdout.splitlines()


def test_logs_probe_prints_permitted_reads_and_conflicts_unchanged(tmp_path):
    lines = _probe(tmp_path, "t1\nt2\nt3\n", "WARNING: " + SENTINEL, 0)
    # GNU wc (the runner) prints "3"; BSD wc (a Mac's local gate) pads the count with spaces.
    assert len(lines) == 2 and re.fullmatch(r"logs-probe: logging\.read PERMITTED \( *3 recent entries visible\)", lines[0])
    assert lines[1] == "company_upsert_conflict entries in last 7d: 2"


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
    lines = _probe(tmp_path, "", stderr, code)
    assert lines == [f"logs-probe: logging.read DENIED (rc={code})",
                     f"logs-probe: failure class {klass} (gcloud's error text withheld)",
                     "company_upsert_conflict entries in last 7d: 2"]
    assert _policy_class(monkeypatch, capsys, stderr, code) == klass


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


def test_ops_workflow_gcloud_stderr_is_discarded_or_captured_except_listed_actions():
    inherited, captured = {}, []
    calls = list(_gcloud_calls())
    _, steps = _steps()
    words = sum(len(re.findall(r"(?:^|[\s;|&!]|\$\()gcloud\s+[a-z]", "\n".join(_executable_lines(step.get("run") or "")),
                               re.M)) for step in steps.values())
    assert len(calls) == words >= 14, "the scanner must see every gcloud call in ops.yml"
    for name, group, command in calls:
        # The last stderr redirect of the command wins (`2>/dev/null 2>&1` inherits).
        targets = re.findall(r"(?<![0-9&>])2>\s*([^\s;|&)]+)", command)
        if not targets or targets[-1].startswith("&"):
            inherited[(name, group)] = inherited.get((name, group), 0) + 1
        elif targets[-1] != "/dev/null":
            captured.append((name, targets[-1]))
    assert inherited == INHERITED, "a gcloud call lets its stderr reach the job log; discard or classify it"
    assert captured == [(PROBE_STEP, "/tmp/probe.err")]
    # A file that captured stderr is only tested, never printed: every other command naming it, in any step, is
    # a grep -q.
    for _, path in captured:
        readers = [command for step in steps.values() for line in _executable_lines(step.get("run") or "")
                   for command in _commands(line) if path in command and not command.startswith("gcloud ")]
        assert readers and all(re.match(r"grep\s+-q[A-Za-z]*\s", reader) for reader in readers), readers


def test_no_ops_step_runs_an_inline_python_program():
    """Python a step runs is a committed ops/ module, so this suite loads, lints and gates it."""
    _, steps = _steps()
    inline = [name for name, step in steps.items()
              if re.search(r"\bpython3?\s+-\s*<<", step.get("run") or "")]
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
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module in ("subprocess", "os", "pty"):
                assert node.module == "os" and not any(OS_SPAWNERS.fullmatch(a.name) for a in node.names), path
            if isinstance(node, ast.Import):  # an alias would hide a call from this gate
                assert all(a.asname is None for a in node.names if a.name in ("os", "subprocess")), path
            if (isinstance(node, ast.Attribute) and node.attr == "stderr"
                    and not (isinstance(node.value, ast.Name) and node.value.id in ("sys", "subprocess"))):
                stderr_reads.append((path.relative_to(ROOT).as_posix(), owner.get(node)))
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
    assert spawns >= 2  # describe-service's gcloud seam and the readout's identity reads
    # A captured stderr is read in one place only, the seam that reduces it to a closed class.
    assert stderr_reads == [("ops/describe/service.py", "gcloud_json")], stderr_reads


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


def test_ops_python_passes_the_backend_lint_rule_set():
    """CI's ruff runs inside backend/, so it never reaches ops/; this runs the same pinned ruff and rule set here,
    and the local gate's pytest runs it too."""
    result = subprocess.run([sys.executable, "-m", "ruff", "check", "--no-cache", "--config",
                             str(ROOT / "backend/ruff.toml"), *map(str, _ops_modules())],
                            cwd=ROOT, capture_output=True, text=True, timeout=120, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
