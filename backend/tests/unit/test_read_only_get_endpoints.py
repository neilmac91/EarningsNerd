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
   ``x_service.f`` on an imported module, relative imports, re-exports, function-local imports, a
   function handed to ``run_in_threadpool``, a ``Depends(...)`` dependency, and every method of a
   class or module-level instance it names: ``x_service = XService()``, ``Svc().run(db)``),
   transitively, so moving a write into ``app/services/`` keeps it in view. A session there is also
   any ``Session``-annotated parameter (nested defs included) and any name bound from
   ``SessionLocal()``/``next(get_db())``; a write handed uncalled (``run_in_threadpool(db.commit)``)
   counts. ``api_route(methods=["GET"])`` handlers are GET handlers too. Limitation: the walk
   resolves names, not types, so a method on an object it cannot name (a parameter, an attribute
   of ``self``, a function's return value) is not followed; that remains a review concern.
   ``test_walk_follows_every_documented_form`` pins each form on a synthetic tree.

Both allow-lists are shrink-only: a NEW hit fails with file:line and the remedy; an allow-listed
handler that no longer trips the check fails too (prune the entry — the fix is done); an entry
whose file has been deleted is tolerated so a teardown PR and this gate merge in either order.
Every entry carries its one-line justification. An exemption is a shape, not a name: each
side-effecting GET also pins the functions (``file::qualname``) where its writes may happen, so a
new write reached from an exempt handler fails, and a moved write updates its pin.
"""
import ast
import sys
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

# (file, handler) -> every function (``file::qualname``) where that GET's side effects may happen.
# A write that moves (a router helper into a service) moves its pin in the same PR.
ALLOWED_WRITE_SITES: dict[tuple[str, str], frozenset[str]] = {
    ("app/routers/analysis.py", "get_coverage"): frozenset({
        "app/routers/analysis.py::get_coverage",
        "app/services/facts_service.py::_persist_companyfacts_payload",
        "app/services/facts_service.py::upsert_facts_bulk",
    }),
    ("app/routers/auth.py", "apple_login"): frozenset({
        "app/routers/auth.py::apple_login",
        "app/routers/auth.py::_store_oauth_state",
    }),
    ("app/routers/auth.py", "google_login"): frozenset({
        "app/routers/auth.py::_start_google",
        "app/routers/auth.py::_store_oauth_state",
    }),
    ("app/routers/auth.py", "google_callback"): frozenset({
        "app/routers/auth.py::google_callback",
        "app/routers/auth.py::_consume_oauth_state",
        "app/routers/auth.py::_oauth_create_account",
        "app/routers/auth.py::issue_session",
        "app/services/audit_service.py::create_audit_log",
        "app/services/invite_service.py::redeem_invite",
        "app/services/refresh_token_service.py::create_refresh_token",
    }),
    ("app/routers/companies.py", "search_companies"): frozenset({
        "app/routers/companies.py::search_companies",
        "app/services/company_resolution.py::resolve_or_create_company_by_cik",
    }),
    ("app/routers/companies.py", "get_company"): frozenset({
        "app/routers/companies.py::get_company",
        "app/services/company_resolution.py::resolve_or_create_company_by_cik",
    }),
    ("app/routers/filings.py", "get_company_filings"): frozenset({
        "app/routers/filings.py::get_company_filings",
        "app/services/company_resolution.py::resolve_or_create_company_by_cik",
        "app/services/filing_amendment_service.py::mark_superseded_filings",
        "app/services/filing_history_service.py::_persist_history_rows",
        "app/services/filing_scan_service.py::upsert_filings",
    }),
    ("app/routers/summaries.py", "get_summary_progress"): frozenset({
        "app/routers/summaries.py::get_summary_progress",
    }),
    ("app/routers/users.py", "get_notification_preferences"): frozenset({
        "app/services/notification_service.py::get_or_create_preferences",
    }),
    ("app/routers/users.py", "export_user_data"): frozenset({
        "app/services/audit_service.py::create_audit_log",
    }),
}

_SESSION_NAMES = {"db", "session"}
_SESSION_WRITES = {"add", "add_all", "delete", "commit", "flush", "merge"}


def _scanned_files() -> list[Path]:
    return [BACKEND_DIR / "main.py", *sorted(ROUTERS_DIR.rglob("*.py"))]


def _is_get_route(deco: ast.AST) -> bool:
    """``@<x>.get(...)``, or ``@<x>.api_route(..., methods=[..."GET"...])``."""
    if not (isinstance(deco, ast.Call) and isinstance(deco.func, ast.Attribute)):
        return False
    if deco.func.attr == "get":
        return True
    return deco.func.attr == "api_route" and any(
        kw.arg == "methods" and any(
            isinstance(m, ast.Constant) and str(m.value).upper() == "GET" for m in ast.walk(kw.value)
        )
        for kw in deco.keywords
    )


def _get_handlers(path: Path) -> list[ast.AST]:
    """Every function decorated as a GET route (routers and ``app`` alike)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [
        node for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and any(_is_get_route(deco) for deco in node.decorator_list)
    ]


def _is_mutating_name(name: str) -> bool:
    return name.split("_", 1)[0].lower() in MUTATING_VERBS


def _opens_session(expr: ast.AST) -> bool:
    """``SessionLocal()``, ``database.SessionLocal()``, ``next(get_db())``, ``Session(engine)``."""
    if not isinstance(expr, ast.Call):
        return False
    func = expr.func
    name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
    return name in {"SessionLocal", "Session", "get_db"} or (
        name == "next" and bool(expr.args) and _opens_session(expr.args[0])
    )


def _session_names_in(fn: ast.AST) -> set[str]:
    """``db``/``session``, plus every ``Session``-annotated parameter of ``fn`` or a def nested in
    it, and every name bound from a session factory (``s = SessionLocal()``, ``with ... as s``)."""
    names = set(_SESSION_NAMES)
    for node in ast.walk(fn):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            args = node.args
            for arg in [*args.posonlyargs, *args.args, *args.kwonlyargs]:
                if arg.annotation is not None and "Session" in ast.unparse(arg.annotation):
                    names.add(arg.arg)
        elif isinstance(node, ast.Assign) and _opens_session(node.value):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                if isinstance(item.optional_vars, ast.Name) and _opens_session(item.context_expr):
                    names.add(item.optional_vars.id)
    return names


def _side_effect_markers(fn: ast.AST) -> list[str]:
    """Human-readable markers (``kind@line``) for every side-effect construct in ``fn``."""
    markers: list[str] = []
    sessions = _session_names_in(fn)
    args = fn.args
    for arg in [*args.posonlyargs, *args.args, *args.kwonlyargs]:
        if arg.annotation is not None and "BackgroundTasks" in ast.unparse(arg.annotation):
            markers.append(f"param {arg.arg}: BackgroundTasks")
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        for arg in [*node.args, *(kw.value for kw in node.keywords)]:  # run_in_threadpool(db.commit)
            if isinstance(arg, ast.Attribute) and isinstance(arg.value, ast.Name) \
                    and arg.value.id in sessions and arg.attr in _SESSION_WRITES:
                markers.append(f"{arg.value.id}.{arg.attr} (passed)@{node.lineno}")
        func = node.func
        if not isinstance(func, ast.Attribute):
            continue
        if isinstance(func.value, ast.Name) and func.value.id in sessions and func.attr in _SESSION_WRITES:
            markers.append(f"{func.value.id}.{func.attr}()@{node.lineno}")
        elif func.attr == "add_task":
            markers.append(f".add_task()@{node.lineno}")
        elif func.attr == "create_task" and isinstance(func.value, ast.Name) and func.value.id == "asyncio":
            markers.append(f"asyncio.create_task()@{node.lineno}")
    return markers


_PARSED: dict[Path, ast.Module] = {}
_BINDINGS: dict[Path, dict[str, tuple[str, str | None]]] = {}
_Target = tuple[Path, ast.AST, str]  # (file, function node, qualified name in that file)


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


def _methods(path: Path, cls: ast.ClassDef) -> list[_Target]:
    return [
        (path, node, f"{cls.name}.{node.name}") for node in cls.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]


def _targets(path: Path | None, name: str, depth: int = 0) -> list[_Target]:
    """What ``name`` in module ``path`` can run: a module-level function; every method of a class,
    or of the class a module-level instance was built from (``x_service = XService()``); following
    re-exports (``from .x import f``) through the module's imports."""
    if path is None or depth > 8:
        return []
    body = _module(path).body
    for node in body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return [(path, node, name)]
        if isinstance(node, ast.ClassDef) and node.name == name:
            return _methods(path, node)
    for node in body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call) \
                and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return [t for t in _callee_targets(path, node.value.func, depth + 1) if "." in t[2]]  # class methods only
    bound = _bindings(path).get(name)
    if bound is not None and bound[1] is not None:
        return _targets(_module_path(bound[0]), bound[1], depth + 1)
    return []


def _callee_targets(path: Path, func: ast.AST, depth: int) -> list[_Target]:
    if isinstance(func, ast.Name):
        return _targets(path, func.id, depth)
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        bound = _bindings(path).get(func.value.id)
        if bound is not None and bound[1] is None:
            return _targets(_module_path(bound[0]), func.attr, depth)
    return []


def _referenced_functions(path: Path, fn: ast.AST) -> list[_Target]:
    """App code ``fn`` names: functions it calls, hands to ``run_in_threadpool`` or uses in
    ``Depends``, and every method of a class or module-level instance it names."""
    bindings = _bindings(path)
    out: list[_Target] = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            bound = bindings.get(node.id)
            if bound is None or bound[1] is not None:  # a module alias is followed through its attribute
                out.extend(_targets(path, node.id))
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            bound = bindings.get(node.value.id)
            if bound is not None and bound[1] is None:
                out.extend(_targets(_module_path(bound[0]), node.attr))
    return out


def _site(path: Path, qualname: str) -> str:
    return f"{path.relative_to(BACKEND_DIR).as_posix()}::{qualname}"


def _handler_markers(path: Path, handler: ast.AST) -> list[tuple[str, str]]:
    """(site, marker) for the handler body and every app function it reaches, transitively."""
    found = [(_site(path, handler.name), marker) for marker in _side_effect_markers(handler)]
    seen = {(path, handler.lineno)}
    stack = _referenced_functions(path, handler)
    while stack:
        fn_path, fn, qualname = stack.pop()
        if (fn_path, fn.lineno) in seen:
            continue
        seen.add((fn_path, fn.lineno))
        found.extend((_site(fn_path, qualname), marker) for marker in _side_effect_markers(fn))
        stack.extend(_referenced_functions(fn_path, fn))
    return sorted(found)


def _side_effecting_handlers(files: list[Path]) -> dict[tuple[str, str], list[tuple[str, str]]]:
    found: dict[tuple[str, str], list[tuple[str, str]]] = {}
    for py in files:
        rel = py.relative_to(BACKEND_DIR).as_posix()
        for fn in _get_handlers(py):
            markers = _handler_markers(py, fn)
            if markers:
                found[(rel, fn.name)] = markers
    return found


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
    found = {
        key: ", ".join(f"{marker} in {site}" for site, marker in markers)
        for key, markers in _side_effecting_handlers(_scanned_files()).items()
    }
    _check(
        found,
        ALLOWED_SIDE_EFFECTING_GETS,
        "GET handlers whose body writes or spawns work",
        "A GET must not write to the session or spawn background work. Move the mutation to a "
        "POST/PUT/DELETE endpoint; if this is genuinely a read-through cache, an OAuth GET-by-protocol "
        "callback, or a self-healing read, add the (file, handler) to ALLOWED_SIDE_EFFECTING_GETS "
        "with a one-line reason, and its write sites to ALLOWED_WRITE_SITES, in the same PR.",
    )


def test_exempt_gets_write_only_at_their_pinned_sites():
    found = _side_effecting_handlers(_scanned_files())
    problems: list[str] = []
    for key, pinned in sorted(ALLOWED_WRITE_SITES.items()):
        if key not in found:
            continue  # a handler that writes nowhere is reported stale by the body check
        reached = {site for site, _ in found[key]}
        problems.extend(
            f"  {key[0]}::{key[1]} reaches a write outside its pins: {site} "
            f"({', '.join(m for s, m in found[key] if s == site)})"
            for site in sorted(reached - pinned)
        )
        problems.extend(
            f"  {key[0]}::{key[1]} no longer writes at pinned {site} (moved or fixed: update the pin)"
            for site in sorted(pinned - reached)
        )
    assert not problems, (
        "Side-effecting GET exemptions drifted from their pinned write sites:\n" + "\n".join(problems)
        + "\nAn exemption covers the writes it was granted for. A new write reached from an exempt GET "
        "belongs on POST/PUT/DELETE; a write that moved (router helper -> service) moves its pin in "
        "ALLOWED_WRITE_SITES in the same PR."
    )


def test_write_site_pins_match_the_exemptions():
    assert set(ALLOWED_WRITE_SITES) == set(ALLOWED_SIDE_EFFECTING_GETS)
    assert all(ALLOWED_WRITE_SITES.values()), "an exemption pins at least one write site"


_SYNTHETIC_TREE = {
    "app/__init__.py": "",
    "app/database.py": "SessionLocal = None\ndef get_db():\n    yield None\n",
    "app/routers/__init__.py": "",
    "app/services/__init__.py": "from .pkg_impl import reexported\n",
    "app/services/w.py": "def write(db):\n    db.commit()\n",
    "app/services/pkg_impl.py": "def reexported(db):\n    db.add(1)\n",
    "app/services/svc.py": (
        "class Svc:\n    def run(self, db):\n        self._go(db)\n    def _go(self, db):\n        db.flush()\n"
        "svc = Svc()\n"
    ),
    "app/services/opener.py": (
        "from app.database import SessionLocal\n"
        "def opens():\n    with SessionLocal() as s:\n        s.merge(1)\n"
        "def assigns():\n    s = SessionLocal()\n    s.delete(1)\n"
    ),
    "app/services/nested.py": (
        "from sqlalchemy.orm import Session\n"
        "def outer():\n    def inner(conn: Session):\n        conn.add_all([])\n    return inner\n"
    ),
    "app/services/passed.py": "async def f(db):\n    await run_in_threadpool(db.commit)\n",
    "app/services/spawns.py": "import asyncio\ndef spawn(bg):\n    asyncio.create_task(bg())\n",
    "app/services/reader.py": "def read(db):\n    return db.query(1).all()\n",
    "app/routers/r.py": """\
from fastapi import APIRouter, Depends
from app.database import get_db
from app.services.w import write
from app.services import w as w_mod
import app.services.w as w_alias
from ..services.w import write as rel_write
from ..services import w as rel_mod
from app.services import reexported
from app.services.svc import svc, Svc
from app.services.reader import read

router = APIRouter()


def _local(db):
    db.delete(1)


def dep(db=Depends(get_db)):
    write(db)


@router.get("/a")
def same_module(db):
    _local(db)


@router.get("/b")
def from_import(db):
    write(db)


@router.get("/c")
def module_attribute(db):
    w_mod.write(db)


@router.get("/d")
def import_as(db):
    w_alias.write(db)


@router.get("/e")
def relative_from(db):
    rel_write(db)


@router.get("/f")
def relative_module(db):
    rel_mod.write(db)


@router.get("/g")
def package_reexport(db):
    reexported(db)


@router.get("/h")
def function_local_import():
    from app.services.opener import opens
    opens()


@router.get("/i")
def factory_assignment():
    from app.services.opener import assigns
    assigns()


@router.get("/j")
async def threadpool(db):
    await run_in_threadpool(write, db)


@router.get("/k")
def dependency(x=Depends(dep)):
    return x


@router.get("/l")
def singleton(db):
    svc.run(db)


@router.get("/m")
def class_instance(db):
    Svc().run(db)


@router.get("/n")
def nested_annotated():
    from app.services.nested import outer
    outer()


@router.get("/o")
async def passed_uncalled(db):
    from app.services.passed import f
    await f(db)


@router.get("/p")
def spawns_task():
    from app.services.spawns import spawn
    spawn(None)


@router.api_route("/q", methods=["GET", "HEAD"])
def api_route_get(db):
    write(db)


@router.get("/r")
def reads_only(db):
    return read(db)
""",
}


def test_walk_follows_every_documented_form(tmp_path, monkeypatch):
    """Each documented resolution form, on a synthetic app tree: dropping any branch of the walk
    leaves its handler unflagged and fails this test (the real tree alone would not notice)."""
    for rel, source in _SYNTHETIC_TREE.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(source, encoding="utf-8")
    module = sys.modules[__name__]
    monkeypatch.setattr(module, "BACKEND_DIR", tmp_path)
    monkeypatch.setattr(module, "_PARSED", {})
    monkeypatch.setattr(module, "_BINDINGS", {})

    found = _side_effecting_handlers([tmp_path / "app/routers/r.py"])
    flagged = {name for (_, name) in found}
    expected = {
        "same_module", "from_import", "module_attribute", "import_as", "relative_from",
        "relative_module", "package_reexport", "function_local_import", "factory_assignment",
        "threadpool", "dependency", "singleton", "class_instance", "nested_annotated",
        "passed_uncalled", "spawns_task", "api_route_get",
    }
    assert flagged == expected, f"missed: {sorted(expected - flagged)}; unexpected: {sorted(flagged - expected)}"
    assert {site for site, _ in found[("app/routers/r.py", "singleton")]} == {"app/services/svc.py::Svc._go"}


def test_allowlist_entries_are_actually_mutating_names():
    """Guards the gate itself: an allow-list entry that the verb rule would not flag is dead weight."""
    for (_, name) in ALLOWED_MUTATING_GETS:
        assert _is_mutating_name(name), f"{name!r} is not flagged by MUTATING_VERBS — prune it"


def test_every_allowlist_entry_carries_a_reason():
    for allowed in (ALLOWED_MUTATING_GETS, ALLOWED_SIDE_EFFECTING_GETS):
        for key, reason in allowed.items():
            assert isinstance(reason, str) and len(reason.strip()) > 20, f"{key} needs a real reason"
