"""Ratchet gate: routers are HTTP only (CLAUDE.md "Where things live").

``app/routers/`` parses the request, declares its dependencies and shapes the response; queries
and business rules live in ``app/services/``. Nothing enforced that, so the routers grew a data
layer of their own (``auth.py`` carried about 30 non-route helpers). An AST walk over
``app/routers/**/*.py`` counts each file's ORM touchpoints and fails when a file exceeds its
ceiling in ``ROUTER_ORM_CEILINGS``. The ceilings are the counts when the gate landed. A PR that
thins a router lowers that router's ceiling in the same diff (to 0 when it is done). An unlisted
file's ceiling is 0, so every new router starts thin. Raising a ceiling is a reviewed diff that has
to explain itself. The gate fails only above a ceiling, never below one: while other branches edit
routers in parallel, an exact match would turn main red when one of them merges with fewer
touchpoints. Lowering is therefore each thinning PR's job, checked in review.

A touchpoint is any of:

1. **A session attribute**: ``db.query(...)``, ``db.commit()``, or ``db.commit`` handed uncalled
   to ``run_in_threadpool``. A session is a name annotated with a SQLAlchemy type, a name bound
   from an ``app.database`` factory (``s = SessionLocal()``, ``with SessionLocal() as s``,
   ``s = next(get_db())``), a parameter defaulting to ``Depends(<an app.database name>)``, an
   alias of any of these (``s = db``), or a name called ``db``. The session call opens one
   touchpoint for its chain (``db.query(User).filter(User.id == 1).first()`` is one); column
   methods and SQLAlchemy names inside the chain each add one more.
2. **A SQLAlchemy name outside an annotation**: ``select(...)``, ``func.count()``,
   ``joinedload(...)``, ``except IntegrityError``, ``sa.update(...)``.
3. **An ``app.database`` name outside ``Depends(...)``**: ``SessionLocal()``, ``engine``.
4. **A call rooted at an ``app.models`` name**: a row constructor ``User(...)`` or a column
   expression ``Filing.filing_date.desc()``.

Imports are resolved whether absolute or relative (``from ..database import SessionLocal``).

Plumbing does not count: ``db: Session = Depends(get_db)`` is how a router receives its session,
``current_user: User`` is an annotation, ``SessionDep = Annotated[Session, Depends(get_db)]`` is an
annotation alias, and ``watchlist_service.add(db, ...)`` (handing the session to a service) is the
shape this gate asks for. A router that hands a service a session *factory* (``SessionLocal``) for
work outside the request still touches ``app.database``: let the service default to the factory.

Limitation: without type inference the walk cannot see an ORM *instance*: a lazy-loaded
relationship (``user.oauth_accounts``), an attribute write (``user.full_name = ...``) on a row a
service returned, a bare column clause handed to a service (``svc.find(db, User.email == x)``), or
a session that a local helper returns under another name. Those remain a review concern. ``test_counter_sees_each_shape`` proves the counter's reach on synthetic source, so
a regression in the walk fails there instead of passing every router vacuously.
"""
import ast
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]
ROUTERS_DIR = BACKEND_DIR / "app" / "routers"

# Router file (relative to backend/) -> its ceiling. Counted on origin/main da636f6 (2026-10-08) by
# this file's own walk. Lower an entry when a PR moves work into app/services/, and set it to 0 (do
# not delete it) when the router is done. Git conflicts on edits to adjacent lines: the blank line
# between entries keeps in-place number edits on different entries mergeable in any order, which
# deleting a line (with or without its blank line) would not be. A cleanup PR prunes the zero rows
# once no sibling branch is editing the table.
ROUTER_ORM_CEILINGS: dict[str, int] = {
    "app/routers/admin.py": 52,

    "app/routers/analysis.py": 10,


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

    "app/routers/watchlist.py": 49,

    "app/routers/webhooks.py": 1,
}

_SQLALCHEMY = "sqlalchemy"
_DATABASE = "app.database"
_MODELS = "app.models"


def _within(qualname: str | None, family: str) -> bool:
    return qualname is not None and (qualname == family or qualname.startswith(family + "."))


def _import_table(tree: ast.AST, package: str) -> dict[str, str]:
    """Local name -> fully qualified origin, for every import anywhere in the file. ``package`` is
    the file's package (``app.routers``), against which relative imports resolve."""
    table: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    table[alias.asname] = alias.name
                else:  # ``import app.models`` binds ``app``
                    root = alias.name.split(".")[0]
                    table[root] = root
        elif isinstance(node, ast.ImportFrom):
            parts = package.split(".")
            base = parts[: len(parts) - node.level + 1] if node.level else []
            module = ".".join([*base, *([node.module] if node.module else [])])
            for alias in node.names:
                table[alias.asname or alias.name] = f"{module}.{alias.name}"
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


def _annotation_aliases(tree: ast.AST, imports: dict[str, str]) -> dict[str, ast.AST]:
    """``SessionDep = Annotated[Session, Depends(get_db)]`` (or ``X: TypeAlias = ...``): name -> value."""
    aliases: dict[str, ast.AST] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            value = node.value
            if isinstance(value, ast.Subscript) and (_qualname(value.value, imports) or "").endswith(".Annotated"):
                aliases[node.targets[0].id] = value
        elif (
            isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None
            and (_qualname(node.annotation, imports) or "").endswith(".TypeAlias")
        ):
            aliases[node.target.id] = node.value
    return aliases


def _annotation_node_ids(tree: ast.AST, aliases: dict[str, ast.AST]) -> set[int]:
    annotations: list[ast.AST] = list(aliases.values())
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


def _annotation_is_sqlalchemy(annotation: ast.AST, imports: dict[str, str], aliases: dict[str, ast.AST]) -> bool:
    if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
        try:
            annotation = ast.parse(annotation.value, mode="eval").body
        except SyntaxError:
            return False
    for node in ast.walk(annotation):
        if isinstance(node, ast.Name) and node.id in aliases:
            if _annotation_is_sqlalchemy(aliases[node.id], imports, {k: v for k, v in aliases.items() if k != node.id}):
                return True
        elif isinstance(node, (ast.Name, ast.Attribute)) and _within(_qualname(node, imports), _SQLALCHEMY):
            return True
    return False


def _is_database_dependency(default: ast.AST | None, imports: dict[str, str]) -> bool:
    """``Depends(get_db)`` / ``Depends(dependency=get_db)``."""
    if not isinstance(default, ast.Call):
        return False
    func = default.func
    name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
    return name == "Depends" and any(
        _within(_qualname(arg, imports), _DATABASE) for arg in [*default.args, *(kw.value for kw in default.keywords)]
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


def _session_names(tree: ast.AST, imports: dict[str, str], aliases: dict[str, ast.AST]) -> set[str]:
    names = {"db"}
    copies: list[tuple[str, str]] = []  # (target, source) for ``s = db``
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = node.args
            positional = [*args.posonlyargs, *args.args]
            defaults = dict(zip([a.arg for a in positional[len(positional) - len(args.defaults):]], args.defaults))
            defaults.update({a.arg: d for a, d in zip(args.kwonlyargs, args.kw_defaults) if d is not None})
            for arg in [*positional, *args.kwonlyargs]:
                if (arg.annotation is not None and _annotation_is_sqlalchemy(arg.annotation, imports, aliases)) \
                        or _is_database_dependency(defaults.get(arg.arg), imports):
                    names.add(arg.arg)
        elif isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if _is_session_factory(node.value, imports):
                names.update(targets)
            elif isinstance(node.value, ast.Name):
                copies.extend((target, node.value.id) for target in targets)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and (
            _annotation_is_sqlalchemy(node.annotation, imports, aliases)
            or (node.value is not None and _is_session_factory(node.value, imports))
        ):
            names.add(node.target.id)
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                if isinstance(item.optional_vars, ast.Name) and _is_session_factory(item.context_expr, imports):
                    names.add(item.optional_vars.id)
    while True:  # follow ``s = db`` (and chains of such copies) to a fixpoint
        grown = {target for target, source in copies if source in names} - names
        if not grown:
            return names
        names |= grown


def _touchpoints(source: str, package: str = "app.routers") -> list[tuple[int, str]]:
    """(line, what) for every ORM touchpoint in ``source``; see the module docstring."""
    tree = ast.parse(source)
    imports = _import_table(tree, package)
    aliases = _annotation_aliases(tree, imports)
    sessions = _session_names(tree, imports, aliases)
    in_annotation = _annotation_node_ids(tree, aliases)
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


def _package_of(py: Path) -> str:
    return ".".join(py.relative_to(BACKEND_DIR).parent.parts)


def test_router_orm_touchpoints_stay_under_their_ceilings():
    over: list[str] = []
    for py in _router_files():
        rel = py.relative_to(BACKEND_DIR).as_posix()
        points = _touchpoints(py.read_text(encoding="utf-8"), _package_of(py))
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
        assert isinstance(ceiling, int) and not isinstance(ceiling, bool) and ceiling >= 0, (
            f"{rel}: ceiling {ceiling!r} must be a non-negative int (a finished router sits at 0)"
        )
    # A deleted router's entry is tolerated, so a teardown PR and a ceiling change merge in either order.


def test_walk_reaches_the_routers():
    """Anti-vacuity: a broken glob and a thin codebase look the same from the outside."""
    files = _router_files()
    assert len(files) >= 20, f"expected the router package, found {len(files)} files"
    assert sum(len(_touchpoints(py.read_text(encoding="utf-8"), _package_of(py))) for py in files) > 0


_HEADER = """\
import sqlalchemy
import sqlalchemy as sa
from typing import Annotated, TypeAlias
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
    "an unannotated db parameter": ("def f(db, uid):\n    return db.get(User, uid)\n", 1),
    "an AnnAssign-bound session": (
        "def f(x):\n    s: Session = x\n    s.flush()\n", 1),
    "a Session(engine) factory": (
        "def f(e):\n    s = Session(e)\n    s.close()\n", 2),
    "a bare sqlalchemy import": ("def f():\n    return sqlalchemy.select(User)\n", 1),
    "a relative models import": (
        "from ..models import Company\ndef f():\n    return Company(ticker='X')\n", 1),
    "a relative database import": (
        "from ..database import SessionLocal as SL\ndef f():\n    s = SL()\n    return s.query(1)\n", 2),
    "a relative models package": (
        "from .. import models as m\ndef f():\n    return m.User()\n", 1),
    "a Depends-default session under another name": (
        "def f(conn=Depends(get_db)):\n    conn.commit()\n", 1),
    "a keyword Depends-default session": (
        "def f(*, conn=Depends(dependency=get_db)):\n    conn.commit()\n", 1),
    "an Annotated session alias under another name": (
        "SessionDep = Annotated[Session, Depends(get_db)]\ndef f(conn: SessionDep):\n    conn.add(1)\n", 1),
    "a copied session": ("def f(db: Session):\n    s = db\n    t = s\n    t.delete(1)\n", 1),
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
    "a returns annotation": "def f(db: Session = Depends(get_db)) -> Session:\n    return service.do(db)\n",
    "an annotated local": "def f(x):\n    y: Session = x\n    return service.do(y)\n",
    "a keyword Depends": "def f(db: Session = Depends(dependency=get_db)):\n    return service.do(db)\n",
    "an annotation alias": (
        "SessionDep = Annotated[Session, Depends(get_db)]\nSA: TypeAlias = Session\n"
        "def f(db: SessionDep, other: SA):\n    return service.do(db, other)\n"),
    "a parameter named like a model column": "def f(db: Session, filing_date: str):\n    return service.do(db, filing_date)\n",
}


@pytest.mark.parametrize("label", sorted(_COUNTED_SHAPES))
def test_counter_sees_each_shape(label):
    body, expected = _COUNTED_SHAPES[label]
    assert len(_touchpoints(_HEADER + body)) == expected, _touchpoints(_HEADER + body)


@pytest.mark.parametrize("label", sorted(_FREE_SHAPES))
def test_counter_ignores_plumbing(label):
    assert _touchpoints(_HEADER + _FREE_SHAPES[label]) == []
