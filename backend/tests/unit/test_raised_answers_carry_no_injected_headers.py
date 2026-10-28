"""A raised answer carries none of the headers a route set on its injected Response (E121).

FastAPI answers an exception, an ``HTTPException`` or the global handler's 500, with a fresh response, and
drops every header and cookie the route set on the ``Response`` it was handed. A route that edits that
Response and then raises in the same block sends none of the edit. ``/refresh`` deleted the session cookies
that way before each refusal, and the browser never saw the deletions (E121 removed them: a refused refresh
sets no cookie, on purpose, ``test_a_refused_refresh_sets_no_cookie_and_a_newer_login_keeps_its_session`` in
``test_auth_token_flows.py``). An answer that must carry headers is a response of the route's own, as the
logout's 503 is (``test_logout_failure_clears_cookies.py``).

The walk reads every function in ``app/`` with a parameter annotated ``Response`` and refuses a block of
statements in it, or in a function nested in it, where one statement edits that parameter and a later one
raises. An edit is a call on the parameter, a call passed it as an argument, or an assignment into one of its
attributes. What it cannot see, left to review: the edit and the raise in different blocks (an edit, then a
raise inside a later ``if``), a helper that edits and raises in one call, and the parameter under another name.
"""
import ast
from pathlib import Path

APP = Path(__file__).resolve().parents[2] / "app"


def _injected_responses(function: ast.AST) -> set[str]:
    arguments = function.args
    names = set()
    for argument in arguments.posonlyargs + arguments.args + arguments.kwonlyargs:
        annotation = argument.annotation
        if isinstance(annotation, ast.Name) and annotation.id == "Response":
            names.add(argument.arg)
        elif isinstance(annotation, ast.Attribute) and annotation.attr == "Response":
            names.add(argument.arg)
    return names


def _edits(statement: ast.stmt, names: set[str]) -> bool:
    if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return False
    for node in ast.walk(statement):
        if isinstance(node, ast.Call):
            target = node.func
            if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id in names:
                return True
            passed = list(node.args) + [keyword.value for keyword in node.keywords]
            if any(isinstance(value, ast.Name) and value.id in names for value in passed):
                return True
        if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                for part in ast.walk(target):
                    if isinstance(part, ast.Attribute) and isinstance(part.value, ast.Name) and part.value.id in names:
                        return True
    return False


def edits_then_raises(source: str) -> list[tuple[str, int, int]]:
    """``(function, edit line, raise line)`` for each block that edits an injected Response and then raises."""
    found = []
    for function in ast.walk(ast.parse(source)):
        if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        names = _injected_responses(function)
        if not names:
            continue
        for node in ast.walk(function):
            for field in ("body", "orelse", "finalbody"):
                block = getattr(node, field, None)
                if not isinstance(block, list):
                    continue
                edit = None
                for statement in block:
                    if edit is None and _edits(statement, names):
                        edit = statement
                    elif edit is not None and isinstance(statement, ast.Raise):
                        found.append((function.name, edit.lineno, statement.lineno))
                        break
    return found


PLANTED_REFUSED = {
    "a helper's deletion, a log, then the raise": """
async def route(response: Response):
    try:
        work()
    except Error as exc:
        _clear_refresh_cookie(response)
        logger.info(exc)
        raise HTTPException(status_code=401)
""",
    "a method on the parameter": """
def route(response: Response):
    response.delete_cookie("a")
    raise HTTPException(status_code=401)
""",
    "an assignment into its headers": """
def route(response: Response):
    response.headers["Retry-After"] = "5"
    raise HTTPException(status_code=429)
""",
    "an attribute assignment": """
def route(response: Response):
    response.status_code = 202
    raise RuntimeError()
""",
    "passed by keyword": """
def route(response: fastapi.Response):
    issue(response=response)
    raise HTTPException(status_code=500)
""",
    "another parameter name": """
def route(reply: Response):
    reply.set_cookie("a", "b")
    raise HTTPException(status_code=401)
""",
    "in a function nested in the route": """
async def route(response: Response):
    def unit():
        _set_auth_cookie(response, "t")
        raise LookupError()
    return await run(unit)
""",
    "in an else branch": """
def route(response: Response, ok: bool):
    if ok:
        return {}
    else:
        _clear_auth_cookie(response)
        raise HTTPException(status_code=401)
""",
}

PLANTED_PASSING = {
    "an edit, then a return": """
def route(response: Response):
    _set_auth_cookie(response, "t")
    return {}
""",
    "a raise before any edit": """
def route(response: Response, ok: bool):
    if not ok:
        raise HTTPException(status_code=401)
    _set_auth_cookie(response, "t")
    return {}
""",
    "a response of the route's own": """
def route(response: Response):
    refused = JSONResponse(status_code=401, content={})
    _clear_auth_cookie(refused)
    return refused
""",
    "a function with no injected Response": """
def helper(reply):
    reply.set_cookie("a", "b")
    raise RuntimeError()
""",
    "a nested definition that edits, which runs later": """
def route(response: Response):
    def later():
        response.set_cookie("a", "b")
    raise HTTPException(status_code=401)
""",
}

# The walk's stated gaps: each edits the Response and raises, and passes.
PLANTED_GAPS = {
    "the raise in a later block": """
def route(response: Response, ok: bool):
    _clear_auth_cookie(response)
    if not ok:
        raise HTTPException(status_code=401)
""",
    "a helper that edits and raises": """
def route(response: Response):
    refuse_and_clear(response)
""",
    "an alias": """
def route(response: Response):
    reply = response
    reply.delete_cookie("a")
    raise HTTPException(status_code=401)
""",
}


def test_no_route_edits_its_injected_response_and_then_raises():
    found = {
        f"{path.relative_to(APP.parent)}:{edit} ({function}, raises at {raised})"
        for path in sorted(APP.rglob("*.py"))
        for function, edit, raised in edits_then_raises(path.read_text(encoding="utf-8"))
    }
    assert found == set(), (
        "These blocks set headers or cookies on the injected Response and then raise; FastAPI drops them from "
        "the fresh response it builds for the exception. Answer on a response of the route's own, or drop the "
        f"edit: {sorted(found)}"
    )


def test_the_walk_refuses_the_planted_edits():
    missed = [name for name, source in PLANTED_REFUSED.items() if not edits_then_raises(source)]
    assert missed == []


def test_the_walk_passes_the_planted_clean_forms_and_its_stated_gaps():
    flagged = [name for name, source in {**PLANTED_PASSING, **PLANTED_GAPS}.items() if edits_then_raises(source)]
    assert flagged == []


def test_the_walk_reads_the_routes_it_guards():
    """The walk sees the session routes' injected Response, so an empty finding is not an empty walk."""
    source = (APP / "routers" / "auth.py").read_text(encoding="utf-8")
    guarded = {
        function.name
        for function in ast.walk(ast.parse(source))
        if isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)) and _injected_responses(function)
    }
    assert {"refresh", "login", "logout", "logout_all", "change_password"} <= guarded
