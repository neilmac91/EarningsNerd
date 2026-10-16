"""Structural gate for ``lessons/sec-bind-a-ticker-by-exact-match-only.md``.

``sec_edgar_service.search_company`` is the typeahead's search: exact ticker hits first, then any
entry whose name or ticker merely contains the query. The company page, the filings list and
precompute took its first hit as the requested ticker's company, so a ticker missing from SEC's
file served, persisted and paid to summarize an unrelated issuer (RTN bound to Enterprise
Products PARTNERS, X to Exxon). A ticker binds through ``resolve_ticker`` (exact match only).

An AST walk over the backend's non-test code collects every access to an attribute named
``search_company`` (the call, a bare read that aliases the method, and
``getattr(x, "search_company")``) and compares the (file, enclosing scope) pairs against the
sanctioned callers below: a new caller fails with its file:line, and a sanctioned caller that
disappears fails too, so the list cannot go stale. A second check fails on positional indexing of
a search result anywhere, the sanctioned callers included: ``search_company(...)[i]``, or a name
assigned from a ``search_company`` call and then subscripted (the first-hit binding that caused
the bug).
"""
import ast
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
SCANNED_DIRS = ("app", "scripts", "evals")

# (file relative to backend/, enclosing scope) -> why it may call the partial-match search.
ALLOWED_SEARCH_COMPANY_CALLERS: dict[tuple[str, str], str] = {
    ("app/routers/companies.py", "search_companies"): (
        "the typeahead (GET /api/companies/search): returns every hit to the user and binds none "
        "to a requested ticker"
    ),
    ("app/services/edgar/compat.py", "SECEdgarServiceCompat.resolve_ticker"): (
        "the exact resolver: keeps only the hit whose ticker is the requested one"
    ),
}


def _is_search_call(node: ast.AST) -> bool:
    """``x.search_company(...)``, awaited or not."""
    if isinstance(node, ast.Await):
        node = node.value
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "search_company"
    )


class _SearchCompanyFinder(ast.NodeVisitor):
    """Collect (scope, lineno) for every ``search_company`` access and every positional index of
    a search result."""

    def __init__(self) -> None:
        self.accesses: list[tuple[str, int]] = []
        self.positional: list[tuple[str, int]] = []
        self._stack: list[str] = []
        self._result_names: list[set[str]] = [set()]

    def _scope(self) -> str:
        return ".".join(self._stack) if self._stack else "<module>"

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
        if _is_search_call(node.value):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self._result_names[-1].add(target.id)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        # A call's callee is this node too, so a call and a bare read are one case each.
        if node.attr == "search_company":
            self.accesses.append((self._scope(), node.lineno))
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if (
            isinstance(node.func, ast.Name) and node.func.id == "getattr" and len(node.args) >= 2
            and isinstance(node.args[1], ast.Constant) and node.args[1].value == "search_company"
        ):
            self.accesses.append((self._scope(), node.lineno))
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        value = node.value
        if _is_search_call(value) or (
            isinstance(value, ast.Name) and value.id in self._result_names[-1]
        ):
            self.positional.append((self._scope(), node.lineno))
        self.generic_visit(node)


def _scanned_files() -> list[Path]:
    files = sorted(BACKEND_DIR.glob("*.py"))
    for directory in SCANNED_DIRS:
        files.extend(sorted((BACKEND_DIR / directory).rglob("*.py")))
    return files


def _scan() -> tuple[dict[tuple[str, str], list[str]], list[str]]:
    accesses: dict[tuple[str, str], list[str]] = {}
    positional: list[str] = []
    for py in _scanned_files():
        rel = py.relative_to(BACKEND_DIR).as_posix()
        finder = _SearchCompanyFinder()
        finder.visit(ast.parse(py.read_text(encoding="utf-8")))
        for scope, lineno in finder.accesses:
            accesses.setdefault((rel, scope), []).append(f"{rel}:{lineno}")
        positional.extend(f"{rel}:{lineno} ({scope})" for scope, lineno in finder.positional)
    return accesses, positional


def test_search_company_callers_match_the_allowlist():
    accesses, _ = _scan()
    unexpected = {key: locs for key, locs in accesses.items() if key not in ALLOWED_SEARCH_COMPANY_CALLERS}
    missing = set(ALLOWED_SEARCH_COMPANY_CALLERS) - set(accesses)

    assert not unexpected and not missing, (
        "search_company accesses drifted from the allow-list "
        "(lessons/sec-bind-a-ticker-by-exact-match-only.md).\n"
        f"  unexpected: {sorted(loc for locs in unexpected.values() for loc in locs)}\n"
        f"  missing (a sanctioned caller was removed/moved — prune the allow-list): {sorted(missing)}\n"
        "To bind a requested ticker to its company, call sec_edgar_service.resolve_ticker (exact "
        "match; None means 404 / company_not_found). search_company is the typeahead's partial-match "
        "search."
    )


def test_no_search_result_is_bound_by_position():
    _, positional = _scan()
    assert not positional, (
        "a search_company result is indexed by position "
        "(lessons/sec-bind-a-ticker-by-exact-match-only.md): its first hit is a partial name/ticker "
        f"match whenever SEC's file does not list the query. Use resolve_ticker.\n  {positional}"
    )


def test_finder_sees_calls_bare_reads_getattr_and_positional_binding():
    finder = _SearchCompanyFinder()
    finder.visit(ast.parse(
        "async def f(svc, q):\n"
        "    hits = await svc.search_company(q)\n"
        "    first = hits[0]\n"
        "    one = (await svc.search_company(q))[0]\n"
        "    alias = svc.search_company\n"
        "    other = getattr(svc, 'search_company')\n"
        "    rows = [h for h in hits]\n"
        "    return rows, svc.search_companies(q)[0], first, one, alias, other\n"
        "def g(hits):\n"
        "    return hits[0]\n"
    ))
    assert sorted(finder.accesses) == [("f", 2), ("f", 4), ("f", 5), ("f", 6)]
    assert sorted(finder.positional) == [("f", 3), ("f", 4)]
