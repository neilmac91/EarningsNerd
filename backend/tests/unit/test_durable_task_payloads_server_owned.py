"""Gate for ``lessons/arch-caller-input-never-names-a-durable-task.md``: a public route's durable task
is named only by server-owned values.

``enqueue_task`` names a task ``sha256(key:body)``, so whatever a route puts in the payload or the
dedupe key decides how many distinct tasks its callers can queue. This AST walk finds every call of
an enqueuer under ``app/`` by its own name and checks it as a site of the def it sits directly in. So
an enqueuer is imported only by that name, absolutely, from the module that defines it (an alias or a
re-export would name it something the walk does not look for); it is called only directly in a def,
never at module or class level or in a lambda, where no list could name the site; and any other use
of one (an assignment alias such as ``submit = enqueue_task``, a ``partial``, a callback argument)
fails, since the walk could not see its calls. In ``app/routers/`` the payload must be a
dict literal with literal keys and the key a literal or f-string, built only from
``SERVER_OWNED_NAMES`` (never a route parameter, and bound in the route only by plain assignment
from a resolved row's ``.id``) and ``SERVER_OWNED_CALLS`` (fixed vocabularies called bare with no
arguments, each bound in its module only by its import from the source named here, as Python's own
symbol table resolves it, so a router cannot rebind one to return caller input). An f-string part
takes no format spec, since a spec is an expression of its own. A route may queue one task per
fixed vocabulary, each behind any condition, so how many tasks a company can have per bucket stays
review-checked. Every such call passes a key, because a keyless task is named at random and so each
request would queue a new one. Its window (``seconds``/``dedupe_seconds``) sets the time bucket appended to the
key, so it is a literal or built only from module-level names and builtins, never from the route's
own values. A ``PASS_THROUGH`` wrapper is exempt because its callers are checked as enqueue sites,
and only while it hands ``enqueue_task`` its own kind, payload, key and window unchanged and takes
no other parameter (one would carry caller input past the checked call sites). Any other
site must be listed in ``EXEMPT`` with its reason, and a listed site that is gone fails. Growing any
of these sets is a reviewed change to this file.

A route that needs no login bounds the handoffs its callers can cause: in ``app/routers/`` a direct
``enqueue_task`` call sits in a route that takes ``Depends(get_current_user)``, and a ``PASS_THROUGH``
spends a process-wide budget before it hands off, an ``if not LIMITER.allow("<key>"): return`` among
its own statements ahead of the call, ``LIMITER`` a module-level ``RateLimiter`` bound once. Any other
form fails closed. The limiter is known by its class name. That it is spent only past the handoff
guard is pinned by ``test_filings_routes.py``, which also sums, across the API's instances, the cap on
every site a request with no login reaches (``public_queue_caps``: each ``PASS_THROUGH``'s budget and
key, as its budget check names them, and each ``EXEMPT`` site's in ``EXEMPT_PUBLIC_CAPS``, which must
list every ``EXEMPT`` site; a limiter counts once per key) against the drain of the one queue they all
share; the synchronous SEC calls such a route makes (reached through services and edgartools, out of an
AST walk's reach) are review-checked.

The exempt ``queue_account_mail`` carries a caller's address (F60), so its callers are followed:
``test_account_mail_is_queued_only_behind_the_two_routes_limits`` holds it to one helper in the auth
router, the helper to the forgot-password and resend-verification routes, each after its per-IP and
per-address limits, and the helper to the process-wide account-mail cap before its handoff, charged on
the one literal key ``EXEMPT_PUBLIC_CAPS`` names with ``include_client_ip=False``, so every caller
shares it (any other form fails closed).

Known limits, review-checked: ``.id`` is accepted from any object, so a request model's ``.id``
passes as a row's. Callers of the exempt ``enqueue_internal_job`` are not followed; today all 10
routes that reach it carry ``Depends(_require_internal_token)``. An enqueuer looked up by a string
(``getattr(module, "enqueue_task")``) is out of reach, as is a limit a route takes inside a branch
of its own (the account-mail check counts only the route's own top-level calls). The login
dependency, like the limiter, is known by its name: a bare ``Depends(get_current_user)`` passes
whatever ``get_current_user`` the router defines or imports, while attribute access and
``Annotated`` fail closed.
"""
import ast
import builtins
import symtable
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[2] / "app"
PASS_THROUGH = {("routers/filings.py", "_enqueue_visit_task")}
ENQUEUERS = {"enqueue_task"} | {name for _, name in PASS_THROUGH}
ENQUEUER_SOURCES = {"enqueue_task": "app.services.durable_tasks"}  # a pass-through is never imported
KEYS, WINDOWS = ("key", "dedupe_key"), ("seconds", "dedupe_seconds")
SERVER_OWNED_NAMES = {"company_id"}
LOGIN = "get_current_user"  # a route that depends on it answers an anonymous caller 401
SERVER_OWNED_CALLS = {
    "company_list_forms": "app.services.latest_filing_service",
    "other_filing_forms": "app.services.filing_list_service",
}
EXEMPT = {
    ("services/internal_task_runner.py", "enqueue_internal_job"): "operator routes (_require_internal_token)",
    ("services/internal_task_runner.py", "run_internal_task"): "worker-side fan-out of an operator job",
    ("services/account_mail_service.py", "queue_account_mail"): (
        "F60's account mail (the founder's option B): both branches of forgot-password and resend-verification "
        "queue it before any lookup, so it carries the address the request schema validated, with a fixed "
        "two-mail vocabulary; the routes' per-IP and per-address limits bound each caller and the process-wide "
        "account-mail cap bounds them all (callers pinned by the account-mail test below)"
    ),
}
# The account mail's callers (F60): the one helper that may name the exempt enqueue, the routes that may call
# that helper, and the limits each must take first.
ACCOUNT_MAIL_HELPER = ("routers/auth.py", "_queue_account_mail")
ACCOUNT_MAIL_ROUTES = {"forgot_password", "resend_verification"}
ACCOUNT_MAIL_CAP = "ACCOUNT_MAIL_LIMITER"
ACCOUNT_MAIL_CAP_KEY = "account-mail"  # the one key the helper charges the cap on, for every caller


def _module_of(rel: str) -> str:
    return "app." + rel.removesuffix(".py").replace("/", ".")


# Every EXEMPT site, with the process-wide cap that bounds it when a request that needs no login reaches it,
# as (module, RateLimiter name, the one key charged), else None. These and each PASS_THROUGH's budget are the
# caps test_filings_routes.py sums, times the API's instances, against the drain of the one queue every
# durable task shares, so a new EXEMPT site must say here whether such a request reaches it, and what caps it.
EXEMPT_PUBLIC_CAPS = {
    ("services/internal_task_runner.py", "enqueue_internal_job"): None,  # its routes take the internal token
    ("services/internal_task_runner.py", "run_internal_task"): None,  # the worker's fan-out of an operator job
    ("services/account_mail_service.py", "queue_account_mail"): (
        _module_of(ACCOUNT_MAIL_HELPER[0]), ACCOUNT_MAIL_CAP, ACCOUNT_MAIL_CAP_KEY,
    ),
}


def _called_name(call: ast.Call) -> str | None:
    func = call.func
    return func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None


def _modules():
    for py in sorted(APP_DIR.rglob("*.py")):
        yield py.relative_to(APP_DIR).as_posix(), ast.parse(py.read_text(encoding="utf-8"))


def _misimported(tree: ast.AST) -> list[ast.ImportFrom]:
    """Each import of an enqueuer other than ``from <its module> import <its name>``: an alias or a re-export
    names it something ``_enqueue_calls`` does not look for (a relative import is flagged too)."""
    return [n for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for a in n.names
            if a.name in ENQUEUERS and (a.asname not in (None, a.name) or n.module != ENQUEUER_SOURCES.get(a.name))]


def _escaping(tree: ast.AST, enqueuers: set[str]) -> list[ast.expr]:
    """Each read of an enqueuer that is not a call's callee: an alias, a partial or a callback, whose calls
    ``_enqueue_calls`` cannot find."""
    callees = {id(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
    return [n for n in ast.walk(tree) if isinstance(n, (ast.Name, ast.Attribute)) and isinstance(n.ctx, ast.Load)
            and (n.id if isinstance(n, ast.Name) else n.attr) in enqueuers and id(n) not in callees]


def _scoped(node: ast.AST, scope: ast.AST | None = None):
    """Each node under ``node`` with the def or lambda it sits directly in, None at module or class level."""
    for child in ast.iter_child_nodes(node):
        yield child, scope
        yield from _scoped(child, child if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)) else scope)


def _enqueue_calls(tree: ast.AST):
    """Each call of an enqueuer with the def it sits directly in, or None when it sits at module or class level
    or in a lambda, where no list can name its site."""
    for node, scope in _scoped(tree):
        if isinstance(node, ast.Call) and _called_name(node) in ENQUEUERS:
            yield (scope if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)) else None), node


def _sites():
    for rel, tree in _modules():
        for fn, call in _enqueue_calls(tree):
            yield rel, tree, fn, call


def _params(fn: ast.AST) -> list[str]:
    args = fn.args
    return [a.arg for a in args.posonlyargs + args.args + args.kwonlyargs + [v for v in (args.vararg, args.kwarg) if v]]


def _stored(fn: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(fn) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}


def _scopes(table):
    """``table`` and every scope nested in it."""
    yield table
    for child in table.get_children():
        yield from _scopes(child)


def _bound_only_by_import(text: str, name: str, origin: str) -> bool:
    """Every scope of the module ``text`` reads ``name`` from its ``from <origin> import name``, and nothing
    rebinds it: no other import of it, no assignment or def at module level, no binding in any scope."""
    imports = [n for n in ast.walk(ast.parse(text)) if isinstance(n, (ast.Import, ast.ImportFrom))
               and any((a.asname or a.name).split(".")[0] == name for a in n.names)]
    if not imports or any(not isinstance(n, ast.ImportFrom) or n.module != origin for n in imports):
        return False
    module, *nested = _scopes(symtable.symtable(text, "<route module>", "exec"))
    return not module.lookup(name).is_assigned() and all(
        scope.lookup(name).is_global() and not scope.lookup(name).is_declared_global()
        for scope in nested if name in scope.get_identifiers())


def _server_owned(expr: ast.expr, fn: ast.AST) -> bool:
    if isinstance(expr, ast.Call):
        return (isinstance(expr.func, ast.Name) and expr.func.id in SERVER_OWNED_CALLS
                and not expr.args and not expr.keywords)
    if not (isinstance(expr, ast.Name) and expr.id in SERVER_OWNED_NAMES):
        return False
    from_rows = [t for n in ast.walk(fn) if isinstance(n, ast.Assign) and isinstance(n.value, ast.Attribute)
                 and n.value.attr == "id" for t in n.targets if isinstance(t, ast.Name) and t.id == expr.id]
    stores = [n for n in ast.walk(fn) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store) and n.id == expr.id]
    return expr.id not in _params(fn) and bool(from_rows) and len(from_rows) == len(stores)


def _module_level(expr: ast.expr, fn: ast.AST, tree: ast.Module) -> bool:
    names = set(vars(builtins))
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names |= {(a.asname or a.name).split(".")[0] for a in node.names}
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            names |= {t.id for t in (node.targets if isinstance(node, ast.Assign) else [node.target])
                      if isinstance(t, ast.Name)}
    local = set(_params(fn)) | _stored(fn)
    return all(n.id in names and n.id not in local for n in ast.walk(expr) if isinstance(n, ast.Name))


def _forwards_unchanged(fn: ast.AST, call: ast.Call) -> bool:
    params = _params(fn)
    forwarded = {k.arg: ast.unparse(k.value) for k in call.keywords}
    return (len(params) == 4 and [ast.unparse(a) for a in call.args] == params[:2] and {"key", "seconds"} <= set(params)
            and forwarded == {"dedupe_key": "key", "dedupe_seconds": "seconds"}
            and not {*params[:2], "key", "seconds"} & _stored(fn))


def _limiters(tree: ast.Module) -> set[str]:
    """Module-level names bound to a ``RateLimiter(...)`` and bound nowhere else in the module."""
    stores = [n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)]
    return {t.id for node in tree.body if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)
            and _called_name(node.value) == "RateLimiter" for t in node.targets
            if isinstance(t, ast.Name) and stores.count(t.id) == 1}


def _budget_spent_first(fn: ast.AST, call: ast.Call, tree: ast.Module) -> tuple[str, str] | None:
    """The module-level limiter that must admit ``fn``, and the one literal key it charges, before the
    statement holding ``call``, ``fn`` returning otherwise, so the count is the process's whoever asks; None
    when there is none."""
    for stmt in fn.body:
        if any(node is call for node in ast.walk(stmt)):
            return None
        test = stmt.test if isinstance(stmt, ast.If) else None
        admits = test.operand if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not) else None
        if (isinstance(admits, ast.Call) and isinstance(admits.func, ast.Attribute) and admits.func.attr == "allow"
                and isinstance(admits.func.value, ast.Name) and admits.func.value.id in _limiters(tree)
                and len(admits.args) == 1 and not admits.keywords and isinstance(admits.args[0], ast.Constant)
                and isinstance(admits.args[0].value, str)
                and len(stmt.body) == 1 and isinstance(stmt.body[0], ast.Return) and not stmt.orelse):
            return admits.func.value.id, admits.args[0].value
    return None


def _spends_a_budget_first(fn: ast.AST, call: ast.Call, tree: ast.Module) -> bool:
    return _budget_spent_first(fn, call, tree) is not None


def public_queue_caps() -> dict[tuple[str, str], tuple[str, str, str]]:
    """Every enqueue site a request that needs no login reaches, with the process-wide cap that bounds it as
    (module, RateLimiter name, key): each PASS_THROUGH's budget and key, as its own budget check names them,
    and each EXEMPT site's listed cap. A limiter keeps one window per key, so each distinct triple is a budget
    of its own. A direct router call needs a login, so none is among them."""
    caps = {site: cap for site, cap in EXEMPT_PUBLIC_CAPS.items() if cap is not None}
    for rel, tree, fn, call in _sites():
        if fn is not None and (rel, fn.name) in PASS_THROUGH:
            budget = _budget_spent_first(fn, call, tree)
            assert budget, f"{rel} {fn.name}: a PASS_THROUGH that spends no budget cannot be counted"
            caps[(rel, fn.name)] = (_module_of(rel), *budget)
    return caps


def _requires_login(fn: ast.AST) -> bool:
    """A parameter of ``fn`` defaults to ``Depends(get_current_user)``."""
    defaults = fn.args.defaults + [d for d in fn.args.kw_defaults if d is not None]
    return any(isinstance(d, ast.Call) and isinstance(d.func, ast.Name) and d.func.id == "Depends"
               and len(d.args) == 1 and not d.keywords and isinstance(d.args[0], ast.Name) and d.args[0].id == LOGIN
               for d in defaults)


def _violations(rel: str, tree: ast.Module, fn: ast.AST, call: ast.Call) -> list[str]:
    kwargs = {k.arg: k.value for k in call.keywords}
    payload = call.args[1] if len(call.args) > 1 else kwargs.get("payload")
    problems = []
    if not (call.args and isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, str)):
        problems.append("kind is not a string literal")
    if not (isinstance(payload, ast.Dict) and all(isinstance(k, ast.Constant) for k in payload.keys)
            and all(_server_owned(v, fn) for v in payload.values)):
        problems.append(f"payload is not built from server-owned values: {ast.unparse(payload) if payload else None}")
    if None in kwargs:
        problems.append(f"passes **{ast.unparse(kwargs[None])}, which hides its key and window from this check")
    keys = [kwargs[name] for name in KEYS if name in kwargs]
    if not keys or any(isinstance(k, ast.Constant) and not k.value for k in keys):
        problems.append("passes no dedupe key, so each call gets a random task name and every request queues a new task")
    for name in KEYS:
        key = kwargs.get(name)
        parts = key.values if isinstance(key, ast.JoinedStr) else [key] if key is not None else []
        if any(not (isinstance(p, ast.Constant) or (isinstance(p, ast.FormattedValue) and p.format_spec is None
                                                    and _server_owned(p.value, fn)))
               for p in parts):
            problems.append(f"{name} is not built from server-owned values: {ast.unparse(key)}")
    for name in WINDOWS:
        window = kwargs.get(name)
        if window is not None and not _module_level(window, fn, tree):
            problems.append(f"{name} is not a literal or module-level constant: {ast.unparse(window)}")
    return [f"{rel}:{call.lineno} {fn.name}: {p}" for p in problems]


def test_public_durable_tasks_are_named_only_by_server_owned_values():
    offenders, seen = [], set()
    for rel, tree, fn, call in _sites():
        if fn is None:
            offenders.append(f"{rel}:{call.lineno}: an enqueuer called at module or class level or in a lambda, "
                             "where no list can name its site; call it directly in a def")
        elif (rel, fn.name) in PASS_THROUGH:
            seen.add((rel, fn.name))
            if not _forwards_unchanged(fn, call):
                offenders.append(f"{rel}:{call.lineno} {fn.name}: a pass-through must hand enqueue_task its own "
                                 f"kind, payload, key and window unchanged, and take no other parameter: {ast.unparse(call)}")
            if not _spends_a_budget_first(fn, call, tree):
                offenders.append(f"{rel}:{call.lineno} {fn.name}: a pass-through must spend a process-wide budget "
                                 "before it hands off: `if not LIMITER.allow(\"<key>\"): return` ahead of the call, "
                                 "LIMITER a module-level RateLimiter")
        elif (rel, fn.name) in EXEMPT:
            seen.add((rel, fn.name))
        elif rel.startswith("routers/"):
            offenders += _violations(rel, tree, fn, call)
            if _called_name(call) == "enqueue_task" and not _requires_login(fn):
                offenders.append(f"{rel}:{call.lineno} {fn.name}: a route that needs no login hands a durable task "
                                 "off only through a budgeted PASS_THROUGH; or take Depends(get_current_user)")
        else:
            offenders.append(f"{rel}:{call.lineno} {fn.name}: unlisted enqueue site; add it to EXEMPT with its reason")
    for rel, tree in _modules():
        offenders += [f"{rel}:{n.lineno}: {ast.unparse(n)} imports an enqueuer other than by its own name, absolutely, "
                      "from the module that defines it (a pass-through is never imported), so its calls escape this "
                      "check" for n in _misimported(tree)]
        offenders += [f"{rel}:{n.lineno}: {ast.unparse(n)} is used other than as a direct call, so its calls "
                      "escape this check; call it by name" for n in _escaping(tree, ENQUEUERS)]
        offenders += [f"{rel}: {name} is bound other than by its import from {origin}, so a call to it may not "
                      "return the fixed vocabulary" for name, origin in SERVER_OWNED_CALLS.items()
                      if rel.startswith("routers/") and any(isinstance(n, ast.Name) and n.id == name for n in ast.walk(tree))
                      and not _bound_only_by_import((APP_DIR / rel).read_text(encoding="utf-8"), name, origin)]
    assert not offenders, "\n".join(offenders)
    listed = set(EXEMPT) | PASS_THROUGH
    assert seen == listed, f"stale EXEMPT or PASS_THROUGH entries: {listed - seen}"


def test_every_exempt_site_says_whether_a_request_without_a_login_reaches_it():
    """``test_filings_routes.py`` sums the caps of the sites such a request reaches against the shared queue's
    drain (``public_queue_caps``), so an EXEMPT site left out of ``EXEMPT_PUBLIC_CAPS`` could feed that queue
    uncounted."""
    assert set(EXEMPT_PUBLIC_CAPS) == set(EXEMPT), "list each EXEMPT site in EXEMPT_PUBLIC_CAPS with its cap, or None"


@pytest.mark.parametrize("source,escapes", [
    ("submit = enqueue_task", 1),
    ("submit = durable_tasks.enqueue_task", 1),
    ("run(partial(_enqueue_visit_task, 'filings'))", 1),
    ("await enqueue_task('filings', {}, dedupe_key='k')", 0),
    ("await durable_tasks.enqueue_task('filings', {}, dedupe_key='k')", 0),
])
def test_an_enqueuer_used_other_than_as_a_call_is_flagged(source, escapes):
    assert len(_escaping(ast.parse(source), ENQUEUERS)) == escapes


@pytest.mark.parametrize("source,misimported", [
    ("from app.services.durable_tasks import enqueue_task", 0),
    ("from app.services.durable_tasks import enqueue_task as submit", 1),
    ("from app.services.queues import enqueue_task", 1),
    ("from app.routers.filings import _enqueue_visit_task", 1),
])
def test_an_enqueuer_is_imported_only_by_its_own_name_from_its_module(source, misimported):
    assert len(_misimported(ast.parse(source))) == misimported


@pytest.mark.parametrize("source,site", [
    ("async def route():\n    await enqueue_task('filings', {}, dedupe_key='k')\n", "route"),
    ("async def route():\n    async def inner():\n        await enqueue_task('filings', {}, dedupe_key='k')\n", "inner"),
    ("submit = lambda kind, payload, **kw: enqueue_task(kind, payload, **kw)\n", None),
    ("async def route():\n    submit = lambda payload: enqueue_task('filings', payload, dedupe_key='k')\n", None),
    ("class Jobs:\n    queued = enqueue_task('filings', {}, dedupe_key='k')\n", None),
])
def test_an_enqueue_call_is_a_site_of_the_def_it_sits_directly_in(source, site):
    [(fn, _call)] = _enqueue_calls(ast.parse(source))
    assert (fn.name if fn else None) == site


@pytest.mark.parametrize("source,forwards", [
    ("async def w(kind, payload, *, key, seconds):\n"
     "    await enqueue_task(kind, payload, dedupe_key=key, dedupe_seconds=seconds)\n", True),
    ("async def w(kind, payload, types, *, key, seconds):\n    payload['filing_types'] = types\n"
     "    await enqueue_task(kind, payload, dedupe_key=key, dedupe_seconds=seconds)\n", False),
])
def test_a_pass_through_takes_only_what_it_forwards(source, forwards):
    fn = ast.parse(source).body[0]
    call = next(n for n in ast.walk(fn) if isinstance(n, ast.Call) and _called_name(n) == "enqueue_task")
    assert _forwards_unchanged(fn, call) is forwards


FORMS_IMPORT = "from app.services.latest_filing_service import company_list_forms\n"


@pytest.mark.parametrize("source,bound", [
    (FORMS_IMPORT + "def route(filing_types):\n    return company_list_forms()\n", True),
    (FORMS_IMPORT + "company_list_forms = lambda: [filing_types]\n", False),
    (FORMS_IMPORT + "def route(filing_types):\n    company_list_forms = lambda: [filing_types]\n    return company_list_forms()\n", False),
    (FORMS_IMPORT + "def company_list_forms():\n    return []\n", False),
    ("from app.services.other import company_list_forms\n", False),
])
def test_a_fixed_vocabulary_is_bound_only_by_its_import(source, bound):
    assert _bound_only_by_import(source, "company_list_forms", SERVER_OWNED_CALLS["company_list_forms"]) is bound


@pytest.mark.parametrize("key,owned", [
    ('f"filings:{company_id}"', True),
    ('f"filings:{company_id!r}"', True),
    ('f"filings:{company_id:>{len(filing_types)}}"', False),  # the spec reads the route's own values
    ('f"filings:{company_id:>8}"', False),
])
def test_a_key_part_takes_no_format_spec(key, owned):
    tree = ast.parse("async def route(ticker, filing_types):\n    company_id = row.id\n"
                     "    await enqueue_task('filings', {'company_id': company_id}, dedupe_key=" + key + ", dedupe_seconds=60)\n")
    fn = tree.body[0]
    call = next(n for n in ast.walk(fn) if isinstance(n, ast.Call) and _called_name(n) == "enqueue_task")
    assert (_violations("routers/planted.py", tree, fn, call) == []) is owned


def test_a_fixed_vocabulary_is_called_bare_with_no_arguments():
    def expr(source):
        return ast.parse(source, mode="eval").body
    assert _server_owned(expr("company_list_forms()"), None)
    assert not _server_owned(expr("forms.company_list_forms()"), None)
    assert not _server_owned(expr("company_list_forms(filing_types)"), None)


BUDGET = "VISIT_TASK_BUDGET = RateLimiter(limit=20, window_seconds=300)\n"
HANDOFF = "    await enqueue_task(kind, payload, dedupe_key=key, dedupe_seconds=seconds)\n"
SPEND = "    if not VISIT_TASK_BUDGET.allow('visit-tasks'):\n        return\n"


@pytest.mark.parametrize("source,spends", [
    pytest.param(BUDGET + "async def w(kind, payload, *, key, seconds):\n" + SPEND + HANDOFF, True, id="spends"),
    pytest.param(BUDGET + "async def w(kind, payload, *, key, seconds):\n" + HANDOFF, False, id="no-budget"),
    pytest.param(BUDGET + "async def w(kind, payload, *, key, seconds):\n" + HANDOFF + SPEND, False, id="after-the-call"),
    pytest.param(BUDGET + "async def w(kind, payload, *, key, seconds):\n"
                 "    if not VISIT_TASK_BUDGET.allow('visit-tasks'):\n        pass\n" + HANDOFF, False, id="never-refuses"),
    pytest.param(BUDGET + "async def w(kind, payload, *, key, seconds):\n"
                 "    VISIT_TASK_BUDGET.allow('visit-tasks')\n" + HANDOFF, False, id="result-ignored"),
    pytest.param(BUDGET + "async def w(kind, payload, *, key, seconds):\n"
                 "    if not VISIT_TASK_BUDGET.allow(key):\n        return\n" + HANDOFF, False, id="a-count-per-key"),
    pytest.param("VISIT_TASK_BUDGET = object()\nasync def w(kind, payload, *, key, seconds):\n" + SPEND + HANDOFF,
                 False, id="not-a-limiter"),
    pytest.param(BUDGET + "async def w(kind, payload, *, key, seconds):\n"
                 "    VISIT_TASK_BUDGET = RateLimiter(limit=10**9, window_seconds=1)\n" + SPEND + HANDOFF,
                 False, id="rebound"),
])
def test_a_pass_through_spends_a_process_wide_budget_before_it_hands_off(source, spends):
    tree = ast.parse(source)
    fn = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef))
    call = next(n for n in ast.walk(fn) if isinstance(n, ast.Call) and _called_name(n) == "enqueue_task")
    assert _spends_a_budget_first(fn, call, tree) is spends


@pytest.mark.parametrize("signature,login", [
    ("ticker, current_user: User = Depends(get_current_user)", True),
    ("ticker, *, current_user: User = Depends(get_current_user)", True),
    ("ticker, current_user: User = Depends(get_current_user_optional)", False),
    ("ticker, current_user: Annotated[User, Depends(get_current_user)]", False),  # fails closed
    ("ticker, db: Session = Depends(get_db)", False),
])
def test_a_direct_handoff_in_a_router_needs_a_login(signature, login):
    assert _requires_login(ast.parse(f"async def route({signature}):\n    pass\n").body[0]) is login


def _named(node: ast.AST) -> str | None:
    return node.id if isinstance(node, ast.Name) else node.attr if isinstance(node, ast.Attribute) else None


def _top_level_calls(fn: ast.AST, name: str) -> list[int]:
    """The indexes of ``fn``'s own statements that are a call of ``name``, awaited or not."""
    calls = []
    for index, statement in enumerate(fn.body):
        value = statement.value if isinstance(statement, ast.Expr) else None
        value = value.value if isinstance(value, ast.Await) else value
        if isinstance(value, ast.Call) and _called_name(value) == name:
            calls.append(index)
    return calls


def _process_wide_key(call: ast.Call, limiter: str) -> str | None:
    """The key ``call`` charges ``limiter`` on when the call is ``enforce_rate_limit(request, LIMITER, "<key>",
    ..., include_client_ip=False)``, with the key a string literal, so its count is one for every caller; None
    for any other form: a key built from the request, the client IP prefixed (the default), the flag or the key
    passed some other way, or arguments this reading cannot see."""
    kwargs = {k.arg: k.value for k in call.keywords}
    flag = kwargs.get("include_client_ip")
    if (_called_name(call) != "enforce_rate_limit" or len(call.args) != 3 or _named(call.args[1]) != limiter
            or None in kwargs or not (isinstance(flag, ast.Constant) and flag.value is False)
            or not (isinstance(call.args[2], ast.Constant) and isinstance(call.args[2].value, str))):
        return None
    return call.args[2].value


def _account_mail_offenders(modules) -> list[str]:
    """Why the account mail's callers break its exemption, given ``modules`` as (path, tree) pairs."""
    enqueue, helper_rel, helper = "queue_account_mail", *ACCOUNT_MAIL_HELPER
    offenders = []
    for rel, tree in modules:
        callees = {id(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
        offenders += [f"{rel}:{n.lineno}: imports {enqueue}; reach it as account_mail_service.{enqueue} from "
                      f"{helper} alone" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)
                      and any(a.name == enqueue for a in n.names)]
        for node, scope in _scoped(tree):
            name = _named(node)
            if name not in (enqueue, helper) or not isinstance(getattr(node, "ctx", None), ast.Load):
                continue
            where = getattr(scope, "name", None)
            if id(node) not in callees:
                offenders.append(f"{rel}:{node.lineno}: {name} is used other than as a direct call")
            elif name == enqueue and (rel, where) != ACCOUNT_MAIL_HELPER:
                offenders.append(f"{rel}:{node.lineno} {where}: calls {enqueue}; only {helper} may")
            elif name == helper and (rel != helper_rel or where not in ACCOUNT_MAIL_ROUTES):
                offenders.append(f"{rel}:{node.lineno} {where}: calls {helper}; only {sorted(ACCOUNT_MAIL_ROUTES)} may")
    defs = {(rel, fn.name): fn for rel, tree in modules for fn in ast.walk(tree)
            if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef))}
    for route in sorted(ACCOUNT_MAIL_ROUTES):
        fn = defs.get((helper_rel, route))
        handoffs = _top_level_calls(fn, helper) if fn else []
        limits = _top_level_calls(fn, "enforce_rate_limit") if fn else []
        if len(handoffs) != 1 or len([i for i in limits if i < handoffs[0]]) < 2:
            offenders.append(f"{helper_rel} {route}: must call {helper} once, as its own statement, after its "
                             "per-IP and per-address enforce_rate_limit calls")
    body = defs[ACCOUNT_MAIL_HELPER].body if ACCOUNT_MAIL_HELPER in defs else []
    caps = [(i, statement.value) for i, statement in enumerate(body) if isinstance(statement, ast.Expr)
            and isinstance(statement.value, ast.Call) and _called_name(statement.value) == "enforce_rate_limit"
            and any(_named(a) == ACCOUNT_MAIL_CAP for a in statement.value.args)]
    handoff = [i for i, statement in enumerate(body) if any(
        isinstance(n, ast.Call) and _called_name(n) in (enqueue, "add_task") for n in ast.walk(statement))]
    if not caps or not handoff or caps[0][0] > handoff[0]:
        offenders.append(f"{helper_rel} {ACCOUNT_MAIL_HELPER[1]}: must take {ACCOUNT_MAIL_CAP} before its handoff")
    offenders += [f"{helper_rel}:{call.lineno} {ACCOUNT_MAIL_HELPER[1]}: must charge {ACCOUNT_MAIL_CAP} on the one "
                  f"literal key \"{ACCOUNT_MAIL_CAP_KEY}\" with include_client_ip=False, so every caller shares it; keyed "
                  "per client IP or by the request, a caller rotating addresses would get a cap of its own"
                  for _, call in caps if _process_wide_key(call, ACCOUNT_MAIL_CAP) != ACCOUNT_MAIL_CAP_KEY]
    return offenders


def test_account_mail_is_queued_only_behind_the_two_routes_limits():
    """The account mail's EXEMPT entry rests on its callers (F60): only the auth router's helper names the
    enqueue, only forgot-password and resend-verification call the helper, each after its per-IP and
    per-address limits, and the helper takes the process-wide cap before it hands the work off, on one
    literal key and not per client IP, so an address rotating through an IPv6 block meets the same cap."""
    assert _account_mail_offenders(list(_modules())) == []


ROUTES_SRC = """
async def _queue_account_mail(request, background, mail, email):
    enforce_rate_limit(request, ACCOUNT_MAIL_LIMITER, "account-mail", error_detail="x", include_client_ip=False)
    if settings.DURABLE_TASKS_ENABLED:
        await account_mail_service.queue_account_mail(mail, email)
    else:
        background.add_task(account_mail_service.send_account_mail_after_response, mail, email)

async def forgot_password(payload, request, background):
    enforce_rate_limit(request, RESET_RESEND_IP_LIMITER, "reset-ip", error_detail="x")
    enforce_rate_limit(request, RESET_REQUEST_LIMITER, "reset:e", error_detail="x", include_client_ip=False)
    await _queue_account_mail(request, background, "password_reset", payload.email)

async def resend_verification(payload, request, background):
    enforce_rate_limit(request, RESET_RESEND_IP_LIMITER, "resend-ip", error_detail="x")
    enforce_rate_limit(request, RESEND_VERIFY_LIMITER, "resend:e", error_detail="x", include_client_ip=False)
    await _queue_account_mail(request, background, "verification", payload.email)
"""


def _appending(extra: str):
    return lambda source: source + extra


def _handing_off_before_the_per_address_limit(source: str) -> str:
    lines = source.splitlines(keepends=True)
    handoff = next(i for i, line in enumerate(lines) if '"password_reset", payload.email' in line)
    lines.insert(handoff - 1, lines.pop(handoff))
    return "".join(lines)


def _dropping_the_cap(source: str) -> str:
    return "".join(line for line in source.splitlines(keepends=True) if ACCOUNT_MAIL_CAP not in line)


def _on_the_cap_line(change):
    return lambda source: "".join(change(line) if ACCOUNT_MAIL_CAP in line else line
                                  for line in source.splitlines(keepends=True))


@pytest.mark.parametrize("change,offends", [
    (lambda source: source, False),
    (_appending("\nasync def register(request, background):\n"
                "    await _queue_account_mail(request, background, 'verification', 'x')\n"), True),
    (_handing_off_before_the_per_address_limit, True),
    (_dropping_the_cap, True),
    (_on_the_cap_line(lambda line: line.replace(", include_client_ip=False", "")), True),
    (_on_the_cap_line(lambda line: line.replace('"account-mail"', 'f"account-mail:{email}"')), True),
    (_appending("\nasync def other():\n    await account_mail_service.queue_account_mail('verification', 'x')\n"), True),
    (_appending("\nfrom app.services.account_mail_service import queue_account_mail\n"), True),
    (_appending("\nqueue = _queue_account_mail\n"), True),
], ids=["as-built", "third-caller", "handoff-before-limit", "no-cap", "per-ip-cap", "per-address-cap",
        "other-enqueue-caller", "imported", "aliased"])
def test_the_account_mail_check_flags_each_broken_premise(change, offends):
    offenders = _account_mail_offenders([("routers/auth.py", ast.parse(change(ROUTES_SRC)))])
    assert bool(offenders) is offends, offenders
