"""No test decides pass or fail by racing the wall clock (lessons/ops-one-test-process-per-worktree.md).

Under ``-n auto`` a worker shares the runner's CPUs with the other workers, so an event loop can run a
timer, or a thread can be scheduled, hundreds of milliseconds late. An assert that elapsed time stays
under a bound then fails without any defect: the parallel suite's flakes include a 1.22 s run against
a 1.2 s bound and 0.34 s against 0.2 s. Assert on the deadline instead: record the
``asyncio.timeout``/``timeout_at`` the code enters and compare its ``when()`` or ``expired()``, or
expire it yourself (``reschedule``) once the operation is under way.

This gate reads every module under ``backend/tests`` and flags an assert whose comparison a late loop
can break. That means a value that grows with lateness (a clock read in the assert, or elapsed time:
a later reading minus an earlier one, directly or through a name) on the small side of ``<``/``<=``.
It also means a value that shrinks (time remaining: a deadline minus a clock read now) on the large
side, or an earlier reading plus an offset as the bound. Lower bounds on elapsed time
(``elapsed >= 0.4``) cannot fail from slowness, so they pass. A value carried through a helper
function is out of reach unless its name says it is elapsed time (``elapsed``, ``duration``,
``took``), as a name, an attribute or a string key. ``min``, ``max``, ``abs``, ``round``, ``sum``,
``int``, ``float`` and scaling by a constant keep a value's direction. A site that remains must be a
guard whose bound is many times the time it measures; ``ALLOWED`` names why, and an entry whose site is
gone fails too.

Out of reach entirely: a real budget patched short enough to race the setup work it also covers
(a 0.6 s pipeline deadline that expired during a 0.53 s fetch). The fix is the same, arm or expire
the deadline once the operation it bounds is under way, but no assert shows the race. Also out of
reach: datetime clocks (``utcnow()``, ``datetime.now(tz)``), an elapsed value compared with
``== pytest.approx(..., abs=...)``, and a bound written as an earlier reading plus an offset when the
value it bounds was produced before that reading (flagged anyway; list it with its reason).
"""
import ast
import re
from pathlib import Path

TESTS = Path(__file__).resolve().parents[1]
BACKEND = TESTS.parent

ALLOWED = {
    "tests/integration/test_usage_counter_transactions.py::test_postgres_counter_lock_wait_is_bounded_and_failure_does_not_increment":
        "an 80 ms lock_timeout measured against 1.5 s, in the serial migrations-postgres job",
    "tests/integration/test_usage_counter_transactions.py::test_postgres_reservation_lock_wait_is_bounded_and_admits_nothing":
        "an 80 ms lock_timeout measured against 1.5 s, in the serial migrations-postgres job",
    "tests/unit/test_app_loop_lifespan.py::test_hanging_startup_schema_step_fails_the_start_within_the_deadline":
        "a 1 s startup deadline measured against 5 s; the hang it guards against lasts 30 s",
    "tests/unit/test_copilot_prose_quotations.py::test_quotation_work_is_bounded":
        "a performance guard: the best of three runs, about 40 ms, against 0.25 s",
    "tests/unit/test_citation_markers.py::TestCopilotConfiguration::test_linear_on_degenerate_whitespace_runs":
        "a performance guard: the linear scan takes milliseconds, the quadratic regression seconds",
    "tests/unit/test_recovery_context.py::test_actual_generation_deadline_covers_source_preparation_and_prevents_late_sdk":
        "the 75 s budget's remaining time read just after the worker starts, against 70 s: 5 s of slack",
    "tests/unit/test_redis_disabled_skip.py::test_cache_ops_are_fast_no_op_when_disabled":
        "two no-op calls measured against 0.5 s; the regression waits out a 2 s operation timeout",
}

_CLOCK_FUNCTIONS = {"monotonic", "monotonic_ns", "perf_counter", "perf_counter_ns"}
# A name that says it holds elapsed time is read as one, wherever it came from: the flake this gate was
# written after returned its elapsed time from a nested coroutine, through a task result.
_ELAPSED_NAME = re.compile(r"elapsed|duration|took")
# Builtins that keep elapsed time elapsed: min(elapsed), abs(now - started), round(...).
_PASS_THROUGH = {"min", "max", "abs", "round", "sum", "int", "float"}
_LOOP_GETTERS = {"get_running_loop", "get_event_loop"}


def _is_clock_call(node: ast.AST) -> bool:
    """A monotonic/perf_counter read, or time.time() and a loop's .time(); a datetime's .time() is not."""
    if not isinstance(node, ast.Call) or node.args or node.keywords:
        return False
    func = node.func
    if isinstance(func, ast.Name):
        return func.id in _CLOCK_FUNCTIONS  # from time import monotonic
    if not isinstance(func, ast.Attribute):
        return False
    if func.attr in _CLOCK_FUNCTIONS:
        return True
    if func.attr not in {"time", "time_ns"}:
        return False
    owner = func.value
    if isinstance(owner, ast.Name):
        return owner.id == "time" or "loop" in owner.id
    getter = owner.func if isinstance(owner, ast.Call) else None
    return getattr(getter, "attr", getattr(getter, "id", None)) in _LOOP_GETTERS


def _mentions(node: ast.AST, names: set[str]) -> bool:
    return any(_is_clock_call(n) or (isinstance(n, ast.Name) and n.id in names) for n in ast.walk(node))


def _trend(node: ast.AST, readings: set[str], spans: set[str], remains: set[str]) -> str | None:
    """How a value moves when the loop runs late: "up" (a clock read now, or elapsed time), "down" (a
    fixed point minus a clock read now: time remaining), or None (no clock, or an earlier reading,
    which is a fixed point in time)."""
    if _is_clock_call(node):
        return "up"
    if isinstance(node, ast.Name):
        if node.id in spans or _ELAPSED_NAME.search(node.id):
            return "up"
        return "down" if node.id in remains else None
    if isinstance(node, ast.Attribute):
        return "up" if _ELAPSED_NAME.search(node.attr) else None  # r.elapsed
    if isinstance(node, ast.Subscript):
        key = node.slice
        if isinstance(key, ast.Constant) and isinstance(key.value, str) and _ELAPSED_NAME.search(key.value):
            return "up"  # row["duration_ms"]
        return _trend(node.value, readings, spans, remains)
    if isinstance(node, ast.Call):
        if not (isinstance(node.func, ast.Name) and node.func.id in _PASS_THROUGH):
            return None
        trends = {_trend(arg, readings, spans, remains) for arg in node.args} - {None}
        return trends.pop() if len(trends) == 1 else None
    if not isinstance(node, ast.BinOp):
        return None
    left = _trend(node.left, readings, spans, remains)
    right = _trend(node.right, readings, spans, remains)
    if isinstance(node.op, ast.Sub):
        if right == "up" and left is None:
            return "down"  # deadline - now: a fixed point minus a clock read now
        if left == "up" or (left is None and _mentions(node.left, readings) and _mentions(node.right, readings)):
            return "up"  # now - started, or end - started
        return "down" if left == "down" else None
    if isinstance(node.op, ast.Add):
        return left or right
    if isinstance(node.op, (ast.Mult, ast.Div, ast.FloorDiv)):
        return left if right is None else None  # (now - started) * 1000 keeps its direction
    return None


def _assigned_names(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Assign):
        targets = node.targets
    elif isinstance(node, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr)):
        targets = [node.target]
    else:
        return []
    return [n.id for target in targets for n in ast.walk(target) if isinstance(n, ast.Name)]


def _is_offset_reading(node: ast.AST, readings: set[str]) -> bool:
    """An earlier reading (a name) plus an offset, as a bound a later value must stay under."""
    return isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add) and any(
        isinstance(side, ast.Name) and side.id in readings for side in (node.left, node.right))


def _races(function: ast.AST) -> list[int]:
    readings: set[str] = set()  # names computed from a clock reading
    spans: set[str] = set()     # ... that grow when the loop runs late (elapsed time)
    remains: set[str] = set()   # ... that shrink (time remaining)
    changed = True
    while changed:
        changed = False
        for node in ast.walk(function):
            value = getattr(node, "value", None)
            if value is None or not _assigned_names(node) or not _mentions(value, readings | spans | remains):
                continue
            # A stored reading (started = loop.time(), deadline = loop.time() + 5) is a fixed point in
            # time; only a value computed from a difference keeps moving with lateness.
            is_difference = any(isinstance(n, ast.BinOp) and isinstance(n.op, ast.Sub) for n in ast.walk(value))
            trend = _trend(value, readings, spans, remains) if is_difference else None
            for name in _assigned_names(node):
                kind = spans if trend == "up" else remains if trend == "down" else readings
                if name not in kind:
                    kind.add(name)
                    changed = True
    readings |= spans | remains
    lines = []
    for node in ast.walk(function):
        if not isinstance(node, ast.Assert):
            continue
        for compare in (n for n in ast.walk(node.test) if isinstance(n, ast.Compare)):
            operands = [compare.left, *compare.comparators]
            for op, left, right in zip(compare.ops, operands, operands[1:]):
                if isinstance(op, (ast.Lt, ast.LtE)):
                    small, big = left, right
                elif isinstance(op, (ast.Gt, ast.GtE)):
                    small, big = right, left
                else:
                    continue
                if (_trend(small, readings, spans, remains) == "up" or _trend(big, readings, spans, remains) == "down"
                        or _is_offset_reading(big, readings - spans - remains)):
                    lines.append(node.lineno)
    return lines


def _sites() -> dict[str, list[int]]:
    """``path::Class::function`` (the outermost function, so a nested helper counts for its test) → lines."""
    sites: dict[str, list[int]] = {}

    def visit(body, path: str, prefix: str) -> None:
        for node in body:
            if isinstance(node, ast.ClassDef):
                visit(node.body, path, f"{prefix}{node.name}::")
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                lines = _races(node)
                if lines:
                    sites[f"{path}::{prefix}{node.name}"] = sorted(set(lines))

    for module in sorted(TESTS.rglob("*.py")):
        visit(ast.parse(module.read_text(encoding="utf-8")).body, module.relative_to(BACKEND).as_posix(), "")
    return sites


def test_no_test_races_the_wall_clock():
    sites = _sites()
    unlisted = {site: lines for site, lines in sites.items() if site not in ALLOWED}
    assert not unlisted, (
        "These asserts require elapsed wall-clock time to stay under a bound, which a loaded xdist worker can "
        f"overrun with no defect present: {unlisted}. Assert on the deadline the code enters instead (record "
        "its asyncio.timeout/timeout_at and compare when() or expired()), or, for a guard many times longer than "
        "what it measures, add it to ALLOWED with the reason."
    )
    stale = sorted(set(ALLOWED) - set(sites))
    assert not stale, f"ALLOWED names sites that no longer race the clock; remove them: {stale}"


def _flags(source: str) -> list[int]:
    function = ast.parse(source).body[0]
    return _races(function)


def test_the_detector_finds_each_racing_shape_and_spares_the_safe_ones():
    racing = {
        "inline span": "def t():\n    started = time.monotonic()\n    run()\n    assert time.monotonic() - started < 0.1\n",
        "named span": "def t():\n    s = loop.time()\n    run()\n    elapsed = loop.time() - s\n    assert elapsed < 1.2\n",
        "reversed": "def t():\n    s = time.perf_counter()\n    run()\n    assert 0.5 > time.perf_counter() - s\n",
        "offset reading": "def t():\n    before = asyncio.get_running_loop().time()\n    d = run()\n    assert d <= before + 75.1\n",
        "chained": "def t():\n    before = time.time()\n    d = run()\n    assert before < d <= before + 75.1\n",
        "an elapsed name from a task": "def t():\n    first, elapsed = await task\n    assert elapsed < 1.2\n",
        "the best of several runs": "def t():\n    elapsed = []\n    elapsed.append(time.perf_counter() - s)\n    assert min(elapsed) < 0.25\n",
        "abs of a span": "def t():\n    s = time.monotonic()\n    assert abs(time.monotonic() - s) < 1\n",
        "an elapsed attribute": "def t():\n    r = run()\n    assert r.elapsed < 1\n",
        "a scaled span": "def t():\n    s = time.perf_counter()\n    ms = (time.perf_counter() - s) * 1000\n    assert ms < 50\n",
        "a stored deadline's floor": "def t():\n    deadline = loop.time() + 60\n    assert deadline - loop.time() > 50\n",
        "imported clock": "def t():\n    s = monotonic()\n    run()\n    took = monotonic() - s\n    assert took <= 2\n",
        "a clock read now below a deadline": "def t():\n    deadline = start()\n    assert loop.time() < deadline\n",
        "remaining time above a floor": "def t():\n    timer = arm()\n    assert 70 < timer.when() - loop.time()\n",
        "named remaining time": "def t():\n    left = timer.when() - time.monotonic()\n    assert left > 70\n",
    }
    safe = {
        "lower bound": "def t():\n    started = time.monotonic()\n    run()\n    assert time.monotonic() - started >= 0.4\n",
        "a reading below a later value": "def t():\n    before = time.time()\n    d = run()\n    assert before < d\n",
        "deadline comparison": "def t():\n    d = record()\n    assert d[1].when() < d[0].when() - 30\n",
        "equality": "def t():\n    s = loop.time()\n    assert run() == s + 1.0\n",
        "datetime.time(...)": "def t():\n    assert datetime.time(9, 30) < datetime.time(10)\n",
        "clock read in the assert": "def t():\n    d = run()\n    assert d <= time.time() + 5\n",
        "not an assert": "def t():\n    s = time.monotonic()\n    while time.monotonic() - s < 5:\n        poll()\n",
        "remaining time under its budget": "def t():\n    timer = arm()\n    assert timer.when() - loop.time() <= 75\n",
        "a stored deadline's cap": "def t():\n    deadline = loop.time() + 60\n    assert deadline - loop.time() <= 60\n",
        "a datetime's time of day": "def t():\n    row = fetch()\n    assert row.accepted_at.time() < dtime(16, 0)\n",
        "an elapsed field's floor": "def t():\n    events = run()\n    assert events[1][1][\"duration_ms\"] >= 0\n",
    }
    assert {name: _flags(src) for name, src in racing.items() if not _flags(src)} == {}
    assert {name: _flags(src) for name, src in safe.items() if _flags(src)} == {}
