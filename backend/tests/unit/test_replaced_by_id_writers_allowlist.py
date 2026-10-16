"""Structural gate: only refresh-token rotation writes ``RefreshToken.replaced_by_id``.

``refresh_token_service.rotate_refresh_token`` revokes every live token of the user when a revoked
token with ``replaced_by_id`` set is presented, reading the link as proof that the token was rotated
away and that someone else holds its successor. That reading is sound only while rotation is the one
writer. A revocation path or a session transfer that set the link would send its tokens down the
theft sweep again, which is the bug ``test_refresh_token_revocation_kinds.py`` pins for the writers
that exist today.

A writer can reach the column in more spellings than a write-only scan sees: an alias
(``successor = RefreshToken.replaced_by_id`` then ``.update({successor: value})``), ``setattr`` or
``getattr`` with the name, ``sqlalchemy.column("replaced_by_id")``, or a name computed at run time
(``setattr(token, "_".join(("replaced", "by", "id")), value)``). So this gate counts every MENTION of
the column in ``backend/app``, reads included, as (file, enclosing function or class, kind) with how
many times each occurs, and holds that equal to ``ALLOWED_MENTIONS``: any new mention, read or write,
fails until it is reviewed and listed, including a second one inside an already-listed scope. A
mention is an attribute access in any context, a bare name, a keyword argument, or a string outside a
docstring that contains the name, whether a literal or an expression built only from literals
(concatenation, ``%``, an f-string, ``str.join``, ``str.format`` and the case and replace methods are
folded). Comments and docstrings are not code and are not counted.

A name built from anything else (a variable, a loop over the table's columns, a row copied from
another) cannot be read off the source, so every module that names the model, its table or
``User.refresh_tokens`` also has each place a column could be chosen at run time counted as a
``dynamic`` mention:
- a call that takes an attribute name (``setattr``, ``getattr``, ``delattr``, ``hasattr``,
  ``__setattr__``, ``object.__setattr__``, ``set_attribute``, ``set_committed_value``) with a name that
  is not spelled out, positionally or by keyword, or with ``*args``; such a function handed on as a
  value (``partial(setattr, t)``, ``put = setattr``);
- raw SQL or a column built from a non-literal (``text``, ``column``, ``literal_column``,
  ``exec_driver_sql``), under any import alias;
- a ``**mapping`` argument;
- row data, positional or keyword (``params``, ``parameters``, ``mappings``, ``values``, ``set_``),
  handed to ``update``, ``values``, ``ordered_values``, ``execute``, ``executemany``,
  ``on_conflict_do_update`` or a ``bulk_*_mappings`` call, unless it is a literal mapping (or list of
  them) whose keys are literals or attributes of an imported class such as
  ``RefreshToken.revoked_at``; so ``.update(carried)``, ``{col.name: v}``, ``dict(row)`` and a
  constant the module picked from the columns all count, and so does any other mapping argument
  with such a key;
- a by-name lookup in ``.c``, ``.columns``, ``.attrs``, ``.all_orm_descriptors`` and the like,
  directly, through ``.get`` or through a name bound to one.

Out of reach, planted as named gaps (``test_the_named_gaps_stay_out_of_reach``): a module that names
none of those and writes an attribute by a name it did not build from literals (a generic helper
handed a token); a name assembled by code the folder does not evaluate; and a whole-row copy that
moves every column without naming one (``insert(...).from_select`` over the table's columns, or
``make_transient`` and re-adding the row). ``test_the_mention_scan_scores_every_planted_form`` scores
the scan on planted bypasses and look-alikes.
"""
import ast
from collections import Counter
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[2] / "app"
COLUMN = "replaced_by_id"

# Every mention of the successor link in backend/app, as (file, scope, kind) -> how many times. The
# count matters: a second write inside an already-listed scope is a new mention too. Rotation is the
# only writer; its own presence check is the only reader; the model defines the column.
ALLOWED_MENTIONS = {
    ("services/refresh_token_service.py", "rotate_refresh_token", "read"): 1,
    ("services/refresh_token_service.py", "rotate_refresh_token", "write"): 1,
    ("models/refresh_token.py", "RefreshToken", "definition"): 1,
    # Dynamic-name sinks in a module that names RefreshToken (the model registry imports it): they
    # read Filing's two URL columns by a name from _FILING_URL_FIELDS (getattr, and the attribute
    # state lookup) and cannot reach refresh_tokens.
    ("models/__init__.py", "_validate_filing_url", "dynamic"): 1,
    ("models/__init__.py", "validate_filing_before_update", "dynamic"): 2,
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
        self._stack: list[str] = []

    def _scoped(self, node: ast.AST, name: str) -> None:
        self._stack.append(name)
        self.generic_visit(node)
        self._stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._scoped(node, node.name)

    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._scoped(node, node.name)

    def _record(self, kind: str) -> None:
        self.mentions[(self._stack[-1] if self._stack else "<module>", kind)] += 1

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr == COLUMN:
            self._record("read" if isinstance(node.ctx, ast.Load) else "write")
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id == COLUMN:
            self._record("definition" if isinstance(node.ctx, ast.Store) else "name")
        # A sink handed on as a value (``partial(setattr, t)``, ``map(setattr, ...)``, ``put = setattr``)
        # is called where its name argument cannot be seen.
        if (self._in_scope and isinstance(node.ctx, ast.Load) and id(node) not in self._called
                and self._module.sink(node.id) in _SINK_NAMES):
            self._record("dynamic")

    def visit_keyword(self, node: ast.keyword) -> None:
        if node.arg == COLUMN:
            self._record("keyword")
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, str) and COLUMN in node.value and id(node) not in self._docstrings:
            self._record("string")

    def _built_string(self, node: ast.expr) -> None:
        folded = _fold(node)
        if folded is not None and COLUMN in folded:
            self._record("string")

    def visit_BinOp(self, node: ast.BinOp) -> None:
        self._built_string(node)
        self.generic_visit(node)

    def visit_JoinedStr(self, node: ast.JoinedStr) -> None:
        self._built_string(node)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        self._called.add(id(node.func))
        self._built_string(node)
        if self._in_scope and _dynamic_sink(node, self._module):
            self._record("dynamic")
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        if self._in_scope and _keyed_collection(node.value, self._module) and _fold(node.slice) is None:
            self._record("dynamic")
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
        items = node.right.elts if isinstance(node.right, ast.Tuple) else [node.right]
        args = [_fold(item) for item in items]
        if any(arg is None for arg in args):
            return None
        try:
            return left % tuple(args)
        except (TypeError, ValueError):
            return None
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in _FOLDED_METHODS:
        owner = _fold(node.func.value)
        if owner is None or node.keywords:
            return None
        if node.func.attr == "join":
            if len(node.args) != 1 or not isinstance(node.args[0], (ast.Tuple, ast.List)):
                return None
            items = [_fold(item) for item in node.args[0].elts]
            return None if any(item is None for item in items) else owner.join(items)
        args = [_fold(arg) for arg in node.args]
        if any(arg is None for arg in args):
            return None
        try:
            return getattr(owner, node.func.attr)(*args)
        except (TypeError, ValueError, IndexError, KeyError, AttributeError):
            return None
    return None


_SINK_NAMES = set(_NAME_FUNCTIONS) | _SQL_FUNCTIONS
# Keywords that carry row data, a column or attribute name, or SQL text.
_DATA_KEYWORDS = {"params", "values", "parameters", "mappings", "set_"}
_NAME_KEYWORDS = {"name", "key", "attr"}
_SQL_KEYWORDS = {"text", "statement", "sql", "name"}


class _Module:
    """What the scan needs from the whole module: the names it imports (a key such as
    ``RefreshToken.revoked_at`` counts as spelled out only on an imported class), local aliases of the
    sink functions (``from sqlalchemy import text as sa_text``, ``put = setattr``), and names bound to
    a by-name lookup collection (``COLS = RefreshToken.__table__.c``)."""

    def __init__(self, tree: ast.AST) -> None:
        self.imported: set[str] = set()
        self.aliases: dict[str, str] = {}
        self.keyed: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    self.imported.add(alias.asname or alias.name.split(".")[0])
                    original = alias.name.split(".")[-1]
                    if alias.asname and original in _SINK_NAMES:
                        self.aliases[alias.asname] = original
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in (t for t in targets if isinstance(t, ast.Name)):
                    if isinstance(node.value, ast.Attribute) and node.value.attr in _KEYED_ATTRS:
                        self.keyed.add(target.id)
                    if isinstance(node.value, ast.Name) and node.value.id in _SINK_NAMES:
                        self.aliases[target.id] = node.value.id

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
    return isinstance(key, ast.Attribute) and isinstance(key.value, ast.Name) and key.value.id in module.imported


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
        at = _NAME_FUNCTIONS[callee]
        bound = isinstance(node.func, ast.Attribute) and callee.startswith("__")
        if bound and isinstance(node.func.value, ast.Name) and node.func.value.id in ("object", "type"):
            at = 1  # object.__setattr__(t, name, v): the instance comes first
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
    """Whether a module names ``RefreshToken``, its table or ``User.refresh_tokens``, outside
    docstrings (a table name built from literals counts)."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == "RefreshToken":
            return True
        if isinstance(node, ast.Attribute) and node.attr in ("RefreshToken", "refresh_tokens"):
            return True
        if isinstance(node, ast.alias) and node.name.split(".")[-1] in ("RefreshToken", "refresh_token"):
            return True
        if isinstance(node, (ast.Constant, ast.JoinedStr, ast.BinOp, ast.Call)) and id(node) not in docstrings:
            folded = _fold(node)
            if folded is not None and ("refresh_tokens" in folded or "RefreshToken" in folded):
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
     {("f", "read")}),
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
    # Names built from literals are folded, in any module.
    ("joined-name-then-setattr",
     "def f(t, v):\n    key = '_'.join(('replaced', 'by', 'id'))\n    setattr(t, key, v)\n", {("f", "string")}),
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

# Named gaps: what the scan cannot see. A case that starts being counted moves to PLANTED.
GAPS = [
    ("generic-helper-handed-a-token",
     "def stamp(obj, field, value):\n    setattr(obj, field, value)\n\ndef revoke(t, field, v):\n"
     "    stamp(t, field, v)\n"),
    ("name-from-code-the-folder-does-not-run",
     "def f(t, v):\n    setattr(t, ''.join(reversed('di_yb_decalper')), v)\n"),
    # Whole-row copies move every column, the link included, without naming one.
    ("insert-from-select-copy",
     "from app.models import RefreshToken\n\ndef f(db, uid):\n    t = RefreshToken.__table__\n"
     "    cols = [c for c in t.columns if c.name != 'id']\n"
     "    db.execute(insert(t).from_select(cols, select(*cols).where(t.c.user_id == uid)))\n"),
    ("transient-copy",
     "from app.models import RefreshToken\n\ndef f(db, old, h):\n    make_transient(old)\n    old.id = None\n"
     "    old.token_hash = h\n    db.add(old)\n"),
]


@pytest.mark.parametrize("source, expected", [p[1:] for p in PLANTED], ids=[p[0] for p in PLANTED])
def test_the_mention_scan_scores_every_planted_form(source, expected):
    assert _mentions(source) == expected


@pytest.mark.parametrize("source", [g[1] for g in GAPS], ids=[g[0] for g in GAPS])
def test_the_named_gaps_stay_out_of_reach(source):
    assert _mentions(source) == set()


def test_every_mention_of_the_successor_link_is_reviewed():
    found: Counter[tuple[str, str, str]] = Counter()
    for py in APP_DIR.rglob("*.py"):
        rel = py.relative_to(APP_DIR).as_posix()
        for (scope, kind), count in _mention_counts(py.read_text(encoding="utf-8")).items():
            found[(rel, scope, kind)] += count

    new = sorted((found - Counter(ALLOWED_MENTIONS)).items())
    stale = sorted((Counter(ALLOWED_MENTIONS) - found).items())
    assert not new and not stale, (
        f"{COLUMN} mentions changed. New, to review: {new}. Gone, to remove from ALLOWED_MENTIONS: "
        f"{stale}. Only rotation may set the link, because the theft sweep reads it as proof of "
        "rotation (lessons/arch-only-a-rotated-refresh-token-signals-theft.md): list a reviewed "
        "mention here with its count and reason. A 'dynamic' mention is a place in a module that "
        "names RefreshToken, its table or User.refresh_tokens where a column could be picked at run "
        "time (setattr with a computed name, row data that is not a literal mapping): spell the "
        "column out, or list it with why it cannot reach replaced_by_id."
    )
