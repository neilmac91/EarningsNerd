"""Structural gate: only refresh-token rotation writes ``RefreshToken.replaced_by_id``.

``refresh_token_service.rotate_refresh_token`` revokes every live token of the user when a revoked
token with ``replaced_by_id`` set is presented, reading the link as proof that the token was rotated
away and that someone else holds its successor. That reading is sound only while rotation is the one
writer. A revocation path or a session transfer that set the link would send its tokens down the
theft sweep again, which is the bug ``test_refresh_token_revocation_kinds.py`` pins for the writers
that exist today.

A writer can reach the column in more spellings than a write-only scan sees: an alias
(``successor = RefreshToken.replaced_by_id`` then ``.update({successor: value})``), ``setattr`` or
``getattr`` with the name, ``sqlalchemy.column("replaced_by_id")``, a name computed at run time
(``setattr(token, "_".join(("replaced", "by", "id")), value)``), or a migration
(``UPDATE refresh_tokens SET replaced_by_id = ...``). So this gate counts every MENTION of the column
in every Python, SQL, shell and workflow file that can reach the production database: the whole
repository but the browser app (``frontend/``), git and tool caches, and the test homes. That is the
backend (the app, the entrypoints, ``scripts/`` one-offs, the migrations), ``ops/`` (the detection and
capacity SQL that ops.yml runs with the app's credentials), the root ``scripts/``, ``tasks/`` (SQL
written to be run against production by hand), ``.github`` and ``.claude``; a new folder is scanned by
default, while a nested checkout or worktree (an agent worktree under ``.claude/worktrees/``) is another
tree and is not. It counts reads too, as (path from the
repository root, enclosing function or class, kind) with how many times each occurs, and holds that
equal to ``ALLOWED_MENTIONS``: any new mention fails until it is reviewed and listed, including a
second one inside an already-listed scope.

In Python a mention is an attribute access (``read`` or ``write``), the column as a key of a mapping
literal or an ``ordered_values`` pair (``key``: the shape of a row write), a bare name (``definition``
when assigned, ``name`` when read), a keyword argument, or a string or bytes literal outside a
docstring that contains the name in any case (SQL folds unquoted names), whether a literal or an
expression built only from literals (concatenation, ``%`` with a tuple or a mapping, an f-string,
``str.join``, ``str.format`` with positional or keyword arguments, and the case and replace methods are
folded). Comments and docstrings are not code and are not counted. A migration, shell script or
workflow is read as text: every occurrence of the name, in any case and comments included, is a
``text`` mention, and the whole file is one scope. SQL is read without its ``--`` and ``/* */``
comments (a ``'--'`` inside a string is kept), a shell script or workflow without its whole-line ``#``
comments. Kinds are syntactic: a ``read``, ``string`` or
``text`` can be part of a write.

The link is ``ON DELETE SET NULL``, so deleting a successor writes NULL into its predecessor's link,
and the theft check then reads the predecessor as merely revoked. So in every file in scope (below),
each delete is a ``delete`` mention: a ``delete`` or ``Delete`` call (``delete(RefreshToken)``,
``query.delete()``, ``db.delete(token)``, under an import or assignment alias, or ``db.delete`` handed on
as a value), and SQL, in a string or a migration (a migration's comments aside), that runs ``DELETE FROM
refresh_tokens`` (a CTE's too), a ``TRUNCATE`` listing the table, or ``MERGE INTO refresh_tokens ...
THEN DELETE``; a Python string is matched raw, comments included, so a CLI ``--flag`` before the SQL
hides nothing. ``User.refresh_tokens`` is ``delete-orphan``, so a token dropped from it is deleted at
flush, and each such drop is a ``delete`` too: a member-dropping method of the collection (``remove``,
``pop``, ``clear``, ``discard``, ``popitem``, ``__delitem__`` and the like), called or handed on, on
``x.refresh_tokens``, a name bound to it or ``getattr(x, "refresh_tokens")``; an item stored or deleted
(``user.refresh_tokens[:] = keep``, ``del user.refresh_tokens[0]``); the collection assigned, augmented
(an adding ``+=`` too) or deleted; a ``user`` attribute stored or deleted (``t.user = None`` cuts the
token loose, and so may a user that is None at run time); either name set or deleted by ``setattr`` and
the like; and a ``merge`` call, since merging a detached user deletes the tokens its copy lacks. A read of
the collection (``list(user.refresh_tokens)``, ``append``, ``any``) drops nothing. A Python delete
counts whatever it removes, so the reviewed list carries the OAuth deletes of the modules that import
``refresh_token_service``; a decorator's own callee, such as ``@router.delete(...)``, deletes nothing. A
user's whole chain goes with the user (``ON DELETE CASCADE``), so SQL that deletes users is not a delete
mention.

A name built from anything else (a variable, a loop over the table's columns, a row copied from
another) cannot be read off the source, so every module in scope, one that names the model, its table,
``User.refresh_tokens`` or the column, or imports a refresh-token module (``refresh_token_service``
hands its callers token rows), also has each place a column could be chosen at run time counted as a
``dynamic`` mention:
- a call that takes an attribute name (``setattr``, ``getattr``, ``delattr``, ``hasattr``,
  ``__setattr__``, ``object.__setattr__``, ``set_attribute``, ``set_committed_value``) with a name that
  is not spelled out, positionally or by keyword, or with ``*args``; such a function handed on as a
  value (``partial(setattr, t)``, ``put = setattr``), though not a parameter or local of the same
  function, or of a function enclosing it (a closure), that only shares its name;
- raw SQL or a column built from a non-literal (``text``, ``column``, ``literal_column``,
  ``exec_driver_sql``, under any import alias); a SQL write assembled at run time wherever it is built
  (``stmt = f"UPDATE ... SET {col} = NULL"`` then ``cursor.execute(stmt)``), or with a placeholder a
  caller fills in (``sql.SQL("UPDATE ... SET {} = NULL").format(sql.Identifier(col))``), or from
  pieces (a ``"UPDATE refresh_tokens SET "`` or ``["UPDATE refresh_tokens SET"]`` that the code grows
  with ``+=``, ``x = x + ...`` or ``append``, joined from a list, or handed to psycopg2's ``sql.SQL`` /
  ``Composed``); a SQL write is a statement that opens with its verb, after a CTE, a comment or an
  earlier statement, so prose is not one (unless it follows a ``;``), and a ``.format`` that folds is
  static; and any other
  string assembled at run time straight into ``execute``;
- a ``**mapping`` argument;
- row data, positional or keyword (``params``, ``parameters``, ``mappings``, ``values``, ``set_``),
  handed to ``update``, ``values``, ``ordered_values``, ``execute``, ``executemany``,
  ``on_conflict_do_update`` or a ``bulk_*_mappings`` call, unless it is a literal mapping (or list of
  them) whose keys are literals or attributes of an imported CapWords class such as
  ``RefreshToken.revoked_at``; so ``.update(carried)``, ``{col.name: v}``, ``dict(row)``, a module
  constant (``{fields.LINK: v}``) and a constant the module picked from the columns all count, and so
  does any other mapping argument with such a key;
- a by-name lookup in ``.c``, ``.columns``, ``.attrs``, ``.all_orm_descriptors`` and the like,
  directly, through ``.get`` or through a name bound to one.
In a text file that names the table or the column, each ``EXECUTE`` in SQL but a trigger's ``EXECUTE
FUNCTION``, and each psql ``\\gexec``, is ``dynamic``; in a shell script or workflow, gcloud's ``jobs
execute`` and an ``--execute`` flag are not.

Out of reach, planted as named gaps (``test_the_named_gaps_stay_out_of_reach`` and
``test_the_text_scan_gaps_stay_out_of_reach``): a module out of scope that writes an attribute by a
name it did not build from literals, deletes or merges a model it was handed, or cuts a token from its
user (a generic helper); a name assembled by code the folder does not evaluate; a whole-row copy or
load that moves every column without naming one (``insert(...).from_select`` over the table's columns, ``make_transient`` and
re-adding the row, ``INSERT INTO refresh_tokens SELECT *``, a positional ``INSERT ... VALUES``, ``COPY``
or psql ``\\copy``); the delete-orphan collection handed to a helper that drops its members; a write
through an ORM synonym of the column; a psql variable standing in for the column; and dynamic SQL in
a file that builds both the table's and the column's names; and SQL quoted in a Markdown runbook,
which is read, not run (``test_the_scan_reads_every_tree_that_can_reach_the_database``). Swapping one mention for another of the same kind inside one scope keeps the
counts equal and is not seen either.
``test_the_mention_scan_scores_every_planted_form`` and ``test_the_text_scan_scores_every_planted_form``
score the scan on planted bypasses and look-alikes.
"""
import ast
import os
import re
from collections import Counter
from pathlib import Path

import pytest

REPO_DIR = Path(__file__).resolve().parents[3]
COLUMN = "replaced_by_id"
TABLE = "refresh_tokens"

# Every mention of the successor link, as (path from the repository root, scope, kind) -> how many
# times. The count matters: a second write inside an already-listed scope is a new mention too.
# Rotation is the only writer; its own presence check is the only reader; the model defines the column.
ALLOWED_MENTIONS = {
    ("backend/app/services/refresh_token_service.py", "rotate_refresh_token", "read"): 1,
    ("backend/app/services/refresh_token_service.py", "rotate_refresh_token", "write"): 1,
    ("backend/app/models/refresh_token.py", "RefreshToken", "definition"): 1,
    # Dynamic-name sinks in a module that names RefreshToken (the model registry imports it): they
    # read Filing's two URL columns by a name from _FILING_URL_FIELDS (getattr, and the attribute
    # state lookup) and cannot reach refresh_tokens.
    ("backend/app/models/__init__.py", "_validate_filing_url", "dynamic"): 1,
    ("backend/app/models/__init__.py", "validate_filing_before_update", "dynamic"): 2,
    # The link is ON DELETE SET NULL, so a delete writes it. The purge deletes expired and revoked
    # tokens in ascending id order, so a predecessor always goes before its successor and keeps its
    # link (test_retention_purge.py pins the order).
    ("backend/app/services/retention_service.py", "_purge", "delete"): 1,
    # Modules that import refresh_token_service are in scope (it could hand them a token row to delete);
    # these deletes remove OAuth rows: expired OAuthState rows, a consumed OAuthState, an OAuthAccount.
    ("backend/app/services/oauth_account_service.py", "store_oauth_state", "delete"): 1,
    ("backend/app/services/oauth_account_service.py", "consume_oauth_state", "delete"): 1,
    ("backend/app/services/oauth_account_service.py", "unlink_oauth_provider", "delete"): 1,
    # The table's migration defines the column, with that ON DELETE SET NULL.
    ("backend/migrations/20260613_create_refresh_tokens.sql", "<file>", "text"): 1,
}


def _docstring_ids(tree: ast.AST) -> set[int]:
    """ids of the string constants that are docstrings (module, class or function)."""
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            first = node.body[0] if node.body else None
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
                    and isinstance(first.value.value, str):
                ids.add(id(first.value))
    return ids


class _ColumnMentionFinder(ast.NodeVisitor):
    """Collect (scope, kind) for every mention of ``replaced_by_id``, and, in a module that names the
    model or its table (``in_scope``), for every dynamic-name sink."""

    def __init__(self, docstrings: set[int], *, in_scope: bool, module: "_Module") -> None:
        self.mentions: Counter[tuple[str, str]] = Counter()
        self._docstrings = docstrings
        self._in_scope = in_scope
        self._module = module
        self._called: set[int] = set()
        self._keys: set[int] = set()
        self._inner: set[int] = set()
        self._locals: list[set[str]] = []
        self._decorators: set[int] = set()
        self._stack: list[str] = []

    def _scoped(self, node: ast.AST, name: str) -> None:
        self._stack.append(name)
        self.generic_visit(node)
        self._stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        # A decorator registers the function (``@router.delete("/connections/{provider}")``); its own
        # callee deletes nothing, though its arguments are code like any other.
        for decorator in node.decorator_list:
            self._decorators.update({id(decorator), id(getattr(decorator, "func", decorator))})
        self._locals.append(_function_locals(node))
        self._scoped(node, node.name)
        self._locals.pop()

    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]

    def visit_Lambda(self, node: ast.Lambda) -> None:
        self._locals.append({arg.arg for arg in ast.walk(node.args) if isinstance(arg, ast.arg)})
        self.generic_visit(node)
        self._locals.pop()

    def _shadowed(self, name: str) -> bool:
        """A parameter or local of an enclosing function (a closure sees them too) that only shares a
        sink's name."""
        return any(name in frame for frame in self._locals) and name not in self._module.aliases

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._scoped(node, node.name)

    def _record(self, kind: str) -> None:
        self.mentions[(self._scope(), kind)] += 1

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr == COLUMN:
            self._record("key" if id(node) in self._keys else "read" if isinstance(node.ctx, ast.Load) else "write")
        # ``db.delete`` handed on as a value (``map(db.delete, tokens)``, ``drop = db.delete``) deletes
        # where the call cannot be seen.
        if (self._in_scope and node.attr in _DELETERS and isinstance(node.ctx, ast.Load)
                and id(node) not in self._called and id(node) not in self._decorators):
            self._record("delete")
        # User.refresh_tokens is delete-orphan: a token dropped from it is deleted at flush, and deleting a
        # successor clears its predecessor's link like any other delete.
        if self._in_scope and _orphans(node, self._module):
            self._record("delete")
        self.generic_visit(node)

    def visit_Dict(self, node: ast.Dict) -> None:
        # The column as a mapping key is the shape of a row write (``.update({RefreshToken.x: v})``), so
        # it counts as ``key``, never as the read or string it looks like.
        self._keys.update(id(key) for key in node.keys if key is not None)
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id == COLUMN:
            self._record("definition" if isinstance(node.ctx, ast.Store) else "name")
        # A sink handed on as a value (``partial(setattr, t)``, ``map(setattr, ...)``, ``put = setattr``)
        # is called where its name argument cannot be seen. A parameter or local that only shares a
        # sink's name (``def f(text): text.strip()``) is not the sink.
        if self._in_scope and isinstance(node.ctx, ast.Load) and id(node) not in self._called and not self._shadowed(node.id):
            sink = self._module.sink(node.id)
            if sink in _SINK_NAMES:
                self._record("dynamic")
            elif sink in _DELETERS:
                self._record("delete")

    def visit_keyword(self, node: ast.keyword) -> None:
        if node.arg == COLUMN:
            self._record("keyword")
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        value = _fold(node)
        if value is None or id(node) in self._docstrings:
            return
        self._string(node, value)
        # SQL a caller fills in later (``sql.SQL("UPDATE refresh_tokens SET {} = NULL").format(...)``).
        if (self._in_scope and id(node) not in self._inner and _PLACEHOLDER.search(value)
                and _is_sql_write(value)):
            self._record("dynamic")

    def _built_string(self, node: ast.expr) -> None:
        folded = _fold(node)
        if folded is not None:
            self._string(node, folded)

    def _string(self, node: ast.expr, value: str) -> None:
        if COLUMN in value.lower():  # SQL folds unquoted names: "SET REPLACED_BY_ID = NULL" writes it
            self._record("key" if id(node) in self._keys else "string")
        deletes = len(_TABLE_DELETE.findall(value)) if self._in_scope else 0
        if deletes:  # raw SQL that deletes refresh-token rows
            self.mentions[(self._scope(), "delete")] += deletes

    def _scope(self) -> str:
        return self._stack[-1] if self._stack else "<module>"

    def _sql_fragment(self, node: ast.AST | None) -> None:
        # A SQL write that is only a piece (``"UPDATE refresh_tokens SET "`` extended with ``+=``, or
        # handed to psycopg2's ``sql.SQL`` / ``Composed``) has its column added at run time.
        if (self._in_scope and isinstance(node, ast.Constant) and isinstance(node.value, str)
                and id(node) not in self._inner and _is_sql_write(node.value)):
            self._record("dynamic")
            self._inner.add(id(node))

    def visit_Assign(self, node: ast.Assign | ast.AnnAssign) -> None:
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if node.value is not None and any(ast.unparse(target) in self._module.extended for target in targets):
            # A start the code grows later: "UPDATE ... SET " or ["UPDATE refresh_tokens SET"].
            for piece in (node.value.elts if isinstance(node.value, (ast.List, ast.Tuple)) else [node.value]):
                self._sql_fragment(piece)
        self.generic_visit(node)

    visit_AnnAssign = visit_Assign  # type: ignore[assignment]

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self._sql_fragment(node.value)
        if self._in_scope and isinstance(node.target, ast.Name) and node.target.id in self._module.collections:
            self._record("delete")  # tokens = user.refresh_tokens; tokens -= gone
        self.generic_visit(node)

    def _run_time_sql(self, node: ast.expr) -> None:
        # SQL assembled at run time names its column where the source cannot show it, wherever the
        # string goes next (``stmt = f"UPDATE ... SET {col} = NULL"`` then ``cursor.execute(stmt)``).
        if (self._in_scope and id(node) not in self._inner and _sql_built_at_run_time(node)
                and _is_sql_write(_literal_text(node))):
            self._record("dynamic")
            self._inner.update(id(inner) for inner in ast.walk(node))

    def visit_BinOp(self, node: ast.BinOp) -> None:
        self._built_string(node)
        self._run_time_sql(node)
        self.generic_visit(node)

    def visit_JoinedStr(self, node: ast.JoinedStr) -> None:
        self._built_string(node)
        self._run_time_sql(node)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        self._called.add(id(node.func))
        callee = _callee(node, self._module)
        if callee == "ordered_values":  # (column, value) pairs
            self._keys.update(id(pair.elts[0]) for pair in node.args if isinstance(pair, ast.Tuple) and pair.elts)
        if _fold(node) is not None:  # "UPDATE users SET {} = 1".format("x") is static SQL
            self._inner.update(id(inner) for inner in ast.walk(node))
        if callee in _SQL_COMPOSERS:
            for arg in node.args:
                for part in (arg.elts if isinstance(arg, (ast.List, ast.Tuple)) else [arg]):
                    self._sql_fragment(part)
        self._built_string(node)
        self._run_time_sql(node)
        if self._in_scope and _dynamic_sink(node, self._module):
            self._record("dynamic")
        # The link is ON DELETE SET NULL: deleting a successor writes NULL into its predecessor's link,
        # so in a module that names the model every ``delete`` (``delete(RefreshToken)``,
        # ``query.delete()``, ``db.delete(token)``, ``Delete(table)``) is a writer to review.
        if self._in_scope and callee in _DELETERS and id(node) not in self._decorators:
            self._record("delete")
        if (self._in_scope and callee in _ATTRIBUTE_SETTERS
                and _spelled_name(node, callee) in (_COLLECTION, _BACK_REFERENCE)):
            self._record("delete")  # setattr(user, "refresh_tokens", keep), setattr(t, "user", None)
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        if self._in_scope and _keyed_collection(node.value, self._module) and _fold(node.slice) is None:
            self._record("dynamic")
        if self._in_scope and not isinstance(node.ctx, ast.Load) and _token_collection(node.value, self._module):
            self._record("delete")  # user.refresh_tokens[:] = keep, del user.refresh_tokens[0]
        self.generic_visit(node)


_FOLDED_METHODS = {"lower", "upper", "casefold", "strip", "lstrip", "rstrip", "replace", "format", "join"}
# Calls that take an attribute or column NAME, and the position of that name among the arguments
# (``object.__setattr__(t, name, v)`` and ``set_attribute(t, name, v)`` carry it second).
_NAME_FUNCTIONS = {"setattr": 1, "getattr": 1, "delattr": 1, "hasattr": 1, "__setattr__": 0, "__delattr__": 0,
                   "__getattribute__": 0, "set_attribute": 1, "set_committed_value": 1, "flag_modified": 1}
_SQL_FUNCTIONS = {"text", "column", "literal_column", "exec_driver_sql"}
# Collections a column or attribute is looked up in by name (``RefreshToken.__table__.c[key]``,
# ``.c.get(key)``, ``__mapper__.all_orm_descriptors[key]``), directly or through a name bound to one.
_KEYED_ATTRS = {"c", "columns", "attrs", "column_attrs", "all_orm_descriptors", "relationships", "synonyms",
                "__dict__"}
# Session and statement methods that write rows from a mapping or a list of mappings, and how many
# leading positional arguments are not row data (the statement, or the mapper of a bulk call).
_ROW_WRITERS = {"update": 0, "values": 0, "execute": 1, "executemany": 1, "bulk_update_mappings": 1,
                "bulk_insert_mappings": 1, "on_conflict_do_update": 0, "on_conflict_do_nothing": 0}


def _fold(node: ast.AST) -> str | None:
    """The string an expression built only from string literals evaluates to, else None."""
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bytes):
            return node.value.decode("latin-1")
        return node.value if isinstance(node.value, str) else None
    if isinstance(node, ast.JoinedStr):
        parts = []
        for value in node.values:
            inner = value.value if isinstance(value, ast.FormattedValue) else value
            if isinstance(value, ast.FormattedValue) and (value.conversion != -1 or value.format_spec):
                return None
            folded = _fold(inner)
            if folded is None:
                return None
            parts.append(folded)
        return "".join(parts)
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mod)):
        left = _fold(node.left)
        if left is None:
            return None
        if isinstance(node.op, ast.Add):
            right = _fold(node.right)
            return None if right is None else left + right
        if isinstance(node.right, ast.Dict):  # "replaced_%(b)s_id" % {"b": "by"}
            pairs = [(_fold(k) if k is not None else None, _fold(v)) for k, v in zip(node.right.keys, node.right.values)]
            if any(k is None or v is None for k, v in pairs):
                return None
            operand: object = dict(pairs)
        else:
            items = node.right.elts if isinstance(node.right, ast.Tuple) else [node.right]
            args = [_fold(item) for item in items]
            if any(arg is None for arg in args):
                return None
            operand = tuple(args)
        try:
            return left % operand
        except (TypeError, ValueError, KeyError):
            return None
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in _FOLDED_METHODS:
        owner = _fold(node.func.value)
        kwargs = {k.arg: _fold(k.value) for k in node.keywords}
        if owner is None or any(k is None or v is None for k, v in kwargs.items()):
            return None
        if node.func.attr == "join":
            if node.keywords or len(node.args) != 1 or not isinstance(node.args[0], (ast.Tuple, ast.List)):
                return None
            items = [_fold(item) for item in node.args[0].elts]
            return None if any(item is None for item in items) else owner.join(items)
        args = [_fold(arg) for arg in node.args]
        if any(arg is None for arg in args):
            return None
        try:
            return getattr(owner, node.func.attr)(*args, **kwargs)
        except (TypeError, ValueError, IndexError, KeyError, AttributeError):
            return None
    return None


_SINK_NAMES = set(_NAME_FUNCTIONS) | _SQL_FUNCTIONS
# Calls that delete rows: ``delete(Model)``, ``query.delete()``, ``db.delete(obj)``, ``Delete(table)``, and
# ``db.merge(user)``, which lays a detached user's ``refresh_tokens`` over the stored ones and so deletes
# the tokens the copy lacks.
_DELETERS = {"delete", "Delete", "merge"}
# ``User.refresh_tokens`` is delete-orphan: a token dropped from it, or cut from its user through the
# ``RefreshToken.user`` back-reference, is deleted at flush. The collection methods that drop members, in
# the list, set and dict spellings (``append``, ``extend``, ``add``, ``any`` and reads keep them all), and
# the calls that set or delete an attribute by name.
_COLLECTION, _BACK_REFERENCE = "refresh_tokens", "user"
_DROPS_MEMBERS = {"remove", "pop", "popitem", "clear", "discard", "update", "difference_update",
                  "intersection_update", "symmetric_difference_update", "__delitem__", "__setitem__",
                  "__isub__", "__iand__", "__ixor__", "__imul__"}
_ATTRIBUTE_SETTERS = {"setattr", "delattr", "__setattr__", "__delattr__", "set_attribute"}
# SQL that deletes refresh-token rows, in a string or a migration: ``DELETE FROM refresh_tokens`` (also
# inside a CTE), a ``TRUNCATE`` statement that lists the table, ``MERGE INTO refresh_tokens ... THEN
# DELETE``.
_TABLE_NAME = r'(?:only\s+)?(?:"?\w+"?\.)?"?' + TABLE + r"\b"
_TABLE_DELETE = re.compile(
    r"\bdelete\s+from\s+" + _TABLE_NAME
    + r"|(?:^|[;\"'(]|\$\$|\b(?:begin|then|else|loop|do)\b)\s*truncate\s+(?:table\s+)?[\w\".,\s]*?\b" + TABLE + r"\b"
    + r"|\bmerge\s+into\s+" + _TABLE_NAME + r"[^;]*?\bthen\s+delete\b",
    re.IGNORECASE | re.MULTILINE)
# A SQL write: a statement that opens with its verb, after a CTE, a comment or an earlier statement
# (``_is_sql_write``), so prose such as "skipped the update: the plan is set by ..." is not one; a format placeholder a caller fills
# in later (not ``'{}'``, a quoted empty array or JSON object); psycopg2's SQL composers.
_SQL_WRITE = re.compile(
    r"(?:\A|;)\s*(?:with\b[^;]*?[()]\s*)?(?:update\b[^;]*?\bset\b|insert\s+into\b|delete\s+from\b"
    r"|merge\s+into\b|alter\s+table\b|truncate\b|copy\b[^;]*?\bfrom\b)", re.IGNORECASE | re.DOTALL)
_PLACEHOLDER = re.compile(r"(?<!')\{[^{}']*\}(?!')")
_SQL_COMPOSERS = {"SQL", "Composed", "Template"}
# Keywords that carry row data, a column or attribute name, or SQL text.
_DATA_KEYWORDS = {"params", "values", "parameters", "mappings", "set_"}
_NAME_KEYWORDS = {"name", "key", "attr"}
_SQL_KEYWORDS = {"text", "statement", "sql", "name"}


class _Module:
    """What the scan needs from the whole module: the names it imports (a key such as
    ``RefreshToken.revoked_at`` counts as spelled out only on an imported class), local aliases of the
    sink functions (``from sqlalchemy import text as sa_text``, ``put = setattr``), and names bound to
    a by-name lookup collection (``COLS = RefreshToken.__table__.c``) or to the delete-orphan collection
    (``tokens = user.refresh_tokens``)."""

    def __init__(self, tree: ast.AST) -> None:
        self.imported: set[str] = set()
        self.aliases: dict[str, str] = {}
        self.keyed: set[str] = set()
        self.collections: set[str] = set()
        self.extended: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    self.imported.add(alias.asname or alias.name.split(".")[0])
                    original = alias.name.split(".")[-1]
                    if alias.asname and (original in _SINK_NAMES or original in _DELETERS):
                        self.aliases[alias.asname] = original
            elif isinstance(node, ast.AugAssign) and isinstance(node.op, ast.Add):
                self.extended.add(ast.unparse(node.target))  # stmt += col, self.sql += col
            elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                  and node.func.attr in ("append", "extend", "insert")):
                self.extended.add(ast.unparse(node.func.value))  # parts.append(col)
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                head = node.value
                while isinstance(head, ast.BinOp) and isinstance(head.op, ast.Add):
                    head = head.left  # stmt = stmt + col + " = NULL" nests to the left
                if head is not node.value and ast.unparse(head) == ast.unparse(node.targets[0]):
                    self.extended.add(ast.unparse(node.targets[0]))
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in (t for t in targets if isinstance(t, ast.Name)):
                    if isinstance(node.value, ast.Attribute) and node.value.attr in _KEYED_ATTRS:
                        self.keyed.add(target.id)
                    if isinstance(node.value, ast.Attribute) and node.value.attr == _COLLECTION:
                        self.collections.add(target.id)
                    if isinstance(node.value, ast.Name) and node.value.id in _SINK_NAMES | _DELETERS:
                        self.aliases[target.id] = node.value.id
                    if isinstance(node.value, ast.Attribute) and node.value.attr in _DELETERS:
                        self.aliases[target.id] = node.value.attr  # drop = db.delete

    def sink(self, name: str | None) -> str | None:
        return self.aliases.get(name, name) if name else None


def _callee(node: ast.Call, module: _Module) -> str | None:
    func = node.func
    name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
    return module.sink(name)


def _spelled_key(key: ast.AST | None, module: _Module) -> bool:
    """A mapping key that names its column in the source: a literal (or a string built only from
    literals), or an attribute of an imported class such as ``RefreshToken.revoked_at``; not
    ``col.name`` and not a constant the module picked itself."""
    if key is None:
        return False
    if _fold(key) is not None:
        return True
    if not (isinstance(key, ast.Attribute) and isinstance(key.value, ast.Name)):
        return False
    owner = key.value.id
    # A class by its CapWords name: ``fields.LINK`` or ``settings.KEY`` is a constant, not a column.
    return owner in module.imported and owner[:1].isupper() and not owner.isupper()


def _keyed_collection(node: ast.AST | None, module: _Module) -> bool:
    """A by-name lookup collection: ``X.c``, ``X.__mapper__.attrs``, or a name bound to one."""
    if isinstance(node, ast.Attribute):
        return node.attr in _KEYED_ATTRS
    return isinstance(node, ast.Name) and node.id in module.keyed


def _literal_rows(node: ast.AST, module: _Module) -> bool:
    """A mapping, or a list or tuple of mappings, whose every key is spelled out (``_spelled_key``)."""
    if isinstance(node, (ast.List, ast.Tuple)):
        return all(_literal_rows(element, module) for element in node.elts)
    return isinstance(node, ast.Dict) and all(_spelled_key(key, module) for key in node.keys)


def _dynamic_sink(node: ast.Call, module: _Module) -> bool:
    """A call that can reach a column by a name the source does not spell out."""
    callee = _callee(node, module)
    keywords = {k.arg: k.value for k in node.keywords if k.arg is not None}
    if any(keyword.arg is None for keyword in node.keywords):
        return True  # f(**mapping)
    if callee in _NAME_FUNCTIONS:
        if any(isinstance(arg, ast.Starred) for arg in node.args):
            return True  # setattr(*args): the name is not in the source
        at = _name_position(node, callee)
        if len(node.args) > at and _fold(node.args[at]) is None:
            return True
        if any(_fold(value) is None for name, value in keywords.items() if name in _NAME_KEYWORDS):
            return True
    if callee in _SQL_FUNCTIONS:
        if node.args and _fold(node.args[0]) is None:
            return True
        if any(_fold(value) is None for name, value in keywords.items() if name in _SQL_KEYWORDS):
            return True
    owner = node.func.value if isinstance(node.func, ast.Attribute) else None
    if callee == "get" and node.args and _fold(node.args[0]) is None and _keyed_collection(owner, module):
        return True
    # A string assembled at run time straight into execute; SQL-shaped ones are counted where they
    # are built (``_run_time_sql``), wherever they go.
    if (callee in ("execute", "executemany") and node.args and _sql_built_at_run_time(node.args[0])
            and not _is_sql_write(_literal_text(node.args[0]))):
        return True
    # A row write must spell out its columns: any row data that is not a literal mapping (a name, a
    # call, a comprehension, ``dict(row)``) can carry a column picked at run time.
    if callee == "ordered_values":
        if not all(isinstance(pair, ast.Tuple) and pair.elts and _spelled_key(pair.elts[0], module)
                   for pair in node.args):
            return True
    elif callee in _ROW_WRITERS and isinstance(node.func, ast.Attribute):
        data = node.args[_ROW_WRITERS[callee]:] + [v for k, v in keywords.items() if k in _DATA_KEYWORDS]
        if any(not _literal_rows(item, module) for item in data):
            return True
    return any(not _mappings_spelled(arg, module) for arg in [*node.args, *keywords.values()])


def _name_position(node: ast.Call, callee: str) -> int:
    """Where a name-taking call carries the attribute name among its positional arguments."""
    bound = isinstance(node.func, ast.Attribute) and callee.startswith("__")
    if bound and isinstance(node.func.value, ast.Name) and node.func.value.id in ("object", "type"):
        return 1  # object.__setattr__(t, name, v): the instance comes first
    return _NAME_FUNCTIONS[callee]


def _spelled_name(node: ast.Call, callee: str) -> str | None:
    """The attribute name a name-taking call spells out (``setattr(user, "refresh_tokens", [])``), else None."""
    at = _name_position(node, callee)
    names = node.args[at:at + 1] + [k.value for k in node.keywords if k.arg in _NAME_KEYWORDS]
    return _fold(names[0]) if names else None


def _token_collection(node: ast.AST, module: _Module) -> bool:
    """``User.refresh_tokens`` as the source reaches it: ``x.refresh_tokens``, a name bound to one, or
    ``getattr(x, "refresh_tokens")``."""
    if isinstance(node, ast.Attribute):
        return node.attr == _COLLECTION
    if isinstance(node, ast.Name):
        return node.id in module.collections
    return (isinstance(node, ast.Call) and _callee(node, module) == "getattr"
            and _spelled_name(node, "getattr") == _COLLECTION)


def _orphans(node: ast.Attribute, module: _Module) -> bool:
    """An attribute that drops a token from the delete-orphan collection: the collection or a token's
    ``user`` stored or deleted (``user.refresh_tokens = keep``, ``-=``, ``t.user = None``, ``del t.user``;
    a user that may be None at run time cuts the token loose too), or a member-dropping method of the
    collection, called or handed on (``user.refresh_tokens.remove``)."""
    if node.attr in (_COLLECTION, _BACK_REFERENCE) and not isinstance(node.ctx, ast.Load):
        return True
    return node.attr in _DROPS_MEMBERS and _token_collection(node.value, module)


def _sql_built_at_run_time(node: ast.AST) -> bool:
    """A string assembled from a non-literal part: an f-string, ``+`` or ``%`` with a string side, or
    ``.format``/``.join`` on a string literal, that does not fold."""
    if _fold(node) is not None:
        return False
    if isinstance(node, ast.JoinedStr):
        return True
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mod)):
        return any(isinstance(side, ast.JoinedStr) or (isinstance(side, ast.Constant) and isinstance(side.value, str))
                   or _sql_built_at_run_time(side) for side in (node.left, node.right))
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr in ("format", "join") and isinstance(node.func.value, ast.Constant))


def _function_locals(node: ast.AST) -> set[str]:
    """The parameters and assigned names of one function, not of the functions nested in it."""
    names = {arg.arg for arg in ast.walk(node.args) if isinstance(arg, ast.arg)}
    stack = list(node.body)
    while stack:
        child = stack.pop()
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(child.name)
        elif isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store):
            names.add(child.id)
        elif not isinstance(child, ast.Lambda):
            stack.extend(ast.iter_child_nodes(child))
    return names


def _is_sql_write(text: str) -> bool:
    return bool(_SQL_WRITE.search(_strip_sql_comments(text)))


def _literal_text(node: ast.AST) -> str:
    """The literal parts of a string expression, joined; the parts filled in at run time dropped."""
    if isinstance(node, ast.Constant):
        return node.value if isinstance(node.value, str) else ""
    if isinstance(node, ast.JoinedStr):
        return " ".join(_literal_text(value) for value in node.values if isinstance(value, ast.Constant))
    if isinstance(node, ast.BinOp):
        return _literal_text(node.left) + " " + _literal_text(node.right)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in ("format", "join"):
        elements = node.args[0].elts if node.func.attr == "join" and node.args and isinstance(node.args[0], (ast.List, ast.Tuple)) else []
        return " ".join([_literal_text(node.func.value), *(_literal_text(element) for element in elements)])
    return ""


def _mappings_spelled(node: ast.AST, module: _Module) -> bool:
    """Every mapping literal in an argument, inside lists and tuples too, spells out its keys; a
    comprehension never does. Values that are not mappings do not matter here."""
    if isinstance(node, ast.DictComp):
        return False
    if isinstance(node, ast.Dict):
        return all(_spelled_key(key, module) for key in node.keys)
    if isinstance(node, (ast.List, ast.Tuple)):
        return all(_mappings_spelled(element, module) for element in node.elts)
    return True


def _names_the_model(tree: ast.AST, docstrings: set[int]) -> bool:
    """Whether a module names ``RefreshToken``, its table, ``User.refresh_tokens`` or the column itself
    (a field of that name in a dataclass or schema too), outside docstrings (a name built from literals
    counts, in any case), or imports a refresh-token module (``refresh_token_service`` hands its
    callers token rows to delete)."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and "refresh_token" in (node.module or ""):
            return True
        if isinstance(node, ast.alias) and "refresh_token" in node.name:
            return True
        if isinstance(node, ast.Name) and node.id in ("RefreshToken", COLUMN):
            return True
        if isinstance(node, ast.Attribute) and node.attr in ("RefreshToken", "refresh_tokens", COLUMN):
            return True
        if isinstance(node, ast.keyword) and node.arg == COLUMN:
            return True
        if isinstance(node, ast.alias) and node.name.split(".")[-1] in ("RefreshToken", "refresh_token"):
            return True
        if isinstance(node, (ast.Constant, ast.JoinedStr, ast.BinOp, ast.Call)) and id(node) not in docstrings:
            folded = _fold(node)
            if folded is not None and ("RefreshToken" in folded or any(name in folded.lower() for name in (TABLE, COLUMN))):
                return True
    return False


def _mention_counts(source: str) -> Counter[tuple[str, str]]:
    tree = ast.parse(source)
    docstrings = _docstring_ids(tree)
    finder = _ColumnMentionFinder(docstrings, in_scope=_names_the_model(tree, docstrings), module=_Module(tree))
    finder.visit(tree)
    return finder.mentions


def _mentions(source: str) -> set[tuple[str, str]]:
    return set(_mention_counts(source))


# Dynamic SQL: a statement assembled and run inside the database (PL/pgSQL ``EXECUTE format(...)``,
# ``EXECUTE concat(...)``, ``EXECUTE stmt``; psql's ``\\gexec``), whose column cannot be read off the
# file. In SQL every ``EXECUTE`` counts but a trigger's ``EXECUTE FUNCTION``; in a shell script or a
# workflow, only one that takes SQL (not ``gcloud run jobs execute``, an ``--execute`` flag or prose).
_DYNAMIC_SQL = re.compile(r"\bexecute\b(?!\s+(?:function|procedure)\b)|\\gexec\b", re.IGNORECASE)
_DYNAMIC_SHELL = re.compile(
    r"(?<!jobs\s)(?<![-\w])execute\s+(?!function\b|procedure\b)(?:[a-z_]\w*\s*(?:\(|;|\|\||using\b|into\b)|e?'|\(|\$\w*\$)"
    r"|\\gexec\b", re.IGNORECASE)
_SHELL_COMMENT = re.compile(r"^\s*#.*$", re.MULTILINE)


def _strip_sql_comments(text: str) -> str:
    """SQL without its ``--`` and ``/* */`` comments; a single-quoted string, where ``--`` is text, is kept."""
    out, i = [], 0
    while i < len(text):
        if text[i] == "'":
            escapes = i > 0 and text[i - 1] in "eE"  # E'it\'s': a backslash escapes the quote
            j = i + 1
            while j < len(text) and (text[j] != "'" or text[j + 1:j + 2] == "'"):
                j += 2 if text[j] == "'" or (escapes and text[j] == "\\") else 1
            out.append(text[i:j + 1])
            i = j + 1
        elif text.startswith("--", i):
            end = text.find("\n", i)
            i = len(text) if end < 0 else end
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            out.append(" ")
            i = len(text) if end < 0 else end + 2
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


_TEXT_SCOPE = "<file>"


def _text_mention_counts(text: str, *, sql: bool = True) -> Counter[tuple[str, str]]:
    """A migration, shell script or workflow, read as text: every occurrence of the column in any case
    (SQL folds unquoted names) is a ``text`` mention, comments included; in a file that names the
    column or the table, each statement that deletes refresh-token rows is a ``delete`` and each
    dynamic-SQL ``EXECUTE`` or ``\\gexec`` is ``dynamic``."""
    lowered = text.lower()
    counts: Counter[tuple[str, str]] = Counter({(_TEXT_SCOPE, "text"): lowered.count(COLUMN)})
    if COLUMN in lowered or TABLE in lowered:
        code = _strip_sql_comments(text) if sql else _SHELL_COMMENT.sub("", text)  # a comment runs nothing
        counts[(_TEXT_SCOPE, "delete")] = len(_TABLE_DELETE.findall(code))
        counts[(_TEXT_SCOPE, "dynamic")] = len((_DYNAMIC_SQL if sql else _DYNAMIC_SHELL).findall(code))
    return +counts  # drop the zero counts


# What never reaches the production database: the browser app (it holds no database credentials), git
# itself, and tool caches. The records folders are scanned: tasks/ holds SQL written to be run against
# production by hand.
_UNSCANNED_ROOTS = {"frontend"}
_UNSCANNED_PARTS = {"tests", ".git", "node_modules", "__pycache__", "venv", ".venv", ".pytest_cache", ".ruff_cache",
                    ".mypy_cache"}


def _scanned_files(root: Path = REPO_DIR) -> list[Path]:
    """Every Python, SQL, shell and workflow file that can reach the production database: the whole
    repository but the browser app and the test homes, so the backend (the app, the entrypoints,
    ``scripts/`` one-offs, the migrations), ``ops/`` (the detection and capacity SQL that ops.yml runs
    with the app's credentials), the root ``scripts/``, ``tasks/`` (operator SQL), ``.github`` and
    ``.claude``. A new folder is scanned by default; a nested checkout or worktree (a folder with its
    own ``.git``, such as an agent worktree under ``.claude/worktrees/``) is another tree, not this one."""
    files = []
    for folder, subfolders, names in os.walk(root):
        here = Path(folder)
        subfolders[:] = [name for name in subfolders if name not in _UNSCANNED_PARTS
                         and not (here == root and name in _UNSCANNED_ROOTS)
                         and not (here / name / ".git").exists()]
        files += [here / name for name in names
                  if Path(name).suffix in (".py", ".sql", ".sh", ".yml", ".yaml") and (here / name).is_file()]
    return sorted(files)


def _file_mention_counts(path: Path) -> Counter[tuple[str, str]]:
    text = path.read_text(encoding="utf-8-sig")  # a byte-order mark is not code
    if path.suffix == ".py":
        return _mention_counts(text)
    return _text_mention_counts(text, sql=path.suffix == ".sql")


# Planted forms: every way a second writer could reach the column must be counted; a docstring or a
# comment that names it must not be.
PLANTED = [
    ("alias-then-update",
     "def f(q, v):\n    successor = RefreshToken.replaced_by_id\n    q.update({successor: v})\n",
     {("f", "read"), ("f", "dynamic")}),
    ("attribute-assignment", "def f(t, v):\n    t.replaced_by_id = v\n", {("f", "write")}),
    ("annotated-assignment", "def f(t, v):\n    t.replaced_by_id: int = v\n", {("f", "write")}),
    ("dict-key",
     "from app.models import RefreshToken\n\ndef f(q, v):\n    q.update({RefreshToken.replaced_by_id: v})\n",
     {("f", "key")}),
    ("string-key-update", "def f(q):\n    q.update({'replaced_by_id': None})\n", {("f", "key")}),
    ("ordered-values-column-key",
     "from app.models import RefreshToken\n\ndef f(stmt, v):\n"
     "    return stmt.ordered_values((RefreshToken.replaced_by_id, v))\n", {("f", "key")}),
    ("constructor-keyword", "def f(v):\n    return RefreshToken(user_id=1, replaced_by_id=v)\n",
     {("f", "keyword")}),
    ("values-keyword", "def f(s, v):\n    return s.values(replaced_by_id=v)\n", {("f", "keyword")}),
    ("setattr", "def f(t, v):\n    setattr(t, 'replaced_by_id', v)\n", {("f", "string")}),
    ("getattr", "def f(t):\n    return getattr(t, 'replaced_by_id')\n", {("f", "string")}),
    ("column-by-name", "def f(v):\n    return column('replaced_by_id') == v\n", {("f", "string")}),
    ("raw-sql-text", "def f():\n    return text('UPDATE refresh_tokens SET replaced_by_id = 1')\n",
     {("f", "string")}),
    ("module-level-alias", "SUCCESSOR = RefreshToken.replaced_by_id\n", {("<module>", "read")}),
    ("column-definition", "class T:\n    replaced_by_id = Column(Integer)\n", {("T", "definition")}),
    ("docstring-only", 'def f():\n    """Reads replaced_by_id to decide."""\n    return 1\n', set()),
    ("comment-only", "def f():\n    # replaced_by_id is written by rotation only\n    return 1\n", set()),
    ("other-column", "def f(t, v):\n    t.revoked_at = v\n", set()),
    # Names built from literals are folded, in any module; the module then names the column, so its
    # dynamic-name sinks count too.
    ("joined-name-then-setattr",
     "def f(t, v):\n    key = '_'.join(('replaced', 'by', 'id'))\n    setattr(t, key, v)\n",
     {("f", "string"), ("f", "dynamic")}),
    ("concatenated-name", "def f(t, v):\n    t.__setattr__('replaced' + '_by_id', v)\n", {("f", "string")}),
    ("percent-formatted-name", "def f(t, v):\n    setattr(t, 'replaced_%s_id' % 'by', v)\n", {("f", "string")}),
    ("f-string-name", "def f(t, v):\n    setattr(t, f\"{'replaced'}_by_id\", v)\n", {("f", "string")}),
    ("format-method-name", "def f(t, v):\n    setattr(t, '{}_by_id'.format('replaced'), v)\n", {("f", "string")}),
    ("case-folded-name", "def f(t, v):\n    setattr(t, 'REPLACED_BY_ID'.lower(), v)\n", {("f", "string")}),
    # In a module that names the model or its table, every dynamic-name sink is counted.
    ("joined-name-in-the-models-module",
     "from app.models import RefreshToken\n\ndef f(t, v):\n    key = '_'.join(('replaced', 'by', 'id'))\n"
     "    setattr(t, key, v)\n", {("f", "string"), ("f", "dynamic")}),
    ("loop-over-the-columns",
     "from app.models import RefreshToken as Token\n\ndef f(t, v):\n    for col in Token.__table__.columns:\n"
     "        setattr(t, col.name, v)\n", {("f", "dynamic")}),
    ("star-star-values", "TABLE = 'refresh_tokens'\n\ndef f(s, fields):\n    return s.values(**fields)\n",
     {("f", "dynamic")}),
    ("dict-comprehension-update",
     "from app.models import RefreshToken\n\ndef f(q, keys, v):\n    q.update({k: v for k in keys})\n",
     {("f", "dynamic")}),
    ("raw-sql-built-at-run-time",
     "from app.models import RefreshToken\n\ndef f(s, sql):\n    return s.execute(text(sql))\n", {("f", "dynamic")}),
    ("column-collection-lookup",
     "from app.models import RefreshToken\n\ndef f(key):\n    return RefreshToken.__table__.c[key]\n",
     {("f", "dynamic")}),
    ("literal-names-in-the-models-module",
     "from app.models import RefreshToken\n\ndef f(q, t, v):\n    setattr(t, 'revoked_at', v)\n"
     "    q.update({RefreshToken.revoked_at: v})\n    return getattr(t, 'expires_at'), q.values(revoked_at=v)\n",
     set()),
    ("carried-row-copy",
     "from app.models import RefreshToken\n\ndef f(db, row, new_id):\n    carried = dict(row)\n"
     "    db.query(RefreshToken).filter(RefreshToken.id == new_id).update(carried)\n", {("f", "dynamic")}),
    ("column-loop-mapping",
     "from app.models import RefreshToken\n\ndef f(db, v):\n    for col in RefreshToken.__table__.columns:\n"
     "        db.query(RefreshToken).update({col.name: v})\n", {("f", "dynamic")}),
    ("executemany-rows",
     "from app.models import RefreshToken\n\ndef f(db, key, v):\n"
     "    db.execute(update(RefreshToken), [{'id': 1, key: v}])\n", {("f", "dynamic")}),
    ("bulk-update-mappings",
     "from app.models import RefreshToken\n\ndef f(db, rows):\n    db.bulk_update_mappings(RefreshToken, rows)\n",
     {("f", "dynamic")}),
    ("dunder-setattr", "from app.models import RefreshToken\n\ndef f(t, key, v):\n    object.__setattr__(t, key, v)\n",
     {("f", "dynamic")}),
    ("aliased-column-collection",
     "from app.models import RefreshToken\n\nCOLS = RefreshToken.__table__.c\n\ndef f(key):\n"
     "    return COLS.get(key)\n", {("f", "dynamic")}),
    ("driver-sql", "from app.models import RefreshToken\n\ndef f(conn, sql):\n    conn.exec_driver_sql(sql)\n",
     {("f", "dynamic")}),
    ("relationship-names-the-model",
     "def f(user, key, v):\n    for t in user.refresh_tokens:\n        setattr(t, key, v)\n", {("f", "dynamic")}),
    ("upsert-set-keyword",
     "from app.models import RefreshToken\n\ndef f(db, stmt, key, v):\n"
     "    db.execute(stmt.on_conflict_do_update(index_elements=['token_hash'], set_={key: v}))\n",
     {("f", "dynamic")}),
    ("bulk-mappings-keyword",
     "from app.models import RefreshToken\n\ndef f(db, rows):\n"
     "    db.bulk_update_mappings(RefreshToken, mappings=rows)\n",
     {("f", "dynamic")}),
    ("execute-parameters-keyword",
     "from app.models import RefreshToken\n\ndef f(conn, rows):\n"
     "    conn.execute(RefreshToken.__table__.update(), parameters=rows)\n", {("f", "dynamic")}),
    ("ordered-values-picked-column",
     "from app.models import RefreshToken\n\ndef f(db, v):\n    col = list(RefreshToken.__table__.columns)[-1]\n"
     "    db.execute(update(RefreshToken).ordered_values((col, v)))\n", {("f", "dynamic")}),
    ("name-by-keyword",
     "from app.models import RefreshToken\n\ndef f(t, key, v):\n    set_attribute(t, key=key, value=v)\n",
     {("f", "dynamic")}),
    ("aliased-sql-text",
     "from sqlalchemy import text as sa_text\nfrom app.models import RefreshToken\n\ndef f(db, sql):\n"
     "    db.execute(sa_text(sql))\n", {("f", "dynamic")}),
    ("setattr-handed-on",
     "from functools import partial\nfrom app.models import RefreshToken\n\ndef f(t, key, v):\n"
     "    partial(setattr, t)(key, v)\n", {("f", "dynamic")}),
    ("module-picked-constant",
     "from app.models import RefreshToken\n\nclass Cols:\n    LINK = list(RefreshToken.__table__.columns)[-1]\n\n"
     "def f(q, v):\n    q.update({Cols.LINK: v})\n", {("f", "dynamic")}),
    ("key-off-a-module-constant",
     "from app.auth import fields\nfrom app.models import RefreshToken\n\ndef f(q, v):\n    q.update({fields.LINK: v})\n",
     {("f", "dynamic")}),
    ("sql-built-at-run-time",
     "from app.models import RefreshToken\n\ndef f(cursor, col):\n"
     "    cursor.execute(f'UPDATE refresh_tokens SET {col} = NULL')\n", {("f", "dynamic")}),
    ("field-only-module-writer",
     "@dataclass\nclass Patch:\n    replaced_by_id: int | None\n\ndef apply(t, patch):\n"
     "    for k, v in asdict(patch).items():\n        setattr(t, k, v)\n",
     {("Patch", "definition"), ("apply", "dynamic")}),
    # Deleting a successor writes NULL into its predecessor's link (ON DELETE SET NULL), so every delete
    # in a module that names the model counts, in each spelling.
    ("query-delete",
     "from app.models import RefreshToken\n\ndef f(db, uid):\n"
     "    db.query(RefreshToken).filter(RefreshToken.user_id == uid).delete()\n", {("f", "delete")}),
    ("delete-construct-under-an-alias",
     "from sqlalchemy import delete as sa_delete\nfrom app.models import RefreshToken\n\ndef f(db):\n"
     "    db.execute(sa_delete(RefreshToken))\n", {("f", "delete")}),
    ("session-delete", "def f(db, user):\n    for t in user.refresh_tokens:\n        db.delete(t)\n",
     {("f", "delete")}),
    ("raw-sql-delete", "def f(db):\n    db.execute(text('DELETE FROM refresh_tokens WHERE revoked_at IS NOT NULL'))\n",
     {("f", "delete")}),
    # SQL folds unquoted names, so a Python string matches in any case.
    ("upper-case-raw-sql", "def f(db):\n    db.execute(text('UPDATE REFRESH_TOKENS SET REPLACED_BY_ID = NULL'))\n",
     {("f", "string")}),
    ("upper-case-table-delete", "def f(db):\n    db.execute(text('DELETE FROM REFRESH_TOKENS WHERE expires_at < now()'))\n",
     {("f", "delete")}),
    ("bytes-sql", "def f(cur):\n    cur.execute(b'UPDATE refresh_tokens SET replaced_by_id = NULL')\n", {("f", "string")}),
    ("keyword-formatted-name", "def f(t, v):\n    setattr(t, '{a}_by_id'.format(a='replaced'), v)\n", {("f", "string")}),
    ("mapping-percent-name", "def f(t, v):\n    setattr(t, 'replaced_%(b)s_id' % {'b': 'by'}, v)\n", {("f", "string")}),
    # SQL assembled at run time counts where it is built, whether or not it goes straight to execute.
    ("sql-bound-to-a-name-first",
     "from app.models import RefreshToken\n\ndef f(conn, col):\n    sql = 'UPDATE refresh_tokens SET ' + col + ' = NULL'\n"
     "    conn.connection.cursor().execute(sql)\n", {("f", "dynamic")}),
    ("f-string-sql-in-a-script",
     "TABLE = 'refresh_tokens'\n\ndef main(cur, field):\n"
     "    stmt = f'UPDATE {TABLE} SET {field} = NULL WHERE revoked_at IS NOT NULL'\n    cur.execute(stmt)\n",
     {("main", "dynamic")}),
    ("psycopg2-composed-sql",
     "from psycopg2 import sql\nfrom app.models import RefreshToken\n\ndef f(cur, field):\n"
     "    cur.execute(sql.SQL('UPDATE refresh_tokens SET {} = NULL').format(sql.Identifier(field)))\n",
     {("f", "dynamic")}),
    ("local-named-like-a-sink",
     "from app.models import RefreshToken\n\ndef f(text, column):\n    return text.strip(), column\n", set()),
    # Deletes reached another way: through a refresh-token module, handed on, aliased, the Delete class.
    ("delete-of-a-row-a-sibling-service-found",
     "from app.services import refresh_token_service\n\ndef f(db, raw):\n"
     "    token = refresh_token_service.find(db, raw)\n    db.delete(token)\n", {("f", "delete")}),
    ("delete-handed-on", "from app.models import RefreshToken\n\ndef f(db, tokens):\n    list(map(db.delete, tokens))\n",
     {("f", "delete")}),
    ("delete-aliased-then-called",
     "from app.models import RefreshToken\n\ndef f(db, t):\n    drop = db.delete\n    drop(t)\n", {("f", "delete")}),
    ("delete-construct-class",
     "from sqlalchemy.sql.expression import Delete\nfrom app.models import RefreshToken\n\ndef f(db):\n"
     "    db.execute(Delete(RefreshToken.__table__))\n", {("f", "delete")}),
    ("route-decorator-is-not-a-delete",
     "from app.services import refresh_token_service\n\n@router.delete('/sessions/{sid}')\ndef f(sid):\n    return sid\n",
     set()),
    # A SQL write assembled from pieces counts where its pieces are: extended with +=, joined from a
    # list, or composed with psycopg2's sql module.
    ("sql-extended-with-plus-equals",
     "from app.models import RefreshToken\n\ndef f(cur, col):\n    stmt = 'UPDATE refresh_tokens SET '\n    stmt += col\n    stmt += ' = NULL'\n"
     "    cur.execute(stmt)\n", {("f", "dynamic")}),
    ("sql-joined-from-a-list",
     "from app.models import RefreshToken\n\ndef f(cur, col):\n    stmt = ' '.join(['UPDATE', 'refresh_tokens', 'SET', col, '= NULL'])\n"
     "    cur.execute(stmt)\n", {("f", "dynamic")}),
    ("psycopg2-concatenated-sql",
     "from psycopg2 import sql\nfrom app.models import RefreshToken\n\ndef f(cur, col):\n"
     "    cur.execute(sql.SQL('UPDATE refresh_tokens SET ') + sql.Identifier(col) + sql.SQL(' = NULL'))\n",
     {("f", "dynamic")}),
    ("psycopg2-composed-list",
     "from psycopg2 import sql\nfrom app.models import RefreshToken\n\ndef f(cur, col):\n"
     "    cur.execute(sql.Composed([sql.SQL('UPDATE refresh_tokens SET '), sql.Identifier(col), sql.SQL(' = NULL')]))\n",
     {("f", "dynamic")}),
    # A parameter named like a sink shadows it only inside its own function.
    ("sink-shadowed-in-one-function-only",
     "from sqlalchemy import text\nfrom app.models import RefreshToken\n\ndef clean(text):\n    return text.strip()\n\n"
     "def f(db, stmts):\n    for stmt in map(text, stmts):\n        db.execute(stmt)\n",
     {("f", "dynamic")}),
    # Prose, static SQL with a quoted '{}', and a format that folds are not SQL built at run time.
    ("prose-and-static-sql-look-alikes",
     "from app.models import RefreshToken\n\ndef f(db, sid):\n    logger.info(f'Skipped the update for {sid}: the plan is set by the bound subscription')\n"
     "    db.execute(text(\"UPDATE refresh_tokens SET tags = '{}' WHERE tags IS NULL\"))\n"
     "    return 'UPDATE refresh_tokens SET {} = 1'.format('flag')\n", set()),
    # A SQL write after a CTE, a comment or an earlier statement still opens a statement.
    ("cte-led-sql-write",
     "from app.models import RefreshToken\n\ndef f(cur, col):\n    stmt = f'WITH stale AS (SELECT id FROM refresh_tokens) UPDATE refresh_tokens SET {col} = NULL'\n"
     "    cur.execute(stmt)\n", {("f", "dynamic")}),
    ("statement-before-the-write",
     "from app.models import RefreshToken\n\ndef f(cur, col):\n    stmt = f\"SET LOCAL lock_timeout = '5s'; UPDATE refresh_tokens SET {col} = NULL\"\n"
     "    cur.execute(stmt)\n", {("f", "dynamic")}),
    ("comment-led-sql-write",
     "from app.models import RefreshToken\n\ndef f(cur, col):\n    stmt = '-- clear the field\\nUPDATE refresh_tokens SET ' + col + ' = NULL'\n    cur.execute(stmt)\n",
     {("f", "dynamic")}),
    # A start the code grows later, however it grows.
    ("list-bound-then-grown",
     "from app.models import RefreshToken\n\ndef f(cur, col):\n    parts = ['UPDATE refresh_tokens SET']\n    parts.append(col + ' = NULL')\n"
     "    stmt = ' '.join(parts)\n    cur.execute(stmt)\n", {("f", "dynamic")}),
    ("annotated-start-then-extended",
     "from app.models import RefreshToken\n\ndef f(cur, col):\n    stmt: str = 'UPDATE refresh_tokens SET '\n    stmt += col\n    cur.execute(stmt)\n",
     {("f", "dynamic")}),
    ("attribute-start-then-extended",
     "from app.models import RefreshToken\n\nclass Q:\n    def f(self, col):\n        self.sql = 'UPDATE refresh_tokens SET '\n        self.sql += col\n",
     {("f", "dynamic")}),
    ("start-reassigned-with-a-chain",
     "from app.models import RefreshToken\n\ndef f(cur, col):\n    stmt = 'UPDATE refresh_tokens SET '\n    stmt = stmt + col + ' = NULL'\n    cur.execute(stmt)\n",
     {("f", "dynamic")}),
    ("start-reassigned-with-plus",
     "from app.models import RefreshToken\n\ndef f(cur, col):\n    stmt = 'UPDATE refresh_tokens SET '\n    stmt = stmt + col\n    cur.execute(stmt)\n",
     {("f", "dynamic")}),
    # A closure or a lambda sees its function's parameter, not the sink it is named after.
    ("closure-over-a-sink-named-parameter",
     "from app.models import RefreshToken\n\ndef f(rows, column, text):\n    def inner():\n        return text.strip()\n"
     "    return sorted(rows, key=lambda r: r[column]), inner()\n", set()),
    ("lambda-parameter-named-like-a-sink",
     "from app.models import RefreshToken\n\ndef f(items):\n    return list(map(lambda text: text.strip(), items))\n", set()),
    ("delete-in-a-decorator-argument",
     "from app.models import RefreshToken\n\n@cache(on_evict=db.delete)\ndef f(t):\n    return t\n", {("f", "delete")}),
    ("delete-after-a-cli-flag",
     "def f():\n    return \"psql --quiet -c 'DELETE FROM refresh_tokens WHERE revoked_at IS NOT NULL'\"\n", {("f", "delete")}),
    # User.refresh_tokens is delete-orphan: a token dropped from it, or cut from its user, is deleted at
    # flush, and so is one a merged detached user no longer holds.
    ("delete-orphan-removal", "def f(user, t):\n    user.refresh_tokens.remove(t)\n", {("f", "delete")}),
    ("delete-orphan-drops-in-every-spelling",
     "def by_pop(user):\n    user.refresh_tokens.pop()\n\ndef by_clear(user):\n    user.refresh_tokens.clear()\n\n"
     "def by_discard(user, t):\n    user.refresh_tokens.discard(t)\n\ndef by_popitem(user):\n    user.refresh_tokens.popitem()\n\n"
     "def by_dunder(user):\n    user.refresh_tokens.__delitem__(0)\n\n"
     "def handed_on(user, stale):\n    list(map(user.refresh_tokens.remove, stale))\n\n"
     "def by_getattr(user):\n    getattr(user, 'refresh_tokens').clear()\n",
     {(scope, "delete") for scope in ("by_pop", "by_clear", "by_discard", "by_popitem", "by_dunder", "handed_on", "by_getattr")}),
    ("delete-orphan-collection-replaced",
     "def by_assign(user):\n    user.refresh_tokens = []\n\ndef by_augmented(user, gone):\n    user.refresh_tokens -= gone\n\n"
     "def by_del(user):\n    del user.refresh_tokens\n\ndef by_slice(user, keep):\n    user.refresh_tokens[:] = keep\n\n"
     "def by_del_item(user):\n    del user.refresh_tokens[0]\n\ndef by_setattr(user):\n    setattr(user, 'refresh_tokens', [])\n",
     {(scope, "delete") for scope in ("by_assign", "by_augmented", "by_del", "by_slice", "by_del_item", "by_setattr")}),
    ("delete-orphan-through-an-alias",
     "def by_call(user, t):\n    tokens = user.refresh_tokens\n    tokens.remove(t)\n\n"
     "def by_item(user, t):\n    tokens = user.refresh_tokens\n    tokens[0] = t\n\n"
     "def by_augmented(user):\n    tokens = user.refresh_tokens\n    tokens *= 0\n",
     {("by_call", "delete"), ("by_item", "delete"), ("by_augmented", "delete")}),
    # A user that may be None at run time cuts the token loose as None does; another user moves it.
    ("delete-orphan-back-reference",
     "from app.models import RefreshToken\n\ndef cut(t):\n    t.user = None\n\ndef moved(t, owner):\n    t.user = owner\n\n"
     "def by_del(t):\n    del t.user\n\ndef by_setattr(t):\n    setattr(t, 'user', None)\n",
     {("cut", "delete"), ("moved", "delete"), ("by_del", "delete"), ("by_setattr", "delete")}),
    ("merge-of-a-detached-user",
     "from app.models import RefreshToken\n\ndef f(db, detached_user):\n    return db.merge(detached_user)\n", {("f", "delete")}),
    ("delete-orphan-look-alikes",
     "from app.models import RefreshToken, User\n\ndef f(db, user, t, stale):\n"
     "    live = [x for x in user.refresh_tokens if x.revoked_at is None]\n    kept = list(user.refresh_tokens)\n"
     "    kept.remove(t)\n    user.refresh_tokens.append(t)\n    user.searches.remove(stale)\n    first = user.refresh_tokens[0]\n"
     "    db.query(User).options(selectinload(User.refresh_tokens)).filter(User.refresh_tokens.any(RefreshToken.id == t.id))\n"
     "    t.user_id = user.id\n"
     "    return live, len(user.refresh_tokens), t in user.refresh_tokens, first, t.user, getattr(user, 'refresh_tokens')\n",
     set()),
    ("payload-tuple-in-the-models-module",
     "from app.models import RefreshToken\n\ndef f(events, t):\n"
     "    events.append((str(t.id), 'revoked', {'reason': 'logout'}))\n", set()),
    ("literal-rows-in-the-models-module",
     "from app.models import RefreshToken\n\ndef f(db, uid, v):\n"
     "    db.query(RefreshToken).filter(RefreshToken.user_id == uid).update({RefreshToken.revoked_at: v})\n"
     "    db.execute(update(RefreshToken), [{'id': 1, 'revoked_at': v}])\n"
     "    return db.execute(select(RefreshToken))\n",
     set()),
]

# Named gaps: what the scan cannot see. A case that starts being counted moves to PLANTED. Each gap
# sits in ``f``; the first four are out of scope (the module names neither the model, its table, the
# column nor a refresh-token module), the rest stay unseen inside it.
GAPS = [
    ("generic-helper-handed-a-token",
     "def stamp(obj, field, value):\n    setattr(obj, field, value)\n\ndef f(t, field, v):\n"
     "    stamp(t, field, v)\n", False),
    ("generic-delete-helper-handed-the-model",
     "def f(db, model, cond):\n    db.execute(delete(model).where(cond))\n", False),
    ("merge-or-cut-in-a-module-out-of-scope", "def f(db, user, t):\n    db.merge(user)\n    t.user = None\n", False),
    ("name-from-code-the-folder-does-not-run",
     "def f(t, v):\n    setattr(t, ''.join(reversed('di_yb_decalper')), v)\n", False),
    # Whole-row copies move every column, the link included, without naming one.
    ("insert-from-select-copy",
     "from app.models import RefreshToken\n\ndef f(db, uid):\n    t = RefreshToken.__table__\n"
     "    cols = [c for c in t.columns if c.name != 'id']\n"
     "    db.execute(insert(t).from_select(cols, select(*cols).where(t.c.user_id == uid)))\n", True),
    ("transient-copy",
     "from app.models import RefreshToken\n\ndef f(db, old, h):\n    make_transient(old)\n    old.id = None\n"
     "    old.token_hash = h\n    db.add(old)\n", True),
    # A helper elsewhere handed the delete-orphan collection drops its members where the scan cannot see.
    ("delete-orphan-collection-handed-to-a-helper", "def f(user, prune):\n    prune(user.refresh_tokens)\n", True),
    # An ORM synonym is one reviewed mention; writes through it name only the synonym.
    ("write-through-a-synonym",
     "class RefreshToken(Base):\n    link = synonym('replaced_by_id')\n\ndef f(t, v):\n    t.link = v\n", True),
]

# The same scan over a migration, shell script or workflow, read as text.
TEXT_PLANTED = [
    ("migration-sets-the-link", "UPDATE refresh_tokens SET replaced_by_id = NULL WHERE revoked_at IS NOT NULL;\n",
     {("<file>", "text")}),
    ("upper-case-column", "UPDATE refresh_tokens SET REPLACED_BY_ID = NULL;\n", {("<file>", "text")}),
    ("comment-naming-the-column", "-- replaced_by_id stays as rotation wrote it\nSELECT 1;\n", {("<file>", "text")}),
    ("psql-in-a-workflow-step", '      - run: psql -c "UPDATE refresh_tokens SET replaced_by_id = NULL"\n',
     {("<file>", "text")}),
    ("delete-strips-the-remaining-links", "DELETE FROM refresh_tokens WHERE expires_at < now();\n",
     {("<file>", "delete")}),
    ("schema-qualified-delete", 'DELETE FROM public."refresh_tokens" WHERE id = 1;\n', {("<file>", "delete")}),
    ("comment-split-delete", "DELETE FROM -- expired\n  refresh_tokens WHERE expires_at < now();\n",
     {("<file>", "delete")}),
    ("delete-in-a-cte", "WITH gone AS (DELETE FROM refresh_tokens WHERE id = 1 RETURNING id) SELECT 1;\n",
     {("<file>", "delete")}),
    ("truncate", "TRUNCATE TABLE users, refresh_tokens;\n", {("<file>", "delete")}),
    ("merge-then-delete",
     "MERGE INTO refresh_tokens t USING stale s ON t.id = s.id WHEN MATCHED THEN DELETE;\n", {("<file>", "delete")}),
    ("dynamic-sql-in-a-do-block",
     "DO $$ BEGIN EXECUTE format('UPDATE refresh_tokens SET %I = NULL', 'replaced' || '_by_id'); END $$;\n",
     {("<file>", "dynamic")}),
    ("dynamic-sql-from-a-variable",
     "DO $$ DECLARE stmt text := 'UPDATE refresh_tokens SET x = 1'; BEGIN EXECUTE stmt; END $$;\n",
     {("<file>", "dynamic")}),
    ("gexec", "SELECT format('UPDATE refresh_tokens SET %I = NULL', name) FROM cols\n\\gexec\n",
     {("<file>", "dynamic")}),
    ("dynamic-sql-in-other-shapes",
     "DO $$ BEGIN EXECUTE concat('UPDATE refresh_tokens SET ', c, ' = NULL'); "
     "EXECUTE E'UPDATE refresh_tokens SET ' || c; EXECUTE ('UPDATE refresh_tokens SET ' || c || ' = NULL'); END $$;\n",
     {("<file>", "dynamic")}),
    ("truncate-after-begin", "DO $$ BEGIN TRUNCATE refresh_tokens; END $$;\n", {("<file>", "delete")}),
    ("escaped-quote-in-an-e-string",
     "DO $$ BEGIN RAISE NOTICE E'it\\'s -- not a comment'; EXECUTE stmt; END $$; -- refresh_tokens\n",
     {("<file>", "dynamic")}),
    ("dashes-inside-a-string-hide-nothing",
     "DO $$ BEGIN RAISE NOTICE '-- start'; EXECUTE stmt; TRUNCATE refresh_tokens; END $$;\n",
     {("<file>", "dynamic"), ("<file>", "delete")}),
    # A user's chain goes with the user (ON DELETE CASCADE), so no predecessor is left to strip; a
    # trigger's EXECUTE FUNCTION, a gcloud job and a comment run no dynamic SQL.
    ("look-alikes",
     "UPDATE users SET is_pro = false;\nDELETE FROM users WHERE id = 1;\n-- never truncate refresh_tokens\n"
     "CREATE TRIGGER touch AFTER UPDATE ON refresh_tokens FOR EACH ROW EXECUTE FUNCTION touch();\n"
     "-- execute this once\n", set()),
]
# A workflow or shell script: whole-line comments and gcloud's ``jobs execute`` run no SQL.
SHELL_TEXT_PLANTED = [
    ("gcloud-jobs-beside-the-table",
     "# refresh_tokens are never touched here\n      - run: gcloud run jobs execute migrate --region us-west1 || true\n"
     "      - run: gcloud sql connect db --execute status\n", set()),
    ("comment-line-and-gcloud-beside-the-table",
     "# EXECUTE stmt; refresh_tokens\n      - run: gcloud run jobs execute migrate || true  # refresh_tokens\n", set()),
    ("psql-dynamic-sql-in-a-step", '      - run: psql -c "DO $$ BEGIN EXECUTE stmt; END $$" # refresh_tokens\n',
     {("<file>", "dynamic")}),
]
TEXT_GAPS = [
    ("whole-row-copy", "INSERT INTO refresh_tokens SELECT * FROM refresh_tokens_backup;\n"),
    ("positional-insert", "INSERT INTO refresh_tokens VALUES (1, 2, 'h', now(), now(), NULL, 5);\n"),
    ("copy-from-a-file", "COPY refresh_tokens FROM '/tmp/tokens.csv' WITH (FORMAT csv);\n"),
    ("psql-meta-copy", "\\copy refresh_tokens FROM 'tokens.csv' csv\n"),
    ("psql-variable-column", "UPDATE refresh_tokens SET :col = NULL;\n"),
    ("names-built-in-sql",
     "DO $$ BEGIN EXECUTE format('UPDATE %I SET %I = NULL', 'refresh' || '_tokens', 'replaced' || '_by_id'); END $$;\n"),
]


@pytest.mark.parametrize("source, expected", [p[1:] for p in PLANTED], ids=[p[0] for p in PLANTED])
def test_the_mention_scan_scores_every_planted_form(source, expected):
    assert _mentions(source) == expected


@pytest.mark.parametrize("source, in_scope", [g[1:] for g in GAPS], ids=[g[0] for g in GAPS])
def test_the_named_gaps_stay_out_of_reach(source, in_scope):
    tree = ast.parse(source)
    assert _names_the_model(tree, _docstring_ids(tree)) is in_scope
    assert not {mention for mention in _mentions(source) if mention[0] == "f"}


@pytest.mark.parametrize("text, expected", [p[1:] for p in TEXT_PLANTED], ids=[p[0] for p in TEXT_PLANTED])
def test_the_text_scan_scores_every_planted_form(text, expected):
    assert set(_text_mention_counts(text)) == expected


@pytest.mark.parametrize("text, expected", [p[1:] for p in SHELL_TEXT_PLANTED], ids=[p[0] for p in SHELL_TEXT_PLANTED])
def test_the_text_scan_reads_a_workflow_as_shell(text, expected):
    assert set(_text_mention_counts(text, sql=False)) == expected


@pytest.mark.parametrize("text", [g[1] for g in TEXT_GAPS], ids=[g[0] for g in TEXT_GAPS])
def test_the_text_scan_gaps_stay_out_of_reach(text):
    assert not _text_mention_counts(text)


def test_the_scan_reads_every_tree_that_can_reach_the_database(tmp_path):
    scanned_paths = {"backend/app/a.py", "backend/migrations/m.sql", "ops/detection/d.sql", "scripts/s.sh", "tasks/x/t.sql",
                     "docs/runbooks/r.sh", ".claude/skills/k/k.sh", ".github/workflows/w.yml", "main.yaml"}
    skipped = {"frontend/f.py", "backend/tests/unit/t.py", "frontend/tests/e2e/e.py", ".claude/worktrees/agent/backend/app/a.py",
               ".worktrees/other/ops/d.sql", "backend/app/__pycache__/c.py", "ops/node_modules/n.sh", "docs/runbook.md"}
    for rel in scanned_paths | skipped:
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text("x = 1\n")
    for checkout in (".claude/worktrees/agent", ".worktrees/other"):  # another tree, not this one
        (tmp_path / checkout / ".git").write_text("gitdir: elsewhere\n")
    assert {path.relative_to(tmp_path).as_posix() for path in _scanned_files(tmp_path)} == scanned_paths


def test_every_mention_of_the_successor_link_is_reviewed():
    found: Counter[tuple[str, str, str]] = Counter()
    for path in _scanned_files():
        rel = path.relative_to(REPO_DIR).as_posix()
        for (scope, kind), count in _file_mention_counts(path).items():
            found[(rel, scope, kind)] += count

    new = sorted((found - Counter(ALLOWED_MENTIONS)).items())
    stale = sorted((Counter(ALLOWED_MENTIONS) - found).items())
    assert not new and not stale, (
        f"{COLUMN} mentions changed. New, to review, then raise or add the listed count by the number "
        f"shown: {new}. Gone, to lower or remove by the number shown: {stale}. Only rotation may set the "
        "link, because the theft sweep reads it as proof of rotation "
        "(lessons/arch-only-a-rotated-refresh-token-signals-theft.md): list each reviewed mention in "
        "ALLOWED_MENTIONS with its count and reason. Kinds are syntactic, so review the line, not the label: a 'read', 'string', "
        "'keyword' or 'text' can be part of a write, and 'key' is the column as a mapping key, the shape "
        "of a row write. A 'delete' is any delete in a file in scope, whatever it removes (say what in its "
        "entry): ON DELETE SET NULL clears the link of a refresh token whose successor goes first. Dropping a "
        "token from the delete-orphan User.refresh_tokens deletes it too, so a member-dropping call on the "
        "collection, a store or del of it, of its items or of a .user attribute, and a merge are deletes. "
        "A 'dynamic' mention is a place in a file that names "
        "RefreshToken, its table, User.refresh_tokens or the column, or imports a refresh-token module, "
        "where a column could be picked at "
        "run time (setattr with a computed name, row data that is not a literal mapping, SQL assembled "
        "at run time, EXECUTE in a migration): "
        "spell the column out, or list it with why it cannot reach replaced_by_id. Swapping one mention "
        "for another of the same kind in the same scope (a text file is one scope) keeps the counts equal "
        "and is not seen."
    )
