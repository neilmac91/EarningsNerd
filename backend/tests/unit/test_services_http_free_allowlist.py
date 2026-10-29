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
``fastapi.concurrency`` is exempt everywhere: ``run_in_threadpool`` offloads blocking work and
carries no HTTP meaning. ``app.api_errors`` counts as the HTTP layer (E31): it holds ``CodedHTTPException``,
so a service imports the HTTP-free ``app.error_codes`` instead. A relative import is resolved against the importing
file's package before it is compared (``from ...api_errors import CodedHTTPException`` in
``app/services/summary_stages/`` is ``app.api_errors``).
"""
import ast
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
_HTTP_APP_MODULES = {"app.api_errors"}


def _resolved(node: ast.ImportFrom, package: list[str]):
    """The absolute module a `from` import names: a relative one (`from ...api_errors import X`) is resolved against
    the importing file's package, as Python resolves it. None when it climbs above the top package."""
    if node.level == 0:
        return node.module
    if node.level - 1 > len(package):
        return None
    base = package[: len(package) - (node.level - 1)]
    return ".".join(base + ([node.module] if node.module else []))


def _http_imports_in(source: str, package: list[str]) -> list[tuple[int, str]]:
    """Each (line, module) of ``source`` that imports the HTTP layer, for a file in the dotted ``package``."""
    hits: list[tuple[int, str]] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and (module := _resolved(node, package)):
            # `from app import api_errors` (or `from . import api_errors`) names the module as an imported name.
            named = (f"{module}.{alias.name}" for alias in node.names)
            modules = [module, *(name for name in named if name in _HTTP_APP_MODULES)]
        else:
            continue
        for module in modules:
            if (module.split(".")[0] in _HTTP_ROOTS and module not in _EXEMPT_MODULES) or module in _HTTP_APP_MODULES:
                hits.append((node.lineno, module))
    return hits


def _http_imports(path: Path) -> list[tuple[int, str]]:
    package = list(path.resolve().relative_to(BACKEND_DIR).parts[:-1])
    return _http_imports_in(path.read_text(encoding="utf-8"), package)


PLANTED_HTTP_IMPORTS = {
    # (source, the importing file's package) -> the modules it must report
    "an absolute import": ("from app.api_errors import CodedHTTPException\n", ["app", "services"], ["app.api_errors"]),
    "a relative import up two packages": (
        "from ...api_errors import CodedHTTPException\n", ["app", "services", "summary_stages"], ["app.api_errors"]),
    "the module as a relative name": ("from . import api_errors\n", ["app"], ["app.api_errors"]),
    "the module from its parent": ("from .. import api_errors\n", ["app", "services"], ["app.api_errors"]),
    "fastapi, absolute": ("from fastapi import HTTPException\n", ["app", "services"], ["fastapi"]),
    "the exempt concurrency helper": ("from fastapi.concurrency import run_in_threadpool\n", ["app", "services"], []),
    "the HTTP-free vocabulary, relative": ("from ..error_codes import ErrorCode\n", ["app", "services"], []),
    "a sibling service, relative": ("from .user_account_service import delete_account\n", ["app", "services"], []),
}


def test_the_walk_resolves_relative_imports():
    assert {
        name: [module for _line, module in _http_imports_in(source, package)]
        for name, (source, package, _expected) in PLANTED_HTTP_IMPORTS.items()
    } == {name: expected for name, (_source, _package, expected) in PLANTED_HTTP_IMPORTS.items()}


def test_services_import_no_http_layer_outside_the_allowlist():
    found: dict[str, list[str]] = {}
    for py in sorted(SERVICES_DIR.rglob("*.py")):
        rel = py.relative_to(BACKEND_DIR).as_posix()
        for lineno, module in _http_imports(py):
            found.setdefault(rel, []).append(f"{rel}:{lineno} imports {module}")

    unexpected = sorted(loc for rel, locs in found.items() if rel not in ALLOWED_HTTP_IMPORTERS for loc in locs)
    stale = sorted(rel for rel in ALLOWED_HTTP_IMPORTERS if rel not in found)
    assert not unexpected and not stale, (
        "app/services/ imports of fastapi/starlette drifted from the allow-list.\n"
        f"  unexpected: {unexpected}\n"
        f"  stale (no longer imports the HTTP layer — prune it): {stale}\n"
        "Keep HTTP in the router: return a value or raise a domain exception from the service, and "
        "map it to the HTTPException, cookie or header in the router. run_in_threadpool comes from "
        "fastapi.concurrency, which is exempt."
    )


def test_walk_reaches_the_services():
    assert len(list(SERVICES_DIR.rglob("*.py"))) > 50
