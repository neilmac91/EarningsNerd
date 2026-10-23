"""Structural gate: every delete of ``summaries`` rows the scan can see is listed and reviewed.

``saved_summaries.summary_id`` references ``summaries.id`` with no ``ondelete``, so on PostgreSQL a
delete of a bookmarked summary raises (NO ACTION), while SQLite, the test database, enforces nothing
and orphans the bookmark (``lessons/arch-fk-safe-bulk-deletes.md``). A refresh never needs a delete:
the one orchestrator regenerates a stored summary in place under keep-better (T1.4), which keeps its
id and its bookmarks. A forced precompute deleted the row before regenerating until P11, outside both
guarantees. This gate holds the delete sites it finds to ``ALLOWED_SITES``, so a new one fails until
a review has checked it is FK-safe and lists it; what the scan cannot see is listed at the end.

Scope: every Python, SQL, shell and workflow file that can reach the production database, which is
the whole repository but the browser app (``frontend/``), the test homes (``backend/tests/``), git and
tool caches, and nested checkouts (an agent worktree under ``.claude/worktrees/``). That is the backend
(the app, its entrypoints, ``scripts/`` one-offs, ``evals/``, the migrations), ``ops/`` (the SQL that
``ops.yml`` runs), the root ``scripts/``, ``tasks/`` (operator SQL), ``.github`` and ``.claude``.

What counts, as (path from the repository root, enclosing function or ``<module>``, kind) -> count:

* ``delete`` (Python): a ``delete`` call that names the summaries where it decides what is deleted.
  Naming them is the ``Summary`` model (an import alias of it, ``<module>.Summary``), the
  ``Filing.summaries`` relationship (any ``.summaries`` attribute) or the string ``"summaries"``. The
  forms: ``query(Summary ...)...delete()``, ``delete(Summary)`` (sqlalchemy's, under any import alias,
  positional or ``table=``),
  ``Summary.__table__.delete()``, ``metadata.tables["summaries"].delete()``, ``session.delete(obj)``,
  and ``q.delete()`` on a bare name. A name, or its ``.__table__``, is followed to what the name is bound
  to in the same function or at module level (outside function and class bodies), directly or through
  a loop, ``with`` or comprehension over another name: ``summary = db.query(Summary)...first()``,
  ``q = db.query(Summary)...``, ``M = models.Summary`` (and ``M.__table__``), ``T = Summary.__table__``,
  ``for s in filing.summaries``. An alias of a session's ``delete`` (``remove = db.delete``) is followed.
* ``unresolved`` (Python, in a module that names ``Summary``, its table or ``.summaries``): a
  ``session.delete(obj)`` or a bare ``q.delete()`` whose target the scan cannot tie to a model (a
  parameter, an attribute, a helper's return value), and a ``.delete`` handed on uncalled
  (``run_in_threadpool(db.delete, row)``). A target bound to a query, lookup or row of another model
  (``progress = db.query(SummaryGenerationProgress)...``) is not counted.
* ``sql``: SQL that deletes ``summaries`` rows, in a Python string (a literal, a ``+`` of literals or an
  f-string's literal parts; docstrings are not code) or in a SQL, shell or workflow file read as text
  without its comments (``--`` and ``/* */`` in SQL, whole-line ``#`` elsewhere): ``DELETE FROM
  summaries``, ``TRUNCATE`` naming ``summaries`` or with ``CASCADE`` (which reaches it from
  ``filings``), ``DROP TABLE summaries`` and ``MERGE INTO summaries ... DELETE``, in any case, quoted
  or not, with or without a schema (``public.summaries``).
* ``cascade``: SQL that creates or alters ``summaries`` with ``ON DELETE CASCADE``, so a delete of the
  row it references would delete summaries.

Deletes by cascade, pinned by ``test_nothing_deletes_summaries_by_cascade``: no mapped relationship
into ``Summary`` cascades a delete or deletes orphans (``Filing.summaries`` saves only, so deleting a
filing, or a company whose filings go with it, fails on ``summaries.filing_id`` instead of deleting
the summary), ``summaries`` has no ``ondelete`` foreign key, and the retention purge has no
``Summary`` target. Account deletion removes the user's ``saved_summaries`` bookmarks, never a
summary (the same relationship check).

Out of reach, stated so nothing is overclaimed:

* a module that never names ``Summary``, its table or ``.summaries`` and deletes a row it was handed
  (a generic helper);
* a model, table or relationship chosen at run time (``getattr(models, name)``,
  ``getattr(filing, attr)``, ``delete(target.model)`` as the retention purge does, which is why its
  targets are pinned);
* a name bound in another function or module, or through an attribute (``self.q = ...``), or a model
  handed in as a parameter default (``def purge(db, model=Summary)``);
* a name rebound more than eight times in one scope, which is followed through its first eight bindings;
* a no-argument ``.delete()`` on an attribute or call the scan cannot resolve (``self.q.delete()``);
* SQL assembled from non-literals (``f"DELETE FROM {table}"``) or with ``%``, ``.format`` or
  ``str.join``, held in a psql variable, or in a statement object built elsewhere from such pieces;
* SQL quoted in Markdown, which is read, not run.

``test_the_scan_scores_every_planted_form`` scores the scan on planted deletes and look-alikes.
"""
import ast
import os
import re
from collections import Counter, deque
from collections.abc import Iterable, Iterator
from pathlib import Path

import pytest

REPO_DIR = Path(__file__).resolve().parents[3]
MODEL = "Summary"
TABLE = "summaries"

# Every place that can delete summaries rows -> how many times it does. A second delete inside an
# already-listed scope is a new site too.
ALLOWED_SITES = {
    # Admin reset-all: deletes the matched summaries, skipping bookmarked ones unless include_saved,
    # which deletes their bookmarks first (FK-safe by construction).
    ("backend/app/services/admin_summary_service.py", "delete_summaries", "delete"): 1,
    # Admin per-filing tools (DELETE /api/admin/filing/{id}/summary, /reset, POST
    # /filings/bulk-reset-stale): one summary each, deliberately. They do not clear bookmarks first,
    # so on PostgreSQL a bookmarked summary makes them raise and roll back, deleting nothing.
    ("backend/app/services/admin_filing_service.py", "delete_filing_summary", "delete"): 1,
    ("backend/app/services/admin_filing_service.py", "reset_filing", "delete"): 1,
    ("backend/app/services/admin_filing_service.py", "bulk_reset_stale_xbrl", "delete"): 1,
    # Operator one-off for one ticker and form: skips bookmarked summaries unless --include-saved,
    # which deletes their bookmarks first (FK-safe by construction).
    ("backend/scripts/reset_filing_summary.py", "main", "delete"): 1,
    # Deduplication before UNIQUE(filing_id): repoints the duplicates' bookmarks to the survivor first.
    ("backend/migrations/20260705_summary_filing_id_unique.sql", "<file>", "sql"): 1,
    # Not a summary: the Watchlist row _watched() returns (the module names Summary for its reads).
    ("backend/app/services/watchlist_service.py", "remove_company", "unresolved"): 1,
}

_SKIP_DIRS = {".git", "frontend", "node_modules", "__pycache__", ".cache", ".pytest_cache",
              ".ruff_cache", ".mypy_cache", ".next", ".venv", "venv"}
_SKIP_PATHS = {"backend/tests", ".claude/worktrees"}
_TEXT_SUFFIXES = {".sql", ".sh", ".yml", ".yaml"}

_T = rf'"?{TABLE}"?(?![\w"])'
_SQL_DELETE = re.compile(
    rf'\bDELETE\s+FROM\s+(?:ONLY\s+)?(?:"?\w+"?\.)?{_T}'
    rf'|\bTRUNCATE\b[^;]*?(?:(?<![\w."])(?:"?\w+"?\.)?{_T}|\bCASCADE\b)'
    rf'|\bDROP\s+TABLE\b[^;]*?(?<![\w."])(?:"?\w+"?\.)?{_T}'
    rf'|\bMERGE\s+INTO\s+(?:"?\w+"?\.)?{_T}[^;]*?\bDELETE\b',
    re.IGNORECASE,
)
_SQL_CASCADE = re.compile(
    rf'\b(?:CREATE|ALTER)\s+TABLE\s+(?:IF\s+(?:NOT\s+)?EXISTS\s+)?(?:ONLY\s+)?(?:"?\w+"?\.)?{_T}'
    rf'[^;]*?\bON\s+DELETE\s+CASCADE\b',
    re.IGNORECASE,
)
_SQL_COMMENTS = re.compile(r"--[^\n]*|/\*.*?\*/", re.DOTALL)


def _sql_sites(sql: str) -> list[str]:
    return ["sql"] * len(_SQL_DELETE.findall(sql)) + ["cascade"] * len(_SQL_CASCADE.findall(sql))


def text_sites(text: str, suffix: str) -> list[str]:
    """Kinds found in a SQL, shell or workflow file, read without its comments."""
    if suffix == ".sql":
        text = _SQL_COMMENTS.sub(" ", text)
    else:
        text = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    return _sql_sites(text)


def _docstring_ids(tree: ast.AST) -> set[int]:
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            first = node.body[0] if node.body else None
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
                    and isinstance(first.value.value, str):
                ids.add(id(first.value))
    return ids


def _folded(node: ast.AST) -> str | None:
    """A string literal, a ``+`` of them, or an f-string's literal parts; None for anything else."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(v.value if isinstance(v, ast.Constant) else " " for v in node.values)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _folded(node.left), _folded(node.right)
        return None if left is None or right is None else left + right
    return None


def _bindings(nodes: Iterable[ast.AST]) -> dict[str, list[ast.AST]]:
    """Each name bound among ``nodes`` -> what it is bound to (an assignment, a loop, a ``with``)."""
    bindings: dict[str, list[ast.AST]] = {}
    for inner in nodes:
        if isinstance(inner, (ast.Assign, ast.AnnAssign, ast.NamedExpr)):
            targets = inner.targets if isinstance(inner, ast.Assign) else [inner.target]
            for target in targets:
                for leaf in ast.walk(target):
                    if isinstance(leaf, ast.Name) and inner.value is not None:
                        bindings.setdefault(leaf.id, []).append(inner.value)
        elif isinstance(inner, (ast.For, ast.AsyncFor, ast.comprehension)):
            for leaf in ast.walk(inner.target):
                if isinstance(leaf, ast.Name):
                    bindings.setdefault(leaf.id, []).append(inner.iter)
        elif isinstance(inner, ast.withitem) and inner.optional_vars is not None:
            for leaf in ast.walk(inner.optional_vars):
                if isinstance(leaf, ast.Name):
                    bindings.setdefault(leaf.id, []).append(inner.context_expr)
    return bindings


def _module_level(tree: ast.Module) -> Iterator[ast.AST]:
    """Every node of a module outside its function and class bodies, in ``ast.walk``'s order, as a
    function's bindings are read."""
    todo: deque[ast.AST] = deque([tree])
    while todo:
        node = todo.popleft()
        yield node
        todo.extend(child for child in ast.iter_child_nodes(node)
                    if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)))


class _DeleteFinder(ast.NodeVisitor):
    def __init__(self, tree: ast.Module) -> None:
        self.sites: Counter[tuple[str, str]] = Counter()
        self._docstrings = _docstring_ids(tree)
        self._models = {MODEL}
        self._core_deletes = {"delete"}  # sqlalchemy's delete() and its import aliases
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name == MODEL:
                        self._models.add(alias.asname or MODEL)
                    if alias.name == "delete" and (node.module or "").startswith("sqlalchemy"):
                        self._core_deletes.add(alias.asname or "delete")
        source_names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        source_strings = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
        self._in_scope = bool(self._models & source_names) or any(
            re.search(rf"(?<!\w){TABLE}(?!\w)", s) for s in source_strings
        ) or any(isinstance(n, ast.Attribute) and n.attr == TABLE for n in ast.walk(tree))
        self._stack: list[str] = []
        self._bindings: list[dict[str, list[ast.AST]]] = [{}]
        self._handled: set[int] = set()

    # --- scopes and bindings -------------------------------------------------------------------
    def _scope(self) -> str:
        return ".".join(self._stack) or "<module>"

    def _visit_scope(self, node: ast.AST, name: str) -> None:
        self._stack.append(name)
        self._bindings.append(_bindings(ast.walk(node)))
        self.generic_visit(node)
        self._bindings.pop()
        self._stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_scope(node, node.name)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._visit_scope(node, node.name)

    def visit_Module(self, node: ast.Module) -> None:
        self._bindings = [_bindings(_module_level(node))]
        self.generic_visit(node)

    # --- what a node names ---------------------------------------------------------------------
    def _names_model(self, node: ast.AST) -> bool:
        """The model (an alias, ``<module>.Summary``), ``Filing.summaries`` or the table's name."""
        return any(
            (isinstance(n, ast.Name) and n.id in self._models)
            or (isinstance(n, ast.Attribute) and n.attr in (MODEL, TABLE))
            or (isinstance(n, ast.Constant) and n.value == TABLE)
            for n in ast.walk(node)
        )

    def _target(self, node: ast.AST, seen: frozenset[str] = frozenset()) -> str:
        """``summary``, ``other`` (a query, lookup or row of another model) or ``unknown``."""
        if self._names_model(node):
            return "summary"
        if isinstance(node, ast.Attribute) and node.attr == "__table__":  # M.__table__ is M's table
            return self._target(node.value, seen)
        if isinstance(node, ast.Name):
            if node.id in seen:
                return "unknown"
            values = [v for scope in reversed(self._bindings) for v in scope.get(node.id, [])][:8]
            if not values:
                return "unknown"
            kinds = {self._target(v, seen | {node.id}) for v in values}
            return "summary" if "summary" in kinds else "unknown" if "unknown" in kinds else "other"
        loaders = {"query", "get", "select", "scalar", "scalars", "first", "one", "one_or_none", "all"}
        for inner in ast.walk(node):
            if isinstance(inner, ast.Call):
                func = inner.func
                name = func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else ""
                if name in loaders and any(isinstance(a, ast.Name) and a.id[:1].isupper() for a in inner.args):
                    return "other"
                if name[:1].isupper():  # a row constructor of another model
                    return "other"
        return "unknown"

    def _receiver_query(self, node: ast.AST) -> ast.Call | None:
        """The ``query(...)``/``select(...)`` call a ``....delete()`` chain starts from, if any."""
        while isinstance(node, (ast.Call, ast.Attribute)):
            if isinstance(node, ast.Call):
                func = node.func
                name = func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else ""
                if name in {"query", "select"}:
                    return node
                node = func
            else:
                node = node.value
        return None

    def _session_alias(self, name: str) -> bool:
        values = [v for scope in reversed(self._bindings) for v in scope.get(name, [])]
        return any(isinstance(v, ast.Attribute) and v.attr == "delete" for v in values)

    # --- deletes -------------------------------------------------------------------------------
    def _instance_delete(self, call: ast.Call) -> None:
        if not call.args or isinstance(call.args[0], ast.Constant):
            return  # @router.delete("/path") and the like register a route; they delete nothing
        self._count(self._target(call.args[0]))

    def _count(self, kind: str) -> None:
        if kind == "summary":
            self.sites[(self._scope(), "delete")] += 1
        elif kind == "unknown" and self._in_scope:
            self.sites[(self._scope(), "unresolved")] += 1

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "delete":
            self._handled.add(id(func))
            query = self._receiver_query(func.value)
            if query is not None:  # query(<entities>)...delete(): the entities decide
                if any(self._target(arg) == "summary" for arg in query.args):
                    self.sites[(self._scope(), "delete")] += 1
            elif self._target(func.value) == "summary":  # Summary.__table__.delete(), M.__table__.delete()
                self.sites[(self._scope(), "delete")] += 1
            elif not node.args and isinstance(func.value, ast.Name):  # q = db.query(...); q.delete()
                self._count(self._target(func.value))
            else:  # session.delete(obj), sa.delete(Summary)
                self._instance_delete(node)
        elif isinstance(func, ast.Name) and func.id in self._core_deletes:
            table = node.args[0] if node.args else next((k.value for k in node.keywords if k.arg == "table"), None)
            if table is not None and self._target(table) == "summary":
                self.sites[(self._scope(), "delete")] += 1
        elif isinstance(func, ast.Name) and self._session_alias(func.id):
            self._instance_delete(node)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        if isinstance(node.value, ast.Attribute) and node.value.attr == "delete":
            self._handled.add(id(node.value))  # an alias; its calls are followed above
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr == "delete" and id(node) not in self._handled and self._in_scope:
            self.sites[(self._scope(), "unresolved")] += 1  # a delete handed on uncalled
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, str) and id(node) not in self._docstrings:
            for kind in _sql_sites(node.value):
                self.sites[(self._scope(), kind)] += 1

    def visit_JoinedStr(self, node: ast.JoinedStr) -> None:
        self._sql_expression(node)

    def visit_BinOp(self, node: ast.BinOp) -> None:
        if _folded(node) is not None:
            self._sql_expression(node)
        else:
            self.generic_visit(node)

    def _sql_expression(self, node: ast.AST) -> None:
        for kind in _sql_sites(_folded(node) or ""):
            self.sites[(self._scope(), kind)] += 1


def python_sites(source: str) -> Counter[tuple[str, str]]:
    tree = ast.parse(source)
    finder = _DeleteFinder(tree)
    finder.visit(tree)
    return finder.sites


def _in_scope_files():
    for root, dirs, files in os.walk(REPO_DIR):
        rel_root = Path(root).relative_to(REPO_DIR).as_posix()
        dirs[:] = sorted(
            d for d in dirs
            if d not in _SKIP_DIRS
            and (f"{rel_root}/{d}" if rel_root != "." else d) not in _SKIP_PATHS
            and not (Path(root, d) / ".git").exists()  # a nested checkout is another tree
        )
        for name in sorted(files):
            path = Path(root, name)
            if path.suffix == ".py" or path.suffix in _TEXT_SUFFIXES:
                yield path


def scan() -> Counter[tuple[str, str, str]]:
    found: Counter[tuple[str, str, str]] = Counter()
    for path in _in_scope_files():
        rel = path.relative_to(REPO_DIR).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        if path.suffix == ".py":
            for (scope, kind), count in python_sites(text).items():
                found[(rel, scope, kind)] += count
        else:
            for kind in text_sites(text, path.suffix):
                found[(rel, "<file>", kind)] += 1
    return found


def test_every_summary_delete_site_is_reviewed():
    found = dict(scan())
    unlisted = {key: count for key, count in found.items() if ALLOWED_SITES.get(key) != count}
    stale = {key: count for key, count in ALLOWED_SITES.items() if key not in found}
    assert not unlisted and not stale, (
        "A place that can delete summaries rows changed. A refresh regenerates in place under keep-better "
        "(generate_summary_background(..., force_regenerate=True)), never by deleting the row; a delete "
        "must be FK-safe against saved_summaries (lessons/arch-fk-safe-bulk-deletes.md) and reviewed into "
        f"ALLOWED_SITES.\nNew or changed: {unlisted}\nNo longer found: {stale}"
    )


def test_nothing_deletes_summaries_by_cascade():
    from app.models import Base, Summary
    from app.services.retention_service import purge_targets
    from app.utils.datetimes import utcnow

    for mapper in Base.registry.mappers:
        for relationship in mapper.relationships:
            if relationship.mapper.class_ is Summary:
                cascade = relationship.cascade
                assert not cascade.delete and not cascade.delete_orphan, (
                    f"{mapper.class_.__name__}.{relationship.key} would delete summaries by cascade"
                )
    assert all(fk.ondelete is None for fk in Summary.__table__.foreign_keys), \
        "a summaries foreign key with ondelete would delete or null summaries rows from its parent"
    assert all(target.model is not Summary for target in purge_targets(utcnow())), \
        "the retention purge deletes summaries"


PLANTED = '''"""DELETE FROM summaries -- a docstring is not code"""
from sqlalchemy import delete as sa_delete, text
from app.models import Summary as S, SummaryGenerationProgress, SavedSummary
import sqlalchemy as sa

ModuleAlias = S
AnnotatedAlias: type = S
TupleAlias, Unrelated = S, None
try:
    GuardedAlias = models.Summary
except ImportError:
    GuardedAlias = None

def query_delete(db, fid):
    db.query(S).filter(S.filing_id == fid).delete()

def core_delete(db):
    db.execute(sa_delete(S))
    db.execute(sa.delete(S).where(S.id == 1))

def core_delete_keyword(db):
    db.execute(delete(table=S))
    db.execute(sa_delete(table=ModuleAlias))

def core_delete_local_alias(db):
    M = S
    db.execute(delete(M))
    db.execute(sa_delete(M))

def core_delete_module_alias(db):
    db.execute(delete(ModuleAlias))
    db.execute(sa_delete(ModuleAlias))

def core_delete_module_bindings(db):
    db.execute(delete(AnnotatedAlias))
    db.execute(sa_delete(TupleAlias))
    db.execute(delete(GuardedAlias))

def table_delete(db):
    db.execute(models.Summary.__table__.delete())

def table_delete_local_alias(db):
    M = models.Summary
    db.execute(M.__table__.delete())
    db.execute(delete(M.__table__))
    db.execute(sa_delete(M.__table__))
    db.execute(sa.delete(M.__table__))

def table_delete_module_alias(db):
    db.execute(ModuleAlias.__table__.delete())
    db.execute(delete(ModuleAlias.__table__))
    db.execute(sa_delete(ModuleAlias.__table__))

def instance_delete(db, fid):
    summary = db.query(S).filter(S.filing_id == fid).first()
    db.delete(summary)

def loop_delete(db):
    rows = db.query(S).all()
    for row in rows:
        db.delete(row)

def aliased_delete(db, fid):
    remove = db.delete
    remove(db.get(S, fid))

def bound_query_delete(db, fid):
    q = db.query(S).filter(S.filing_id == fid)
    q.delete()

def aliased_model_and_table(db):
    M = models.Summary
    db.query(M).delete()
    T = S.__table__
    db.execute(T.delete())
    db.execute(Base.metadata.tables["summaries"].delete())

def relationship_delete(db, filing):
    db.delete(db.get(Filing, filing.id).summaries[0])
    for summary in filing.summaries:
        db.delete(summary)

def handed_on(db, row):
    run_in_threadpool(db.delete, row)

def unresolved(db, row, stmt):
    db.delete(row)
    stmt.delete()

def raw_sql(db):
    db.execute(text("DELETE FROM summaries WHERE id = 1"))
    db.execute(text("delete from " + "public.summaries"))
    db.execute(text(f"TRUNCATE {name} CASCADE"))

def look_alikes(db, fid):
    progress = db.query(SummaryGenerationProgress).filter(SummaryGenerationProgress.filing_id == fid).first()
    db.delete(progress)
    pending = db.query(SummaryGenerationProgress).filter(SummaryGenerationProgress.filing_id == fid)
    pending.delete()
    db.query(SavedSummary).filter(SavedSummary.user_id == 1).delete()
    db.execute(sa_delete(SummaryGenerationProgress))
    P = SummaryGenerationProgress
    db.execute(delete(P))
    db.execute(delete(P.__table__))
    db.execute(P.__table__.delete())
    db.execute(text("DELETE FROM saved_summaries WHERE id = 1"))
    note = "a delete would orphan the bookmark"

@router.delete("/x")
def route():
    return None
'''


def test_the_scan_scores_every_planted_form():
    assert python_sites(PLANTED) == Counter({
        ("query_delete", "delete"): 1,
        ("core_delete", "delete"): 2,
        ("core_delete_keyword", "delete"): 2,
        ("core_delete_local_alias", "delete"): 2,
        ("core_delete_module_alias", "delete"): 2,
        ("core_delete_module_bindings", "delete"): 3,
        ("table_delete", "delete"): 1,
        ("table_delete_local_alias", "delete"): 4,
        ("table_delete_module_alias", "delete"): 3,
        ("instance_delete", "delete"): 1,
        ("loop_delete", "delete"): 1,
        ("aliased_delete", "delete"): 1,
        ("bound_query_delete", "delete"): 1,
        ("aliased_model_and_table", "delete"): 3,
        ("relationship_delete", "delete"): 2,
        ("handed_on", "unresolved"): 1,
        ("unresolved", "unresolved"): 2,
        ("raw_sql", "sql"): 3,
    })
    # A module that never names the model or its table does not count what it cannot tie to one,
    # but one that walks the relationship does.
    assert python_sites("def helper(db, row):\n    db.delete(row)\n") == Counter()
    # A module-level name is followed through its first eight bindings in source order, as a function's are.
    rebound = "from app.models import Summary\nM = Summary\n" + "M = None\n" * 8 + "def f(db):\n    db.execute(delete(M))\n"
    assert python_sites(rebound) == Counter({("f", "delete"): 1})
    assert python_sites("def purge(db, filing):\n    for s in filing.summaries:\n        db.delete(s)\n") \
        == Counter({("purge", "delete"): 1})
    sql = """
        -- DELETE FROM summaries;   (a comment)
        /* TRUNCATE summaries */
        DELETE FROM saved_summaries WHERE id = 1;
        delete from "summaries" where id = 2;
        TRUNCATE TABLE filings CASCADE;
        TRUNCATE public.summaries;
        DROP TABLE IF EXISTS summaries;
        DROP TABLE "public"."summaries";
        DROP TABLE public.summaries_archive;
        ALTER TABLE summaries ADD CONSTRAINT fk FOREIGN KEY (filing_id) REFERENCES filings (id) ON DELETE CASCADE;
        CREATE TABLE notes (summary_id INTEGER REFERENCES summaries (id) ON DELETE CASCADE);
    """
    assert Counter(text_sites(sql, ".sql")) == Counter({"sql": 5, "cascade": 1})
    workflow = "# psql -c 'DELETE FROM summaries'\nrun: psql -c 'DELETE FROM summaries'\n"
    assert text_sites(workflow, ".yml") == ["sql"]


@pytest.mark.parametrize("tree", [
    "backend/app", "backend/scripts", "backend/migrations", "ops", "scripts", "tasks", ".github",
])
def test_the_scan_reads_every_tree_that_can_reach_the_database(tree):
    files = [p.relative_to(REPO_DIR).as_posix() for p in _in_scope_files()]
    assert any(f.startswith(f"{tree}/") for f in files)
    assert not any(f.startswith(("frontend/", "backend/tests/", ".claude/worktrees/")) for f in files)
