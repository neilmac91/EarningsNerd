"""Gate for lessons/ops-auth-lookups-must-let-request-cleanup-progress.md: work that waits for a database
pool slot never runs on the event loop's default executor.

The default executor is shared with work that may hold a slot: a password change or reset keeps its
connection checked out while it awaits bcrypt through ``asyncio.to_thread``. A unit waiting there for a
slot could hold the thread such a holder needs, and neither could move until the pool timed out.
Pool-waiting units run on threads of their own instead (``copilot_chat._LOOKUP_THREADS``,
``facts.sync_threads._SYNC_THREADS``).

The scan reads every module under ``app/`` and the backend's top-level modules (``main.py``,
``task_worker_main.py``) through ``ast`` and lists each call that hands work to the default executor:
``asyncio.to_thread(...)`` under any name the module imports it by, from ``asyncio`` or
``asyncio.threads``, and ``run_in_executor(None, ...)`` on any loop. ``SITES`` names each one by file,
the outermost function holding it and the work it hands over, with why that work never waits for a
slot. A new site fails until it is listed, once its work has been checked, and a listed site that is
gone fails until its line is.

Out of reach, so review holds them: the default executor reached any other way (an executor of ``None``
held in a variable or passed by keyword, a callable passed by keyword, ``to_thread`` reached through
the ``asyncio.threads`` module itself under any name it is imported or assigned by,
``loop.getaddrinfo`` and the other loop methods that use it, a library that calls it), and a listed
callable that later starts to open a session.
"""

from __future__ import annotations

import ast
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]

_BCRYPT = "bcrypt over the request's own values; it opens no session"
SITES: dict[tuple[str, str, str], str] = {
    ("app/routers/analysis.py", "export_analysis_xlsx", "build_analysis_workbook"):
        "openpyxl over the dataset its unit built and released; it opens no session",
    ("app/routers/auth.py", "register", "get_password_hash"): _BCRYPT,
    ("app/routers/auth.py", "login", "verify_password"): _BCRYPT,
    ("app/routers/auth.py", "reset_password", "get_password_hash"): _BCRYPT,
    ("app/routers/auth.py", "change_password", "verify_password"): _BCRYPT,
    ("app/routers/auth.py", "change_password", "get_password_hash"): _BCRYPT,
    ("app/services/copilot_service.py", "_admit_not_disclosed", "_withhold_unsupported_quotations"):
        "string matching against the filing text already in memory; it opens no session",
    ("app/services/copilot_service.py", "_admit_answer", "_withhold_unsupported_quotations"):
        "string matching against the filing text already in memory; it opens no session",
    ("app/services/export_service.py", "export_pdf", "lambda: HTML(string=html_content).write_pdf(**PDF_OPTIONS)"):
        "WeasyPrint over HTML already rendered; it opens no session",
    ("app/services/export_service.py", "export_analysis_pdf", "lambda: HTML(string=html_content).write_pdf(**PDF_OPTIONS)"):
        "WeasyPrint over HTML already rendered; it opens no session",
    ("main.py", "lifespan", "_validate_db_connection"):
        "the startup connection check, before the app serves a request, so no other work holds a slot",
}


def default_executor_sites(source: str, file: str = "probe.py") -> list[tuple[str, str, str]]:
    """Each call in ``source`` that hands work to the default executor, as (file, function, work)."""
    tree = ast.parse(source)
    asyncio_names = {"asyncio"}
    to_thread_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            asyncio_names.update(alias.asname or alias.name for alias in node.names if alias.name == "asyncio")
        elif isinstance(node, ast.ImportFrom) and node.module in ("asyncio", "asyncio.threads"):
            to_thread_names.update(alias.asname or alias.name for alias in node.names if alias.name == "to_thread")

    def work(call: ast.Call) -> str | None:
        func = call.func
        to_thread = (
            isinstance(func, ast.Attribute) and func.attr == "to_thread"
            and isinstance(func.value, ast.Name) and func.value.id in asyncio_names
        ) or (isinstance(func, ast.Name) and func.id in to_thread_names)
        if to_thread and call.args:
            return ast.unparse(call.args[0])
        on_default = (
            isinstance(func, ast.Attribute) and func.attr == "run_in_executor" and len(call.args) >= 2
            and isinstance(call.args[0], ast.Constant) and call.args[0].value is None
        )
        return ast.unparse(call.args[1]) if on_default else None

    sites: list[tuple[str, str, str]] = []

    def visit(node: ast.AST, function: str) -> None:
        for child in ast.iter_child_nodes(node):
            outer = function
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and function == "<module>":
                outer = child.name
            if isinstance(child, ast.Call) and (handed := work(child)) is not None:
                sites.append((file, outer, handed))
            visit(child, outer)

    visit(tree, "<module>")
    return sites


def test_every_default_executor_site_is_listed_with_its_reason():
    found: list[tuple[str, str, str]] = []
    for path in sorted((BACKEND_DIR / "app").rglob("*.py")) + sorted(BACKEND_DIR.glob("*.py")):
        file = path.relative_to(BACKEND_DIR).as_posix()
        found.extend(default_executor_sites(path.read_text(encoding="utf-8"), file))
    assert len(found) == len(set(found)), "two sites share a key; name the work apart"
    new = sorted(set(found) - set(SITES))
    gone = sorted(set(SITES) - set(found))
    assert not new, (
        f"Work handed to the default executor at {new}. If it can wait for a database pool slot, run it "
        "on threads of its own (lessons/ops-auth-lookups-must-let-request-cleanup-progress.md); if it "
        "cannot, list it in SITES with the reason."
    )
    assert not gone, f"Listed sites no longer found: {gone}. Remove their lines."


def test_the_scan_reads_each_form_it_claims():
    probe = '''
import asyncio
import asyncio as aio
from asyncio import to_thread
from asyncio import to_thread as off_loop
from asyncio.threads import to_thread as threads_to_thread

async def plain():
    await asyncio.to_thread(first)

async def aliased():
    await aio.to_thread(second)

async def imported():
    await to_thread(third)
    await off_loop(fourth)
    await threads_to_thread(from_threads)

async def on_a_loop(loop):
    await loop.run_in_executor(None, fifth)
    await asyncio.get_running_loop().run_in_executor(None, sixth)

async def nested():
    def inner():
        return asyncio.to_thread(seventh)
    return inner

async def own_threads(loop, threads):
    await loop.run_in_executor(threads, not_default)
    await loop.run_in_executor(executor=None, func=keywords_out_of_reach)
'''
    assert default_executor_sites(probe) == [
        ("probe.py", "plain", "first"),
        ("probe.py", "aliased", "second"),
        ("probe.py", "imported", "third"),
        ("probe.py", "imported", "fourth"),
        ("probe.py", "imported", "from_threads"),
        ("probe.py", "on_a_loop", "fifth"),
        ("probe.py", "on_a_loop", "sixth"),
        ("probe.py", "nested", "seventh"),
    ]
