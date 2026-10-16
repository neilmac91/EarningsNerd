"""Rule-7 gate: app code reads the clock as an aware UTC instant, never the process's local wall clock.

``test_naive_utcnow_allowlist.py`` catches the stdlib naive ``datetime.utcnow()``. It cannot see the
other naive reads: ``datetime.now()`` with no time zone, ``datetime.today()``, ``date.today()`` and
``datetime.fromtimestamp(ts)`` with no time zone all return the local wall clock, which equals UTC
only while the process runs in UTC. Stored timestamps are UTC, so a bound built from local time
slides by the process's offset: the trending window did exactly that until it moved to
``utcnow()`` (``test_company_routes.py::test_trending_window_is_thirty_utc_days_whatever_the_process_clock``).

Use ``app.utils.datetimes.utcnow()`` (or ``datetime.now(timezone.utc)``) for an instant, and the
existing Eastern-time helpers for a calendar day (``calendar_service``, ``earnings_calendar_service``).

The walk resolves ``datetime``/``date`` however they are imported (``from datetime import datetime``,
an alias, or ``import datetime`` then ``datetime.datetime.now()``), counts call nodes only (a
docstring or comment never matches), and treats an explicit ``None`` time zone as naive. Each
allowed site is a (file, qualified function) pair pinned to its exact count, so a further naive call
inside an allowed function fails too. ``test_finder_sees_each_shape`` proves the walk's reach on
synthetic source, so a regression in the finder fails there instead of passing app/ vacuously.
"""
from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[2] / "app"

# (file relative to app/, qualified function) -> exact number of naive local-clock reads there.
ALLOWED_NAIVE_LOCAL_NOW: dict[tuple[str, str], int] = {
    # The in-process SEC tickers cache times its own TTL against itself, so the naive clock cancels
    # out. SEC transport code is outside this gate's PRs; move it to utcnow() when that layer is next
    # changed, and drop this row in the same diff.
    ("services/edgar/compat.py", "SECEdgarServiceCompat._get_cached_tickers"): 3,
}


def _is_none(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and node.value is None


class _NaiveLocalClockFinder(ast.NodeVisitor):
    """Collect the qualified enclosing function of every naive local-clock read."""

    def __init__(self, tree: ast.AST) -> None:
        self.sites: list[str] = []
        self._stack: list[str] = []
        self._names: dict[str, str] = {}  # local name -> "datetime" (module), "datetime.datetime" or "datetime.date"
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "datetime":
                for alias in node.names:
                    if alias.name in ("datetime", "date"):
                        self._names[alias.asname or alias.name] = f"datetime.{alias.name}"
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "datetime":
                        self._names[alias.asname or "datetime"] = "datetime"

    def _scope(self, node: ast.AST) -> None:
        self._stack.append(node.name)  # type: ignore[attr-defined]
        self.generic_visit(node)
        self._stack.pop()

    visit_FunctionDef = visit_AsyncFunctionDef = visit_ClassDef = _scope  # type: ignore[assignment]

    def _receiver(self, expr: ast.AST) -> str | None:
        """``datetime`` / ``dt`` / ``datetime.datetime`` -> the class it names, else None."""
        if isinstance(expr, ast.Name):
            resolved = self._names.get(expr.id)
            return resolved if resolved in ("datetime.datetime", "datetime.date") else None
        if (isinstance(expr, ast.Attribute) and isinstance(expr.value, ast.Name)
                and self._names.get(expr.value.id) == "datetime" and expr.attr in ("datetime", "date")):
            return f"datetime.{expr.attr}"
        return None

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        if isinstance(func, ast.Attribute):
            cls, method = self._receiver(func.value), func.attr
            tz = next((kw.value for kw in node.keywords if kw.arg == "tz"), None)
            naive = False
            if cls == "datetime.datetime" and method == "now":
                given = node.args[0] if node.args else tz
                naive = given is None or _is_none(given)
            elif cls == "datetime.datetime" and method == "fromtimestamp":
                given = node.args[1] if len(node.args) > 1 else tz
                naive = given is None or _is_none(given)
            elif cls in ("datetime.datetime", "datetime.date") and method == "today":
                naive = True
            if naive:
                self.sites.append(".".join(self._stack) or "<module>")
        self.generic_visit(node)


def _sites(source: str) -> list[str]:
    tree = ast.parse(source)
    finder = _NaiveLocalClockFinder(tree)
    finder.visit(tree)
    return finder.sites


def test_app_reads_no_naive_local_clock_outside_the_allowlist():
    found: Counter = Counter()
    for path in sorted(APP_DIR.rglob("*.py")):
        rel = path.relative_to(APP_DIR).as_posix()
        for qualname in _sites(path.read_text(encoding="utf-8")):
            found[(rel, qualname)] += 1
    unexpected = {site: n for site, n in found.items() if ALLOWED_NAIVE_LOCAL_NOW.get(site) != n}
    stale = {site: n for site, n in ALLOWED_NAIVE_LOCAL_NOW.items() if site not in found}
    assert not unexpected, (
        f"naive local-clock reads (file, function) -> count: {unexpected}. Use "
        "app.utils.datetimes.utcnow() or datetime.now(timezone.utc); stored timestamps are UTC. "
        f"Allowed exactly: {ALLOWED_NAIVE_LOCAL_NOW}"
    )
    assert not stale, f"allowlist rows with no naive read left; delete them: {stale}"


CAUGHT = {
    "bare now": "from datetime import datetime\ndef f():\n    return datetime.now()\n",
    "aliased class": "from datetime import datetime as dt\ndef f():\n    return dt.now()\n",
    "module import": "import datetime\ndef f():\n    return datetime.datetime.now()\n",
    "aliased module": "import datetime as d\ndef f():\n    return d.datetime.now()\n",
    "explicit None": "from datetime import datetime\ndef f():\n    return datetime.now(None), datetime.now(tz=None)\n",
    "datetime.today": "from datetime import datetime\ndef f():\n    return datetime.today()\n",
    "date.today": "from datetime import date\ndef f():\n    return date.today()\n",
    "module date.today": "import datetime\ndef f():\n    return datetime.date.today()\n",
    "fromtimestamp": "from datetime import datetime\ndef f(ts):\n    return datetime.fromtimestamp(ts)\n",
    "method": "from datetime import datetime\nclass C:\n    def m(self):\n        return datetime.now()\n",
    "module level": "from datetime import datetime\nSTARTED = datetime.now()\n",
}
EXPECTED_SITES = {
    "explicit None": ["f", "f"], "method": ["C.m"], "module level": ["<module>"],
}
IGNORED = {
    "aware now": "from datetime import datetime, timezone\ndef f():\n    return datetime.now(timezone.utc)\n",
    "aware kw": "from datetime import datetime, timezone\ndef f():\n    return datetime.now(tz=timezone.utc)\n",
    "helper": "from app.utils.datetimes import utcnow\ndef f():\n    return utcnow()\n",
    "aware fromtimestamp": (
        "from datetime import datetime, timezone\ndef f(ts):\n"
        "    return datetime.fromtimestamp(ts, timezone.utc), datetime.fromtimestamp(ts, tz=timezone.utc)\n"
    ),
    "docstring": 'def f():\n    """Never datetime.now() or date.today()."""\n',
    "unrelated now": "import pendulum\ndef f():\n    return pendulum.now(), time.now()\n",
}


@pytest.mark.parametrize("label", sorted(CAUGHT))
def test_finder_sees_each_shape(label):
    assert _sites(CAUGHT[label]) == EXPECTED_SITES.get(label, ["f"])


@pytest.mark.parametrize("label", sorted(IGNORED))
def test_finder_ignores_aware_reads(label):
    assert _sites(IGNORED[label]) == []
