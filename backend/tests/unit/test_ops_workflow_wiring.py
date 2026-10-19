"""Gate for how `.github/workflows/ops.yml` wires its production steps, read from the workflow itself.

Ops runs committed SQL and scripts against production through a Cloud SQL proxy. Its steps are
chosen by `if:` conditions and fed through `inputs.*` and `steps.request.outputs.*`. A slip there
fails silently:
- An input or output name GitHub cannot find evaluates to '' with no error. `outputs.ticker` for
  `tickers`, or `inputs.ticker` one hop earlier, would turn a relabel of one company into a relabel
  of every company.
- An `if:` that misses the proxy step leaves a script with no `DATABASE_URL`.
- A Cloud SQL step without a bound queues behind held locks with no statement limit.

So:
- Every `run:` step after the proxy step, for any operation the proxy starts for, can reach Cloud
  SQL, whatever its command looks like: each must bound its locks (at most 10 s) and its statements
  (at most 600 s) through `env: PGOPTIONS`, read as Postgres reads it (the last `-c` wins, a bare
  number is milliseconds, 0 means no bound). A step there that opens no session is named in
  `NO_DATABASE`.
- Every step whose text runs `psql` or a committed script (`python` or `bash` with a `scripts/`
  path, wherever it sits on the line) runs only for operations the proxy also runs for, and after
  it. A script also needs the dependency install before it, and the file committed. This half reads
  text, so a database client it cannot name (`pg_dump`, a Python one-liner) is outside it; the
  half above still bounds such a step.

The fiscal-year relabel step runs for exactly its two operations, and any other operation would get
a read-only dry run. It compares the settings its session reports with its own guards before the
script runs. Those guards and the dry run's read-only transactions reach the database only through
libpq's `PGOPTIONS`. An `options` setting in the app engine's `connect_args`, a query on the URL
the proxy step exports or on the URL the app builds from it, or a connection-level SQLAlchemy event
that could `SET` them again would replace them, so none may exist.

`_selected` reads each `if:` as GitHub evaluates it: `contains()` on a string is a substring test.
An `if:` form it does not know fails the gate rather than being skipped.
"""
import ast
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
OPS_TEXT = (ROOT / ".github/workflows/ops.yml").read_text(encoding="utf-8")
OPS = yaml.load(OPS_TEXT, Loader=yaml.BaseLoader)  # strings only: `on` stays a key, versions stay text
STEPS = OPS["jobs"]["ops"]["steps"]
INPUTS = OPS["on"]["workflow_dispatch"]["inputs"]
OPTIONS = INPUTS["operation"]["options"]
BY_NAME = {step.get("name"): (index, step) for index, step in enumerate(STEPS)}
RESOLVE, PROXY, DEPS = ("Resolve requested operation", "Start Cloud SQL proxy and export connection env",
                        "Install backend dependencies")
RELABEL = "Run fiscal-year relabel script"
NO_DATABASE = {DEPS}  # runs after the proxy for its operations, but opens no database session
DB_COMMAND = re.compile(r"\bpsql\b|(?:\bpython3?|\bbash|\bsh)\s+(?:-\S+\s+)*\S*\bscripts/")
RUNNER_SCRIPT = re.compile(r"(?:\bpython3?|\bbash|\bsh)\s+(?:-\S+\s+)*(\S*\bscripts/[\w./-]+\.(?:py|sh))")
UNIT_MS = {"ms": 1, "s": 1_000, "min": 60_000, "h": 3_600_000, "d": 86_400_000}
LOCK_MAX_MS, STATEMENT_MAX_MS = 10_000, 600_000
CONNECTION_EVENTS = {"connect", "first_connect", "checkout", "engine_connect", "begin"}


def _selected(step) -> set[str]:
    """The operations whose dispatch runs this step, read as GitHub evaluates its `if:`."""
    condition = step.get("if")
    if condition is None:
        return set(OPTIONS)
    condition = re.sub(r"^\$\{\{\s*(.*?)\s*\}\}$", r"\1", condition.strip())
    condition = re.sub(r"^always\(\) && ", "", condition)
    if match := re.fullmatch(r"(!?)contains\('([^']*)', steps\.request\.outputs\.operation\)", condition):
        hit = {op for op in OPTIONS if op in match.group(2)}
        return set(OPTIONS) - hit if match.group(1) else hit
    if match := re.fullmatch(r"steps\.request\.outputs\.operation == '([^']*)'", condition):
        return {match.group(1)} & set(OPTIONS)
    raise AssertionError(f"{step.get('name')!r}: teach _selected() this if: form rather than skip it: {condition!r}")


def _setting_ms(options: str, name: str) -> int | None:
    """The value Postgres applies from PGOPTIONS: the last `-c name=value` (or `--name=value`) wins,
    and a bare number is milliseconds."""
    values = re.findall(rf"(?:-c\s*|--){name}=(\S+)", options)
    if not values:
        return None
    match = re.fullmatch(r"(\d+)(ms|s|min|h|d)?", values[-1])
    assert match, f"unreadable {name}={values[-1]!r}: teach _setting_ms() this form rather than pass it"
    return int(match.group(1)) * UNIT_MS[match.group(2) or "ms"]


def _shown(ms: int) -> str:
    """A time setting as Postgres shows it: in the largest unit that holds it exactly."""
    for unit in ("d", "h", "min", "s"):
        if ms and ms % UNIT_MS[unit] == 0:
            return f"{ms // UNIT_MS[unit]}{unit}"
    return f"{ms}ms" if ms else "0"


def _cloud_sql_reach() -> list[tuple[int, dict]]:
    proxy_at, proxy = BY_NAME[PROXY]
    return [(at, step) for at, step in enumerate(STEPS) if at > proxy_at and step.get("run")
            and _selected(step) & _selected(proxy) and step.get("name") not in NO_DATABASE]


def test_dispatch_options_are_exactly_the_operations_the_resolve_step_accepts():
    run = BY_NAME[RESOLVE][1]["run"]
    accepted = re.search(r'case "\$OP" in\s+([a-z0-9|-]+)\) ;;', run).group(1).split("|")
    assert sorted(accepted) == sorted(OPTIONS)


def test_every_input_a_step_reads_is_declared_and_reaches_the_resolve_step_under_its_own_name():
    read = set(re.findall(r"\b(?:github\.event\.)?inputs\.(\w+)", OPS_TEXT))
    assert read <= set(INPUTS), f"inputs no dispatch declares, which GitHub reads as '': {sorted(read - set(INPUTS))}"
    assert BY_NAME[RESOLVE][1]["env"] == {
        "OP": "${{ inputs.operation }}", "TICKERS": "${{ inputs.tickers }}", "REVISION": "${{ inputs.revision }}"}


def test_every_request_output_a_step_reads_is_one_the_resolve_step_writes():
    written = set(re.findall(r'echo "(\w+)=\$', BY_NAME[RESOLVE][1]["run"]))
    assert written == {"operation", "tickers", "revision"}
    read = set(re.findall(r"steps\.request\.outputs\.(\w+)", OPS_TEXT))
    assert read <= written, f"outputs no step writes, which GitHub reads as '': {sorted(read - written)}"


def test_every_step_that_can_reach_cloud_sql_bounds_its_locks_and_statements():
    reach = _cloud_sql_reach()
    assert len(reach) >= 4  # the capacity ledger, detection SQL, the ticker repair, the FY relabel
    for _, step in reach:
        options = (step.get("env") or {}).get("PGOPTIONS", "")
        lock, statement = _setting_ms(options, "lock_timeout"), _setting_ms(options, "statement_timeout")
        assert lock and lock <= LOCK_MAX_MS, f"{step['name']!r}: env PGOPTIONS must set lock_timeout to 1ms..10s ({options!r})"
        assert statement and statement <= STATEMENT_MAX_MS, (
            f"{step['name']!r}: env PGOPTIONS must set statement_timeout to 1ms..600s ({options!r})")
    unused = {op for op in _selected(BY_NAME[PROXY][1]) if not any(op in _selected(step) for _, step in reach)}
    assert unused == set(), f"the proxy starts for operations no Cloud SQL step uses: {sorted(unused)}"


def test_every_database_command_runs_after_the_proxy_for_its_operations_with_its_script_installed():
    proxy_at, proxy = BY_NAME[PROXY]
    deps_at, deps = BY_NAME[DEPS]
    consumers = [(at, step) for at, step in enumerate(STEPS) if at != proxy_at and DB_COMMAND.search(step.get("run") or "")]
    assert len(consumers) >= 4
    for at, step in consumers:
        name, ops = step["name"], _selected(step)
        assert ops, f"{name!r}: its if: selects no operation, so it never runs"
        assert ops <= _selected(proxy) and proxy_at < at, (
            f"{name!r} runs with no DATABASE_URL for {sorted(ops - _selected(proxy))}")
        for script in RUNNER_SCRIPT.findall(step["run"]):
            assert ops <= _selected(deps) and deps_at < at, (
                f"{name!r} runs with no backend dependencies for {sorted(ops - _selected(deps))}")
            assert any((ROOT / base / script).is_file() for base in (step.get("working-directory", "."), ".")), (
                f"{name!r}: {script} is not committed there")


def test_the_relabel_step_runs_for_exactly_the_relabel_operations_and_reads_their_outputs():
    step = BY_NAME[RELABEL][1]
    assert _selected(step) == {"relabel-fy-dry-run", "relabel-fy-apply"}
    assert step["env"]["OP"] == "${{ steps.request.outputs.operation }}"
    assert step["env"]["TICKERS"] == "${{ steps.request.outputs.tickers }}"


def test_the_relabel_readback_expects_the_steps_own_guards():
    """The step stops when its session reports other settings; the line it expects must be the one
    Postgres shows for the step's own PGOPTIONS (10s stays 10s, 120s shows as 2min)."""
    step = BY_NAME[RELABEL][1]
    expected = re.search(r'EXPECTED="session read_only=\$READ_ONLY lock_timeout=(\S+) statement_timeout=(\S+)"', step["run"])
    assert expected, "the relabel step no longer compares its session's settings with its own"
    options = step["env"]["PGOPTIONS"]
    assert expected.groups() == (_shown(_setting_ms(options, "lock_timeout")), _shown(_setting_ms(options, "statement_timeout")))


def test_pgoptions_is_the_only_source_of_the_database_session_settings(monkeypatch):
    """libpq applies PGOPTIONS unless the connection names its own options, and a connection-level
    event could set the guards again after it. So the engine's connect_args carry no `options`, the
    URL the proxy step exports carries no query, the app uses that URL as it parses it, and nothing
    in the app or the relabel script listens for a connection event."""
    from sqlalchemy.engine import make_url

    from app import database
    from app.config import settings

    tree = ast.parse((ROOT / "backend/app/database.py").read_text(encoding="utf-8"))
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
