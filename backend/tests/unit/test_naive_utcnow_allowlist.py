"""Structural gate for the S5 naive-`datetime.utcnow()` allow-list.

S5 sweep 1 moved the backend onto the aware `app.utils.datetimes.utcnow()` helper, but three
columns are naive `DateTime` BY DESIGN — `OAuthState.expires_at` and
`RefreshToken.expires_at`/`revoked_at` — and are written/compared with the stdlib naive
`datetime.utcnow()` in exactly two modules to avoid the offset-naive/offset-aware `TypeError`
(Postgres tz-aware vs SQLite naive). See `app/utils/datetimes.py` + those models' docstrings.
(`services/retention_service.py` also compares them, through a naive projection of the aware
`utcnow()` instant rather than a new naive call, so it needs no allow-list entry.)

The plan's original "rg 'datetime.utcnow' → 0" expectation therefore became a 6-site allow-list.
This test encodes it structurally (the same move as the components allowlist + the query-key rule)
so the exception can't silently grow: a NEW naive call anywhere fails here and points the author at
the aware helper, and "fixing" the token-expiry cluster to aware (which reintroduces the crash) also
trips it. It matches on (file, enclosing function) — not line numbers — and is AST-based, so it
counts attribute nodes (a call, or an uncalled reference such as `default=datetime.utcnow` that a
column or model calls later) and ignores docstrings and the aware `utcnow()` helper (a bare-name
call, not an attribute access). `datetime.utcfromtimestamp(ts)` is the same naive UTC value built from a
timestamp, so it counts as a naive site too; no app/ code calls it (`datetime.fromtimestamp(ts,
timezone.utc)` is the aware form). Local-clock reads (`datetime.now()`, `today()`) are the other
half of rule 7, gated by `test_naive_local_now_allowlist.py`.
"""
import ast
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[2] / "app"

# The ONLY sanctioned stdlib-naive `datetime.utcnow()` call sites in app/, as (file, function) pairs
# — the deliberately-naive OAuthState/RefreshToken token-expiry cluster.
ALLOWED_NAIVE_UTCNOW = {
    ("services/oauth_account_service.py", "store_oauth_state"),     # OAuthState.expires_at write + GC compare
    ("services/oauth_account_service.py", "consume_oauth_state"),   # OAuthState.expires_at compare
    ("services/refresh_token_service.py", "create_refresh_token"),
    ("services/refresh_token_service.py", "rotate_refresh_token"),
    ("services/refresh_token_service.py", "revoke_refresh_token"),
    ("services/refresh_token_service.py", "revoke_all_for_user"),
}


# The stdlib classmethods that return a naive UTC datetime.
NAIVE_UTC_METHODS = ("utcnow", "utcfromtimestamp")


class _NaiveUtcnowFinder(ast.NodeVisitor):
    """Collect the enclosing-function name of every `<x>.utcnow` / `<x>.utcfromtimestamp` reference.

    The aware helper is a bare-name `utcnow()` (ast.Name), never an attribute, so it is not matched.
    """

    def __init__(self) -> None:
        self.functions: list[str] = []
        self._stack: list[str] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._stack.append(node.name)
        self.generic_visit(node)
        self._stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr in NAIVE_UTC_METHODS:  # called, or passed uncalled as a default factory
            self.functions.append(self._stack[-1] if self._stack else "<module>")
        self.generic_visit(node)


def _naive_utcnow_sites(source: str) -> list[str]:
    finder = _NaiveUtcnowFinder()
    finder.visit(ast.parse(source))
    return finder.functions


def test_naive_utcnow_calls_match_the_allowlist():
    found: set[tuple[str, str]] = set()
    for py in APP_DIR.rglob("*.py"):
        rel = py.relative_to(APP_DIR).as_posix()
        for func in _naive_utcnow_sites(py.read_text(encoding="utf-8")):
            found.add((rel, func))

    for relative in (
        "services/edgar/xbrl_service.py", "services/edgar/xbrl_cache.py",
        "services/facts/ingest.py", "services/facts/upsert.py",
    ):
        tree = ast.parse((APP_DIR / relative).read_text(encoding="utf-8"))
        assert not any(
            isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == "now" for node in ast.walk(tree)
        ), f"{relative}: use app.utils.datetimes.utcnow for the Rule-7 follow-up sites"

    assert found == ALLOWED_NAIVE_UTCNOW, (
        "Naive `datetime.utcnow()` / `datetime.utcfromtimestamp()` call sites in app/ drifted from "
        "the allow-list.\n"
        f"  unexpected (add the aware helper instead): {sorted(found - ALLOWED_NAIVE_UTCNOW)}\n"
        f"  missing (a sanctioned site was removed/renamed): {sorted(ALLOWED_NAIVE_UTCNOW - found)}\n"
        "Use the aware `app.utils.datetimes.utcnow()` helper (or `datetime.fromtimestamp(ts, "
        "timezone.utc)`) for ephemeral values and any "
        "DateTime(timezone=True) column. The only sanctioned naive sites are the deliberately-naive "
        "OAuthState/RefreshToken token-expiry columns (see app/utils/datetimes.py). If you added a "
        "genuinely-naive column by design, update ALLOWED_NAIVE_UTCNOW in this test in the same PR."
    )


@pytest.mark.parametrize(("source", "expected"), [
    ("from datetime import datetime\ndef f():\n    return datetime.utcnow()\n", ["f"]),
    ("from datetime import datetime\ndef f(ts):\n    return datetime.utcfromtimestamp(ts)\n", ["f"]),
    ("import datetime\nSTARTED = datetime.datetime.utcfromtimestamp(0)\n", ["<module>"]),
    ("from datetime import datetime\ncreated = Column(DateTime, default=datetime.utcnow)\n", ["<module>"]),
    ("from datetime import datetime\ndef f():\n    return Field(default_factory=datetime.utcnow)\n", ["f"]),
    ("from app.utils.datetimes import utcnow\ndef f():\n    return utcnow()\n", []),
    ("from datetime import datetime, timezone\ndef f(ts):\n    return datetime.fromtimestamp(ts, timezone.utc)\n", []),
], ids=["utcnow", "utcfromtimestamp", "module-level utcfromtimestamp", "column default", "default factory",
        "aware helper", "aware fromtimestamp"])
def test_finder_sees_each_naive_utc_call(source, expected):
    assert _naive_utcnow_sites(source) == expected
