"""Gate for F51: the permission rules that let a session run the read-only Ops `describe-service` and
`logs-probe` dispatches and read back the Ops run list without a prompt or the auto-mode classifier, in a
session that applies this checkout's project settings (rule 12; docs/OPERATIONS.md "Agent production
readbacks (F51)", which names when that is).

The three rules are exact-match: permissions.md says "A rule with no `*` matches one exact command", so no
other operation, input, ref, repository or input channel rides on them. `admitted` models Claude Code's
matcher conservatively: it strips the documented wrappers and EVERY leading assignment (an allow rule strips
only "certain known-safe" ones, which the docs do not list), and it counts a command as allowed when each
subcommand matches a rule after splitting on the documented separators OR when the whole text matches one;
the second stands in for text the parser does not split, such as a command substitution, whose handling by
allow rules the docs do not state. Under that model a wildcard rule admits whatever it is chained to, which
is why the pinned rules carry no `*`.

The gate fails when the allow entries outside the E8 launch kit's seven are not exactly the pinned three; when
a pinned rule carries a wildcard or shell syntax; when a deny or ask rule shadows one; when a dispatched
operation is gated by `ops-apply` or is not exempt from the deploy pre-flight; when ops.yml gains a job, or a job
other than `ops` or a step of `ops` may run for a read dispatch beyond the pinned read-only steps (a condition
the gate cannot read counts as one that runs: `read_dispatch_problems`, with its evasion cases); when ops.yml,
the ops job or a read's own step gains a key, the workflow's env names, permissions or runner change, a shared
step a read runs is not its pinned shape, the resolve script runs a line outside its validation vocabulary, or a
read step hands an environment on to the steps after it; when the reads lose the concurrency group of their own
run, which keeps a read from replacing a pending run, an approved apply's included; when a read step reaches gcloud other than to read; when any allow rule admits a command in
the forbidden corpus (every other Ops operation, read from ops.yml, in the same form; the same two operations
with any other input, ref or repository; REST and GraphQL dispatches; deployment approvals and rejections; run
re-runs, cancellations and log reads; cloud writes and direct production reads; and the pinned forms chained to
an apply dispatch); when a pinned form is refused by the approval guard (which test_ops_approval_guard.py
pins for the approval and rejection calls); or when docs/OPERATIONS.md does not show each pinned command
verbatim.

Review-checked, not gated: `ops/describe/service.py`, the free-form Python every allowed describe-service runs.
test_ops_stderr_withheld.py pins its subprocess and import vocabulary and the six gcloud reads it makes, but a gate
cannot decide what a module does; a change to it changes what the no-prompt dispatch does, so it is high-tier.
"""
from __future__ import annotations

import ast
import copy
import json
import re
from pathlib import Path

import pytest

from tests.support.ops_workflow import OPS, OPTIONS, STEPS, TEMPLATE_FREE, selected
from tests.unit.test_ops_approval_guard import _decision

ROOT = Path(__file__).resolve().parents[3]
SETTINGS = ROOT / ".claude" / "settings.json"
OPERATIONS_DOC = ROOT / "docs" / "OPERATIONS.md"
SERVICE_MODULE = ROOT / "ops" / "describe" / "service.py"

# The F51 policy and nothing else: proposed as founder action 8 in DECISIONS-30.md for the two dispatches, accepted
# in the Wave 3 planning (Agent E brief, F51: "the existing read-only describe-service and logs-probe workflow
# dispatch/readback forms"); the third rule reads GitHub's run metadata only.
OPS_READBACK_ALLOW_RULES = (
    "Bash(gh workflow run ops.yml -R neilmac91/EarningsNerd --ref main -f operation=describe-service)",
    "Bash(gh workflow run ops.yml -R neilmac91/EarningsNerd --ref main -f operation=logs-probe)",
    "Bash(gh run list -R neilmac91/EarningsNerd --workflow ops.yml --branch main --event workflow_dispatch"
    " -L 5 --json databaseId,status,conclusion,createdAt,headSha)",
)
COMMANDS = tuple(rule[len("Bash("):-1] for rule in OPS_READBACK_ALLOW_RULES)
DISPATCH = "gh workflow run ops.yml -R neilmac91/EarningsNerd --ref main -f operation={}"
READ_OPERATIONS = ("describe-service", "logs-probe")
# Every step a read dispatch runs; a step added for either operation is a change to what the rule approves.
SHARED_STEPS = ["actions/checkout@v7", "Resolve requested operation", "Authenticate to Google Cloud", "Set up gcloud"]
READ_STEPS = {
    "describe-service": SHARED_STEPS + ["Describe service env (values only for known feature flags)"],
    "logs-probe": SHARED_STEPS + ["Logs read probe (safeguard-2 alert feasibility)"],
}
PREFLIGHT = "Refuse to run while a main push (deploy) is in flight"
JOBS = {"approve-apply", "ops", "refuse-rerun"}
# Each read dispatch runs in a group of its own run, so it never replaces, nor waits behind, a pending run.
READ_GROUP = ("${{ (" + " || ".join(f"inputs.operation == '{operation}'" for operation in READ_OPERATIONS)
              + ") && format('ops-read-{0}', github.run_id) || 'ops' }}")
# What each shared step a read runs is, whole, so a write cannot ride inside one under its name. A new version of
# one of these actions (a Dependabot bump) fails here until someone checks it still only reads and updates this.
SHARED_SHAPES = {
    "actions/checkout@v7": {"uses": "actions/checkout@v7", "with": {"persist-credentials": "false"}},
    "Authenticate to Google Cloud": {
        "name": "Authenticate to Google Cloud", "uses": "google-github-actions/auth@v3",
        "with": {"workload_identity_provider": "${{ vars.GCP_WIF_PROVIDER }}", "service_account": "${{ vars.GCP_DEPLOYER_SA }}"}},
    "Set up gcloud": {"name": "Set up gcloud", "uses": "google-github-actions/setup-gcloud@v3"},
}
# The resolve step's whole vocabulary: it validates the three inputs and writes $GITHUB_OUTPUT, nothing else. Every
# line of its script must be one of these forms (a new operation's case label needs no change here); anything else (a
# command, a sourced file, an expansion that builds a name) fails until someone checks it and teaches this list.
_ERROR = r'echo "::error::[^"$`\\]*(?:\$(?:OP|TICKERS|REVISION)[^"$`\\]*)*"'
_INPUT = r'"\$(?:TICKERS|REVISION)"'
RESOLVE_LINES = [re.compile(form) for form in (
    r"", r"#.*", r"set -euo pipefail", r'case "\$OP" in', r"esac", r";;", r"fi", r"\{",
    r"[a-z0-9-]+(?:\|[a-z0-9-]+)*\)(?: ;;)?",
    rf"\*\) {_ERROR}; exit 1 ;;",
    rf"\[\[ {_INPUT} =~ \^[^\s$`]+\$ \]\] \\",
    rf"\|\| \{{ {_ERROR}; exit 1; \}}",
    r"""COUNT=\$\(echo "\$TICKERS" \| tr ',' '\\n' \| wc -l\)""",
    rf'\[ "\$COUNT" -le \d+ \] \|\| \{{ {_ERROR}; exit 1; \}}',
    r'if \[ -n "\$TICKERS" \]; then',
    r'echo "(?:operation=\$OP|tickers=\$TICKERS|revision=\$REVISION|Requested operation: \$OP)"',
    r'\} >> "\$GITHUB_OUTPUT"',
)]
# What every read inherits, pinned whole: a new key (an env, `defaults`, a `container`), another env name (HOME,
# NODE_OPTIONS), another runner or a wider token changes every step. After checking a change only reads, update these.
WORKFLOW_KEYS = {"name", "on", "permissions", "env", "jobs"}
WORKFLOW_ENV = {"REGION", "SERVICE", "JOBS_CHANNEL_JOB", "CLOUD_SQL_PROXY_VERSION", "CLOUD_SQL_PROXY_SHA256"}
WORKFLOW_PERMISSIONS = {"contents": "read", "actions": "read", "id-token": "write"}
OPS_JOB_KEYS = {"needs", "if", "concurrency", "runs-on", "steps"}
RUNNER = "ubuntu-latest"
LAST_STEP_KEYS = {"describe-service": {"name", "if", "timeout-minutes", "run"}, "logs-probe": {"name", "if", "run"}}
# A step a read runs may not change the environment of the steps after it (only the proxy step does, for writes).
ENV_WRITES = re.compile(r"GITHUB_ENV|GITHUB_PATH|BASH_ENV")
# A condition on an earlier step's result that is false when that step was skipped.
UNRUN_OUTCOME = re.compile(r"steps\.([\w-]+)\.(?:outcome|conclusion) (?:!= 'skipped'|== '(?:success|failure|cancelled)')")

# Claude Code's matcher (permissions.md "Wildcard patterns", "Compound commands", "Wrappers"), read conservatively.
SEPARATORS = re.compile(r"&&|\|\||\|&|;|\||&|\n")
WRAPPER = re.compile(r"^(?:timeout(?:\s+-\S+)*\s+\S+|time|nice(?:\s+-n)?(?:\s+-?\d+)?|nohup|stdbuf(?:\s+-\S+)+"
                     r"|command|builtin|noglob|xargs)\s+")
ASSIGNMENT = re.compile(r"""^[A-Za-z_]\w*=(?:'[^']*'|"[^"]*"|\S)*\s+""")
SHELL_SYNTAX = ("*", "$", "`", ";", "&", "|", "<", ">", "(", ")", "'", '"', "\\", "\n")


def _rule_regex(pattern: str) -> re.Pattern[str]:
    if pattern.endswith((":*", " *")):
        body = pattern[:-2]
        if "*" in body:
            return re.compile(".*".join(re.escape(part) for part in body.split("*")) + r" .*", re.DOTALL)
        return re.compile(re.escape(body) + r"(?: .*)?", re.DOTALL)
    return re.compile(".*".join(re.escape(part) for part in pattern.split("*")), re.DOTALL)


def _strip(text: str) -> str:
    text = " ".join(text.split()).strip("(){} ")
    while (stripped := ASSIGNMENT.sub("", WRAPPER.sub("", text, count=1), count=1)) != text:
        text = stripped.strip()
    return text


def admitted(command: str, entries: list[str]) -> bool:
    """True when any reading of Claude Code's documented matcher could let an allow entry approve the command."""
    matchers = [_rule_regex(m.group(1)) for entry in entries if (m := re.fullmatch(r"Bash\((.+)\)", entry, re.DOTALL))]

    def matches(text: str) -> bool:
        return any(matcher.fullmatch(_strip(text)) for matcher in matchers)

    parts = [part for part in SEPARATORS.split(command) if _strip(part)]
    return matches(command) or (bool(parts) and all(matches(part) for part in parts))


def _settings() -> dict:
    return json.loads(SETTINGS.read_text(encoding="utf-8"))


def _allow() -> list[str]:
    return _settings()["permissions"]["allow"]


def test_the_allow_entries_beyond_the_launch_kit_are_exactly_the_pinned_ops_rules():
    from tests.unit.test_e8_launch_kit_matches_allow_rules import EXPECTED_ALLOW_RULES

    allow = _allow()
    assert len(allow) == len(set(allow)), "an allow entry is listed twice"
    assert [entry for entry in allow if entry not in EXPECTED_ALLOW_RULES] == list(OPS_READBACK_ALLOW_RULES)


def test_each_pinned_rule_is_one_exact_command():
    for command in COMMANDS:
        assert not any(token in command for token in SHELL_SYNTAX), command
        assert command.startswith(("gh workflow run ops.yml ", "gh run list ")), command


def test_no_deny_or_ask_rule_shadows_a_pinned_command():
    permissions = _settings()["permissions"]
    blocked = permissions.get("deny", []) + permissions.get("ask", [])
    assert "Bash" not in blocked and "Bash(*)" not in blocked
    assert [command for command in COMMANDS if admitted(command, blocked)] == []


def _conjuncts(condition: str) -> list[str] | None:
    """The top-level `&&` terms of an `if:`, or None when a top-level `||` makes no single term decisive."""
    if "${{" in condition and not TEMPLATE_FREE.fullmatch(condition):
        return None  # text around ${{ }}: GitHub reads the whole value as a string template, always true
    body = re.sub(r"^\$\{\{\s*(.*?)\s*\}\}$", r"\1", condition.strip(), flags=re.DOTALL)
    terms, depth, quoted, start = [], 0, False, 0
    for at, char in enumerate(body):
        if char == "'":
            quoted = not quoted
        elif quoted:
            continue
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif depth == 0 and body.startswith("||", at):
            return None
        elif depth == 0 and body.startswith("&&", at):
            terms.append(body[start:at].strip())
            start = at + 2
    return terms + [body[start:].strip()]


def _never_runs_for_a_read(condition: str, unrun: set[str], operand: str) -> bool:
    """True only when one top-level term of the condition is false for both read operations: it names another
    operation, lists operations that include neither read, or needs an earlier step that a read skipped."""
    for term in _conjuncts(condition) or []:
        if (match := re.fullmatch(rf"{operand} == '([^']*)'", term)) and match.group(1).lower() not in READ_OPERATIONS:
            return True
        if (match := re.fullmatch(rf"contains\('([^']*)', {operand}\)", term)) and not any(
                operation in match.group(1).lower() for operation in READ_OPERATIONS):
            return True
        if (match := UNRUN_OUTCOME.fullmatch(term)) and match.group(1) in unrun:
            return True
    return False


def read_dispatch_problems(workflow: dict) -> list[str]:
    """Every way a read dispatch could run more than the pinned read-only steps: another job, another step, a
    condition this gate cannot read (counted as one that runs), a shared step that is not its pinned shape, an
    environment a step inherits or hands on; and the reads' own concurrency group."""
    jobs, problems = workflow["jobs"], []
    if set(workflow) != WORKFLOW_KEYS:
        problems.append(f"ops.yml's top-level keys changed: {sorted(set(workflow) ^ WORKFLOW_KEYS)}")
    if set(workflow.get("env", {})) != WORKFLOW_ENV:
        problems.append(f"ops.yml's env names changed ({sorted(set(workflow.get('env', {})) ^ WORKFLOW_ENV)}): after "
                        "checking every read step still only reads, update WORKFLOW_ENV")
    if workflow.get("permissions") != WORKFLOW_PERMISSIONS:
        problems.append(f"ops.yml's token permissions changed: {workflow.get('permissions')}")
    if set(jobs) != JOBS:
        problems.append(f"ops.yml's jobs changed ({sorted(set(jobs) ^ JOBS)}): pin what a read dispatch runs in them")
    for name, job in jobs.items():
        if name != "ops" and not _never_runs_for_a_read(job.get("if", ""), set(), r"inputs\.operation"):
            problems.append(f"job {name!r} may run for a read dispatch")
    ops = jobs.get("ops", {})
    if set(ops) != OPS_JOB_KEYS:
        problems.append(f"the ops job's keys changed: {sorted(set(ops) ^ OPS_JOB_KEYS)}")
    if ops.get("runs-on") != RUNNER:
        problems.append(f"the ops job runs on {ops.get('runs-on')!r}, not {RUNNER!r}: every read would run there")
    if ops.get("concurrency") != {"group": READ_GROUP, "cancel-in-progress": "false"}:
        problems.append("the ops job no longer gives each read dispatch a concurrency group of its own run")
    read_steps = {}  # id() of each step a read runs -> the step, in order
    for operation in READ_OPERATIONS:
        runs, unrun = [], set()
        for step in ops.get("steps", []):
            label = step.get("name") or step.get("uses")
            try:
                runs_here = operation in selected(step)
            except AssertionError:  # a form selected() does not read: it must be decisively false for a read
                runs_here = not _never_runs_for_a_read(step["if"], unrun, r"steps\.request\.outputs\.operation")
                if runs_here:
                    problems.append(f"{label!r} may run for {operation}: its if: is not one the gate can read")
                    continue
            if runs_here:
                runs.append(label)
                read_steps[id(step)] = step
            elif step.get("id"):
                unrun.add(step["id"])
        if runs != READ_STEPS[operation]:
            problems.append(f"{operation} runs {runs}, not the pinned read-only steps {READ_STEPS[operation]}")
        last = next((step for step in ops.get("steps", []) if step.get("name") == READ_STEPS[operation][-1]), {})
        if set(last) != LAST_STEP_KEYS[operation]:
            problems.append(f"{operation}'s own step's keys changed: {sorted(set(last) ^ LAST_STEP_KEYS[operation])}")
    for step in read_steps.values():
        label = step.get("name") or step.get("uses")
        if label in SHARED_SHAPES and step != SHARED_SHAPES[label]:
            problems.append(f"{label!r} is not its pinned shape; after checking the new form only reads, update "
                            f"SHARED_SHAPES: {step}")
        if label == "Resolve requested operation":
            if set(step) != {"name", "id", "env", "run"}:
                problems.append(f"the resolve step's keys changed: {sorted(set(step) ^ {'name', 'id', 'env', 'run'})}")
            outside = [line.strip() for line in step.get("run", "").splitlines()
                       if not any(form.fullmatch(line.strip()) for form in RESOLVE_LINES)]
            if outside:
                problems.append(f"the resolve script runs lines outside its validation vocabulary: {outside}; after "
                                "checking they only validate the inputs, teach RESOLVE_LINES")
        if writes := ENV_WRITES.search(step.get("run", "")):
            problems.append(f"{label!r} writes {writes.group()}, which reaches the steps after it")
    return problems


@pytest.mark.parametrize("operation", READ_OPERATIONS)
def test_a_dispatched_operation_is_an_existing_ungated_read(operation):
    assert DISPATCH.format(operation) in COMMANDS
    assert operation in OPTIONS
    assert operation not in selected(OPS["jobs"]["approve-apply"]), "an ops-apply operation must never be allow-listed"
    assert operation not in selected(next(step for step in STEPS if step.get("name") == PREFLIGHT)), (
        "the deploy pre-flight exempts only read-only inspection")


def test_a_read_dispatch_runs_only_the_pinned_steps_in_its_own_group():
    assert read_dispatch_problems(OPS) == []


WRITE = "gcloud run services update-traffic earningsnerd-backend --region=us-west1 --to-latest 2>/dev/null"


def _step_before_the_read(condition: str | None):
    def mutate(workflow: dict) -> None:
        steps = workflow["jobs"]["ops"]["steps"]
        at = next(index for index, step in enumerate(steps) if step.get("name") == READ_STEPS["describe-service"][-1])
        steps.insert(at, {"name": "Pin traffic", "run": WRITE, **({"if": condition} if condition is not None else {})})
    return mutate


def _step_named(workflow: dict, name: str) -> dict:
    return next(step for step in workflow["jobs"]["ops"]["steps"] if step.get("name") == name)


def _append_to_resolve(workflow: dict, line: str) -> None:
    step = _step_named(workflow, "Resolve requested operation")
    step["run"] = step["run"].rstrip("\n") + "\n" + line + "\n"


EVASIONS = {  # each change would put a production write, or a replacement, into every allowed read dispatch
    "a step with no condition": _step_before_the_read(None),
    "a step that always runs": _step_before_the_read("always()"),
    "a step that runs unless another operation": _step_before_the_read("steps.request.outputs.operation != 'rollback-traffic'"),
    "a step whose || reopens it": _step_before_the_read("steps.request.outputs.operation == 'sync-companyfacts' || always()"),
    "a step that lists a read": _step_before_the_read("contains('describe-service rollback-traffic', steps.request.outputs.operation)"),
    "a step after a skipped step's skip": _step_before_the_read("always() && steps.quarterly.outcome == 'skipped'"),
    "a step on a step that ran": _step_before_the_read("always() && steps.request.outcome == 'success'"),
    "a step on a later step's outcome": _step_before_the_read("always() && steps.quarterly.outcome != 'skipped'"),
    "text before the expression": _step_before_the_read("${{ always() }} && steps.request.outputs.operation == 'rollback-traffic'"),
    "a block scalar's newline": _step_before_the_read("${{ steps.request.outputs.operation == 'rollback-traffic' }}\n"),
    "a leading space": _step_before_the_read(" ${{ steps.request.outputs.operation == 'rollback-traffic' }}"),
    "a write in the gcloud set-up step": lambda workflow: workflow["jobs"]["ops"]["steps"].__setitem__(
        next(index for index, step in enumerate(workflow["jobs"]["ops"]["steps"]) if step.get("name") == "Set up gcloud"),
        {"name": "Set up gcloud", "run": WRITE}),
    "the resolve step reaching the cloud": lambda workflow: next(
        step for step in workflow["jobs"]["ops"]["steps"] if step.get("name") == "Resolve requested operation"
    ).update(run="gcloud auth print-access-token >/dev/null 2>&1\n" + next(
        step for step in workflow["jobs"]["ops"]["steps"] if step.get("name") == "Resolve requested operation")["run"]),
    "BASH_ENV handed on from the resolve step": lambda workflow: _append_to_resolve(
        workflow, "printf 'BASH_ENV=%s\\n' \"${GITHUB_WORKSPACE:-.}/ops/describe/env.sh\" >> \"${GITHUB_ENV:-/dev/null}\""),
    "a PATH handed on from the resolve step": lambda workflow: _append_to_resolve(
        workflow, 'echo "$GITHUB_WORKSPACE/ops/bin" >> "$GITHUB_PATH"'),
    "BASH_ENV on the describe step": lambda workflow: _step_named(workflow, READ_STEPS["describe-service"][-1]).update(
        env={"BASH_ENV": "ops/describe/env.sh"}),
    "an env on the ops job": lambda workflow: workflow["jobs"]["ops"].update(env={"BASH_ENV": "ops/describe/env.sh"}),
    "a default shell on the ops job": lambda workflow: workflow["jobs"]["ops"].update(
        defaults={"run": {"shell": "bash --rcfile ops/describe/env.sh {0}"}}),
    "a loader in the workflow's env": lambda workflow: workflow["env"].update(BASH_ENV="ops/describe/env.sh"),
    "a container for the ops job": lambda workflow: workflow["jobs"]["ops"].update(container="ghcr.io/example/ops:1"),
    "another name in the workflow's env": lambda workflow: workflow["env"].update(NODE_OPTIONS="--require ./x.js"),
    "a self-hosted runner": lambda workflow: workflow["jobs"]["ops"].update({"runs-on": "self-hosted"}),
    "a wider token": lambda workflow: workflow["permissions"].update(contents="write"),
    "a script the resolve step runs": lambda workflow: _append_to_resolve(workflow, "bash ops/request/placeholder.sh"),
    "a name the resolve step builds": lambda workflow: _append_to_resolve(workflow, 'v=GITHUB_; v+=ENV; : "${!v:-/dev/null}"'),
    "a command inside an input check": lambda workflow: _append_to_resolve(
        workflow, '[[ "$TICKERS" =~ ^$(id)$ ]] \\'),
    "a command after an error exit": lambda workflow: _append_to_resolve(
        workflow, '|| { echo "::error::bad"; exit 1; }; source ops/x.sh'),
    "an apply added to the reads' group": lambda workflow: workflow["jobs"]["ops"]["concurrency"].update(
        {"group": READ_GROUP.replace("inputs.operation == 'logs-probe')",
                                     "inputs.operation == 'logs-probe' || inputs.operation == 'relabel-fy-apply')")}),
    "a new job after ops": lambda workflow: workflow["jobs"].update({"post-read": {
        "needs": "ops", "if": "github.ref == 'refs/heads/main'", "runs-on": "ubuntu-latest", "steps": [{"run": WRITE}]}}),
    "the approval job opened to every operation": lambda workflow: workflow["jobs"]["approve-apply"].update(
        {"if": "github.ref == 'refs/heads/main'"}),
    "the reads back in the shared group": lambda workflow: workflow["jobs"]["ops"].update(
        {"concurrency": {"group": "ops", "cancel-in-progress": "false"}}),
}


@pytest.mark.parametrize("case", EVASIONS)
def test_the_read_dispatch_gate_catches_each_evasion(case):
    workflow = copy.deepcopy(OPS)
    EVASIONS[case](workflow)
    assert read_dispatch_problems(workflow), case


def test_the_read_steps_reach_gcloud_only_to_read():
    by_name = {step.get("name"): step for step in STEPS}
    assert by_name[READ_STEPS["describe-service"][-1]]["run"].strip() == "python3 ops/describe/service.py"
    probe = by_name[READ_STEPS["logs-probe"][-1]]["run"]
    calls = re.findall(r"(?m)^\s*(?:if\s+)?gcloud\s+(\S+\s+\S+)", probe)  # each command line that runs gcloud
    assert calls and set(calls) == {"logging read"}, calls
    tree = ast.parse(SERVICE_MODULE.read_text(encoding="utf-8"))
    verbs = [call.args[0].elts[1].value for call in ast.walk(tree)
             if isinstance(call, ast.Call) and getattr(call.func, "id", None) == "gcloud_json"]
    assert verbs and set(verbs) <= {"describe", "get-iam-policy"}, verbs
    seams = [node for node in ast.walk(tree) if isinstance(node, ast.Attribute) and getattr(node.value, "id", None) == "subprocess"
             and node.attr not in {"PIPE", "TimeoutExpired", "CalledProcessError"}]
    assert [node.attr for node in seams] == ["check_output"], "describe-service reaches gcloud only through gcloud_json"


APPLY = DISPATCH.format("relabel-fy-apply")
RUNS = "repos/neilmac91/EarningsNerd/actions/runs/40079338662"
APPROVALS = [
    f"gh api -X POST {RUNS}/pending_deployments -F 'environment_ids[]=1' -f state=approved -f comment=ok",
    f"gh api -X POST {RUNS}/pending_deployments -F 'environment_ids[]=1' -f state=rejected -f comment=no",
    f"gh api -X POST {RUNS}/deployment_protection_rule -f environment_name=ops-apply -f state=approved",
    "gh api graphql -f query='mutation { approveDeployments(input: {workflowRunId: \"R\", environmentIds: [\"E\"]})"
    " { clientMutationId } }'",
    "gh api graphql -f query='mutation { rejectDeployments(input: {workflowRunId: \"R\", environmentIds: [\"E\"]})"
    " { clientMutationId } }'",
    "gh api -X PUT repos/neilmac91/EarningsNerd/environments/ops-apply -F 'reviewers[][id]=1'",
    "gh api -X DELETE repos/neilmac91/EarningsNerd/environments/ops-apply",
]
FORBIDDEN = [
    *(DISPATCH.format(op) for op in OPTIONS if op not in READ_OPERATIONS),
    DISPATCH.format("describe-service") + " -f revision=earningsnerd-backend-00001-abc",
    DISPATCH.format("logs-probe") + " -f tickers=AAPL",
    DISPATCH.format("describe-service") + " -f operation=relabel-fy-apply",  # the last -f wins
    "gh workflow run ops.yml -R neilmac91/EarningsNerd --ref other -f operation=describe-service",
    "gh workflow run ops.yml -R neilmac91/EarningsNerd --ref main -F operation=@operation.txt",
    "gh workflow run ops.yml -R neilmac91/EarningsNerd --ref main --json",
    "gh workflow run ops.yml -R neilmac91/EarningsNerd --ref main",
    "gh workflow run ops.yml --ref main -f operation=describe-service",
    "gh workflow run ops.yml -R someone/EarningsNerd --ref main -f operation=describe-service",
    "gh workflow run Ops -R neilmac91/EarningsNerd --ref main -f operation=relabel-fy-apply",
    "gh workflow run ci.yml -R neilmac91/EarningsNerd --ref main",
    "gh api -X POST repos/neilmac91/EarningsNerd/actions/workflows/ops.yml/dispatches -f ref=main"
    " -f 'inputs[operation]=relabel-fy-apply'",
    *APPROVALS,
    "gh run rerun 40079338662 -R neilmac91/EarningsNerd",
    "gh run cancel 40079338662 -R neilmac91/EarningsNerd",
    "gh run delete 40079338662 -R neilmac91/EarningsNerd",
    "gh run view 40079338662 -R neilmac91/EarningsNerd --log",  # the log read stays with the classifier
    COMMANDS[2] + " -R someone/EarningsNerd",
    COMMANDS[2].replace("-L 5", "-L 500"),
    "gcloud run services update-traffic earningsnerd-backend --region=us-west1 --to-revisions=r=100",
    "gcloud run services update earningsnerd-backend --region=us-west1 --update-env-vars=X=1",
    "gcloud run jobs execute earningsnerd-backfill-facts --region=us-west1",
    "gcloud run services describe earningsnerd-backend --region=us-west1",
    "gcloud logging read 'resource.type=\"cloud_run_revision\"' --limit=3",
    "python3 ops/describe/service.py",
    *(f"{command} {separator} {APPLY}" for command in COMMANDS for separator in ("&&", "||", ";", "|", "|&", "&", "\n")),
    *(f"{APPLY} && {command}" for command in COMMANDS),
    *(f"{command} $({APPLY})" for command in COMMANDS),
    *(f"{command} `{APPLY}`" for command in COMMANDS),
    f"timeout 30 {APPLY}",
    f"GH_REPO=neilmac91/EarningsNerd {APPLY}",
    f"bash -c '{COMMANDS[0]}; {APPLY}'",
]


@pytest.mark.parametrize("command", FORBIDDEN)
def test_no_allow_rule_admits_a_forbidden_command(command):
    assert not admitted(command, _allow()), f"an allow rule in .claude/settings.json admits: {command!r}"


@pytest.mark.parametrize("command", [*COMMANDS, *(f"timeout 60 {c}" for c in COMMANDS), f"nohup {COMMANDS[0]}"])
def test_the_pinned_forms_are_admitted_and_pass_the_guard(command):
    assert admitted(command, _allow())
    assert _decision("Bash", {"command": command}) is None


MATCHER_SEMANTICS = [  # permissions.md rows, plus the conservative reading of a wildcard rule
    ("Bash(npm run build)", "npm run build", True),
    ("Bash(npm run build)", "npm run build --watch", False),
    ("Bash(ls *)", "ls", True),
    ("Bash(ls *)", "lsof", False),
    ("Bash(ls*)", "lsof", True),
    ("Bash(npm test *)", "timeout 30 npm test", True),
    ("Bash(npm test *)", "NODE_ENV=test npm test", True),
    ("Bash(npm run build)", "npm run build && rm -rf x", False),
    ("Bash(npm run *)", "npm run build $(rm -rf x)", True),
    ("Bash(npm run *)", "npm run build && rm -rf x", True),
]


@pytest.mark.parametrize(("rule", "command", "expected"), MATCHER_SEMANTICS)
def test_the_matcher_is_documented_or_more_permissive(rule, command, expected):
    assert admitted(command, [rule]) is expected


def test_the_operations_doc_shows_each_pinned_command():
    text = OPERATIONS_DOC.read_text(encoding="utf-8")
    assert "### Agent production readbacks (F51)" in text
    assert [command for command in COMMANDS if f"\n{command}\n" not in text] == []
