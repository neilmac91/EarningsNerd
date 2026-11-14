"""AST helpers for the gates that keep an exception's text out of what the app answers or stores.

``calls_in`` lists every call in a module with the functions and the ``except ... as <name>:`` handlers around it;
``uses_caught_text`` says whether an expression builds its text from a caught exception. The router gate
(``tests/unit/test_router_exception_text_allowlist.py``) and the progress-row gate
(``tests/unit/test_progress_error_text_allowlist.py``) each choose which calls and which arguments they read.
"""
import ast


def _is_caught(node: ast.AST, name: str) -> bool:
    return isinstance(node, ast.Name) and node.id == name


def _operands(node: ast.expr) -> list[ast.expr]:
    """An operand of ``+`` or ``%``, or the members of a tuple or dict operand (``"%s: %s" % (label, exc)``)."""
    if isinstance(node, ast.Tuple):
        return list(node.elts)
    if isinstance(node, ast.Dict):
        return [value for value in node.values if value is not None]
    return [node]


def uses_caught_text(expression: ast.expr, name: str) -> bool:
    """Whether an expression puts the caught exception ``name`` into the text it builds: the bare name, an f-string,
    a ``+`` or ``%`` expression (a tuple or dict operand's members included), or an argument to ``.format``, ``str()``
    or ``repr()``."""
    if _is_caught(expression, name):
        return True
    for node in ast.walk(expression):
        if isinstance(node, ast.FormattedValue) and _is_caught(node.value, name):
            return True
        if isinstance(node, ast.BinOp) and any(
            _is_caught(operand, name) for side in (node.left, node.right) for operand in _operands(side)
        ):
            return True
        if isinstance(node, ast.Call):
            arguments = [*node.args, *(keyword.value for keyword in node.keywords)]
            if not any(_is_caught(argument, name) for argument in arguments):
                continue
            if isinstance(node.func, ast.Name) and node.func.id in {"str", "repr"}:
                return True
            if isinstance(node.func, ast.Attribute) and node.func.attr == "format":
                return True
    return False


def name_of(node: ast.AST) -> str:
    """The last name of a plain or dotted reference (``HTTPException``, ``status.HTTPException``), else ""."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


class _Calls(ast.NodeVisitor):
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[str, ...], ast.Call]] = []
        self._functions: list[str] = []
        self._caught: list[str] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._functions.append(node.name)
        self.generic_visit(node)
        self._functions.pop()

    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.name:
            self._caught.append(node.name)
        self.generic_visit(node)
        if node.name:
            self._caught.pop()

    def visit_Call(self, node: ast.Call) -> None:
        self.calls.append((".".join(self._functions) or "<module>", tuple(self._caught), node))
        self.generic_visit(node)


def calls_in(source: str) -> list[tuple[str, tuple[str, ...], ast.Call]]:
    """Every call in ``source``: (the functions it sits in, dotted; the exceptions caught around it; the call)."""
    finder = _Calls()
    finder.visit(ast.parse(source))
    return finder.calls
