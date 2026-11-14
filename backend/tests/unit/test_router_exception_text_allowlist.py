"""Structural gate: a router never builds an ``HTTPException`` detail from the exception it caught.

``GET /api/companies/{ticker}`` and ``GET /api/filings/company/{ticker}`` answered an unexpected failure with
``detail=f"Error fetching company: {str(e)}"``: a database or driver error's text (its SQL, its parameters) went to an
unauthenticated caller in every environment, past ``main.global_exception_handler``, which hides ``str(exc)`` in
production. A route logs the error with ``logger.exception`` and answers a fixed detail.

An AST walk over ``app/routers/**/*.py`` finds every ``HTTPException(...)`` inside an ``except ... as <name>:`` whose
detail (the ``detail=`` keyword or the second positional argument) is built from ``<name>``: in an f-string, in a
``+`` or ``%`` expression, as an argument to ``.format``, ``str()`` or ``repr()``, or the bare name. Each
(file, enclosing function) holding such a site is listed below with its count and why it stays; the counts are
equalities (lessons/test-allowlist-caps-are-equalities.md), so a new site fails and a removed one must lower its count.

Not covered: a detail built from the caught exception in a variable first, or from an attribute of it (``exc.detail``,
``exc.args``); a 500 handled by ``JSONResponse`` rather than ``HTTPException``.
"""
import ast
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
ROUTERS_DIR = BACKEND_DIR / "app" / "routers"

# (file relative to backend/, enclosing function) -> (sites, why the caught exception's text may be the detail).
ALLOWED: dict[tuple[str, str], tuple[int, str]] = {
    ("app/routers/analysis.py", "get_dataset.dataset_for_reader"): (
        1, "the 400 carries build_dataset's ValueError messages (period range, mode, period key) to a Pro reader",
    ),
    ("app/routers/analysis.py", "export_analysis_xlsx.dataset_for_export"): (
        2, "the 400s carry build_dataset's ValueError and IncompatibleUnitsError messages to a Pro reader",
    ),
    ("app/routers/feedback.py", "submit_feedback_with_attachments"): (
        1, "the 422 carries FeedbackImageError's fixed code (format, animation, dimensions, input_size, ...), never "
           "a library's text",
    ),
    ("app/routers/auth.py", "_require_new_collection"): (
        1, "high-risk file: the 503 carries CollectionUnavailable's fixed closure message; not changed here",
    ),
    ("app/routers/auth.py", "register"): (
        1, "high-risk file: the 503 carries CollectionUnavailable's fixed closure message; not changed here",
    ),
    ("app/routers/auth.py", "google_start"): (
        1, "high-risk file: the 503 carries CollectionUnavailable's fixed closure message; not changed here",
    ),
    ("app/routers/auth.py", "apple_start"): (
        1, "high-risk file: the 503 carries CollectionUnavailable's fixed closure message; not changed here",
    ),
    ("app/routers/admin.py", "create_free_account"): (
        1, "high-risk file, admin only: the 409 carries AccountInvitationRequired's message; not changed here",
    ),
    ("app/routers/internal.py", "_enqueue_durable"): (
        1, "high-risk file, cron token only: the 400 carries enqueue_internal_job's ValueError; not changed here",
    ),
}


def _is_caught(node: ast.AST, name: str) -> bool:
    return isinstance(node, ast.Name) and node.id == name


def detail_uses_caught_text(detail: ast.expr, name: str) -> bool:
    """Whether a detail expression puts the caught exception ``name`` into the text it builds."""
    if _is_caught(detail, name):
        return True
    for node in ast.walk(detail):
        if isinstance(node, ast.FormattedValue) and _is_caught(node.value, name):
            return True
        if isinstance(node, ast.BinOp) and (_is_caught(node.left, name) or _is_caught(node.right, name)):
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


def _is_http_exception(call: ast.Call) -> bool:
    func = call.func
    return (isinstance(func, ast.Name) and func.id == "HTTPException") or (
        isinstance(func, ast.Attribute) and func.attr == "HTTPException"
    )


class _SiteFinder(ast.NodeVisitor):
    """Collect (enclosing function, lineno) for each HTTPException whose detail is built from the caught exception."""

    def __init__(self) -> None:
        self.hits: list[tuple[str, int]] = []
        self._functions: list[str] = []
        self._caught: list[str] = []

    def _scope(self) -> str:
        return ".".join(self._functions) if self._functions else "<module>"

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
        if self._caught and _is_http_exception(node):
            details = [keyword.value for keyword in node.keywords if keyword.arg == "detail"] + node.args[1:2]
            if any(detail_uses_caught_text(detail, name) for detail in details for name in self._caught):
                self.hits.append((self._scope(), node.lineno))
        self.generic_visit(node)


def sites_in(source: str) -> list[tuple[str, int]]:
    finder = _SiteFinder()
    finder.visit(ast.parse(source))
    return finder.hits


def test_router_details_built_from_a_caught_exception_match_the_allowlist():
    found: dict[tuple[str, str], list[int]] = {}
    for path in sorted(ROUTERS_DIR.rglob("*.py")):
        relative = path.relative_to(BACKEND_DIR).as_posix()
        for scope, lineno in sites_in(path.read_text(encoding="utf-8")):
            found.setdefault((relative, scope), []).append(lineno)

    unlisted = {key: lines for key, lines in found.items() if key not in ALLOWED}
    assert not unlisted, (
        "A router builds an HTTPException detail from the exception it caught, which sends the error's text "
        "(SQL, parameters, provider bodies) to the caller. Log it with logger.exception and answer a fixed detail: "
        + ", ".join(f"{file}:{lines} in {scope}" for (file, scope), lines in sorted(unlisted.items()))
    )
    counts = {key: len(lines) for key, lines in found.items()}
    expected = {key: count for key, (count, _reason) in ALLOWED.items()}
    assert counts == expected, (
        "A listed site's count changed or it is gone; lower or remove its entry in ALLOWED: "
        f"found {dict(sorted(counts.items()))}"
    )


def test_each_form_of_a_detail_built_from_the_caught_exception_is_found():
    forms = [
        'f"Error: {exc}"',
        'f"Error: {str(exc)}"',
        'f"Error: {repr(exc)}"',
        '"Error: " + str(exc)',
        '"Error: %s" % exc',
        '"Error: {}".format(exc)',
        '"Error: {e}".format(e=exc)',
        "str(exc)",
        "repr(exc)",
        "exc",
    ]
    for form in forms:
        for call in (f"HTTPException(status_code=500, detail={form})", f"HTTPException(500, {form})"):
            source = f"def route():\n    try:\n        pass\n    except Exception as exc:\n        raise {call} from exc\n"
            assert sites_in(source) == [("route", 5)], call


def test_a_fixed_detail_or_a_detail_outside_the_handler_is_not_found():
    fixed = (
        "def route(name):\n"
        "    try:\n"
        "        pass\n"
        "    except Exception as exc:\n"
        "        logger.exception('failed')\n"
        "        raise HTTPException(status_code=500, detail='We could not load this.') from exc\n"
        "    raise HTTPException(status_code=404, detail=f'No {name}')\n"
    )
    assert sites_in(fixed) == []
