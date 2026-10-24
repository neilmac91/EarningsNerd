"""Rule-12 gate: a filing's stored excerpt is written only by its two owners.

``FilingContentCache.critical_excerpt`` is the text read-time citation verification, the Risks
projection and Copilot read a stored summary against. A forced refresh that cleared it before its run
and put it back afterwards (P11, #1545) left a window in which an overlapping refresh captured a
rejected run's excerpt and wrote it back beside the kept summary (Codex 4365089688). The owners now:

* ``summary_generation_service.get_or_cache_excerpt``: caches the excerpt an unforced run builds
  (``persist=True``; a forced run passes ``persist=False`` and keeps it to itself);
* ``content_cache.upsert_content_cache``: finalize's write, in the same commit as the summary row it
  grounds (``replace_excerpt`` for a forced run).

This gate holds the writes it can see in ``backend/app`` and ``backend/scripts`` to ``ALLOWED``:
an assignment to a ``.critical_excerpt`` attribute (a tuple target included), a ``critical_excerpt=``
keyword to ``FilingContentCache(...)``, and a ``critical_excerpt`` key (``X.critical_excerpt`` or the string) in a dict literal.
Out of reach, stated so nothing is overclaimed: ``setattr`` with a computed name, SQL text, a Core
``update().values(**kw)`` built from a variable, and deleting the whole cache row (the admin filing
reset deletes the summary in the same commit).
"""
from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
ROOTS = (BACKEND / "app", BACKEND / "scripts")
FIELD = "critical_excerpt"

ALLOWED = Counter({
    ("app/services/content_cache.py", "upsert_content_cache"): 3,
    ("app/services/summary_generation_service.py", "get_or_cache_excerpt"): 2,
})


def _is_field(node: ast.AST) -> bool:
    return (isinstance(node, ast.Attribute) and node.attr == FIELD) or (
        isinstance(node, ast.Constant) and node.value == FIELD
    )


def _names_model(func: ast.AST) -> bool:
    """``FilingContentCache(...)`` under its name or as ``models.FilingContentCache(...)``; a
    ``SimpleNamespace(critical_excerpt=...)`` snapshot (Copilot's) is a read, not a write."""
    return (isinstance(func, ast.Name) and func.id == "FilingContentCache") or (
        isinstance(func, ast.Attribute) and func.attr == "FilingContentCache"
    )


def _writes(tree: ast.AST) -> list[tuple[str, int]]:
    found: list[tuple[str, int]] = []

    def visit(node: ast.AST, scope: str) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and scope == "<module>":
            scope = node.name
        if isinstance(node, ast.Attribute) and node.attr == FIELD and isinstance(node.ctx, ast.Store):
            found.append((scope, node.lineno))
        elif isinstance(node, ast.Call) and _names_model(node.func):
            found.extend((scope, kw.value.lineno) for kw in node.keywords if kw.arg == FIELD)
        elif isinstance(node, ast.Dict):
            found.extend((scope, key.lineno) for key in node.keys if key is not None and _is_field(key))
        for child in ast.iter_child_nodes(node):
            visit(child, scope)

    visit(tree, "<module>")
    return found


def scan() -> Counter:
    sites: Counter = Counter()
    for root in ROOTS:
        for path in sorted(root.rglob("*.py")):
            rel = path.relative_to(BACKEND).as_posix()
            for scope, _line in _writes(ast.parse(path.read_text(encoding="utf-8"), filename=rel)):
                sites[(rel, scope)] += 1
    return sites


def test_only_the_two_owners_write_the_stored_excerpt():
    sites = scan()
    assert sites == ALLOWED, (
        "a new or changed writer of FilingContentCache.critical_excerpt; a forced run keeps its excerpt "
        f"private until finalize stores it with the summary it grounds. New or changed: {dict(sites - ALLOWED)}; "
        f"gone: {dict(ALLOWED - sites)}"
    )


def test_the_scan_scores_every_planted_form():
    planted = ast.parse(
        "def f(cache, stored):\n"
        "    stored, cache.critical_excerpt = cache.critical_excerpt, None\n"
        "    cache.critical_excerpt = stored\n"
        "    q.update({FilingContentCache.critical_excerpt: stored})\n"
        "    q.update({'critical_excerpt': stored})\n"
        "    FilingContentCache(filing_id=1, critical_excerpt=stored)\n"
        "    SimpleNamespace(critical_excerpt=stored)\n"  # a snapshot, not a write
        "    return cache.critical_excerpt\n"  # a read, not a write
    )
    assert Counter(scope for scope, _ in _writes(planted)) == Counter({"f": 5})
