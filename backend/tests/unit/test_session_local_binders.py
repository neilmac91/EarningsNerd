"""Every app module that copies ``SessionLocal`` at import is imported before any test can patch the factory (E263).

``tests/support/session_local_binders.py`` explains the leak this closes. Here the list it keeps is held to the code:
each module under ``app/`` whose import-time code copies ``app.database.SessionLocal`` is listed, and nothing else is.
A copy is an import of ``SessionLocal`` from ``app.database`` (relative imports, aliases and a star import included)
or a read of it off the module (``database.SessionLocal``, ``app.database.SessionLocal``), anywhere that runs at
import: the top level, a top-level ``if``, ``try``, ``with`` or class body, and a function's decorators and default
values. A function body runs when it is called, so it reads the factory then, which is the remedy.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

from tests.support.session_local_binders import SESSION_LOCAL_BINDERS

BACKEND = Path(__file__).resolve().parents[2]
APP = BACKEND / "app"


def _import_time_nodes(node: ast.AST):
    """Every node that runs when its module is imported. A function's or a lambda's body is left out; its decorators
    and default values are kept, since they run when the function is defined."""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            defined = [*getattr(child, "decorator_list", ()), *child.args.defaults]
            for part in [*defined, *(default for default in child.args.kw_defaults if default is not None)]:
                yield part
                yield from _import_time_nodes(part)
            continue
        yield child
        yield from _import_time_nodes(child)


def _resolved_module(node: ast.ImportFrom, package: str) -> str | None:
    """The absolute module an ``ImportFrom`` reads, resolving a relative import against ``package``."""
    if node.level == 0:
        return node.module
    parts = package.split(".")
    if node.level - 1 >= len(parts):
        return None
    base = parts[: len(parts) - (node.level - 1)]
    return ".".join(base + ([node.module] if node.module else []))


def binds_session_local(source: str, module: str, *, is_package: bool = False) -> bool:
    """True when ``source``, the module named ``module``, copies ``app.database.SessionLocal`` at import."""
    package = module if is_package else module.rpartition(".")[0]
    nodes = list(_import_time_nodes(ast.parse(source)))
    database_names: set[str] = set()  # names the module binds to app.database at import
    app_names: set[str] = set()  # names it binds to the app package, through which it can reach app.database
    for node in nodes:
        if isinstance(node, ast.ImportFrom):
            resolved = _resolved_module(node, package)
            if resolved == "app.database" and any(alias.name in ("SessionLocal", "*") for alias in node.names):
                return True
            if resolved == "app":
                database_names |= {alias.asname or alias.name for alias in node.names if alias.name == "database"}
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "app.database":
                    (database_names if alias.asname else app_names).add(alias.asname or "app")
    for node in nodes:
        if isinstance(node, ast.Attribute) and node.attr == "SessionLocal":
            base = node.value
            if isinstance(base, ast.Name) and base.id in database_names:
                return True
            if isinstance(base, ast.Attribute) and base.attr == "database" and isinstance(base.value, ast.Name):
                if base.value.id in app_names:
                    return True
    return False


def binders_under(root: Path) -> list[str]:
    """The dotted names of the modules under ``root`` (a directory inside ``backend/``) that bind the factory."""
    found = []
    for path in sorted(root.rglob("*.py")):
        relative = path.relative_to(BACKEND).with_suffix("")
        is_package = relative.name == "__init__"
        parts = relative.parent.parts if is_package else relative.parts
        name = ".".join(parts)
        if binds_session_local(path.read_text(encoding="utf-8"), name, is_package=is_package):
            found.append(name)
    return found


def test_the_list_names_every_app_module_that_binds_session_local_at_import():
    assert binders_under(APP) == sorted(SESSION_LOCAL_BINDERS), (
        "an app module copies app.database.SessionLocal at import: list it in tests/support/session_local_binders.py "
        "so tests/conftest.py imports it before any test can patch the factory, or read the factory inside the "
        "function that calls it (`from app import database` at the top, `database.SessionLocal()` in the body)"
    )


def test_every_listed_binder_is_imported_by_the_time_a_test_runs():
    # tests/conftest.py's session fixture imports each one before the first test body.
    assert [name for name in SESSION_LOCAL_BINDERS if name not in sys.modules] == []


def test_the_scan_reads_each_import_time_form_and_skips_a_call_time_one():
    module = "app.services.planted"
    binding = [
        "from app.database import SessionLocal\n",
        "from app.database import engine, SessionLocal as Factory\n",
        "from app.database import *\n",
        "from ..database import SessionLocal\n",
        "try:\n    from app.database import SessionLocal\nexcept ImportError:\n    SessionLocal = None\n",
        "if True:\n    from app.database import SessionLocal\n",
        "class Store:\n    from app.database import SessionLocal\n",
        # A read of the factory off the module at import copies it too.
        "from app import database\nFactory = database.SessionLocal\n",
        "from app import database as db\nFactory = db.SessionLocal\n",
        "import app.database as db\nFactory = db.SessionLocal\n",
        "import app.database\nFactory = app.database.SessionLocal\n",
        "from .. import database\nFactory = database.SessionLocal\n",
        "from app import database\nclass Store:\n    factory = database.SessionLocal\n",
        "from app import database\ndef unit(factory=database.SessionLocal):\n    return factory()\n",
        "from app import database\ndef unit(*, factory=database.SessionLocal):\n    return factory()\n",
        "from app import database\n@cache(database.SessionLocal)\ndef unit():\n    pass\n",
        "from app import database\nunit = lambda factory=database.SessionLocal: factory()\n",
    ]
    not_binding = [
        "def unit():\n    from app.database import SessionLocal\n    return SessionLocal()\n",
        "async def unit():\n    from app.database import SessionLocal\n",
        "from app import database\n",
        "import app.database\n",
        "from app.database import engine, Base\n",
        "from .database import SessionLocal\n",  # app.services.database, not app.database
        "from sqlalchemy.orm import sessionmaker as SessionLocal\n",
        # Read when called, the remedy: a function body, or a lambda's.
        "from app import database\ndef unit():\n    return database.SessionLocal()\n",
        "from app import database\nunit = lambda: database.SessionLocal()\n",
        # A module named database that is not app.database.
        "from app.services import database\nFactory = database.SessionLocal\n",
        "from . import database\nFactory = database.SessionLocal\n",  # app.services.database
        "import database\nFactory = database.SessionLocal\n",
    ]
    assert [source for source in binding if not binds_session_local(source, module)] == []
    assert [source for source in not_binding if binds_session_local(source, module)] == []
    # A package's own relative import resolves against the package itself.
    assert binds_session_local("from ..database import SessionLocal\n", "app.services.edgar", is_package=True) is False
    assert binds_session_local("from ..database import SessionLocal\n", "app.services", is_package=True) is True
