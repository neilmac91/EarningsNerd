"""Every refused request's 422 carries each error's type, loc and msg only, on every route of the API (E97-H1).

``main.py`` answers ``RequestValidationError`` with ``auth_validation.public_validation_errors``. FastAPI's default
answer quoted each refused value (for a missing field, the whole body) and could not render a lone surrogate, a 500
whose traceback carried every input. ``test_password_byte_limit.py``'s E97 section holds the password routes; this file
holds the handler's reach: a body on another router, a query and a path parameter, every error of a request; and every
FastAPI app in backend code: one ``FastAPI(...)`` call to a module, none mounted in the API at any depth (behind a
middleware too), and each registering a handler whose body names ``public_validation_errors``, or listed with the row
that will.

Out of the app finder's reach, review-checked: an app built through a subclass of ``FastAPI``, ``functools.partial``,
``getattr``, ``importlib``, a star import, a name another module re-exports, a parameter's default, a container element
or a loop variable, or by one call that runs more than once (a factory, a loop); a handler registered other than by
``exception_handler`` or ``add_exception_handler`` (the constructor's ``exception_handlers``, the handlers mapping), or
passed as anything but a lambda or a name the module binds to a def or a lambda (such a handler fails closed); an
app mounted behind a middleware that holds it other than as ``app``, unless the mount's own ``middleware`` wraps it;
and whether a registered handler other than main.py's (which the route cases hold) answers through
``public_validation_errors`` rather than only naming it.
"""
import ast
import json

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.routing import Host, Mount

import main
from tests.support.summary_stream_harness import reset_rate_limiters
from tests.unit.test_never_echo_environment_values import BACKEND_DIR, _scanned_files

MARK = "Qx7mark"  # gitleaks:allow
# The apps that answer with FastAPI's default 422 until the row beside them registers a handler: the change that
# registers one removes its entry here.
DEFAULT_ANSWER = {"task_worker_main.py": "#1711's handoff row E97-R3"}
SANITIZER = "public_validation_errors"


@pytest.fixture(scope="module")
def client():
    with TestClient(main.app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def _fresh(client):
    reset_rate_limiters()
    client.cookies.clear()
    yield


def _contact(**fields) -> dict:
    return {"name": "Probe Name", "email": "probe@example.com", "message": MARK + " a message long enough", **fields}


@pytest.mark.requires_db
@pytest.mark.parametrize("method, path, body, detail", [
    # A body on a router other than auth's: a missing field's `input` was the whole body, the message beside it.
    ("post", "/api/contact/", {k: v for k, v in _contact().items() if k != "email"},
     [{"type": "missing", "loc": ["body", "email"], "msg": "Field required"}]),
    # A lone surrogate the default answer could not render: a 500 whose traceback quoted the message.
    ("post", "/api/contact/", _contact(message=MARK + "\ud800 a message long enough"),
     [{"type": "string_unicode", "loc": ["body", "message"],
       "msg": "Input should be a valid string, unable to parse raw data as a unicode string"}]),
    # Every error of a request, in pydantic's order.
    ("post", "/api/contact/", {},
     [{"type": "missing", "loc": ["body", field], "msg": "Field required"} for field in ("name", "email", "message")]),
    # A query and a path parameter: `input` and `ctx` (the bound) leave them too.
    ("get", "/api/companies/trending?limit=0", None,
     [{"type": "greater_than_equal", "loc": ["query", "limit"], "msg": "Input should be greater than or equal to 1"}]),
    ("get", f"/api/filings/{MARK}", None,
     [{"type": "int_parsing", "loc": ["path", "filing_id"],
       "msg": "Input should be a valid integer, unable to parse string as an integer"}]),
], ids=["body-missing-field", "body-lone-surrogate", "body-every-error", "query", "path"])
def test_every_route_answers_a_refused_request_with_type_loc_and_msg_only(client, method, path, body, detail):
    # json.dumps escapes a lone surrogate as the "\ud800" a client sends; httpx's own `json=` would raise on it.
    kwargs = {} if body is None else {"content": json.dumps(body), "headers": {"content-type": "application/json"}}
    resp = getattr(client, method)(path, **kwargs)
    assert resp.status_code == 422, resp.text
    assert resp.json() == {"detail": detail}
    assert MARK not in resp.text


def _bindings(tree: ast.Module):
    """Each (name, value) a module binds by an assignment, an annotated assignment or a walrus, a tuple target taking
    the matching element of a tuple value."""
    for node in ast.walk(tree):
        pairs = []
        if isinstance(node, ast.Assign):
            pairs = [(target, node.value) for target in node.targets]
        elif isinstance(node, (ast.AnnAssign, ast.NamedExpr)) and node.value is not None:
            pairs = [(node.target, node.value)]
        while pairs:
            target, value = pairs.pop()
            if isinstance(target, ast.Name):
                yield target.id, value
            elif (isinstance(target, (ast.Tuple, ast.List)) and isinstance(value, (ast.Tuple, ast.List))
                  and len(target.elts) == len(value.elts)):
                pairs.extend(zip(target.elts, value.elts))


def _root(node: ast.expr):
    while isinstance(node, ast.Attribute):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def _names(node: ast.expr, names: set[str], module_names: set[str], name: str) -> bool:
    """Whether an expression names the bound class: by a bound name, or as an attribute of a bound module."""
    if isinstance(node, ast.Name):
        return node.id in names
    return isinstance(node, ast.Attribute) and node.attr == name and _root(node.value) in module_names


def _bound(tree: ast.Module, modules: tuple[str, ...], name: str) -> tuple[set[str], set[str]]:
    """The names a module binds to ``name`` from one of ``modules``, and the names it binds to those modules: by an
    import or its alias, and by any binding (``_bindings``) of a name already bound, of an attribute naming ``name``
    on a bound module, or of one of those modules itself."""
    names, module_names = set(), set()
    parents = {module.rsplit(".", 1)[0]: module.rsplit(".", 1)[1] for module in modules if "." in module}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in modules:
            names |= {alias.asname or alias.name for alias in node.names if alias.name == name}
        if isinstance(node, ast.ImportFrom) and node.module in parents:
            module_names |= {alias.asname or alias.name for alias in node.names if alias.name == parents[node.module]}
        if isinstance(node, ast.Import):
            module_names |= {alias.asname or alias.name.split(".")[0] for alias in node.names if alias.name in modules}
    while True:
        before = len(names), len(module_names)
        for target, value in _bindings(tree):
            if _names(value, names, module_names, name):
                names.add(target)
            elif (isinstance(value, ast.Name) and value.id in module_names) or (
                    isinstance(value, ast.Attribute) and value.attr in parents.values()
                    and _root(value.value) in module_names):
                module_names.add(target)
        if (len(names), len(module_names)) == before:
            return names, module_names


def _app_calls(tree: ast.Module) -> int:
    """How many calls in a module build a FastAPI app, by any name the module binds the class to."""
    classes, modules = _bound(tree, ("fastapi", "fastapi.applications"), "FastAPI")
    return sum(isinstance(node, ast.Call) and _names(node.func, classes, modules, "FastAPI") for node in ast.walk(tree))


def _argument(call: ast.Call, at: int, keyword: str):
    if len(call.args) > at:
        return call.args[at]
    return next((item.value for item in call.keywords if item.arg == keyword), None)


def _validation_handlers(tree: ast.Module) -> list[ast.AST]:
    """The handlers a module registers for ``RequestValidationError``: each function an ``exception_handler``
    decorator registers, and each handler passed to ``add_exception_handler``, the class and the handler given
    positionally or by keyword, a name resolved to the def or the lambda the module binds to it (anything else stays
    as passed, and names nothing)."""
    errors, modules = _bound(tree, ("fastapi", "fastapi.exceptions"), "RequestValidationError")
    defs = {node.name: node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    lambdas = {target: value for target, value in _bindings(tree) if isinstance(value, ast.Lambda)}
    handlers = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            handlers += [node for decorator in node.decorator_list
                         if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute)
                         and decorator.func.attr == "exception_handler"
                         and (raised := _argument(decorator, 0, "exc_class_or_status_code")) is not None
                         and _names(raised, errors, modules, "RequestValidationError")]
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
              and node.func.attr == "add_exception_handler"):
            raised, handler = _argument(node, 0, "exc_class_or_status_code"), _argument(node, 1, "handler")
            if raised is not None and _names(raised, errors, modules, "RequestValidationError"):
                if isinstance(handler, ast.Name):
                    handler = defs.get(handler.id) or lambdas.get(handler.id) or handler
                handlers.append(handler)
    return handlers


def _names_the_sanitizer(handler) -> bool:
    """Whether a registered handler's own code names ``public_validation_errors`` (a bare name stays unresolved)."""
    if handler is None or isinstance(handler, ast.Name):
        return False
    return any((isinstance(node, ast.Name) and node.id == SANITIZER)
               or (isinstance(node, ast.Attribute) and node.attr == SANITIZER) for node in ast.walk(handler))


def _served(app):
    """The app a mount serves, past any middleware wrapped around it (each keeps the app it wraps as ``app``)."""
    for _ in range(20):
        if app is None or isinstance(app, Starlette):
            return app
        app = getattr(app, "app", None)
    return None


def _mounted_apps(routes) -> list[str]:
    """Where an app is mounted at any depth of a route list (the path within its router, or a host): an included
    router's routes, a mount's own routes, and a mount's app behind any middleware, before or after the mount wraps
    it."""
    found = []
    for route in routes:
        served = _served(getattr(route, "_base_app", None)) or _served(getattr(route, "app", None))
        if served is not None:
            found.append(getattr(route, "path", None) or getattr(route, "host", None))
            continue
        nested = getattr(getattr(route, "original_router", None), "routes", None)
        found += _mounted_apps(nested if nested is not None else getattr(route, "routes", None) or [])
    return found


@pytest.mark.parametrize("source, calls", [
    ("from fastapi import FastAPI\napp = FastAPI()", 1),
    ("from fastapi import FastAPI as Api\napp = Api(docs_url=None)", 1),
    ("import fastapi\napp = fastapi.FastAPI()", 1),
    ("import fastapi as fa\napp = fa.FastAPI()", 1),
    ("import fastapi.applications\napp = fastapi.applications.FastAPI()", 1),
    ("from fastapi.applications import FastAPI\napp = FastAPI()", 1),
    ("from fastapi import applications\napp = applications.FastAPI()", 1),
    ("from fastapi import FastAPI\nApi = FastAPI\nNamed = Api\napp = Named()", 1),
    ("import fastapi\nApi = fastapi.FastAPI\napp = Api()", 1),
    ("from fastapi import applications\nApi = applications.FastAPI\napp = Api()", 1),
    ("from fastapi import FastAPI\nApi: type = FastAPI\napp = Api()", 1),
    ("from fastapi import FastAPI\nApi, _ = FastAPI, None\napp = Api()", 1),
    ("from fastapi import FastAPI\nif (Api := FastAPI):\n    app = Api()", 1),
    ("import fastapi\nfa = fastapi\napp = fa.FastAPI()", 1),
    ("import fastapi\napps = fastapi.applications\napp = apps.FastAPI()", 1),
    ("from fastapi import FastAPI\napp = FastAPI()\nv2 = FastAPI()\napp.mount('/v2', v2)", 2),
    ("from fastapi import FastAPI\n", 0),
    ("from fastapi import APIRouter\nrouter = APIRouter()", 0),
    ("FastAPI = object\napp = FastAPI()", 0),
    ("import mylib\napp = mylib.FastAPI()", 0),
], ids=["name", "alias", "module", "module-alias", "submodule", "from-submodule", "from-package", "assigned",
        "assigned-attribute", "assigned-submodule-attribute", "annotated", "tuple", "walrus", "module-assigned",
        "submodule-assigned", "two-apps", "import-only", "router", "unbound", "look-alike"])
def test_the_app_finder_counts_each_form_an_import_or_a_binding_makes(source, calls):
    assert _app_calls(ast.parse(source)) == calls


REGISTRATIONS = {
    "decorator": ("from fastapi.exceptions import RequestValidationError\n"
                  "@app.exception_handler(RequestValidationError)\n"
                  "async def answer(request, exc):\n    return public_validation_errors(exc.errors())", True),
    "decorator-keyword": ("from fastapi.exceptions import RequestValidationError\n"
                          "@app.exception_handler(exc_class_or_status_code=RequestValidationError)\n"
                          "async def answer(request, exc):\n    return public_validation_errors(exc.errors())", True),
    "decorator-echoes": ("from fastapi.exceptions import RequestValidationError\n"
                         "def tidy(errors):\n    return public_validation_errors(errors)\n"
                         "@app.exception_handler(RequestValidationError)\n"
                         "async def answer(request, exc):\n    return exc.errors()", False),
    "alias": ("from fastapi.exceptions import RequestValidationError as Refused\n"
              "def answer(request, exc):\n    return auth_validation.public_validation_errors(exc.errors())\n"
              "app.add_exception_handler(Refused, answer)", True),
    "assigned": ("from fastapi.exceptions import RequestValidationError\nRefused = RequestValidationError\n"
                 "answer = lambda request, exc: public_validation_errors(exc.errors())\n"
                 "app.add_exception_handler(Refused, answer)", True),
    "assigned-attribute": ("import fastapi\nRefused = fastapi.exceptions.RequestValidationError\n"
                           "app.add_exception_handler(Refused, lambda request, exc: public_validation_errors(exc))",
                           True),
    "module": ("import fastapi.exceptions\n"
               "app.add_exception_handler(fastapi.exceptions.RequestValidationError, "
               "lambda request, exc: public_validation_errors(exc.errors()))", True),
    "keywords": ("from fastapi.exceptions import RequestValidationError\n"
                 "def answer(request, exc):\n    return public_validation_errors(exc.errors())\n"
                 "app.add_exception_handler(exc_class_or_status_code=RequestValidationError, handler=answer)", True),
    "handler-echoes": ("from fastapi.exceptions import RequestValidationError\n"
                       "def tidy(errors):\n    return public_validation_errors(errors)\n"
                       "def answer(request, exc):\n    return exc.errors()\n"
                       "app.add_exception_handler(RequestValidationError, answer)", False),
    "handler-imported": ("from fastapi.exceptions import RequestValidationError\nfrom elsewhere import answer\n"
                         "app.add_exception_handler(RequestValidationError, answer)", False),
}


@pytest.mark.parametrize("source, answers", REGISTRATIONS.values(), ids=REGISTRATIONS)
def test_the_registration_finder_reads_each_form_and_the_handler_it_registers(source, answers):
    handlers = _validation_handlers(ast.parse(source))
    assert len(handlers) == 1
    assert _names_the_sanitizer(handlers[0]) is answers


@pytest.mark.parametrize("source", [
    "from fastapi import HTTPException\n@app.exception_handler(HTTPException)\nasync def answer(request, exc): ...",
    "app.add_exception_handler(ValueError, answer)",
    "RequestValidationError = ValueError\napp.add_exception_handler(RequestValidationError, answer)",
], ids=["other-exception", "builtin", "unbound"])
def test_the_registration_finder_reads_no_other_exception(source):
    assert _validation_handlers(ast.parse(source)) == []


class _Opaque:
    """A middleware that holds the app it wraps other than as ``app``."""

    def __init__(self, app):
        self.inner = app

    async def __call__(self, scope, receive, send):
        await self.inner(scope, receive, send)


def test_the_mount_walk_finds_an_app_at_any_depth_and_behind_any_middleware():
    app, router = FastAPI(), APIRouter()
    router.mount("/inner", FastAPI())
    app.include_router(router, prefix="/api")
    app.mount("/plain", FastAPI())
    app.mount("/wrapped", GZipMiddleware(FastAPI()))
    app.routes.append(Mount("/with-middleware", app=FastAPI(), middleware=[Middleware(GZipMiddleware)]))
    app.routes.append(Mount("/with-opaque-middleware", app=FastAPI(), middleware=[Middleware(_Opaque)]))
    app.routes.append(Mount("/outer", routes=[Mount("/nested", app=FastAPI())]))
    app.routes.append(Host("review.example", app=FastAPI()))
    assert sorted(_mounted_apps(app.routes)) == [
        "/inner", "/nested", "/plain", "/with-middleware", "/with-opaque-middleware", "/wrapped", "review.example"]
    assert _mounted_apps(FastAPI().routes) == []


def test_every_fastapi_app_answers_a_refused_request_through_the_handler():
    builders = {path.relative_to(BACKEND_DIR).as_posix(): _app_calls(ast.parse(path.read_text()))
                for path in _scanned_files()}
    builders = {path: calls for path, calls in builders.items() if calls}
    # One FastAPI(...) call to a module, so the API's own checks below cover main.py's one app.
    assert all(calls == 1 for calls in builders.values()), builders
    assert "main.py" in builders and set(DEFAULT_ANSWER) <= set(builders), builders
    for path in builders:
        handlers = _validation_handlers(ast.parse((BACKEND_DIR / path).read_text()))
        if path in DEFAULT_ANSWER:
            # A listed app registers no handler yet: the change that registers one removes its entry.
            assert handlers == [], path
        else:
            assert handlers and all(_names_the_sanitizer(handler) for handler in handlers), path
    assert main.app.exception_handlers[RequestValidationError] is main.request_validation_exception_handler
    # A mounted app answers with its own handlers, not main.py's.
    assert _mounted_apps(main.app.routes) == []
