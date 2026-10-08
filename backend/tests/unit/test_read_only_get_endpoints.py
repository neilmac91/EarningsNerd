"""Structural gate: GET endpoints must be read-only (WS-8 (e), security audit + follow-up).

The API authenticates with cookies as well as bearer tokens, so a GET that mutates state is a
CSRF vector (a cross-site top-level navigation carries SameSite=Lax cookies) and — unauthenticated —
a free-abuse vector (the audit's ``/trending_tickers/refresh-prices`` fanned out to a paid API on
every hit). Two AST checks over every ``@<router>.get`` handler in ``app/routers/**`` and every
``@app.get`` route in ``main.py``:

1. **Name check** — a handler must not be NAMED with a state-changing verb (``create_``,
   ``refresh_``, ``sync_`` …). Read-only verbs that merely sound active (``generate_sitemap``
   renders XML, ``export_*`` streams a download) are deliberately not in the list.
2. **Body check** — the handler body (nested defs included) must not contain a session write
   (``db.add/add_all/delete/commit/flush/merge`` on a name called ``db``/``session``), a
   ``BackgroundTasks`` parameter or ``.add_task(`` call, or ``asyncio.create_task(``. This catches
   the ``get_*``/``search_*`` handlers the name check cannot. The check follows the handler into
   every module-level function it reaches under ``app/`` (same module, ``from app.x import f``,
   ``x_service.f`` on an imported module, a function handed to ``run_in_threadpool``, a
   ``Depends(...)`` dependency), transitively, so moving a write into ``app/services/`` keeps it in
   view; there a session is also any parameter annotated ``Session``. Limitation: methods reached
   through an instance or a class (``limiter.check()``, ``Service(db).run()``) are not followed —
   that remains a review concern.

Both allow-lists are shrink-only: a NEW hit fails with file:line and the remedy; an allow-listed
handler that no longer trips the check fails too (prune the entry — the fix is done); an entry
whose file has been deleted is tolerated so a teardown PR and this gate merge in either order.
Every entry carries its one-line justification.
"""
import ast
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
ROUTERS_DIR = BACKEND_DIR / "app" / "routers"

# Verbs that unambiguously change state. Matched as the handler name's first `_`-separated word.
MUTATING_VERBS = {
    "create", "update", "delete", "remove", "add", "set", "reset", "send", "resend", "refresh",
    "sync", "trigger", "regenerate", "mark", "toggle", "upsert", "revoke", "cancel", "purge",
    "clear", "invalidate", "save", "store", "write", "submit", "redeem", "activate", "deactivate",
    "enable", "disable", "start", "stop", "run", "retry", "rotate", "assign", "unassign", "archive",
}

# (file relative to backend/, handler) -> why the mutating NAME is tolerated for now. Empty since
# the WS-8 (a) teardown removed the last offender (trending.py::refresh_ticker_prices, #657).
ALLOWED_MUTATING_GETS: dict[tuple[str, str], str] = {}

# (file relative to backend/, handler) -> why this GET's BODY is allowed to have a side effect.
# Read-through caches persist what they just fetched; OAuth GETs are GET by protocol; the progress
# heartbeat self-heals an orphaned row. Anything new belongs on POST or needs a reason here.
ALLOWED_SIDE_EFFECTING_GETS: dict[tuple[str, str], str] = {
    ("app/routers/analysis.py", "get_coverage"): (
        "read-through: fires a fire-and-forget companyfacts ingest (asyncio.create_task, deduped, "
        "through the SEC limiter) when coverage is stale; the response itself is a read"
    ),
    ("app/routers/auth.py", "apple_login"): (
        "Apple sign-in GET start commits the single-use nonce/state row for the form_post callback; "
        "the signed SameSite=None, Secure cookie separately binds it to the initiating browser"
    ),
    ("app/routers/auth.py", "google_login"): (
        "shares _start_google with POST /google/start, which stores the OAuth state row only for a "
        "live invite; the GET passes invite=None, so the reachable write never runs on this route"
    ),
    ("app/routers/auth.py", "google_callback"): (
        "OAuth redirect callback — the provider returns the user via GET by protocol; creates or "
        "links the account (db.add/flush)"
    ),
    ("app/routers/companies.py", "search_companies"): (
        "read-through cache: persists Company rows discovered via the SEC ticker lookup "
        "(db.add/flush/commit under a SAVEPOINT for the concurrent-search race)"
    ),
    ("app/routers/companies.py", "get_company"): (
        "read-through cache: creates/self-heals the Company row from SEC data on a miss (db.commit)"
    ),
    ("app/routers/filings.py", "get_company_filings"): (
        "read-through cache: persists newly listed filings (db.add/commit) and kicks the history "
        "backfill / listing refresh as BackgroundTasks — the response is served from the cache"
    ),
    ("app/routers/summaries.py", "get_summary_progress"): (
        "progress heartbeat: marks an orphaned/stalled generation row as a retryable error on read "
        "(db.commit) so the client never sees an eternal 'generating'"
    ),
    ("app/routers/users.py", "get_notification_preferences"): (
        "lazy create: get_or_create_preferences inserts the default preferences row on first read "
        "(db.add/commit); the response is the defaults either way"
    ),
    ("app/routers/users.py", "export_user_data"): (
        "audit trail: the GDPR export records who downloaded their data "
        "(log_data_export -> create_audit_log, db.add/commit); the response is a read"
    ),
}

_SESSION_NAMES = {"db", "session"}
_SESSION_WRITES = {"add", "add_all", "delete", "commit", "flush", "merge"}


def _scanned_files() -> list[Path]:
    return [BACKEND_DIR / "main.py", *sorted(ROUTERS_DIR.rglob("*.py"))]


def _get_handlers(path: Path) -> list[ast.AST]:
    """Every function decorated with ``<anything>.get(...)`` (routers and ``app`` alike)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: list[ast.AST] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if any(
            isinstance(deco, ast.Call)
            and isinstance(deco.func, ast.Attribute)
            and deco.func.attr == "get"
            for deco in node.decorator_list
        ):
            out.append(node)
    return out


def _is_mutating_name(name: str) -> bool:
    return name.split("_", 1)[0].lower() in MUTATING_VERBS


def _side_effect_markers(fn: ast.AST) -> list[str]:
    """Human-readable markers (``kind@line``) for every side-effect construct in the handler body."""
    markers: list[str] = []
    session_names = set(_SESSION_NAMES)
    for arg in [*fn.args.args, *fn.args.kwonlyargs]:
        if arg.annotation is not None and "BackgroundTasks" in ast.unparse(arg.annotation):
            markers.append(f"param {arg.arg}: BackgroundTasks")
        if arg.annotation is not None and "Session" in ast.unparse(arg.annotation):
            session_names.add(arg.arg)
    for node in ast.walk(fn):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        func = node.func
        if (
            isinstance(func.value, ast.Name)
            and func.value.id in session_names
            and func.attr in _SESSION_WRITES
        ):
            markers.append(f"{func.value.id}.{func.attr}()@{node.lineno}")
        elif func.attr == "add_task":
            markers.append(f".add_task()@{node.lineno}")
        elif (
            func.attr == "create_task"
            and isinstance(func.value, ast.Name)
            and func.value.id == "asyncio"
        ):
            markers.append(f"asyncio.create_task()@{node.lineno}")
    return markers


_PARSED: dict[Path, ast.Module] = {}
_BINDINGS: dict[Path, dict[str, tuple[str, str | None]]] = {}


def _module(path: Path) -> ast.Module:
    if path not in _PARSED:
        _PARSED[path] = ast.parse(path.read_text(encoding="utf-8"))
    return _PARSED[path]


def _module_path(dotted: str) -> Path | None:
    """``app.services.audit_service`` -> its file (a module or a package ``__init__``); None outside app."""
    if dotted.split(".")[0] != "app":
        return None
    base = BACKEND_DIR.joinpath(*dotted.split("."))
    for candidate in (base.with_suffix(".py"), base / "__init__.py"):
        if candidate.is_file():
            return candidate
    return None


def _bindings(path: Path) -> dict[str, tuple[str, str | None]]:
    """Local name -> (app module, symbol) for every app import in ``path`` (function-local ones
    included); the symbol is None when the name is bound to the module itself."""
    if path not in _BINDINGS:
        package = list(path.relative_to(BACKEND_DIR).with_suffix("").parts)[:-1]
        table: dict[str, tuple[str, str | None]] = {}
        for node in ast.walk(_module(path)):
            if isinstance(node, ast.ImportFrom):
                base = package[: len(package) - node.level + 1] if node.level else []
                module = ".".join([*base, *([node.module] if node.module else [])])
                for alias in node.names:
                    local = alias.asname or alias.name
                    if _module_path(f"{module}.{alias.name}"):
                        table[local] = (f"{module}.{alias.name}", None)
                    elif _module_path(module):
                        table[local] = (module, alias.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.asname and _module_path(alias.name):
                        table[alias.asname] = (alias.name, None)
        _BINDINGS[path] = table
    return _BINDINGS[path]


def _top_level_function(path: Path, name: str) -> ast.AST | None:
    for node in _module(path).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    return None


def _resolve(module: str, symbol: str, depth: int = 0) -> tuple[Path, ast.AST] | None:
    """The module-level function ``module.symbol``, following re-exports (``from .x import f``)."""
    path = _module_path(module)
    if path is None or depth > 8:
        return None
    fn = _top_level_function(path, symbol)
    if fn is not None:
        return path, fn
    bound = _bindings(path).get(symbol)
    return _resolve(bound[0], bound[1], depth + 1) if bound and bound[1] is not None else None


def _referenced_functions(path: Path, fn: ast.AST) -> list[tuple[Path, ast.AST]]:
    """App functions ``fn`` names: called, handed to ``run_in_threadpool``, or used in ``Depends``."""
    bindings = _bindings(path)
    out: list[tuple[Path, ast.AST]] = []
    for node in ast.walk(fn):
        target = None
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            bound = bindings.get(node.id)
            if bound is not None and bound[1] is not None:
                target = _resolve(*bound)
            elif bound is None:
                local = _top_level_function(path, node.id)
                target = (path, local) if local is not None else None
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            bound = bindings.get(node.value.id)
            if bound is not None and bound[1] is None:
                target = _resolve(bound[0], node.attr)
        if target is not None:
            out.append(target)
    return out


def _reachable_markers(path: Path, handler: ast.AST) -> list[str]:
    """Side-effect markers in every app function the handler reaches, transitively."""
    seen = {(path, handler.lineno)}
    stack = _referenced_functions(path, handler)
    markers: list[str] = []
    while stack:
        fn_path, fn = stack.pop()
        if (fn_path, fn.lineno) in seen:
            continue
        seen.add((fn_path, fn.lineno))
        rel = fn_path.relative_to(BACKEND_DIR).as_posix()
        markers.extend(f"{marker} in {rel}::{fn.name}" for marker in _side_effect_markers(fn))
        stack.extend(_referenced_functions(fn_path, fn))
    return sorted(markers)


def _check(found: dict[tuple[str, str], str], allowed: dict[tuple[str, str], str], what: str, remedy: str):
    unexpected = {key: detail for key, detail in found.items() if key not in allowed}
    stale = [
        key for key in allowed
        if key not in found and (BACKEND_DIR / key[0]).exists()  # a deleted file is tolerated
    ]
    assert not unexpected and not stale, (
        f"{what}:\n"
        + "".join(f"  {file}::{name} — {detail}\n" for (file, name), detail in sorted(unexpected.items()))
        + (f"  stale allow-list entries (handler fixed — prune them): {sorted(stale)}\n" if stale else "")
        + remedy
    )


def test_get_handlers_are_not_named_as_mutations():
    found: dict[tuple[str, str], str] = {}
    for py in _scanned_files():
        rel = py.relative_to(BACKEND_DIR).as_posix()
        for fn in _get_handlers(py):
            if _is_mutating_name(fn.name):
                found[(rel, fn.name)] = f"line {fn.lineno}"

    _check(
        found,
        ALLOWED_MUTATING_GETS,
        "GET handlers named with a state-changing verb",
        "A GET must be safe and idempotent (cookie auth makes a mutating GET a CSRF vector). Make it "
        "a POST/PUT/DELETE, or rename it if it really is read-only. Extending ALLOWED_MUTATING_GETS "
        "needs a documented reason in the same PR.",
    )


def test_get_handler_bodies_have_no_side_effects():
    found: dict[tuple[str, str], str] = {}
    for py in _scanned_files():
        rel = py.relative_to(BACKEND_DIR).as_posix()
        for fn in _get_handlers(py):
            markers = _side_effect_markers(fn) + _reachable_markers(py, fn)
            if markers:
                found[(rel, fn.name)] = ", ".join(markers)

    _check(
        found,
        ALLOWED_SIDE_EFFECTING_GETS,
        "GET handlers whose body writes or spawns work",
        "A GET must not write to the session or spawn background work. Move the mutation to a "
        "POST/PUT/DELETE endpoint; if this is genuinely a read-through cache, an OAuth GET-by-protocol "
        "callback, or a self-healing read, add the (file, handler) to ALLOWED_SIDE_EFFECTING_GETS "
        "with a one-line reason in the same PR.",
    )


def test_allowlist_entries_are_actually_mutating_names():
    """Guards the gate itself: an allow-list entry that the verb rule would not flag is dead weight."""
    for (_, name) in ALLOWED_MUTATING_GETS:
        assert _is_mutating_name(name), f"{name!r} is not flagged by MUTATING_VERBS — prune it"


def test_every_allowlist_entry_carries_a_reason():
    for allowed in (ALLOWED_MUTATING_GETS, ALLOWED_SIDE_EFFECTING_GETS):
        for key, reason in allowed.items():
            assert isinstance(reason, str) and len(reason.strip()) > 20, f"{key} needs a real reason"
