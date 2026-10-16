"""Structural gate for ``lessons/sec-bind-a-ticker-by-exact-match-only.md``.

``sec_edgar_service.search_company`` is the typeahead's search over SEC's ticker file, ranked by
the private ``_local_search``: exact ticker hits first, then any entry whose name or ticker merely
contains the query. The company page, the filings list and precompute took its first hit as the
requested ticker's company, so a ticker missing from SEC's file that is a substring of another
entry's name or ticker served, persisted and paid to summarize an unrelated issuer (RTN bound to
Enterprise Products PARTNERS, X to Exxon). A ticker binds through ``resolve_ticker`` (exact match
only).

An AST walk over the backend's non-test code collects every access to an attribute named
``search_company`` or ``_local_search`` (the call, a bare read that aliases the method, and
``getattr(x, "<name>")``) and compares the (file, enclosing scope) pairs against the sanctioned
callers below: a new caller fails with its file:line, and a sanctioned caller that disappears
fails too, so the list cannot go stale. This allow-list is the guarantee.

A second, heuristic check fails on positional use of a search result anywhere, the sanctioned
callers included: the first-hit binding that caused the bug. A search result is a call to either
method (awaited or not), a name bound from one by ``=``, an annotated ``=`` or ``:=`` (or from
another such name), and an ``a or b`` holding one. Positional use is indexing it
(``hits[0]``, ``(hits or [None])[0]``), destructuring it (``first, *_ = hits``) and
``next(iter(hits))``. Other spellings, such as a loop that returns its first item, are
review-checked.
"""
import ast
from pathlib import Path
from typing import Optional

BACKEND_DIR = Path(__file__).resolve().parents[2]
SCANNED_DIRS = ("app", "scripts", "evals")

# method -> {(file relative to backend/, enclosing scope) -> why it may call that partial-match
# search}.
ALLOWED_SEARCH_CALLERS: dict[str, dict[tuple[str, str], str]] = {
    "search_company": {
        ("app/routers/companies.py", "search_companies"): (
            "the typeahead (GET /api/companies/search): returns every hit to the user and binds "
            "none to a requested ticker"
        ),
        ("app/services/edgar/compat.py", "SECEdgarServiceCompat.resolve_ticker"): (
            "the exact resolver: keeps only the hit whose ticker is the requested one"
        ),
    },
    "_local_search": {
        ("app/services/edgar/compat.py", "SECEdgarServiceCompat.search_company"): (
            "the search itself: ranks the cached ticker file for search_company's callers above"
        ),
    },
}
SEARCH_METHODS = frozenset(ALLOWED_SEARCH_CALLERS)


def _is_search_call(node: ast.AST) -> bool:
    """``x.search_company(...)`` or ``x._local_search(...)``, awaited or not."""
    if isinstance(node, ast.Await):
        node = node.value
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in SEARCH_METHODS
    )


class _SearchFinder(ast.NodeVisitor):
    """Collect (method, scope, lineno) for every search access and (scope, lineno) for every
    positional use of a search result."""

    def __init__(self) -> None:
        self.accesses: list[tuple[str, str, int]] = []
        self.positional: list[tuple[str, int]] = []
        self._stack: list[str] = []
        self._result_names: list[set[str]] = [set()]

    def _scope(self) -> str:
        return ".".join(self._stack) if self._stack else "<module>"

    def _is_result(self, node: Optional[ast.AST]) -> bool:
        if isinstance(node, ast.NamedExpr):
            return self._is_result(node.value)
        if isinstance(node, ast.BoolOp):
            return any(self._is_result(value) for value in node.values)
        if isinstance(node, ast.Name):
            return node.id in self._result_names[-1]
        return node is not None and _is_search_call(node)

    def _bind(self, target: ast.AST, value: Optional[ast.AST]) -> None:
        if not self._is_result(value):
            return
        if isinstance(target, ast.Name):
            self._result_names[-1].add(target.id)
        elif isinstance(target, (ast.Tuple, ast.List)):
            self.positional.append((self._scope(), target.lineno))

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._stack.append(node.name)
        self.generic_visit(node)
        self._stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._stack.append(node.name)
        self._result_names.append(set())
        self.generic_visit(node)
        self._result_names.pop()
        self._stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]

    def visit_Assign(self, node: ast.Assign) -> None:
        self.generic_visit(node)
        for target in node.targets:
            self._bind(target, node.value)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self.generic_visit(node)
        self._bind(node.target, node.value)

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        self.generic_visit(node)
        self._bind(node.target, node.value)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        # A call's callee is this node too, so a call and a bare read are one case each.
        if node.attr in SEARCH_METHODS:
            self.accesses.append((node.attr, self._scope(), node.lineno))
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        func, args = node.func, node.args
        if (
            isinstance(func, ast.Name) and func.id == "getattr" and len(args) >= 2
            and isinstance(args[1], ast.Constant) and isinstance(args[1].value, str)
            and args[1].value in SEARCH_METHODS
        ):
            self.accesses.append((args[1].value, self._scope(), node.lineno))
        if (
            isinstance(func, ast.Name) and func.id == "next" and args
            and isinstance(args[0], ast.Call) and isinstance(args[0].func, ast.Name)
            and args[0].func.id == "iter" and args[0].args and self._is_result(args[0].args[0])
        ):
            self.positional.append((self._scope(), node.lineno))
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        if self._is_result(node.value):
            self.positional.append((self._scope(), node.lineno))
        self.generic_visit(node)


def _scanned_files() -> list[Path]:
    files = sorted(BACKEND_DIR.glob("*.py"))
    for directory in SCANNED_DIRS:
        files.extend(sorted((BACKEND_DIR / directory).rglob("*.py")))
    return files


def _scan() -> tuple[dict[str, dict[tuple[str, str], list[str]]], list[str]]:
    accesses: dict[str, dict[tuple[str, str], list[str]]] = {method: {} for method in SEARCH_METHODS}
    positional: list[str] = []
    for py in _scanned_files():
        rel = py.relative_to(BACKEND_DIR).as_posix()
        finder = _SearchFinder()
        finder.visit(ast.parse(py.read_text(encoding="utf-8")))
        for method, scope, lineno in finder.accesses:
            accesses[method].setdefault((rel, scope), []).append(f"{rel}:{lineno}")
        positional.extend(f"{rel}:{lineno} ({scope})" for scope, lineno in finder.positional)
    return accesses, positional


def test_search_callers_match_the_allowlist():
    accesses, _ = _scan()
    drift = []
    for method, allowed in sorted(ALLOWED_SEARCH_CALLERS.items()):
        found = accesses[method]
        unexpected = sorted(loc for key, locs in found.items() if key not in allowed for loc in locs)
        missing = sorted(set(allowed) - set(found))
        if unexpected or missing:
            drift.append(
                f"  {method}: unexpected {unexpected}; missing (a sanctioned caller was "
                f"removed/moved — prune the allow-list) {missing}"
            )

    assert not drift, (
        "search_company/_local_search accesses drifted from the allow-list "
        "(lessons/sec-bind-a-ticker-by-exact-match-only.md).\n" + "\n".join(drift) + "\n"
        "To bind a requested ticker to its company, call sec_edgar_service.resolve_ticker (exact "
        "match; None means 404 / company_not_found). search_company is the typeahead's partial-match "
        "search."
    )


def test_no_search_result_is_bound_by_position():
    _, positional = _scan()
    assert not positional, (
        "a search_company/_local_search result is used by position "
        "(lessons/sec-bind-a-ticker-by-exact-match-only.md): its first hit is a partial name/ticker "
        f"match whenever SEC's file does not list the query. Use resolve_ticker.\n  {positional}"
    )


def test_finder_sees_every_access_and_positional_binding():
    finder = _SearchFinder()
    finder.visit(ast.parse(
        "async def f(svc, q):\n"
        "    hits = await svc.search_company(q)\n"
        "    first = hits[0]\n"
        "    one = (await svc.search_company(q))[0]\n"
        "    alias = svc.search_company\n"
        "    other = getattr(svc, 'search_company')\n"
        "    rows = [h for h in hits]\n"
        "    exact = next((h for h in hits if h['ticker'] == q), None)\n"
        "    typed: list = svc._local_search({}, q)\n"
        "    head, *_ = typed\n"
        "    if (found := await svc.search_company(q)):\n"
        "        found = (found or [None])[0]\n"
        "    return rows, exact, next(iter(hits)), svc.search_companies(q)[0], first, one, alias, other, head\n"
        "def g(hits):\n"
        "    return hits[0]\n"
    ))
    assert sorted(finder.accesses) == [
        ("_local_search", "f", 9),
        ("search_company", "f", 2),
        ("search_company", "f", 4),
        ("search_company", "f", 5),
        ("search_company", "f", 6),
        ("search_company", "f", 11),
    ]
    assert sorted(finder.positional) == [("f", 3), ("f", 4), ("f", 10), ("f", 12), ("f", 13)]
