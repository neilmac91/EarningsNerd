"""A backend test's bound on a wait for work that should finish only breaks a hang; it never times the work.

On a starved CI runner, work that takes milliseconds alone stretches to seconds, and a short bound on a wait for it
fails a correct run: a one-second ``asyncio.wait_for`` failed main's CI so on 2026-11-04 (``a20c02079``). A defect
the test guards fails it at any bound, by an assertion or by hanging until the bound. So such a wait takes
``HANG_GUARD_S`` from ``tests/support/hang_guard.py``, or a bound of its own of at least ``FLOOR_S`` where production
code would end the wait sooner (``lessons/test-a-wait-bound-only-breaks-a-hang.md``).

This gate reads every tracked Python file under ``backend/tests`` for a timed wait and resolves its bound to a number:
a literal, a module constant (``HANG_GUARD_S`` imported from the support module included), a parameter's default or a
local assignment in an enclosing function, or arithmetic on those. The forms it reads:
- ``wait_for(awaitable, bound)`` (``asyncio``'s and ``threading.Condition``'s), ``asyncio.timeout(bound)``,
  ``asyncio.wait(..., timeout=bound)``;
- ``.wait(bound)``, ``.join(bound)`` and ``.result(bound)``, or with ``timeout=``; ``.get``, ``.put`` and
  ``.acquire`` with ``timeout=``; ``Barrier(parties, action, bound)`` or with ``timeout=``;
- a wait handed to a thread with its bound: ``asyncio.to_thread(event.wait, bound)``,
  ``loop.run_in_executor(executor, event.wait, bound)``;
- a polling deadline, ``time.monotonic() + bound`` or ``loop.time() + bound``.

A bound under ``FLOOR_S`` is short on purpose only where the case needs it: a negative window (the case asserts that
something does not happen within it), a timing assertion (the bound is the property under test), a polling step, or
pacing. Each such site is listed in ``SHORT_ON_PURPOSE`` by file and top-level definition, with its reason, and a new
one fails here until it is listed.

What it does not read: a bound it cannot resolve to a number (a parameter with no default, an attribute, a call, a
patched setting); a wait with no bound; an alias of a wait form (``real_timeout = asyncio.timeout``); a pool's
``pool_timeout``, which ``lessons/test-a-burst-pool-timeout-breaks-a-deadlock-and-detects-nothing.md`` covers and
which some cases set short on purpose; and an elapsed-time assertion (``time.monotonic() - started < bound``).
``.join`` with an argument that is not a number is ``str.join``. Whether a guard stays below a production timeout
that would end the same wait, and whether nested bounds stay in order, is review-checked.
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
_OPS = {
    ast.Add: lambda left, right: left + right,
    ast.Sub: lambda left, right: left - right,
    ast.Mult: lambda left, right: left * right,
    ast.Div: lambda left, right: left / right,
}

# (file under backend/, top-level definition) -> (sites, why each is short on purpose).
_LOCKOUT = "tests/integration/test_login_lockout_transactions.py"
_PROGRESS = "tests/integration/test_summary_progress_transactions.py"
_OWNERSHIP = "tests/unit/test_durable_request_ownership.py"
_OVERLAP = "tests/unit/test_summary_enrichment_overlap.py"
SHORT_ON_PURPOSE: dict[tuple[str, str], tuple[int, str]] = {
    (_LOCKOUT, "test_failure_waiting_on_success_clear_records_against_committed_state"): (
        1, "negative window: the failure's upsert is still blocked on the uncommitted clear, inside statement_timeout"),
    ("tests/integration/test_summary_job_transactions.py", "_LateRelease"): (
        1, "polling step: the late mode's watcher reads pg_locks every 10 ms, how long a waiter stays blocked"),
    (_PROGRESS, "test_a_write_behind_an_uncommitted_clear_waits_and_follows_its_outcome"): (
        1, "negative window: the write is still blocked on the uncommitted clear, inside statement_timeout"),
    (_PROGRESS, "test_a_mark_behind_an_uncommitted_holder_waits_and_follows_its_outcome"): (
        1, "negative window: the stale mark is still blocked on the uncommitted holder, inside statement_timeout"),
    ("tests/integration/test_usage_counter_transactions.py",
     "test_postgres_counter_lock_wait_is_bounded_and_failure_does_not_increment"): (
        1, "timing assertion: the patched lock_timeout ends the counter's lock wait within 1.5 s"),
    (_OWNERSHIP, "test_summary_disconnect_joins_actual_worker_before_releasing_leadership"): (
        1, "negative window: the cancelled request does not end while its worker still runs"),
    (_OWNERSHIP, "test_summary_disconnect_joins_the_section_parse_worker_before_releasing_leadership"): (
        1, "negative window: the cancelled request does not end while its section parse still runs"),
    ("tests/unit/test_event_loop_safety.py", "TestCacheOperationTimeouts"): (
        1, "timing assertion: CACHE_OPERATION_TIMEOUT (2 s) cuts a 10 s cache call within 3 s (vacuous today: E314)"),
    ("tests/unit/test_filing_source_storage.py",
     "test_cancellation_kills_native_child_and_holds_single_permit_through_reap"): (
        1, "negative window: a second put gets no permit while the cancelled put's reap holds it"),
    ("tests/unit/test_provider_admission.py", "test_chat_wait_is_bounded_by_its_own_deadline_and_leaks_no_slot"): (
        1, "timing assertion: the waiter's own 0.05 s budget, not a later one, rejects it within 2 s"),
    ("tests/unit/test_secret_scan_guard.py", "test_a_scan_past_its_deadline_refuses"): (
        1, "timing assertion: the scan's deadline is the property under test, below the stub's 5 s sleep"),
    ("tests/unit/test_summary_delivery_acceptance.py",
     "test_whole_http_deadline_interrupts_real_header_and_body_trickles"): (
        1, "pacing: each trickled byte waits 30 ms, under the client's socket inactivity timeout"),
    (_OVERLAP, "test_the_statement_parse_waits_for_its_own_excerpt_build"): (
        1, "negative window: no statement parse starts during the excerpt build"),
    (_OVERLAP, "test_the_xbrl_write_finishes_before_the_provider_request"): (
        1, "negative window: no provider request starts during the XBRL write"),
    (_OVERLAP, "test_a_disconnect_during_the_excerpt_build_cancels_the_pending_statement_parse"): (
        1, "negative window: no leaked statement task runs after the disconnect"),
    ("tests/unit/test_summary_worker_http_isolation.py", "_ready"): (
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
    return None


def _assigned(node: ast.AST) -> tuple[str, ast.AST] | None:
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        return node.targets[0].id, node.value
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
        return node.target.id, node.value
    return None


def _module_names(tree: ast.Module) -> dict[str, float]:
    names: dict[str, float] = {}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == SUPPORT:
            for alias in node.names:
                if alias.name in SHARED:
                    names[alias.asname or alias.name] = SHARED[alias.name]
        if (assigned := _assigned(node)) and (value := _number(assigned[1], names)) is not None:
            names[assigned[0]] = value
    return names


def _scope_names(functions: list[ast.FunctionDef | ast.AsyncFunctionDef], base: dict[str, float]) -> dict[str, float]:
    names = dict(base)
    for function in functions:  # outermost first, so an inner scope's name wins
        arguments = function.args
        positional = arguments.posonlyargs + arguments.args
        defaulted = zip(positional[len(positional) - len(arguments.defaults):], arguments.defaults)
        for argument, default in [*defaulted, *zip(arguments.kwonlyargs, arguments.kw_defaults)]:
            if (value := _number(default, names)) is not None:
                names[argument.arg] = value
        for node in ast.walk(function):
            if (assigned := _assigned(node)) and (value := _number(assigned[1], names)) is not None:
                names[assigned[0]] = value
    return names


def _is_clock(func: ast.AST) -> bool:
    """``time.monotonic`` or a loop's ``time``; ``time.time()`` is the wall clock, which stamps rather than waits."""
    name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
    if name == "monotonic":
        return True
    return name == "time" and isinstance(func, ast.Attribute) and ast.unparse(func.value) != "time"


def _keyword(call: ast.Call, name: str) -> ast.AST | None:
    return next((keyword.value for keyword in call.keywords if keyword.arg == name), None)


def _bound(node: ast.AST) -> tuple[str, ast.AST | None] | None:
    """The form of a timed wait and its bound's expression, else None."""
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        for side, other in ((node.left, node.right), (node.right, node.left)):
            if isinstance(side, ast.Call) and _is_clock(side.func):
                return "deadline", other
        return None
    if not isinstance(node, ast.Call):
        return None
    func = node.func
    name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
    receiver = ast.unparse(func.value) if isinstance(func, ast.Attribute) else ""
    args = node.args
    if name == "wait_for":
        return "wait_for", args[1] if len(args) > 1 else _keyword(node, "timeout")
    if name == "timeout" and receiver == "asyncio":
        return "asyncio.timeout", args[0] if args else _keyword(node, "delay")
    if name == "wait" and receiver == "asyncio":
        return "asyncio.wait", _keyword(node, "timeout")
    if name in ("wait", "join", "result"):
        return name, args[0] if args else _keyword(node, "timeout")
    if name in ("get", "put", "acquire"):
        return name, _keyword(node, "timeout")
    if name == "Barrier":
        return "Barrier", args[2] if len(args) > 2 else _keyword(node, "timeout")
    if name == "to_thread" and args and getattr(args[0], "attr", "") in THREAD_WAITS:
        return "to_thread", args[1] if len(args) > 1 else _keyword(node, "timeout")
    if name == "run_in_executor" and len(args) > 1 and getattr(args[1], "attr", "") in THREAD_WAITS:
        return "run_in_executor", args[2] if len(args) > 2 else None
    return None


def timed_waits(path: str, text: str) -> list[tuple[str, int, str, float]]:
    """Each timed wait in one file whose bound resolves to a number: (top-level definition, line, form, seconds)."""
    tree = ast.parse(text)
    base = _module_names(tree)
    found: list[tuple[str, int, str, float]] = []

    def visit(node: ast.AST, functions: list, top: str) -> None:
        for child in ast.iter_child_nodes(node):
            hit = _bound(child)
            if hit is not None and hit[1] is not None:
                seconds = _number(hit[1], _scope_names(functions, base))
                if seconds is not None:
                    found.append((top, child.lineno, hit[0], seconds))
            nested = functions + [child] if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) else functions
            named = isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            visit(child, nested, child.name if top == "<module>" and named else top)

    visit(tree, [], "<module>")
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


def test_the_shared_guard_clears_the_floor():
    assert HANG_GUARD_S >= FLOOR_S
    assert all(reason.strip() for _, reason in SHORT_ON_PURPOSE.values())


def test_every_short_bound_under_tests_is_listed_as_short_on_purpose():
    found: Counter[tuple[str, str]] = Counter()
    sites: dict[tuple[str, str], list[str]] = {}
    for path, text in sorted(_tracked().items()):
        for top, line, form, seconds in short_waits(path, text):
            found[(path, top)] += 1
            sites.setdefault((path, top), []).append(f"{path}:{line} {form} {seconds:g}s")
    listed = {key: count for key, (count, _) in SHORT_ON_PURPOSE.items()}
    unlisted = [site for key in sorted(found) if found[key] != listed.get(key) for site in sites[key]]
    gone = sorted(key for key in listed if key not in found)
    assert not unlisted and not gone, (
        f"a wait for work that should finish takes HANG_GUARD_S (tests/support/hang_guard.py), or a bound of its own of "
        f"at least {FLOOR_S:g} s; list a bound that is short on purpose in SHORT_ON_PURPOSE with why.\n"
        + "\n".join(unlisted) + ("\nlisted but not found: " + repr(gone) if gone else "")
    )
