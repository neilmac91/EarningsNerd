"""Rule-12 gate: a filing's stored excerpt is written only by its two owners.

``FilingContentCache.critical_excerpt`` is the text read-time citation verification, the Risks
projection and Copilot read a stored summary against. A forced refresh that cleared it before its run
and put it back afterwards (P11, #1545) left a window in which an overlapping refresh captured a
rejected run's excerpt and wrote it back beside the kept summary (Codex 4365089688). The owners now:

* ``summary_generation_service.get_or_cache_excerpt``: caches the excerpt an unforced run builds
  (``persist=True``; a forced run passes ``persist=False`` and keeps it to itself);
* ``content_cache.upsert_content_cache``: finalize's write, in the same commit as the summary row it
  grounds (``replace_excerpt`` for a forced run, which stores its excerpt; ``clear_stale_excerpt`` for a
  forced precompute's rebuild, which clears the stale stored one when the run has none).

Scope: the files ``test_summary_delete_sites_allowlist.py`` reads (its ``_in_scope_files``, so the two
gates keep one scope), every Python, SQL, shell and workflow file that can reach the production
database: the whole repository but the browser app (``frontend/``), the test homes (``backend/tests/``),
git and tool caches, and nested checkouts. That is the backend (the app, its entrypoints ``main.py``
and ``task_worker_main.py``, ``scripts/`` one-offs, ``evals/``, the migrations), ``ops/``, the root
``scripts/``, ``tasks/``, ``.github`` and ``.claude``.

What counts, as (path from the repository root, enclosing top-level function or ``<module>``) -> count:

* in Python, an assignment to or ``del`` of a ``.critical_excerpt`` attribute (an augmented, annotated,
  tuple, ``for`` or ``with`` target included); a ``critical_excerpt=`` keyword to any call (the model
  under any name or import alias, a Core ``insert(...)``/``update(...)``/``__table__.update()``
  ``.values(...)``, a ``dict(...)`` handed to ``.update``, ``bulk_update_mappings`` or ``set_=``) except a
  call in ``READ_ONLY_CALLS`` (a ``SimpleNamespace`` snapshot copies the value it read; ``filter_by``
  filters on it); a dict-literal key that names the column (``X.critical_excerpt``,
  ``t.c["critical_excerpt"]`` or the string); a subscript assignment or ``del`` whose key names it the
  same way (``row["critical_excerpt"] = None``, ``vals[FCC.critical_excerpt] = None``); ``setattr``,
  ``delattr``, ``__setattr__``, ``__delattr__`` and SQLAlchemy's ``set_attribute`` or ``del_attribute``,
  and the call forms of a keyed store or ``del`` (``__setitem__``, ``__delitem__``, ``operator.setitem``,
  ``operator.delitem`` and ``setdefault``), given the string by position or by keyword
  (``set_attribute(cache, key="critical_excerpt", value=None)``); and a call, keyword or key of these
  forms inside an f-string's replacement field, which is code;
* SQL, in a Python string (a literal, a ``+`` of literals or an f-string's literal parts; docstrings are
  not code) or in a SQL, shell or workflow file read as text without its comments (``--`` and ``/* */``
  in SQL, whole-line ``#`` elsewhere), in any case, quoted or not, with or without a qualifier:
  ``critical_excerpt`` as a target of an ``UPDATE ... SET`` (an ``ON CONFLICT ... DO UPDATE SET`` and a
  ``MERGE``'s ``UPDATE SET`` included, alone or in a parenthesized target list), in the column list of an
  ``INSERT`` (a ``MERGE``'s included) or of a ``COPY ... FROM``, and an ``INSERT INTO`` or ``COPY ... FROM``
  of ``filing_content_cache`` with no column list, which writes every column.

Read-only code that names the column as a keyword, a dict key or a subscript key (a projection dict
``{"critical_excerpt": cache.critical_excerpt}``, a response schema's ``critical_excerpt=`` keyword,
``seen[cache.critical_excerpt] = True``) counts too, and fails loudly; its way out is a callee in
``READ_ONLY_CALLS`` (for a keyword only) or an ``ALLOWED`` entry, each with review.

Out of reach, stated so nothing is overclaimed:

* a column named by a value the scan cannot read as the literal: a variable or a constant
  (``setattr(cache, FIELD, None)``, ``{FIELD: None}``, ``row[FIELD] = None``, a ``.values(**kw)`` whose
  ``kw`` is built so), an element of a list or tuple (``dict.fromkeys(["critical_excerpt"])``,
  ``dict(zip(...))``), or, to an attribute or item writer, the column object or its key rather than the
  string (``vals.__setitem__(FCC.critical_excerpt, None)``, ``setattr(cache, FCC.critical_excerpt.key,
  None)``);
* an attribute or item writer bound or imported under another name (``from sqlalchemy.orm.attributes
  import set_attribute as sa``, ``w = setattr``), since the writers are matched by the callee's name;
* a Core insert given its values by position (``FCC.__table__.insert().values((1, None, None))``), which
  writes every column;
* a writer under a ``READ_ONLY_CALLS`` name (``from app.models import FilingContentCache as
  SimpleNamespace``), since that exemption is matched by the callee's name, and a ``SimpleNamespace``
  snapshot turned into a mapping and handed to a writer (``bulk_update_mappings(FCC, [vars(ns)])``,
  ``FCC(**vars(ns))``);
* SQL assembled from non-literals (``f"UPDATE ... SET {column} = NULL"``) or with ``%``, ``.format`` or
  ``str.join``, held in a psql variable, or quoted in Markdown, which is read, not run; and a statement
  split by a ``;`` inside one of its string literals (``SET markdown_content = 'a;b', critical_excerpt =
  NULL``), since the scan splits statements on every ``;``;
* DDL that rewrites the column (``DROP COLUMN``, a type change's ``USING``);
* deleting or replacing the whole cache row (``DELETE``, ``TRUNCATE``, ``session.delete(cache)``,
  ``filing.content_cache = None`` under its ``delete-orphan`` cascade); the admin filing reset deletes
  the summary in the same commit;
* a write from outside the scanned files (a test, an operator's ad-hoc psql session).

``test_the_scan_scores_every_planted_form`` scores the scan on planted writes and look-alikes.
"""
from __future__ import annotations

import ast
import functools
import re
from collections import Counter

import pytest

from tests.unit.test_summary_delete_sites_allowlist import (
    _SQL_COMMENTS,
    REPO_DIR,
    _docstring_ids,
    _folded,
    _in_scope_files,
)

FIELD = "critical_excerpt"
TABLE = "filing_content_cache"
# Calls whose ``critical_excerpt=`` keyword copies or filters on a value read, never a write: Copilot's
# snapshot, and a ``query.filter_by``.
READ_ONLY_CALLS = {"SimpleNamespace", "filter_by"}
# Calls that write the attribute or key their string argument names, matched by the callee's name.
_ATTR_WRITERS = {"setattr", "delattr", "__setattr__", "__delattr__", "set_attribute", "del_attribute"}
_ITEM_WRITERS = {"__setitem__", "__delitem__", "setitem", "delitem", "setdefault"}

ALLOWED = Counter({
    ("backend/app/services/content_cache.py", "upsert_content_cache"): 4,
    ("backend/app/services/summary_generation_service.py", "get_or_cache_excerpt"): 2,
})

_COL = rf'(?:"?\w+"?\.)?"?{FIELD}"?(?![\w"])'
_TBL = rf'(?:"?\w+"?\.)?"?{TABLE}"?(?![\w"])'
_SQL_UPDATE = re.compile(r"\bUPDATE\b", re.IGNORECASE)
_SQL_SET_TARGET = re.compile(rf'(?:\bSET\b|,)\s*(?:{_COL}|\([^()]*?(?<![\w."]){_COL}[^()]*\))\s*=', re.IGNORECASE)
_SUBQUERY = r"(?:SELECT|WITH|VALUES|TABLE)\b"
_SQL_COLUMN_LIST = re.compile(
    rf'\bINSERT\b(?:\s+INTO\s+(?:ONLY\s+)?[\w".]+(?:\s+AS\s+\w+)?)?\s*\((?!\s*{_SUBQUERY})([^()]*)\)'
    rf'|\bCOPY\s+[\w".]+\s*\(([^()]*)\)\s*FROM\b',
    re.IGNORECASE,
)
_SQL_EVERY_COLUMN = re.compile(
    rf'\bINSERT\s+INTO\s+(?:ONLY\s+)?{_TBL}(?:\s+AS\s+\w+)?\s*(?:\(\s*)?(?:{_SUBQUERY}|DEFAULT\b|OVERRIDING\b)'
    rf'|\bCOPY\s+{_TBL}\s+FROM\b',
    re.IGNORECASE,
)
_FIELD_NAME = re.compile(rf'(?<![\w."]){_COL}', re.IGNORECASE)


def sql_writes(sql: str) -> int:
    """How many writes of the column a piece of SQL makes (the forms in the module docstring)."""
    count = 0
    for statement in sql.split(";"):
        update = _SQL_UPDATE.search(statement)
        if update:
            count += len(_SQL_SET_TARGET.findall(statement, update.start()))
        count += sum(bool(_FIELD_NAME.search(a or b)) for a, b in _SQL_COLUMN_LIST.findall(statement))
        count += len(_SQL_EVERY_COLUMN.findall(statement))
    return count


def text_writes(text: str, suffix: str) -> int:
    """Writes in a SQL, shell or workflow file, read without its comments."""
    if suffix == ".sql":
        text = _SQL_COMMENTS.sub(" ", text)
    else:
        text = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    return sql_writes(text)


def _names_field(node: ast.AST) -> bool:
    return any(
        (isinstance(n, ast.Attribute) and n.attr == FIELD) or (isinstance(n, ast.Constant) and n.value == FIELD)
        for n in ast.walk(node)
    )


def _replacement_fields(node: ast.AST) -> list[ast.FormattedValue]:
    """The ``{...}`` fields of the f-strings a folded string is built from: code, read as code."""
    if isinstance(node, ast.JoinedStr):
        return [v for v in node.values if isinstance(v, ast.FormattedValue)]
    if isinstance(node, ast.BinOp):
        return _replacement_fields(node.left) + _replacement_fields(node.right)
    return []


def _callee(func: ast.AST) -> str:
    return func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else ""


def _writes(tree: ast.Module) -> list[tuple[str, int]]:
    docstrings = _docstring_ids(tree)
    found: list[tuple[str, int]] = []

    def visit(node: ast.AST, scope: str) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and scope == "<module>":
            scope = node.name
        writes = isinstance(getattr(node, "ctx", None), (ast.Store, ast.Del))
        if isinstance(node, ast.Attribute) and node.attr == FIELD and writes:
            found.append((scope, node.lineno))
        elif isinstance(node, ast.Subscript) and writes and _names_field(node.slice):
            found.append((scope, node.lineno))
        elif isinstance(node, ast.Call):
            callee = _callee(node.func)
            if callee not in READ_ONLY_CALLS:
                found.extend((scope, kw.value.lineno) for kw in node.keywords if kw.arg == FIELD)
            if callee in _ATTR_WRITERS or callee in _ITEM_WRITERS:
                given = [*node.args, *(kw.value for kw in node.keywords)]
                found.extend((scope, a.lineno) for a in given if isinstance(a, ast.Constant) and a.value == FIELD)
        elif isinstance(node, ast.Dict):
            found.extend((scope, key.lineno) for key in node.keys if key is not None and _names_field(key))
        elif isinstance(node, (ast.JoinedStr, ast.BinOp)) and (sql := _folded(node)) is not None:
            found.extend([(scope, node.lineno)] * sql_writes(sql))
            for field in _replacement_fields(node):  # its literal parts are read once, together
                visit(field, scope)
            return
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
            found.extend([(scope, node.lineno)] * sql_writes(node.value))
        for child in ast.iter_child_nodes(node):
            visit(child, scope)

    visit(tree, "<module>")
    return found


@functools.cache
def _scanned_files() -> tuple:
    return tuple(_in_scope_files())


def scan() -> Counter:
    sites: Counter = Counter()
    for path in _scanned_files():
        rel = path.relative_to(REPO_DIR).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        if path.suffix == ".py":
            for scope, _line in _writes(ast.parse(text, filename=rel)):
                sites[(rel, scope)] += 1
        else:
            sites[(rel, "<file>")] += text_writes(text, path.suffix)
    return +sites


def test_only_the_two_owners_write_the_stored_excerpt():
    sites = scan()
    assert sites == ALLOWED, (
        "a new or changed writer of FilingContentCache.critical_excerpt; a forced run keeps its excerpt "
        f"private until finalize stores it with the summary it grounds. New or changed: {dict(sites - ALLOWED)}; "
        f"gone: {dict(ALLOWED - sites)}"
    )


PLANTED = '''"""UPDATE filing_content_cache SET critical_excerpt = NULL -- a docstring is not code"""
import operator
import types
from types import SimpleNamespace
from sqlalchemy import insert, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import attributes
from sqlalchemy.orm.attributes import del_attribute
from app import models
from app.models import FilingContentCache as FCC

def attribute_store(cache, stored):
    cache.critical_excerpt = stored

def attribute_tuple_and_augmented(cache, stored):
    stored, cache.critical_excerpt = cache.critical_excerpt, None
    cache.critical_excerpt += "x"

def attribute_annotated_loop_with_and_del(cache, rows):
    cache.critical_excerpt: str = "x"
    for cache.critical_excerpt in rows:
        pass
    with open("x") as cache.critical_excerpt:
        pass
    del cache.critical_excerpt

def model_under_any_name(stored):
    FCC(filing_id=1, critical_excerpt=stored)
    models.FilingContentCache(filing_id=1, critical_excerpt=stored)

def core_update_values(db, fid):
    db.execute(update(FCC).where(FCC.filing_id == fid).values(critical_excerpt=None))

def core_insert_values(db, fid, stored):
    db.execute(insert(FCC).values(filing_id=fid, critical_excerpt=stored))

def table_update_values(db):
    db.execute(FCC.__table__.update().values(critical_excerpt=None))

def on_conflict_set(db, stored):
    stmt = pg_insert(FCC).values({"filing_id": 1})
    db.execute(stmt.on_conflict_do_update(index_elements=["filing_id"], set_=dict(critical_excerpt=stored)))

def query_update_dict_call(q):
    q.update(dict(critical_excerpt=None))

def bulk_mappings(db):
    db.bulk_update_mappings(FCC, [dict(filing_id=1, critical_excerpt=None)])

def dict_keys(q, stored, t):
    q.update({FCC.critical_excerpt: stored})
    q.update({"critical_excerpt": stored})
    q.update({t.c["critical_excerpt"]: stored})

def subscript_store(row):
    row["critical_excerpt"] = None
    del row["critical_excerpt"]

def subscript_keyed_by_the_column(vals, t):
    vals[FCC.critical_excerpt] = None
    vals[t.c.critical_excerpt] = None
    del vals[t.c["critical_excerpt"]]

def literal_setattr(cache):
    setattr(cache, "critical_excerpt", None)
    delattr(cache, "critical_excerpt")
    object.__setattr__(cache, "critical_excerpt", None)

def literal_set_attribute(cache):
    attributes.set_attribute(cache, "critical_excerpt", None)
    del_attribute(cache, "critical_excerpt")

def attribute_writer_given_the_string_by_keyword(cache):
    attributes.set_attribute(cache, key="critical_excerpt", value=None)
    del_attribute(cache, key="critical_excerpt")

def dunder_item_writers(vals):
    vals.__setitem__("critical_excerpt", None)
    vals.__delitem__("critical_excerpt")

def operator_item_writers(vals):
    operator.setitem(vals, "critical_excerpt", None)
    operator.delitem(vals, "critical_excerpt")

def setdefault_key(vals):
    vals.setdefault("critical_excerpt", None)

def write_inside_an_f_string(db, fid):
    log = f"cleared {db.execute(update(FCC).where(FCC.filing_id == fid).values(critical_excerpt=None))}"

def sql_in_python(db):
    db.execute(text("UPDATE filing_content_cache SET critical_excerpt = NULL WHERE filing_id = 1"))
    db.execute(text("update filing_content_cache set " + "markdown_content = NULL, critical_excerpt = NULL"))
    db.execute(text(f"INSERT INTO filing_content_cache (filing_id, critical_excerpt) VALUES ({1}, NULL)"))

def look_alikes(db, cache, row):
    excerpt = cache.critical_excerpt
    excerpt = getattr(cache, "critical_excerpt", None)
    excerpt = row["critical_excerpt"]
    excerpt = row.get("critical_excerpt")
    excerpt = operator.getitem(row, "critical_excerpt")
    snapshot = SimpleNamespace(critical_excerpt=excerpt)
    snapshot = types.SimpleNamespace(critical_excerpt=excerpt)
    fields = {"cache_excerpt": cache.critical_excerpt}
    fields = {"field": "content_cache.critical_excerpt (inputs.source_text)"}
    db.query(FCC).filter(FCC.critical_excerpt.is_(None)).all()
    db.query(FCC).filter_by(critical_excerpt=None).all()
    db.execute(text("SELECT critical_excerpt FROM filing_content_cache WHERE critical_excerpt = 'x'"))
    db.execute(text("UPDATE filing_content_cache SET markdown_content = NULL WHERE critical_excerpt = 'x'"))
    db.execute(text("INSERT INTO notes (body) SELECT critical_excerpt FROM filing_content_cache"))
    note = "a forced run never sets critical_excerpt before its summary; an UPDATE reads it"
'''


def test_the_scan_scores_every_planted_form():
    assert Counter(scope for scope, _ in _writes(ast.parse(PLANTED))) == Counter({
        "attribute_store": 1,
        "attribute_tuple_and_augmented": 2,
        "attribute_annotated_loop_with_and_del": 4,
        "model_under_any_name": 2,
        "core_update_values": 1,
        "core_insert_values": 1,
        "table_update_values": 1,
        "on_conflict_set": 1,
        "query_update_dict_call": 1,
        "bulk_mappings": 1,
        "dict_keys": 3,
        "subscript_store": 2,
        "subscript_keyed_by_the_column": 3,
        "literal_setattr": 3,
        "literal_set_attribute": 2,
        "attribute_writer_given_the_string_by_keyword": 2,
        "dunder_item_writers": 2,
        "operator_item_writers": 2,
        "setdefault_key": 1,
        "write_inside_an_f_string": 1,
        "sql_in_python": 3,
    })
    sql = """
        -- UPDATE filing_content_cache SET critical_excerpt = NULL;   (a comment)
        /* INSERT INTO filing_content_cache (filing_id, critical_excerpt) VALUES (1, NULL); */
        UPDATE filing_content_cache SET critical_excerpt = NULL WHERE filing_id = 1;
        update public.filing_content_cache as c set markdown_content = NULL, "critical_excerpt" = NULL;
        UPDATE filing_content_cache SET (risk_source_text, c.critical_excerpt) = (NULL, NULL);
        INSERT INTO filing_content_cache (filing_id, critical_excerpt) VALUES (1, 'x')
            ON CONFLICT (filing_id) DO UPDATE SET critical_excerpt = EXCLUDED.critical_excerpt;
        INSERT INTO filing_content_cache VALUES (1, 'x');
        INSERT INTO "public"."filing_content_cache" SELECT * FROM cache_backup;
        MERGE INTO filing_content_cache t USING src s ON t.filing_id = s.filing_id
            WHEN MATCHED THEN UPDATE SET critical_excerpt = s.excerpt
            WHEN NOT MATCHED THEN INSERT (filing_id, critical_excerpt) VALUES (s.filing_id, s.excerpt);
        COPY filing_content_cache (filing_id, critical_excerpt) FROM STDIN;
        \\copy filing_content_cache FROM 'cache.csv' CSV;
        SELECT critical_excerpt FROM filing_content_cache WHERE critical_excerpt = 'x';
        UPDATE filing_content_cache SET markdown_content = critical_excerpt WHERE critical_excerpt = 'x';
        INSERT INTO notes (body) SELECT critical_excerpt FROM filing_content_cache;
        COPY filing_content_cache (filing_id, critical_excerpt) TO STDOUT;
        COPY filing_content_cache TO STDOUT;
        INSERT INTO filing_content_cache_archive SELECT * FROM filing_content_cache;
    """
    assert text_writes(sql, ".sql") == 11
    workflow = (
        "# psql -c 'UPDATE filing_content_cache SET critical_excerpt = NULL'\n"
        "run: psql -c \"UPDATE filing_content_cache SET critical_excerpt = NULL\"\n"
    )
    assert text_writes(workflow, ".yml") == 1


@pytest.mark.parametrize("path", [
    "backend/app", "backend/main.py", "backend/task_worker_main.py", "backend/scripts", "backend/evals",
    "backend/migrations", "ops", "scripts", "tasks", ".github/workflows",
])
def test_the_scan_reads_every_place_that_can_reach_the_database(path):
    files = [p.relative_to(REPO_DIR).as_posix() for p in _scanned_files()]
    assert any(f == path or f.startswith(f"{path}/") for f in files)
    assert not any(f.startswith(("frontend/", "backend/tests/", ".claude/worktrees/")) for f in files)
