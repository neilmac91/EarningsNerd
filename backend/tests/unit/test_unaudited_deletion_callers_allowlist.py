"""Gate: only reviewed callers delete an account without its audit row (F19).

``user_account_service.delete_account`` is the account's own deletion (``DELETE /api/users/me``): it commits the
account's removal with its ``user_deleted`` audit row, or neither. ``user_account_service.delete_user`` deletes with
no audit row, for accounts no person asked to delete: the feedback-media verifier's fixture accounts. A route or job
that called ``delete_user`` for a person's own deletion would delete them unaudited, which F19 forbids. This gate
counts every reference to ``delete_user`` outside its own module and the test homes, per file, and holds the counts
to the reviewed allowlist below: a new caller fails until it is reviewed and listed.

The walk reads every Python file under ``backend/`` (the app, the entrypoints, ``scripts/``) and ``ops/`` through
``ast`` and counts each name, attribute or import named ``delete_user``. It cannot see the function reached by a
computed name (``getattr`` with a built string) or through an alias assigned at run time; review covers those.
"""
import ast
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DEFINING_MODULE = "backend/app/services/user_account_service.py"
SCANNED_ROOTS = ("backend", "ops")

# File -> references to delete_user. Each entry is a deletion no person asked for.
ALLOWED_REFERENCES = {
    # The verifier's own fixture accounts, created and removed by the verification run.
    "ops/feedback_media/verify_runtime.py": 2,
}


def references(source: str) -> int:
    count = 0
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Name) and node.id == "delete_user":
            count += 1
        elif isinstance(node, ast.Attribute) and node.attr == "delete_user":
            count += 1
        elif isinstance(node, ast.ImportFrom):
            count += sum(1 for alias in node.names if alias.name == "delete_user")
    return count


def _scanned_files():
    for root in SCANNED_ROOTS:
        for path in sorted((REPO / root).rglob("*.py")):
            relative = path.relative_to(REPO).as_posix()
            parts = set(path.relative_to(REPO).parts)
            if relative == DEFINING_MODULE or "tests" in parts or "__pycache__" in parts:
                continue
            yield relative, path


def test_only_reviewed_callers_delete_an_account_without_its_audit_row():
    found = {}
    for relative, path in _scanned_files():
        count = references(path.read_text(encoding="utf-8"))
        if count:
            found[relative] = count
    assert found == ALLOWED_REFERENCES, (
        "A new reference to user_account_service.delete_user deletes an account with no audit row. A person's own "
        "deletion goes through delete_account (F19); list a deliberate unaudited deletion here after review."
    )


PLANTED_COUNTED = {
    "a module call": "from app.services import user_account_service\nuser_account_service.delete_user(db, 1)\n",
    "an imported name": "from app.services.user_account_service import delete_user\ndelete_user(db, 1)\n",
    "an import alias": "from app.services.user_account_service import delete_user as drop\ndrop(db, 1)\n",
    "a reference passed on": "run_in_threadpool(user_account_service.delete_user, db, 1)\n",
}
PLANTED_NOT_COUNTED = {
    "the audited deletion": "user_account_service.delete_account(db, 1, third_party_results={})\n",
    "a computed name (a stated gap)": "getattr(user_account_service, 'delete_' + 'user')(db, 1)\n",
}


def test_the_walk_counts_the_planted_references():
    assert {name: references(source) > 0 for name, source in PLANTED_COUNTED.items()} == dict.fromkeys(
        PLANTED_COUNTED, True
    )
    assert {name: references(source) for name, source in PLANTED_NOT_COUNTED.items()} == dict.fromkeys(
        PLANTED_NOT_COUNTED, 0
    )


def test_the_walk_reads_the_files_it_guards():
    scanned = {relative for relative, _path in _scanned_files()}
    assert {"backend/app/routers/users.py", "ops/feedback_media/verify_runtime.py", "backend/main.py"} <= scanned
    assert DEFINING_MODULE not in scanned
