"""Structural gate for ``lessons/sec-parse-app-fetched-html-not-edgartools-filing-objects.md``.

edgartools' ``Filing.obj()`` (and the ``CompanyReport`` it returns) fetches the filing homepage
and the SGML index through edgartools' own HTTP client, which the app's limiter, breaker and
diagnostics never see, and it returned nothing for every document probed from the build
environment. Section text is parsed from the primary document the app fetched
(``filing_section_service.parse_item_1a``). This test encodes the rule the way the os.getenv
gate does: an AST walk over ``app/**/*.py`` collects every ``.obj()`` call and compares the
(file, enclosing scope) pairs against the two sites that predate the rule. A NEW call anywhere
fails with its file:line; a sanctioned site that disappears fails too, so the list cannot go stale.
"""
import ast
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
APP_DIR = BACKEND_DIR / "app"

# (file relative to backend/, enclosing scope) -> why the call predates the rule.
ALLOWED_OBJ_CALLS: dict[tuple[str, str], str] = {
    ("app/services/edgar/xbrl_sections.py", "_extract_sections_sync"): (
        "the USE_EDGARTOOLS_SECTIONS summary-section path; its production hit rate is open item E18"
    ),
    ("app/services/insider_service.py", "_collect_insider_data_sync"): (
        "Form 4 objects for the insider feed, behind ENABLE_INSIDER_ACTIVITY (off in the deploy)"
    ),
}


class _ObjCallFinder(ast.NodeVisitor):
    """Collect (scope, lineno) for every ``<expr>.obj()`` call."""

    def __init__(self) -> None:
        self.hits: list[tuple[str, int]] = []
        self._stack: list[str] = []

    def _scope(self) -> str:
        return ".".join(self._stack) if self._stack else "<module>"

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._stack.append(node.name)
        self.generic_visit(node)
        self._stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._stack.append(node.name)
        self.generic_visit(node)
        self._stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Attribute) and node.func.attr == "obj":
            self.hits.append((self._scope(), node.lineno))
        self.generic_visit(node)


def _obj_calls(path: Path) -> list[tuple[str, int]]:
    finder = _ObjCallFinder()
    finder.visit(ast.parse(path.read_text(encoding="utf-8")))
    return finder.hits


def test_edgartools_obj_calls_match_the_allowlist():
    found: dict[tuple[str, str], list[str]] = {}
    for py in sorted(APP_DIR.rglob("*.py")):
        rel = py.relative_to(BACKEND_DIR).as_posix()
        for scope, lineno in _obj_calls(py):
            found.setdefault((rel, scope), []).append(f"{rel}:{lineno}")

    unexpected = {key: locs for key, locs in found.items() if key not in ALLOWED_OBJ_CALLS}
    missing = set(ALLOWED_OBJ_CALLS) - set(found)

    assert not unexpected and not missing, (
        "edgartools .obj() calls drifted from the allow-list "
        "(lessons/sec-parse-app-fetched-html-not-edgartools-filing-objects.md).\n"
        f"  unexpected: {sorted(loc for locs in unexpected.values() for loc in locs)}\n"
        f"  missing (a sanctioned site was removed/moved — prune ALLOWED_OBJ_CALLS): {sorted(missing)}\n"
        "For document text, fetch the primary document through sec_edgar_service.get_filing_document "
        "and parse it locally (filing_section_service.parse_item_1a is the worked example)."
    )


def test_finder_sees_a_call_and_ignores_the_attribute():
    tree_hits = _ObjCallFinder()
    tree_hits.visit(ast.parse("def f(filing):\n    x = filing.obj()\n    y = filing.obj\n    return x, y\n"))
    assert tree_hits.hits == [("f", 2)]
