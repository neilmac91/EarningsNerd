"""Structural gates for the two rules the Item 1A wording counts carry (tasks/todo.md E17, PR B).

1. **The counts are read behind an access check.** ``filing_section_service`` owns the cached
   comparison (``FilingSectionText.diff_summary``) and the three functions that hand it out with no
   notion of who is asking: ``wording_change_summaries`` (the counts per filing),
   ``build_section_changes`` (the Change Report block, cut to the ``SectionAccess`` it is given) and
   ``cached_diff`` (the paired diff itself). Who sees the counts is decided by ``ENABLE_SECTION_CHANGES``
   and by the viewer: the alert line goes to a recipient whose plan has ``section_changes``; the
   dashboard card shows the counts at teaser and full access and the review progress at full access
   only; the Change Report cuts the block to the viewer's access; the review service reads the full
   comparison for a reader its callers have already gated. So no code outside the owner module names
   ``diff_summary`` (as an attribute, or as the string ``getattr`` would take); inside the owner the
   column is named only in the listed scopes (a new one is a new exporter to list); and every reference
   to one of the three functions outside the owner (a name, an attribute, the name as a string) sits in
   an allow-listed (file, scope) that makes the check or passes the viewer's access through. An aliased
   import (``import … as``) would hide the name from this test and fails outright. A new reader fails
   with file:line; an allow-listed reader that disappears fails too.

2. **"No comparison yet" is read off ``diff_prior_filing_id``, never ``diff_summary``.** The JSON
   column stores the ``None`` a pending comparison writes as a JSON ``null`` (SQLAlchemy's default
   ``none_as_null=False``), which ``IS NOT NULL`` admits and which then reads as a zero comparison:
   PR B's first draft would have told Pro recipients "no changes" for filings whose prior was not
   extracted yet. No code under ``app/`` compares ``diff_summary`` with ``None`` or with SQLAlchemy's
   ``null()`` in any form (``is``, ``is not``, ``==``, ``!=``, ``.is_()``, ``.isnot()``, ``.is_not()``;
   ``!= null()`` is where ruff's E711 steers a ``!= None``); ``lessons/arch-sqlalchemy-json-none-is-json-null.md``.
"""
import ast
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
APP_DIR = BACKEND_DIR / "app"

OWNER = "app/services/filing_section_service.py"
COLUMN_DEFINED_IN = "app/models/filing_section_text.py"
HELPERS = frozenset({"wording_change_summaries", "build_section_changes", "cached_diff"})
JSON_COLUMN = "diff_summary"
_NULL_TESTS = frozenset({"is_", "isnot", "is_not"})

# Scope inside the owner -> why it names the column. A new scope that reads it is a new exporter of
# the counts: list it here and, if it hands them out, add it to HELPERS with its callers below.
OWNER_COLUMN_SCOPES: dict[str, str] = {
    "wording_change_summaries": "reads the cached counts for the allow-listed callers",
    "compute_diff_summary": "writes the cached counts, and None while the prior is not extracted",
    "_upsert": "clears them when a re-extraction replaces the text",
}

# (file relative to backend/, enclosing scope, function) -> the access check that scope makes.
ALLOWED_READERS: dict[tuple[str, str, str], str] = {
    ("app/services/filing_scan_service.py", "alert_wording_changes", "wording_change_summaries"): (
        "returns nothing unless ENABLE_SECTION_CHANGES is on and the recipient's plan has section_changes"
    ),
    ("app/services/dashboard_feed_service.py", "_wording_changes", "wording_change_summaries"): (
        "returns nothing for ACCESS_NONE (the viewer's SectionAccess); the review progress only for ACCESS_FULL"
    ),
    ("app/services/change_report_service.py", "build_change_report", "build_section_changes"): (
        "passes through the SectionAccess its caller computed with section_changes_access (default: none)"
    ),
    ("app/services/section_review_service.py", "_comparison", "build_section_changes"): (
        "reads the full comparison for a reader its callers gated: the review endpoints by "
        "require_entitlement('section_changes'), the dashboard feed by ACCESS_FULL"
    ),
    ("app/services/section_review_service.py", "review_progress", "cached_diff"): (
        "the list's reconciliation (live ids and hashes) over rows the reader wrote behind "
        "require_entitlement('section_changes'); dashboard_feed_service._wording_changes calls it only for ACCESS_FULL"
    ),
}


class _ScopedFinder(ast.NodeVisitor):
    """Collect, with the enclosing scope: every reference to a HELPER (``helper_refs``: scope, line,
    helper, form), every aliased import of one (``aliased``), every naming of JSON_COLUMN
    (``column_refs``: scope, line) and the line of every None-test of it (``null_tests``)."""

    def __init__(self) -> None:
        self.helper_refs: list[tuple[str, int, str, str]] = []
        self.aliased: list[int] = []
        self.column_refs: list[tuple[str, int]] = []
        self.null_tests: list[int] = []
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

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            if alias.name in HELPERS and alias.asname:
                self.aliased.append(node.lineno)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id in HELPERS:
            self.helper_refs.append((self._scope(), node.lineno, node.id, "name"))

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr in HELPERS:
            self.helper_refs.append((self._scope(), node.lineno, node.attr, "attribute"))
        elif node.attr == JSON_COLUMN:
            self.column_refs.append((self._scope(), node.lineno))
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, str):
            if node.value in HELPERS:
                self.helper_refs.append((self._scope(), node.lineno, node.value, "string"))
            elif node.value == JSON_COLUMN:
                self.column_refs.append((self._scope(), node.lineno))

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr in _NULL_TESTS
            and _is_column(func.value)
            and any(_is_null(arg) for arg in node.args)
        ):
            self.null_tests.append(node.lineno)
        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare) -> None:
        operands = [node.left, *node.comparators]
        if any(_is_column(operand) for operand in operands) and any(_is_null(operand) for operand in operands):
            self.null_tests.append(node.lineno)
        self.generic_visit(node)


def _is_column(node: ast.AST) -> bool:
    return isinstance(node, ast.Attribute) and node.attr == JSON_COLUMN


def _is_null(node: ast.AST) -> bool:
    """``None``, or SQLAlchemy's ``null()`` however it is imported (``null()``, ``sa.null()``)."""
    if isinstance(node, ast.Constant) and node.value is None:
        return True
    if isinstance(node, ast.Call):
        func = node.func
        return (func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None) == "null"
    return False


def _scan(source: str) -> _ScopedFinder:
    finder = _ScopedFinder()
    finder.visit(ast.parse(source))
    return finder


def test_wording_counts_are_read_only_behind_an_access_check():
    found: dict[tuple[str, str, str], list[str]] = {}
    aliased: list[str] = []
    column_outside_owner: list[str] = []
    for py in sorted(APP_DIR.rglob("*.py")):
        rel = py.relative_to(BACKEND_DIR).as_posix()
        if rel == OWNER:
            continue
        finder = _scan(py.read_text(encoding="utf-8"))
        for scope, lineno, helper, form in finder.helper_refs:
            found.setdefault((rel, scope, helper), []).append(f"{rel}:{lineno} ({form})")
        aliased += [f"{rel}:{lineno}" for lineno in finder.aliased]
        if rel != COLUMN_DEFINED_IN:
            column_outside_owner += [f"{rel}:{lineno}" for _scope, lineno in finder.column_refs]

    unexpected = sorted((loc, scope, helper) for (_rel, scope, helper), locs in found.items() if (_rel, scope, helper) not in ALLOWED_READERS for loc in locs)
    missing = sorted(set(ALLOWED_READERS) - set(found))
    assert not unexpected and not missing and not aliased and not column_outside_owner, (
        "Readers of the Item 1A wording counts drifted from the allow-list.\n"
        f"  unexpected (file:line, scope, function): {unexpected}\n"
        f"  missing (an access-checking reader was removed or renamed; prune ALLOWED_READERS): {missing}\n"
        f"  aliased imports (import the function under its own name so this test sees its uses): {aliased}\n"
        f"  diff_summary named outside filing_section_service: {column_outside_owner}\n"
        "The counts show behind ENABLE_SECTION_CHANGES and only as the viewer may see them: the alert line to a "
        "recipient whose plan has section_changes, the dashboard card at teaser and full access, the Change Report "
        "cut to the viewer's SectionAccess. Read them through an allow-listed scope, or add a scope that checks the "
        "same and list it here with its check."
    )
    assert (BACKEND_DIR / OWNER).exists() and (BACKEND_DIR / COLUMN_DEFINED_IN).exists()


def test_inside_the_owner_the_column_is_named_only_in_the_listed_scopes():
    finder = _scan((BACKEND_DIR / OWNER).read_text(encoding="utf-8"))
    scopes = {scope for scope, _lineno in finder.column_refs}
    assert scopes == set(OWNER_COLUMN_SCOPES), (
        f"diff_summary is named in {sorted(scopes)} inside filing_section_service; the listed scopes are "
        f"{sorted(OWNER_COLUMN_SCOPES)}. A new reader of the column is a new exporter of the counts: list it "
        "here and, if it hands them out, add it to HELPERS with its allow-listed callers."
    )


def test_no_code_tests_the_cached_comparison_json_against_none():
    hits = [
        f"{py.relative_to(BACKEND_DIR).as_posix()}:{lineno}"
        for py in sorted(APP_DIR.rglob("*.py"))
        for lineno in _scan(py.read_text(encoding="utf-8")).null_tests
    ]
    assert not hits, (
        f"diff_summary is compared with None or null() at {hits}. A pending comparison stores a JSON null that "
        "IS NOT NULL admits and that reads as a zero comparison; read 'no comparison yet' off "
        "diff_prior_filing_id (lessons/arch-sqlalchemy-json-none-is-json-null.md)."
    )


def test_finder_sees_references_by_scope_and_form_and_every_null_test_form():
    finder = _scan(
        "from app.services.filing_section_service import wording_change_summaries as counts\n"
        "def outer():\n"
        "    def inner(db):\n"
        "        return wording_change_summaries(db, [1])\n"
        "    return svc.build_section_changes(db, filing, FULL_SECTION_ACCESS)\n"
        "fn = getattr(svc, 'cached_diff')\n"
        "rows = q.filter(FilingSectionText.diff_summary.isnot(None))\n"
        "rows = q.filter(FilingSectionText.diff_summary.is_not(None))\n"
        "rows = q.filter(FilingSectionText.diff_summary.is_(None))\n"
        "rows = q.filter(FilingSectionText.diff_summary != None)\n"
        "rows = q.filter(FilingSectionText.diff_summary != null())\n"
        "rows = q.filter(FilingSectionText.diff_summary.isnot(sa.null()))\n"
        "ok = row.diff_summary is not None\n"
        "fine = row.diff_prior_filing_id is not None\n"
        "also = FilingSectionText.diff_prior_filing_id.isnot(None)\n"
        "text = 'diff_summary is None'\n"
        "value = getattr(row, 'diff_summary')\n"
    )
    assert finder.aliased == [1]
    assert finder.helper_refs == [
        ("outer.inner", 4, "wording_change_summaries", "name"),
        ("outer", 5, "build_section_changes", "attribute"),
        ("<module>", 6, "cached_diff", "string"),
    ]
    assert finder.null_tests == [7, 8, 9, 10, 11, 12, 13]
    assert [lineno for _scope, lineno in finder.column_refs] == [7, 8, 9, 10, 11, 12, 13, 17]
