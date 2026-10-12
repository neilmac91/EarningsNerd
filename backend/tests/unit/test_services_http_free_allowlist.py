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
carries no HTTP meaning.
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


def _http_imports(path: Path) -> list[tuple[int, str]]:
    hits: list[tuple[int, str]] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules = [node.module]
        else:
            continue
        for module in modules:
            if module.split(".")[0] in _HTTP_ROOTS and module not in _EXEMPT_MODULES:
                hits.append((node.lineno, module))
    return hits


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
