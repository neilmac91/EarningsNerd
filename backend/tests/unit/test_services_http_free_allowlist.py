"""Structural gate: ``app/services/`` stays free of the HTTP layer (CLAUDE.md "Where things live").

The router ORM ratchet (``test_router_orm_ceilings_allowlist.py``) moves queries and business rules
out of ``app/routers/`` into ``app/services/``. That only thins the routers if the HTTP layer does
not move with them: a service that raises ``HTTPException``, reads a ``Request`` or sets a cookie
is a router in the wrong directory, and every other caller (Cloud Run jobs, the task worker, other
services) inherits status codes it cannot mean. Services signal outcomes with return values or
their own domain exceptions (``RefreshTokenError``, ``EarningsAlertLimitError``) and the router
maps them to HTTP.

An AST walk over ``app/services/**/*.py`` collects every ``fastapi``/``starlette`` import and
compares the importing files against a checked-in allow-list. A new importer fails with file:line;
an allow-listed file that stops importing fails too, so the list cannot go stale.
``fastapi.concurrency`` is exempt everywhere, imported as ``from fastapi.concurrency import ...`` or ``import
fastapi.concurrency as ...``: ``run_in_threadpool`` offloads blocking work and carries no HTTP meaning. A bare
``import fastapi.concurrency`` binds ``fastapi`` itself, so it counts as ``fastapi``, and so does ``from fastapi import
concurrency``, which the walk reads as an import from ``fastapi``. The app's own HTTP modules count too:
``app.api_errors``, ``app.dependencies`` and the ``app.routers`` package. ``app.api_errors`` (E31) holds
``CodedHTTPException``, so a service imports the HTTP-free ``app.error_codes`` instead. A relative
import is resolved against the importing file's package before it is compared (``from ...api_errors import
CodedHTTPException`` in ``app/services/summary_stages/`` is ``app.api_errors``).

Out of scope: the walk reads each file's own import statements, not what the modules it imports import or
re-export (a service importing a helper module that itself imports ``fastapi`` passes), and static imports only
(``importlib.import_module`` and ``__import__`` pass).
"""
import ast
import importlib.util
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
SERVICES_DIR = BACKEND_DIR / "app" / "services"

# File (relative to backend/) -> why it may import the HTTP layer.
ALLOWED_HTTP_IMPORTERS: dict[str, str] = {
    "app/services/rate_limiter.py": (
        "the per-IP burst limiter reads the Request's trusted client IP and raises the 429 itself"
    ),
    "app/services/turnstile.py": "the Turnstile check reads the Request's token header and raises the 403/503 itself",
    "app/services/logging_service.py": "request-logging middleware (BaseHTTPMiddleware, Request, Response)",
}

_HTTP_ROOTS = {"fastapi", "starlette"}
_EXEMPT_MODULES = {"fastapi.concurrency"}
_HTTP_APP_MODULES = {"app.api_errors", "app.dependencies"}
_HTTP_APP_PACKAGES = {"app.routers"}


def _is_http_app_module(module: str) -> bool:
    """Whether ``module`` is one of the app's own HTTP modules."""
    return module in _HTTP_APP_MODULES or any(
        module == package or module.startswith(f"{package}.") for package in _HTTP_APP_PACKAGES)


def _is_http(module: str) -> bool:
    """Whether importing ``module`` brings in the HTTP layer."""
    if module.split(".")[0] in _HTTP_ROOTS:
        return module not in _EXEMPT_MODULES
    return _is_http_app_module(module)


def _resolved(node: ast.ImportFrom, package: list[str]) -> str | None:
    """The absolute module a `from` import names: a relative one (`from ...api_errors import X`) is resolved against
    the importing file's package by Python's own resolver. None when it climbs above the top package."""
    if node.level == 0:
        return node.module
    try:
        return importlib.util.resolve_name("." * node.level + (node.module or ""), ".".join(package))
    except ImportError:
        return None


def _http_imports_in(source: str, package: list[str]) -> list[tuple[int, str]]:
    """Each (line, module) of ``source`` that imports the HTTP layer, for a file whose package is ``package`` (its
    dotted parts)."""
    hits: list[tuple[int, str]] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            # Without ``as``, ``import a.b`` binds ``a``, the whole package: an exempt submodule exempts nothing then.
            modules = [alias.name if alias.asname or alias.name not in _EXEMPT_MODULES else alias.name.split(".")[0]
                       for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and (module := _resolved(node, package)):
            # `from app import api_errors` (or `from . import api_errors`) names the module as an imported name.
            named = (f"{module}.{alias.name}" for alias in node.names)
            modules = [module] if _is_http(module) else [name for name in named if _is_http_app_module(name)]
        else:
            continue
        hits.extend((node.lineno, module) for module in modules if _is_http(module))
    return hits


def _package_of(path: Path) -> list[str]:
    """A file's package, as its dotted parts: a module's is its directory's, and so is a package's ``__init__.py``."""
    return list(path.resolve().relative_to(BACKEND_DIR).parts[:-1])


def _http_imports(path: Path, source: str | None = None) -> list[tuple[int, str]]:
    """Each (line, module) of the file at ``path`` that imports the HTTP layer; ``source`` stands in for its text."""
    return _http_imports_in(path.read_text(encoding="utf-8") if source is None else source, _package_of(path))


STAGE = "app/services/summary_stages/stage.py"
PLANTED_HTTP_IMPORTS = {
    # name -> (the importing file, relative to backend/; its source; the modules it must report)
    "an absolute import": ("app/services/x.py", "from app.api_errors import CodedHTTPException\n", ["app.api_errors"]),
    "a stage's relative import up two packages": (
        STAGE, "from ...api_errors import CodedHTTPException\n", ["app.api_errors"]),
    "one inside a function": (
        STAGE, "def build():\n    from ...api_errors import CodedHTTPException\n", ["app.api_errors"]),
    "a package's own relative import": (
        "app/services/summary_stages/__init__.py", "from ... import api_errors\n", ["app.api_errors"]),
    "the module from its parent": ("app/services/x.py", "from .. import api_errors\n", ["app.api_errors"]),
    "the module as a relative name": ("app/x.py", "from . import api_errors\n", ["app.api_errors"]),
    "fastapi, absolute": ("app/services/x.py", "from fastapi import HTTPException\n", ["fastapi"]),
    "the exempt concurrency helper": ("app/services/x.py", "from fastapi.concurrency import run_in_threadpool\n", []),
    "the HTTP-free vocabulary, relative": ("app/services/x.py", "from ..error_codes import ErrorCode\n", []),
    "a sibling service, relative": ("app/services/x.py", "from .user_account_service import delete_account\n", []),
    # Python refuses it (beyond the top-level package), so it imports nothing.
    "one above the top package": ("app/services/x.py", "from ...fastapi import HTTPException\n", []),
    "a bare concurrency import, which binds fastapi": ("app/services/x.py", "import fastapi.concurrency\n", ["fastapi"]),
    "the concurrency module under a name of its own": (
        "app/services/x.py", "import fastapi.concurrency as concurrency\n", []),
    "the router dependencies": ("app/services/x.py", "from app.dependencies import require_pro\n", ["app.dependencies"]),
    "a router module": ("app/services/x.py", "from app.routers import auth\n", ["app.routers"]),
    "a router module, relative": ("app/services/x.py", "from ..routers.auth import router\n", ["app.routers.auth"]),
    "the router dependencies by name": ("app/services/x.py", "from .. import dependencies\n", ["app.dependencies"]),
}


def test_the_walk_resolves_relative_imports():
    assert {
        name: [module for _line, module in _http_imports(BACKEND_DIR / rel, source)]
        for name, (rel, source, _expected) in PLANTED_HTTP_IMPORTS.items()
    } == {name: expected for name, (_rel, _source, expected) in PLANTED_HTTP_IMPORTS.items()}


def test_services_import_no_http_layer_outside_the_allowlist():
    found: dict[str, list[str]] = {}
    for py in sorted(SERVICES_DIR.rglob("*.py")):
        rel = py.relative_to(BACKEND_DIR).as_posix()
        for lineno, module in _http_imports(py):
            found.setdefault(rel, []).append(f"{rel}:{lineno} imports {module}")

    unexpected = sorted(loc for rel, locs in found.items() if rel not in ALLOWED_HTTP_IMPORTERS for loc in locs)
    stale = sorted(rel for rel in ALLOWED_HTTP_IMPORTERS if rel not in found)
    assert not unexpected and not stale, (
        "app/services/ imports of the HTTP layer (fastapi, starlette, the app's HTTP modules) drifted from the allow-list.\n"
        f"  unexpected: {unexpected}\n"
        f"  stale (no longer imports the HTTP layer — prune it): {stale}\n"
        "Keep HTTP in the router: return a value or raise a domain exception from the service, and "
        "map it to the HTTPException, cookie or header in the router. run_in_threadpool comes from "
        "fastapi.concurrency, which is exempt."
    )


def test_walk_reaches_the_services():
    assert len(list(SERVICES_DIR.rglob("*.py"))) > 50
