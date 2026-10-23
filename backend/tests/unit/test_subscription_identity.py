"""Adversarial Stripe identity/delivery sequences, and the inventory of every writer of the billing
binding; existing webhook contracts stay locked."""
import ast
import os
import re
from collections import Counter
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Subscription, User
from app.services.entitlements import get_plan
from app.services.posthog_client import EVENT_TRIAL_STARTED
from app.services.subscription_sync import (
    apply_checkout_completed,
    apply_subscription_deleted,
    apply_subscription_upsert,
)
from app.services.subscription_webhook_service import _apply_event
from app.utils.datetimes import utcnow


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[User.__table__, Subscription.__table__])
    with Session(engine) as session:
        yield session
    engine.dispose()


def _user(db, number=1, **kwargs):
    user = User(email=f"identity-{number}@example.com", email_verified=True, **kwargs)
    db.add(user)
    db.commit()
    return user


def _checkout(user, sub_id="sub_a", customer="cus_a"):
    return {"subscription": sub_id, "customer": customer, "metadata": {"user_id": str(user.id)}}


def _apply(db, handler, obj):
    result = handler(db, obj)
    db.commit()
    db.expire_all()
    return result


def _state(user):
    sub = user.subscription
    return (
        user.stripe_customer_id, user.stripe_subscription_id, user.is_pro,
        get_plan(user).value,
        (sub.stripe_customer_id, sub.stripe_subscription_id, sub.plan, sub.status,
         sub.trial_end, sub.current_period_end, sub.cancel_at_period_end) if sub else None,
    )


@pytest.mark.parametrize("binding", ["user", "subscription"])
def test_checkout_cannot_replace_an_established_customer(db, binding):
    user = _user(db)
    if binding == "user":
        user.stripe_customer_id = "cus_existing"
    else:
        db.add(Subscription(user_id=user.id, stripe_customer_id="cus_existing", status="canceled"))
    db.commit()
    db.expire_all()
    before = _state(user)
    _apply(db, apply_checkout_completed, _checkout(user, customer="cus_conflicting"))
    assert _state(user) == before


@pytest.mark.parametrize("binding", ["user", "subscription"])
@pytest.mark.parametrize("field", ["stripe_customer_id", "stripe_subscription_id"])
def test_checkout_cannot_take_another_users_billing_identity(db, binding, field):
    owner = _user(db, 1)
    target = _user(db, 2)
    value = "cus_a" if field == "stripe_customer_id" else "sub_a"
    if binding == "user":
        setattr(owner, field, value)
    else:
        db.add(Subscription(user_id=owner.id, status="canceled", **{field: value}))
    db.commit()
    db.expire_all()
    before = (_state(owner), _state(target))
    _apply(db, apply_checkout_completed, _checkout(target))
    assert (_state(owner), _state(target)) == before


@pytest.mark.parametrize("status", ["trialing", "past_due", "canceled"])
def test_checkout_after_subscription_event_preserves_authoritative_state(db, status):
    user = _user(db, stripe_customer_id="cus_a")
    future = int((utcnow() + timedelta(days=7)).timestamp())
    _apply(db, apply_subscription_upsert, {
        "id": "sub_a", "customer": "cus_a", "status": status,
        "trial_end": future if status == "trialing" else None,
        "items": {"data": [{"current_period_end": future, "price": {"id": "price_a"}}]},
        "cancel_at_period_end": True,
    })
    before = _state(user)
    result = _apply(db, apply_checkout_completed, _checkout(user))
    assert _state(user) == before
    assert get_plan(user).value == ("pro" if status == "trialing" else "free")
    assert result is (user if status == "trialing" else None)


@pytest.mark.parametrize("old_status", ["canceled", "past_due", "trialing"])
@pytest.mark.parametrize("late_event", ["checkout", "deletion"])
def test_eligible_replacement_survives_old_checkout_and_deletion(db, old_status, late_event):
    user = _user(db)
    _apply(db, apply_checkout_completed, _checkout(user))
    _apply(db, apply_subscription_upsert, {
        "id": "sub_a", "customer": "cus_a", "status": old_status,
        "trial_end": int((utcnow() - timedelta(days=1)).timestamp()) if old_status == "trialing" else None,
    })
    assert get_plan(user).value == "free"
    _apply(db, apply_checkout_completed, _checkout(user, sub_id="sub_b"))
    assert user.subscription.stripe_subscription_id == "sub_b"
    assert get_plan(user).value == "pro"
    before = _state(user)

    if late_event == "checkout":
        _apply(db, apply_checkout_completed, _checkout(user, sub_id="sub_a"))
    else:
        _apply(db, apply_subscription_deleted, {"id": "sub_a", "customer": "cus_a"})
    assert _state(user) == before  # neither old event may change entitled replacement B

    _apply(db, apply_subscription_deleted, {"id": "sub_b", "customer": "cus_a"})
    assert user.subscription.status == "canceled"
    assert user.stripe_subscription_id is None
    assert user.is_pro is False
    assert get_plan(user).value == "free"


def _ts(days):
    return int((utcnow() + timedelta(days=days)).timestamp())


def _replacement_bound(db):
    """Old A went past_due (Free) and the user checked out replacement B: B is bound and Pro."""
    user = _user(db)
    _apply(db, apply_checkout_completed, _checkout(user))
    _apply(db, apply_subscription_upsert, {"id": "sub_a", "customer": "cus_a", "status": "past_due"})
    _apply(db, apply_checkout_completed, _checkout(user, sub_id="sub_b"))
    assert get_plan(user).value == "pro"
    return user


@pytest.mark.parametrize("late_status", ["unpaid", "past_due", "canceled", "incomplete_expired", "trialing"])
def test_late_old_update_cannot_unbind_entitled_replacement(db, late_status):
    user = _replacement_bound(db)
    before = _state(user)

    result = _apply(db, apply_subscription_upsert, {
        "id": "sub_a", "customer": "cus_a", "status": late_status,
        # A late-delivered trial update carries a trial that has since elapsed: not entitling.
        "trial_end": _ts(-1) if late_status == "trialing" else None,
    })
    assert _state(user) == before  # old A's dunning outcome or a late retry may not rebind or revoke B
    assert result is None


# The guard shields only an entitled binding from another subscription's non-entitling state: B's own
# events and an entitling event for a newer subscription (a future trial included) still apply.
@pytest.mark.parametrize("handler, obj, expected", [
    pytest.param(apply_subscription_upsert, {"id": "sub_b", "status": "past_due"},
                 ("sub_b", "past_due", False, "free"), id="bound_update"),
    pytest.param(apply_subscription_deleted, {"id": "sub_b"},
                 (None, "canceled", False, "free"), id="bound_deletion"),
    pytest.param(apply_subscription_upsert, {"id": "sub_c", "status": "active"},
                 ("sub_c", "active", True, "pro"), id="newer_active"),
    pytest.param(apply_subscription_upsert, {"id": "sub_c", "status": "trialing", "trial_end": _ts(30)},
                 ("sub_c", "trialing", True, "pro"), id="newer_trialing"),
])
def test_bound_and_entitling_events_still_apply_to_a_replacement(db, handler, obj, expected):
    user = _replacement_bound(db)
    _apply(db, handler, {"customer": "cus_a", **obj})
    assert (user.stripe_subscription_id, user.subscription.status, user.is_pro, get_plan(user).value) == expected


def test_unentitled_account_still_binds_a_new_non_active_subscription(db):
    user = _user(db)
    _apply(db, apply_checkout_completed, _checkout(user))
    _apply(db, apply_subscription_upsert, {"id": "sub_a", "customer": "cus_a", "status": "past_due"})
    assert get_plan(user).value == "free"
    _apply(db, apply_subscription_upsert, {"id": "sub_b", "customer": "cus_a", "status": "incomplete"})
    # Nothing entitled to protect: B binds, so its later events are current-ID and read Stripe.
    assert (user.stripe_subscription_id, user.subscription.status, get_plan(user).value) == (
        "sub_b", "incomplete", "free")


@pytest.mark.parametrize("sub_id, trial_days, applied", [
    pytest.param("sub_a", -1, False, id="ignored_old_elapsed_trial"),
    pytest.param("sub_c", 30, True, id="applied_newer_trial"),
])
def test_trial_started_is_recorded_only_when_the_upsert_applies(db, sub_id, trial_days, applied):
    user = _replacement_bound(db)
    user_id, before = str(user.id), _state(user)
    obj = {"id": sub_id, "customer": "cus_a", "status": "trialing", "trial_end": _ts(trial_days)}

    analytics = _apply_event(db, "customer.subscription.created", obj, user)
    db.commit()
    db.expire_all()
    # A late created(trialing) for old A whose trial has elapsed is ignored, so it records no trial
    # start on replacement B's account; a created event that applies still records one.
    started = [(user_id, EVENT_TRIAL_STARTED, {"source": "stripe", "trial_end": obj["trial_end"]})]
    assert analytics == (started if applied else [])
    assert (_state(user) != before) is applied


# ── Every writer of the binding is inventoried ────────────────────────────────────────────────
#
# The rule above holds only while every writer of the binding carries the identity guard, and the
# behaviour tests reach the three handlers that exist. So this half counts every MENTION of
# ``stripe_subscription_id`` in every Python, SQL, shell and workflow file that can reach the
# production database: the whole repository but the browser app (``frontend/``), git and tool caches,
# and the test homes. That is the backend (the app, the entrypoints, ``scripts/`` repair one-offs, the
# migrations), ``ops/`` (the detection and capacity SQL that ops.yml runs with the app's
# credentials), the root ``scripts/``, ``tasks/`` (SQL written to be run against production by hand),
# ``.github`` and ``.claude``; a new folder is scanned by default, while a nested checkout or worktree
# (an agent worktree under ``.claude/worktrees/``) is another tree and is not. That covers the binding column on ``Subscription``, its mirror on
# ``User``, and ``BillingPayment``'s own copy, reads included, as (path from the repository root,
# enclosing function or class, kind) with how many times each occurs, and holds that equal to
# ``BINDING_MENTIONS``. A new mention, read or write, fails until it is reviewed and listed,
# including a second one inside an already-listed function (a branch added to the ``_apply_event``
# dispatcher that clears the binding is a new mention there). Listing is a review step: the reviewer
# confirms that a new Python writer has the identity guard and adds its late-event case above, and
# that a SQL writer never replaces or clears a bound row (the one that exists, the 2026-06-17 seed,
# inserts only where a user has no row); this half cannot check either.
#
# In Python a mention is an attribute access (``read`` or ``write``), the column as a key of a
# mapping literal or an ``ordered_values`` pair (``key``: the shape of a row write, whichever
# spelling), a bare name (``definition`` when assigned, a model column or schema field included;
# ``name`` when read), a keyword argument, or a string or bytes literal outside a docstring that
# contains the name in any case (SQL folds unquoted names), whether a literal or an expression built
# only from literals (concatenation, ``%`` with a tuple or a mapping, an f-string, ``str.join``,
# ``str.format`` with positional or keyword arguments, and the case and replace methods are folded).
# A migration, shell script or workflow is read as text: every occurrence of the name, in any case
# and comments included, is a ``text`` mention, and the whole file is one scope, so its counts are
# per file, not per function. SQL is read without its ``--`` and ``/* */`` comments (a ``'--'`` inside a
# string is kept), a shell script or workflow without its whole-line ``#`` comments. Kinds are syntactic: a ``read``, ``string``, ``keyword`` or ``text``
# can still be part of a write.
#
# In every module that names the column in any of those ways, each place a column could be picked at
# run time also counts, as ``dynamic``: a name-taking call (``setattr``, ``getattr``,
# ``set_attribute``, ``object.__setattr__`` and the like) with a name not spelled out, or such a
# function handed on as a value (not a parameter or local of the same or an enclosing function that
# only shares its name); raw SQL or a
# column built from a non-literal (``text``, ``column``, ``literal_column``, ``exec_driver_sql``,
# under any import alias); a SQL write assembled at run time wherever it is built (``stmt = f"UPDATE
# users SET {col} = NULL"`` then ``cursor.execute(stmt)``) or with a placeholder a caller fills in
# (``sql.SQL(...).format(sql.Identifier(col))``) or from pieces (a start the code grows with ``+=``,
# ``x = x + ...`` or ``append``, a list join, ``sql.SQL`` / ``Composed``), where a SQL write is a
# statement that opens with its verb, after a CTE, a comment or an earlier statement, so prose is not
# one (unless it follows a ``;``) and a ``.format`` that folds is static; and any other string assembled at run time
# straight into ``execute``; a ``**mapping`` argument; row data, positional or keyword, handed to
# ``update``, ``values``, ``ordered_values``, ``execute``, ``executemany``,
# ``on_conflict_do_update`` or a ``bulk_*_mappings`` call unless it is a literal mapping (or list of
# them) keyed by literals or attributes of an imported CapWords class; any other mapping argument
# with an unspelled key; and a by-name lookup in ``.c``, ``.columns``, ``.attrs`` and the like. That
# takes in the model modules, where an ORM listener beside the column would live. In a text file
# that names the column, each ``EXECUTE`` in SQL but a trigger's ``EXECUTE FUNCTION``, and each psql
# ``\gexec``, is ``dynamic``; in a shell script or workflow, gcloud's ``jobs execute`` and an
# ``--execute`` flag are not. The scope is not every module that imports ``User`` or ``Subscription``: the
# summary pipeline reads the plan through them, and counting its every ``**kwargs`` would tie this
# gate to unrelated code.
#
# Out of reach, planted as named gaps below: a file that names the column only in a docstring, or
# not at all, and writes it by a name it did not build from literals (a generic helper handed a
# user, a ``stripe_{kind}_id`` loop, a name built in SQL or in the shell, a psql variable); a name
# from code the folder does not run; a whole-row copy or load that moves every column without naming
# one (in Python, ``INSERT ... SELECT *``, a positional ``INSERT ... VALUES``, ``COPY`` or psql
# ``\copy``); moving the binding by deleting, re-parenting or replacing the ``Subscription`` row
# (none names the column); SQL quoted in a Markdown runbook, which is read, not run (the walker test);
# and swapping one
# mention for another of the same kind inside one scope, which keeps the counts equal.

COLUMN = "stripe_subscription_id"
REPO_DIR = Path(__file__).resolve().parents[3]


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


BINDING_MENTIONS = {
    # The writers: each checks the event's subscription against the bound one before it writes.
    ("backend/app/services/subscription_sync.py", "apply_checkout_completed", "write"): 2,
    ("backend/app/services/subscription_sync.py", "apply_subscription_upsert", "write"): 2,
    ("backend/app/services/subscription_sync.py", "apply_subscription_deleted", "write"): 1,
    # Their guards and lookups read the binding.
    ("backend/app/services/subscription_sync.py", "apply_checkout_completed", "read"): 2,
    ("backend/app/services/subscription_sync.py", "apply_subscription_upsert", "read"): 3,
    ("backend/app/services/subscription_sync.py", "apply_subscription_deleted", "read"): 2,
    ("backend/app/services/subscription_sync.py", "_find_user", "read"): 2,
    # The identity check walks ("stripe_customer_id", "stripe_subscription_id") and filters with
    # getattr(User, field) and getattr(Subscription, field): reads only.
    ("backend/app/services/subscription_sync.py", "_checkout_identity_conflict", "read"): 2,
    ("backend/app/services/subscription_sync.py", "_checkout_identity_conflict", "string"): 1,
    ("backend/app/services/subscription_sync.py", "_checkout_identity_conflict", "dynamic"): 2,
    # The worker reads the bound ID (Subscription row, else the User mirror) to fetch it from Stripe.
    ("backend/app/services/subscription_webhook_service.py", "_reconcile_current_subscription", "read"): 2,
    # An analytics payload key, after the handler ran.
    ("backend/app/services/subscription_webhook_service.py", "_apply_event", "key"): 1,
    # The status response model and the endpoint's thread-pool unit that fills it from the binding.
    ("backend/app/routers/subscriptions.py", "SubscriptionStatus", "definition"): 1,
    ("backend/app/routers/subscriptions.py", "status_for_reader", "read"): 2,
    ("backend/app/routers/subscriptions.py", "status_for_reader", "keyword"): 1,
    # run_in_threadpool(stripe.checkout.Session.create, **session_kwargs): the Stripe API call, no
    # database write.
    ("backend/app/routers/subscriptions.py", "create_checkout_session", "dynamic"): 1,
    # Payment attribution looks the paying account up by the binding (User and Subscription filters)
    # and collects the matching user ids into Python sets (set.update over a generator).
    ("backend/app/services/billing_revenue_service.py", "payment_attribution", "read"): 2,
    ("backend/app/services/billing_revenue_service.py", "payment_attribution", "dynamic"): 2,
    # A BillingPayment row records the paying subscription in its own column, not the binding.
    ("backend/app/services/billing_revenue_service.py", "record_payment", "keyword"): 1,
    # {"currency": ..., **group}: a report row, no database write.
    ("backend/app/services/billing_revenue_service.py", "payment_report", "dynamic"): 1,
    # The GDPR export reads the binding and each payment's copy into the export payload.
    ("backend/app/services/user_data_export_service.py", "build_user_data_export", "read"): 2,
    ("backend/app/services/user_data_export_service.py", "build_user_data_export", "key"): 2,
    # The columns.
    ("backend/app/models/subscription.py", "Subscription", "definition"): 1,
    ("backend/app/models/__init__.py", "User", "definition"): 1,
    ("backend/app/models/billing_payment.py", "BillingPayment", "definition"): 1,
    # The migrations that created the columns. The subscriptions one also seeded a row per user from the
    # users mirror when the table was new (INSERT ... SELECT ... ON CONFLICT (user_id) DO NOTHING, so it
    # never replaces a bound row): column, index name and column, insert list, select list.
    ("backend/migrations/20260617_create_subscriptions_and_stripe_events.sql", "<file>", "text"): 5,
    ("backend/migrations/20260906_earningsnerd_billing_payments.sql", "<file>", "text"): 1,
    # The critique harness's mock API serves canned subscription payloads to the frontend; it has no
    # database.
    ("tasks/critique-env-2026-10-04/mock_api.py", "<module>", "key"): 2,
    # The Filing URL listeners in the model module read sec_url and document_url by name
    # (getattr(target, field), state.attrs[field]) from _FILING_URL_FIELDS: no billing column.
    ("backend/app/models/__init__.py", "_validate_filing_url", "dynamic"): 1,
    ("backend/app/models/__init__.py", "validate_filing_before_update", "dynamic"): 2,
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
    """Count (scope, kind) for every mention of the binding column, and, in a module that mentions
    the column (``in_scope``), for every dynamic-name sink."""

    def __init__(self, docstrings: set[int], *, in_scope: bool, module: "_Module") -> None:
        self.mentions: Counter[tuple[str, str]] = Counter()
        self._docstrings = docstrings
        self._in_scope = in_scope
        self._module = module
        self._called: set[int] = set()
        self._keys: set[int] = set()
        self._inner: set[int] = set()
        self._locals: list[set[str]] = []
        self._stack: list[str] = []

    def _scoped(self, node: ast.AST, name: str) -> None:
        self._stack.append(name)
        self.generic_visit(node)
        self._stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
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
        self.mentions[(self._stack[-1] if self._stack else "<module>", kind)] += 1

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr == COLUMN:
            self._record("key" if id(node) in self._keys else "read" if isinstance(node.ctx, ast.Load) else "write")
        self.generic_visit(node)

    def visit_Dict(self, node: ast.Dict) -> None:
        # The column as a mapping key is the shape of a row write (``.update({User.x: v})``), so it
        # counts as ``key``, never as the read or string it looks like.
        self._keys.update(id(key) for key in node.keys if key is not None)
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id == COLUMN:
            self._record("definition" if isinstance(node.ctx, ast.Store) else "name")
        # A sink handed on as a value (``partial(setattr, t)``, ``map(setattr, ...)``, ``put = setattr``)
        # is called where its name argument cannot be seen. A parameter or local that only shares a
        # sink's name (``def f(text): text.strip()``) is not the sink.
        if (self._in_scope and isinstance(node.ctx, ast.Load) and id(node) not in self._called
                and not self._shadowed(node.id) and self._module.sink(node.id) in _SINK_NAMES):
            self._record("dynamic")

    def visit_keyword(self, node: ast.keyword) -> None:
        if node.arg == COLUMN:
            self._record("keyword")
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        value = _fold(node)
        if value is None or id(node) in self._docstrings:
            return
        if COLUMN in value.lower():  # SQL folds unquoted names: "SET STRIPE_SUBSCRIPTION_ID = NULL" writes it
            self._record("key" if id(node) in self._keys else "string")
        # SQL a caller fills in later (``sql.SQL("UPDATE users SET {} = NULL").format(...)``).
        if (self._in_scope and id(node) not in self._inner and _PLACEHOLDER.search(value)
                and _is_sql_write(value)):
            self._record("dynamic")

    def _built_string(self, node: ast.expr) -> None:
        folded = _fold(node)
        if folded is not None and COLUMN in folded.lower():
            self._record("key" if id(node) in self._keys else "string")

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
        if _callee(node, self._module) == "ordered_values":  # (column, value) pairs
            self._keys.update(id(pair.elts[0]) for pair in node.args if isinstance(pair, ast.Tuple) and pair.elts)
        if _fold(node) is not None:  # "UPDATE users SET {} = 1".format("x") is static SQL
            self._inner.update(id(inner) for inner in ast.walk(node))
        if _callee(node, self._module) in _SQL_COMPOSERS:
            for arg in node.args:
                for part in (arg.elts if isinstance(arg, (ast.List, ast.Tuple)) else [arg]):
                    self._sql_fragment(part)
        self._built_string(node)
        self._run_time_sql(node)
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
# Collections a column or attribute is looked up in by name (``Subscription.__table__.c[key]``,
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
        if isinstance(node.right, ast.Dict):  # "stripe_%(k)s_id" % {"k": "subscription"}
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
    ``Subscription.status`` counts as spelled out only on an imported class), local aliases of the
    sink functions (``from sqlalchemy import text as sa_text``, ``put = setattr``), and names bound to
    a by-name lookup collection (``COLS = Subscription.__table__.c``)."""

    def __init__(self, tree: ast.AST) -> None:
        self.imported: set[str] = set()
        self.aliases: dict[str, str] = {}
        self.keyed: set[str] = set()
        self.extended: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    self.imported.add(alias.asname or alias.name.split(".")[0])
                    original = alias.name.split(".")[-1]
                    if alias.asname and original in _SINK_NAMES:
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
    literals), or an attribute of an imported class such as ``Subscription.status``; not
    ``col.name`` and not a constant the module picked itself."""
    if key is None:
        return False
    if _fold(key) is not None:
        return True
    if not (isinstance(key, ast.Attribute) and isinstance(key.value, ast.Name)):
        return False
    owner = key.value.id
    # A class by its CapWords name: ``fields.BINDING`` or ``settings.KEY`` is a constant, not a column.
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
    """Whether a module mentions the binding column itself, outside docstrings: where a writer of
    the binding would live, including a model module (its ORM listeners) or one that only declares
    the name as a field. Not every module that imports ``User`` or ``Subscription`` (the summary
    pipeline reads the plan through them): counting their every dynamic-name sink would tie this gate
    to unrelated code."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == COLUMN:
            return True
        if isinstance(node, ast.Name) and node.id == COLUMN:
            return True
        if isinstance(node, ast.keyword) and node.arg == COLUMN:
            return True
        if isinstance(node, (ast.Constant, ast.JoinedStr, ast.BinOp, ast.Call)) and id(node) not in docstrings:
            folded = _fold(node)
            if folded is not None and COLUMN in folded.lower():
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
    column, each dynamic-SQL ``EXECUTE`` or ``\\gexec`` is ``dynamic``."""
    lowered = text.lower()
    counts: Counter[tuple[str, str]] = Counter({(_TEXT_SCOPE, "text"): lowered.count(COLUMN)})
    if COLUMN in lowered:
        code = _strip_sql_comments(text) if sql else _SHELL_COMMENT.sub("", text)  # a comment runs nothing
        counts[(_TEXT_SCOPE, "dynamic")] = len((_DYNAMIC_SQL if sql else _DYNAMIC_SHELL).findall(code))
    return +counts  # drop the zero counts


def _file_mention_counts(path: Path) -> Counter[tuple[str, str]]:
    text = path.read_text(encoding="utf-8-sig")  # a byte-order mark is not code
    if path.suffix == ".py":
        return _mention_counts(text)
    return _text_mention_counts(text, sql=path.suffix == ".sql")


# Planted forms: every way a new writer could reach the binding must be counted; a docstring or a
# comment that names it, and another column, must not be.
PLANTED = [
    ("attribute-assignment", "def f(u, v):\n    u.stripe_subscription_id = v\n", {("f", "write")}),
    ("constructor-keyword", "def f(v):\n    return Subscription(user_id=1, stripe_subscription_id=v)\n",
     {("f", "keyword")}),
    ("column-key-update",
     "from app.models import User\n\ndef f(q, v):\n    q.update({User.stripe_subscription_id: v})\n",
     {("f", "key")}),
    ("string-key-update", "def f(q):\n    q.update({'stripe_subscription_id': None})\n", {("f", "key")}),
    ("ordered-values-column-key",
     "from app.models import Subscription\n\ndef f(stmt, v):\n"
     "    return stmt.ordered_values((Subscription.stripe_subscription_id, v))\n", {("f", "key")}),
    ("values-keyword",
     "def f(db, uid, v):\n    db.execute(update(User).where(User.id == uid).values(stripe_subscription_id=v))\n",
     {("f", "keyword")}),
    ("alias-then-update",
     "def f(q, v):\n    binding = Subscription.stripe_subscription_id\n    q.update({binding: v})\n",
     {("f", "read"), ("f", "dynamic")}),
    ("setattr-by-name", "def f(u, v):\n    setattr(u, 'stripe_subscription_id', v)\n", {("f", "string")}),
    ("joined-name", "def f(u, v):\n    setattr(u, '_'.join(('stripe', 'subscription', 'id')), v)\n",
     {("f", "string")}),
    ("f-string-name", "def f(u, kind, v):\n    setattr(u, f\"stripe_{'subscription'}_id\", v)\n", {("f", "string")}),
    ("raw-sql", "def f():\n    return text('UPDATE users SET stripe_subscription_id = NULL')\n", {("f", "string")}),
    # In a module that mentions the column, each place a column could be picked at run time counts.
    ("computed-key-mapping",
     "def f(db, user_id, obj):\n    values = {f'stripe_{k}_id': obj.get(k) for k in ('customer', 'subscription')}\n"
     "    db.query(Subscription).filter(Subscription.user_id == user_id).update(values)\n"
     "    return obj.get('stripe_subscription_id')\n", {("f", "string"), ("f", "dynamic")}),
    ("bulk-mappings",
     "def f(db, ids, field):\n    db.bulk_update_mappings(User, [{'id': i, field: None} for i in ids])\n"
     "    return User.stripe_subscription_id\n", {("f", "read"), ("f", "dynamic")}),
    ("dynamic-name-in-a-binding-module",
     "def f(s, field, v):\n    setattr(s, field, v)\n    return s.stripe_subscription_id\n",
     {("f", "read"), ("f", "dynamic")}),
    ("star-star-into-the-model",
     "def f(fields):\n    return Subscription(**fields), fields['stripe_subscription_id']\n",
     {("f", "dynamic"), ("f", "string")}),
    ("docstring-only", 'def f():\n    """Reads stripe_subscription_id to decide."""\n    return 1\n', set()),
    ("comment-only", "def f():\n    # stripe_subscription_id is written by the handlers\n    return 1\n", set()),
    ("other-column", "def f(u, v):\n    u.stripe_customer_id = v\n", set()),
    ("payload-tuple-in-a-binding-module",
     "def f(events, u):\n    events.append((str(u.id), 'activated', {'plan': 'pro'}))\n"
     "    return u.stripe_subscription_id\n", {("f", "read")}),
    # The name-taking calls, row writers and lookups of the comment block, each beside a read that puts
    # the module in scope.
    ("set-attribute",
     "from sqlalchemy.orm.attributes import set_attribute\n\ndef f(u, field, v):\n    set_attribute(u, field, v)\n"
     "    return u.stripe_subscription_id\n", {("f", "dynamic"), ("f", "read")}),
    ("bound-dunder-setattr", "def f(u, field, v):\n    u.__setattr__(field, v)\n    return u.stripe_subscription_id\n",
     {("f", "dynamic"), ("f", "read")}),
    ("object-dunder-setattr",
     "def f(u, field, v):\n    object.__setattr__(u, field, v)\n    return u.stripe_subscription_id\n",
     {("f", "dynamic"), ("f", "read")}),
    ("partial-setattr",
     "from functools import partial\n\ndef f(u):\n    put = partial(setattr, u)\n    return put, u.stripe_subscription_id\n",
     {("f", "dynamic"), ("f", "read")}),
    ("text-under-an-alias",
     "from sqlalchemy import text as sql\n\ndef f(db, stmt):\n    db.execute(sql(stmt))\n"
     "    return User.stripe_subscription_id\n", {("f", "dynamic"), ("f", "read")}),
    ("sql-built-at-run-time",
     "def f(cursor, col):\n    cursor.execute(f'UPDATE users SET {col} = NULL')\n    return User.stripe_subscription_id\n",
     {("f", "dynamic"), ("f", "read")}),
    ("execute-with-row-list",
     "def f(db, rows):\n    db.execute(update(Subscription), rows)\n    return Subscription.stripe_subscription_id\n",
     {("f", "dynamic"), ("f", "read")}),
    ("params-keyword",
     "def f(db, stmt, row):\n    db.execute(stmt, params=row)\n    return User.stripe_subscription_id\n",
     {("f", "dynamic"), ("f", "read")}),
    ("ordered-values-by-name",
     "def f(stmt, col, v):\n    return stmt.ordered_values((col, v)), User.stripe_subscription_id\n",
     {("f", "dynamic"), ("f", "read")}),
    ("upsert-set-from-a-row",
     "def f(stmt, row):\n    return stmt.on_conflict_do_update(index_elements=['id'], set_=row), User.stripe_subscription_id\n",
     {("f", "dynamic"), ("f", "read")}),
    ("column-collection-by-name",
     "def f(key):\n    return Subscription.__table__.c[key], User.stripe_subscription_id\n",
     {("f", "dynamic"), ("f", "read")}),
    ("key-off-a-module-constant",
     "from app.billing import fields\n\ndef f(q, v):\n    q.update({fields.BINDING: v})\n"
     "    return User.stripe_subscription_id\n", {("f", "dynamic"), ("f", "read")}),
    # A module that names the column only as a field or a model column is in scope too: a dataclass or
    # schema copied onto the user, or an ORM listener beside the column.
    ("field-only-module-writer",
     "@dataclass\nclass Patch:\n    stripe_subscription_id: str | None\n\ndef apply(u, patch):\n"
     "    for k, v in asdict(patch).items():\n        setattr(u, k, v)\n",
     {("Patch", "definition"), ("apply", "dynamic")}),
    # SQL folds unquoted names, so a Python string matches in any case.
    ("upper-case-sql", "def f(db):\n    db.execute(text('UPDATE USERS SET STRIPE_SUBSCRIPTION_ID = NULL'))\n",
     {("f", "string")}),
    ("bytes-sql", "def f(cur):\n    cur.execute(b'UPDATE users SET stripe_subscription_id = NULL')\n", {("f", "string")}),
    ("keyword-formatted-name", "def f(u, v):\n    setattr(u, 'stripe_{k}_id'.format(k='subscription'), v)\n",
     {("f", "string")}),
    ("mapping-percent-name", "def f(u, v):\n    setattr(u, 'stripe_%(k)s_id' % {'k': 'subscription'}, v)\n",
     {("f", "string")}),
    # SQL assembled at run time counts where it is built, whether or not it goes straight to execute.
    ("sql-bound-to-a-name-first",
     "def f(conn, col):\n    sql = 'UPDATE users SET ' + col + ' = NULL'\n    conn.connection.cursor().execute(sql)\n"
     "    return User.stripe_subscription_id\n", {("f", "dynamic"), ("f", "read")}),
    ("f-string-sql-in-a-script",
     "COLUMN = 'stripe_subscription_id'\n\ndef main(cur, table):\n    stmt = f'UPDATE {table} SET {COLUMN} = NULL'\n"
     "    cur.execute(stmt)\n", {("<module>", "string"), ("main", "dynamic")}),
    ("psycopg2-composed-sql",
     "from psycopg2 import sql\n\ndef f(cur, field):\n"
     "    cur.execute(sql.SQL('UPDATE users SET {} = NULL').format(sql.Identifier(field)))\n"
     "    return User.stripe_subscription_id\n", {("f", "dynamic"), ("f", "read")}),
    ("local-named-like-a-sink",
     "def f(text, column):\n    return text.strip(), column, User.stripe_subscription_id\n", {("f", "read")}),
    # A SQL write assembled from pieces counts where its pieces are: extended with +=, joined from a
    # list, or composed with psycopg2's sql module.
    ("sql-extended-with-plus-equals",
     "def f(cur, col):\n    stmt = 'UPDATE users SET '\n    stmt += col\n    stmt += ' = NULL'\n"
     "    cur.execute(stmt)\n    return User.stripe_subscription_id\n", {("f", "dynamic"), ("f", "read")}),
    ("sql-joined-from-a-list",
     "def f(cur, col):\n    stmt = ' '.join(['UPDATE', 'users', 'SET', col, '= NULL'])\n"
     "    cur.execute(stmt)\n    return User.stripe_subscription_id\n", {("f", "dynamic"), ("f", "read")}),
    ("psycopg2-concatenated-sql",
     "from psycopg2 import sql\ndef f(cur, col):\n"
     "    cur.execute(sql.SQL('UPDATE users SET ') + sql.Identifier(col) + sql.SQL(' = NULL'))\n    return User.stripe_subscription_id\n",
     {("f", "dynamic"), ("f", "read")}),
    ("psycopg2-composed-list",
     "from psycopg2 import sql\ndef f(cur, col):\n"
     "    cur.execute(sql.Composed([sql.SQL('UPDATE users SET '), sql.Identifier(col), sql.SQL(' = NULL')]))\n    return User.stripe_subscription_id\n",
     {("f", "dynamic"), ("f", "read")}),
    # A parameter named like a sink shadows it only inside its own function.
    ("sink-shadowed-in-one-function-only",
     "from sqlalchemy import text\ndef clean(text):\n    return text.strip()\n\n"
     "def f(db, stmts):\n    for stmt in map(text, stmts):\n        db.execute(stmt)\n    return User.stripe_subscription_id\n",
     {("f", "dynamic"), ("f", "read")}),
    # Prose, static SQL with a quoted '{}', and a format that folds are not SQL built at run time.
    ("prose-and-static-sql-look-alikes",
     "def f(db, sid):\n    logger.info(f'Skipped the update for {sid}: the plan is set by the bound subscription')\n"
     "    db.execute(text(\"UPDATE users SET tags = '{}' WHERE tags IS NULL\"))\n"
     "    return 'UPDATE users SET {} = 1'.format('flag')\n    return User.stripe_subscription_id\n", {("f", "read")}),
    # A SQL write after a CTE, a comment or an earlier statement still opens a statement.
    ("cte-led-sql-write",
     "def f(cur, col):\n    stmt = f'WITH stale AS (SELECT id FROM users) UPDATE users SET {col} = NULL'\n"
     "    cur.execute(stmt)\n    return User.stripe_subscription_id\n", {("f", "dynamic"), ("f", "read")}),
    ("statement-before-the-write",
     "def f(cur, col):\n    stmt = f\"SET LOCAL lock_timeout = '5s'; UPDATE users SET {col} = NULL\"\n"
     "    cur.execute(stmt)\n    return User.stripe_subscription_id\n", {("f", "dynamic"), ("f", "read")}),
    ("comment-led-sql-write",
     "def f(cur, col):\n    stmt = '-- clear the field\\nUPDATE users SET ' + col + ' = NULL'\n    cur.execute(stmt)\n    return User.stripe_subscription_id\n",
     {("f", "dynamic"), ("f", "read")}),
    # A start the code grows later, however it grows.
    ("list-bound-then-grown",
     "def f(cur, col):\n    parts = ['UPDATE users SET']\n    parts.append(col + ' = NULL')\n"
     "    stmt = ' '.join(parts)\n    cur.execute(stmt)\n    return User.stripe_subscription_id\n", {("f", "dynamic"), ("f", "read")}),
    ("annotated-start-then-extended",
     "def f(cur, col):\n    stmt: str = 'UPDATE users SET '\n    stmt += col\n    cur.execute(stmt)\n    return User.stripe_subscription_id\n",
     {("f", "dynamic"), ("f", "read")}),
    ("attribute-start-then-extended",
     "class Q:\n    def f(self, col):\n        self.sql = 'UPDATE users SET '\n        self.sql += col\n        return User.stripe_subscription_id\n",
     {("f", "dynamic"), ("f", "read")}),
    ("start-reassigned-with-a-chain",
     "def f(cur, col):\n    stmt = 'UPDATE users SET '\n    stmt = stmt + col + ' = NULL'\n    cur.execute(stmt)\n    return User.stripe_subscription_id\n",
     {("f", "dynamic"), ("f", "read")}),
    ("start-reassigned-with-plus",
     "def f(cur, col):\n    stmt = 'UPDATE users SET '\n    stmt = stmt + col\n    cur.execute(stmt)\n    return User.stripe_subscription_id\n",
     {("f", "dynamic"), ("f", "read")}),
    # A closure or a lambda sees its function's parameter, not the sink it is named after.
    ("closure-over-a-sink-named-parameter",
     "def f(rows, column, text):\n    def inner():\n        return text.strip()\n"
     "    return sorted(rows, key=lambda r: r[column]), inner()\n    return User.stripe_subscription_id\n", {("f", "read")}),
    ("lambda-parameter-named-like-a-sink",
     "def f(items):\n    return list(map(lambda text: text.strip(), items))\n    return User.stripe_subscription_id\n", {("f", "read")}),
    ("listener-beside-the-column",
     "class User:\n    stripe_subscription_id = Column(String)\n\ndef clear(mapper, connection, target):\n"
     "    for key in BINDING_KEYS:\n        setattr(target, key, None)\n",
     {("User", "definition"), ("clear", "dynamic")}),
]

# Named gaps: what the scan cannot see. A case that starts being counted moves to PLANTED. The first
# three are out of scope (the module never names the column outside a docstring); the rest stay unseen
# even beside a mention (``decoy``) that puts the module in scope.
_DECOY = "\n\ndef decoy(u):\n    return u.stripe_subscription_id\n"
GAPS = [
    ("generic-helper-handed-a-user",
     "def stamp(obj, field, value):\n    setattr(obj, field, value)\n\ndef rebind(u, field, v):\n"
     "    stamp(u, field, v)\n", False),
    ("kinds-loop-named-only-in-a-docstring",
     '"""Clears stripe_subscription_id on cancel."""\n\ndef f(u):\n    for kind in ("customer", "subscription"):\n'
     '        setattr(u, f"stripe_{kind}_id", None)\n', False),
    ("name-from-code-the-folder-does-not-run",
     "def f(u, v):\n    setattr(u, ''.join(reversed('di_noitpircsbus_epirts')), v)\n", False),
    ("whole-row-copy",
     "def f(db, old):\n    make_transient(old)\n    old.id = None\n    db.add(old)\n" + _DECOY, True),
    ("insert-from-select-copy",
     "def f(db, cols):\n    db.execute(insert(Subscription).from_select(cols, select(*cols)))\n" + _DECOY, True),
    ("delete-the-subscription-row", "def f(db, sub):\n    db.delete(sub)\n" + _DECOY, True),
    ("re-parent-the-subscription-row", "def f(sub, other_user_id):\n    sub.user_id = other_user_id\n" + _DECOY, True),
    ("replace-the-subscription-row",
     "def f(u, status):\n    u.subscription = Subscription(user_id=u.id, status=status)\n" + _DECOY, True),
]


# The same scan over a migration, shell script or workflow, read as text.
TEXT_PLANTED = [
    ("migration-clears-the-binding", "UPDATE subscriptions SET stripe_subscription_id = NULL WHERE status = 'canceled';\n",
     {("<file>", "text")}),
    ("upper-case-column", "UPDATE users SET STRIPE_SUBSCRIPTION_ID = NULL;\n", {("<file>", "text")}),
    ("backfill-copies-the-mirror",
     "INSERT INTO subscriptions (user_id, stripe_subscription_id)\nSELECT id, stripe_subscription_id FROM users;\n",
     {("<file>", "text")}),
    ("psql-in-a-workflow-step", '      - run: psql -c "UPDATE users SET stripe_subscription_id = NULL"\n',
     {("<file>", "text")}),
    ("dynamic-sql-in-a-do-block",
     "-- clears stripe_subscription_id\nDO $$ BEGIN EXECUTE format('UPDATE users SET %I = NULL', col); END $$;\n",
     {("<file>", "text"), ("<file>", "dynamic")}),
    ("dynamic-sql-from-a-variable",
     "DO $$ DECLARE stmt text := 'UPDATE users SET stripe_subscription_id = NULL'; BEGIN EXECUTE stmt; END $$;\n",
     {("<file>", "text"), ("<file>", "dynamic")}),
    ("dynamic-sql-in-other-shapes",
     "-- stripe_subscription_id\nDO $$ BEGIN EXECUTE concat('UPDATE users SET ', c, ' = NULL'); "
     "EXECUTE E'UPDATE users SET ' || c; EXECUTE ('UPDATE users SET ' || c || ' = NULL'); END $$;\n",
     {("<file>", "text"), ("<file>", "dynamic")}),
    ("escaped-quote-in-an-e-string",
     "DO $$ BEGIN RAISE NOTICE E'it\\'s -- not a comment'; EXECUTE stmt; END $$; -- stripe_subscription_id\n",
     {("<file>", "text"), ("<file>", "dynamic")}),
    ("dashes-inside-a-string-hide-nothing",
     "-- stripe_subscription_id\nDO $$ BEGIN RAISE NOTICE '-- start'; EXECUTE stmt; END $$;\n",
     {("<file>", "text"), ("<file>", "dynamic")}),
    ("other-column", "UPDATE users SET stripe_customer_id = NULL;\nDO $$ BEGIN EXECUTE 'SELECT 1'; END $$;\n", set()),
    # A trigger's EXECUTE FUNCTION, a gcloud job and a comment run no dynamic SQL.
    ("look-alikes",
     "-- stripe_subscription_id: execute this once\n"
     "CREATE TRIGGER touch AFTER UPDATE ON subscriptions FOR EACH ROW EXECUTE FUNCTION touch();\n",
     {("<file>", "text")}),
]
# A workflow or shell script: whole-line comments and gcloud's ``jobs execute`` run no SQL.
SHELL_TEXT_PLANTED = [
    ("gcloud-jobs-beside-the-column",
     "# stripe_subscription_id is never touched here\n      - run: gcloud run jobs execute migrate --region us-west1 || true\n"
     "      - run: gcloud sql connect db --execute status\n", {("<file>", "text")}),
    ("comment-line-and-gcloud-beside-the-column",
     "# EXECUTE stmt;\n      - run: gcloud run jobs execute migrate || true  # stripe_subscription_id\n",
     {("<file>", "text")}),
    ("psql-dynamic-sql-in-a-step", '      - run: psql -c "DO $$ BEGIN EXECUTE stmt; END $$" # stripe_subscription_id\n',
     {("<file>", "text"), ("<file>", "dynamic")}),
]
# Named gaps: a file that never names the column (a whole-row copy, a psql variable, a dynamic name
# built in SQL, deleting the Subscription row).
TEXT_GAPS = [
    ("whole-row-copy", "INSERT INTO subscriptions SELECT * FROM subscriptions_backup;\n"),
    ("psql-variable-column", "UPDATE subscriptions SET :col = NULL;\n"),
    ("name-built-in-sql",
     "DO $$ BEGIN EXECUTE format('UPDATE users SET %I = NULL', 'stripe_' || 'subscription_id'); END $$;\n"),
    ("delete-the-subscription-rows", "DELETE FROM subscriptions WHERE status = 'canceled';\n"),
    ("re-parent-the-subscription-row", "UPDATE subscriptions SET user_id = 7 WHERE id = 3;\n"),
    ("positional-insert", "INSERT INTO subscriptions VALUES (1, 2, 'pro', 'active', 'cus_x', 'sub_x');\n"),
    ("copy-from-a-file", "COPY subscriptions FROM '/tmp/subs.csv' WITH (FORMAT csv);\n"),
    ("psql-meta-copy", "\\copy subscriptions FROM 'subs.csv' csv\n"),
    ("name-built-in-the-shell", 'col="stripe_""subscription_id"\npsql -c "UPDATE users SET $col = NULL"\n'),
]


@pytest.mark.parametrize("source, expected", [p[1:] for p in PLANTED], ids=[p[0] for p in PLANTED])
def test_the_binding_mention_scan_scores_every_planted_form(source, expected):
    assert _mentions(source) == expected


@pytest.mark.parametrize("source, in_scope", [g[1:] for g in GAPS], ids=[g[0] for g in GAPS])
def test_the_binding_scan_gaps_stay_out_of_reach(source, in_scope):
    tree = ast.parse(source)
    assert _names_the_model(tree, _docstring_ids(tree)) is in_scope
    assert {scope for scope, _ in _mentions(source)} <= {"decoy"}


@pytest.mark.parametrize("text, expected", [p[1:] for p in TEXT_PLANTED], ids=[p[0] for p in TEXT_PLANTED])
def test_the_binding_text_scan_scores_every_planted_form(text, expected):
    assert set(_text_mention_counts(text)) == expected


@pytest.mark.parametrize("text, expected", [p[1:] for p in SHELL_TEXT_PLANTED], ids=[p[0] for p in SHELL_TEXT_PLANTED])
def test_the_binding_text_scan_reads_a_workflow_as_shell(text, expected):
    assert set(_text_mention_counts(text, sql=False)) == expected


@pytest.mark.parametrize("text", [g[1] for g in TEXT_GAPS], ids=[g[0] for g in TEXT_GAPS])
def test_the_binding_text_scan_gaps_stay_out_of_reach(text):
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


def test_every_mention_of_the_binding_is_reviewed():
    found: Counter[tuple[str, str, str]] = Counter()
    for path in _scanned_files():
        rel = path.relative_to(REPO_DIR).as_posix()
        for (scope, kind), count in _file_mention_counts(path).items():
            found[(rel, scope, kind)] += count

    new = sorted((found - Counter(BINDING_MENTIONS)).items())
    stale = sorted((Counter(BINDING_MENTIONS) - found).items())
    assert not new and not stale, (
        f"{COLUMN} mentions changed. New, to review, then raise or add the listed count by the number "
        f"shown: {new}. Gone, to lower or remove by the number shown: {stale}. A new writer of the billing "
        "binding must check the event's subscription against the bound one before it writes "
        "(lessons/arch-guard-every-writer-of-the-billing-binding.md): give it that guard and its late-event "
        "case in this file, then list it here; SQL that writes the column (a migration, an ops/ or tasks/ file, a script, a workflow step) must never "
        "replace or clear a bound row (insert only where none exists, as the 2026-06-17 seed does), and "
        "its entry says so; list a non-writer with its reason. Kinds are syntactic, so "
        "review the line, not the label: 'read', 'string', 'keyword' and 'text' can each be part of a write, and "
        "'key' is the column as a mapping key, the shape of a row write. A 'dynamic' mention is a place in "
        "a module that names the column where a column could be picked at run time (setattr with a "
        "computed name, row data that is not a literal mapping, **kwargs): spell the column out, or list "
        "it with why it cannot reach the binding. Swapping one mention for another of the same kind in "
        "the same scope (a text file is one scope) keeps the counts equal and is not seen. See the comment block above "
        "BINDING_MENTIONS."
    )
