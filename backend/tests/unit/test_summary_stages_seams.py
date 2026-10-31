"""Gates for the stage decomposition of ``summary_pipeline.stream_filing_summary`` (rule 12).

The ONE summary orchestrator (rule 1) is a short stage map over ``app/services/summary_stages``.
Three things must stay true for that split to be invisible to callers and to the test suite:

1. **Patch seams resolve through the pipeline module.** Tests patch collaborators on the
   ``app.services.summary_pipeline`` MODULE (``patch.object(summary_pipeline, "record_progress", …)``,
   ``monkeypatch.setattr(pipeline, "run_in_threadpool", …)``, ``patch("app.services.summary_pipeline.X")``)
   and expect the patch to take effect at call time. A stage module that imported such a name
   directly would silently bypass every one of those patches, so: every name any test patches on
   the pipeline module is reached in the stages ONLY as ``pipeline.<name>``, never bound by an
   import or used bare; every ``pipeline.<name>`` a stage references actually exists on the module;
   and the stages import nothing from ``app.*`` except the pipeline module, ``app.database`` (whose
   ``SessionLocal`` is patched on that module), the ORM models and the stages package itself.
   ``asyncio`` is the one patched name the stages may use bare — the lifecycle test proxies the
   pipeline's ``asyncio`` only to intercept ``asyncio.timeout(PIPELINE_TIMEOUT_SECONDS)``, which
   therefore stays in the orchestrator: no stage may call ``asyncio.timeout``.
2. **Either import order works.** The stage modules import the pipeline module (circular by design)
   and bind only module objects at import time, so importing a stage module FIRST must succeed.
3. **The terminal-event protocol.** The orchestrator stops after forwarding a ``complete``,
   ``partial`` or ``error`` event. That mirrors the inline body only while every terminal yield in a
   stage is followed by ``return`` or is in tail position (a stage that did work after a terminal
   yield would silently lose it), and while every ``return`` in a stage follows a terminal yield (in
   the inline body a bare ``return`` ended the whole pipeline; in a stage it ends only that stage,
   and the orchestrator would run the next one).

Plus two shape pins from the brief that made this split: the orchestrator stays short, and the
stage loggers are the pipeline's logger (log records keep their logger name).
"""
from __future__ import annotations

import ast
import inspect
import re
import subprocess
import sys
from pathlib import Path

import pytest

from app.services import summary_pipeline
from app.services import summary_stages

BACKEND = Path(__file__).resolve().parents[2]
# Patch sites live in the tests and in the offline acceptance harnesses under evals/.
PATCHING_ROOTS = (BACKEND / "tests", BACKEND / "evals")
STAGES_DIR = BACKEND / "app" / "services" / "summary_stages"
STAGE_MODULES = sorted(p for p in STAGES_DIR.glob("*.py") if p.name != "__init__.py")

PIPELINE_MODULE = "app.services.summary_pipeline"
ALLOWED_APP_IMPORTS = ("app.database", "app.models", PIPELINE_MODULE, "app.services.summary_stages")
# The only patched name the stages may use bare (see the module docstring, point 1).
BARE_ALLOWED = {"asyncio"}

_STRING_TARGET = re.compile(r"patch\(\s*[\"']app\.services\.summary_pipeline\.([A-Za-z_][A-Za-z0-9_]*)[\"']")
# Every name the pipeline module is bound to in a file: ``from app.services import summary_pipeline
# [as X]`` and ``import app.services.summary_pipeline as X``; ``pipeline`` and ``summary_pipeline``
# are always included (fixtures receive the module under those names).
_MODULE_ALIASES = (
    re.compile(r"from\s+app\.services\s+import\s+summary_pipeline(?:\s+as\s+([A-Za-z_][A-Za-z0-9_]*))?"),
    re.compile(r"import\s+app\.services\.summary_pipeline\s+as\s+([A-Za-z_][A-Za-z0-9_]*)"),
)


def patched_pipeline_names() -> set[str]:
    """Every name some test patches ON the pipeline module, through any alias of the module and any
    helper that takes it: ``patch.object(sp, "X", …)``, ``monkeypatch.setattr(pipeline, "X", …)``,
    the stream harness's ``_patch(summary_pipeline, "X", …)``, and ``patch("app.services.summary_pipeline.X")``.
    Object attributes such as ``summary_pipeline.settings.X`` are patched on the shared object and
    are not seams here."""
    names: set[str] = set()
    for root in PATCHING_ROOTS:
        for py in root.rglob("*.py"):
            if py == Path(__file__):
                continue
            text = py.read_text(encoding="utf-8")
            names.update(_STRING_TARGET.findall(text))
            aliases = {"pipeline", "summary_pipeline"}
            for pattern in _MODULE_ALIASES:
                aliases.update(a for a in pattern.findall(text) if a)
            module_then_name = re.compile(
                r"[A-Za-z_][A-Za-z0-9_.]*\(\s*(?:" + "|".join(sorted(map(re.escape, aliases)))
                + r")\s*,\s*[\"']([A-Za-z_][A-Za-z0-9_]*)[\"']"
            )
            names.update(module_then_name.findall(text))
    return names


def _module_tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _imported_names(tree: ast.Module) -> dict[str, str]:
    """name bound at module level -> the module it came from."""
    bound: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                bound[alias.asname or alias.name.split(".")[0]] = alias.name
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                bound[alias.asname or alias.name] = f"{node.module}.{alias.name}"
        elif isinstance(node, ast.If):  # ``if TYPE_CHECKING:`` blocks bind nothing at runtime
            continue
    return bound


def _pipeline_attribute_uses(tree: ast.Module) -> set[str]:
    return {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "pipeline"
    }


def _annotation_node_ids(tree: ast.Module) -> set[int]:
    """Names inside annotations are types, not runtime lookups (``from __future__ import annotations``)."""
    ids: set[int] = set()
    for node in ast.walk(tree):
        annotations = []
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            annotations = [a.annotation for a in node.args.args + node.args.kwonlyargs + node.args.posonlyargs if a.annotation]
            annotations += [node.returns] if node.returns else []
            for arg in (node.args.vararg, node.args.kwarg):
                if arg is not None and arg.annotation is not None:
                    annotations.append(arg.annotation)
        elif isinstance(node, ast.AnnAssign):
            annotations = [node.annotation]
        for annotation in annotations:
            ids.update(id(sub) for sub in ast.walk(annotation))
    return ids


def _bare_name_uses(tree: ast.Module) -> set[str]:
    skip = _annotation_node_ids(tree)
    return {node.id for node in ast.walk(tree) if isinstance(node, ast.Name) and id(node) not in skip}


def test_the_seams_tests_patch_are_never_imported_or_used_bare_in_a_stage():
    seams = patched_pipeline_names()
    assert {"record_progress", "run_in_threadpool", "check_usage_limit", "_release_inflight"} <= seams, (
        "the seam scan lost known patch sites; fix the scan before trusting this gate"
    )
    offenders: list[str] = []
    for path in STAGE_MODULES:
        tree = _module_tree(path)
        bound = _imported_names(tree)
        bare = _bare_name_uses(tree)
        for name in sorted(seams - BARE_ALLOWED):
            if name in bound:
                offenders.append(f"{path.name} imports {name!r} ({bound[name]}); use pipeline.{name}")
            elif name in bare:
                offenders.append(f"{path.name} uses {name!r} bare; use pipeline.{name}")
    assert not offenders, "\n".join(offenders)


def test_stages_import_only_the_sanctioned_app_modules():
    offenders: list[str] = []
    for path in STAGE_MODULES:
        for node in _module_tree(path).body:
            modules: list[str] = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                # ``from app.services import summary_pipeline`` binds the module app.services.summary_pipeline
                modules = [f"{node.module}.{alias.name}" if node.module in {"app", "app.services"} else (node.module or "")
                           for alias in node.names]
            for module in modules:
                if module.startswith("app") and not module.startswith(ALLOWED_APP_IMPORTS):
                    offenders.append(f"{path.name}: {ast.unparse(node)}")
    assert not offenders, (
        "stage modules reach app collaborators as pipeline.<name> (the patch seams); found:\n  "
        + "\n  ".join(offenders)
    )


def test_every_pipeline_attribute_a_stage_uses_exists_on_the_module():
    missing: list[str] = []
    for path in STAGE_MODULES:
        for attr in sorted(_pipeline_attribute_uses(_module_tree(path))):
            if not hasattr(summary_pipeline, attr):
                missing.append(f"{path.name}: pipeline.{attr}")
    assert not missing, (
        "a stage references a name summary_pipeline no longer exposes (an import was removed?):\n  "
        + "\n  ".join(missing)
    )


def test_pipeline_binds_stage_modules_only_as_modules():
    """A ``from app.services.summary_stages.<m> import <Name>`` in the pipeline (or any import in the
    package ``__init__``) breaks the stage-first import order with an ImportError on a partially
    initialized module."""
    tree = _module_tree(BACKEND / "app" / "services" / "summary_pipeline.py")
    offenders = [
        ast.unparse(node) for node in tree.body
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("app.services.summary_stages.")
    ]
    assert not offenders, offenders
    init_tree = _module_tree(STAGES_DIR / "__init__.py")
    assert not [n for n in init_tree.body if isinstance(n, (ast.Import, ast.ImportFrom))], "keep __init__ import-free"


_BROAD = {"BaseException", "GeneratorExit", "CancelledError"}


def _has_yield(node: ast.AST) -> bool:
    """A yield in this subtree, not counting nested function bodies (their yields are their own)."""
    stack = [node]
    while stack:
        current = stack.pop()
        if isinstance(current, (ast.Yield, ast.YieldFrom)):
            return True
        for child in ast.iter_child_nodes(current):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                continue
            stack.append(child)
    return False


def _broad_handler(handler: ast.ExceptHandler) -> bool:
    if handler.type is None:
        return True
    names = [n for n in ast.walk(handler.type) if isinstance(n, (ast.Name, ast.Attribute))]
    return any((getattr(n, "id", None) or getattr(n, "attr", None)) in _BROAD for n in names)


def test_nothing_in_a_stage_runs_cleanup_across_a_yield():
    """The orchestrator closes a stage with ``aclose()`` from inside its own cleanup. That stays a
    synchronous unwind only while no ``with``/``async with`` body, no ``try … finally`` and no
    broad ``except`` (bare, BaseException, GeneratorExit, CancelledError) spans a ``yield``: an
    awaiting ``finally`` there would become an unshielded suspension under a disconnect and could
    turn the pipeline deadline's TimeoutError into an escaped CancelledError."""
    offenders: list[str] = []
    for path in STAGE_MODULES:
        for func in _module_tree(path).body:
            if not isinstance(func, ast.AsyncFunctionDef):
                continue
            for node in ast.walk(func):
                if isinstance(node, (ast.With, ast.AsyncWith)) and any(_has_yield(s) for s in node.body):
                    offenders.append(f"{path.name}::{func.name}:{node.lineno} with-block spans a yield")
                if isinstance(node, ast.Try) and (node.finalbody or any(_broad_handler(h) for h in node.handlers)):
                    if _has_yield(node):
                        offenders.append(f"{path.name}::{func.name}:{node.lineno} try/finally or broad except spans a yield")
    assert not offenders, "\n".join(offenders)


def test_no_stage_calls_asyncio_timeout():
    offenders = [
        f"{path.name}:{node.lineno}"
        for path in STAGE_MODULES
        for node in ast.walk(_module_tree(path))
        if isinstance(node, ast.Attribute) and node.attr == "timeout"
        and isinstance(node.value, ast.Name) and node.value.id == "asyncio"
    ]
    assert not offenders, f"asyncio.timeout belongs to the orchestrator (its asyncio is proxied by tests): {offenders}"


@pytest.mark.parametrize("module", [p.stem for p in STAGE_MODULES])
def test_each_stage_module_imports_cleanly_when_imported_first(module):
    """The circular import with the pipeline module must work in either order."""
    proc = subprocess.run(
        [sys.executable, "-c", f"import app.services.summary_stages.{module}; import app.services.summary_pipeline"],
        cwd=BACKEND, capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]


def _terminal_yield(stmt: ast.stmt) -> bool:
    if not (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Yield) and isinstance(stmt.value.value, ast.Dict)):
        return False
    for key, value in zip(stmt.value.value.keys, stmt.value.value.values):
        if isinstance(key, ast.Constant) and key.value == "type" and isinstance(value, ast.Constant):
            return value.value in summary_pipeline.TERMINAL_EVENT_TYPES
    return False


def _violations(stmts: list[ast.stmt], tail: bool, where: str) -> list[str]:
    """A terminal yield must be followed by ``return``, or sit in tail position."""
    out: list[str] = []
    for i, stmt in enumerate(stmts):
        last = i == len(stmts) - 1
        if _terminal_yield(stmt):
            followed_by_return = not last and isinstance(stmts[i + 1], ast.Return)
            if not (followed_by_return or (last and tail)):
                out.append(f"{where}:{stmt.lineno}")
            continue
        child_tail = tail and last
        for field in ("body", "orelse", "finalbody"):
            block = getattr(stmt, field, None)
            if isinstance(block, list) and block and isinstance(block[0], ast.stmt):
                # a loop body is never tail position: the loop may iterate again
                out.extend(_violations(block, child_tail and not isinstance(stmt, (ast.For, ast.AsyncFor, ast.While)), where))
        for handler in getattr(stmt, "handlers", []) or []:
            out.extend(_violations(handler.body, child_tail, where))
    return out


def test_every_terminal_yield_in_a_stage_ends_the_stage():
    offenders: list[str] = []
    for path in STAGE_MODULES:
        for node in _module_tree(path).body:
            if isinstance(node, ast.AsyncFunctionDef):
                offenders.extend(_violations(node.body, tail=True, where=f"{path.name}::{node.name}"))
    assert not offenders, (
        "a terminal event (complete/partial/error) must be the last thing a stage does — the "
        "orchestrator returns after forwarding it:\n  " + "\n  ".join(offenders)
    )


def _bare_returns(stmts: list[ast.stmt], where: str) -> list[str]:
    """A ``return`` in a stage's own scope that does not directly follow a terminal yield."""
    out: list[str] = []
    for i, stmt in enumerate(stmts):
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue  # a nested helper's return returns from the helper
        if isinstance(stmt, ast.Return) and not (i and _terminal_yield(stmts[i - 1])):
            out.append(f"{where}:{stmt.lineno}")
        for field in ("body", "orelse", "finalbody"):
            block = getattr(stmt, field, None)
            if isinstance(block, list) and block and isinstance(block[0], ast.stmt):
                out.extend(_bare_returns(block, where))
        for handler in getattr(stmt, "handlers", []) or []:
            out.extend(_bare_returns(handler.body, where))
        for case in getattr(stmt, "cases", []) or []:
            out.extend(_bare_returns(case.body, where))
    return out


def test_a_stage_returns_only_right_after_a_terminal_yield():
    """In the inline body a bare ``return`` ended the whole pipeline; in a stage it ends only that
    stage and the orchestrator runs the next one. So a stage may return only to stop after the
    terminal event it just yielded (the converse of the gate above)."""
    stages = {(stage.__module__.rsplit(".", 1)[-1], stage.__name__) for stage in summary_pipeline._stage_sequence()}
    offenders: list[str] = []
    for path in STAGE_MODULES:
        for node in _module_tree(path).body:
            if isinstance(node, ast.AsyncFunctionDef) and (path.stem, node.name) in stages:
                offenders.extend(_bare_returns(node.body, where=f"{path.name}::{node.name}"))
    assert len(stages) == 7, f"expected the seven stages of _stage_sequence(), got {sorted(stages)}"
    assert not offenders, (
        "a stage ends early only by yielding its terminal event and returning; a bare return would "
        "let the orchestrator run the next stage:\n  " + "\n  ".join(offenders)
    )


def _own_scope(func: ast.AST) -> list[ast.AST]:
    """Nodes in ``func``'s own scope (nested defs, lambdas and classes are their own scope)."""
    out: list[ast.AST] = []
    stack = list(func.body)
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            continue  # a nested scope: its locals are its own
        out.append(node)
        stack.extend(ast.iter_child_nodes(node))
    return out


def _store_names(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
        return [node.id]
    if isinstance(node, (ast.Tuple, ast.List)):
        return [n for elt in node.elts for n in _store_names(elt)]
    if isinstance(node, ast.Starred):
        return _store_names(node.value)
    return []


def _run_fields() -> tuple[set[str], set[str]]:
    """(all GenerationRun field names, the constructor-parameter subset).

    The parameters are the orchestrator's own arguments (``filing_id``, ``current_user``, …), which
    nothing rebinds. Every other field is pipeline state that stages and methods write, so a bare
    alias of one (``summary_payload = run.summary_payload``) would be a snapshot that goes stale."""
    tree = _module_tree(STAGES_DIR / "generation_run.py")
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "GenerationRun")
    fields = {n.target.id for n in cls.body if isinstance(n, ast.AnnAssign)}
    params = fields & set(inspect.signature(summary_pipeline.stream_filing_summary).parameters)
    return fields, params


def test_no_stage_binds_a_run_field_as_a_bare_local():
    """``summary_task = create_task(...)`` instead of ``run.summary_task = …`` would hide the task
    from ``release()``; the same for every field the metering helpers or a later stage reads.
    Only an exact alias of an immutable constructor parameter (``filing_id = run.filing_id``) may
    reuse a field name; the parameters are ``stream_filing_summary``'s own arguments."""
    fields, params = _run_fields()
    offenders: list[str] = []
    for path in STAGE_MODULES:
        funcs: list[ast.AST] = []
        for node in _module_tree(path).body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                funcs.append(node)
            elif isinstance(node, ast.ClassDef):
                funcs.extend(n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)))
        for func in funcs:
            for node in _own_scope(func):
                targets: list[ast.AST] = []
                if isinstance(node, ast.Assign):
                    targets = node.targets
                elif isinstance(node, (ast.AnnAssign, ast.AugAssign, ast.For, ast.AsyncFor, ast.NamedExpr)):
                    targets = [node.target]
                elif isinstance(node, (ast.With, ast.AsyncWith)):
                    targets = [i.optional_vars for i in node.items if i.optional_vars is not None]
                bound = [n for t in targets for n in _store_names(t)]
                clashes = [n for n in bound if n in fields]
                if not clashes:
                    continue
                if isinstance(node, ast.Assign) and len(node.targets) == 1:
                    sources = node.value.elts if isinstance(node.value, ast.Tuple) else [node.value]
                    if len(sources) == len(bound) and all(n in params for n in bound) and all(
                        isinstance(s, ast.Attribute) and isinstance(s.value, ast.Name)
                        and s.value.id in {"run", "self"} and s.attr == n
                        for s, n in zip(sources, bound)
                    ):
                        continue
                offenders.append(f"{path.name}::{func.name}:{node.lineno} binds {clashes} bare; write run.<field>")
    assert not offenders, "\n".join(offenders)


def test_no_stage_snapshots_a_pipeline_attribute():
    """``X = pipeline.X`` (at module level or inside a function) binds the collaborator once and
    defeats a later ``monkeypatch.setattr(summary_pipeline, "X", …)``; look it up at the call.
    Writing a pipeline constant INTO an attribute (``row.schema_version = pipeline.SUMMARY_SCHEMA_VERSION``)
    is a call-time read and stays allowed."""
    offenders = [
        f"{path.name}:{node.lineno} {ast.unparse(node)}"
        for path in STAGE_MODULES
        for node in ast.walk(_module_tree(path))
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and isinstance(node.value, ast.Attribute)
        and isinstance(node.value.value, ast.Name) and node.value.value.id == "pipeline"
        and any(isinstance(t, ast.Name) for t in (node.targets if isinstance(node, ast.Assign) else [node.target]))
    ]
    assert not offenders, "\n".join(offenders)


def test_every_stage_yield_is_a_dict_literal_with_a_constant_type():
    """The terminal-event gate reads the ``type`` key off the yielded literal; a ``yield event`` of a
    variable could carry a terminal type past it."""
    offenders: list[str] = []
    for path in STAGE_MODULES:
        for func in _module_tree(path).body:
            if not isinstance(func, ast.AsyncFunctionDef):
                continue
            for node in _own_scope(func):
                if isinstance(node, ast.Yield):
                    value = node.value
                    ok = isinstance(value, ast.Dict) and any(
                        isinstance(k, ast.Constant) and k.value == "type" and isinstance(v, ast.Constant)
                        for k, v in zip(value.keys, value.values)
                    )
                    if not ok:
                        offenders.append(f"{path.name}::{func.name}:{node.lineno}")
    assert not offenders, "\n".join(offenders)


def test_stage_sequence_is_async_generators_and_handlers_are_coroutines():
    for stage in summary_pipeline._stage_sequence():
        assert inspect.isasyncgenfunction(stage), stage
    from app.services.summary_stages import failure

    assert inspect.iscoroutinefunction(failure.timed_out)
    assert inspect.iscoroutinefunction(failure.failed)


def test_stage_loggers_are_the_pipeline_logger():
    import importlib

    for path in STAGE_MODULES:
        module = importlib.import_module(f"{summary_stages.__name__}.{path.stem}")
        assert module.logger is summary_pipeline.logger, path.name


def test_orchestrator_stays_a_short_stage_map():
    source, _ = inspect.getsourcelines(summary_pipeline.stream_filing_summary)
    assert len(source) <= 150, (
        f"stream_filing_summary is {len(source)} lines; it is the stage map, not a stage — move "
        "logic into app/services/summary_stages"
    )
