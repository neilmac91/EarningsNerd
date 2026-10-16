"""Structural gate for ``lessons/sec-parse-app-fetched-html-not-edgartools-filing-objects.md``.

edgartools' ``Filing.obj()`` (and the ``CompanyReport`` it returns) fetches the filing homepage
and the SGML index through edgartools' own HTTP client, which the app's limiter, breaker and
diagnostics never see, and it returned nothing for every document probed from the build
environment. Section text is parsed from the primary document the app fetched
(``filing_section_service.parse_item_1a``). This test encodes the rule the way the os.getenv
gate does: an AST walk over ``app/**/*.py`` collects every access to an attribute named ``obj``:
the call (``filing.obj()``), the bare read that aliases the accessor (``loader = filing.obj``,
then ``loader()``) and the string form: any call that passes ``"obj"`` as an argument, which covers
``getattr(filing, "obj")`` and getattr wrappers such as ``sixk_extractor._safe(filing, "obj")``.
Any literal way of reaching the accessor starts with one of those; a name built at runtime (held in a
variable) is outside an AST walk, and review catches it. The (file, enclosing scope) pairs are
compared against the two sites that predate the rule. The summary-section path left the list with
E28: it parses the primary document the pipeline fetched and never calls ``obj()``. A NEW access
anywhere fails with its file:line; a sanctioned site that disappears fails too, so the list cannot
go stale.
"""
import ast
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
APP_DIR = BACKEND_DIR / "app"

# (file relative to backend/, enclosing scope) -> why the call predates the rule.
ALLOWED_OBJ_CALLS: dict[tuple[str, str], str] = {
    ("app/services/edgar/sixk_extractor.py", "_extract_sixk_text_sync"): (
        "the 6-K exhibit text for summary grounding, through the _safe getattr wrapper"
    ),
    ("app/services/insider_service.py", "_collect_insider_data_sync"): (
        "Form 4 objects for the insider feed, behind ENABLE_INSIDER_ACTIVITY (off in the deploy)"
    ),
}


class _ObjAccessFinder(ast.NodeVisitor):
    """Collect (scope, lineno) for every ``<expr>.obj`` attribute (called or not) and every call
    that passes the string ``"obj"`` as an argument (``getattr`` or a wrapper around it)."""

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

    def visit_Attribute(self, node: ast.Attribute) -> None:
        # A call's callee is this node too, so a call and a bare read are one case each.
        if node.attr == "obj":
            self.hits.append((self._scope(), node.lineno))
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        arguments = [*node.args, *(keyword.value for keyword in node.keywords)]
        if any(isinstance(arg, ast.Constant) and arg.value == "obj" for arg in arguments):
            self.hits.append((self._scope(), node.lineno))
        self.generic_visit(node)


def _obj_accesses(path: Path) -> list[tuple[str, int]]:
    finder = _ObjAccessFinder()
    finder.visit(ast.parse(path.read_text(encoding="utf-8")))
    return finder.hits


def test_edgartools_obj_accesses_match_the_allowlist():
    found: dict[tuple[str, str], list[str]] = {}
    for py in sorted(APP_DIR.rglob("*.py")):
        rel = py.relative_to(BACKEND_DIR).as_posix()
        for scope, lineno in _obj_accesses(py):
            found.setdefault((rel, scope), []).append(f"{rel}:{lineno}")

    unexpected = {key: locs for key, locs in found.items() if key not in ALLOWED_OBJ_CALLS}
    missing = set(ALLOWED_OBJ_CALLS) - set(found)

    assert not unexpected and not missing, (
        "edgartools .obj accesses (a call, a bare read of the accessor, or 'obj' passed by name as in "
        "getattr(x, 'obj')) drifted "
        "from the allow-list (lessons/sec-parse-app-fetched-html-not-edgartools-filing-objects.md).\n"
        f"  unexpected: {sorted(loc for locs in unexpected.values() for loc in locs)}\n"
        f"  missing (a sanctioned site was removed/moved — prune ALLOWED_OBJ_CALLS): {sorted(missing)}\n"
        "For document text, fetch the primary document through sec_edgar_service.get_filing_document "
        "and parse it locally (filing_section_service.parse_item_1a is the worked example)."
    )


def test_finder_sees_a_call_a_bare_read_and_the_string_forms_and_ignores_other_names():
    finder = _ObjAccessFinder()
    finder.visit(ast.parse(
        "def f(filing):\n"
        "    x = filing.obj()\n"
        "    loader = filing.obj\n"
        "    y = loader()\n"
        "    z = getattr(filing, 'obj')()\n"
        "    w = filing.object(); v = getattr(filing, 'objects'); u = obj(filing)\n"
        "    s = _safe(filing, 'obj'); t = _safe(filing, name='obj')\n"
        "    return x, y, z, w, v, u, s, t\n"
    ))
    assert finder.hits == [("f", 2), ("f", 3), ("f", 5), ("f", 7), ("f", 7)]
