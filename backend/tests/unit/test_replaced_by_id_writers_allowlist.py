"""Structural gate: only refresh-token rotation writes ``RefreshToken.replaced_by_id``.

``refresh_token_service.rotate_refresh_token`` revokes every live token of the user when a revoked
token with ``replaced_by_id`` set is presented, reading the link as proof that the token was rotated
away and that someone else holds its successor. That reading is sound only while rotation is the one
writer. A revocation path or a session transfer that set the link would send its tokens down the
theft sweep again, which is the bug ``test_refresh_token_revocation_kinds.py`` pins for the writers
that exist today.

A writer can reach the column in more spellings than a write-only scan sees: an alias
(``successor = RefreshToken.replaced_by_id`` then ``.update({successor: value})``), ``setattr`` or
``getattr`` with the name, ``sqlalchemy.column("replaced_by_id")``. So this gate counts every
MENTION of the column in ``backend/app``, reads included, as (file, enclosing function or class,
kind) and holds the set equal to ``ALLOWED_MENTIONS``: any new mention, read or write, fails until it
is reviewed and listed. A mention is an attribute access in any context, a bare name, a keyword
argument, or a string literal that contains the name outside a docstring. Comments and docstrings
are not code and are not counted. ``test_the_mention_scan_scores_every_planted_form`` scores the scan
on planted bypasses and look-alikes.
"""
import ast
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[2] / "app"
COLUMN = "replaced_by_id"

# Every mention of the successor link in backend/app, as (file, scope, kind). Rotation is the only
# writer; its own presence check is the only reader; the model defines the column.
ALLOWED_MENTIONS = {
    ("services/refresh_token_service.py", "rotate_refresh_token", "read"),
    ("services/refresh_token_service.py", "rotate_refresh_token", "write"),
    ("models/refresh_token.py", "RefreshToken", "definition"),
}


def _docstring_ids(tree: ast.AST) -> set[int]:
    """ids of the string constants that are docstrings (module, class or function)."""
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            first = node.body[0] if node.body else None
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
                    and isinstance(first.value.value, str):
                ids.add(id(first.value))
    return ids


class _ColumnMentionFinder(ast.NodeVisitor):
    """Collect (scope, kind) for every mention of ``replaced_by_id``."""

    def __init__(self, docstrings: set[int]) -> None:
        self.mentions: set[tuple[str, str]] = set()
        self._docstrings = docstrings
        self._stack: list[str] = []

    def _scoped(self, node: ast.AST, name: str) -> None:
        self._stack.append(name)
        self.generic_visit(node)
        self._stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._scoped(node, node.name)

    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._scoped(node, node.name)

    def _record(self, kind: str) -> None:
        self.mentions.add((self._stack[-1] if self._stack else "<module>", kind))

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr == COLUMN:
            self._record("read" if isinstance(node.ctx, ast.Load) else "write")
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id == COLUMN:
            self._record("definition" if isinstance(node.ctx, ast.Store) else "name")

    def visit_keyword(self, node: ast.keyword) -> None:
        if node.arg == COLUMN:
            self._record("keyword")
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, str) and COLUMN in node.value and id(node) not in self._docstrings:
            self._record("string")


def _mentions(source: str) -> set[tuple[str, str]]:
    tree = ast.parse(source)
    finder = _ColumnMentionFinder(_docstring_ids(tree))
    finder.visit(tree)
    return finder.mentions


# Planted forms: every way a second writer could reach the column must be counted; a docstring or a
# comment that names it must not be.
PLANTED = [
    ("alias-then-update",
     "def f(q, v):\n    successor = RefreshToken.replaced_by_id\n    q.update({successor: v})\n",
     {("f", "read")}),
    ("attribute-assignment", "def f(t, v):\n    t.replaced_by_id = v\n", {("f", "write")}),
    ("annotated-assignment", "def f(t, v):\n    t.replaced_by_id: int = v\n", {("f", "write")}),
    ("dict-key", "def f(q, v):\n    q.update({RefreshToken.replaced_by_id: v})\n", {("f", "read")}),
    ("constructor-keyword", "def f(v):\n    return RefreshToken(user_id=1, replaced_by_id=v)\n",
     {("f", "keyword")}),
    ("values-keyword", "def f(s, v):\n    return s.values(replaced_by_id=v)\n", {("f", "keyword")}),
    ("setattr", "def f(t, v):\n    setattr(t, 'replaced_by_id', v)\n", {("f", "string")}),
    ("getattr", "def f(t):\n    return getattr(t, 'replaced_by_id')\n", {("f", "string")}),
    ("column-by-name", "def f(v):\n    return column('replaced_by_id') == v\n", {("f", "string")}),
    ("raw-sql-text", "def f():\n    return text('UPDATE refresh_tokens SET replaced_by_id = 1')\n",
     {("f", "string")}),
    ("module-level-alias", "SUCCESSOR = RefreshToken.replaced_by_id\n", {("<module>", "read")}),
    ("column-definition", "class T:\n    replaced_by_id = Column(Integer)\n", {("T", "definition")}),
    ("docstring-only", 'def f():\n    """Reads replaced_by_id to decide."""\n    return 1\n', set()),
    ("comment-only", "def f():\n    # replaced_by_id is written by rotation only\n    return 1\n", set()),
    ("other-column", "def f(t, v):\n    t.revoked_at = v\n", set()),
]


@pytest.mark.parametrize("source, expected", [p[1:] for p in PLANTED], ids=[p[0] for p in PLANTED])
def test_the_mention_scan_scores_every_planted_form(source, expected):
    assert _mentions(source) == expected


def test_every_mention_of_the_successor_link_is_reviewed():
    found: set[tuple[str, str, str]] = set()
    for py in APP_DIR.rglob("*.py"):
        rel = py.relative_to(APP_DIR).as_posix()
        found.update((rel, scope, kind) for scope, kind in _mentions(py.read_text(encoding="utf-8")))

    assert found == ALLOWED_MENTIONS, (
        f"{COLUMN} mentions changed: {sorted(found ^ ALLOWED_MENTIONS)}. Only rotation may set the "
        "link, because the theft sweep reads it as proof of rotation "
        "(lessons/arch-only-a-rotated-refresh-token-signals-theft.md); review a new mention, read or "
        "write, and list it here with its reason."
    )
