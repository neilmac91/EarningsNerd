"""Gate for F51: the permission rules that let a session run the read-only Ops `describe-service` and
`logs-probe` dispatches and read back the Ops run list without a prompt or the auto-mode classifier
(rule 12; docs/OPERATIONS.md "Agent production readbacks (F51)").

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
operation is gated by `ops-apply`, is not exempt from the deploy pre-flight, runs any step beyond the pinned
read-only ones, or reaches gcloud other than by a read; when any allow rule admits a command in the forbidden
corpus (every other Ops operation, read from ops.yml, in the same form; the same two operations with any other
input, ref or repository; REST and GraphQL dispatches; deployment approvals and rejections; run re-runs,
cancellations and log reads; cloud writes and direct production reads; and the pinned forms chained to an apply
dispatch); when the approval guard lets an approval or rejection in the corpus through; or when
docs/OPERATIONS.md does not show each pinned command verbatim.
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

from tests.support.ops_workflow import OPS, OPTIONS, STEPS, selected
from tests.unit.test_ops_approval_guard import _decision

ROOT = Path(__file__).resolve().parents[3]
SETTINGS = ROOT / ".claude" / "settings.json"
OPERATIONS_DOC = ROOT / "docs" / "OPERATIONS.md"
SERVICE_MODULE = ROOT / "ops" / "describe" / "service.py"

# The founder-accepted F51 policy, and nothing else (tasks/todo.md F51; DECISIONS-30.md founder action 8).
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


@pytest.mark.parametrize("operation", READ_OPERATIONS)
def test_a_dispatched_operation_is_an_existing_ungated_read(operation):
    assert DISPATCH.format(operation) in COMMANDS
    assert operation in OPTIONS
    assert operation not in selected(OPS["jobs"]["approve-apply"]), "an ops-apply operation must never be allow-listed"
    assert operation not in selected(next(step for step in STEPS if step.get("name") == PREFLIGHT)), (
        "the deploy pre-flight exempts only read-only inspection")
    runs = []
    for step in STEPS:
        try:
            chosen = selected(step)
        except AssertionError:  # an if: form selected() does not read; it must not name a read operation
            assert not any(op in step["if"] for op in READ_OPERATIONS), step.get("name")
            continue
        if operation in chosen:
            runs.append(step.get("name") or step.get("uses"))
    assert runs == READ_STEPS[operation]


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


@pytest.mark.parametrize("command", APPROVALS)
def test_the_approval_guard_refuses_every_approval_and_rejection(command):
    decision = _decision("Bash", {"command": command})
    assert decision and decision["permissionDecision"] == "deny", command


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
