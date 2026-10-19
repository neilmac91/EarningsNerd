"""Gate for how `.github/workflows/ops.yml` wires its production steps, read from the workflow itself.

Ops runs committed SQL and scripts against production through a Cloud SQL proxy. Its steps are
chosen by `if:` conditions and fed through `steps.request.outputs.*`. A slip there fails silently:
- An output name GitHub cannot find evaluates to '' with no error. `outputs.ticker` for `tickers`
  would turn a relabel of one company into a relabel of every company.
- An `if:` that misses the proxy step leaves a script with no `DATABASE_URL`.
- A Cloud SQL step without `PGOPTIONS` queues behind held locks with no statement bound.

So every step that runs `psql` or a committed script must:
- run only for operations the proxy step also runs for, and after it;
- bound its locks and statements through `env: PGOPTIONS`;
- for a script, also run after the dependency install, with the script committed under its
  `working-directory`.

The fiscal-year relabel step runs for exactly its two operations, and any other operation would get
a read-only dry run. Its guards and the dry run's read-only transactions reach the database only
through libpq's `PGOPTIONS`. An `options` setting in the app engine's `connect_args`, or in the URL
the proxy step exports, would replace them, so neither may carry one.

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
OPTIONS = OPS["on"]["workflow_dispatch"]["inputs"]["operation"]["options"]
BY_NAME = {step.get("name"): (index, step) for index, step in enumerate(STEPS)}
RESOLVE, PROXY, DEPS = ("Resolve requested operation", "Start Cloud SQL proxy and export connection env",
                        "Install backend dependencies")
RELABEL = "Run fiscal-year relabel script"
DB_CONSUMER = re.compile(r"^\s*(?:psql\b|python3? scripts/)", re.M)
RUNNER_SCRIPT = re.compile(r"^\s*python3? (scripts/\S+\.py)", re.M)


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


def test_dispatch_options_are_exactly_the_operations_the_resolve_step_accepts():
    run = BY_NAME[RESOLVE][1]["run"]
    accepted = re.search(r'case "\$OP" in\s+([a-z0-9|-]+)\) ;;', run).group(1).split("|")
    assert sorted(accepted) == sorted(OPTIONS)


def test_every_request_output_a_step_reads_is_one_the_resolve_step_writes():
    written = set(re.findall(r'echo "(\w+)=\$', BY_NAME[RESOLVE][1]["run"]))
    assert written == {"operation", "tickers", "revision"}
    read = set(re.findall(r"steps\.request\.outputs\.(\w+)", OPS_TEXT))
    assert read <= written, f"outputs no step writes, which GitHub reads as '': {sorted(read - written)}"


def test_every_cloud_sql_step_has_the_proxy_its_guards_and_for_scripts_the_dependencies_and_the_file():
    proxy_at, proxy = BY_NAME[PROXY]
    deps_at, deps = BY_NAME[DEPS]
    consumers = [(index, step) for index, step in enumerate(STEPS) if DB_CONSUMER.search(step.get("run") or "")]
    assert len(consumers) >= 4  # detection SQL, the capacity ledger, the ticker repair, the FY relabel
    for at, step in consumers:
        name, ops = step["name"], _selected(step)
        assert ops, f"{name!r}: its if: selects no operation, so it never runs"
        assert ops <= _selected(proxy) and proxy_at < at, (
            f"{name!r} runs with no DATABASE_URL for {sorted(ops - _selected(proxy))}")
        options = (step.get("env") or {}).get("PGOPTIONS", "")
        assert re.search(r"-c lock_timeout=\d+s", options) and re.search(r"-c statement_timeout=\d+s", options), (
            f"{name!r} must bound locks and statements through env PGOPTIONS (found {options!r})")
        for script in RUNNER_SCRIPT.findall(step["run"]):
            assert ops <= _selected(deps) and deps_at < at, (
                f"{name!r} runs with no backend dependencies for {sorted(ops - _selected(deps))}")
            assert (ROOT / step.get("working-directory", ".") / script).is_file(), f"{name!r}: {script} is not committed there"
    unused = {op for op in _selected(proxy) if not any(op in _selected(step) for _, step in consumers)}
    assert unused == set(), f"the proxy starts for operations no Cloud SQL step uses: {sorted(unused)}"


def test_the_relabel_step_runs_for_exactly_the_relabel_operations_and_reads_their_outputs():
    step = BY_NAME[RELABEL][1]
    assert _selected(step) == {"relabel-fy-dry-run", "relabel-fy-apply"}
    assert step["env"]["OP"] == "${{ steps.request.outputs.operation }}"
    assert step["env"]["TICKERS"] == "${{ steps.request.outputs.tickers }}"


def test_pgoptions_is_the_only_source_of_the_database_session_settings():
    """libpq applies PGOPTIONS unless the connection names its own options."""
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
    exported = re.search(r'LOCAL_URL="([^"]*)"', BY_NAME[PROXY][1]["run"]).group(1)
    assert "?" not in exported, f"a query on the exported URL can carry options that replace PGOPTIONS: {exported}"
