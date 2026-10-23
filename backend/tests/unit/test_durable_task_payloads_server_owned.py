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
guard, and that the filings budget's size stays under the queue's drain across the API's instances,
are pinned by ``test_filings_routes.py``; the synchronous SEC calls such a route makes (reached
through services and edgartools, out of an AST walk's reach) are review-checked.

Known limits, review-checked: ``.id`` is accepted from any object, so a request model's ``.id``
passes as a row's. Callers of the exempt ``enqueue_internal_job`` are not followed; today all 10
routes that reach it carry ``Depends(_require_internal_token)``. An enqueuer looked up by a string
(``getattr(module, "enqueue_task")``) is out of reach. The login dependency, like the limiter, is
known by its name: a bare ``Depends(get_current_user)`` passes whatever ``get_current_user`` the
router defines or imports, while attribute access and ``Annotated`` fail closed.
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


def _spends_a_budget_first(fn: ast.AST, call: ast.Call, tree: ast.Module) -> bool:
    """``fn`` returns ahead of the statement holding ``call`` unless a module-level limiter admits it, on
    one literal key, so the count is the process's whoever asks."""
    for stmt in fn.body:
        if any(node is call for node in ast.walk(stmt)):
            return False
        test = stmt.test if isinstance(stmt, ast.If) else None
        admits = test.operand if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not) else None
        if (isinstance(admits, ast.Call) and isinstance(admits.func, ast.Attribute) and admits.func.attr == "allow"
                and isinstance(admits.func.value, ast.Name) and admits.func.value.id in _limiters(tree)
                and len(admits.args) == 1 and not admits.keywords and isinstance(admits.args[0], ast.Constant)
                and isinstance(admits.args[0].value, str)
                and len(stmt.body) == 1 and isinstance(stmt.body[0], ast.Return) and not stmt.orelse):
            return True
    return False


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
