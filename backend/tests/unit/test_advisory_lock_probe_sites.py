"""A test proves that a closed session freed its advisory lock by waiting for it.

PostgreSQL frees a session's advisory lock when the session's backend exits, and that comes after the client's close
returns. On a busy runner, a probe that does not wait can run before that exit and find the lock still held: #1990's
`migrations-postgres` run failed so, in `tests/integration/test_summary_job_transactions.py`. A test that proves the
lock is free takes it with the blocking `pg_advisory_xact_lock`, under a statement timeout that bounds the wait
(`lessons/test-wait-for-a-closed-sessions-advisory-lock.md`).

A probe that does not wait is sound only while a live session holds the lock and the test asserts that it fails. This
gate holds every line, in every tracked file under `backend/tests/`, that names one of PostgreSQL's non-blocking
advisory-lock functions (in code, a string or a comment) to the exact list below, by file and by the top-level
definition around it. In Python source, each call of one sits inside an `assert not`, so no helper can hand its result
to a check that it succeeded. A new probe fails here until it is listed, with why it cannot race a close.
"""

from __future__ import annotations

import ast
import re
import subprocess  # nosec B404 - runs git ls-files on this checkout, fixed arguments
from collections import Counter
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
# Joined here, so that no line of this module names a probe.
PROBE = re.compile("pg_try" + "_advisory")

# (file under backend/, top-level definition or "<file>") -> the lines that name a probe there. Each probe runs while
# a live session holds the lock, and its case asserts that the probe fails.
HELD_LOCK_PROBES: dict[tuple[str, str], int] = {
    # The recovery cases' one probe, run while the pass under test holds the lock.
    ("tests/integration/test_summary_job_transactions.py", "_assert_held_elsewhere"): 1,
    # The child's observer, in the case's script: it probes before the pass releases its lock and reports `not got`.
    ("tests/integration/test_summary_job_transactions.py", "test_asyncio_run_shutdown_finishes_recovery_disconnect"): 1,
}


def _definitions(tree: ast.Module) -> list[tuple[int, int, str]]:
    spans = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            start = min([node.lineno, *(decorator.lineno for decorator in node.decorator_list)])
            spans.append((start, node.end_lineno or node.lineno, node.name))
    return spans


def probe_lines(path: str, text: str) -> Counter[tuple[str, str]]:
    """The lines of one file that name a probe, counted by the top-level definition around each, else ``<file>``."""
    numbers = [number for number, line in enumerate(text.splitlines(), 1) if PROBE.search(line)]
    spans = _definitions(ast.parse(text)) if numbers and path.endswith(".py") else []
    return Counter(
        (path, next((name for start, end, name in spans if start <= number <= end), "<file>")) for number in numbers
    )


def unasserted_probe_calls(path: str, text: str) -> list[str]:
    """Each call of a probe in Python source that is not inside an ``assert not``, as ``file:line``."""
    tree = ast.parse(text)
    negated: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assert) and isinstance(node.test, ast.UnaryOp) and isinstance(node.test.op, ast.Not):
            negated.update(id(inner) for inner in ast.walk(node.test.operand))
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
            if PROBE.match(name) and id(node) not in negated:
                found.append((node.lineno, f"{path}:{node.lineno}"))
    return [site for _, site in sorted(found)]


def _tracked() -> dict[str, str]:
    listing = subprocess.run(  # nosec B603 B607 - git on this checkout, fixed arguments
        ["git", "ls-files", "-z", "tests"], cwd=BACKEND, capture_output=True, check=True
    ).stdout.decode("utf-8")
    files = {}
    for path in filter(None, listing.split("\0")):
        target = BACKEND / path
        if target.is_file():
            files[path] = target.read_bytes().decode("utf-8", errors="replace")
    return files


PLANTED = '''\
QUERY = "SELECT @@_lock(1)"
@case("@@_xact_lock")
def test_planted(probe):
    # @@_lock_shared, named in a comment
    assert probe.execute(select(func.@@_lock(KEY))).scalar_one()
    assert not probe.execute(select(func.@@_xact_lock(KEY))).scalar_one()
    probe.execute(select(func.pg_advisory_xact_lock(KEY)))
class Planted:
    def helper(self, probe):
        return probe.execute(select(func.@@_lock(KEY))).scalar_one()
'''.replace("@@", "pg_try" + "_advisory")


def test_the_scan_reads_every_planted_form_of_a_probe():
    assert probe_lines("tests/planted.py", PLANTED) == Counter({
        ("tests/planted.py", "<file>"): 1,
        ("tests/planted.py", "test_planted"): 4,
        ("tests/planted.py", "Planted"): 1,
    })
    sql = "SELECT 1;\nSELECT @@_lock(7);\n".replace("@@", "pg_try" + "_advisory")
    assert probe_lines("tests/fixtures/planted.sql", sql) == Counter({("tests/fixtures/planted.sql", "<file>"): 1})
    assert unasserted_probe_calls("tests/planted.py", PLANTED) == ["tests/planted.py:5", "tests/planted.py:10"]
    # The blocking wait is no probe, and this module names none, so it can never count itself.
    wait = "def test_wait(probe):\n    probe.execute(select(func.pg_advisory_xact_lock(KEY)))\n"
    assert probe_lines("tests/wait.py", wait) == Counter()
    assert probe_lines("tests/unit/test_advisory_lock_probe_sites.py", Path(__file__).read_text()) == Counter()


def test_the_recovery_cases_also_run_with_late_releases():
    # The late mode guards the recovery cases only while it runs, so its fixture's params must keep it. What the mode
    # does when it runs is pinned by test_late_mode_frees_a_released_lock_only_for_a_waiter.
    tree = ast.parse((BACKEND / "tests/integration/test_summary_job_transactions.py").read_text(encoding="utf-8"))
    (fixture,) = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "recovery_guard"]
    (decorator,) = fixture.decorator_list
    assert ast.unparse(decorator) == "pytest.fixture(params=['prompt', 'late'])"


def test_every_probe_under_tests_is_a_listed_check_of_a_held_lock():
    found: Counter[tuple[str, str]] = Counter()
    unasserted: list[str] = []
    for path, text in sorted(_tracked().items()):
        if PROBE.search(text):
            found += probe_lines(path, text)
            if path.endswith(".py"):
                unasserted += unasserted_probe_calls(path, text)
    assert dict(found) == HELD_LOCK_PROBES, (
        "a probe that does not wait was added or moved; to prove a closed session freed its lock, wait for it with "
        "pg_advisory_xact_lock (lessons/test-wait-for-a-closed-sessions-advisory-lock.md), or list a check of a held lock"
    )
    assert unasserted == [], "each probe call must sit inside an `assert not`: a live session holds the lock"
