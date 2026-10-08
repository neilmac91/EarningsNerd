"""Ratchet gate: routers are HTTP only (CLAUDE.md "Where things live").

``app/routers/`` parses the request, declares its dependencies and shapes the response; queries
and business rules live in ``app/services/``. Nothing enforced that, so the routers grew a data
layer of their own (``auth.py`` carried about 30 non-route helpers). An AST walk over
``app/routers/**/*.py`` counts each file's ORM touchpoints and fails when a file exceeds its
ceiling in ``ROUTER_ORM_CEILINGS``. The ceilings are the counts when the gate landed. A PR that
thins a router lowers that router's ceiling in the same diff; a router at zero leaves the table,
because an unlisted file's ceiling is 0 and every new router therefore starts thin. Raising a
ceiling is a reviewed diff that has to explain itself.

A touchpoint is any of:

1. **A session attribute**: ``db.query(...)``, ``db.commit()``, or ``db.commit`` handed uncalled
   to ``run_in_threadpool``. A session is a name annotated with a SQLAlchemy type, a name bound
   from an ``app.database`` factory (``s = SessionLocal()``, ``with SessionLocal() as s``,
   ``s = next(get_db())``), or a name called ``db``. A chain counts once:
   ``db.query(User).filter(...).first()`` is one touchpoint.
2. **A SQLAlchemy name outside an annotation**: ``select(...)``, ``func.count()``,
   ``joinedload(...)``, ``except IntegrityError``, ``sa.update(...)``.
3. **An ``app.database`` name outside ``Depends(...)``**: ``SessionLocal()``, ``engine``.
4. **A call rooted at an ``app.models`` name**: a row constructor ``User(...)`` or a column
   expression ``Filing.filing_date.desc()``.

Plumbing does not count: ``db: Session = Depends(get_db)`` is how a router receives its session,
``current_user: User`` is an annotation, and ``watchlist_service.add(db, ...)`` (handing the
session to a service) is the shape this gate asks for.

Limitation: without type inference the walk cannot see an ORM *instance*: a lazy-loaded
relationship (``user.oauth_accounts``) or an attribute write (``user.full_name = ...``) on a row a
service returned, or a session that a local helper returns under another name. Those remain a
review concern. ``test_counter_sees_each_shape`` proves the counter's reach on synthetic source, so
a regression in the walk fails there instead of passing every router vacuously.
"""
import ast
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]
ROUTERS_DIR = BACKEND_DIR / "app" / "routers"

# Router file (relative to backend/) -> its ceiling. Counted on origin/main da636f6 (2026-10-08) by
# this file's own walk. Lower an entry when a PR moves work into app/services/; delete it at zero.
# The blank line between entries is deliberate: git conflicts on edits to adjacent lines, so the
# spacing lets sibling PRs that lower different ceilings merge in any order.
ROUTER_ORM_CEILINGS: dict[str, int] = {
    "app/routers/admin.py": 52,

    "app/routers/analysis.py": 10,

    "app/routers/auth.py": 60,

    "app/routers/companies.py": 21,

    "app/routers/contact.py": 5,

    "app/routers/feedback.py": 5,

    "app/routers/filings.py": 39,

    "app/routers/internal.py": 18,

    "app/routers/saved_summaries.py": 21,

    "app/routers/sitemap.py": 7,

    "app/routers/subscriptions.py": 3,

    "app/routers/summaries.py": 31,

    "app/routers/users.py": 18,


    "app/routers/webhooks.py": 1,
}

_SQLALCHEMY = "sqlalchemy"
_DATABASE = "app.database"
_MODELS = "app.models"


def _within(qualname: str | None, family: str) -> bool:
    return qualname is not None and (qualname == family or qualname.startswith(family + "."))


def _import_table(tree: ast.AST) -> dict[str, str]:
    """Local name -> fully qualified origin, for every import anywhere in the file."""
    table: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    table[alias.asname] = alias.name
                else:  # ``import app.models`` binds ``app``
                    root = alias.name.split(".")[0]
                    table[root] = root
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            for alias in node.names:
                table[alias.asname or alias.name] = f"{node.module}.{alias.name}"
    return table


def _qualname(expr: ast.AST, imports: dict[str, str]) -> str | None:
    """``sa.orm.joinedload`` -> ``sqlalchemy.orm.joinedload``; None unless rooted at an import."""
    parts: list[str] = []
    while isinstance(expr, ast.Attribute):
        parts.append(expr.attr)
        expr = expr.value
    if not isinstance(expr, ast.Name) or expr.id not in imports:
        return None
    return ".".join([imports[expr.id], *reversed(parts)])


def _annotation_node_ids(tree: ast.AST) -> set[int]:
    annotations: list[ast.AST] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = node.args
            for arg in [*args.posonlyargs, *args.args, *args.kwonlyargs, args.vararg, args.kwarg]:
                if arg is not None and arg.annotation is not None:
                    annotations.append(arg.annotation)
            if node.returns is not None:
                annotations.append(node.returns)
        elif isinstance(node, ast.AnnAssign):
            annotations.append(node.annotation)
    return {id(inner) for annotation in annotations for inner in ast.walk(annotation)}


def _depends_argument_ids(tree: ast.AST) -> set[int]:
    """ids of the direct arguments of ``Depends(...)`` calls (``Depends(get_db)``)."""
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
            if name == "Depends":
                ids.update(id(arg) for arg in [*node.args, *(kw.value for kw in node.keywords)])
    return ids


def _annotation_is_sqlalchemy(annotation: ast.AST, imports: dict[str, str]) -> bool:
    if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
        try:
            annotation = ast.parse(annotation.value, mode="eval").body
        except SyntaxError:
            return False
    return any(
        _within(_qualname(node, imports), _SQLALCHEMY)
        for node in ast.walk(annotation)
        if isinstance(node, (ast.Name, ast.Attribute))
    )


def _is_session_factory(expr: ast.AST, imports: dict[str, str]) -> bool:
    """``SessionLocal()``, ``next(get_db())``, ``Session(engine)``."""
    if not isinstance(expr, ast.Call):
        return False
    qualname = _qualname(expr.func, imports)
    if _within(qualname, _DATABASE) or _within(qualname, _SQLALCHEMY):
        return True
    return (
        isinstance(expr.func, ast.Name) and expr.func.id == "next"
        and bool(expr.args) and _is_session_factory(expr.args[0], imports)
    )


def _session_names(tree: ast.AST, imports: dict[str, str]) -> set[str]:
    names = {"db"}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = node.args
            for arg in [*args.posonlyargs, *args.args, *args.kwonlyargs]:
                if arg.annotation is not None and _annotation_is_sqlalchemy(arg.annotation, imports):
                    names.add(arg.arg)
        elif isinstance(node, ast.Assign) and _is_session_factory(node.value, imports):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and (
            _annotation_is_sqlalchemy(node.annotation, imports)
            or (node.value is not None and _is_session_factory(node.value, imports))
        ):
            names.add(node.target.id)
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                if isinstance(item.optional_vars, ast.Name) and _is_session_factory(item.context_expr, imports):
                    names.add(item.optional_vars.id)
    return names


def _touchpoints(source: str) -> list[tuple[int, str]]:
    """(line, what) for every ORM touchpoint in ``source``; see the module docstring."""
    tree = ast.parse(source)
    imports = _import_table(tree)
    sessions = _session_names(tree, imports)
    in_annotation = _annotation_node_ids(tree)
    depends_args = _depends_argument_ids(tree)
    found: list[tuple[int, str]] = []

    def visit(node: ast.AST) -> None:
        if id(node) in in_annotation:
            return
        if isinstance(node, (ast.Name, ast.Attribute)) and isinstance(node.ctx, ast.Load):
            qualname = _qualname(node, imports)
            if _within(qualname, _SQLALCHEMY):
                found.append((node.lineno, qualname))
                return
            if _within(qualname, _DATABASE):
                if id(node) not in depends_args:
                    found.append((node.lineno, qualname))
                return
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in sessions:
            found.append((node.lineno, f"{node.value.id}.{node.attr}"))  # read, call or write
            return  # the session name itself is not a second touchpoint
        if isinstance(node, ast.Call):
            qualname = _qualname(node.func, imports)
            if _within(qualname, _MODELS):
                found.append((node.lineno, f"{qualname}(...)"))
                for arg in [*node.args, *(kw.value for kw in node.keywords)]:
                    visit(arg)
                return
        for child in ast.iter_child_nodes(node):
            visit(child)

    visit(tree)
    return sorted(found)


def _router_files() -> list[Path]:
    return sorted(ROUTERS_DIR.rglob("*.py"))


def test_router_orm_touchpoints_stay_under_their_ceilings():
    over: list[str] = []
    for py in _router_files():
        rel = py.relative_to(BACKEND_DIR).as_posix()
        points = _touchpoints(py.read_text(encoding="utf-8"))
        ceiling = ROUTER_ORM_CEILINGS.get(rel, 0)
        if len(points) > ceiling:
            over.append(
                f"{rel}: {len(points)} ORM touchpoints, ceiling {ceiling}\n"
                + "".join(f"    {rel}:{line} {what}\n" for line, what in points)
            )

    assert not over, (
        "Routers are HTTP only: request parsing, dependencies and response shaping. These files "
        "grew ORM work past their ceilings:\n" + "".join(over)
        + "Move the query or business rule into app/services/ (an existing module where one fits) "
        "and call it with the request's session. Do not raise a ceiling to make room; a new router "
        "file's ceiling is 0."
    )


def test_ceiling_table_is_well_formed():
    for rel, ceiling in ROUTER_ORM_CEILINGS.items():
        assert rel.startswith("app/routers/") and rel.endswith(".py"), f"{rel} is not a router file"
        assert isinstance(ceiling, int) and ceiling > 0, (
            f"{rel}: ceiling {ceiling!r}; a router at zero leaves ROUTER_ORM_CEILINGS (unlisted = 0)"
        )
    # A deleted router's entry is tolerated, so a teardown PR and a ceiling change merge in either order.


def test_walk_reaches_the_routers():
    """Anti-vacuity: a broken glob and a thin codebase look the same from the outside."""
    files = _router_files()
    assert len(files) >= 20, f"expected the router package, found {len(files)} files"
    assert sum(len(_touchpoints(py.read_text(encoding="utf-8"))) for py in files) > 0


_HEADER = """\
import sqlalchemy as sa
from typing import Annotated
from fastapi import Depends
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app import models
from app.database import SessionLocal, engine, get_db
from app.models import Filing, User
"""

_COUNTED_SHAPES = {
    "a query chain counts once": (
        "def f(db: Session):\n    return db.query(User).filter(User.id == 1).first()\n", 1),
    "an uncalled session method": (
        "async def f(db: Session):\n    await run_in_threadpool(db.commit)\n", 1),
    "a session under another annotated name": (
        "def f(conn: Session):\n    conn.add(1)\n    conn.flush()\n", 2),
    "a string-annotated session": (
        "def f(conn: 'Session'):\n    conn.rollback()\n", 1),
    "a factory-bound session": (
        "def f():\n    s = SessionLocal()\n    s.close()\n", 2),
    "a with-bound session": (
        "def f():\n    with SessionLocal() as s:\n        s.commit()\n", 2),
    "a session from next(get_db())": (
        "def f():\n    s = next(get_db())\n    s.execute(1)\n", 2),
    "select()": ("def f():\n    return select(User)\n", 1),
    "func.count()": ("def f():\n    return func.count(User.id)\n", 1),
    "an except clause": (
        "def f():\n    try:\n        g()\n    except IntegrityError:\n        pass\n", 1),
    "a sqlalchemy module alias": ("def f():\n    return sa.update(User)\n", 1),
    "a database engine": ("def f():\n    return engine.connect()\n", 1),
    "a row constructor": ("def f():\n    return User(email='x')\n", 1),
    "a column expression": ("def f():\n    return Filing.filing_date.desc()\n", 1),
    "a models module alias": ("def f():\n    return models.User()\n", 1),
    "a row constructor holding a query": (
        "def f(db: Session):\n    return User(n=db.scalar(select(func.count())))\n", 4),
}

_FREE_SHAPES = {
    "dependency plumbing": (
        "def f(db: Session = Depends(get_db), user: User = Depends(current)):\n"
        "    return service.do(db, user)\n"),
    "an Annotated dependency": (
        "def f(db: Annotated[Session, Depends(get_db)]):\n    return service.do(db)\n"),
    "a Stripe session": (
        "def f():\n    checkout = stripe.checkout.Session.create()\n    return checkout.url\n"),
    "reading a returned row": (
        "def f(user: User):\n    return {'email': user.email, 'is_user': isinstance(user, User)}\n"),
}


@pytest.mark.parametrize("label", sorted(_COUNTED_SHAPES))
def test_counter_sees_each_shape(label):
    body, expected = _COUNTED_SHAPES[label]
    assert len(_touchpoints(_HEADER + body)) == expected, _touchpoints(_HEADER + body)


@pytest.mark.parametrize("label", sorted(_FREE_SHAPES))
def test_counter_ignores_plumbing(label):
    assert _touchpoints(_HEADER + _FREE_SHAPES[label]) == []
