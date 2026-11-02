"""Gate: every write-shaped mention of ``User.is_pro`` outside the test homes is reviewed (PB-02; CLAUDE.md rule 12).

The complimentary beta grant's revoke clears ``is_pro`` only for an account whose ledger row says the grant set it and
that holds no billing state (``complimentary_access_service``). That is safe only while every writer of the flag is
known: today ``subscription_sync``'s three (the Stripe webhook's mirror, its deletion handler, the retired reverse
trial) and the grant's two units. A new writer, such as an admin "make Pro" route, a repair script or a migration, could
set the flag on an account that also holds a grant, and a revoke would then clear a right the grant never gave; or it
could clear a grant's flag, which the readout reports as drift. So this gate finds, in every Python file under
``backend/`` (its test homes excepted), ``ops/``, ``scripts/`` and ``tasks/``, each write-shaped mention:

* ``assign``: an assignment to an ``is_pro`` attribute (plain, augmented or annotated, or one target of a tuple);
* ``keyword``: an ``is_pro=`` keyword argument (a constructor, ``values(is_pro=...)``, a response model);
* ``key``: ``"is_pro"`` or ``<model>.is_pro`` as a key of a mapping literal (``update({...})``, a payload);
* ``setattr``: ``setattr``/``set_attribute``/``__setattr__`` naming ``"is_pro"``;
* ``string``: any other string literal outside a docstring that names ``is_pro`` (raw SQL), except the name a
  ``getattr``/``hasattr`` or a ``.get`` reads;

and in every SQL, shell and workflow file, each line naming ``is_pro`` outside a comment (``text``). It holds the counts,
per (path, enclosing function or class, kind), equal to ``REVIEWED``, whose comments say why each is or is not a write
of the flag. A new one fails until it is reviewed and listed; the reviewer confirms that a new writer of the flag never
touches an account a complimentary grant holds (or revokes the grant with it) and lists it.

Out of reach, said so nothing is overclaimed (each planted in ``OUT_OF_REACH``): a name built at run time
(``setattr(user, "is_" + "pro", True)``), a mapping that is not a literal handed on (``User(**fields)``,
``update(values)``), raw SQL assembled from pieces that are not literals, and a helper that is handed the attribute name.
"""
import ast
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PYTHON_ROOTS = ("backend", "ops", "scripts", "tasks")
SKIPPED = (ROOT / "backend" / "tests", ROOT / ".claude" / "worktrees")
TEXT_SUFFIXES = (".sql", ".sh", ".yml", ".yaml")
TEXT_ROOTS = ("backend", "ops", "scripts", "tasks", ".github")
_NAME = re.compile(r"\bis_pro\b", re.IGNORECASE)
_SETATTR = {"setattr", "set_attribute", "__setattr__"}
_READERS = {"getattr", "hasattr", "get"}

REVIEWED = {
    # The writers. The Stripe webhook's mirror of a subscription's state, written only for the account the event's
    # Stripe ids or checkout metadata name (an account with neither, as every complimentary grant's is, is never
    # reached): checkout and created/updated events through _apply_mirror, the deletion handler, and the retired
    # reverse trial (verify-email behind REVERSE_TRIAL_ENABLED, skipped for an account already Pro).
    ("backend/app/services/subscription_sync.py", "_apply_mirror", "assign"): 1,
    ("backend/app/services/subscription_sync.py", "apply_subscription_deleted", "assign"): 1,
    ("backend/app/services/subscription_sync.py", "start_reverse_trial", "assign"): 1,
    # The complimentary grant and its revoke (PB-02), each under the grants' lock and the account's row lock, only
    # for an account with no Subscription row and no Stripe ids; the revoke only where its own grant is active.
    ("backend/app/services/complimentary_access_service.py", "_grant_one", "assign"): 1,
    ("backend/app/services/complimentary_access_service.py", "_revoke_one", "assign"): 1,
    # Not writes: the flag read into a response or a payload. /api/auth/me, /api/users/profile, PATCH /api/users/me's
    # answer (its write is full_name alone) and the account export serve the raw mirror; /usage and /subscription
    # serve the resolved plan into their response models.
    ("backend/app/routers/auth.py", "get_current_user_info", "key"): 1,
    ("backend/app/routers/users.py", "get_profile", "key"): 1,
    ("backend/app/services/user_account_service.py", "apply_profile_update", "key"): 1,
    ("backend/app/services/user_data_export_service.py", "build_user_data_export", "key"): 1,
    ("backend/app/routers/subscriptions.py", "usage_for_reader", "keyword"): 1,
    ("backend/app/routers/subscriptions.py", "status_for_reader", "keyword"): 1,
    # The grant's and revoke's audit rows record the flag before and after in their details.
    ("backend/app/services/complimentary_access_service.py", "_state", "key"): 1,
    ("backend/app/services/complimentary_access_service.py", "_grant_one", "key"): 1,
    ("backend/app/services/complimentary_access_service.py", "_revoke_one", "key"): 1,
    # The critique harness's mock API serves canned /me, /subscription and /usage payloads; it has no database.
    ("tasks/critique-env-2026-10-04/mock_api.py", "<module>", "key"): 4,
    ("tasks/critique-env-2026-10-04/mock_api.py", "usage", "key"): 2,
    # The 2026-06-17 seed reads the flag into a new subscriptions row's plan (INSERT ... SELECT ... FROM users):
    # it writes no users column.
    ("backend/migrations/20260617_create_subscriptions_and_stripe_events.sql", "<file>", "text"): 1,
}

# Forms the scan must find, one count each (a planted module, scanned as a file under backend/app would be).
PLANTED = '''
"""A docstring naming is_pro is not a mention."""
from sqlalchemy import update


def plain(user):
    user.is_pro = True


def augmented(user):
    user.is_pro |= True


def annotated(user):
    user.is_pro: bool = False


def tupled(user, other):
    user.is_pro, other.x = True, 1


def keyword(db):
    db.add(User(email="a@example.invalid", is_pro=True))


def key(db):
    db.query(User).update({"is_pro": False})


def column_key(db):
    db.execute(update(User).values({User.is_pro: True}))


def named(user):
    setattr(user, "is_pro", True)


def raw(db):
    db.execute("UPDATE users SET IS_PRO = true")


def reads(user, row):
    return getattr(user, "is_pro", False), hasattr(user, "is_pro"), row.get("is_pro"), user.is_pro
'''
PLANTED_FOUND = {
    ("plain", "assign"): 1, ("augmented", "assign"): 1, ("annotated", "assign"): 1, ("tupled", "assign"): 1,
    ("keyword", "keyword"): 1, ("key", "key"): 1, ("column_key", "key"): 1, ("named", "setattr"): 1,
    ("raw", "string"): 1,
}
OUT_OF_REACH = '''
def built(user):
    setattr(user, "is_" + "pro", True)


def spread(db, fields):
    db.add(User(**fields))


def handed(db, values):
    db.query(User).update(values)


def assembled(db, column):
    db.execute("UPDATE users SET " + column + " = true")
'''


def _docstring_ids(tree: ast.AST) -> set[int]:
    ids = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                ids.add(id(first.value))
    return ids


def _targets(node: ast.AST):
    if isinstance(node, (ast.Tuple, ast.List)):
        for element in node.elts:
            yield from _targets(element)
    elif isinstance(node, ast.Starred):
        yield from _targets(node.value)
    else:
        yield node


def _is_flag(node: ast.AST) -> bool:
    return isinstance(node, ast.Attribute) and node.attr == "is_pro"


def _callee(call: ast.Call) -> str:
    return call.func.id if isinstance(call.func, ast.Name) else getattr(call.func, "attr", "")


def scan_python(source: str) -> Counter:
    """(enclosing function or class, kind) -> count, for one module's source."""
    tree = ast.parse(source)
    docstrings = _docstring_ids(tree)
    found: Counter = Counter()
    exempt: set[int] = set()  # string constants already classified (a key, a setattr name, a reader's name)

    def visit(node: ast.AST, scope: str) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            scope = node.name
        if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                found[(scope, "assign")] += sum(1 for t in _targets(target) if _is_flag(t))
        elif isinstance(node, ast.Call):
            found[(scope, "keyword")] += sum(1 for kw in node.keywords if kw.arg == "is_pro")
            name = _callee(node)
            if name in _SETATTR and len(node.args) >= 2 and isinstance(node.args[1], ast.Constant) \
                    and node.args[1].value == "is_pro":
                found[(scope, "setattr")] += 1
                exempt.add(id(node.args[1]))
            if name in _READERS:
                exempt.update(id(arg) for arg in node.args if isinstance(arg, ast.Constant))
        elif isinstance(node, ast.Dict):
            for key in node.keys:
                if isinstance(key, ast.Constant) and key.value == "is_pro":
                    found[(scope, "key")] += 1
                    exempt.add(id(key))
                elif key is not None and _is_flag(key):
                    found[(scope, "key")] += 1
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings \
                and id(node) not in exempt and _NAME.search(node.value):
            found[(scope, "string")] += 1
        for child in ast.iter_child_nodes(node):
            visit(child, scope)

    visit(tree, "<module>")
    return Counter({key: count for key, count in found.items() if count})


def _strip_comments(path: Path, text: str) -> str:
    if path.suffix == ".sql":
        text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
        return "\n".join(line.split("--", 1)[0] for line in text.splitlines())
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))


def _skipped(path: Path) -> bool:
    return any(path.is_relative_to(skipped) for skipped in SKIPPED)


def scan_repository() -> Counter:
    found: Counter = Counter()
    for root in PYTHON_ROOTS:
        for path in (ROOT / root).rglob("*.py"):
            if _skipped(path):
                continue
            rel = path.relative_to(ROOT).as_posix()
            for (scope, kind), count in scan_python(path.read_text(encoding="utf-8")).items():
                found[(rel, scope, kind)] += count
    for root in TEXT_ROOTS:
        for path in (ROOT / root).rglob("*"):
            if path.suffix not in TEXT_SUFFIXES or not path.is_file() or _skipped(path):
                continue
            text = _strip_comments(path, path.read_text(encoding="utf-8", errors="replace"))
            count = sum(1 for line in text.splitlines() if _NAME.search(line))
            if count:
                found[(path.relative_to(ROOT).as_posix(), "<file>", "text")] += count
    return found


def test_every_write_shaped_mention_of_is_pro_is_reviewed():
    found = scan_repository()
    new = sorted((found - Counter(REVIEWED)).items())
    gone = sorted((Counter(REVIEWED) - found).items())
    assert not new and not gone, (
        f"is_pro mentions changed. New, to review: {new}. Gone, to lower or remove: {gone}. A new writer of the flag "
        "must never set or clear it on an account a complimentary grant holds (complimentary_access_service), or the "
        "grant's revoke could clear a right it did not give; list a non-writer with its reason. See this module's "
        "docstring."
    )


def test_the_scan_finds_every_planted_write_form_and_names_its_gaps():
    assert scan_python(PLANTED) == Counter(PLANTED_FOUND)
    assert scan_python(OUT_OF_REACH) == Counter(), "the out-of-reach forms are documented gaps, not findings"
