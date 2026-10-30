"""Gate: only reviewed callers reach the unaudited account deletion (F19).

``user_account_service.delete_account`` is the account's own deletion (``DELETE /api/users/me``): it commits the
account's removal with its ``user_deleted`` audit row, or neither. ``delete_user`` deletes with no audit row, for
accounts no person asked to delete (the feedback-media verifier's fixtures), and both go through the private
``_delete_locked_account``. A route or job that reached either unaudited path, or deleted ``users`` rows itself, for a
person's own deletion would delete them unaudited, which F19 forbids. So this gate counts, per file, and holds the
counts to the reviewed allowlist below, so a new one fails until it is reviewed and listed:

* every reference to ``delete_user`` or ``_delete_locked_account``: a name, an attribute, an import, or the name as a
  string constant, as ``getattr`` and ``vars()`` take it;
* every delete of ``users`` rows it can see in Python. Naming the rows is the ``User`` model (an import alias of it,
  ``<module>.User``, ``aliased(User)``), its table (``User.__table__``, ``metadata.tables["users"]``,
  ``table("users")``, ``Table("users", ...)``), a lookup of it (a ``query``, ``get``, ``select``, ``scalar``,
  ``scalars``, ``execute``, ``filter``, ``filter_by`` or ``where`` call taking one of those or another lookup:
  ``db.query(User)...``, ``db.get(User, id)``, ``db.scalar(select(User)...)``), or a name the module binds to any of
  those. A binding is an assignment (element by element for ``a, b = x, y``), a walrus, a ``for`` or comprehension
  over a value, or a ``with ... as``; only plain names are bound, not ``self.x`` or ``d[k]``. Bindings are read
  module-wide: a name bound so anywhere in the module counts wherever it is used, over a local rebinding or a
  parameter of that name too. The forms: a ``delete`` call (under any import alias of ``delete``, or a name bound to
  one: ``drop = sa.delete``) with such an argument, positional or ``table=`` (``delete(User)``, ``db.delete(user)``);
  and ``.delete(...)`` on such a lookup or table, whatever its arguments (``db.query(User)...delete(False)``,
  ``q.delete()``, ``User.__table__.delete()``). These go by name, not type: any ``delete`` call so spelled counts (a
  cache's ``delete(User)`` too) and needs a reviewed entry saying it deletes no account;
* SQL that deletes ``users`` rows, in a Python string (a literal, a ``+`` of literals or an f-string's literal parts;
  docstrings are not code) or in a SQL, shell or workflow file read without its comments (``--`` and ``/* */`` in SQL,
  outside quoted strings; whole-line ``#`` comments in shell and workflow files): ``DELETE FROM users``, a
  ``TRUNCATE`` or ``DROP TABLE`` whose list of tables names ``users``, and ``MERGE INTO users ... DELETE``, in any
  case, quoted or not, with or without a schema. ``users`` references no other table, so a ``TRUNCATE ... CASCADE``
  of another cannot reach it.

``test_the_retention_purge_has_no_users_target`` pins the purge, whose ``delete(target.model)`` the scan cannot read.

The walk is ``test_replaced_by_id_writers_allowlist.py``'s (``_scanned_files``): the whole repository but the browser
app, the test homes and nested checkouts. Out of reach, stated so nothing is overclaimed (the Python forms each planted
in ``PLANTED_GAPS``): a name built at run time (``'delete_' + 'user'``); a model or table chosen at run time
(``getattr(models, name)``, ``delete(target.model)``); a row, model or query reached through a parameter
(``def drop(db, account): db.delete(account)``, ``def purge(db, model=User)``), unless the module binds that name to
one elsewhere, through an attribute or an item (``db.delete(request.state.user)``, ``db.delete(users[0])``; an
attribute of a row, ``user.subscription``, is a child row, not the account), through a helper's return, or bound in
another module; SQL
assembled from non-literals (``"DELETE FROM " + table``) or with ``%``, ``.format`` or ``str.join``; SQL quoted in
Markdown, which is read, not run; and a caller in a folder named ``tests`` outside the test homes
(``backend/app/tests/``), which the shared walk skips.
"""
import ast
import re
from pathlib import Path

from tests.unit.test_replaced_by_id_writers_allowlist import REPO_DIR, _scanned_files, _strip_sql_comments
from tests.unit.test_summary_delete_sites_allowlist import _docstring_ids, _folded

GUARDED = {"delete_user", "_delete_locked_account"}
MODEL = "User"
TABLE = "users"

# File -> references to the unaudited deletion and deletes of users rows. Each one is reviewed.
ALLOWED_REFERENCES = {
    # delete_account's and delete_user's own calls of the delete step they share, run under the lock they each take
    # first (``_delete_locked_account``), and that step's own delete of the locked row
    # (``db.delete(db.get(User, user_id))``).
    "backend/app/services/user_account_service.py": 3,
    # The verifier's own fixture accounts, created and removed by the verification run (its import and its call).
    "ops/feedback_media/verify_runtime.py": 2,
}

# A table name, schema-qualified or not, quoted or not; the table itself; and a list of names before it, so that a
# TRUNCATE or DROP TABLE counts only when users is among the tables it names (prose such as "never truncate a quote.
# Users rely on it" is not one).
_ID = r'(?:"?\w+"?\.)?"?\w+"?'
_T = rf'(?:"?\w+"?\.)?"?{TABLE}"?(?![\w"])'
_SQL_DELETE = re.compile(
    rf'\bDELETE\s+FROM\s+(?:ONLY\s+)?{_T}'
    rf'|\bTRUNCATE\s+(?:TABLE\s+)?(?:ONLY\s+)?(?:{_ID}\s*,\s*)*{_T}'
    rf'|\bDROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?(?:{_ID}\s*,\s*)*{_T}'
    rf'|\bMERGE\s+INTO\s+{_T}[^;]*?\bDELETE\b',
    re.IGNORECASE,
)
_TEXT_SUFFIXES = {".sql", ".sh", ".yml", ".yaml"}
_LOOKUPS = {"query", "get", "select", "scalar", "scalars", "execute", "filter", "filter_by", "where"}


def _sql_deletes(text: str) -> int:
    return len(_SQL_DELETE.findall(text))


def _text_deletes(text: str, suffix: str) -> int:
    """SQL deletes of users rows in a SQL, shell or workflow file, read without its comments."""
    if suffix == ".sql":
        text = _strip_sql_comments(text)
    else:
        text = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    return _sql_deletes(text)


def _name(func: ast.AST) -> str | None:
    return func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None


def _target_names(target: ast.AST) -> set[str]:
    """The plain names a binding target binds: ``x``, ``x, y``, ``*rest``; never ``self.x`` or ``d[k]``, which bind
    an attribute or an item, not the names inside them."""
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, (ast.Tuple, ast.List)):
        return set().union(*map(_target_names, target.elts))
    if isinstance(target, ast.Starred):
        return _target_names(target.value)
    return set()


def _bindings(tree: ast.AST) -> list[tuple[set[str], ast.AST]]:
    """Each (names, value) a module binds: an assignment (element by element for ``a, b = x, y``), a walrus, a ``for``
    or comprehension over a value, and a ``with ... as``."""
    pairs: list[tuple[ast.AST, ast.AST]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            pairs += [(target, node.value) for target in node.targets]
        elif isinstance(node, (ast.AnnAssign, ast.NamedExpr)) and node.value is not None:
            pairs.append((node.target, node.value))
        elif isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)):
            pairs.append((node.target, node.iter))
        elif isinstance(node, ast.withitem) and node.optional_vars is not None:
            pairs.append((node.optional_vars, node.context_expr))
    bindings = []
    for target, value in pairs:
        if (isinstance(target, (ast.Tuple, ast.List)) and isinstance(value, (ast.Tuple, ast.List))
                and len(target.elts) == len(value.elts)):
            bindings += [(_target_names(t), v) for t, v in zip(target.elts, value.elts)]
        else:
            bindings.append((_target_names(target), value))
    return [(names, value) for names, value in bindings if names]


class _Names:
    """What a module binds to the model, its table, a lookup of it, or ``delete``, by name, module-wide."""

    def __init__(self, tree: ast.Module) -> None:
        imported = [alias for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) for alias in node.names]
        self.models = {MODEL, *(alias.asname for alias in imported if alias.name == MODEL and alias.asname)}
        self.deletes = {"delete", *(alias.asname for alias in imported if alias.name == "delete" and alias.asname)}
        self.lookups: set[str] = set()
        bindings = _bindings(tree)
        for _round in range(8):  # names bound to names bound to the model: follow a few hops
            before = (len(self.models), len(self.lookups), len(self.deletes))
            for names, value in bindings:
                if self.model(value):
                    self.models |= names
                elif self.lookup(value):
                    self.lookups |= names
                elif self._delete_reference(value):
                    self.deletes |= names
            if (len(self.models), len(self.lookups), len(self.deletes)) == before:
                break

    def model(self, node: ast.AST) -> bool:
        """The model or its table: ``User``, an alias, ``models.User``, ``aliased(User)``, ``User.__table__``,
        ``metadata.tables["users"]``, ``table("users")``, ``Table("users", ...)``."""
        if isinstance(node, ast.Attribute) and node.attr == "__table__":
            return self.model(node.value)
        if isinstance(node, ast.Name):
            return node.id in self.models
        if isinstance(node, ast.Attribute):
            return node.attr == MODEL
        if isinstance(node, ast.Subscript):
            return (isinstance(node.value, ast.Attribute) and node.value.attr == "tables"
                    and isinstance(node.slice, ast.Constant) and node.slice.value == TABLE)
        if isinstance(node, ast.Call):
            name = _name(node.func)
            if name == "aliased":
                return bool(node.args) and self.model(node.args[0])
            if name in {"table", "Table"}:
                return bool(node.args) and isinstance(node.args[0], ast.Constant) and node.args[0].value == TABLE
        return False

    def lookup(self, node: ast.AST) -> bool:
        """A lookup of the model: a method chain holding ``query(User ...)``, ``get(User, ...)``, ``select(User)`` or the
        like, or starting from a name bound to one (``q.filter(...)``). The chain is followed through its calls only:
        an attribute of a row (``user.subscription``, ``user.id``) is not the row."""
        while isinstance(node, ast.Call):
            if _name(node.func) in _LOOKUPS and any(self.model(arg) or self.lookup(arg) for arg in node.args):
                return True  # query(User), get(User, id), select(User), scalar(select(User)), execute(stmt)
            node = node.func.value if isinstance(node.func, ast.Attribute) else node.func
        return isinstance(node, ast.Name) and node.id in self.lookups

    def _delete_reference(self, node: ast.AST) -> bool:
        return (isinstance(node, ast.Name) and node.id in self.deletes) or (
            isinstance(node, ast.Attribute) and node.attr == "delete")

    def rows(self, node: ast.AST) -> bool:
        return self.model(node) or self.lookup(node)


def references(source: str) -> int:
    tree = ast.parse(source)
    names = _Names(tree)
    docstrings = _docstring_ids(tree)
    folded: set[int] = set()
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in GUARDED:
            count += 1
        elif isinstance(node, ast.Attribute) and node.attr in GUARDED:
            count += 1
        elif isinstance(node, ast.ImportFrom):
            count += sum(1 for alias in node.names if alias.name in GUARDED)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value in GUARDED:
                count += 1
            if id(node) not in docstrings and id(node) not in folded:
                count += _sql_deletes(node.value)
        elif isinstance(node, (ast.JoinedStr, ast.BinOp)) and id(node) not in folded and (text := _folded(node)):
            # A `+` of literals or an f-string is read whole, and its parts are not read again.
            folded |= {id(part) for part in ast.walk(node)}
            count += _sql_deletes(text)
        elif isinstance(node, ast.Call) and _name(node.func) in names.deletes:
            func = node.func
            if isinstance(func, ast.Attribute) and names.rows(func.value):
                count += 1  # db.query(User)...delete(), .delete(False), q.delete(), User.__table__.delete()
            elif any(names.rows(arg) for arg in [*node.args, *(k.value for k in node.keywords if k.arg == "table")]):
                count += 1  # delete(User), delete(table=User), db.delete(user), db.delete(db.get(User, id))
    return count


def _scanned():
    for path in _scanned_files():
        if path.suffix == ".py" or path.suffix in _TEXT_SUFFIXES:
            yield path.relative_to(REPO_DIR).as_posix(), path


def _count(path: Path) -> int:
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    return references(text) if path.suffix == ".py" else _text_deletes(text, path.suffix)


def test_only_reviewed_callers_reach_the_unaudited_deletion():
    found = {}
    for relative, path in _scanned():
        if count := _count(path):
            found[relative] = count
    assert found == ALLOWED_REFERENCES, (
        "A reference to the unaudited account deletion (user_account_service.delete_user, _delete_locked_account, or "
        "a delete of users rows) is new or gone. A person's own deletion goes through delete_account (F19); list a "
        "deliberate unaudited deletion here after review."
    )


def test_the_retention_purge_has_no_users_target():
    from app.models import User
    from app.services.retention_service import purge_targets
    from app.utils.datetimes import utcnow

    assert all(target.model not in (User, User.__table__) for target in purge_targets(utcnow())), (
        "the retention purge deletes users rows, unaudited (F19)"
    )


PLANTED_COUNTED = {
    "a module call": "from app.services import user_account_service\nuser_account_service.delete_user(db, 1)\n",
    "an imported name": "from app.services.user_account_service import delete_user\ndelete_user(db, 1)\n",
    "an import alias": "from app.services.user_account_service import delete_user as drop\ndrop(db, 1)\n",
    "a reference passed on": "run_in_threadpool(user_account_service.delete_user, db, 1)\n",
    "the private step": "user_account_service._delete_locked_account(db, 1)\n",
    "getattr with the name": "getattr(user_account_service, 'delete_user')(db, 1)\n",
    "vars() with the name": "vars(user_account_service)['_delete_locked_account'](db, 1)\n",
    "a query delete of User rows": "db.query(User).filter(User.id == 1).delete()\n",
    "a core delete of User": "db.execute(delete(User).where(User.id == 1))\n",
    "a module-qualified core delete": "db.execute(sa.delete(User).where(User.id == 1))\n",
    "an aliased core delete": "from sqlalchemy import delete as sa_delete\ndb.execute(sa_delete(User))\n",
    "a core delete by keyword": "db.execute(delete(table=User).where(User.id == 1))\n",
    "the table's own delete": "db.execute(User.__table__.delete())\n",
    "a core delete of the table": "db.execute(delete(User.__table__).where(User.__table__.c.id == 1))\n",
    "the table by its name": "db.execute(Base.metadata.tables['users'].delete())\n",
    "a table clause by its name": "db.execute(delete(table('users')))\n",
    "an aliased model's query delete": "from app.models import User as Account\ndb.query(Account).delete()\n",
    "a module-qualified model's query delete": "db.query(models.User).filter(models.User.id == 1).delete()\n",
    "an aliased() entity": "db.query(aliased(User)).delete()\n",
    "the model bound to a name": "Account = User\ndb.execute(delete(Account))\n",
    "the table bound to a name": "table = User.__table__\ndb.execute(table.delete())\n",
    "the delete bound to a name": "drop = sa.delete\ndb.execute(drop(User))\n",
    "a query bound to a name": "stale = db.query(User).filter(User.id == 1)\nstale.delete(synchronize_session=False)\n",
    "a looked-up row deleted": "user = db.get(User, 1)\ndb.delete(user)\n",
    "a lookup deleted in place": "db.delete(db.get(User, 1))\n",
    "raw SQL": "db.execute(text('DELETE FROM users WHERE id = :id'), {'id': 1})\n",
    "raw SQL with a schema, quoted": 'cursor.execute(\'delete from public."users" where id = 1\')\n',
    "raw SQL from literals": "db.execute(text('DELETE FROM ' + 'users WHERE id = 1'))\n",
    "raw SQL in an f-string": "db.execute(text(f'DELETE FROM users WHERE id = {user_id}'))\n",
    "a truncate": "db.execute(text('TRUNCATE users CASCADE'))\n",
    "a truncate of several tables": "db.execute(text('TRUNCATE TABLE refresh_tokens, public.users'))\n",
    "a drop": "db.execute(text('DROP TABLE IF EXISTS users'))\n",
    "a row selected and deleted": "user = db.scalar(select(User).where(User.id == 1))\ndb.delete(user)\n",
    "a select deleted in place": "db.delete(db.scalars(select(User)).first())\n",
    "a statement bound, then run": "stmt = select(User).where(User.id == 1)\nuser = db.execute(stmt).scalar_one()\ndb.delete(user)\n",
    "rows deleted in a loop": "for user in db.query(User).filter(User.id > 1).all():\n    db.delete(user)\n",
    "rows deleted in a comprehension": "[db.delete(user) for user in db.query(User).all()]\n",
    "a row bound by a walrus": "if (user := db.get(User, 1)) is not None:\n    db.delete(user)\n",
    "a row bound in a tuple": "user, token = db.get(User, 1), db.get(RefreshToken, 2)\ndb.delete(user)\n",
    "a query delete with positional options": "db.query(User).filter(User.id == 1).delete(False)\n",
}
PLANTED_LOOK_ALIKES = {
    "the audited deletion": "user_account_service.delete_account(db, 1, third_party_results={})\n",
    "another table's query delete": "db.query(RefreshToken).filter(RefreshToken.user_id == 1).delete()\n",
    "another table's core delete": "db.execute(delete(RefreshToken).where(RefreshToken.user_id == 1))\n",
    "another table's qualified core delete": "db.execute(sa.delete(RefreshToken))\n",
    "another table's own delete": "db.execute(RefreshToken.__table__.delete())\n",
    "another table by its name": "db.execute(Base.metadata.tables['user_searches'].delete())\n",
    "another row looked up and deleted": "token = db.get(RefreshToken, 1)\ndb.delete(token)\n",
    "a route registered for deletion": "@router.delete('/me')\nasync def delete_me(user: User = Depends(current_user)):\n    pass\n",
    "SQL of a table that only starts with the name": "db.execute(text('DELETE FROM users_archive'))\n",
    "SQL of another table": "db.execute(text('DELETE FROM user_searches WHERE user_id = 1'))\n",
    "SQL in a docstring": "def f():\n    '''DELETE FROM users, as the docs say.'''\n",
    "a name that only contains it": "undelete_user_cache.clear()\n",
    "another row selected and deleted": "db.delete(db.scalar(select(RefreshToken)))\n",
    "another row in a tuple": "user, token = db.get(User, 1), db.get(RefreshToken, 2)\ndb.delete(token)\n",
    "a row on an attribute, then another attribute deleted": (
        "def a(self, db):\n    self.user = db.get(User, 1)\n"
        "def b(self):\n    self.storage.delete(self.key)\n"),
    "a child row of a looked-up account": "user = db.get(User, 1)\ndb.delete(user.subscription)\n",
    "a child row's own lookup": "user = db.get(User, 1)\ndb.delete(db.get(NotificationPreference, user.id))\n",
    "the account's tokens in a loop": "user = db.get(User, 1)\nfor token in user.refresh_tokens:\n    db.delete(token)\n",
    "prose that says truncate, then users": "logger.warning('Refusing to truncate the export for %d users', n)\n",
    "prose that says drop table, then users": "msg = 'cannot drop table rows owned by users'\n",
    "a truncate of another table, then users": "db.execute(text('TRUNCATE companies; SELECT * FROM users'))\n",
}
# The stated gaps: each reaches the unaudited deletion, and the scan counts none of them.
PLANTED_GAPS = {
    "a name built at run time": "getattr(user_account_service, 'delete_' + 'user')(db, 1)\n",
    "a model chosen at run time": "db.execute(delete(target.model))\n",
    "a row handed in": "def drop(db, account):\n    db.delete(account)\n",
    "a model as a parameter default": "def purge(db, model=User):\n    db.execute(delete(model))\n",
    "SQL assembled from a non-literal": "db.execute(text('DELETE FROM ' + table))\n",
    "SQL formatted with %": "db.execute(text('DELETE FROM %s' % table))\n",
    "SQL formatted with .format": "db.execute(text('DELETE FROM {}'.format('users')))\n",
    "SQL joined": "db.execute(text(' '.join(['DELETE FROM', 'users'])))\n",
    "a model got by name": "db.execute(delete(getattr(models, 'User')))\n",
    "a row on an attribute": "db.delete(request.state.user)\n",
    "a row from a helper": "db.delete(_find_account(db, 1))\n",
    "a row by item": "users = db.query(User).all()\ndb.delete(users[0])\n",
    "a model bound in another module": "from app.services.accounts import ACCOUNT_MODEL\ndb.execute(delete(ACCOUNT_MODEL))\n",
    "a table chosen by a run-time name": "db.execute(Base.metadata.tables[name].delete())\n",
}


def test_the_walk_counts_the_planted_forms_and_states_its_gaps():
    assert {name: references(source) for name, source in PLANTED_COUNTED.items()} == {
        # An imported name counts at its import and its call; an alias at its import only.
        name: (2 if name == "an imported name" else 1) for name in PLANTED_COUNTED
    }
    assert {name: references(source) for name, source in {**PLANTED_LOOK_ALIKES, **PLANTED_GAPS}.items()} == dict.fromkeys(
        {**PLANTED_LOOK_ALIKES, **PLANTED_GAPS}, 0
    )


def test_the_text_scan_reads_sql_without_its_comments():
    assert _text_deletes("DELETE FROM users WHERE id = 1;\n-- DELETE FROM users\n/* TRUNCATE users */", ".sql") == 1
    assert _text_deletes("INSERT INTO t VALUES ('a--b'); DELETE FROM users;", ".sql") == 1
    assert _text_deletes("psql -c 'DELETE FROM users'\n# DELETE FROM users\n", ".sh") == 1
    assert _text_deletes("DELETE FROM user_searches;\nTRUNCATE companies CASCADE;", ".sql") == 0


def test_the_walk_reads_the_files_it_guards():
    scanned = {relative for relative, _path in _scanned()}
    assert {
        "backend/app/routers/users.py", "backend/app/services/user_account_service.py",
        "ops/feedback_media/verify_runtime.py", "backend/main.py",
    } <= scanned
    assert any(relative.endswith(".sql") for relative in scanned)
    assert not any(part == "tests" for relative in scanned for part in Path(relative).parts)
