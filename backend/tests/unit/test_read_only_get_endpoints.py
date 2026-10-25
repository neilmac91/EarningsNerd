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
   (``add``, ``add_all``, ``delete``, ``merge``, ``flush``, ``commit``, ``begin``, ``execute``,
   ``exec_driver_sql``, ``bulk_save_objects``, ``bulk_insert_mappings`` or
   ``bulk_update_mappings`` on a name called ``db``/``session``, or ``.update()``/``.delete()`` on
   a ``db.query(...)`` chain or on a local the function binds to one), a ``BackgroundTasks``
   parameter or ``.add_task(`` call, or ``asyncio.create_task(``. An engine (a name called
   ``engine``, one bound from ``create_engine()`` however it is called (``sa.create_engine(...)``, or
   under a name the file imports it as), and ``app.database``'s ``engine`` however the
   file imports it: ``from app.database import engine as db_engine`` or ``database.engine``) and a
   Connection (bound from
   ``engine.connect()``, ``engine.begin()`` or ``db.connection()``, or written through directly:
   ``db.connection().execute(...)``) write as a session does, so ``engine.begin()``,
   ``conn.execute(...)`` and ``conn.exec_driver_sql(...)`` count. ``execute`` runs reads as well as
   writes and the check does not look at the statement, so every ``execute`` counts unless its
   function is pinned in ``READ_ONLY_EXECUTE_SITES`` and makes exactly the pinned number of them; a
   different number there counts every one. This catches
   the ``get_*``/``search_*`` handlers the name check cannot. The check follows the handler into
   every module-level function it reaches under ``app/`` (same module, ``from app.x import f``,
   ``x_service.f`` on an imported module, relative imports, re-exports, function-local imports (a
   name imported in two places is followed through both), a function handed to
   ``run_in_threadpool``, a ``Depends(...)`` dependency, a dotted name through an
   unaliased ``import app.x`` (``app.x.f(db)``, followed beside any alias the file gives ``app``),
   and every method of a class or module-level instance it names: ``x_service = XService()``,
   ``Svc().run(db)``),
   transitively, so moving a write into ``app/services/`` keeps it in view. A session there is also
   any ``Session``-annotated parameter (nested defs included) and any name bound from
   ``SessionLocal()``/``next(get_db())``; a write or spawn counts wherever it is named, called or
   not (``run_in_threadpool(db.commit)``, ``commit = db.commit``). A local is bound by ``=``, an
   annotated ``=``, ``:=``, a tuple that unpacks a literal of the same length (``q, n = db.query(X),
   0``) and a ``for`` target over a literal tuple, list or set (``for q in (db.query(X),
   db.query(Y))``), a session or a Connection by ``with``/``async with ... as`` too, and so is a
   copy of a known session, Connection or Query (``conn = original``) by any of these. A
   conditional value (``a if c else b``, ``a or b``, ``(n := v)``) counts as each value it may
   take: when it is bound, as the receiver of a write, and as what a Query or a Connection is
   opened on (``(db if c else other).query(X)``). A comprehension's ``for`` target binds only
   inside that comprehension, in order, with the first iterable read outside it, as Python scopes
   it. A name that every item of a literal tuple, list or set gives a value means what the items
   give it there. Any other name keeps its meaning and gains what the items give it (fail closed):
   one that a starred item, or an item the target does not unpack, gives nothing, and always
   ``db``, ``session``, ``engine``, the file's engine names and a ``Session``-annotated parameter.
   A lambda's or nested def's parameter keeps the meaning its name has outside too: the gate cannot
   see what it receives. ``api_route(methods=["GET"])`` handlers are GET handlers too. Limitation:
   the walk resolves names, not types, so a method on an object it cannot name (a parameter, an
   attribute of ``self``, a function's return value) is not followed, and a Query, a Connection or
   an engine is traced only inside the function that builds it and only through the bindings above
   (not as a parameter, a helper's return value or an item of a container bound to a name); that
   remains a review concern. Nor does it follow a module re-exported as a package's attribute
   (``app.services.writer.f`` through ``from . import w as writer``), a re-export chain more than
   eight deep, a Connection through ``execution_options(...)`` or ``await engine.connect()``, or
   a ``:=`` in a comprehension whose value reads one of that comprehension's own names
   (``[(c := q.filter(...)) for q in [db.query(X)]]``, then ``c.delete()``); app code has none of
   these today, and ``tasks/todo.md`` keeps them as follow-ups.
   ``test_walk_follows_every_documented_form`` pins each form on a synthetic tree, and
   ``test_every_session_write_kind_is_flagged`` each write kind.

Both allow-lists are shrink-only: a NEW hit fails with file:line and the remedy; an allow-listed
handler that no longer trips the check fails too (prune the entry — the fix is done); an entry
whose file has been deleted is tolerated so a teardown PR and this gate merge in either order.
Every entry carries its one-line justification. An exemption is a shape, not a name: each
side-effecting GET also pins every function (``file::qualname``) where its side effects may
happen, with the kind and count of each one there (``{"add": 1, "commit": 1}``). A write in a new,
unpinned function reached from an exempt handler fails, and so does one more or one fewer inside a
pinned function; a moved write moves its pin. A ``READ_ONLY_EXECUTE_SITES`` pin is exact the same
way: its function must be reached from a GET and make exactly the pinned number of executes. A
count is of the calls written in a function, not of how often they run: a loop, or a second call
to a pinned function, repeats its writes without changing any count. Nor can a count tell two
calls of one kind apart, so swapping a pinned call for another of the same kind (a read-only
``execute`` for a writing one) passes. Both remain review concerns.
"""
import ast
import sys
from collections import Counter
from collections.abc import Iterator
from pathlib import Path

import pytest

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
    ("app/routers/feedback.py", "feedback_attachment"): (
        "private object read: launch and reap a hard-deadline storage child; both tasks are awaited "
        "and settled before return/cancellation, never detached work or database writes"
    ),
    ("app/routers/analysis.py", "get_coverage"): (
        "read-through: fires a fire-and-forget companyfacts ingest (asyncio.create_task, deduped, "
        "through the SEC limiter) when coverage is stale; the response itself is a read"
    ),
    ("app/routers/auth.py", "apple_login"): (
        "Apple sign-in GET start commits the single-use nonce/state row for the form_post callback; "
        "the signed SameSite=None, Secure cookie separately binds it to the initiating browser"
    ),
    ("app/routers/auth.py", "google_login"): (
        "OAuth GET start commits a single-use state row, including plain existing-user login; "
        "the callback requires this row and the initiating browser's state cookie"
    ),
    ("app/routers/auth.py", "google_callback"): (
        "OAuth redirect callback — the provider returns the user via GET by protocol; creates or "
        "links the account (db.add/flush)"
    ),
    ("app/routers/companies.py", "search_companies"): (
        "read-through cache: persists Company rows discovered via the SEC ticker lookup "
        "(db.add/flush/commit; the concurrent-search race re-resolves each CIK, inserting a new one "
        "under a SAVEPOINT)"
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
        "(db.add/flush/commit); an insert that clashes with another (a concurrent read, an update or "
        "the alert scanner) rolls back under a SAVEPOINT, and the read answers the stored row"
    ),
    ("app/routers/users.py", "export_user_data"): (
        "audit trail: the GDPR export records who downloaded their data "
        "(log_data_export -> create_audit_log, db.add/commit); the response is a read"
    ),
}

# (file, handler) -> every function (``file::qualname``) where that GET's side effects may happen,
# with the kind and count of each one there. A write that moves (a router helper into a service)
# moves its pin in the same PR; one more or one fewer changes its count.
ALLOWED_WRITE_SITES: dict[tuple[str, str], dict[str, dict[str, int]]] = {
    ("app/routers/feedback.py", "feedback_attachment"): {
        "app/services/feedback_storage_worker_service.py::run_feedback_storage_operation": {"create_task": 1},
        "app/services/feedback_storage_worker_service.py::_finish_child": {"create_task": 1},
    },
    ("app/routers/analysis.py", "get_coverage"): {
        "app/routers/analysis.py::get_coverage": {"create_task": 1},
        "app/services/facts/ingest.py::_persist_companyfacts_payload": {"commit": 1},
        "app/services/facts/upsert.py::upsert_facts_bulk": {"add": 1, "commit": 1},
        # The same ingest's own-report history rows, which the bulk upsert stores beside its winners.
        "app/services/facts/own_reports.py::insert_history_rows": {"add": 1},
    },
    ("app/routers/auth.py", "apple_login"): {
        "app/services/oauth_account_service.py::save_apple_state": {"commit": 1},
        "app/services/oauth_account_service.py::store_oauth_state": {"add": 1, "query.delete": 1},
    },
    ("app/routers/auth.py", "google_login"): {
        "app/services/oauth_account_service.py::save_google_state": {"commit": 1},
        "app/services/oauth_account_service.py::store_oauth_state": {"add": 1, "query.delete": 1},
    },
    ("app/routers/auth.py", "google_callback"): {
        # DELETE RETURNING consumes state atomically; execute replaces the former ORM delete.
        "app/services/oauth_account_service.py::consume_oauth_state": {"commit": 1, "execute": 1},
        # The existing OIDC GET callback persists only explicit, versioned POST-start assent,
        # atomically with new-account creation; it never invents assent during plain login.
        "app/services/account_agreement_service.py::stage_account_agreement": {"add": 1},
        "app/services/oauth_account_service.py::oauth_create_account": {"add": 1, "flush": 1},
        "app/services/oauth_account_service.py::resolve_google_user": {"add": 1},
        "app/services/audit_service.py::create_audit_log": {"add": 1, "commit": 1},
        "app/services/invite_service.py::redeem_invite": {"commit": 1, "execute": 1},
        "app/services/refresh_token_service.py::create_refresh_token": {"add": 1, "flush": 1},
        "app/services/refresh_token_service.py::mint_refresh_token": {"commit": 1},
    },
    ("app/routers/companies.py", "search_companies"): {
        "app/services/company_lookup_service.py::resolve_search_conflict": {"commit": 1, "flush": 1},
        "app/services/company_lookup_service.py::_upsert_companies": {"add": 1, "commit": 1, "flush": 1},
        "app/services/company_resolution.py::resolve_or_create_company_by_cik": {"add": 1, "flush": 1},
    },
    ("app/routers/companies.py", "get_company"): {
        "app/services/company_lookup_service.py::persist_sec_company": {"commit": 1},
        "app/services/company_resolution.py::resolve_or_create_company_by_cik": {"add": 1, "flush": 1},
    },
    ("app/routers/filings.py", "get_company_filings"): {
        "app/routers/filings.py::get_company_filings": {"BackgroundTasks": 1, "add_task": 2},
        "app/services/company_resolution.py::resolve_or_create_company_by_cik": {"add": 1, "flush": 1},
        # The filing-insert lock a persisted listing takes before it inserts (E153), a SELECT that writes nothing.
        "app/services/filing_amendment_service.py::existing_filings_for_insert": {"execute": 1},
        "app/services/filing_amendment_service.py::mark_superseded_filings": {
            "bulk_update_mappings": 1, "flush": 1,
        },
        "app/services/filing_history_service.py::_persist_history_rows": {"commit": 1},
        "app/services/filing_list_service.py::persist_live_filings": {"add": 1, "commit": 1, "flush": 1},
        "app/services/filing_list_service.py::persist_sec_company": {"commit": 1},
        "app/services/filing_scan_service.py::upsert_filings": {"add": 1, "commit": 1},
    },
    ("app/routers/summaries.py", "get_summary_progress"): {
        "app/routers/summaries.py::get_summary_progress": {"commit": 1},
    },
    ("app/routers/users.py", "get_notification_preferences"): {
        "app/services/notification_service.py::get_or_create_preferences": {"add": 1, "commit": 1, "flush": 2},
    },
    ("app/routers/users.py", "export_user_data"): {
        "app/services/audit_service.py::create_audit_log": {"add": 1, "commit": 1},
    },
}

# file::qualname -> (how many ``execute`` calls there only read, why). ``execute`` runs reads as well
# as writes and the walk cannot tell them apart, so every one counts as a write unless its function is
# pinned here; a pinned function that makes any other number of executes has every one counted.
READ_ONLY_EXECUTE_SITES: dict[str, tuple[int, str]] = {
    "main.py::health_check_detailed": (
        1, "the database health probe runs SELECT 1 in a session of its own and writes nothing"
    ),
}

_SESSION_NAMES = {"db", "session"}
_ENGINE_NAMES = {"engine"}  # app.database's engine; one bound from create_engine() counts as well
_SESSION_WRITES = {
    "add", "add_all", "delete", "merge", "flush", "commit", "begin", "execute", "exec_driver_sql",
    "bulk_save_objects", "bulk_insert_mappings", "bulk_update_mappings",
}
_QUERY_WRITES = {"update", "delete"}  # db.query(...)...update()/.delete(): a bulk write by criteria
_QUERY_FETCHES = {"all", "first", "one", "one_or_none", "scalar", "count", "get"}  # rows, not a Query
_COMPREHENSIONS = (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)


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


def _dotted(expr: ast.AST) -> str | None:
    """``a.b.c`` for a name or a chain of attributes on one; None for anything else."""
    parts: list[str] = []
    while isinstance(expr, ast.Attribute):
        parts.insert(0, expr.attr)
        expr = expr.value
    return ".".join([expr.id, *parts]) if isinstance(expr, ast.Name) else None


def _pairs(target: ast.AST, value: ast.AST) -> Iterator[tuple[str, ast.AST]]:
    """(name, value) for a name target, and pair by pair for a tuple or list target that unpacks a
    literal of the same length (``q, n = db.query(X), 0``); no other unpacking is traced."""
    if isinstance(target, ast.Name):
        yield target.id, value
    elif isinstance(target, (ast.Tuple, ast.List)) and isinstance(value, (ast.Tuple, ast.List)) \
            and len(target.elts) == len(value.elts) \
            and not any(isinstance(elt, ast.Starred) for elt in (*target.elts, *value.elts)):
        for name, item in zip(target.elts, value.elts):
            yield from _pairs(name, item)


def _item_pairs(target: ast.AST, iterable: ast.AST) -> list[list[tuple[str, ast.AST]]]:
    """For a ``for`` target over a literal tuple, list or set, the (name, value) pairs each item
    gives it; a starred item gives none, since its values are not traced. Empty for any other
    iterable."""
    if not isinstance(iterable, (ast.Tuple, ast.List, ast.Set)):
        return []
    return [[] if isinstance(item, ast.Starred) else list(_pairs(target, item)) for item in iterable.elts]


def _literal_items(target: ast.AST, iterable: ast.AST) -> Iterator[tuple[str, ast.AST]]:
    """(name, value) for a ``for`` target over a literal tuple, list or set: each item is a value
    the name takes (``_item_pairs``)."""
    for pairs in _item_pairs(target, iterable):
        yield from pairs


def _local_bindings(fn: ast.AST) -> Iterator[tuple[str, ast.AST]]:
    """(name, value) for every ``name = value``, ``name: T = value`` and ``(name := value)`` in ``fn``,
    a tuple that unpacks a literal included, and for every ``for`` statement's target over a literal
    tuple, list or set. A comprehension's targets stay in the comprehension (``_comprehension_target``)."""
    for node in ast.walk(fn):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                yield from _pairs(target, node.value)
        elif isinstance(node, (ast.AnnAssign, ast.NamedExpr)) and node.value is not None:
            yield from _pairs(node.target, node.value)
        elif isinstance(node, ast.For):
            yield from _literal_items(node.target, node.iter)


def _kept_sessions(fn: ast.AST, engines: frozenset[str]) -> set[str]:
    """The sessions ``fn`` has by convention or declaration: ``db``, ``session``, ``engine``, the names
    its file gives ``app.database``'s engine (``engines``, from ``_engine_names``) and every
    ``Session``-annotated parameter of ``fn`` or of a def nested in it. A comprehension never
    rebinds them (fail closed)."""
    # An engine and a Connection write as a session does (``engine.begin()``, ``conn.execute(...)``).
    return set(_SESSION_NAMES) | _ENGINE_NAMES | set(engines) | {
        arg.arg for node in ast.walk(fn) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda))
        for arg in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
        if arg.annotation is not None and "Session" in ast.unparse(arg.annotation)
    }


def _session_names_in(fn: ast.AST, engines: frozenset[str] = frozenset(),
                      kept: set[str] | None = None) -> set[str]:
    """``db``/``session``, plus every ``Session``-annotated parameter of ``fn`` or a def nested in
    it, and every name bound from a session factory (``s = SessionLocal()``, annotated or ``:=``
    alike, and ``with ... as s``). An engine and a Connection write as a session does, so they are
    in the set too: ``engine``, a name bound from ``create_engine()``, and one bound from
    ``engine.connect()``, ``engine.begin()`` or ``db.connection()``. A copy of any of them
    (``conn = original``) is one as well. A ``with``/``async with ... as`` target is judged as an
    ``=`` binding is (``_binds_session``). ``engines``: the names the function's file gives
    ``app.database``'s engine (``_engine_names``); ``kept``: ``_kept_sessions(fn, engines)``, when the
    caller has it already."""
    names = set(_kept_sessions(fn, engines) if kept is None else kept)
    opened = [(item.optional_vars.id, item.context_expr) for node in ast.walk(fn)
              if isinstance(node, (ast.With, ast.AsyncWith)) for item in node.items
              if isinstance(item.optional_vars, ast.Name)]
    bindings = [*_local_bindings(fn), *opened]
    while True:  # a Connection opened on a copy, and a copy of a copy, need another round
        bound = {name for name, value in bindings if _binds_session(value, names)}
        if bound <= names:
            return names
        names |= bound


def _alternatives(expr: ast.AST) -> Iterator[ast.AST]:
    """The values ``expr`` may evaluate to: each branch of ``a if c else b``, each operand of ``a or
    b`` and ``a and b``, and the value of ``(n := v)``, however nested; ``expr`` itself otherwise."""
    if isinstance(expr, ast.IfExp):
        yield from _alternatives(expr.body)
        yield from _alternatives(expr.orelse)
    elif isinstance(expr, ast.BoolOp):
        for value in expr.values:
            yield from _alternatives(value)
    elif isinstance(expr, ast.NamedExpr):
        yield from _alternatives(expr.value)
    else:
        yield expr


def _held(expr: ast.AST, sessions: set[str]) -> str | None:
    """The name (or dotted name) in ``sessions`` that ``expr`` may evaluate to (``_alternatives``):
    ``db`` for ``db``, ``(db if c else other)`` or ``(s := db)``; None when it may be none of them."""
    return next((name for alt in _alternatives(expr) if (name := _dotted(alt)) in sessions), None)


def _binds_session(value: ast.AST, sessions: set[str]) -> bool:
    """Whether a value bound to a name is a session, an engine or a Connection: a session factory
    (``SessionLocal()``), ``create_engine()`` (``_creates_engine``), a Connection opened on a name in
    ``sessions``, or a copy of one; a conditional is one if any value it may take is
    (``_alternatives``). A local binding and a comprehension's target are judged by this one test."""
    return any(_opens_session(alt) or _creates_engine(alt, sessions) or _opens_connection(alt, sessions)
               or _dotted(alt) in sessions for alt in _alternatives(value))


def _creates_engine(expr: ast.AST, sessions: set[str]) -> bool:
    """A call that builds an engine: ``create_engine(...)`` however qualified (``sa.create_engine(...)``),
    or a call to a name the file imports it as, which ``sessions`` holds as ``name()``
    (``_engine_names``)."""
    if not isinstance(expr, ast.Call):
        return False
    func = expr.func
    name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
    return name == "create_engine" or f"{_dotted(func)}()" in sessions


def _opens_connection(expr: ast.AST, sessions: set[str]) -> bool:
    """``engine.connect()``, ``engine.begin()`` or ``db.connection()``: a Connection, on a name (or a
    dotted name: ``database.engine``) the function holds as an engine or a session, or on a
    conditional that may be one (``(engine or fallback).connect()``, ``_held``)."""
    return isinstance(expr, ast.Call) and isinstance(expr.func, ast.Attribute) \
        and expr.func.attr in {"connect", "begin", "connection"} and _held(expr.func.value, sessions) is not None


def _query_root(expr: ast.AST, sessions: set[str], queries: set[str]) -> str | None:
    """What a Query chain hangs from: ``db.query(...)`` for ``db.query(X).filter(...)`` (and for
    ``(db if c else other).query(X)``, ``_held``), or ``q`` for ``q.filter(...)`` when the local ``q``
    holds a Query; None for anything else."""
    while isinstance(expr, (ast.Call, ast.Attribute)):
        if isinstance(expr, ast.Call):
            func = expr.func
            if isinstance(func, ast.Attribute) and func.attr == "query" and (held := _held(func.value, sessions)):
                return f"{held}.query(...)"
            expr = func
        else:
            expr = expr.value
    if isinstance(expr, (ast.IfExp, ast.BoolOp, ast.NamedExpr)):  # ``(q if c else other).delete()``
        return next(filter(None, (_query_root(alt, sessions, queries) for alt in _alternatives(expr))), None)
    return expr.id if isinstance(expr, ast.Name) and expr.id in queries else None


def _query_names_in(fn: ast.AST, sessions: set[str]) -> set[str]:
    """Locals ``fn`` binds to a Query: ``q = db.query(X)`` (annotated or ``:=`` alike), then
    ``narrowed = q.filter(...)``. A chain that ends by fetching (``.first()``, ``.all()`` …) binds
    its rows, not a Query."""
    names: set[str] = set()
    bindings = list(_local_bindings(fn))
    while True:
        bound = {name for name, value in bindings if _binds_query(value, sessions, names)}
        if bound <= names:
            return names
        names |= bound


def _binds_query(value: ast.AST, sessions: set[str], queries: set[str]) -> bool:
    """Whether a value is a Query: a chain from ``db.query(...)`` or a Query name that does not
    end by fetching (``.first()``, ``.all()`` … bind rows); a conditional is one if any value it
    may take is (``_alternatives``)."""
    return any(bool(_query_root(alt, sessions, queries)) and not (
        isinstance(alt, ast.Call) and isinstance(alt.func, ast.Attribute) and alt.func.attr in _QUERY_FETCHES
    ) for alt in _alternatives(value))


def _comprehension_target(generator: ast.comprehension, sessions: set[str], queries: set[str],
                          kept: set[str]) -> tuple[set[str], set[str]]:
    """The sessions (engines and Connections included) and Queries in scope after one ``for`` of a
    comprehension. A name the target takes from every item of a literal tuple, list or set means
    what the items give it (``_binds_session``, ``_binds_query``), read with the names in scope
    before the ``for``, and no longer what it meant outside. A name some item shows no value for (a
    starred item, or one the target does not unpack), a name whose values the gate cannot see, and
    every name in ``kept`` keep their meaning, adding what the items show (fail closed). Python keeps
    a comprehension's targets in its own scope, so these names count only inside it."""
    per_item = _item_pairs(generator.target, generator.iter)
    pairs = [pair for item in per_item for pair in item]
    bound_sessions = {name for name, value in pairs if _binds_session(value, sessions)}
    bound_queries = {name for name, value in pairs if _binds_query(value, sessions, queries)}
    seen = set.intersection(*({name for name, _ in item} for item in per_item)) - kept if per_item else set()
    return (sessions - seen) | bound_sessions, (queries - seen) | bound_queries


def _side_effect_markers(fn: ast.AST, engines: frozenset[str] = frozenset()) -> list[tuple[str, str]]:
    """(kind, ``label@line``) for every side-effect construct in ``fn``. The kind (``commit``,
    ``query.delete``, ``add_task``, ``BackgroundTasks`` …) is what a write-site pin counts. A write
    or spawn counts wherever it is named, called or not: ``db.commit()``,
    ``run_in_threadpool(db.commit)`` and ``commit = db.commit`` are one marker each."""
    markers: list[tuple[str, str]] = []
    kept = _kept_sessions(fn, engines)  # stays a session wherever a comprehension rebinds its name
    sessions = _session_names_in(fn, engines, kept)
    queries = _query_names_in(fn, sessions)
    args = fn.args
    for arg in [*args.posonlyargs, *args.args, *args.kwonlyargs]:
        if arg.annotation is not None and "BackgroundTasks" in ast.unparse(arg.annotation):
            markers.append(("BackgroundTasks", f"param {arg.arg}: BackgroundTasks"))
    called = {id(node.func) for node in ast.walk(fn) if isinstance(node, ast.Call)}

    def marker(node: ast.Attribute, sessions: set[str], queries: set[str]) -> tuple[str, str] | None:
        how = "()" if id(node) in called else " (uncalled)"
        receiver = node.value
        held = _held(receiver, sessions)
        if held and node.attr in _SESSION_WRITES:
            return node.attr, f"{held}.{node.attr}{how}@{node.lineno}"
        if any(_opens_connection(alt, sessions) for alt in _alternatives(receiver)) and node.attr in _SESSION_WRITES:
            return node.attr, f"{ast.unparse(receiver)}.{node.attr}{how}@{node.lineno}"
        if node.attr in _QUERY_WRITES and (root := _query_root(receiver, sessions, queries)):
            return f"query.{node.attr}", f"{root}.{node.attr}{how}@{node.lineno}"
        if node.attr == "add_task":
            return "add_task", f".add_task{how}@{node.lineno}"
        if node.attr == "create_task" and isinstance(receiver, ast.Name) and receiver.id == "asyncio":
            return "create_task", f"asyncio.create_task{how}@{node.lineno}"
        return None

    found: list[tuple[str, str]] = []

    def scoped(node: ast.AST, sessions: set[str], queries: set[str]) -> None:
        """Check every attribute with the names in scope where it stands. A comprehension's ``for``s
        bind in order, for the rest of that comprehension only (a nested one's on top of its
        enclosing one's); its first iterable is read before any of them, outside it, as Python
        evaluates it."""
        if isinstance(node, _COMPREHENSIONS):
            for generator in node.generators:
                scoped(generator.iter, sessions, queries)
                sessions, queries = _comprehension_target(generator, sessions, queries, kept)
                for part in (generator.target, *generator.ifs):
                    scoped(part, sessions, queries)
            for part in (node.key, node.value) if isinstance(node, ast.DictComp) else (node.elt,):
                scoped(part, sessions, queries)
            return
        if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load) \
                and (hit := marker(node, sessions, queries)):
            found.append(hit)
        for child in ast.iter_child_nodes(node):
            scoped(child, sessions, queries)

    scoped(fn, sessions, queries)
    return markers + found


_PARSED: dict[Path, ast.Module] = {}
_BINDINGS: dict[Path, dict[str, list[tuple[str, str | None]]]] = {}
_IMPORTS_APP: dict[Path, bool] = {}
_FACTORIES: dict[Path, frozenset[str]] = {}
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


def _bindings(path: Path) -> dict[str, list[tuple[str, str | None]]]:
    """Local name -> every (app module, symbol) an app import in ``path`` binds it to (function-local
    ones included); the symbol is None when the name is bound to the module itself. The table is
    file-wide, so a name imported in two places keeps both, and each is followed (fail closed)."""
    if path not in _BINDINGS:
        package = list(path.relative_to(BACKEND_DIR).with_suffix("").parts)[:-1]
        table: dict[str, list[tuple[str, str | None]]] = {}

        def bind(local: str, entry: tuple[str, str | None]) -> None:
            if entry not in table.setdefault(local, []):
                table[local].append(entry)

        for node in ast.walk(_module(path)):
            if isinstance(node, ast.ImportFrom):
                base = package[: len(package) - node.level + 1] if node.level else []
                module = ".".join([*base, *([node.module] if node.module else [])])
                for alias in node.names:
                    local = alias.asname or alias.name
                    if _module_path(f"{module}.{alias.name}"):
                        bind(local, (f"{module}.{alias.name}", None))
                    elif _module_path(module):
                        bind(local, (module, alias.name))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.asname and _module_path(alias.name):
                        bind(alias.asname, (alias.name, None))
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
    return [target for module, symbol in _bindings(path).get(name, []) if symbol is not None
            for target in _targets(_module_path(module), symbol, depth + 1)]


def _engine_names(path: Path) -> frozenset[str]:
    """What ``path`` calls ``app.database``'s engine besides ``engine`` itself: an alias (``from
    app.database import engine as db_engine``) or an attribute of the module (``database.engine``,
    and ``app.database.engine`` after an unaliased ``import app.database``). It also holds, written
    ``name()``, each name the file imports ``create_engine`` as (``_engine_factories``)."""
    names = {local if symbol == "engine" else f"{local}.engine"
             for local, entries in _bindings(path).items() for module, symbol in entries
             if module == "app.database" and symbol in ("engine", None)}
    return frozenset(names | _engine_factories(path) | ({"app.database.engine"} if _imports_app(path) else set()))


def _engine_factories(path: Path) -> frozenset[str]:
    """``name()`` for each name ``path`` imports ``create_engine`` as (``from sqlalchemy import
    create_engine as make_engine``), anywhere in the file: a call to it builds an engine."""
    if path not in _FACTORIES:
        _FACTORIES[path] = frozenset(
            f"{alias.asname}()" for node in ast.walk(_module(path)) if isinstance(node, ast.ImportFrom)
            for alias in node.names if alias.name == "create_engine" and alias.asname
        )
    return _FACTORIES[path]


def _imports_app(path: Path) -> bool:
    """Whether ``path`` has an unaliased ``import app.x`` anywhere, which binds the package ``app``
    in the scope it stands in."""
    if path not in _IMPORTS_APP:
        _IMPORTS_APP[path] = any(
            isinstance(node, ast.Import) and any(not alias.asname and alias.name.split(".")[0] == "app"
                                                 for alias in node.names)
            for node in ast.walk(_module(path))
        )
    return _IMPORTS_APP[path]


def _named_modules(path: Path, expr: ast.AST) -> list[Path]:
    """The app modules a name or dotted name in ``path`` may stand for: ``w_mod`` bound by ``from
    app.services import w as w_mod``, and ``app.services.w`` after an unaliased ``import
    app.services.w``. The import table is file-wide, so a dotted ``app`` chain is followed both
    through any alias the file gives ``app`` and as the package (fail closed)."""
    parts: list[str] = []
    while isinstance(expr, ast.Attribute):
        parts.insert(0, expr.attr)
        expr = expr.value
    if not isinstance(expr, ast.Name):
        return []
    dotted = [".".join([module, *parts]) for module, symbol in _bindings(path).get(expr.id, []) if symbol is None]
    if expr.id == "app" and _imports_app(path):
        dotted.append(".".join(["app", *parts]))
    return [module for name in dotted if (module := _module_path(name))]


def _callee_targets(path: Path, func: ast.AST, depth: int) -> list[_Target]:
    if isinstance(func, ast.Name):
        return _targets(path, func.id, depth)
    if isinstance(func, ast.Attribute):
        return [target for module in _named_modules(path, func.value) for target in _targets(module, func.attr, depth)]
    return []


def _referenced_functions(path: Path, fn: ast.AST) -> list[_Target]:
    """App code ``fn`` names: functions it calls, hands to ``run_in_threadpool`` or uses in
    ``Depends``, and every method of a class or module-level instance it names."""
    bindings = _bindings(path)
    out: list[_Target] = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            entries = bindings.get(node.id, [])
            # A name bound only to modules is followed through its attribute.
            if not entries or any(symbol is not None for _, symbol in entries):
                out.extend(_targets(path, node.id))
        elif isinstance(node, ast.Attribute):
            for module in _named_modules(path, node.value):
                out.extend(_targets(module, node.attr))
    return out


def _site(path: Path, qualname: str) -> str:
    return f"{path.relative_to(BACKEND_DIR).as_posix()}::{qualname}"


_Marker = tuple[str, str, str]  # (site ``file::qualname``, kind, ``label@line``)


def _handler_markers(path: Path, handler: ast.AST) -> list[_Marker]:
    """(site, kind, label) for the handler body and every app function it reaches, transitively."""
    found = [(_site(path, handler.name), kind, label)
             for kind, label in _side_effect_markers(handler, _engine_names(path))]
    seen = {(path, handler.lineno)}
    stack = _referenced_functions(path, handler)
    while stack:
        fn_path, fn, qualname = stack.pop()
        if (fn_path, fn.lineno) in seen:
            continue
        seen.add((fn_path, fn.lineno))
        found.extend((_site(fn_path, qualname), kind, label)
                     for kind, label in _side_effect_markers(fn, _engine_names(fn_path)))
        stack.extend(_referenced_functions(fn_path, fn))
    return sorted(found)


def _without_pinned_reads(markers: list[_Marker]) -> list[_Marker]:
    """Drop the ``execute`` markers of each READ_ONLY_EXECUTE_SITES function that makes exactly its
    pinned count; any other count leaves every one of them in place."""
    executes = Counter(site for site, kind, _ in markers if kind == "execute")
    reads = {site for site, count in executes.items() if site in READ_ONLY_EXECUTE_SITES
             and READ_ONLY_EXECUTE_SITES[site][0] == count}
    return [(site, kind, label) for site, kind, label in markers if not (kind == "execute" and site in reads)]


def _side_effecting_handlers(files: list[Path]) -> dict[tuple[str, str], list[_Marker]]:
    found: dict[tuple[str, str], list[_Marker]] = {}
    for py in files:
        rel = py.relative_to(BACKEND_DIR).as_posix()
        for fn in _get_handlers(py):
            markers = _without_pinned_reads(_handler_markers(py, fn))
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
        key: ", ".join(f"{label} in {site}" for site, _, label in markers)
        for key, markers in _side_effecting_handlers(_scanned_files()).items()
    }
    _check(
        found,
        ALLOWED_SIDE_EFFECTING_GETS,
        "GET handlers whose body writes or spawns work",
        "A GET must not write to the session or spawn background work. Move the mutation to a "
        "POST/PUT/DELETE endpoint; if this is genuinely a read-through cache, an OAuth GET-by-protocol "
        "callback, or a self-healing read, add the (file, handler) to ALLOWED_SIDE_EFFECTING_GETS "
        "with a one-line reason, and its write sites to ALLOWED_WRITE_SITES, in the same PR. An "
        "execute that only reads is pinned, with its function's execute count, in "
        "READ_ONLY_EXECUTE_SITES instead.",
    )


def _pin_drift(
    found: dict[tuple[str, str], list[_Marker]], pins: dict[tuple[str, str], dict[str, dict[str, int]]],
) -> list[str]:
    """Every way an exempt handler's reached side effects differ from its pins, by site and kind."""
    problems: list[str] = []
    for key, pinned in sorted(pins.items()):
        if key not in found:
            continue  # a handler that writes nowhere is reported stale by the body check
        handler = f"{key[0]}::{key[1]}"
        reached: dict[str, Counter] = {}
        for site, kind, _ in found[key]:
            reached.setdefault(site, Counter())[kind] += 1
        for site in sorted(reached.keys() | pinned.keys()):
            labels = ", ".join(label for s, _, label in found[key] if s == site)
            if site not in pinned:
                problems.append(f"  {handler} reaches a write outside its pins: {site} ({labels})")
            elif site not in reached:
                problems.append(f"  {handler} no longer writes at pinned {site} (moved or fixed: update the pin)")
            elif reached[site] != Counter(pinned[site]):
                problems.append(
                    f"  {handler} makes {dict(sorted(reached[site].items()))} at {site}, "
                    f"pinned {dict(sorted(pinned[site].items()))} ({labels})"
                )
    return problems


def test_exempt_gets_write_only_at_their_pinned_sites():
    problems = _pin_drift(_side_effecting_handlers(_scanned_files()), ALLOWED_WRITE_SITES)
    assert not problems, (
        "Side-effecting GET exemptions drifted from their pinned write sites:\n" + "\n".join(problems)
        + "\nAn exemption covers the writes it was granted for, by kind and count. A new write reached "
        "from an exempt GET belongs on POST/PUT/DELETE; a write that moved (router helper -> service) "
        "moves its pin in ALLOWED_WRITE_SITES in the same PR, and a removed one leaves it."
    )


def test_write_site_pins_match_the_exemptions():
    assert set(ALLOWED_WRITE_SITES) == set(ALLOWED_SIDE_EFFECTING_GETS)
    assert all(ALLOWED_WRITE_SITES.values()), "an exemption pins at least one write site"
    assert all(
        kinds and all(count > 0 for count in kinds.values())
        for sites in ALLOWED_WRITE_SITES.values() for kinds in sites.values()
    ), "a pinned site names each kind it may write with a positive count"


def test_read_only_execute_pins_match_their_sites():
    """Each READ_ONLY_EXECUTE_SITES function is reached by a GET and makes exactly its pinned count."""
    reached: dict[str, int] = {}
    for py in _scanned_files():
        for fn in _get_handlers(py):
            # A function's count is the same from every handler that reaches it.
            reached.update(Counter(site for site, kind, _ in _handler_markers(py, fn) if kind == "execute"))
    drifted = [
        f"  {site}: pinned {count}, a GET reaches {reached.get(site, 0)} there"
        for site, (count, _) in sorted(READ_ONLY_EXECUTE_SITES.items())
        if reached.get(site, 0) != count
    ]
    assert not drifted, (
        "Read-only execute pins drifted from their functions:\n" + "\n".join(drifted)
        + "\nA pin covers the reads it was granted for. An execute added beside them may write: put it "
        "behind POST/PUT/DELETE, or raise the count if it only reads. None left: prune the pin."
    )


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
    "app/services/built.py": "import app.services.svc\nbuilt = app.services.svc.Svc()\n",
    "app/services/raw.py": (
        "from app.database import engine as raw_engine\n\n\n"
        "def purge():\n    with raw_engine.begin() as conn:\n        conn.exec_driver_sql('DELETE FROM t')\n"
    ),
    "app/routers/alias.py": (
        "from fastapi import APIRouter\nfrom app.services import w as app\n\nrouter = APIRouter()\n\n\n"
        "@router.get('/v')\ndef module_alias_named_app(db):\n    app.write(db)\n\n\n"
        "def unrelated():\n    import app.services.reader\n\n\n"
        "@router.get('/x')\ndef module_imported_twice(db):\n    from app.services import w as shared\n"
        "    shared.write(db)\n\n\n"
        "@router.get('/y')\ndef function_imported_twice(db):\n    from app.services.w import write as save\n"
        "    save(db)\n\n\n"
        "def imports_both_names_again():\n    from app.services import reader as shared\n"
        "    from app.services.reader import read as save\n    return shared, save\n"
    ),
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
import app.services.w

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


@router.get("/s")
def unaliased_import(db):
    app.services.w.write(db)


@router.get("/t")
def unaliased_instance(db):
    import app.services.svc
    app.services.svc.svc.run(db)


@router.get("/u")
def unaliased_factory(db):
    from app.services.built import built
    built.run(db)


@router.get("/w")
def reaches_aliased_engine():
    from app.services.raw import purge
    purge()
""",
}


def _use_tree(tmp_path: Path, monkeypatch, tree: dict[str, str]) -> None:
    """Point the walk at a synthetic app tree written under ``tmp_path``."""
    for rel, source in tree.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(source, encoding="utf-8")
    module = sys.modules[__name__]
    monkeypatch.setattr(module, "BACKEND_DIR", tmp_path)
    monkeypatch.setattr(module, "_PARSED", {})
    monkeypatch.setattr(module, "_BINDINGS", {})
    monkeypatch.setattr(module, "_IMPORTS_APP", {})
    monkeypatch.setattr(module, "_FACTORIES", {})


def test_walk_follows_every_documented_form(tmp_path, monkeypatch):
    """Each documented resolution form, on a synthetic app tree: dropping any branch of the walk
    leaves its handler unflagged and fails this test (the real tree alone would not notice)."""
    _use_tree(tmp_path, monkeypatch, _SYNTHETIC_TREE)

    # An import in an unrelated function does not replace the binding a GET names (alias.py: an
    # unaliased ``import app.x`` beside ``w as app``; ``shared`` and ``save`` imported twice): each is followed.
    found = _side_effecting_handlers([tmp_path / "app/routers/r.py", tmp_path / "app/routers/alias.py"])
    flagged = {name for (_, name) in found}
    expected = {
        "same_module", "from_import", "module_attribute", "import_as", "relative_from",
        "relative_module", "package_reexport", "function_local_import", "factory_assignment",
        "threadpool", "dependency", "singleton", "class_instance", "nested_annotated",
        "passed_uncalled", "spawns_task", "api_route_get", "unaliased_import", "unaliased_instance",
        "unaliased_factory", "module_alias_named_app", "reaches_aliased_engine", "module_imported_twice",
        "function_imported_twice",
    }
    assert flagged == expected, f"missed: {sorted(expected - flagged)}; unexpected: {sorted(flagged - expected)}"
    assert {site for site, _, _ in found[("app/routers/r.py", "singleton")]} == {"app/services/svc.py::Svc._go"}
    assert {site for site, _, _ in found[("app/routers/r.py", "unaliased_import")]} == {"app/services/w.py::write"}


_WRITE_KINDS_ROUTER = """\
import asyncio

from fastapi import APIRouter
from sqlalchemy import create_engine, delete, select, update
from sqlalchemy.orm import Query, Session
from starlette.concurrency import run_in_threadpool

from app import database
from app.database import SessionLocal, engine
from app.database import engine as db_engine

router = APIRouter()


@router.get("/a")
def executes(db):
    db.execute(update(T).values(x=1))


@router.get("/b")
def begins(db):
    with db.begin():
        pass


@router.get("/c")
def bulk_saves(db):
    db.bulk_save_objects([])


@router.get("/d")
def bulk_inserts(db):
    db.bulk_insert_mappings(T, [])


@router.get("/e")
def bulk_updates(db):
    db.bulk_update_mappings(T, [])


@router.get("/f")
def query_deletes(db):
    db.query(T).filter(T.x < 1).delete(synchronize_session=False)


@router.get("/g")
def query_updates(db):
    db.query(T).filter(T.x < 1).update({"x": 1})


@router.get("/h")
def unpinned_read(db):
    return db.execute(select(T)).all()


@router.get("/i")
def pinned_read(db):
    return db.execute(select(T)).all()


@router.get("/j")
def pinned_read_and_a_write(db):
    db.execute(select(T))
    db.execute(delete(T))


@router.get("/k")
def assigned_query_updates(db):
    current = db.query(T).filter(T.x < 1)
    narrowed = current.filter(T.y < 1)
    narrowed.update({"x": 1})


@router.get("/l")
def reads_rows_and_merges_dicts(db):
    db.query(T).filter(T.x < 1).all()
    row = db.query(T).filter(T.x < 1).first()
    row.update({})
    row.add_task = None
    {}.update({})


@router.get("/m")
def annotated_query_deletes(db):
    stale: Query = db.query(T).filter(T.x < 1)
    stale.delete()


@router.get("/n")
def walrus_query_deletes(db):
    if (stale := db.query(T).filter(T.x < 1)).count():
        stale.delete()


@router.get("/o")
def annotated_session_commits():
    s: Session = SessionLocal()
    s.commit()


@router.get("/p")
def walrus_session_commits():
    if s := SessionLocal():
        s.commit()


@router.get("/q")
async def passes_query_write_uncalled(db):
    stale = db.query(T).filter(T.x < 1)
    await run_in_threadpool(stale.delete)


@router.get("/r")
def aliases_session_write(db):
    commit = db.commit
    commit()


@router.get("/s")
def passes_spawn_uncalled(loop, job):
    loop.call_soon_threadsafe(asyncio.create_task, job())


@router.get("/t")
def connection_executes(db):
    db.connection().execute(update(T).values(x=1))


@router.get("/u")
def assigned_connection_executes(db):
    conn = db.connection()
    conn.execute(delete(T))


@router.get("/v")
def engine_begins():
    with engine.begin():
        pass


@router.get("/w")
def engine_connection_commits():
    with engine.connect() as conn:
        conn.commit()


@router.get("/x")
def created_engine_begins():
    other = create_engine("sqlite://")
    other.begin()


@router.get("/y")
def tuple_query_deletes(db):
    stale, keep = db.query(T).filter(T.x < 1), None
    stale.delete()


@router.get("/z")
def for_query_deletes(db):
    for stale in (db.query(T).filter(T.x < 1),):
        stale.delete()


@router.get("/aa")
def comprehension_query_updates(db):
    return [stale.update({"x": 1}) for stale in [db.query(T)]]


@router.get("/ac")
def engine_begin_connection_executes():
    with engine.begin() as conn:
        conn.execute(delete(T))
        conn.exec_driver_sql("DELETE FROM t")


@router.get("/af")
def driver_sql_executes():
    with engine.connect() as conn:
        conn.exec_driver_sql("DELETE FROM t")


@router.get("/ag")
def copied_connection_commits():
    with engine.connect() as original:
        first = original
        conn = first
        conn.commit()


@router.get("/ah")
def tuple_copied_connection_executes():
    with engine.connect() as original:
        conn, unused = original, None
        conn.execute(delete(T))


@router.get("/ai")
def loop_copied_connection_executes():
    with engine.connect() as original:
        for conn in (original,):
            conn.execute(delete(T))


@router.get("/aj")
def tuple_session_commits():
    s, n = SessionLocal(), 0
    s.commit()


@router.get("/ak")
def loop_session_commits():
    for s in (SessionLocal(),):
        s.commit()


@router.get("/al")
def tuple_connection_executes(db):
    conn, n = db.connection(), 0
    conn.execute(delete(T))


@router.get("/am")
def comprehension_session_commits():
    return [s.commit() for s in (SessionLocal(),)]


@router.get("/an")
def comprehension_names_stay_in_scope(db):
    q = {}
    counts = [q.count() for q in [db.query(T)]]
    q.update({"counts": counts})
    merged = [q.update({}) for q in [{}]]
    rows = [[inner.update({}) for inner in [{}]] for outer in [db.query(T)]]
    return q, merged, rows


@router.get("/aq")
def nested_comprehension_query_deletes(db):
    return [[inner.delete() for inner in [outer]] for outer in [db.query(T)]]


@router.get("/as")
def later_for_copies_a_query(db):
    return [copy.delete() for stale in [db.query(T)] for copy in [stale]]


@router.get("/aw")
def comprehension_engine_begins():
    return [e.begin() for e in [create_engine("sqlite://")]]


@router.get("/at")
def comprehension_targets_shadow_outer_names(db):
    q = db.query(T)
    rebound = [q.update({}) for q in [{}]]
    nested = [[q.update({"read": True}) for q in [{}]] for q in [db.query(T)]]
    in_order = [q.update({}) for q in [db.query(T)] for q in [{}]]
    return rebound, nested, in_order


@router.get("/ax")
def comprehension_over_unknown_keeps_the_query(db):
    q = db.query(T)
    return [q.update({}) for q in rows]


@router.get("/ay")
def comprehension_target_named_db_commits():
    return [db.commit() for db in [pool]]


@router.get("/ba")
def comprehension_target_named_db_engine_begins():
    return [db_engine.begin() for db_engine in [pool]]


@router.get("/bb")
def comprehension_target_annotated_commits(s: Session):
    return [s.commit() for s in [pool]]


@router.get("/bc")
def lambda_parameter_keeps_the_query(db):
    return [(lambda q: q.delete())(q) for q in [db.query(T)]]


@router.get("/av")
def attribute_target_keeps_the_query(db):
    q = db.query(T)
    return [q.delete() for q.attr in [0]]


@router.get("/au")
def first_iterable_is_read_outside(db):
    q = {}
    return [str(q) for q in [db.query(T), q.update({})]]


@router.get("/ad")
async def async_connection_executes():
    async with engine.connect() as conn:
        await conn.execute(delete(T))


@router.get("/ae")
def set_for_query_deletes(db):
    for stale in {db.query(T).filter(T.x < 1)}:
        stale.delete()


@router.get("/ao")
def aliased_engine_runs_driver_sql():
    with db_engine.begin() as conn:
        conn.exec_driver_sql("DELETE FROM t")


@router.get("/ap")
def module_engine_begins():
    with database.engine.begin() as conn:
        conn.execute(delete(T))


@router.get("/ar")
def engine_imported_under_a_reused_name():
    from app.database import engine as shared
    with shared.begin() as conn:
        conn.execute(delete(T))


def reuses_the_name():
    import app.routers as shared
    return shared


@router.get("/bd")
def conditional_query_deletes(db):
    q = db.query(T) if enabled else None
    q.delete()


@router.get("/be")
def loop_conditional_query_deletes(db):
    for q in [db.query(T) if enabled else {}]:
        q.delete()


@router.get("/bf")
def fallback_query_deletes(db):
    q = cached or db.query(T)
    q.delete()


@router.get("/bg")
def walrus_value_query_deletes(db):
    stale = (inner := db.query(T))
    stale.delete()


@router.get("/bh")
def conditional_session_commits():
    s = SessionLocal() if enabled else None
    s.commit()


@router.get("/bi")
def conditional_receiver_deletes(db):
    return (db.query(T) if enabled else db.query(U)).delete()


@router.get("/bj")
def conditional_session_receiver_commits(db):
    (db if enabled else other).commit()


@router.get("/bk")
def conditional_connection_receiver_executes():
    (engine.connect() if enabled else other).execute(delete(T))


@router.get("/bl")
def conditional_rows_stay_rows(db):
    first = db.query(T).first() if enabled else db.query(U).one()
    first.update({})


@router.get("/bm")
def qualified_factory_engine_begins():
    import sqlalchemy as sa
    other = sa.create_engine("sqlite://")
    with other.begin() as conn:
        conn.execute(delete(T))


@router.get("/bn")
def aliased_factory_engine_begins():
    from sqlalchemy import create_engine as make_engine
    other = make_engine("sqlite://")
    other.begin()


@router.get("/bo")
def with_conditional_connection_executes():
    with (engine.connect() if enabled else other) as conn:
        conn.execute(delete(T))


@router.get("/bp")
def with_copied_connection_commits():
    original = engine.connect()
    with original as conn:
        conn.commit()


@router.get("/bq")
def starred_item_keeps_the_query(db):
    q = db.query(T)
    return [q.update({}) for q in [*rows]]


@router.get("/br")
def unpacked_item_keeps_the_query(db):
    q = db.query(T)
    return [q.update({}) for q, n in [({}, 0), pair]]


@router.get("/bs")
def starred_literal_binds_its_other_items(db):
    return [q.delete() for q in [*rows, db.query(T)]]


@router.get("/bt")
def conditional_query_root_deletes(db):
    (db if enabled else other).query(T).delete()


@router.get("/bu")
def fallback_engine_connects():
    with (engine or fallback).connect() as conn:
        conn.execute(delete(T))


@router.get("/bv")
def other_calls_bind_no_session():
    cache = make_cache()
    cache.add(1)
    with open("log") as fh:
        fh.flush()
    (cache if enabled else other).query(T).delete()


@router.get("/ab")
def connects_iterates_and_unpacks_rows(db):
    with engine.connect() as conn:
        pass
    for row in db.query(T).filter(T.x < 1):
        row.update({})
    first, count = db.query(T).first(), 0
    first.update({})
    one, two = db.query(T)  # unpacking a Query yields its rows
    one.update({})
"""


# A router that imports no engine, so ``engine`` there is an engine by its name alone.
_PLAIN_ROUTER = """\
from fastapi import APIRouter

router = APIRouter()


@router.get("/a")
def comprehension_target_named_engine_begins():
    return [engine.begin() for engine in [pool]]
"""


def test_every_session_write_kind_is_flagged(tmp_path, monkeypatch):
    """Self-check for the session writes the gate used to miss: ``execute``, ``exec_driver_sql``,
    ``begin``, ``bulk_*`` and ``.update()``/``.delete()`` on a ``db.query(...)`` chain or a local
    bound to one. A local is bound by ``=``, an annotated ``=``, ``:=``, a tuple unpacking a literal
    or a ``for`` target over one (a session or a Connection by ``with ... as`` too), and so is a
    copy of a known name, for a Query, a session and a Connection alike, a conditional value
    counting as each value it may take, there and where a Query or a Connection is opened on it; a
    comprehension's target only inside it and in order, a nested comprehension's on top of its
    enclosing one's. A comprehension rebinds a name only where every item of a literal shows its
    value, and never a session by convention or declaration; a lambda's parameter rebinds nothing.
    A write or spawn counts where it is named, called or not. An engine and a Connection write as a
    session does, under any name the file imports it as; opening one, calling another factory,
    iterating a Query's rows, unpacking a fetched row, or reusing a comprehension's name outside it
    or rebinding it inside to a literal's other value, writes nothing. Every ``execute`` counts
    unless its function is pinned read-only with exactly its count; with any of these dropped, this
    fails."""
    _use_tree(tmp_path, monkeypatch, {
        "app/__init__.py": "", "app/database.py": "engine = SessionLocal = None\n",
        "app/routers/__init__.py": "", "app/routers/w.py": _WRITE_KINDS_ROUTER,
        "app/routers/plain.py": _PLAIN_ROUTER,
    })
    monkeypatch.setattr(sys.modules[__name__], "READ_ONLY_EXECUTE_SITES", {
        "app/routers/w.py::pinned_read": (1, "fixture: its one execute is a SELECT"),
        "app/routers/w.py::pinned_read_and_a_write": (1, "fixture: pinned for one execute, makes two"),
    })

    found = _side_effecting_handlers([tmp_path / "app/routers/w.py", tmp_path / "app/routers/plain.py"])
    flagged = {name for (_, name) in found}
    expected = {
        "executes", "begins", "bulk_saves", "bulk_inserts", "bulk_updates", "query_deletes",
        "query_updates", "assigned_query_updates", "annotated_query_deletes", "walrus_query_deletes",
        "annotated_session_commits", "walrus_session_commits", "passes_query_write_uncalled",
        "aliases_session_write", "passes_spawn_uncalled", "unpinned_read", "pinned_read_and_a_write",
        "connection_executes", "assigned_connection_executes", "engine_begins", "engine_connection_commits",
        "created_engine_begins", "tuple_query_deletes", "for_query_deletes", "comprehension_query_updates",
        "engine_begin_connection_executes", "async_connection_executes", "set_for_query_deletes",
        "driver_sql_executes", "copied_connection_commits", "tuple_copied_connection_executes",
        "loop_copied_connection_executes", "tuple_session_commits", "loop_session_commits",
        "tuple_connection_executes", "comprehension_session_commits", "aliased_engine_runs_driver_sql",
        "module_engine_begins", "nested_comprehension_query_deletes", "engine_imported_under_a_reused_name",
        "later_for_copies_a_query", "attribute_target_keeps_the_query", "comprehension_engine_begins",
        "comprehension_over_unknown_keeps_the_query", "comprehension_target_named_db_commits",
        "comprehension_target_named_engine_begins", "comprehension_target_named_db_engine_begins",
        "comprehension_target_annotated_commits", "lambda_parameter_keeps_the_query",
        "conditional_query_deletes", "loop_conditional_query_deletes", "fallback_query_deletes",
        "walrus_value_query_deletes", "conditional_session_commits", "conditional_receiver_deletes",
        "conditional_session_receiver_commits", "conditional_connection_receiver_executes",
        "qualified_factory_engine_begins", "aliased_factory_engine_begins",
        "with_conditional_connection_executes", "with_copied_connection_commits", "starred_item_keeps_the_query",
        "unpacked_item_keeps_the_query", "starred_literal_binds_its_other_items", "conditional_query_root_deletes",
        "fallback_engine_connects",
    }
    assert flagged == expected, f"missed: {sorted(expected - flagged)}; unexpected: {sorted(flagged - expected)}"
    # The Connection that engine.begin() opens counts its own writes, as a pin's per-kind count needs;
    # exec_driver_sql is a kind of its own, so no read-only execute pin covers it.
    kinds = Counter(kind for _, kind, _ in found[("app/routers/w.py", "engine_begin_connection_executes")])
    assert kinds == {"begin": 1, "execute": 1, "exec_driver_sql": 1}, kinds
    # app.database's engine counts however the file names it, an alias or the module's attribute.
    for handler, expected_kinds in (("aliased_engine_runs_driver_sql", {"begin": 1, "exec_driver_sql": 1}),
                                    ("module_engine_begins", {"begin": 1, "execute": 1})):
        kinds = Counter(kind for _, kind, _ in found[("app/routers/w.py", handler)])
        assert kinds == expected_kinds, (handler, kinds)


_AUDIT_PINS = {
    ("app/routers/users.py", "export_user_data"): {
        "app/services/audit_service.py::create_audit_log": {"add": 1, "commit": 1},
    },
}


@pytest.mark.parametrize("body, drifts", [
    pytest.param("db.add(entry)\n    db.commit()", False, id="matches-its-pin"),
    pytest.param("db.add(entry)\n    db.delete(entry)\n    db.commit()", True, id="a-further-write-of-a-new-kind"),
    pytest.param("db.add(entry)\n    db.commit()\n    db.commit()", True, id="a-further-write-of-a-pinned-kind"),
    pytest.param("db.add(entry)", True, id="a-pinned-write-removed"),
])
def test_a_pinned_function_pins_each_write_kind_and_count(tmp_path, monkeypatch, body, drifts):
    """Self-check for per-site counts: #1134's pins named functions only, so a further write inside
    a pinned function passed. Compared by function name alone, every drifting case here fails."""
    _use_tree(tmp_path, monkeypatch, {
        "app/__init__.py": "",
        "app/routers/__init__.py": "",
        "app/services/__init__.py": "",
        "app/services/audit_service.py": f"def create_audit_log(db, entry):\n    {body}\n",
        "app/routers/users.py": (
            "from fastapi import APIRouter\n"
            "from app.services.audit_service import create_audit_log\n\n"
            "router = APIRouter()\n\n\n"
            "@router.get('/export')\n"
            "def export_user_data(db):\n"
            "    create_audit_log(db, None)\n"
        ),
    })

    problems = _pin_drift(_side_effecting_handlers([tmp_path / "app/routers/users.py"]), _AUDIT_PINS)
    assert bool(problems) is drifts, problems


def test_allowlist_entries_are_actually_mutating_names():
    """Guards the gate itself: an allow-list entry that the verb rule would not flag is dead weight."""
    for (_, name) in ALLOWED_MUTATING_GETS:
        assert _is_mutating_name(name), f"{name!r} is not flagged by MUTATING_VERBS — prune it"


def test_every_allowlist_entry_carries_a_reason():
    for allowed in (ALLOWED_MUTATING_GETS, ALLOWED_SIDE_EFFECTING_GETS):
        for key, reason in allowed.items():
            assert isinstance(reason, str) and len(reason.strip()) > 20, f"{key} needs a real reason"
    for site, (count, reason) in READ_ONLY_EXECUTE_SITES.items():
        assert count > 0 and len(reason.strip()) > 20, f"{site} needs a positive count and a real reason"
