"""A raised answer carries none of the headers a route set on its injected Response (E121).

FastAPI answers an exception, an ``HTTPException`` or an exception handler's 500, with a fresh response, and
drops every header and cookie the route set on the ``Response`` it was handed (the runtime cases below pin
that). A route that edits that Response and then raises in the same block sends none of the edit. ``/refresh``
deleted the session cookies that way before each refusal, and the browser never saw the deletions (E121
removed them: a refused refresh sets no cookie, on purpose,
``test_a_refused_refresh_sets_no_cookie_so_a_newer_login_keeps_its_cookies`` in ``test_auth_token_flows.py``).
Cookies, and any header set on the Response, need an answer of the route's own, as the logout's 503 is
(``test_logout_failure_clears_cookies.py``); ``HTTPException(headers=...)`` carries plain headers such as
``WWW-Authenticate`` or ``Retry-After``.

The walk reads every function in ``app/`` with a parameter annotated as FastAPI's or Starlette's ``Response``
(bare, under an import alias, dotted as ``fastapi.Response``, quoted, or inside ``Optional``, ``Annotated`` or
``| None``) and refuses a block of statements in it, or in a function nested in it, where one statement edits
that parameter and a later one raises. An edit is a call on the parameter or on one of its attributes
(``response.headers.update``), a call passed the parameter, an assignment into or deletion of one of its
attributes, or a call of, or a call passed, a function nested in the route that edits it (a thread-pool unit).
What it cannot see, left to review: the edit and the raise in different blocks (an edit, then a raise inside a
later ``if``), a helper defined outside the route that edits and raises in one call, and the parameter under
another local name.
"""
import ast
from pathlib import Path

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

APP = Path(__file__).resolve().parents[2] / "app"

_RESPONSE_MODULES = {"fastapi", "fastapi.responses", "starlette.responses"}
_WRAPPERS = {"Optional", "Annotated", "Union"}


def _response_names(tree: ast.Module) -> set[str]:
    """The local names this module gives FastAPI's or Starlette's Response. A bare ``Response`` counts unless the
    module imports that name from somewhere else (``from httpx import Response``)."""
    names, foreign = set(), False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name != "Response":
                    continue
                if node.module in _RESPONSE_MODULES:
                    names.add(alias.asname or alias.name)
                elif not alias.asname:
                    foreign = True
    if not foreign:
        names.add("Response")
    return names


def _is_response(annotation, names: set[str]) -> bool:
    if annotation is None:
        return False
    if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
        try:
            return _is_response(ast.parse(annotation.value, mode="eval").body, names)
        except SyntaxError:
            return False
    if isinstance(annotation, ast.Name):
        return annotation.id in names
    if isinstance(annotation, ast.Attribute):
        return annotation.attr == "Response" and ast.unparse(annotation.value) in _RESPONSE_MODULES
    if isinstance(annotation, ast.BinOp) and isinstance(annotation.op, ast.BitOr):
        return _is_response(annotation.left, names) or _is_response(annotation.right, names)
    if isinstance(annotation, ast.Subscript) and ast.unparse(annotation.value).split(".")[-1] in _WRAPPERS:
        inner = annotation.slice
        parts = inner.elts if isinstance(inner, ast.Tuple) else [inner]
        if ast.unparse(annotation.value).split(".")[-1] == "Annotated":
            parts = parts[:1]
        return any(_is_response(part, names) for part in parts)
    return False


def _injected_responses(function: ast.AST, names: set[str]) -> set[str]:
    arguments = function.args
    every = arguments.posonlyargs + arguments.args + arguments.kwonlyargs
    return {argument.arg for argument in every if _is_response(argument.annotation, names)}


def _rooted_at(node: ast.AST, params: set[str]) -> bool:
    """Whether ``node`` is ``param``, or an attribute, subscript or method chain off it (``response.headers[...]``)."""
    while isinstance(node, (ast.Attribute, ast.Subscript)):
        node = node.value
    return isinstance(node, ast.Name) and node.id in params


def _edits(statement: ast.stmt, params: set[str], units: set[str]) -> bool:
    if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return False
    for node in ast.walk(statement):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute) and _rooted_at(node.func.value, params):
                return True
            if isinstance(node.func, ast.Name) and node.func.id in units:
                return True
            passed = list(node.args) + [keyword.value for keyword in node.keywords]
            if any(isinstance(value, ast.Name) and value.id in params | units for value in passed):
                return True
        if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign, ast.Delete)):
            targets = node.targets if isinstance(node, (ast.Assign, ast.Delete)) else [node.target]
            if any(isinstance(target, (ast.Attribute, ast.Subscript)) and _rooted_at(target, params)
                   for target in targets):
                return True
    return False


def _editing_units(function: ast.AST, params: set[str]) -> set[str]:
    """The functions nested in ``function`` that edit the parameter, directly or through another such unit."""
    nested = [node for node in ast.walk(function)
              if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node is not function]
    units: set[str] = set()
    while True:
        found = {unit.name for unit in nested
                 if unit.name not in units and any(_edits(statement, params, units) for statement in unit.body)}
        if not found:
            return units
        units |= found


def edits_then_raises(source: str) -> list[tuple[str, int, int]]:
    """``(function, edit line, raise line)`` for each block that edits an injected Response and then raises."""
    tree = ast.parse(source)
    names = _response_names(tree)
    found = []
    for function in ast.walk(tree):
        if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        params = _injected_responses(function, names)
        if not params:
            continue
        units = _editing_units(function, params)
        for node in ast.walk(function):
            for field in ("body", "orelse", "finalbody"):
                block = getattr(node, field, None)
                if not isinstance(block, list):
                    continue
                edit = None
                for statement in block:
                    if edit is None and _edits(statement, params, units):
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
    "a log, then the edit, then the raise": """
def route(response: Response):
    logger.info("refusing")
    _clear_auth_cookie(response)
    raise HTTPException(status_code=401)
""",
    "a method on the parameter": """
def route(response: Response):
    response.delete_cookie("a")
    raise HTTPException(status_code=401)
""",
    "a method on one of its attributes": """
def route(response: Response):
    response.headers.update({"Cache-Control": "no-store"})
    raise HTTPException(status_code=400)
""",
    "an append to its raw headers": """
def route(response: Response):
    response.raw_headers.append((b"set-cookie", b"a=b"))
    raise HTTPException(status_code=401)
""",
    "an assignment into its headers": """
def route(response: Response):
    response.headers["Retry-After"] = "5"
    raise HTTPException(status_code=429)
""",
    "a deletion from its headers": """
def route(response: Response):
    del response.headers["ETag"]
    raise HTTPException(status_code=412)
""",
    "an attribute assignment": """
def route(response: Response):
    response.status_code = 202
    raise RuntimeError()
""",
    "an augmented assignment": """
def route(response: Response):
    response.status_code += 1
    raise RuntimeError()
""",
    "an annotated assignment": """
def route(response: Response):
    response.status_code: int = 202
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
    "a keyword-only parameter": """
def route(*, response: Response):
    response.set_cookie("a", "b")
    raise HTTPException(status_code=401)
""",
    "an import alias": """
from fastapi import Response as FastAPIResponse
def route(response: FastAPIResponse):
    response.set_cookie("a", "b")
    raise HTTPException(status_code=401)
""",
    "Optional, Annotated, a union and a quoted annotation": """
def optional(response: Optional[Response]):
    response.set_cookie("a", "b")
    raise HTTPException(status_code=401)
def annotated(response: Annotated[Response, Depends(x)]):
    response.set_cookie("a", "b")
    raise HTTPException(status_code=401)
def union(response: Response | None):
    response.set_cookie("a", "b")
    raise HTTPException(status_code=401)
def quoted(response: "Response"):
    response.set_cookie("a", "b")
    raise HTTPException(status_code=401)
""",
    "in a function nested in the route": """
async def route(response: Response):
    def unit():
        _set_auth_cookie(response, "t")
        raise LookupError()
    return await run(unit)
""",
    "a nested unit run in the thread pool, then the raise": """
async def route(db: Session, response: Response):
    def unit():
        return issue_session(db, user, response)
    token = await run_in_threadpool(unit)
    raise HTTPException(status_code=401)
""",
    "a nested unit called, through another unit, then the raise": """
def route(response: Response):
    def clear():
        _clear_auth_cookie(response)
    def unit():
        clear()
    unit()
    raise HTTPException(status_code=401)
""",
    "in an else branch": """
def route(response: Response, ok: bool):
    if ok:
        return {}
    else:
        _clear_auth_cookie(response)
        raise HTTPException(status_code=401)
""",
    "in a finally block": """
def route(response: Response):
    try:
        work()
    finally:
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
    "an outbound HTTP response (httpx)": """
def check(resp: httpx.Response):
    resp.raise_for_status()
    raise RuntimeError(resp.json())
""",
    "a module whose Response is httpx's": """
from httpx import Response
def check(resp: Response):
    resp.read()
    raise RuntimeError()
""",
    "a nested definition that edits, never called before the raise": """
def route(response: Response):
    def later():
        response.set_cookie("a", "b")
    raise HTTPException(status_code=401)
""",
    "a nested unit run, then a return": """
async def route(response: Response):
    def unit():
        _set_auth_cookie(response, "t")
    await run_in_threadpool(unit)
    return {}
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
    "a helper defined outside the route that edits and raises": """
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
    expected = {name: (4 if name.startswith("Optional") else 1) for name in PLANTED_REFUSED}
    assert {name: len(edits_then_raises(source)) for name, source in PLANTED_REFUSED.items()} == expected


def test_the_walk_passes_the_planted_clean_forms_and_its_stated_gaps():
    flagged = [name for name, source in {**PLANTED_PASSING, **PLANTED_GAPS}.items() if edits_then_raises(source)]
    assert flagged == []


def test_the_walk_reads_the_routes_it_guards():
    """The walk sees the session routes' injected Response and their thread-pool units, so an empty finding is
    not an empty walk."""
    tree = ast.parse((APP / "routers" / "auth.py").read_text(encoding="utf-8"))
    names = _response_names(tree)
    guarded = {
        function.name: _editing_units(function, _injected_responses(function, names))
        for function in ast.walk(tree)
        if isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)) and _injected_responses(function, names)
    }
    assert {"refresh", "login", "logout", "logout_all", "change_password"} <= guarded.keys()
    assert "rotate_and_issue" in guarded["refresh"]


# ── the premise, at runtime ───────────────────────────────────────────────────

def _app_that_edits_then_raises() -> FastAPI:
    app = FastAPI()

    @app.exception_handler(Exception)
    async def _server_error(_request, _exc):
        return JSONResponse(status_code=500, content={"detail": "server error"})

    @app.get("/refused")
    def refused(response: Response):
        response.set_cookie("planted", "1")
        response.headers["X-Planted"] = "1"
        raise HTTPException(status_code=401, detail="refused", headers={"WWW-Authenticate": "Bearer"})

    @app.get("/failed")
    def failed(response: Response):
        response.set_cookie("planted", "1")
        raise RuntimeError("boom")

    @app.get("/answered")
    def answered(response: Response):
        response.set_cookie("planted", "1")
        return {"ok": True}

    return app


def test_fastapi_drops_the_injected_responses_edits_from_a_raised_answer():
    """The gate's premise, pinned against the installed FastAPI: the edits reach the answer only when the route
    returns. HTTPException(headers=) is the one way a raised answer carries a header."""
    client = TestClient(_app_that_edits_then_raises(), raise_server_exceptions=False)

    refused = client.get("/refused")
    assert refused.status_code == 401
    assert refused.headers.get_list("set-cookie") == [] and "x-planted" not in refused.headers
    assert refused.headers["www-authenticate"] == "Bearer"

    failed = client.get("/failed")
    assert failed.status_code == 500 and failed.headers.get_list("set-cookie") == []

    answered = client.get("/answered")
    assert answered.status_code == 200 and answered.headers.get_list("set-cookie") == ["planted=1; Path=/; SameSite=lax"]
