"""Structural gate: ``section_reviews`` rows are read and written only through the review service.

A review row's ``labels``, ``completed_at`` and ``receipt`` mean nothing on their own: labels hang
on the change ids of the comparison that was live when they were set, and the receipt describes
the two texts it was frozen against. ``section_review_service`` reconciles every read against the
live comparison (ids the comparison no longer has are ignored, a receipt whose fingerprints no
longer match reads as not complete). PR B's review found the dashboard feed reading
``row.completed_at`` raw and calling the review "Reviewed" after a re-extraction had reopened it;
the feed now reads ``review_progress`` from the service. This test keeps every other reader out:
an AST walk over ``app/**/*.py`` collects every reference to the ``SectionReview`` model, by name
(an import, a name, an attribute) and without one (``relationship("SectionReview", …)`` or
``backref("SectionReview", …)`` on another model, the string form ``User`` declares every other
user-owned table with; and the table name ``section_reviews`` as a word in any string that is not
a docstring: ``Base.metadata.tables[...]``, ``Table(...)``, raw SQL, ``backref="section_reviews"``),
and compares the referencing files against the allow-list below. A new reader fails with
file:line; an allow-listed file that stops referencing the model fails too, so the list cannot go
stale. The model module and the models package re-export are not readers by name; the model module
may not declare a ``backref`` (the reverse side belongs on the other model, where this test sees it).
"""
import ast
import re
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
APP_DIR = BACKEND_DIR / "app"

MODEL = "SectionReview"
TABLE = "section_reviews"
MODEL_MODULE = "app/models/section_review.py"
# The class is defined here and re-exported here: those names are not reads. The string forms
# (a relationship declared on another model, the table name) are checked in the re-export too.
NOT_READERS_BY_NAME = frozenset({MODEL_MODULE, "app/models/__init__.py"})
_RELATIONSHIP_CALLS = frozenset({"relationship", "backref"})
_TABLE_WORD = re.compile(rf"\b{TABLE}\b")

# File (relative to backend/) -> why it may touch the rows.
ALLOWED_REFERENCERS: dict[str, str] = {
    "app/services/section_review_service.py": "the one writer, and the reader that reconciles rows against the live comparison",
    "app/services/user_data_export_service.py": (
        "the GDPR export dumps the reader's own rows verbatim (a record of what was stored, not a claim about the text)"
    ),
}


def model_references(tree: ast.AST) -> list[int]:
    """Lines that reference the model by name: imported, read as a name, or read as an attribute."""
    lines: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and any(alias.name == MODEL for alias in node.names):
            lines.append(node.lineno)
        elif isinstance(node, ast.Name) and node.id == MODEL:
            lines.append(node.lineno)
        elif isinstance(node, ast.Attribute) and node.attr == MODEL:
            lines.append(node.lineno)
    return sorted(set(lines))


def _call_name(node: ast.Call) -> str | None:
    func = node.func
    return func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None


def _docstring_ids(tree: ast.AST) -> set[int]:
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                ids.add(id(first.value))
    return ids


def string_references(tree: ast.AST) -> list[int]:
    """Lines that reach the rows without naming the class: ``relationship("SectionReview", …)`` or
    ``backref("SectionReview", …)``, and the table name as a word in any string that is not a
    docstring. A bare ``'SectionReview'`` string is not one."""
    docstrings = _docstring_ids(tree)
    lines: list[int] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and _call_name(node) in _RELATIONSHIP_CALLS
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == MODEL
        ):
            lines.append(node.lineno)
        elif (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in docstrings
            and _TABLE_WORD.search(node.value)
        ):
            lines.append(node.lineno)
    return sorted(set(lines))


def backref_declarations(tree: ast.AST) -> list[int]:
    """Lines where a ``relationship(…)`` carries ``backref=``: an attribute created on another model."""
    return sorted({
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and _call_name(node) == "relationship" and any(kw.arg == "backref" for kw in node.keywords)
    })


def test_section_review_rows_are_touched_only_by_the_allowlisted_files():
    found: dict[str, list[str]] = {}
    for py in sorted(APP_DIR.rglob("*.py")):
        rel = py.relative_to(BACKEND_DIR).as_posix()
        tree = ast.parse(py.read_text(encoding="utf-8"))
        lines: list[int] = [] if rel in NOT_READERS_BY_NAME else model_references(tree)
        lines += backref_declarations(tree) if rel == MODEL_MODULE else string_references(tree)
        for lineno in sorted(set(lines)):
            found.setdefault(rel, []).append(f"{rel}:{lineno}")

    unexpected = sorted(loc for rel, locs in found.items() if rel not in ALLOWED_REFERENCERS for loc in locs)
    stale = sorted(rel for rel in ALLOWED_REFERENCERS if rel not in found)
    assert not unexpected and not stale, (
        "Readers of section_reviews drifted from the allow-list.\n"
        f"  unexpected: {unexpected}\n"
        f"  stale (no longer references the model; prune it): {stale}\n"
        "Read a review through section_review_service (review_state, review_progress): a raw row's "
        "labels and receipt describe the comparison that was live when they were written, not the "
        "one in front of the reader. A relationship to SectionReview on another model, a backref from "
        "it, or the table name in a string is a reader too."
    )


def test_reference_finders_see_every_form_but_not_a_bare_string_or_a_docstring():
    tree = ast.parse(
        '"""The section_reviews table, described in a docstring."""\n'
        "from app.models import SectionReview\n"
        "rows = db.query(SectionReview).all()\n"
        "other = models.SectionReview\n"
        "note = 'SectionReview'\n"
        "reviews = relationship('SectionReview', back_populates='user')\n"
        "again = orm.relationship('User', backref=backref('SectionReview'))\n"
        "table = Base.metadata.tables['section_reviews']\n"
        "sql = text('SELECT 1 FROM section_reviews WHERE 1')\n"
        "name = 'uq_section_reviews_user_filing_section'\n"
        "def f():\n"
        "    '''Reads section_reviews: a docstring, not a reference.'''\n"
    )
    assert model_references(tree) == [2, 3, 4]
    assert string_references(tree) == [6, 7, 8, 9]
    assert backref_declarations(ast.parse(
        "user = relationship('User', backref='section_reviews')\n"
        "other = relationship('User', back_populates='section_reviews')\n"
    )) == [1]
