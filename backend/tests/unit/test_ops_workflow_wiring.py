"""Gate for how `.github/workflows/ops.yml` wires its production steps, read from the workflow itself.

Ops runs committed SQL and scripts against production through a Cloud SQL proxy. Its steps are
chosen by `if:` conditions and fed through `inputs.*` and `steps.request.outputs.*`. A slip there
fails silently:
- An input or output name GitHub cannot find evaluates to '' with no error. `outputs.ticker` for
  `tickers`, or `inputs.ticker` one hop earlier, would turn a relabel of one company into a relabel
  of every company.
- An `if:` that misses the proxy step leaves a script with no `DATABASE_URL`.

So every step whose text runs `psql` or a committed script (`python` or `bash` with a `scripts/`
path, wherever it sits on the line) runs only for operations the proxy also runs for, and after it;
a script also needs the dependency install before it, and the file committed. This reads text, so a
database client it cannot name (`pg_dump`, a Python one-liner) is outside it. The step exempt as
opening no session (`NO_DATABASE`) runs no database command, and the proxy starts for no operation
that no Cloud SQL step uses. Every Cloud SQL step's lock and statement bounds are gated once, in
`test_migration_lock_safety.py::test_ops_workflow_is_dispatch_only_and_sets_lock_timeout`, through
the same readers (`tests/support/ops_workflow.py`).

The fiscal-year relabel step, the quarterly fact repair step and the lineage backfill step each run
for exactly their two operations, with no `continue-on-error`, and any other operation would get a
read-only dry run or preview. The quarterly and lineage steps' `if:` is pinned as written, since
`selected()` reads past a leading `always()`, which would run the step after a failed approval check.
Each step compares the settings its session reports with its own guards before its script runs. Whenever the quarterly repair step
ran, the step after it keeps the report file the script wrote as an artifact. A batch the script
refuses as a whole, or a run stopped before its report, writes no file; its log then holds the
error, or the script's start line, which names the run. E264's financial revenue preview step runs for
its one operation, as written, with its keys and its env pinned whole. It only reads, through its fixed
PGOPTIONS alone, and the step after it keeps its report whenever it ran. The script's own time budget
ends inside the step's timeout, so a run ends with its summary and its report. Those guards and the read-only transactions
reach the database only through libpq's `PGOPTIONS`. An `options` setting in the app engine's
`connect_args`, a query on the URL the proxy step exports or on the URL the app builds from it, a
connection-level SQLAlchemy event that could `SET` them again, or a `SET` of a guard in any committed
file a Cloud SQL step runs through python, bash or sh (each read from its step's command, not named by
hand; a module, inline code, a file run with no interpreter and a path held in a variable are out of
reach, each planted in `STEP_SCRIPT_CASES`) or in the modules that run the quarterly repair's or the lineage backfill's SQL
would replace them, so none may exist.
The one connection-level event allowed is database.py's `connect` listener that runs each session
at UTC (E151), held by running it on a recording connection: it sets the time zone and touches
nothing else, no other statement, attribute or method.

Every -apply operation waits for the founder's approval: an approval job in the `ops-apply`
environment, whose required reviewer is the founder, runs for exactly those operations. The
operations job runs an -apply only once that job has passed, and only in the run's first attempt,
and runs every other operation when that job is skipped. Before the cloud sign-in, and after the
resolve step names the operation, an apply stops unless the run records an approval of `ops-apply`
(what that step does is run in `test_workflow_dispatch_inputs.py`). A re-run of an apply fails in its
own job rather than reading green. The operations job keeps no environment, so its OIDC subject is
unchanged, and the `ops` concurrency group is its own, so a wait for approval holds up no other
dispatch; the two read operations a session may dispatch take a group of their own run (F51).

`inputs[...]` and `outputs[...]` index syntax, which these checks would not see, is refused.

Every name an expression gives the operation is a dispatch option (E257): a contains() list's words,
and an `==` or `!=` name either way round, in a job's or a step's `if:` or in any other `${{ }}`.
`selected()` reads a word no dispatch offers as selecting nothing, so an operation retired or renamed in
the dispatch but left in a list, or misspelled there, would pass every gate that reads its step
through it. Every other literal in an expression that reads the operation is one of
`NOT_AN_OPERATION`, each of them in use, so a form the check does not read (a list `fromJSON()`
parses, a `startsWith()` prefix) fails it too. Out of reach, each planted in `STALE_NAME_CASES` as a
gap: the operation read under another name (an `env.` value), a list an expression reads from outside
itself, and a shell test of `$OP` in a run script.
"""
import ast
import copy
import importlib
import os
import re
import subprocess
from pathlib import Path

import pytest

from tests.support.ops_workflow import (
    BASELINE, BY_NAME, DEPS, INPUTS, LINEAGE, NO_DATABASE, OPS, OPS_TEXT, OPTIONS, PREVIEW, PROXY, QUARTERLY, RELABEL,
    RESOLVE, ROOT, STEPS, cloud_sql_reach, pg_settings, selected, setting_ms, shown,
)

DB_COMMAND = re.compile(
    r"\bpsql\b|(?:\bpython3?|\bbash|\bsh)\s+(?:-\S+\s+)*\S*\bscripts/"
    r"|\bpython3?\s+ops/summary_readout/readout\.py\b"
)
RUNNER_SCRIPT = re.compile(r"(?:\bpython3?|\bbash|\bsh)\s+(?:-\S+\s+)*(\S*\bscripts/[\w./-]+\.(?:py|sh))")
# Any file a step runs through an interpreter, wherever it lives: what the listener scan reads. RUNNER_SCRIPT
# reads only the scripts that also need the dependency install and the SEC budgets.
STEP_SCRIPT = re.compile(r"(?:\bpython3?|\bbash|\bsh)\s+(?:-\S+\s+)*(\S+\.(?:py|sh))\b")
CONNECTION_EVENTS = {"do_connect", "connect", "first_connect", "checkout", "engine_connect", "begin", "after_begin"}
# The one connection-level listener allowed: database.py's UTC pin (E151), on `connect`, by this name.
UTC_PIN = ("backend/app/database.py", "connect", "_set_session_time_zone_utc")
OPERATION_READ = re.compile(r"\b(?:inputs|outputs)\.operation\b")  # the dispatch input however reached, or a step's output
LITERAL = re.compile(r"'((?:[^']|'')*)'")  # GitHub writes a quote inside a literal as two
# The literals beside the operation's names that name no operation: the main ref, the approval job's two
# results and the first attempt, the read group's format and the shared group's name, and the
# verification output's glob with the empty string its hashFiles() is compared with.
NOT_AN_OPERATION = {"refs/heads/main", "skipped", "success", "1", "ops-read-{0}", "ops", "verification-output/*", ""}


def test_dispatch_options_are_exactly_the_operations_the_resolve_step_accepts():
    run = BY_NAME[RESOLVE][1]["run"]
    accepted = re.search(r'case "\$OP" in\s+([a-z0-9|-]+)\) ;;', run).group(1).split("|")
    assert sorted(accepted) == sorted(OPTIONS)


def test_every_input_a_step_reads_is_declared_and_reaches_the_resolve_step_under_its_own_name():
    assert not re.search(r"\b(?:inputs|outputs)\s*\[", OPS_TEXT), "read inputs and outputs as .name, which these checks see"
    read = set(re.findall(r"\b(?:github\.event\.)?inputs\.(\w+)", OPS_TEXT))
    assert read <= set(INPUTS), f"inputs no dispatch declares, which GitHub reads as '': {sorted(read - set(INPUTS))}"
    assert BY_NAME[RESOLVE][1]["env"] == {
        "OP": "${{ inputs.operation }}", "TICKERS": "${{ inputs.tickers }}", "REVISION": "${{ inputs.revision }}"}


def test_every_request_output_a_step_reads_is_one_the_resolve_step_writes():
    written = set(re.findall(r'echo "(\w+)=\$', BY_NAME[RESOLVE][1]["run"]))
    assert written == {"operation", "tickers", "revision"}
    read = set(re.findall(r"steps\.request\.outputs\.(\w+)", OPS_TEXT))
    assert read <= written, f"outputs no step writes, which GitHub reads as '': {sorted(read - written)}"


def _expressions(node, key=None) -> list[str]:
    """Each expression in a workflow as GitHub reads it: every `if:`, which is one with or without
    `${{ }}`, and every `${{ }}` in any other value (a concurrency group, an env value, a run script)."""
    if isinstance(node, dict):
        return [found for name, value in node.items() for found in _expressions(value, name)]
    if isinstance(node, list):
        return [found for item in node for found in _expressions(item, key)]
    return [node] if key == "if" else re.findall(r"\$\{\{(.*?)\}\}", node, re.DOTALL)


def _beside_the_operation(workflow) -> list[str]:
    """Each literal in the workflow's expressions that read the operation, lowercased, as GitHub
    compares strings."""
    return [literal.lower() for expression in _expressions(workflow) if OPERATION_READ.search(expression)
            for literal in LITERAL.findall(expression)]


def _names_no_dispatch_offers(workflow) -> set[str]:
    """Each word of a literal beside the operation that the workflow's dispatch does not offer, in every
    literal but NOT_AN_OPERATION's; an empty literal outside them reads as itself."""
    options = set(workflow["on"]["workflow_dispatch"]["inputs"]["operation"]["options"])
    return {word for literal in _beside_the_operation(workflow) if literal not in NOT_AN_OPERATION
            for word in literal.split() or [literal] if word not in options}


def _lists_options(literal: str, options) -> bool:
    """Whether a literal is one or more dispatch options, as a contains() list or an == name."""
    return bool(literal.split()) and set(literal.split()) <= set(options)


def _planted_step(condition: str, **more):
    """A planted step right after the resolve step, with this `if:`."""
    return lambda workflow: workflow["jobs"]["ops"]["steps"].insert(
        2, {"name": "Planted", "if": condition, "run": "true", **more})


STALE = "figure-check-count"  # an operation the dispatch offered until #1857 retired it
STALE_NAME_CASES = {  # each planted change, and the words the check flags in it
    "an operation retired from the dispatch and left in every list that names it": (
        lambda workflow: workflow["on"]["workflow_dispatch"]["inputs"]["operation"]["options"].remove(
            "repair-lineage-apply"), {"repair-lineage-apply"}),
    "a misspelled word in a step's list": (_planted_step(
        "contains('repair-quarterly-dry-run repair-quarterly-aply', steps.request.outputs.operation)"),
        {"repair-quarterly-aply"}),
    "a name a step compares with": (_planted_step(f"steps.request.outputs.operation == '{STALE}'"), {STALE}),
    "a name compared unequal": (_planted_step(f"steps.request.outputs.operation != '{STALE}'"), {STALE}),
    "a name compared the other way round": (_planted_step(f"'{STALE}' == steps.request.outputs.operation"), {STALE}),
    "a name in the event's input": (_planted_step(f"contains('{STALE}', github.event.inputs.operation)"), {STALE}),
    "a name in a job's list under ${{ }}": (lambda workflow: workflow["jobs"]["refuse-rerun"].update(
        {"if": f"${{{{ !cancelled() && contains('relabel-fy-apply {STALE}', inputs.operation) }}}}"}), {STALE}),
    "a name in the concurrency group": (lambda workflow: workflow["jobs"]["ops"]["concurrency"].update(
        group=workflow["jobs"]["ops"]["concurrency"]["group"].replace("'logs-probe'", "'logs-probes'")),
        {"logs-probes"}),
    "a name in an env value's expression": (_planted_step(
        "always()", env={"APPLY": f"${{{{ steps.request.outputs.operation == '{STALE}' }}}}"}), {STALE}),
    "a list fromJSON() reads": (_planted_step(
        "contains(fromJSON('[\"relabel-fy-apply\"]'), steps.request.outputs.operation)"), {'["relabel-fy-apply"]'}),
    "a prefix startsWith() reads": (_planted_step("startsWith(steps.request.outputs.operation, 'repair-')"), {"repair-"}),
    # Look-alikes, which pass.
    "an option in capitals, as GitHub compares": (_planted_step("steps.request.outputs.operation == 'Detection-SQL'"), set()),
    "a list across lines": (_planted_step(
        "contains('relabel-fy-dry-run\n  relabel-fy-apply', steps.request.outputs.operation)"), set()),
    "a literal in an expression that does not read the operation": (_planted_step("github.ref == 'refs/heads/dev'"), set()),
    # Gaps, which pass though the rule forbids them: the module docstring names each.
    "gap: the operation read under another name": (_planted_step(f"env.OP == '{STALE}'"), set()),
    "gap: a list the expression reads from outside itself": (_planted_step(
        "contains(env.APPLIES, steps.request.outputs.operation)", env={"APPLIES": f"relabel-fy-apply {STALE}"}), set()),
    "gap: a shell test of the operation in a run script": (lambda workflow: workflow["jobs"]["ops"]["steps"].insert(
        2, {"name": "Planted", "run": f'if [ "$OP" = "{STALE}" ]; then exit 1; fi'}), set()),
}


def test_every_name_an_expression_gives_the_operation_is_a_dispatch_option():
    """selected() reads a word no dispatch offers as selecting nothing, so no gate that reads a step
    through it sees a stale name: each literal beside the operation names dispatch options or is one of
    NOT_AN_OPERATION, and each of those is still in use (E257)."""
    assert STALE not in OPTIONS, "the planted cases' stale name must be one the dispatch does not offer"
    assert _names_no_dispatch_offers(OPS) == set(), "names no dispatch offers, or a form this check does not read"
    others = {literal for literal in _beside_the_operation(OPS) if not _lists_options(literal, OPTIONS)}
    assert others == NOT_AN_OPERATION, f"NOT_AN_OPERATION lists what no expression holds: {sorted(NOT_AN_OPERATION - others)}"


@pytest.mark.parametrize("case", STALE_NAME_CASES)
def test_the_stale_name_check_scores_its_planted_cases(case):
    """The check's reach, on planted changes to a copy of the workflow: each flags the words it names,
    and each look-alike and each gap flags none."""
    plant, flagged = STALE_NAME_CASES[case]
    workflow = copy.deepcopy(OPS)
    plant(workflow)
    assert _names_no_dispatch_offers(workflow) == flagged


def test_every_database_command_runs_after_the_proxy_for_its_operations_with_its_script_installed():
    proxy_at, proxy = BY_NAME[PROXY]
    deps_at, deps = BY_NAME[DEPS]
    consumers = [(at, step) for at, step in enumerate(STEPS) if at != proxy_at and DB_COMMAND.search(step.get("run") or "")]
    assert len(consumers) >= 4
    for at, step in consumers:
        name, ops = step["name"], selected(step)
        assert ops, f"{name!r}: its if: selects no operation, so it never runs"
        assert ops <= selected(proxy) and proxy_at < at, (
            f"{name!r} runs with no DATABASE_URL for {sorted(ops - selected(proxy))}")
        for script in RUNNER_SCRIPT.findall(step["run"]):
            assert ops <= selected(deps) and deps_at < at, (
                f"{name!r} runs with no backend dependencies for {sorted(ops - selected(deps))}")
            assert any((ROOT / base / script).is_file() for base in (step.get("working-directory", "."), ".")), (
                f"{name!r}: {script} is not committed there")
    for name in NO_DATABASE:
        assert not DB_COMMAND.search(BY_NAME[name][1].get("run") or ""), f"{name!r} is exempt as opening no session, yet runs one"
    reach = cloud_sql_reach()
    unused = {op for op in selected(proxy) if not any(op in selected(step) for _, step in reach)}
    assert unused == set(), f"the proxy starts for operations no Cloud SQL step uses: {sorted(unused)}"


def test_summary_recovery_readout_is_fixed_read_only_and_retains_failure_evidence():
    """The summary receipt operation cannot broaden into arbitrary SQL or a mutating task."""
    name = "Read bounded summary recovery receipts"
    at, step = BY_NAME[name]
    assert selected(step) == {"summary-recovery-readout"}
    assert step["run"] == "python3 ops/summary_readout/readout.py"
    assert "continue-on-error" not in step
    assert 0 < int(step["timeout-minutes"]) <= 2
    options = step["env"]["PGOPTIONS"]
    assert dict(pg_settings(options))["default_transaction_read_only"] == "on"
    assert setting_ms(options, "statement_timeout") == 15_000
    assert setting_ms(options, "lock_timeout") == 2_000
    assert "summary-recovery-readout" in selected(BY_NAME[PROXY][1])
    assert "summary-recovery-readout" in selected(BY_NAME["Refuse to run while a main push (deploy) is in flight"][1])
    retained_at, retained = BY_NAME["Retain summary recovery readout"]
    assert retained_at > at
    assert retained["if"] == "always() && steps.request.outputs.operation == 'summary-recovery-readout'"
    assert retained["with"]["path"] == "summary-recovery-receipt.json"
    assert retained["with"]["if-no-files-found"] == "error"
    assert int(retained["with"]["retention-days"]) <= 14


def test_the_relabel_step_runs_for_exactly_the_relabel_operations_and_reads_their_outputs():
    step = BY_NAME[RELABEL][1]
    assert selected(step) == {"relabel-fy-dry-run", "relabel-fy-apply"}
    assert "continue-on-error" not in step, "a failed company must fail the run"
    assert step["env"]["OP"] == "${{ steps.request.outputs.operation }}"
    assert step["env"]["TICKERS"] == "${{ steps.request.outputs.tickers }}"


def test_the_quarterly_repair_step_runs_for_exactly_its_operations_and_keeps_its_report():
    """The quarterly repair step runs for its two operations alone, fails with the script, reads the
    resolved operation and tickers, and the report file the script wrote is kept after it whenever it
    ran, whatever its result. Its `if:` is pinned as written: `selected()` reads past a leading
    `always()`, which would run the write step after the approval check refused the apply. The
    keeping step reads the repair step's outcome, not the operation: after a failed resolve step the
    operation output is '', which contains() finds in any string."""
    at, step = BY_NAME[QUARTERLY]
    assert selected(step) == {"repair-quarterly-dry-run", "repair-quarterly-apply"}
    assert step["if"] == "contains('repair-quarterly-dry-run repair-quarterly-apply', steps.request.outputs.operation)", (
        "no status function: the step keeps GitHub's success(), so a refused approval check stops it")
    assert "continue-on-error" not in step, "a failed company must fail the run"
    assert step["env"]["OP"] == "${{ steps.request.outputs.operation }}"
    assert step["env"]["TICKERS"] == "${{ steps.request.outputs.tickers }}"
    retain_at, retain = BY_NAME["Retain quarterly repair report"]
    assert retain_at > at and retain["if"] == f"always() && steps.{step['id']}.outcome != 'skipped'"
    assert retain["with"]["path"] == "${{ runner.temp }}/quarterly-repair/", "the directory the step writes its report to"


def test_the_lineage_step_runs_for_exactly_its_operations_and_reads_their_outputs():
    """The lineage backfill step runs for its two operations alone, fails with the script and reads the
    resolved operation and tickers. Its `if:` is pinned as written, with no status function, so GitHub's
    success() stops it after a refused approval check."""
    step = BY_NAME[LINEAGE][1]
    assert selected(step) == {"repair-lineage-dry-run", "repair-lineage-apply"}
    assert step["if"] == "contains('repair-lineage-dry-run repair-lineage-apply', steps.request.outputs.operation)", (
        "no status function: the step keeps GitHub's success(), so a refused approval check stops it")
    assert "continue-on-error" not in step, "a failed company must fail the run"
    assert step["env"]["OP"] == "${{ steps.request.outputs.operation }}"
    assert step["env"]["TICKERS"] == "${{ steps.request.outputs.tickers }}"


@pytest.mark.parametrize("name", [RELABEL, QUARTERLY, LINEAGE, BASELINE, PREVIEW])
def test_the_script_readback_expects_the_steps_own_guards(name):
    """The step stops when its session reports other settings; the line it expects must be the one
    Postgres shows for the step's own PGOPTIONS (10s stays 10s, 120s shows as 2min)."""
    step = BY_NAME[name][1]
    expected = re.search(r'EXPECTED="session read_only=\$READ_ONLY lock_timeout=(\S+) statement_timeout=(\S+)"', step["run"])
    assert expected, f"{name!r} no longer compares its session's settings with its own"
    options = step["env"]["PGOPTIONS"]
    assert expected.groups() == (shown(setting_ms(options, "lock_timeout")), shown(setting_ms(options, "statement_timeout")))


def test_the_baseline_step_is_read_only_through_pgoptions_alone():
    """The fixed quarterly baseline needs no approval because it only reads: its session is read-only from the
    step's own PGOPTIONS, its read-back expects that (`read_only=on`, the line the parametrized test above
    ties to the bounds), and its run never appends to PGOPTIONS or passes a flag that could write."""
    step = BY_NAME[BASELINE][1]
    assert selected(step) == {"repair-quarterly-baseline-80fa90d-dry-run"}
    assert ("default_transaction_read_only", "on") in pg_settings(step["env"]["PGOPTIONS"])
    assert re.search(r"^\s*READ_ONLY=on\s*$", step["run"], re.M), "the read-back must expect a read-only session"
    assert "PGOPTIONS=" not in step["run"] and "--apply" not in step["run"]


PREVIEW_OPERATION = "financial-revenue-preview"
PREVIEW_ENV = {  # the step's env, whole: a name added here (a PGHOST, an SEC flag) changes what the run reads or writes
    "PGOPTIONS": "-c lock_timeout=10s -c statement_timeout=120s -c default_transaction_read_only=on",
    "SEC_RATE_LIMIT_PER_SECOND": "1", "EDGAR_RATE_LIMIT_PER_SEC": "1", "SKIP_REDIS_INIT": "true",
    "SECRET_KEY": "ops-workflow-secret-key-not-used-0123456789", "STRIPE_SECRET_KEY": "sk_test_ops",
    "STRIPE_WEBHOOK_SECRET": "whsec_ops", "PWNED_PASSWORD_CHECK_ENABLED": "false",
    "TICKERS": "${{ steps.request.outputs.tickers }}",
}
# The company in flight at the budget's end, at worst: an SEC read of 5 attempts at 20 s with 4 Retry-After waits
# of 120 s (580 s), then its session's four statements at 120 s each (480 s); then the summary and the report.
IN_FLIGHT_SECONDS = 1200


def test_the_preview_step_only_reads_for_its_one_operation_and_keeps_its_report():
    """E264's financial revenue preview needs no approval because it only reads. Its step runs for its one
    operation, with its `if:` pinned as written, and fails with the script. Its keys and its env are pinned
    whole, so its session is read-only through the step's fixed PGOPTIONS alone: its run expects a read-only
    session, never changes PGOPTIONS and passes no flag that could write. No approval list names it, and the
    pre-flight holds it while a main push is in flight. The step after it keeps the report file whenever the
    preview ran, for 30 days (test_workflow_dispatch_inputs.py runs the step and checks the path it writes)."""
    at, step = BY_NAME[PREVIEW]
    assert selected(step) == {PREVIEW_OPERATION}
    assert step["if"] == f"steps.request.outputs.operation == '{PREVIEW_OPERATION}'", (
        "no status function: the step keeps GitHub's success(), so a failed step before it stops it")
    assert set(step) == {"name", "id", "if", "working-directory", "timeout-minutes", "env", "run"}, (
        "no continue-on-error: a failed or stopped run must fail the step")
    assert (step["working-directory"], step["timeout-minutes"], step["env"]) == ("backend", "60", PREVIEW_ENV)
    assert re.search(r"^\s*READ_ONLY=on\s*$", step["run"], re.M), "the readback must expect a read-only session"
    assert "PGOPTIONS=" not in step["run"] and "--apply" not in step["run"]
    assert PREVIEW_OPERATION not in selected(OPS["jobs"]["approve-apply"])
    assert PREVIEW_OPERATION in selected(BY_NAME["Refuse to run while a main push (deploy) is in flight"][1])
    retain_at, retain = BY_NAME["Retain financial revenue preview report"]
    assert retain_at > at and retain["if"] == f"always() && steps.{step['id']}.outcome != 'skipped'"
    assert retain["with"] == {"name": "financial-revenue-preview-${{ github.run_id }}",
                              "path": "${{ runner.temp }}/financial-revenue-preview/report.json",
                              "retention-days": "30", "if-no-files-found": "warn"}


def test_the_preview_stops_itself_inside_its_steps_timeout():
    """The preview stops at its own time budget, so a run always ends with its summary line and its report;
    the step's timeout would kill it mid-company instead. The budget, read from the script the step runs,
    leaves the step IN_FLIGHT_SECONDS for the company in flight when it ends, the summary and the report."""
    step = BY_NAME[PREVIEW][1]
    [script] = RUNNER_SCRIPT.findall(step["run"])
    preview = importlib.import_module(script.removesuffix(".py").replace("/", "."))
    assert 0 < preview.TIME_BUDGET_SECONDS <= int(step["timeout-minutes"]) * 60 - IN_FLIGHT_SECONDS


def _connection_listeners(path: Path) -> list[tuple[str, int, str, str]]:
    """Each listener ``path`` registers on a connection event, as (path, line, event, handler): an
    ``event.listen(target, "<event>", handler)`` call, or an ``@event.listens_for(target, "<event>")``
    decorator. A handler the source does not name (a lambda, an attribute) reads as its source text."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    relative = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else path.name
    decorated = {id(decorator): node.name for node in ast.walk(tree)
                 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) for decorator in node.decorator_list}
    found = []
    for node in ast.walk(tree):
        called = isinstance(node, ast.Call) and getattr(node.func, "attr", getattr(node.func, "id", None))
        if called not in ("listen", "listens_for"):
            continue
        events = [arg.value for arg in node.args if isinstance(arg, ast.Constant) and arg.value in CONNECTION_EVENTS]
        if not events:
            continue
        if called == "listens_for":
            handler = decorated.get(id(node), ast.unparse(node))
        else:
            rest = node.args[node.args.index(next(arg for arg in node.args if isinstance(arg, ast.Constant))) + 1:]
            handler = getattr(rest[0], "id", ast.unparse(rest[0])) if rest else ast.unparse(node)
        found.append((relative, node.lineno, events[0], handler))
    return found


def _cloud_sql_scripts() -> list[Path]:
    """Each committed file a step that can reach Cloud SQL runs (`cloud_sql_reach()`) through python, bash
    or sh, wherever it lives, as STEP_SCRIPT reads the step's command, at the path its working directory
    gives it (E257: a hand-kept list of them missed the ticker repair's). A path it cannot find there,
    a quoted one included, fails the scan."""
    scripts = []
    for _, step in cloud_sql_reach():
        for script in STEP_SCRIPT.findall(step["run"]):
            path = next((ROOT / base / script for base in (step.get("working-directory", "."), ".")
                         if (ROOT / base / script).is_file()), None)
            assert path is not None, f"{step['name']!r}: {script} is not committed there"
            if path not in scripts:
                scripts.append(path)
    return scripts


STEP_SCRIPT_CASES = {  # a step's command, and the files STEP_SCRIPT reads from it
    "a backend script": ("python scripts/repair_ticker_by_cik.py --apply", ["scripts/repair_ticker_by_cik.py"]),
    "a file outside scripts/": ("python3 ops/summary_readout/readout.py", ["ops/summary_readout/readout.py"]),
    "a flag before the file": ("python3 -I ops/quarterly_baseline/run.py", ["ops/quarterly_baseline/run.py"]),
    "a shell script": ("bash scripts/apply_migrations.sh", ["scripts/apply_migrations.sh"]),
    "a quoted path, read as written, so the scan fails on it": ('python "$DIR/run.py"', ['"$DIR/run.py']),
    # Gaps: out of reach, as the docstring says.
    "gap: a module": ("python -m scripts.repair_ticker_by_cik", []),
    "gap: inline code": ("python3 -c 'import app.database'", []),
    "gap: a file run with no interpreter": ("./scripts/run.sh", []),
    "gap: a path held in a variable": ('python3 "$SCRIPT"', []),
}


@pytest.mark.parametrize("case", STEP_SCRIPT_CASES)
def test_the_script_reading_scores_its_planted_commands(case):
    command, read = STEP_SCRIPT_CASES[case]
    assert STEP_SCRIPT.findall(command) == read


def _what_it_does(listener) -> list[str]:
    """What a connect listener does to its session, run on a recording DBAPI connection: each statement
    it executes, each connection attribute it sets but autocommit (psycopg2's readonly, isolation_level
    and deferrable are setters that change the session's transactions), and each attribute it reads or
    method it calls that the recorder does not model (a connection's set_session, a cursor's callproc or
    its connection). A listener that tells the recorder from a real connection can still pass it; the
    guards case in tests/integration/test_session_time_zone.py holds the guards on a real session."""
    did: list[str] = []

    def call(name):
        def record(*args, **kwargs):
            did.append(f"{name}({', '.join([*map(repr, args), *(f'{key}={value!r}' for key, value in kwargs.items())])})")
        return record

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def execute(self, sql, *_args):
            did.append(sql)

        def __getattr__(self, name):
            did.append(f"reads cursor.{name}")
            return call(f"cursor.{name}")

    class Connection:
        closed = 0

        def __init__(self):
            object.__setattr__(self, "autocommit", False)

        def __setattr__(self, name, value):
            if name != "autocommit":
                did.append(f"{name} = {value!r}")
            object.__setattr__(self, name, value)

        def __getattr__(self, name):
            did.append(f"reads {name}")
            return call(name)

        def cursor(self):
            return Cursor()

    listener(Connection(), None)
    return did


def test_the_listener_scan_reads_each_form_it_claims(tmp_path):
    """The scan's own reach, on planted source: each registration it reads and the handler it names."""
    planted = tmp_path / "planted.py"
    planted.write_text(
        "from sqlalchemy import event\n"
        "event.listen(engine, 'connect', pin)\n"
        "event.listen(engine, 'checkout', lambda c, r, p: None)\n"
        "@event.listens_for(engine, 'engine_connect')\n"
        "def on_engine_connect(connection): pass\n"
        "event.listen(engine, 'before_cursor_execute', log)\n",
        encoding="utf-8",
    )
    assert [(event_name, handler) for _, _, event_name, handler in _connection_listeners(planted)] == [
        ("connect", "pin"), ("checkout", "lambda c, r, p: None"), ("engine_connect", "on_engine_connect"),
    ]
    # The run that holds the pin to its one statement, on planted listeners: what each does to its session.

    def also_lock_timeout(connection, _record):
        with connection.cursor() as cursor:
            cursor.execute("SET TIME ZONE 'UTC'")
            cursor.execute("SET lock_timeout = '0'")

    def read_write(connection, _record):
        with connection.cursor() as cursor:
            cursor.execute("SET default_transaction_read_only = off")

    def read_write_attribute(connection, _record):
        connection.readonly = False

    def read_write_session(connection, _record):
        connection.set_session(readonly=False)

    def set_config(connection, _record):
        connection.cursor().callproc("set_config", ["lock_timeout", "0", False])

    def through_the_cursor(connection, _record):
        with connection.cursor() as cursor:
            cursor.execute("SET TIME ZONE 'UTC'")
            cursor.connection.readonly = False

    def only_on_a_real_connection(connection, _record):
        if getattr(connection, "readonly", False) is None:  # psycopg2's default
            connection.readonly = False

    assert _what_it_does(also_lock_timeout) == ["SET TIME ZONE 'UTC'", "SET lock_timeout = '0'"]
    assert _what_it_does(read_write) == ["SET default_transaction_read_only = off"]
    assert _what_it_does(read_write_attribute) == ["readonly = False"]
    assert _what_it_does(read_write_session) == ["reads set_session", "set_session(readonly=False)"]
    assert _what_it_does(set_config) == [
        "reads cursor.callproc", "cursor.callproc('set_config', ['lock_timeout', '0', False])",
    ]
    assert _what_it_does(through_the_cursor) == ["SET TIME ZONE 'UTC'", "reads cursor.connection"]
    assert _what_it_does(only_on_a_real_connection) == ["reads readonly"]


def test_pgoptions_is_the_only_source_of_the_database_session_settings(monkeypatch):
    """libpq applies PGOPTIONS unless the connection names its own options, and a connection-level
    event could set the guards again after it. So the engine's connect_args carry no `options`, the
    URL the proxy step exports carries no query, the app uses that URL as it parses it, and nothing
    in the app or in a committed script a Cloud SQL step runs (`_cloud_sql_scripts()`) listens for a
    connection event but database.py's UTC pin on `connect` (E151), which, run, sets the session's
    time zone and nothing else."""
    from sqlalchemy.engine import make_url

    from app import database
    from app.config import settings

    tree = ast.parse((ROOT / "backend/app/database.py").read_text(encoding="utf-8"))
    assigned = [ast.unparse(node.value) for node in ast.walk(tree) if isinstance(node, ast.Assign)
                and any(getattr(target, "id", None) == "_DATABASE_URL" for target in node.targets)]
    assert assigned == ["_database_url()"], f"the engine must use the URL _database_url() returns: {assigned}"
    engines = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
               and getattr(node.func, "id", getattr(node.func, "attr", None)) == "create_engine"]
    assert engines, "app/database.py no longer calls create_engine: re-point this gate"
    for engine in engines:
        connect_args = next((kw.value for kw in engine.keywords if kw.arg == "connect_args"), None)
        assert connect_args is None or (isinstance(connect_args, ast.Dict) and all(
            isinstance(key, ast.Constant) for key in connect_args.keys)), ast.unparse(engine)
        keys = {key.value for key in connect_args.keys} if connect_args is not None else set()
        assert "options" not in keys, f"connect_args options would replace PGOPTIONS: {ast.unparse(engine)}"
        assert ast.unparse(engine.args[0]) == "_DATABASE_URL", ast.unparse(engine)
    exported = re.search(r'LOCAL_URL="([^"]*)"', BY_NAME[PROXY][1]["run"]).group(1)
    assert "?" not in exported, f"a query on the exported URL can carry options that replace PGOPTIONS: {exported}"

    proxy_url = "postgresql://ops:secret@127.0.0.1:5432/earningsnerd"
    monkeypatch.setattr(settings, "DATABASE_URL", proxy_url)
    assert database._database_url() == make_url(proxy_url), "the app must use the URL it is given, unchanged"

    scripts = _cloud_sql_scripts()
    assert scripts, "no Cloud SQL step runs a committed script: re-point this scan"
    listeners = [  # a shell script registers no SQLAlchemy listener, and only Python parses as Python
        listener for path in [*sorted((ROOT / "backend/app").rglob("*.py")), *(path for path in scripts if path.suffix == ".py")]
        for listener in _connection_listeners(path)
    ]
    others = [f"{path}:{line} ({event_name}: {handler})" for path, line, event_name, handler in listeners
              if (path, event_name, handler) != UTC_PIN]
    assert others == [], f"a connection-level event can set the session's guards again: {others}"
    assert [(path, event_name, handler) for path, _, event_name, handler in listeners] == [UTC_PIN], listeners
    assert _what_it_does(database._set_session_time_zone_utc) == ["SET TIME ZONE 'UTC'"], (
        "the UTC pin may set the session's time zone and nothing else: anything more can set a guard again"
    )
    # The quarterly repair and lineage backfill scripts run their SQL through their services and the fact
    # writers' lock, so those modules are read too, the repair's proxy step included (it runs no SQL, but it
    # sits on the repair's path). database.py's additive-column DDL and subscription_service.py bound their
    # own lock waits on purpose, and stay out.
    sql_modules = [ROOT / "backend/app/services/quarterly_fact_repair.py", ROOT / "backend/app/services/facts/upsert.py",
                   ROOT / "backend/app/services/filing_lineage_repair.py",
                   ROOT / "backend/app/services/proxy_fact_repair.py"]
    for path in [*scripts, *sql_modules]:
        assert not re.search(r"set_config|\bSET\s+(?:LOCAL\s+|SESSION\s+)?(?:lock_timeout|statement_timeout|default_transaction_read_only"
                             r"|transaction_read_only)|READ\s+WRITE|postgresql_readonly", path.read_text(encoding="utf-8"), re.I), (
            f"{path.name} sets its own guards")


def test_every_apply_operation_waits_for_the_founders_approval():
    """The approval job runs for exactly the -apply operations, in the founder's `ops-apply`
    environment, with no token and nothing that could turn a rejection into a pass (no
    `continue-on-error`, no concurrency group). The operations job needs it, runs an -apply only once
    it has passed and only in the run's first attempt, runs every other operation when it is skipped,
    carries no environment of its own and holds the `ops` concurrency group alone, beside each read's own
    run group (test_ops_readback_allow_rules.py). Its approval check
    runs for every apply after the resolve step and before the cloud sign-in, and the refuse-rerun job
    fails a later attempt of an apply, with no token, no action and no environment."""
    approve, ops, rerun = OPS["jobs"]["approve-apply"], OPS["jobs"]["ops"], OPS["jobs"]["refuse-rerun"]
    applies = {op for op in OPTIONS if op.endswith("-apply")}
    assert selected(approve) == applies != set()
    assert set(approve) == {"if", "runs-on", "timeout-minutes", "environment", "permissions", "steps"}
    assert (approve["environment"], approve["permissions"]) == ("ops-apply", {})
    assert [step.get("uses") for step in approve["steps"]] == [None], "the approval job runs no action"
    assert ops["needs"] == "approve-apply" and "environment" not in ops
    listed = re.search(r"contains\('([^']*)', inputs\.operation\)", ops["if"]).group(1)
    assert set(listed.split()) == applies
    assert ops["if"] == (
        "${{ !cancelled() && github.ref == 'refs/heads/main' && ((needs.approve-apply.result == 'skipped' "
        f"&& !contains('{listed}', inputs.operation)) || (needs.approve-apply.result == 'success' "
        "&& github.run_attempt == '1')) }}")
    assert "concurrency" not in OPS and set(ops["concurrency"]) == {"group", "cancel-in-progress"}
    assert ops["concurrency"]["cancel-in-progress"] == "false"
    group = ops["concurrency"]["group"]
    own = re.findall(r"inputs\.operation == '([^']+)'", group)  # every operation but these shares `ops`
    assert set(own) == {"describe-service", "logs-probe"} and not set(own) & applies
    assert group == ("${{ (" + " || ".join(f"inputs.operation == '{op}'" for op in own)
                     + ") && format('ops-read-{0}', github.run_id) || 'ops' }}")
    # approve-apply passes at once while the environment requires no reviewer, so an apply also stops
    # unless the run records an approval. The check reads the resolved operation, so it comes after the
    # step that writes it (before, the operation reads '', which contains() finds in any list), and
    # before the cloud sign-in.
    names = [step.get("name") for step in STEPS]
    at = names.index("Refuse an apply that no one approved in this run")
    request_at = next(index for index, step in enumerate(STEPS) if step.get("id") == "request")
    assert selected(STEPS[at]) == applies and request_at < at < names.index("Authenticate to Google Cloud")
    # Its refusal stops the job: no continue-on-error, no extra condition (its script runs in
    # test_workflow_dispatch_inputs.py).
    assert set(STEPS[at]) == {"name", "if", "env", "run"}
    # A re-run skips the operations job, which GitHub would mark green: refuse-rerun fails it instead,
    # for the approval job's operations, on every attempt but the first.
    assert set(rerun) == {"needs", "if", "runs-on", "timeout-minutes", "permissions", "steps"}  # no environment
    assert (rerun["needs"], rerun["permissions"]) == ("ops", {})
    assert [step.get("uses") for step in rerun["steps"]] == [None], "the refusal runs no action"
    approval_listed = re.search(r"contains\('([^']*)', inputs\.operation\)", approve["if"]).group(1)
    assert rerun["if"] == (
        "${{ !cancelled() && github.ref == 'refs/heads/main' && github.run_attempt != '1' "
        f"&& contains('{approval_listed}', inputs.operation) }}}}")
    assert set(rerun["steps"][0]) == {"name", "env", "run"}, "the refusal runs unconditionally and fails the job"
    refusal = subprocess.run(  # fixed argv; the script under test is repository content
        ["bash", "-e", "-c", rerun["steps"][0]["run"]], env={**os.environ, "OP": "relabel-fy-apply"},
        capture_output=True, text=True, check=False,
    )
    assert (refusal.returncode, "::error::" in refusal.stdout) == (1, True), "the refusal must fail the run"


def test_every_script_step_pins_the_sec_budgets():
    """A committed backend script the Ops runner runs is a process that can reach SEC (the ticker
    repair through the edgar service, the relabel through facts/transport), so it carries the per-process
    budgets the deploy pins everywhere else (docs/OPERATIONS.md, "SEC budgets per process")."""
    script_steps = [step for step in STEPS if RUNNER_SCRIPT.search(step.get("run") or "")]
    assert len(script_steps) >= 2
    for step in script_steps:
        env = step.get("env") or {}
        assert (env.get("SEC_RATE_LIMIT_PER_SECOND"), env.get("EDGAR_RATE_LIMIT_PER_SEC")) == ("1", "1"), (
            f"{step['name']!r} runs a backend script without the per-process SEC budgets pinned to 1")
