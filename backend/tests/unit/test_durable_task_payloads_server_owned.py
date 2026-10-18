"""Gate for ``lessons/arch-caller-input-never-names-a-durable-task.md``: a public route's durable task
is named only by server-owned values.

``enqueue_task`` names a task ``sha256(key:body)``, so whatever a route puts in the payload or the
dedupe key decides how many distinct tasks its callers can queue. This AST walk finds every call of
an enqueuer under ``app/``, by its name or an import alias. In ``app/routers/`` the payload must be a
dict literal with literal keys and the key a literal or f-string, built only from
``SERVER_OWNED_NAMES`` (never a route parameter, and bound in the route only by plain assignment
from a resolved row's ``.id``) and ``SERVER_OWNED_CALLS`` (fixed vocabularies, no arguments).
Every such call passes a key, because a keyless task is named at random and so each request would
queue a new one. Its window (``seconds``/``dedupe_seconds``) sets the time bucket appended to the
key, so it is a literal or built only from module-level names and builtins, never from the route's
own values. A ``PASS_THROUGH`` wrapper is exempt because its callers are checked as enqueue sites,
and only while it hands ``enqueue_task`` its own kind, payload, key and window unchanged. Any other
site must be listed in ``EXEMPT`` with its reason, and a listed site that is gone fails. Growing any
of these sets is a reviewed change to this file.

Known limits, review-checked: ``.id`` is accepted from any object, so a request model's ``.id``
passes as a row's. Callers of the exempt ``enqueue_internal_job`` are not followed; today all 10
routes that reach it carry ``Depends(_require_internal_token)``.
"""
import ast
import builtins
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[2] / "app"
PASS_THROUGH = {("routers/filings.py", "_enqueue_visit_task")}
ENQUEUERS = {"enqueue_task"} | {name for _, name in PASS_THROUGH}
KEYS, WINDOWS = ("key", "dedupe_key"), ("seconds", "dedupe_seconds")
SERVER_OWNED_NAMES = {"company_id"}
SERVER_OWNED_CALLS = {"company_list_forms"}
EXEMPT = {
    ("services/internal_task_runner.py", "enqueue_internal_job"): "operator routes (_require_internal_token)",
    ("services/internal_task_runner.py", "run_internal_task"): "worker-side fan-out of an operator job",
}


def _called_name(call: ast.Call) -> str | None:
    func = call.func
    return func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None


def _sites():
    for py in sorted(APP_DIR.rglob("*.py")):
        rel = py.relative_to(APP_DIR).as_posix()
        tree = ast.parse(py.read_text(encoding="utf-8"))
        enqueuers = ENQUEUERS | {a.asname for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)
                                 for a in n.names if a.name in ENQUEUERS and a.asname}
        for fn in ast.walk(tree):
            if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                nested = {id(n) for d in ast.walk(fn) if d is not fn and isinstance(d, (ast.FunctionDef, ast.AsyncFunctionDef)) for n in ast.walk(d)}
                for node in ast.walk(fn):
                    if isinstance(node, ast.Call) and id(node) not in nested and _called_name(node) in enqueuers:
                        yield rel, tree, fn, node


def _params(fn: ast.AST) -> list[str]:
    args = fn.args
    return [a.arg for a in args.posonlyargs + args.args + args.kwonlyargs + [v for v in (args.vararg, args.kwarg) if v]]


def _stored(fn: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(fn) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}


def _server_owned(expr: ast.expr, fn: ast.AST) -> bool:
    if isinstance(expr, ast.Call):
        return _called_name(expr) in SERVER_OWNED_CALLS and not expr.args and not expr.keywords
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
    return ([ast.unparse(a) for a in call.args] == params[:2] and {"key", "seconds"} <= set(params)
            and forwarded == {"dedupe_key": "key", "dedupe_seconds": "seconds"}
            and not {*params[:2], "key", "seconds"} & _stored(fn))


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
        if any(not (isinstance(p, ast.Constant) or (isinstance(p, ast.FormattedValue) and _server_owned(p.value, fn)))
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
        if (rel, fn.name) in PASS_THROUGH:
            seen.add((rel, fn.name))
            if not _forwards_unchanged(fn, call):
                offenders.append(f"{rel}:{call.lineno} {fn.name}: a pass-through must hand enqueue_task its own "
                                 f"kind, payload, key and window unchanged: {ast.unparse(call)}")
        elif (rel, fn.name) in EXEMPT:
            seen.add((rel, fn.name))
        elif rel.startswith("routers/"):
            offenders += _violations(rel, tree, fn, call)
        else:
            offenders.append(f"{rel}:{call.lineno} {fn.name}: unlisted enqueue site; add it to EXEMPT with its reason")
    assert not offenders, "\n".join(offenders)
    listed = set(EXEMPT) | PASS_THROUGH
    assert seen == listed, f"stale EXEMPT or PASS_THROUGH entries: {listed - seen}"
