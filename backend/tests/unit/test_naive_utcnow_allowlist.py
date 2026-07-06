"""Structural gate for the S5 naive-`datetime.utcnow()` allow-list.

S5 sweep 1 moved the backend onto the aware `app.utils.datetimes.utcnow()` helper, but three
columns are naive `DateTime` BY DESIGN — `OAuthState.expires_at` and
`RefreshToken.expires_at`/`revoked_at` — and are written/compared with the stdlib naive
`datetime.utcnow()` in exactly two modules to avoid the offset-naive/offset-aware `TypeError`
(Postgres tz-aware vs SQLite naive). See `app/utils/datetimes.py` + those models' docstrings.

The plan's original "rg 'datetime.utcnow' → 0" expectation therefore became a 6-site allow-list.
This test encodes it structurally (the same move as the components allowlist + the query-key rule)
so the exception can't silently grow: a NEW naive call anywhere fails here and points the author at
the aware helper, and "fixing" the token-expiry cluster to aware (which reintroduces the crash) also
trips it. It matches on (file, enclosing function) — not line numbers — and is AST-based, so it
counts real call nodes and ignores docstrings and the aware `utcnow()` helper (a bare-name call,
not an attribute access).
"""
import ast
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[2] / "app"

# The ONLY sanctioned stdlib-naive `datetime.utcnow()` call sites in app/, as (file, function) pairs
# — the deliberately-naive OAuthState/RefreshToken token-expiry cluster.
ALLOWED_NAIVE_UTCNOW = {
    ("routers/auth.py", "apple_login"),            # OAuthState.expires_at write + GC compare
    ("routers/auth.py", "apple_callback"),         # OAuthState.expires_at compare
    ("services/refresh_token_service.py", "create_refresh_token"),
    ("services/refresh_token_service.py", "rotate_refresh_token"),
    ("services/refresh_token_service.py", "revoke_refresh_token"),
    ("services/refresh_token_service.py", "revoke_all_for_user"),
}


class _NaiveUtcnowFinder(ast.NodeVisitor):
    """Collect the enclosing-function name of every `<x>.utcnow()` call (the stdlib naive call).

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

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Attribute) and node.func.attr == "utcnow":
            self.functions.append(self._stack[-1] if self._stack else "<module>")
        self.generic_visit(node)


def _naive_utcnow_sites(path: Path) -> list[str]:
    finder = _NaiveUtcnowFinder()
    finder.visit(ast.parse(path.read_text(encoding="utf-8")))
    return finder.functions


def test_naive_utcnow_calls_match_the_allowlist():
    found: set[tuple[str, str]] = set()
    for py in APP_DIR.rglob("*.py"):
        rel = py.relative_to(APP_DIR).as_posix()
        for func in _naive_utcnow_sites(py):
            found.add((rel, func))

    assert found == ALLOWED_NAIVE_UTCNOW, (
        "Naive `datetime.utcnow()` call sites in app/ drifted from the allow-list.\n"
        f"  unexpected (add the aware helper instead): {sorted(found - ALLOWED_NAIVE_UTCNOW)}\n"
        f"  missing (a sanctioned site was removed/renamed): {sorted(ALLOWED_NAIVE_UTCNOW - found)}\n"
        "Use the aware `app.utils.datetimes.utcnow()` helper for ephemeral values and any "
        "DateTime(timezone=True) column. The only sanctioned naive sites are the deliberately-naive "
        "OAuthState/RefreshToken token-expiry columns (see app/utils/datetimes.py). If you added a "
        "genuinely-naive column by design, update ALLOWED_NAIVE_UTCNOW in this test in the same PR."
    )
