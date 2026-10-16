"""Ratchet gate: an async route never works its request session on the event loop.

An ``async def`` route runs on the event loop. A query or commit on the request session there
checks out a pooled connection on the loop and, unless the same synchronous unit releases it, keeps
it until the sync ``get_db`` finalizer runs in the thread pool after the route yields. In production
(four slots, no overflow) the fifth such request blocks the whole loop for the pool timeout while
the four holders' finalizers wait for that loop: the summary read and its progress poll answered
4x200 then 4x500 in a burst of eight (``lessons/ops-release-cached-filing-reads-before-yield.md``).
The fix shape is a sync function handed to ``run_in_threadpool`` that does the session work, builds
the payload and releases the session (``get_summary``, ``get_what_changed``), or a service that
reads and releases in one unit.

An AST walk reads every ``async def`` under ``app/routers/`` that receives a session: a parameter
named ``db``, annotated with ``Session`` (bare or inside ``Annotated``, or through a module-level
alias of either) or defaulting to ``Depends(get_db...)``, plus any name the body binds to one
(``s = db``, ``s: Session = db``, ``(s := db)``). It counts each attribute the function's own body reads off that session
(``db.query(...)``, ``db.commit()``, ``fn = db.get``), nested ``async def`` bodies included since
they run on the loop too. Nested sync functions and lambdas are skipped (the thread pool runs them),
and so is an uncalled method handed straight to the thread pool (``run_in_threadpool(db.commit)``).

A function's count may not exceed its ceiling in ``ON_LOOP_CEILINGS``; an unlisted function's
ceiling is 0, so every new async route starts clean. The ceilings are the counts when the gate
landed. A PR that moves a route's session work off the loop lowers its entry in the same diff and
deletes it at 0. The gate fails only above a ceiling, never below one: while other branches edit
routers in parallel (one moves the contact form's persistence into a service), an exact match would
turn main red when one of them merges with fewer calls, as ``test_router_orm_ceilings_allowlist.py``
explains. Lowering is therefore each fixing PR's job, checked in review.

Out of reach, and left to ``test_cached_filings_pool_lifetime.py`` for the routes it lists and to
review elsewhere: a session handed to a service or helper that runs on the loop
(``peers_service.get_peers(db, ...)``), a nested sync function or lambda called directly on the loop
instead of through the thread pool, a session reached through an attribute or a container, a
session the route opens itself from ``SessionLocal`` (it does not wait on the dependency's
finalizer), and an ORM instance's lazy load. ``test_walk_sees_each_form`` scores the walk on planted
forms, the gaps among them, so a regression in the walk fails there instead of passing every router
vacuously.
"""
import ast
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
ROUTERS_DIR = BACKEND_DIR / "app" / "routers"

# (router file relative to backend/, function name) -> its ceiling. Counted by this file's own walk
# when the gate landed (2026-10-16), after its PR took the summary read and its progress poll off
# the loop. The blank line between entries keeps in-place number edits on different entries
# mergeable in any order.
ON_LOOP_CEILINGS: dict[tuple[str, str], int] = {
    ("app/routers/contact.py", "submit_contact_form"): 4,

    ("app/routers/feedback.py", "submit_feedback"): 4,

    ("app/routers/subscriptions.py", "create_checkout_session"): 2,

    ("app/routers/subscriptions.py", "get_subscription_status"): 1,

    ("app/routers/summaries.py", "ask_filing_stream"): 1,

    ("app/routers/summaries.py", "export_summary_csv"): 2,

    ("app/routers/summaries.py", "export_summary_pdf"): 2,

    ("app/routers/summaries.py", "generate_summary_stream"): 7,
}

# The walk must keep seeing the routers' async session routes; fewer means a broken walk.
MIN_ASYNC_SESSION_FUNCTIONS = 60

# Callees that run their callable argument in a worker thread.
_THREAD_DISPATCHERS = frozenset({"run_in_threadpool", "to_thread", "run_sync", "run_in_executor"})


def _tail(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _names_session(node: ast.AST | None, aliases: set[str]) -> bool:
    """Whether an annotation or default names a session: ``Session``, ``Depends(get_db...)``, or a
    module-level alias of either."""
    if node is None:
        return False
    for part in ast.walk(node):
        if _tail(part) in {"Session", "get_db"} | aliases:
            return True
    return False


def _session_params(fn: ast.AsyncFunctionDef, aliases: set[str]) -> set[str]:
    positional = fn.args.posonlyargs + fn.args.args
    defaults: list[ast.expr | None] = [None] * (len(positional) - len(fn.args.defaults))
    defaults += fn.args.defaults
    pairs = list(zip(positional, defaults)) + list(zip(fn.args.kwonlyargs, fn.args.kw_defaults))
    return {
        arg.arg for arg, default in pairs
        if arg.arg == "db" or _names_session(arg.annotation, aliases) or _names_session(default, aliases)
    }


def _on_loop_uses(fn: ast.AsyncFunctionDef, sessions: set[str]) -> list[tuple[int, str]]:
    """``(line, attribute)`` for each session attribute read on the loop in ``fn``."""
    names = set(sessions)
    handed_to_thread: set[int] = set()
    uses: list[tuple[int, str]] = []

    def visit(node: ast.AST) -> None:
        if isinstance(node, (ast.FunctionDef, ast.Lambda, ast.ClassDef)):
            return  # runs where it is handed, normally the thread pool
        if isinstance(node, ast.Call) and _tail(node.func) in _THREAD_DISPATCHERS:
            handed_to_thread.update(id(arg) for arg in node.args)
        bound = node.value if isinstance(node, (ast.Assign, ast.AnnAssign, ast.NamedExpr)) else None
        if isinstance(bound, ast.Name) and bound.id in names:
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names.update(target.id for target in targets if isinstance(target, ast.Name))
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id in names
            and id(node) not in handed_to_thread
        ):
            uses.append((node.lineno, node.attr))
        for child in ast.iter_child_nodes(node):
            visit(child)

    for statement in fn.body:
        visit(statement)
    return uses


def on_loop_session_uses(source: str) -> dict[str, list[tuple[int, str]]]:
    """Every ``async def`` in ``source`` that receives a session -> its on-loop session reads.

    A function nested in one already read is part of it; any other function is searched for
    async session functions of its own."""
    tree = ast.parse(source)
    aliases = {
        target.id
        for statement in tree.body if isinstance(statement, ast.Assign)
        for target in statement.targets
        if isinstance(target, ast.Name) and _names_session(statement.value, set())
    }
    found: dict[str, list[tuple[int, str]]] = {}

    def search(node: ast.AST) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.AsyncFunctionDef) and (sessions := _session_params(child, aliases)):
                found.setdefault(child.name, []).extend(_on_loop_uses(child, sessions))
            else:
                search(child)

    search(tree)
    return found


def _router_uses() -> dict[tuple[str, str], list[tuple[int, str]]]:
    uses: dict[tuple[str, str], list[tuple[int, str]]] = {}
    for path in sorted(ROUTERS_DIR.rglob("*.py")):
        relative = path.relative_to(BACKEND_DIR).as_posix()
        for name, sites in on_loop_session_uses(path.read_text(encoding="utf-8")).items():
            uses[(relative, name)] = sites
    return uses


def test_async_routes_keep_the_request_session_off_the_loop():
    uses = _router_uses()
    assert len(uses) >= MIN_ASYNC_SESSION_FUNCTIONS, f"the walk found only {len(uses)} async session functions"
    over = {
        f"{path}::{name}": sites
        for (path, name), sites in uses.items()
        if len(sites) > ON_LOOP_CEILINGS.get((path, name), 0)
    }
    assert not over, (
        "These async routes work their request session on the event loop beyond their ceiling "
        f"(line, attribute): {over}. Move the session work, the payload and the release into one "
        "sync function handed to run_in_threadpool, or into a service that reads and releases in "
        "one unit (lessons/ops-release-cached-filing-reads-before-yield.md). Do not raise a ceiling "
        "to pass."
    )


_PLANTED = '''
from typing import Annotated
from fastapi import Depends
from sqlalchemy import orm
from sqlalchemy.orm import Session
from app.database import get_db
import anyio
import asyncio

SessionDep = Annotated[Session, Depends(get_db)]

async def flags_a_query_chain(db: Session = Depends(get_db)):
    return db.query(Row).filter(Row.id == 1).first()

async def flags_each_call_in_branches(flag: bool, db: Session = Depends(get_db)):
    if flag:
        try:
            db.add(Row())
            db.commit()
        except ValueError:
            db.rollback()
        finally:
            db.close()

async def flags_a_scoped_dependency(db: Session = Depends(get_db, scope="function")):
    return db.get(Row, 1)

async def flags_an_annotated_dependency(session: Annotated[Session, Depends(get_db)]):
    return session.execute(statement)

async def flags_a_module_alias(session: SessionDep):
    return session.scalars(statement)

async def flags_a_qualified_annotation(session: orm.Session):
    return session.scalar(statement)

async def flags_an_alias_in_the_body(db: Session = Depends(get_db)):
    held = db
    return held.query(Row).all()

async def flags_an_annotated_alias(db: Session = Depends(get_db)):
    held: Session = db
    return held.query(Row).all()

async def flags_a_walrus_alias(db: Session = Depends(get_db)):
    if (held := db) is not None:
        return held.query(Row).all()

async def flags_a_bound_method(db: Session = Depends(get_db)):
    read = db.get
    return read(Row, 1)

async def flags_a_nested_async_def(db: Session = Depends(get_db)):
    async def stream():
        yield db.query(Row).count()
    return stream()

async def flags_a_comprehension(ids: list, db: Session = Depends(get_db)):
    return [db.get(Row, row_id) for row_id in ids]

def factory():
    async def flags_a_route_a_factory_builds(db: Session = Depends(get_db)):
        return db.query(Row).all()
    return flags_a_route_a_factory_builds

async def clean_threadpool_closure(db: Session = Depends(get_db)):
    def unit():
        try:
            return db.query(Row).all()
        finally:
            release(db)
    return await run_in_threadpool(unit)

async def clean_uncalled_method_to_the_pool(db: Session = Depends(get_db)):
    await run_in_threadpool(db.commit)
    await anyio.to_thread.run_sync(db.rollback)
    await asyncio.to_thread(db.close)

async def clean_lambda_to_the_pool(db: Session = Depends(get_db)):
    return await run_in_threadpool(lambda: db.query(Row).all())

async def clean_no_session(request: Request):
    return await request.json()

def clean_sync_route(db: Session = Depends(get_db)):
    return db.query(Row).all()

async def gap_service_on_the_loop(db: Session = Depends(get_db)):
    return service.read(db, 1)

async def gap_closure_called_on_the_loop(db: Session = Depends(get_db)):
    def unit():
        return db.query(Row).all()
    return unit()

class Holder:
    db: Session

async def gap_session_in_an_attribute(holder: Holder):
    return holder.db.query(Row).all()
'''

# Function -> how many on-loop session reads the walk must find. ``gap_`` forms break the rule but
# are out of the walk's reach (the header names them); they are planted so a widened walk updates
# this table on purpose. The walk reads no other planted function: ``clean_no_session`` and
# ``gap_session_in_an_attribute`` receive no session, and ``clean_sync_route`` is a sync route
# (FastAPI runs it in the thread pool).
_PLANTED_COUNTS = {
    "flags_a_query_chain": 1,
    "flags_each_call_in_branches": 4,
    "flags_a_scoped_dependency": 1,
    "flags_an_annotated_dependency": 1,
    "flags_a_module_alias": 1,
    "flags_a_qualified_annotation": 1,
    "flags_an_alias_in_the_body": 1,
    "flags_an_annotated_alias": 1,
    "flags_a_walrus_alias": 1,
    "flags_a_bound_method": 1,
    "flags_a_nested_async_def": 1,
    "flags_a_comprehension": 1,
    "flags_a_route_a_factory_builds": 1,
    "clean_threadpool_closure": 0,
    "clean_uncalled_method_to_the_pool": 0,
    "clean_lambda_to_the_pool": 0,
    "gap_service_on_the_loop": 0,
    "gap_closure_called_on_the_loop": 0,
}


def test_walk_sees_each_form():
    found = {name: len(sites) for name, sites in on_loop_session_uses(_PLANTED).items()}
    assert found == _PLANTED_COUNTS
