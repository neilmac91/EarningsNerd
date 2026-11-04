"""A backend test's bound on a wait for work that should finish only breaks a hang; it never times the work.

On a starved CI runner, work that takes milliseconds alone stretches to seconds, and a short bound on a wait for it
fails a correct run: a one-second ``asyncio.wait_for`` failed main's CI so on 2026-11-04 (``a20c02079``). A defect
the test guards fails it at any bound, by an assertion or by hanging until the bound. So such a wait takes
``HANG_GUARD_S`` from ``tests/support/hang_guard.py``, or a bound of its own of at least ``FLOOR_S``: one below a
production timeout that would end the wait sooner, or one short enough that a defect making every case of a PostgreSQL
file wait it out still fits that file's CI step (``lessons/test-a-wait-bound-only-breaks-a-hang.md``, rules 2 and 6).

This gate reads every tracked Python file under ``backend/tests`` for a timed wait, and resolves its bound to a number:
a literal, a module constant (``HANG_GUARD_S`` imported from the support module included), a parameter's default or a
local assignment in an enclosing function, ``int()`` or ``float()`` of one, or arithmetic on those. A name assigned
more than once resolves to its smallest value. A module imported at the top of the file under another name
(``import asyncio as aio``, ``import subprocess as sp``, ``from concurrent import futures as pool``) and a form or clock
imported from one (``from asyncio import timeout as within``, ``from time import monotonic as clock``) are read as the
forms they stand for. The forms it reads:
- ``wait_for(awaitable, bound)`` (``asyncio``'s and ``threading.Condition``'s); ``asyncio.timeout(bound)``, imported
  from ``asyncio`` or not; ``asyncio.wait`` and ``concurrent.futures.wait`` or ``as_completed`` with ``timeout=``;
- ``.wait(bound)``, ``.join(bound)`` and ``.result(bound)``, or with ``timeout=``; ``.get``, ``.put`` and ``.acquire``
  with ``timeout=``, or with it after a ``block`` flag given as ``True`` or ``False``;
  ``Barrier(parties, action, bound)`` or with ``timeout=``;
- a child process or a request with ``timeout=``: ``subprocess.run``, ``check_output``, ``check_call`` and ``call``,
  ``.communicate``, ``urlopen``;
- a wait handed to a thread with its bound: ``asyncio.to_thread(event.wait, bound)``,
  ``loop.run_in_executor(executor, event.wait, bound)``;
- a polling deadline: ``time.monotonic() + bound``, ``time.perf_counter() + bound`` or ``loop.time() + bound``, also
  through a name that holds such a clock's reading (``started + bound``), and ``while clock() - started < bound``;
- a counted poll: ``for _ in range(count)`` whose body sleeps ``step`` and can leave early (``break`` or
  ``return``), a bound of ``count * step``;
- a helper's bound passed where it is called: a wait whose bound reads one of the helper's parameters (a timeout, a
  deadline's offset, a poll's count or step) is read again at each call that passes such a parameter, with the value
  passed.

A bound under ``FLOOR_S`` is short on purpose only where the case needs it: a negative window (the case asserts that
something does not happen within it), a timing assertion (the bound is the property under test), an ordering check (what
it looks for has already happened, so it takes no wall-clock time), a polling step, or pacing. Each such site is listed
in ``SHORT_ON_PURPOSE`` by file, top-level definition, form and seconds, with its reason, and a new one, or one that
changes, fails here until it is listed.

What it does not read: a bound it cannot resolve to a number (a parameter that no call resolves, an attribute, a call, a
patched setting); a wait with no bound; a socket's connect timeout (``socket.create_connection(address, timeout)``); an
alias made by assignment (``real_timeout = asyncio.timeout``, ``clock = time.monotonic``) or by an import inside a
function; waits in source held in a string, such as a pytester child's; a pool's ``pool_timeout``, which
``lessons/test-a-burst-pool-timeout-breaks-a-deadlock-and-detects-nothing.md`` covers and which some cases set short on
purpose; and an elapsed-time assertion (``assert clock() - started < bound``), which
``tests/unit/test_wall_clock_bounds.py`` gates. ``time.time()`` is the wall clock, which stamps rather than waits, and
``.join`` with an argument that is not a number is ``str.join``. Whether a guard stays below a production timeout that
would end the same wait, whether nested bounds stay in order, and whether a PostgreSQL step's cases fit its time when a
defect makes each wait out its guard, are review-checked.
"""

from __future__ import annotations

import ast
import subprocess  # nosec B404 - runs git ls-files on this checkout, fixed arguments
from collections import Counter
from pathlib import Path

from tests.support.hang_guard import HANG_GUARD_S

BACKEND = Path(__file__).resolve().parents[2]
FLOOR_S = 10.0
SUPPORT = "tests.support.hang_guard"
SHARED = {"HANG_GUARD_S": HANG_GUARD_S}
THREAD_WAITS = {"wait", "join", "result", "get", "acquire", "wait_for"}
SUBPROCESS_WAITS = {"run", "check_output", "check_call", "call"}
CLOCKS = {"monotonic", "perf_counter"}
MODULES = {"asyncio", "concurrent.futures", "subprocess", "time"}
_OPS = {
    ast.Add: lambda left, right: left + right,
    ast.Sub: lambda left, right: left - right,
    ast.Mult: lambda left, right: left * right,
    ast.Div: lambda left, right: left / right,
}
_Function = ast.FunctionDef | ast.AsyncFunctionDef

# (file under backend/, top-level definition, form, seconds) -> (sites, why each is short on purpose).
_LOCKOUT = "tests/integration/test_login_lockout_transactions.py"
_PROGRESS = "tests/integration/test_summary_progress_transactions.py"
_OWNERSHIP = "tests/unit/test_durable_request_ownership.py"
_OVERLAP = "tests/unit/test_summary_enrichment_overlap.py"
SHORT_ON_PURPOSE: dict[tuple[str, str, str, float], tuple[int, str]] = {
    (_LOCKOUT, "test_failure_waiting_on_success_clear_records_against_committed_state", "wait", 0.1): (
        1, "negative window: the failure's upsert is still blocked on the uncommitted clear, inside statement_timeout"),
    ("tests/integration/test_summary_job_transactions.py", "_LateRelease", "wait", 0.01): (
        1, "polling step: the late mode's watcher reads pg_locks every 10 ms, how long a waiter stays blocked"),
    (_PROGRESS, "test_a_write_behind_an_uncommitted_clear_waits_and_follows_its_outcome", "wait", 0.2): (
        1, "negative window: the write is still blocked on the uncommitted clear, inside statement_timeout"),
    (_PROGRESS, "test_a_mark_behind_an_uncommitted_holder_waits_and_follows_its_outcome", "wait", 0.2): (
        1, "negative window: the stale mark is still blocked on the uncommitted holder, inside statement_timeout"),
    ("tests/integration/test_usage_counter_transactions.py",
     "test_postgres_counter_lock_wait_is_bounded_and_failure_does_not_increment", "result", 1.5): (
        1, "timing assertion: the patched lock_timeout ends the counter's lock wait within 1.5 s"),
    (_OWNERSHIP, "test_summary_disconnect_joins_actual_worker_before_releasing_leadership", "asyncio.wait", 0.3): (
        1, "negative window: the cancelled request does not end while its worker still runs"),
    (_OWNERSHIP, "test_summary_disconnect_joins_the_section_parse_worker_before_releasing_leadership",
     "asyncio.wait", 0.3): (
        1, "negative window: the cancelled request does not end while its section parse still runs"),
    ("tests/unit/test_event_loop_safety.py", "TestCacheOperationTimeouts", "wait_for", 3.0): (
        1, "timing assertion: CACHE_OPERATION_TIMEOUT (2 s) cuts a 10 s cache call within 3 s (vacuous today: E314)"),
    ("tests/unit/test_filing_source_storage.py",
     "test_cancellation_kills_native_child_and_holds_single_permit_through_reap", "deadline", 0.05): (
        1, "negative window: a second put gets no permit while the cancelled put's reap holds it"),
    ("tests/unit/test_provider_admission.py", "test_chat_wait_is_bounded_by_its_own_deadline_and_leaks_no_slot",
     "wait_for", 2.0): (1, "timing assertion: the waiter's own 0.05 s budget, not a later one, rejects it within 2 s"),
    ("tests/unit/test_secret_scan_guard.py", "test_a_scan_past_its_deadline_refuses", "deadline", 1.5): (
        1, "timing assertion: the scan's deadline is the property under test, below the stub's 5 s sleep"),
    ("tests/unit/test_summary_delivery_acceptance.py",
     "test_whole_http_deadline_interrupts_real_header_and_body_trickles", "wait", 0.03): (
        1, "pacing: each trickled byte waits 30 ms, under the client's socket inactivity timeout"),
    ("tests/unit/test_summary_delivery_acceptance.py",
     "test_whole_http_deadline_interrupts_real_header_and_body_trickles", "deadline", 0.15): (
        1, "timing assertion: the whole request's 0.15 s deadline is what must cut the trickle short"),
    ("tests/unit/test_summary_delivery_acceptance.py",
     "test_network_guard_permits_real_event_loop_uvicorn_and_task_child_startup", "urlopen", 1.0): (
        1, "polling step: each health probe gives up at 1 s, and the loop retries under its 20 s deadline"),
    (_OVERLAP, "test_the_statement_parse_waits_for_its_own_excerpt_build", "wait", 2.0): (
        1, "negative window: no statement parse starts during the excerpt build"),
    (_OVERLAP, "test_the_xbrl_write_finishes_before_the_provider_request", "wait", 2.0): (
        1, "negative window: no provider request starts during the XBRL write"),
    (_OVERLAP, "test_a_disconnect_during_the_excerpt_build_cancels_the_pending_statement_parse", "to_thread", 2.0): (
        1, "negative window: no leaked statement task runs after the disconnect"),
    ("tests/unit/test_company_routes_pool_lifetime.py", "_wait_for_released_pool", "counted poll", 0.0): (
        1, "ordering check: each unit releases its session before the route reaches the stall, so the pool is empty "
           "once the stall starts; a wait would let production's 4 s quote timeout pass a session held past the stall"),
    ("tests/unit/test_summary_worker_http_isolation.py", "_ready", "get", 0.5): (
        1, "polling step: each readiness probe gives up at 0.5 s, and the loop retries under its 15 s bound"),
}


def _number(node: ast.AST | None, names: dict[str, float]) -> float | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return float(node.value)
    if isinstance(node, ast.Name):
        return names.get(node.id)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        inner = _number(node.operand, names)
        return None if inner is None else -inner
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        left, right = _number(node.left, names), _number(node.right, names)
        return None if left is None or right is None else _OPS[type(node.op)](left, right)
    if isinstance(node, ast.Call) and getattr(node.func, "id", "") in ("int", "float") and len(node.args) == 1:
        inner = _number(node.args[0], names)
        return None if inner is None else float(int(inner)) if node.func.id == "int" else inner
    return None


def _assigned(node: ast.AST) -> tuple[str, ast.AST] | None:
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        return node.targets[0].id, node.value
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
        return node.target.id, node.value
    return None


def _keep_least(names: dict[str, float], name: str, value: float | None, defined: set[str]) -> None:
    """Records a name's value; a name assigned again in the same scope keeps its smallest."""
    if value is not None:
        names[name] = min(names[name], value) if name in defined else value
        defined.add(name)


def _module_names(tree: ast.Module) -> tuple[dict[str, float], dict[str, str]]:
    """The module's numeric names, and what each name imported at its top stands for: a module of ``MODULES``
    under another name (``{"aio": "asyncio"}``), or a form or clock imported from one (``{"within":
    "asyncio.timeout"}``)."""
    names: dict[str, float] = {}
    imports: dict[str, str] = {}
    defined: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == SUPPORT:
            for alias in node.names:
                if alias.name in SHARED:
                    _keep_least(names, alias.asname or alias.name, SHARED[alias.name], defined)
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in MODULES and alias.asname:
                    imports[alias.asname] = alias.name
        if isinstance(node, ast.ImportFrom) and node.module == "concurrent":
            for alias in node.names:
                if alias.name == "futures":
                    imports[alias.asname or alias.name] = "concurrent.futures"
        if isinstance(node, ast.ImportFrom) and node.module in MODULES:
            for alias in node.names:
                imports[alias.asname or alias.name] = f"{node.module}.{alias.name}"
        if assigned := _assigned(node):
            _keep_least(names, assigned[0], _number(assigned[1], names), defined)
    return names, imports


def _is_clock(func: ast.AST, imports: dict[str, str]) -> bool:
    """``time.monotonic``, ``time.perf_counter`` (also imported under another name) or a loop's ``time``; not
    ``time.time``, the wall clock, under any name."""
    if isinstance(func, ast.Name) and imports.get(func.id) in ("time.monotonic", "time.perf_counter"):
        return True
    name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
    if name in CLOCKS:
        return True
    if name != "time" or not isinstance(func, ast.Attribute):
        return False
    owner = ast.unparse(func.value)
    return owner != "time" and imports.get(owner) != "time"


def _scope(
    functions: list[_Function], base: dict[str, float], imports: dict[str, str]
) -> tuple[dict[str, float], set[str]]:
    """The numeric names an enclosing function chain sees, and the names that hold a clock's reading."""
    names = dict(base)
    clocks: set[str] = set()
    for function in functions:  # outermost first, so an inner scope's name wins
        defined: set[str] = set()
        arguments = function.args
        positional = arguments.posonlyargs + arguments.args
        defaulted = zip(positional[len(positional) - len(arguments.defaults):], arguments.defaults)
        for argument, default in [*defaulted, *zip(arguments.kwonlyargs, arguments.kw_defaults)]:
            _keep_least(names, argument.arg, _number(default, names), defined)
        for node in _own_nodes(function):
            if assigned := _assigned(node):
                _keep_least(names, assigned[0], _number(assigned[1], names), defined)
                if isinstance(assigned[1], ast.Call) and _is_clock(assigned[1].func, imports):
                    clocks.add(assigned[0])
    return names, clocks


def _keyword(call: ast.Call, name: str) -> ast.AST | None:
    return next((keyword.value for keyword in call.keywords if keyword.arg == name), None)


def _is_flag(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, bool)


def _own_nodes(function: _Function):
    """The nodes of a function's own body: a nested def's, class's or lambda's assignments are their own scope's."""
    pending = list(ast.iter_child_nodes(function))
    while pending:
        node = pending.pop()
        yield node
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            pending.extend(ast.iter_child_nodes(node))


def _reads_clock(node: ast.AST, clocks: set[str], imports: dict[str, str]) -> bool:
    return (isinstance(node, ast.Call) and _is_clock(node.func, imports)) or (
        isinstance(node, ast.Name) and node.id in clocks)


def _poll_step(loop: ast.For) -> ast.AST | None:
    """The step a polling loop's body sleeps, if the body sleeps and can leave early (``break`` or ``return``),
    outside any function it defines; a loop that always runs out paces work rather than waiting for it."""
    step, leaves = None, False
    pending = list(loop.body)
    while pending:
        node = pending.pop(0)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        leaves = leaves or isinstance(node, (ast.Break, ast.Return))
        if step is None and isinstance(node, ast.Call) and node.args and (
                getattr(node.func, "attr", getattr(node.func, "id", "")) == "sleep"):
            step = node.args[0]
        pending.extend(ast.iter_child_nodes(node))
    return step if leaves else None


def _bound(node: ast.AST, imports: dict[str, str], clocks: set[str]) -> tuple[str, ast.AST | None] | None:
    """The form of a timed wait and its bound's expression (for a counted poll, the count and step), else None."""
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        for side, other in ((node.left, node.right), (node.right, node.left)):
            if _reads_clock(side, clocks, imports):
                return "deadline", other
        return None
    if isinstance(node, ast.While) and isinstance(node.test, ast.Compare) and len(node.test.ops) == 1:
        left = node.test.left
        if (isinstance(node.test.ops[0], (ast.Lt, ast.LtE)) and isinstance(left, ast.BinOp)
                and isinstance(left.op, ast.Sub) and _reads_clock(left.left, clocks, imports)):
            return "elapsed poll", node.test.comparators[0]
        return None
    if isinstance(node, ast.For) and isinstance(node.iter, ast.Call) and getattr(node.iter.func, "id", "") == "range":
        step = _poll_step(node)
        count = node.iter.args[-1] if len(node.iter.args) == 1 else None
        return ("counted poll", ast.BinOp(left=count, op=ast.Mult(), right=step)) if count and step else None
    if not isinstance(node, ast.Call):
        return None
    func = node.func
    name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
    receiver = ast.unparse(func.value) if isinstance(func, ast.Attribute) else ""
    if imports.get(receiver) in MODULES:
        receiver = imports[receiver]
    if isinstance(func, ast.Name) and name in imports and imports[name] not in MODULES:
        receiver, name = imports[name].rsplit(".", 1)
    args = node.args
    timeout = _keyword(node, "timeout")
    if name == "wait_for":
        return "wait_for", args[1] if len(args) > 1 else timeout
    if name == "timeout" and receiver == "asyncio":
        return "asyncio.timeout", args[0] if args else _keyword(node, "delay")
    if name in ("wait", "as_completed") and receiver in ("asyncio", "futures", "concurrent.futures"):
        return f"{'asyncio' if receiver == 'asyncio' else 'futures'}.{name}", timeout
    if name in ("wait", "join", "result"):
        return name, timeout if timeout is not None else (args[0] if args else None)
    if name in ("get", "acquire"):
        return name, timeout if timeout is not None else (args[1] if len(args) > 1 and _is_flag(args[0]) else None)
    if name == "put":
        return name, timeout if timeout is not None else (args[2] if len(args) > 2 and _is_flag(args[1]) else None)
    if name in SUBPROCESS_WAITS and receiver == "subprocess":
        return f"subprocess.{name}", timeout
    if name in ("communicate", "urlopen"):
        return name, timeout
    if name == "Barrier":
        return "Barrier", args[2] if len(args) > 2 else timeout
    if name == "to_thread" and args and getattr(args[0], "attr", "") in THREAD_WAITS:
        return "to_thread", args[1] if len(args) > 1 else timeout
    if name == "run_in_executor" and len(args) > 1 and getattr(args[1], "attr", "") in THREAD_WAITS:
        return "run_in_executor", args[2] if len(args) > 2 else None
    return None


def _parameter_bounds(
    tree: ast.Module, imports: dict[str, str], base: dict[str, float]
) -> dict[str, list[tuple[_Function, ast.AST, set[str], dict[str, float]]]]:
    """For each function name, the waits in functions of that name whose bound reads one of their parameters (a
    timeout, a deadline's offset, a poll's count or step): the function, the bound's expression, the parameters it
    reads, and the function's own names, its defaults included."""
    helpers: dict[str, list[tuple[_Function, ast.AST, set[str], dict[str, float]]]] = {}
    for function in ast.walk(tree):
        if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        arguments = function.args
        parameters = {a.arg for a in arguments.posonlyargs + arguments.args + arguments.kwonlyargs}
        own, clocks = _scope([function], base, imports)
        for node in ast.walk(function):
            hit = _bound(node, imports, clocks)
            if hit is None or hit[1] is None:
                continue
            read = {name.id for name in ast.walk(hit[1]) if isinstance(name, ast.Name)} & parameters
            if read:
                helpers.setdefault(function.name, []).append((function, hit[1], read, own))
    return helpers


def _passed(call: ast.Call, function: _Function, parameter: str) -> ast.AST | None:
    """What a call passes for a parameter, by keyword or by position (a method's ``self`` or ``cls`` skipped)."""
    if (value := _keyword(call, parameter)) is not None:
        return value
    positional = [a.arg for a in function.args.posonlyargs + function.args.args]
    if positional[:1] in (["self"], ["cls"]) and isinstance(call.func, ast.Attribute):
        positional = positional[1:]
    index = positional.index(parameter) if parameter in positional else len(call.args)
    return call.args[index] if index < len(call.args) else None


def _passed_bound(
    call: ast.Call, helper: tuple[_Function, ast.AST, set[str], dict[str, float]], names: dict[str, float]
) -> float | None:
    """A helper's bound with the values a call passes for its parameters, resolved in the caller's scope; None when
    the call passes none of them (the wait's own reading covers its defaults) or one does not resolve."""
    function, expression, read, own = helper
    passed = {parameter: _passed(call, function, parameter) for parameter in read}
    if all(value is None for value in passed.values()):
        return None
    values = dict(own)
    for parameter, value in passed.items():
        if value is None:
            continue
        resolved = _number(value, names)
        if resolved is None:
            return None
        values[parameter] = resolved
    return _number(expression, values)


def timed_waits(path: str, text: str) -> list[tuple[str, int, str, float]]:
    """Each timed wait in one file whose bound resolves to a number: (top-level definition, line, form, seconds)."""
    tree = ast.parse(text)
    base, imports = _module_names(tree)
    helpers = _parameter_bounds(tree, imports, base)
    found: list[tuple[str, int, str, float]] = []

    def visit(node: ast.AST, functions: list[_Function], top: str, scope: tuple[dict[str, float], set[str]]) -> None:
        names, clocks = scope
        for child in ast.iter_child_nodes(node):
            hit = _bound(child, imports, clocks)
            if hit is not None and hit[1] is not None and (seconds := _number(hit[1], names)) is not None:
                found.append((top, child.lineno, hit[0], seconds))
            # A helper is called by its name, or as a method on self or cls.
            if isinstance(child, ast.Call) and (isinstance(child.func, ast.Name) or (
                    isinstance(child.func, ast.Attribute) and ast.unparse(child.func.value) in ("self", "cls"))):
                called = child.func.attr if isinstance(child.func, ast.Attribute) else child.func.id
                for helper in helpers.get(called, []):
                    if (seconds := _passed_bound(child, helper, names)) is not None:
                        found.append((top, child.lineno, f"{called}()", seconds))
            entered = isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            nested = functions + [child] if entered else functions
            named = isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            visit(child, nested, child.name if top == "<module>" and named else top,
                  _scope(nested, base, imports) if entered else scope)

    visit(tree, [], "<module>", (dict(base), set()))
    return sorted(found, key=lambda site: site[1])


def short_waits(path: str, text: str) -> list[tuple[str, int, str, float]]:
    return [site for site in timed_waits(path, text) if site[3] < FLOOR_S]


def _tracked() -> dict[str, str]:
    listing = subprocess.run(  # nosec B603 B607 - git on this checkout, fixed arguments
        ["git", "ls-files", "-z", "tests"], cwd=BACKEND, capture_output=True, check=True
    ).stdout.decode("utf-8")
    return {
        path: (BACKEND / path).read_text(encoding="utf-8")
        for path in filter(None, listing.split("\0"))
        if path.endswith(".py") and (BACKEND / path).is_file()
    }


PLANTED = '''\
import asyncio, threading, time
from tests.support.hang_guard import HANG_GUARD_S
SHORT = 2
LONG = SHORT * 10
async def test_planted(event, thread, future, lock, queue, loop, condition):
    await asyncio.wait_for(event.wait(), 1)
    await asyncio.wait_for(event.wait(), timeout=LONG)
    await asyncio.wait_for(event.wait(), HANG_GUARD_S)
    async with asyncio.timeout(SHORT):
        pass
    async with asyncio.timeout(None):
        pass
    await asyncio.wait({future}, timeout=0.3)
    assert event.wait(0.5) and condition.wait_for(lambda: True, 3)
    thread.join(timeout=4)
    thread.join()
    ", ".join(["not", "a", "wait"])
    future.result(5)
    lock.acquire(timeout=6)
    queue.get(timeout=HANG_GUARD_S / 2)
    {"key": 1}.get("key", 0)
    threading.Barrier(3, timeout=7)
    await asyncio.to_thread(event.wait, 8)
    await loop.run_in_executor(None, event.wait, 9)
    deadline = time.monotonic() + SHORT / 4
    budget = loop.time() + 2
    stamp = time.time() + 1
def helper(event, bound=2.5, seconds=None):
    local = 0.25
    event.wait(bound)
    event.wait(local)
    event.wait(seconds)
class Planted:
    def method(self, event):
        return event.wait(timeout=-1 + 3)
'''

PLANTED_MORE = '''\
import asyncio, subprocess, time
from asyncio import timeout as within
from concurrent import futures
from concurrent.futures import wait as wait_all
from tests.support.hang_guard import HANG_GUARD_S
GUARD = HANG_GUARD_S
GUARD = 3
async def test_more(queue, lock, pool, process, fs, event):
    subprocess.run(["true"], timeout=5)
    subprocess.check_output(["true"], timeout=HANG_GUARD_S)
    process.communicate(timeout=4)
    futures.wait(fs, timeout=1)
    wait_all(fs, timeout=2)
    queue.get(True, 1)
    lock.acquire(False, 1.5)
    queue.put("item", True, 2)
    async with within(1):
        pass
    started = time.monotonic()
    deadline = started + 2
    late = time.perf_counter() + 3
    while time.monotonic() - started < 4:
        await asyncio.sleep(0.01)
    for _ in range(200):
        if event.is_set():
            break
        await asyncio.sleep(0.01)
    for _ in range(int(HANG_GUARD_S * 100)):
        if event.is_set():
            return
        await asyncio.sleep(0.01)
    for _ in range(3):
        await asyncio.sleep(0.01)
    event.wait(GUARD)
    call(["not", "a", "child"], timeout=1)
def _waited(event, within_s):
    return event.wait(within_s)
def test_callers(event):
    _waited(event, 0.5)
    _waited(event, within_s=HANG_GUARD_S)
'''

PLANTED_ALIASES = '''\
import asyncio as aio
import subprocess as sp
import concurrent.futures as cf
import time as t
from concurrent import futures as pool_futures
from time import monotonic as clock
async def test_aliases(fs, event):
    async with aio.timeout(1):
        pass
    sp.run(["true"], timeout=2)
    cf.wait(fs, timeout=3)
    pool_futures.as_completed(fs, timeout=4)
    deadline = clock() + 5
    stamp = t.time() + 6
    late = t.monotonic() + 7
def _poll(event, polls=3000):
    for _ in range(polls):
        if event.is_set():
            break
        t.sleep(0.01)
def _deadline(within_s=30):
    started = t.monotonic()
    return started + within_s
def test_helper_calls(event):
    _poll(event, polls=200)
    _poll(event)
    _deadline(within_s=0.5)
    _deadline()
from subprocess import run as run_child
import subprocess
SHORT = 1.5
def test_more_forms(event):
    subprocess.check_call(["true"], timeout=2)
    subprocess.call(["true"], timeout=3)
    run_child(["true"], timeout=4)
    event.wait(float(SHORT))
    begun = t.monotonic()
    while t.monotonic() - begun <= 6:
        t.sleep(0.01)
class Waiter:
    def _wait_for(self, event, within_s):
        return event.wait(within_s)
    def check(self, event):
        self._wait_for(event, 0.25)
'''

PLANTED_LEAST = '''\
from tests.support.hang_guard import HANG_GUARD_S
EARLY = 3
EARLY = HANG_GUARD_S
def test_least(event, other):
    event.wait(EARLY)
    bound = 2
    event.wait(bound)
    bound = 30
    def nested():
        EARLY = 60
    class Fake:
        bound = 90
    other.wait(EARLY)
'''


def test_the_scan_reads_every_planted_form_of_a_bound():
    assert timed_waits("tests/planted.py", PLANTED) == [
        ("test_planted", 6, "wait_for", 1.0),
        ("test_planted", 7, "wait_for", 20.0),
        ("test_planted", 8, "wait_for", 30.0),
        ("test_planted", 9, "asyncio.timeout", 2.0),
        ("test_planted", 13, "asyncio.wait", 0.3),
        ("test_planted", 14, "wait", 0.5),
        ("test_planted", 14, "wait_for", 3.0),
        ("test_planted", 15, "join", 4.0),
        ("test_planted", 18, "result", 5.0),
        ("test_planted", 19, "acquire", 6.0),
        ("test_planted", 20, "get", 15.0),
        ("test_planted", 22, "Barrier", 7.0),
        ("test_planted", 23, "to_thread", 8.0),
        ("test_planted", 24, "run_in_executor", 9.0),
        ("test_planted", 25, "deadline", 0.5),
        ("test_planted", 26, "deadline", 2.0),
        ("helper", 30, "wait", 2.5),
        ("helper", 31, "wait", 0.25),
        ("Planted", 35, "wait", 2.0),
    ]
    assert [site[1] for site in short_waits("tests/planted.py", PLANTED)] == [
        6, 9, 13, 14, 14, 15, 18, 19, 22, 23, 24, 25, 26, 30, 31, 35
    ]


def test_the_scan_reads_child_processes_polls_imported_forms_and_bounds_passed_to_helpers():
    assert timed_waits("tests/planted_more.py", PLANTED_MORE) == [
        ("test_more", 9, "subprocess.run", 5.0),
        ("test_more", 10, "subprocess.check_output", 30.0),
        ("test_more", 11, "communicate", 4.0),
        ("test_more", 12, "futures.wait", 1.0),
        ("test_more", 13, "futures.wait", 2.0),
        ("test_more", 14, "get", 1.0),
        ("test_more", 15, "acquire", 1.5),
        ("test_more", 16, "put", 2.0),
        ("test_more", 17, "asyncio.timeout", 1.0),
        ("test_more", 20, "deadline", 2.0),
        ("test_more", 21, "deadline", 3.0),
        ("test_more", 22, "elapsed poll", 4.0),
        ("test_more", 24, "counted poll", 2.0),
        ("test_more", 28, "counted poll", 30.0),
        ("test_more", 34, "wait", 3.0),
        ("test_callers", 39, "_waited()", 0.5),
        ("test_callers", 40, "_waited()", 30.0),
    ]


def test_the_scan_reads_module_and_clock_aliases_and_the_counts_and_deadlines_a_helper_is_passed():
    # The wall clock under another name stays unread (line 14), and a helper called with its defaults is read once, at
    # its own wait (lines 17 and 23), not again at each call.
    assert timed_waits("tests/planted_aliases.py", PLANTED_ALIASES) == [
        ("test_aliases", 8, "asyncio.timeout", 1.0),
        ("test_aliases", 10, "subprocess.run", 2.0),
        ("test_aliases", 11, "futures.wait", 3.0),
        ("test_aliases", 12, "futures.as_completed", 4.0),
        ("test_aliases", 13, "deadline", 5.0),
        ("test_aliases", 15, "deadline", 7.0),
        ("_poll", 17, "counted poll", 30.0),
        ("_deadline", 23, "deadline", 30.0),
        ("test_helper_calls", 25, "_poll()", 2.0),
        ("test_helper_calls", 27, "_deadline()", 0.5),
        ("test_more_forms", 33, "subprocess.check_call", 2.0),
        ("test_more_forms", 34, "subprocess.call", 3.0),
        ("test_more_forms", 35, "subprocess.run", 4.0),
        ("test_more_forms", 36, "wait", 1.5),
        ("test_more_forms", 38, "elapsed poll", 6.0),
        ("Waiter", 44, "_wait_for()", 0.25),
    ]


def test_a_name_assigned_twice_resolves_to_its_smallest_value_in_its_own_scope_only():
    # The smaller value comes first, so reading the last one would give 30 s at lines 5 and 7. A nested def's or class's
    # own assignment (lines 10 and 12) is not the enclosing function's, so line 13 still reads the module's 3 s.
    assert timed_waits("tests/planted_least.py", PLANTED_LEAST) == [
        ("test_least", 5, "wait", 3.0),
        ("test_least", 7, "wait", 2.0),
        ("test_least", 13, "wait", 3.0),
    ]


def test_the_shared_guard_clears_the_floor():
    assert HANG_GUARD_S >= FLOOR_S
    assert all(reason.strip() for _, reason in SHORT_ON_PURPOSE.values())
    assert all(seconds < FLOOR_S for _, _, _, seconds in SHORT_ON_PURPOSE)


def test_every_short_bound_under_tests_is_listed_as_short_on_purpose():
    found: Counter[tuple[str, str, str, float]] = Counter()
    sites: dict[tuple[str, str, str, float], list[str]] = {}
    for path, text in sorted(_tracked().items()):
        for top, line, form, seconds in short_waits(path, text):
            found[(path, top, form, seconds)] += 1
            sites.setdefault((path, top, form, seconds), []).append(f"{path}:{line} {form} {seconds:g}s")
    listed = {key: count for key, (count, _) in SHORT_ON_PURPOSE.items()}
    unlisted = [site for key in sorted(found) if found[key] != listed.get(key) for site in sites[key]]
    gone = sorted(key for key in listed if key not in found)
    assert not unlisted and not gone, (
        "a wait for work that should finish takes HANG_GUARD_S (tests/support/hang_guard.py), or a bound of its own "
        f"of at least {FLOOR_S:g} s; list a bound that is short on purpose in SHORT_ON_PURPOSE with why.\n"
        + "\n".join(unlisted) + ("\nlisted but not found: " + repr(gone) if gone else "")
    )
