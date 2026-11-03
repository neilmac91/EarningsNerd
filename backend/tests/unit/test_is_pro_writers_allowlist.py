"""Gate: every write-shaped mention of ``User.is_pro`` outside the test homes is reviewed (PB-02; CLAUDE.md rule 12).

The complimentary beta grant's revoke clears ``is_pro`` only for an account whose ledger row says the grant set it and
that holds no billing state (``complimentary_access_service``). That is safe only while every writer of the flag is
known: today ``subscription_sync``'s three (the Stripe webhook's mirror, its deletion handler, the retired reverse
trial) and the grant's two units. A new writer, such as an admin "make Pro" route, a repair script or a migration, could
set the flag on an account that also holds a grant, and a revoke would then clear a right the grant never gave; or it
could clear a grant's flag, which the readout reports as drift. So this gate walks the whole repository but the
browser app, the backend's test homes and anything that is not ours (``.claude/``, ``.github/``, any new folder and a
folder named ``tests`` outside the test homes included) and finds, in every Python
file, each write-shaped mention:

* ``assign``: an assignment to an ``is_pro`` attribute (plain, augmented or annotated, one target of a tuple, or the
  target of a ``for``, ``async for``, ``with ... as`` or comprehension);
* ``keyword``: an ``is_pro=`` keyword argument (a constructor, ``values(is_pro=...)``, a response model);
* ``key``: ``"is_pro"`` or ``<model>.is_pro`` as a key of a mapping literal (``update({...})``, a payload), or as the
  column of an ``ordered_values((<model>.is_pro, ...))`` pair;
* ``setattr``: ``setattr``/``set_attribute``/``__setattr__`` naming ``"is_pro"``;
* ``string``: any other string literal outside a docstring that names ``is_pro`` (raw SQL), except the name a
  ``getattr``/``hasattr`` or a ``.get`` reads;

and in every file with a ``.sql``, ``.sh``, ``.yml`` or ``.yaml`` suffix, or with none and a shell shebang (a git
hook), each line naming ``is_pro`` outside a comment (``text``; planted in ``PLANTED_TEXT``). It holds the counts,
per (path, enclosing function or class, kind), equal to ``REVIEWED``, whose comments say why each is or is not a write
of the flag. A new one fails until it is reviewed and listed; the reviewer confirms that a new writer of the flag never
touches an account a complimentary grant holds (or revokes the grant with it) and lists it.

Out of reach, said so nothing is overclaimed (each planted in ``OUT_OF_REACH``): a name built at run time
(``setattr(user, "is_" + "pro", True)``), a mapping that is not a literal handed on (``User(**fields)``,
``update(values)``), raw SQL assembled from pieces that are not literals, and a helper that is handed the attribute name.
Not read at all: a script in another language (JavaScript under ``ops/`` or ``tasks/``, whose one mention of the flag
today is a UI harness's mocked responses).
"""
import ast
import os
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
# What is not ours or never reaches the database: the browser app and the backend's test homes, by their paths (a
# folder named tests anywhere else, tasks/fable-e8-repin-2026-09-22/tests/ for one, is no test home and is read), git
# and tool caches by name (an installed package's own is_pro would otherwise read as a writer), and a nested checkout
# or worktree, a folder with its own .git, which is another tree.
SKIPPED_PATHS = {"frontend", "backend/tests"}
SKIPPED_NAMES = {".git", "node_modules", "__pycache__", "venv", ".venv", ".mypy_cache", ".pytest_cache", ".ruff_cache"}
TEXT_SUFFIXES = (".sql", ".sh", ".yml", ".yaml")
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


def looped(user):
    for user.is_pro in (True,):
        pass


async def looped_async(user, flags):
    async for user.is_pro in flags:
        pass


def managed(user, ctx):
    with ctx() as user.is_pro:
        pass


def comprehended(user):
    return [0 for user.is_pro in (True,)]


def ordered(db):
    db.execute(update(User).ordered_values((User.is_pro, True)))
    db.execute(update(User).ordered_values(("is_pro", False)))
'''
PLANTED_FOUND = {
    ("plain", "assign"): 1, ("augmented", "assign"): 1, ("annotated", "assign"): 1, ("tupled", "assign"): 1,
    ("keyword", "keyword"): 1, ("key", "key"): 1, ("column_key", "key"): 1, ("named", "setattr"): 1,
    ("raw", "string"): 1, ("looped", "assign"): 1, ("looped_async", "assign"): 1, ("managed", "assign"): 1,
    ("comprehended", "assign"): 1, ("ordered", "key"): 2,
}
# Lines a SQL, shell or workflow file holds, and how many name is_pro outside a comment.
PLANTED_TEXT = {
    "repair.sql": ("UPDATE users SET is_pro = true;\n-- is_pro in a comment\n/* is_pro\n in a block */\n"
                   "UPDATE users SET plan = 'pro'; -- set is_pro later\n", 1),
    "repair.sh": ('psql -c "UPDATE users SET IS_PRO = false"\n# is_pro in a comment\n  # and indented\n', 1),
    "ops.yml": ("      - run: psql -c 'UPDATE users SET is_pro = true'\n      # is_pro in a comment\n", 1),
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
        targets = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, (ast.AugAssign, ast.AnnAssign, ast.For, ast.AsyncFor, ast.comprehension)):
            targets = [node.target]
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            targets = [item.optional_vars for item in node.items if item.optional_vars is not None]
        for target in targets:
            found[(scope, "assign")] += sum(1 for t in _targets(target) if _is_flag(t))
        if isinstance(node, ast.Call):
            found[(scope, "keyword")] += sum(1 for kw in node.keywords if kw.arg == "is_pro")
            name = _callee(node)
            if name == "ordered_values":
                for pair in node.args:
                    if isinstance(pair, ast.Tuple) and pair.elts and (
                            _is_flag(pair.elts[0])
                            or (isinstance(pair.elts[0], ast.Constant) and pair.elts[0].value == "is_pro")):
                        found[(scope, "key")] += 1
                        exempt.add(id(pair.elts[0]))
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


def scan_text(path: Path, text: str) -> int:
    """The lines of a SQL, shell or workflow file that name ``is_pro`` outside a comment."""
    return sum(1 for line in _strip_comments(path, text).splitlines() if _NAME.search(line))


def _scanned_files(root: Path = ROOT) -> list[Path]:
    files = []
    for folder, subfolders, names in os.walk(root):
        here = Path(folder)
        subfolders[:] = [name for name in subfolders if name not in SKIPPED_NAMES
                         and (here / name).relative_to(root).as_posix() not in SKIPPED_PATHS
                         and not (here / name / ".git").exists()]
        files += [here / name for name in names
                  if (Path(name).suffix in (".py", *TEXT_SUFFIXES) or _shell_script(here / name))
                  and (here / name).is_file()]
    return sorted(files)


def _shell_script(path: Path) -> bool:
    """A file with no suffix whose first line runs a shell (``#!/bin/sh``, ``#!/usr/bin/env bash``)."""
    if path.suffix or not path.is_file():
        return False
    try:
        with path.open("rb") as handle:
            first = handle.readline(200)
    except OSError:
        return False
    return first.startswith(b"#!") and re.search(rb"\b(?:ba|z|da|k)?sh\b", first) is not None


def scan_repository(root: Path = ROOT) -> Counter:
    found: Counter = Counter()
    for path in _scanned_files(root):
        rel = path.relative_to(root).as_posix()
        if path.suffix == ".py":
            for (scope, kind), count in scan_python(path.read_text(encoding="utf-8")).items():
                found[(rel, scope, kind)] += count
        elif count := scan_text(path, path.read_text(encoding="utf-8", errors="replace")):
            found[(rel, "<file>", "text")] += count
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
    assert {name: scan_text(Path(name), text) for name, (text, _) in PLANTED_TEXT.items()} == {
        name: count for name, (_, count) in PLANTED_TEXT.items()}


def test_the_walk_reads_every_folder_but_the_browser_app_the_test_homes_and_other_trees(tmp_path):
    """Planted writers where the gate's first form never looked (a new top-level folder, .claude/, Python under
    .github/) and in a folder named tests that is no test home, beside the places it must skip."""
    writes = "def repair(user):\n    user.is_pro = True\n"
    for rel, text in {
        "infra/repair_pro.py": writes,
        ".github/scripts/repair_pro.py": writes,
        ".claude/repair_pro.sh": 'psql -c "UPDATE users SET is_pro = true WHERE id = 1"\n',
        ".claude/hooks/git/post-merge": '#!/usr/bin/env bash\npsql -c "UPDATE users SET is_pro = false"\n',
        "ops/NOTES": "is_pro, noted in a file that is no script\n",
        "frontend/scripts/fixture.py": writes,
        "backend/tests/unit/test_fixture.py": writes,
        "ops/tool/tests/repair_pro.py": writes,
        "vendor/checkout/repair_pro.py": writes,
        "vendor/checkout/.git/HEAD": "ref: refs/heads/main\n",
        "backend/node_modules/pkg/setup.py": writes,
    }.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text)
    assert scan_repository(tmp_path) == Counter({
        ("infra/repair_pro.py", "repair", "assign"): 1,
        (".github/scripts/repair_pro.py", "repair", "assign"): 1,
        (".claude/repair_pro.sh", "<file>", "text"): 1,
        (".claude/hooks/git/post-merge", "<file>", "text"): 1,
        ("ops/tool/tests/repair_pro.py", "repair", "assign"): 1,
    })
