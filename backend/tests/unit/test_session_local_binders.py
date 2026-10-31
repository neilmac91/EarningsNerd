"""Every app module that copies ``SessionLocal`` at import is imported before any test can patch the factory (E263).

``tests/support/session_local_binders.py`` explains the leak this closes. Here the list it keeps is held to the code:
each module under ``app/`` whose import-time statements import ``SessionLocal`` from ``app.database`` (relative
imports, aliases, a star import, and imports inside a top-level ``if``, ``try``, ``with`` or class body included) is
listed, and nothing else is. A function body's import is resolved each time the function runs, so it is not one.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

from tests.support.session_local_binders import SESSION_LOCAL_BINDERS

BACKEND = Path(__file__).resolve().parents[2]
APP = BACKEND / "app"


def _import_time_nodes(node: ast.AST):
    """Every node that runs when its module is imported: function bodies and lambdas are left out."""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
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
    for node in _import_time_nodes(ast.parse(source)):
        if isinstance(node, ast.ImportFrom) and _resolved_module(node, package) == "app.database":
            if any(alias.name in ("SessionLocal", "*") for alias in node.names):
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
        "so tests/conftest.py imports it before any test can patch the factory, or read the factory when it is "
        "called (`from app import database` ... `database.SessionLocal()`)"
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
    ]
    not_binding = [
        "def unit():\n    from app.database import SessionLocal\n    return SessionLocal()\n",
        "async def unit():\n    from app.database import SessionLocal\n",
        "from app import database\n",
        "import app.database\n",
        "from app.database import engine, Base\n",
        "from .database import SessionLocal\n",  # app.services.database, not app.database
        "from sqlalchemy.orm import sessionmaker as SessionLocal\n",
    ]
    assert [source for source in binding if not binds_session_local(source, module)] == []
    assert [source for source in not_binding if binds_session_local(source, module)] == []
    # A package's own relative import resolves against the package itself.
    assert binds_session_local("from ..database import SessionLocal\n", "app.services.edgar", is_package=True) is False
    assert binds_session_local("from ..database import SessionLocal\n", "app.services", is_package=True) is True
