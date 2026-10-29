"""Gate: only reviewed callers reach the unaudited account deletion (F19).

``user_account_service.delete_account`` is the account's own deletion (``DELETE /api/users/me``): it commits the
account's removal with its ``user_deleted`` audit row, or neither. ``delete_user`` deletes with no audit row, for
accounts no person asked to delete (the feedback-media verifier's fixtures), and both go through the private
``_delete_locked_account``. A route or job that reached either unaudited path for a person's own deletion would
delete them unaudited, which F19 forbids. So this gate counts, per file, every reference to ``delete_user`` or
``_delete_locked_account`` (a name, an attribute, an import, or the name as a string constant, as ``getattr`` and
``vars()`` take it), and every direct ORM delete of ``User`` rows (``query(User)...delete()``, ``delete(User)`` or
``delete(User.__table__)`` however ``delete`` or ``User`` is imported or qualified, and ``User.__table__.delete()``),
in every Python file the repository holds outside the browser app and the test homes, the defining module included,
and holds the counts to the reviewed allowlist below: a new one fails until it is reviewed and listed.

The walk is ``test_replaced_by_id_writers_allowlist.py``'s (``_scanned_files``), Python files only. What it cannot
see, left to review: the name built at run time (``'delete_' + 'user'``), and an instance delete through the session
(``db.delete(account)``), which reads like any other row's delete, and the table or the ``delete`` bound to a name first
(``table = User.__table__``, then ``table.delete()``; ``drop = sa.delete``, then ``drop(User)``), each planted in
``PLANTED_GAPS``; and a caller in a folder named ``tests`` outside the test homes (``backend/app/tests/``), which the
shared walk skips.
"""
import ast
from pathlib import Path

from tests.unit.test_replaced_by_id_writers_allowlist import REPO_DIR, _scanned_files

GUARDED = {"delete_user", "_delete_locked_account"}

# File -> references to the unaudited deletion. Each one is reviewed.
ALLOWED_REFERENCES = {
    # delete_account's and delete_user's own calls of the shared lock-and-cascade step.
    "backend/app/services/user_account_service.py": 2,
    # The verifier's own fixture accounts, created and removed by the verification run (its import and its call).
    "ops/feedback_media/verify_runtime.py": 2,
}


def _is_user(node: ast.AST, user_names: set[str]) -> bool:
    """Whether an expression names the ``User`` model or its table: ``User``, a name it is imported as,
    ``models.User``, or any of those's ``__table__``."""
    if isinstance(node, ast.Attribute) and node.attr == "__table__":
        node = node.value
    return (isinstance(node, ast.Name) and node.id in user_names) or (
        isinstance(node, ast.Attribute) and node.attr == "User")


def _query_of_user(node: ast.AST, user_names: set[str]) -> bool:
    """Whether an expression chain holds a ``.query(User ...)`` call (``db.query(User).filter(...)``)."""
    while True:
        if isinstance(node, ast.Call):
            func = node.func
            if (isinstance(func, ast.Attribute) and func.attr == "query"
                    and any(_is_user(arg, user_names) for arg in node.args)):
                return True
            node = func
        elif isinstance(node, ast.Attribute):
            node = node.value
        else:
            return False


def references(source: str) -> int:
    tree = ast.parse(source)
    imported = [alias for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) for alias in node.names]
    user_names = {"User", *(alias.asname for alias in imported if alias.name == "User" and alias.asname)}
    delete_names = {"delete", *(alias.asname for alias in imported if alias.name == "delete" and alias.asname)}
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in GUARDED:
            count += 1
        elif isinstance(node, ast.Attribute) and node.attr in GUARDED:
            count += 1
        elif isinstance(node, ast.ImportFrom):
            count += sum(1 for alias in node.names if alias.name in GUARDED)
        elif isinstance(node, ast.Constant) and node.value in GUARDED:
            count += 1
        elif isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
            if name not in delete_names:
                continue
            if isinstance(func, ast.Attribute) and (
                    _query_of_user(func.value, user_names)
                    or (isinstance(func.value, ast.Attribute) and func.value.attr == "__table__"
                        and _is_user(func.value, user_names))):
                count += 1  # query(User)...delete(), User.__table__.delete()
            elif any(_is_user(arg, user_names) for arg in node.args):
                count += 1  # delete(User), sa.delete(User), delete(User.__table__), an alias of delete
    return count


def _python_files():
    for path in _scanned_files():
        if path.suffix == ".py":
            yield path.relative_to(REPO_DIR).as_posix(), path


def test_only_reviewed_callers_reach_the_unaudited_deletion():
    found = {}
    for relative, path in _python_files():
        count = references(path.read_text(encoding="utf-8-sig"))
        if count:
            found[relative] = count
    assert found == ALLOWED_REFERENCES, (
        "A reference to the unaudited account deletion (user_account_service.delete_user, _delete_locked_account, or "
        "a direct ORM delete of User rows) is new or gone. A person's own deletion goes through delete_account (F19); "
        "list a deliberate unaudited deletion here after review."
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
    "the table's own delete": "db.execute(User.__table__.delete())\n",
    "a core delete of the table": "db.execute(delete(User.__table__).where(User.__table__.c.id == 1))\n",
    "an aliased model's query delete": "from app.models import User as Account\ndb.query(Account).delete()\n",
    "a module-qualified model's query delete": "db.query(models.User).filter(models.User.id == 1).delete()\n",
}
PLANTED_LOOK_ALIKES = {
    "the audited deletion": "user_account_service.delete_account(db, 1, third_party_results={})\n",
    "another table's query delete": "db.query(RefreshToken).filter(RefreshToken.user_id == 1).delete()\n",
    "another table's core delete": "db.execute(delete(RefreshToken).where(RefreshToken.user_id == 1))\n",
    "another table's qualified core delete": "db.execute(sa.delete(RefreshToken))\n",
    "another table's own delete": "db.execute(RefreshToken.__table__.delete())\n",
    "a name that only contains it": "undelete_user_cache.clear()\n",
}
# The walk's stated gaps: each reaches the unaudited deletion, and it counts none of them.
PLANTED_GAPS = {
    "a name built at run time": "getattr(user_account_service, 'delete_' + 'user')(db, 1)\n",
    "an instance delete through the session": "db.delete(account)\ndb.commit()\n",
    "the table bound to a name": "table = User.__table__\ndb.execute(table.delete())\n",
    "the delete bound to a name": "drop = sa.delete\ndb.execute(drop(User))\n",
}


def test_the_walk_counts_the_planted_forms_and_states_its_gaps():
    assert {name: references(source) for name, source in PLANTED_COUNTED.items()} == {
        # An imported name counts at its import and its call; an alias at its import only.
        name: (2 if name == "an imported name" else 1) for name in PLANTED_COUNTED
    }
    assert {name: references(source) for name, source in {**PLANTED_LOOK_ALIKES, **PLANTED_GAPS}.items()} == dict.fromkeys(
        {**PLANTED_LOOK_ALIKES, **PLANTED_GAPS}, 0
    )


def test_the_walk_reads_the_files_it_guards():
    scanned = {relative for relative, _path in _python_files()}
    assert {
        "backend/app/routers/users.py", "backend/app/services/user_account_service.py",
        "ops/feedback_media/verify_runtime.py", "backend/main.py",
    } <= scanned
    assert not any(part == "tests" for relative in scanned for part in Path(relative).parts)
