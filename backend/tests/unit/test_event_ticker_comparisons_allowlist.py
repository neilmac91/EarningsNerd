"""Structural gate: an earnings event's ticker is compared to a ticker only in the canonical form.

``Company.ticker`` holds SEC's spelling of a share class (``BRK-B``) and ``EarningsEvent.ticker`` Alpha Vantage's
(``BRK.B``), and nothing normalizes either when it is written. A raw comparison of the two silently never matches for a
dual-class company: the earnings-day alert send joined ``upper(Company.ticker) == EarningsEvent.ticker``, so a reader
who turned BRK-B's alert on got no email, and the dashboard calendar and the anticipation score's watch counts missed
it the same way. A query wraps each side in ``index_membership_service.canonical_ticker_sql`` (the SQL form of
``normalize_ticker``).

An AST walk over ``app/**/*.py`` finds three shapes, each a site:

- a comparison (``==``, ``!=``, ``<`` ...) with an operand holding ``EarningsEvent.ticker`` outside a
  ``canonical_ticker_sql(...)`` call (bare, or inside another call such as ``func.upper``);
- a comparison with ``canonical_ticker_sql(EarningsEvent.ticker)`` on one side and a raw ``Company.ticker`` on another;
- ``.in_``, ``.notin_``, ``.like`` or ``.ilike`` called on an expression holding a raw ``EarningsEvent.ticker``.

Each (file, enclosing class and function) holding a site is listed below with its count and why it stays raw; the
counts are equalities (lessons/test-allowlist-caps-are-equalities.md), so a new site fails and a removed one must lower
its count.

Not covered: the model reached under another name (an import alias, ``aliased(...)``, ``models.EarningsEvent``); raw
SQL text; a comparison written without an operator or one of the listed methods (``filter_by(ticker=...)``,
``.op("=")(...)``, ``.__eq__(...)``), none of which the app uses; a ticker compared in Python after the read (``counts.get(ev.ticker)``, ``ev.ticker in some_set``), which is
how ``_watch_counts``' reader and the dashboard calendar's name lookup compare, and they are pinned by behaviour tests
instead (``test_earnings_calendar_engine.py``, ``test_calendar_service.py``); a company matched to a ticker that came
from an event through a request (the alert toggle), pinned by ``test_earnings_alerts.py``; ``backend/scripts``; and
the frontend, whose bell compares through ``features/calendar/lib/tickers.canonicalTicker``
(``frontend/tests/unit/calendarDualClassBell.spec.tsx``).
"""
import ast
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
APP_DIR = BACKEND_DIR / "app"

_CANONICAL = "canonical_ticker_sql"
_MATCHERS = {"in_", "notin_", "not_in", "like", "ilike", "startswith", "endswith", "contains", "is_", "is_not", "isnot"}

# (file relative to backend/, enclosing scope) -> (sites, why the event ticker is compared raw).
ALLOWED: dict[tuple[str, str], tuple[int, str]] = {
    ("app/services/earnings_calendar_service.py", "_events_by_key"): (
        1, "ingest prefetch: event to event, keyed on the Alpha Vantage symbol the pass writes; it must load exactly "
           "the rows uq_earnings_events_ticker_period holds, as the per-row lookup it replaces did",
    ),
    ("app/services/earnings_calendar_service.py", "events_in_range"): (
        1, "the index member list (already normalize_ticker form) against events, not a company; ingest admits by the "
           "canonical form, so this agrees while Alpha Vantage writes the dot form",
    ),
    ("app/services/reporting_this_week_service.py", "ReportingThisWeekService._fetch"): (
        1, "the index member list (already normalize_ticker form) against events, not a company; as events_in_range",
    ),
}


def _is_column(node: ast.AST, model: str) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "ticker"
        and isinstance(node.value, ast.Name)
        and node.value.id == model
    )


def _is_canonical_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    return (isinstance(func, ast.Name) and func.id == _CANONICAL) or (
        isinstance(func, ast.Attribute) and func.attr == _CANONICAL
    )


def _holds(node: ast.AST, model: str, *, raw: bool) -> bool:
    """Whether ``node`` holds ``<model>.ticker``; with ``raw``, only outside a canonical_ticker_sql call."""
    if _is_column(node, model):
        return True
    if raw and _is_canonical_call(node):
        return False
    return any(_holds(child, model, raw=raw) for child in ast.iter_child_nodes(node))


def _is_raw_comparison(node: ast.Compare) -> bool:
    operands = [node.left, *node.comparators]
    if any(_holds(operand, "EarningsEvent", raw=True) for operand in operands):
        return True
    return any(_holds(operand, "EarningsEvent", raw=False) for operand in operands) and any(
        _holds(operand, "Company", raw=True) for operand in operands
    )


class _SiteFinder(ast.NodeVisitor):
    """Collect (enclosing scope, lineno) for each raw comparison of an event ticker."""

    def __init__(self) -> None:
        self.hits: list[tuple[str, int]] = []
        self._scopes: list[str] = []

    def _scope(self) -> str:
        return ".".join(self._scopes) if self._scopes else "<module>"

    def _visit_scope(self, node: ast.AST, name: str) -> None:
        self._scopes.append(name)
        self.generic_visit(node)
        self._scopes.pop()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._visit_scope(node, node.name)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_scope(node, node.name)

    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]

    def visit_Compare(self, node: ast.Compare) -> None:
        if _is_raw_comparison(node):
            self.hits.append((self._scope(), node.lineno))
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr in _MATCHERS
            and _holds(func.value, "EarningsEvent", raw=True)
        ):
            self.hits.append((self._scope(), node.lineno))
        self.generic_visit(node)


def sites_in(source: str) -> list[tuple[str, int]]:
    finder = _SiteFinder()
    finder.visit(ast.parse(source))
    return finder.hits


def test_raw_event_ticker_comparisons_match_the_allowlist():
    found: dict[tuple[str, str], list[int]] = {}
    for path in sorted(APP_DIR.rglob("*.py")):
        relative = path.relative_to(BACKEND_DIR).as_posix()
        for scope, lineno in sites_in(path.read_text(encoding="utf-8")):
            found.setdefault((relative, scope), []).append(lineno)

    unlisted = {key: lines for key, lines in found.items() if key not in ALLOWED}
    assert not unlisted, (
        "An earnings event's ticker is compared raw, which never matches a dual-class company (BRK-B against "
        "BRK.B). Wrap both sides in index_membership_service.canonical_ticker_sql: "
        + ", ".join(f"{file}:{lines} in {scope}" for (file, scope), lines in sorted(unlisted.items()))
    )
    counts = {key: len(lines) for key, lines in found.items()}
    expected = {key: count for key, (count, _reason) in ALLOWED.items()}
    assert counts == expected, (
        "A listed site's count changed or it is gone; lower or remove its entry in ALLOWED: "
        f"found {dict(sorted(counts.items()))}"
    )


def test_each_raw_form_is_found():
    forms = [
        "func.upper(Company.ticker) == EarningsEvent.ticker",
        "EarningsEvent.ticker == ticker",
        "EarningsEvent.ticker != ticker",
        "func.upper(EarningsEvent.ticker) == ticker",
        "canonical_ticker_sql(Company.ticker) == EarningsEvent.ticker",
        "func.upper(Company.ticker) == idx.canonical_ticker_sql(EarningsEvent.ticker)",
        "EarningsEvent.ticker.in_(tickers)",
        "EarningsEvent.ticker.notin_(tickers)",
        "func.upper(EarningsEvent.ticker).in_(tickers)",
        "EarningsEvent.ticker.like(prefix)",
        "EarningsEvent.ticker.startswith(prefix)",
        "EarningsEvent.ticker.contains(part)",
        "EarningsEvent.ticker.is_(ticker)",
    ]
    for form in forms:
        source = f"class S:\n    def read(self, db):\n        return db.query(EarningsEvent).filter({form})\n"
        assert sites_in(source) == [("S.read", 3)], form


def test_canonical_and_unrelated_forms_are_not_found():
    forms = [
        "canonical_ticker_sql(Company.ticker) == canonical_ticker_sql(EarningsEvent.ticker)",
        "idx.canonical_ticker_sql(EarningsEvent.ticker) == canonical",
        "canonical_ticker_sql(EarningsEvent.ticker).in_(tickers)",
        "canonical_ticker_sql(Company.ticker) == normalize_ticker(ticker)",
        "func.upper(Company.ticker) == ticker",
        "EarningsEvent.event_date == today",
    ]
    for form in forms:
        source = f"def read(db):\n    return db.query(EarningsEvent).filter({form})\n"
        assert sites_in(source) == [], form
    assert sites_in("def read(db):\n    return db.query(EarningsEvent).order_by(EarningsEvent.ticker.asc())\n") == []
