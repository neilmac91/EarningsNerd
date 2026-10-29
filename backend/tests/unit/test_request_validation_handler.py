"""Every refused request's 422 carries each error's type, loc and msg only, on every route of the API (E97-H1).

``main.py`` answers ``RequestValidationError`` with ``auth_validation.public_validation_errors``. FastAPI's default
answer quoted each refused value (for a missing field, the whole body) and could not render a lone surrogate, a 500
whose traceback carried every input. ``test_password_byte_limit.py``'s E97 section holds the password routes; this file
holds the handler's reach: a body on another router, a query and a path parameter, every error of a request; and every
FastAPI app in backend code. A reader of each module's source finds the modules that build one, one ``FastAPI(...)``
call to a module; each is imported (so a module that builds an app must be safe to import, and the process logging the
task worker's first import configures is put back), and the one app it keeps at module level (keeping none, or more than
one, fails) is read as it runs. That app mounts no other at any depth (behind the mount's own middleware, or one that
keeps the app it wraps as ``app``) and answers ``RequestValidationError`` with a function whose own code names
``public_validation_errors``, or with FastAPI's default while it is listed with the row that will change that. Read from
the app, the handler is the one registered however the module registered it; one that is not such a function (a partial,
the sanitizer itself, a decorator's wrapper that does not name it) fails closed, as does one that sanitizes only through
a helper: register a function whose own code names the sanitizer.

Out of the app finder's reach, in a module where it counts no ``FastAPI(...)`` call (where it counts one, the count of
the apps a module keeps fails any further app kept at module level), review-checked and the planted gap marked: an app
built through a subclass of ``FastAPI``, ``functools.partial``, ``getattr``, ``importlib``, ``__import__``,
``sys.modules``, a star import, a name another module re-exports, a class attribute (planted), a ``with`` or ``match``
binding, a walrus inside another assignment, a function or a cast that returns the class, a starred value, a parameter's
default, a container element or a loop variable, or by one call that runs more than once (a factory, a loop). Out of the
checks' reach, review-checked: a module that keeps another module's app while its own sits in a container; a builder
module's further app held other than at module level (a list, an attribute) and never mounted, its one call's second app
among them; an app wrapped, before it is mounted, in a middleware that holds it other than as ``app`` (planted); and
whether a handler other than main.py's (which the route cases hold) answers through ``public_validation_errors`` rather
than only naming it, adds nothing beside it (``exc.body``), and is the only answer to a refused request (a route class,
a dependency or a middleware can answer one itself). On Python 3.11 a comprehension's body is code of its own, so a
handler that calls the sanitizer only inside one fails closed.
"""
import ast
import importlib
import json
import logging
from functools import partial, wraps

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.exception_handlers import request_validation_exception_handler as fastapi_default_answer
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.routing import Host, Mount

import main
from app.services import auth_validation
from app.services.auth_validation import public_validation_errors
from tests.support.summary_stream_harness import reset_rate_limiters
from tests.support.worker_logging import LIBRARY_LOGGERS, preserved_logging
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
    """Each (name, value) a module binds by an assignment (each of a chain's targets), an annotated assignment or a
    walrus: a tuple or list target takes the element of a tuple or list value at its place, counted from the end
    after a starred target (which itself takes a list); a conditional or a boolean value, each value it may be."""
    for node in ast.walk(tree):
        pairs = []
        if isinstance(node, ast.Assign):
            pairs = [(target, node.value) for target in node.targets]
        elif isinstance(node, (ast.AnnAssign, ast.NamedExpr)) and node.value is not None:
            pairs = [(node.target, node.value)]
        while pairs:
            target, value = pairs.pop()
            if isinstance(value, ast.IfExp):
                pairs += [(target, value.body), (target, value.orelse)]
            elif isinstance(value, ast.BoolOp):
                pairs += [(target, each) for each in value.values]
            elif isinstance(target, ast.Name):
                yield target.id, value
            elif isinstance(target, (ast.Tuple, ast.List)) and isinstance(value, (ast.Tuple, ast.List)):
                starred = [at for at, element in enumerate(target.elts) if isinstance(element, ast.Starred)]
                if not starred and len(target.elts) == len(value.elts):
                    pairs.extend(zip(target.elts, value.elts))
                elif len(starred) == 1 and len(value.elts) >= len(target.elts) - 1:
                    after = len(target.elts) - starred[0] - 1
                    pairs.extend(zip(target.elts[:starred[0]], value.elts[:starred[0]]))
                    pairs.extend(zip(target.elts[len(target.elts) - after:], value.elts[len(value.elts) - after:]))


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
    """The names a module binds to ``name`` from one of ``modules``, and the names it binds to those modules: by a
    ``from`` import of the name or of a submodule (or their aliases), by an import of one of the modules under an alias,
    by an import without an alias of any submodule of a top package among them (``import fastapi.exceptions`` binds
    ``fastapi``), and by any binding (``_bindings``) of a name already bound, of an attribute naming ``name`` on a bound
    module, or of one of those modules itself, until no binding adds a name."""
    names, module_names = set(), set()
    parents = {module.rsplit(".", 1)[0]: module.rsplit(".", 1)[1] for module in modules if "." in module}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in modules:
            names |= {alias.asname or alias.name for alias in node.names if alias.name == name}
        if isinstance(node, ast.ImportFrom) and node.module in parents:
            module_names |= {alias.asname or alias.name for alias in node.names if alias.name == parents[node.module]}
        if isinstance(node, ast.Import):
            module_names |= {alias.asname for alias in node.names if alias.asname and alias.name in modules}
            module_names |= {alias.name.split(".")[0] for alias in node.names
                             if not alias.asname and alias.name.split(".")[0] in modules}
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
    """How many calls in a module build a FastAPI app, through a name or a module ``_bound`` reads."""
    classes, modules = _bound(tree, ("fastapi", "fastapi.applications"), "FastAPI")
    return sum(isinstance(node, ast.Call) and _names(node.func, classes, modules, "FastAPI") for node in ast.walk(tree))


def _module_name(path: str) -> str:
    """The name a scanned file is imported by: a package's ``__init__.py`` is the package, which an import under
    ``.__init__`` would run a second time."""
    return path.removesuffix(".py").replace("/", ".").removesuffix(".__init__")


def _answers_through_the_sanitizer(app) -> bool:
    """Whether an app, as it runs, answers ``RequestValidationError`` with a function whose own code names
    ``public_validation_errors``; any other handler, FastAPI's default among them, fails closed."""
    handler = app.exception_handlers.get(RequestValidationError)
    return SANITIZER in getattr(getattr(handler, "__code__", None), "co_names", ())


def _served(app):
    """The app a mount serves, past each middleware around it that keeps the app it wraps as ``app``; one that holds it
    otherwise ends the walk."""
    for _ in range(20):
        if app is None or isinstance(app, Starlette):
            return app
        app = getattr(app, "app", None)
    return None


def _mounted_apps(routes) -> list[str]:
    """Where an app is mounted at any depth of a route list (the path within its router, empty at its root, or a
    host): an included router's routes, a mount's own routes, and a mount's app behind the mount's own middleware or
    behind middleware wrapped around it first that keeps it as ``app``."""
    found = []
    for route in routes:
        served = _served(getattr(route, "_base_app", None)) or _served(getattr(route, "app", None))
        if served is not None:
            path = getattr(route, "path", None)
            found.append(path if path is not None else getattr(route, "host", None))
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
    ("from fastapi import applications as apps\napp = apps.FastAPI()", 1),
    ("import fastapi.exceptions\napp = fastapi.FastAPI()", 1),
    ("from fastapi import FastAPI\nApi = Other = FastAPI\napp = Other()", 1),
    ("from fastapi import FastAPI\n[Api, _] = [FastAPI, None]\napp = Api()", 1),
    ("from fastapi import FastAPI\nApi, *_ = FastAPI, None, None\napp = Api()", 1),
    ("from fastapi import FastAPI\n*_, Api = None, None, FastAPI\napp = Api()", 1),
    ("from fastapi import FastAPI\nApi = FastAPI if True else None\napp = Api()", 1),
    ("from fastapi import FastAPI\nApi = None if True else FastAPI\napp = Api()", 1),
    ("from fastapi import FastAPI\nApi = FastAPI or None\napp = Api()", 1),
    ("from fastapi import FastAPI\nApi = None or FastAPI\napp = Api()", 1),
    # The alias is bound deeper in the tree (inside a try) than the line that reads it, which the walk meets first:
    # only a second pass over the bindings finds it.
    ("from fastapi import FastAPI\ntry:\n    Api = FastAPI\nexcept ImportError:\n    Api = None\nNamed = Api\n"
     "app = Named()", 1),
    ("from fastapi import FastAPI\napp = FastAPI()\nv2 = FastAPI()\napp.mount('/v2', v2)", 2),
    # A gap the module docstring names: an app built through a class attribute is not counted.
    ("from fastapi import FastAPI\nclass Factory:\n    build = FastAPI\napp = Factory.build()", 0),
    ("from fastapi import FastAPI\n", 0),
    ("from fastapi import APIRouter\nrouter = APIRouter()", 0),
    ("FastAPI = object\napp = FastAPI()", 0),
    ("import mylib\napp = mylib.FastAPI()", 0),
    ("import mylib.fastapi\napp = mylib.FastAPI()", 0),
], ids=["name", "alias", "module", "module-alias", "submodule", "from-submodule", "from-package", "assigned",
        "assigned-attribute", "assigned-submodule-attribute", "annotated", "tuple", "walrus", "module-assigned",
        "submodule-assigned", "from-package-alias", "top-package-bound-by-a-submodule", "chained", "list",
        "star-last", "star-first", "conditional-then", "conditional-else", "boolean-first", "boolean-last",
        "bound-deeper", "two-apps", "gap-class-attribute",
        "import-only", "router", "unbound", "look-alike", "look-alike-submodule"])
def test_the_app_finder_scores_its_planted_forms(source, calls):
    assert _app_calls(ast.parse(source)) == calls


@pytest.mark.parametrize("path, name", [
    ("main.py", "main"), ("scripts/deploy_check.py", "scripts.deploy_check"),
    ("app/review_pkg/__init__.py", "app.review_pkg"),
])
def test_a_builder_is_imported_by_its_module_name(path, name):
    assert _module_name(path) == name


async def _sanitizing(request, exc):
    return public_validation_errors(exc.errors())


async def _through_the_module(request, exc):
    return auth_validation.public_validation_errors(exc.errors())


async def _echoing(request, exc):
    return exc.errors()


async def _echoing_beside_a_default(request, exc, sanitize=public_validation_errors):
    return exc.errors()


def _tidy(errors):
    return public_validation_errors(errors)


async def _through_a_helper(request, exc):
    return _tidy(exc.errors())


def _answering(sanitize):
    async def answer(request, exc):
        return exc.errors()
    return answer


def _echoing_decorator(handler):
    @wraps(handler)
    async def wrapper(request, exc):
        return exc.errors()
    return wrapper


HANDLERS = {
    "a-sanitizing-def": (_sanitizing, RequestValidationError, True),
    "a-sanitizing-lambda": (lambda request, exc: public_validation_errors(exc.errors()), RequestValidationError, True),
    "through-the-module": (_through_the_module, RequestValidationError, True),
    # Each fails closed: the function the app answers with does not name the sanitizer in its own code.
    "fastapi-s-default": (None, RequestValidationError, False),
    "an-echoing-def": (_echoing, RequestValidationError, False),
    "a-default-names-it": (_echoing_beside_a_default, RequestValidationError, False),
    "a-lambda-s-default-names-it": (lambda request, exc, sanitize=public_validation_errors: exc.errors(),
                                    RequestValidationError, False),
    "through-a-helper": (_through_a_helper, RequestValidationError, False),
    "a-wrapper-handed-the-sanitizer": (_answering(public_validation_errors), RequestValidationError, False),
    "a-partial": (partial(_echoing_beside_a_default, sanitize=public_validation_errors), RequestValidationError, False),
    "the-sanitizer-itself": (public_validation_errors, RequestValidationError, False),
    "an-echoing-decorator-around-it": (_echoing_decorator(_sanitizing), RequestValidationError, False),
    "registered-for-another-class": (_sanitizing, ValueError, False),
}


@pytest.mark.parametrize("handler, exception, answers", HANDLERS.values(), ids=HANDLERS)
def test_the_runtime_check_reads_the_handler_the_app_answers_with(handler, exception, answers):
    app = FastAPI()
    if handler is not None:
        app.add_exception_handler(exception, handler)
    assert _answers_through_the_sanitizer(app) is answers


def test_a_decorated_registration_is_read_as_the_app_holds_it():
    app = FastAPI()

    @app.exception_handler(RequestValidationError)
    async def answer(request, exc):
        return public_validation_errors(exc.errors())

    assert _answers_through_the_sanitizer(app)
    assert not _answers_through_the_sanitizer(FastAPI())


class _Opaque:
    """A middleware that holds the app it wraps other than as ``app``."""

    def __init__(self, app):
        self.inner = app

    async def __call__(self, scope, receive, send):
        await self.inner(scope, receive, send)


def test_the_mount_walk_finds_an_app_at_any_depth_and_behind_middleware_that_keeps_it_as_app():
    app, router = FastAPI(), APIRouter()
    router.mount("/inner", FastAPI())
    app.include_router(router, prefix="/api")
    app.mount("/plain", FastAPI())
    app.mount("/wrapped", GZipMiddleware(FastAPI()))
    app.mount("/wrapped-twice", GZipMiddleware(GZipMiddleware(FastAPI())))
    app.routes.append(Mount("/with-middleware", app=FastAPI(), middleware=[Middleware(GZipMiddleware)]))
    app.routes.append(Mount("/with-opaque-middleware", app=FastAPI(), middleware=[Middleware(_Opaque)]))
    app.routes.append(Mount("/outer", routes=[Mount("/nested", app=FastAPI())]))
    app.routes.append(Host("review.example", app=FastAPI()))
    # A gap the module docstring names: an app wrapped, before it is mounted, in a middleware that holds it otherwise.
    app.mount("/opaque-before-mount", _Opaque(FastAPI()))
    app.mount("/", FastAPI())
    assert sorted(_mounted_apps(app.routes)) == ["", "/inner", "/nested", "/plain", "/with-middleware",
                                                 "/with-opaque-middleware", "/wrapped", "/wrapped-twice",
                                                 "review.example"]
    assert _mounted_apps(FastAPI().routes) == []


def _logging_state():
    root = logging.getLogger()
    return list(root.handlers), root.level, [logging.getLogger(name).level for name in LIBRARY_LOGGERS]


def test_every_fastapi_app_answers_a_refused_request_through_the_handler_or_is_listed():
    builders = {path.relative_to(BACKEND_DIR).as_posix(): _app_calls(ast.parse(path.read_text()))
                for path in _scanned_files()}
    builders = {path: calls for path, calls in builders.items() if calls}
    # One FastAPI(...) call to a module, so the one app each keeps at module level is the app it builds.
    assert all(calls == 1 for calls in builders.values()), builders
    assert "main.py" in builders and set(DEFAULT_ANSWER) <= set(builders), builders
    before = _logging_state()
    # The task worker's first import configures process logging (INFO, its own handler): the block puts it back, so a
    # later test that reads caplog still sees what the API process logs at DEBUG.
    with preserved_logging():
        for path in builders:
            module = importlib.import_module(_module_name(path))
            apps = [value for value in vars(module).values() if isinstance(value, FastAPI)]
            assert len(apps) == 1, f"{path} builds an app and keeps {len(apps)} at module level"
            handler = apps[0].exception_handlers.get(RequestValidationError)
            if path in DEFAULT_ANSWER:
                # FastAPI's default until the row registers the handler: the change that does removes the entry.
                assert handler is fastapi_default_answer, path
            else:
                assert _answers_through_the_sanitizer(apps[0]), path
            # A mounted app answers with its own handlers, not those of the app it is mounted in.
            assert _mounted_apps(apps[0].routes) == [], path
    assert _logging_state() == before
    assert main.app.exception_handlers[RequestValidationError] is main.request_validation_exception_handler
