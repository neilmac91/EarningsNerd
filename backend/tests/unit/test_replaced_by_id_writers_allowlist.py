"""Structural gate: only refresh-token rotation writes ``RefreshToken.replaced_by_id``.

``refresh_token_service.rotate_refresh_token`` revokes every live token of the user when a revoked
token with ``replaced_by_id`` set is presented, reading the link as proof that the token was rotated
away and that someone else holds its successor. That reading is sound only while rotation is the one
writer. A revocation path or a session transfer that set the link would send its tokens down the
theft sweep again, which is the bug ``test_refresh_token_revocation_kinds.py`` pins for the writers
that exist today. This gate keeps the writer set at one. It is AST-based and matches on
(file, enclosing function): an attribute target, a keyword argument (a constructor or
``.values()``), a dict key (``.update({...})``) or the string ``"replaced_by_id"`` (``setattr``).
Reads are not writes and are not counted. The column definition in the model is a class attribute,
not an attribute access, so it is not counted either.
"""
import ast
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[2] / "app"
COLUMN = "replaced_by_id"

# The ONLY sanctioned writer of the successor link, as (file, function).
ALLOWED_WRITERS = {("services/refresh_token_service.py", "rotate_refresh_token")}


class _SuccessorLinkWriteFinder(ast.NodeVisitor):
    """Collect the enclosing-function name of every write of ``replaced_by_id``."""

    def __init__(self) -> None:
        self.functions: list[str] = []
        self._stack: list[str] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._stack.append(node.name)
        self.generic_visit(node)
        self._stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]

    def _record(self) -> None:
        self.functions.append(self._stack[-1] if self._stack else "<module>")

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr == COLUMN and not isinstance(node.ctx, ast.Load):
            self._record()
        self.generic_visit(node)

    def visit_keyword(self, node: ast.keyword) -> None:
        if node.arg == COLUMN:
            self._record()
        self.generic_visit(node)

    def visit_Dict(self, node: ast.Dict) -> None:
        if any(isinstance(key, ast.Attribute) and key.attr == COLUMN for key in node.keys):
            self._record()
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if node.value == COLUMN:
            self._record()


def test_only_rotation_writes_the_successor_link():
    found: set[tuple[str, str]] = set()
    for py in APP_DIR.rglob("*.py"):
        finder = _SuccessorLinkWriteFinder()
        finder.visit(ast.parse(py.read_text(encoding="utf-8")))
        found.update((py.relative_to(APP_DIR).as_posix(), func) for func in finder.functions)

    assert found == ALLOWED_WRITERS, (
        f"{COLUMN} writers changed: {sorted(found ^ ALLOWED_WRITERS)}. Only rotation may set the "
        "link: the theft sweep reads it as proof of rotation "
        "(lessons/arch-only-a-rotated-refresh-token-signals-theft.md)."
    )
