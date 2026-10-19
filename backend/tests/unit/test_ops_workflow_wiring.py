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

The fiscal-year relabel step runs for exactly its two operations, with no `continue-on-error`, and
any other operation would get a read-only dry run. It compares the settings its session reports
with its own guards before the script runs. Those guards and the dry run's read-only transactions
reach the database only through libpq's `PGOPTIONS`. An `options` setting in the app engine's
`connect_args`, a query on the URL the proxy step exports or on the URL the app builds from it, a
connection-level SQLAlchemy event that could `SET` them again, or a `SET` of a guard in the relabel
script would replace them, so none may exist.

`inputs[...]` and `outputs[...]` index syntax, which these checks would not see, is refused.
"""
import ast
import re

from tests.support.ops_workflow import (
    BY_NAME, DEPS, INPUTS, NO_DATABASE, OPS_TEXT, OPTIONS, PROXY, RELABEL, RESOLVE, ROOT, STEPS,
    cloud_sql_reach, selected, setting_ms, shown,
)

DB_COMMAND = re.compile(r"\bpsql\b|(?:\bpython3?|\bbash|\bsh)\s+(?:-\S+\s+)*\S*\bscripts/")
RUNNER_SCRIPT = re.compile(r"(?:\bpython3?|\bbash|\bsh)\s+(?:-\S+\s+)*(\S*\bscripts/[\w./-]+\.(?:py|sh))")
CONNECTION_EVENTS = {"do_connect", "connect", "first_connect", "checkout", "engine_connect", "begin", "after_begin"}


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


def test_the_relabel_step_runs_for_exactly_the_relabel_operations_and_reads_their_outputs():
    step = BY_NAME[RELABEL][1]
    assert selected(step) == {"relabel-fy-dry-run", "relabel-fy-apply"}
    assert "continue-on-error" not in step, "a failed company must fail the run"
    assert step["env"]["OP"] == "${{ steps.request.outputs.operation }}"
    assert step["env"]["TICKERS"] == "${{ steps.request.outputs.tickers }}"


def test_the_relabel_readback_expects_the_steps_own_guards():
    """The step stops when its session reports other settings; the line it expects must be the one
    Postgres shows for the step's own PGOPTIONS (10s stays 10s, 120s shows as 2min)."""
    step = BY_NAME[RELABEL][1]
    expected = re.search(r'EXPECTED="session read_only=\$READ_ONLY lock_timeout=(\S+) statement_timeout=(\S+)"', step["run"])
    assert expected, "the relabel step no longer compares its session's settings with its own"
    options = step["env"]["PGOPTIONS"]
    assert expected.groups() == (shown(setting_ms(options, "lock_timeout")), shown(setting_ms(options, "statement_timeout")))


def test_pgoptions_is_the_only_source_of_the_database_session_settings(monkeypatch):
    """libpq applies PGOPTIONS unless the connection names its own options, and a connection-level
    event could set the guards again after it. So the engine's connect_args carry no `options`, the
    URL the proxy step exports carries no query, the app uses that URL as it parses it, and nothing
    in the app or the relabel script listens for a connection event."""
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

    listeners = []
    for path in [*sorted((ROOT / "backend/app").rglob("*.py")), ROOT / "backend/scripts/relabel_filing_fy_facts.py"]:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (isinstance(node, ast.Call) and getattr(node.func, "attr", getattr(node.func, "id", None)) in ("listen", "listens_for")
                    and any(isinstance(arg, ast.Constant) and arg.value in CONNECTION_EVENTS for arg in node.args)):
                listeners.append(f"{path.relative_to(ROOT)}:{node.lineno}")
    assert listeners == [], f"a connection-level event can set the session's guards again: {listeners}"
    script = (ROOT / "backend/scripts/relabel_filing_fy_facts.py").read_text(encoding="utf-8")
    assert not re.search(r"set_config|\bSET\s+(?:LOCAL\s+|SESSION\s+)?(?:lock_timeout|statement_timeout|default_transaction_read_only"
                         r"|transaction_read_only)|READ\s+WRITE|postgresql_readonly", script, re.I), "the relabel script sets its own guards"
