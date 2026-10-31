"""Mechanical "pure move" proof for the ``stream_filing_summary`` stage decomposition.

Per ``lessons/test-pure-move-ast-proof.md``: a relocation claim is proven by an AST-normalized diff,
not by reading the diff. Three checks, all against the pre-split module (``--base``, a git revision
whose ``backend/app/services/summary_pipeline.py`` still holds the inline generator):

1. **Top-level parity.** Every top-level symbol of ``summary_pipeline.py`` other than
   ``stream_filing_summary`` (constants, dataclasses, ``_finalize_summary_projection``, the in-flight
   helpers, ``to_sse`` …) is AST-identical (``ast.unparse``) before and after. Added/removed names
   and import changes are listed.

2. **Binding check.** No stage function or ``GenerationRun`` method binds a ``GenerationRun`` field
   name as a bare local (``summary_task = create_task(...)`` instead of ``run.summary_task = …``):
   such a binding would be invisible to ``release()``, the metering helpers and later stages, and
   the prefix-stripping diff below could not tell the two apart. Only exact aliases of immutable
   constructor parameters (``filing_id = run.filing_id``) are allowed.

3. **Normalized body diff.** The old generator body is compared with the new code *re-inlined* in
   pipeline order: the ``GenerationRun`` fields and methods, then each stage function of
   ``_stage_sequence()`` spliced in place of the orchestrator's stage loop, ``start_enrichment_tasks``
   spliced at its call site, the two failure handlers spliced into their ``except`` blocks with their
   ``return`` turned back into ``yield``, and ``release()`` spliced into ``finally``. The new side is
   normalized by the DECLARED renames only — ``run.<x>``/``self.<x>``/``pipeline.<x>`` → ``<x>``,
   the ``self`` parameter dropped, ``nonlocal`` dropped, and pure alias statements such as
   ``filing_id = run.filing_id`` (which become ``x = x``) dropped. On the old side the three metering
   closures (``begin_charge``, ``charge_lease``, ``on_provider_start``) are hoisted next to the other
   closures, where they now live as methods. Everything that survives this normalization is printed
   as a unified diff: those hunks are the complete list of structural edits a reviewer has to read.
   Docstrings, annotations and ``nonlocal`` are dropped on BOTH sides (none of them is behavior).

Run from the repo root::

    python backend/scripts/prove_summary_pipeline_move.py --base <sha-before-the-split>

Exit status is 0 when parity and the binding check hold; the residual hunk count is printed for the
PR body. Reviewer-run (it needs the pre-split revision), not a CI gate; the CI gates are in
``tests/unit/test_summary_stages_seams.py``.
"""
from __future__ import annotations

import argparse
import ast
import copy
import difflib
import subprocess
import sys
from pathlib import Path

PIPELINE_REL = "backend/app/services/summary_pipeline.py"
STAGES_REL = "backend/app/services/summary_stages"
GENERATOR = "stream_filing_summary"
RUN_CLASS = "GenerationRun"
# Closures that became methods: hoisted on the old side so the diff compares them in one place.
HOISTED_CLOSURES = ("begin_charge", "charge_lease", "on_provider_start")
NAMESPACES = ("run", "self", "pipeline")


def git_show(rev: str, rel: str, root: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(root), "show", f"{rev}:{rel}"], check=True, capture_output=True, text=True,
    ).stdout


def top_level(tree: ast.Module) -> dict[str, ast.AST]:
    out: dict[str, ast.AST] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out[node.name] = node
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    out[target.id] = node
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            out[node.target.id] = node
    return out


def imports(tree: ast.Module) -> set[str]:
    out: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            out.add(ast.unparse(node))
    return out


class Normalize(ast.NodeTransformer):
    """Apply the declared renames; drop ``nonlocal`` and pure alias statements."""

    def visit_Attribute(self, node: ast.Attribute):
        self.generic_visit(node)
        if isinstance(node.value, ast.Name) and node.value.id in NAMESPACES:
            return ast.copy_location(ast.Name(id=node.attr, ctx=node.ctx), node)
        return node

    def visit_Nonlocal(self, node: ast.Nonlocal):
        return None

    def visit_Expr(self, node: ast.Expr):
        self.generic_visit(node)
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            return None  # docstrings and bare string statements are not behavior
        return node

    def visit_AnnAssign(self, node: ast.AnnAssign):
        self.generic_visit(node)
        if node.value is None:
            return None  # a bare annotation declares nothing at runtime
        return ast.copy_location(ast.Assign(targets=[node.target], value=node.value), node)

    def visit_Assign(self, node: ast.Assign):
        self.generic_visit(node)
        if len(node.targets) == 1 and ast.unparse(node.targets[0]) == ast.unparse(node.value):
            return None  # ``x = x`` / ``a, b = a, b``: an alias of a run attribute, not behavior
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef):
        return self._strip_self(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        return self._strip_self(node)

    def _strip_self(self, node):
        if node.args.args and node.args.args[0].arg == "self":
            node.args.args = node.args.args[1:]
        self.generic_visit(node)
        return node


def normalized(node: ast.AST) -> ast.AST:
    return ast.fix_missing_locations(Normalize().visit(copy.deepcopy(node)))


def find_def(tree: ast.Module, name: str):
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == name:
            return node
    raise SystemExit(f"missing definition {name!r}")


def body_text(stmts: list[ast.stmt]) -> str:
    module = ast.Module(body=stmts, type_ignores=[])
    return ast.unparse(ast.fix_missing_locations(module))


# --- old side -------------------------------------------------------------------------------

def hoist_closures(func: ast.AsyncFunctionDef) -> ast.AsyncFunctionDef:
    """Move the metering closures next to the prelude closures (they are methods on the new side)."""
    func = copy.deepcopy(func)
    hoisted: list[ast.stmt] = []

    def strip(stmts: list[ast.stmt]) -> list[ast.stmt]:
        kept: list[ast.stmt] = []
        for stmt in stmts:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) and stmt.name in HOISTED_CLOSURES:
                hoisted.append(stmt)
                continue
            for field_name in ("body", "orelse", "finalbody", "handlers"):
                children = getattr(stmt, field_name, None)
                if isinstance(children, list) and children and isinstance(children[0], ast.stmt):
                    setattr(stmt, field_name, strip(children))
                elif isinstance(children, list) and children and isinstance(children[0], ast.ExceptHandler):
                    for handler in children:
                        handler.body = strip(handler.body)
            kept.append(stmt)
        return kept

    func.body = strip(func.body)
    # Insert after the last prelude closure (record_progress_sync) and before the ``try``.
    anchor = next(i for i, s in enumerate(func.body) if isinstance(s, ast.Try))
    func.body[anchor:anchor] = hoisted
    return func


# --- new side -------------------------------------------------------------------------------

def run_class_statements(run_cls: ast.ClassDef, params: set[str]) -> tuple[list[ast.stmt], dict[str, ast.AST]]:
    """Dataclass fields with defaults (as statements), ``__post_init__`` body, and the methods by name.

    Fields that are the orchestrator's own parameters are constructor arguments, not state the
    generator initialized, so they are not emitted.
    """
    fields: list[ast.stmt] = []
    methods: dict[str, ast.AST] = {}
    post_init: list[ast.stmt] = []
    for node in run_cls.body:
        if isinstance(node, ast.AnnAssign) and node.value is not None and node.target.id not in params:
            value = node.value
            if isinstance(value, ast.Call) and getattr(value.func, "id", None) == "field":
                factory = next((kw.value for kw in value.keywords if kw.arg == "default_factory"), None)
                if factory is None:
                    continue  # ``field(init=False)`` without a default: assigned in __post_init__
                value = ast.List(elts=[], ctx=ast.Load()) if getattr(factory, "id", None) == "list" else ast.Call(func=factory, args=[], keywords=[])
            fields.append(ast.AnnAssign(target=node.target, annotation=node.annotation, value=value, simple=1))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == "__post_init__":
                post_init = normalized(node).body
            else:
                methods[node.name] = normalized(node)
    return post_init + fields, methods


def stage_sequence(pipeline_tree: ast.Module) -> list[tuple[str, str]]:
    seq = find_def(pipeline_tree, "_stage_sequence")
    ret = next(s for s in seq.body if isinstance(s, ast.Return))
    out = []
    for elt in ret.value.elts:
        assert isinstance(elt, ast.Attribute) and isinstance(elt.value, ast.Name)
        out.append((elt.value.id, elt.attr))
    return out


def inline_calls(stmts: list[ast.stmt], module_funcs: dict[tuple[str, str], ast.AST]) -> list[ast.stmt]:
    """Splice ``<module>.<func>(run)`` expression statements with that function's normalized body."""
    out: list[ast.stmt] = []
    for stmt in stmts:
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            call = stmt.value
            if isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name):
                key = (call.func.value.id, call.func.attr)
                if key in module_funcs:
                    out.extend(normalized(module_funcs[key]).body)
                    continue
        out.append(stmt)
    return out


def returns_to_yields(stmts: list[ast.stmt]) -> list[ast.stmt]:
    out = []
    for stmt in stmts:
        if isinstance(stmt, ast.Return) and stmt.value is not None:
            out.append(ast.Expr(value=ast.Yield(value=stmt.value)))
        else:
            out.append(stmt)
    return out


def rebuild_new_generator(pipeline_tree: ast.Module, stage_trees: dict[str, ast.Module]) -> ast.AsyncFunctionDef:
    orchestrator = copy.deepcopy(find_def(pipeline_tree, GENERATOR))
    run_cls = find_def(stage_trees["generation_run"], RUN_CLASS)
    params = {a.arg for a in orchestrator.args.kwonlyargs + orchestrator.args.args}
    prelude, methods = run_class_statements(run_cls, params)
    stage_funcs = {
        (mod, name): find_def(tree, name)
        for mod, tree in stage_trees.items()
        for name in [n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    }

    body: list[ast.stmt] = []
    for stmt in orchestrator.body:
        # ``run = generation_run.GenerationRun(...)`` → the fields/__post_init__ and the methods.
        if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Call) and ast.unparse(stmt.value.func).endswith(RUN_CLASS):
            body.extend(prelude)
            body.extend(methods[name] for name in methods if name != "release")
            continue
        if isinstance(stmt, ast.Try):
            stmt = copy.deepcopy(stmt)
            # The stage loop → the stage bodies in _stage_sequence order.
            async_with = stmt.body[0]
            new_with_body: list[ast.stmt] = []
            for inner in async_with.body:
                if isinstance(inner, ast.For):
                    for mod, name in stage_sequence(pipeline_tree):
                        stage_body = normalized(stage_funcs[(mod, name)]).body
                        new_with_body.extend(inline_calls(stage_body, stage_funcs))
                else:
                    new_with_body.append(inner)
            async_with.body = new_with_body
            # ``yield await failure.<handler>(run, …)`` → the handler body with return → yield.
            for handler in stmt.handlers:
                new_handler_body: list[ast.stmt] = []
                for inner in handler.body:
                    if (isinstance(inner, ast.Expr) and isinstance(inner.value, ast.Yield)
                            and isinstance(inner.value.value, ast.Await)):
                        call = inner.value.value.value
                        key = (call.func.value.id, call.func.attr)
                        new_handler_body.extend(returns_to_yields(normalized(stage_funcs[key]).body))
                    else:
                        new_handler_body.append(inner)
                handler.body = new_handler_body
            # ``await run.release()`` → the release body.
            new_final: list[ast.stmt] = []
            for inner in stmt.finalbody:
                if isinstance(inner, ast.Expr) and isinstance(inner.value, ast.Await) and ast.unparse(inner.value.value).endswith("release()"):
                    new_final.extend(methods["release"].body)
                else:
                    new_final.append(inner)
            stmt.finalbody = new_final
        body.append(stmt)
    orchestrator.body = body
    return normalized(orchestrator)


# --- binding check ----------------------------------------------------------------------------

def _own_scope_statements(func) -> list[ast.AST]:
    """Every node in ``func``'s own scope: nested defs/lambdas/classes are their own scope."""
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


def binding_violations(pipeline_tree: ast.Module, stage_trees: dict[str, ast.Module]) -> list[str]:
    """A GenerationRun field bound as a bare local in a stage (or method) would be invisible to
    ``release()``, the metering helpers and later stages — the one bug class the prefix-stripping
    diff cannot see. Allowed: an exact alias of an immutable constructor parameter
    (``filing_id = run.filing_id``). The parameters are the orchestrator's own arguments, never
    the run's mutable state: a ``summary_payload = run.summary_payload`` snapshot would normalize
    to the old local and pass the diff, then go stale when a later statement rebinds the field."""
    run_cls = find_def(stage_trees["generation_run"], RUN_CLASS)
    fields = {n.target.id for n in run_cls.body if isinstance(n, ast.AnnAssign)}
    orchestrator = find_def(pipeline_tree, GENERATOR)
    params = fields & {a.arg for a in orchestrator.args.kwonlyargs + orchestrator.args.args}
    out: list[str] = []
    for mod, tree in stage_trees.items():
        funcs: list = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                funcs.append(node)
            elif isinstance(node, ast.ClassDef):
                funcs.extend(n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)))
        for func in funcs:
            for node in _own_scope_statements(func):
                targets: list[ast.AST] = []
                if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                elif isinstance(node, (ast.For, ast.AsyncFor)):
                    targets = [node.target]
                elif isinstance(node, (ast.With, ast.AsyncWith)):
                    targets = [item.optional_vars for item in node.items if item.optional_vars is not None]
                elif isinstance(node, ast.NamedExpr):
                    targets = [node.target]
                bound = [n for t in targets for n in _store_names(t)]
                clashes = [n for n in bound if n in fields]
                if not clashes:
                    continue
                # an exact alias of constructor parameters: ``a, b = run.a, run.b`` / ``a = self.a``
                if isinstance(node, ast.Assign) and len(node.targets) == 1:
                    sources = node.value.elts if isinstance(node.value, ast.Tuple) else [node.value]
                    if (len(sources) == len(bound) and all(n in params for n in bound) and all(
                        isinstance(s, ast.Attribute) and isinstance(s.value, ast.Name)
                        and s.value.id in ("run", "self") and s.attr == n
                        for s, n in zip(sources, bound)
                    )):
                        continue
                out.append(f"{mod}.py::{func.name}:{node.lineno} binds run field(s) {clashes} bare")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", default="origin/main", help="git revision holding the pre-split module")
    parser.add_argument("--root", default=None, help="repo root (default: the parent of this script's backend/)")
    parser.add_argument("--pipeline", default=None, help="override path of the NEW summary_pipeline.py")
    parser.add_argument("--stages", default=None, help="override directory of the NEW summary_stages package")
    parser.add_argument("--context", type=int, default=2, help="unified-diff context lines")
    args = parser.parse_args()

    root = Path(args.root) if args.root else Path(__file__).resolve().parents[2]
    pipeline_path = Path(args.pipeline) if args.pipeline else root / PIPELINE_REL
    stages_dir = Path(args.stages) if args.stages else root / STAGES_REL

    base_src = git_show(args.base, PIPELINE_REL, root)
    base_tree = ast.parse(base_src)
    new_tree = ast.parse(pipeline_path.read_text())
    stage_trees = {p.stem: ast.parse(p.read_text()) for p in sorted(stages_dir.glob("*.py")) if p.stem != "__init__"}

    # 1. top-level parity
    ok = True
    old_top, new_top = top_level(base_tree), top_level(new_tree)
    print("== 1. top-level symbol parity (summary_pipeline.py, everything but the generator) ==")
    for name, node in old_top.items():
        if name == GENERATOR:
            continue
        if name not in new_top:
            ok = False
            print(f"MISSING  {name}")
        elif ast.unparse(node) != ast.unparse(new_top[name]):
            ok = False
            print(f"CHANGED  {name}")
    for name in new_top:
        if name not in old_top:
            print(f"added    {name}")
    for line in sorted(imports(new_tree) - imports(base_tree)):
        print(f"import + {line}")
    for line in sorted(imports(base_tree) - imports(new_tree)):
        print(f"import - {line}")
    print("parity:", "OK" if ok else "FAILED")

    # 2. binding check (run before the prefix strip, which cannot see this bug class)
    print("\n== 2. binding check: no GenerationRun field bound as a bare local in a stage ==")
    violations = binding_violations(new_tree, stage_trees)
    for line in violations:
        print("BOUND    " + line)
    print("bindings:", "OK" if not violations else "FAILED")
    ok = ok and not violations

    # 3. normalized body diff
    print("\n== 3. normalized body diff: old inline generator vs new stages re-inlined ==")
    old_text = body_text([normalized(hoist_closures(find_def(base_tree, GENERATOR)))]).splitlines()
    new_text = body_text([rebuild_new_generator(new_tree, stage_trees)]).splitlines()
    diff = list(difflib.unified_diff(old_text, new_text, fromfile=f"{args.base}:{PIPELINE_REL}::{GENERATOR}",
                                     tofile="stages re-inlined", n=args.context, lineterm=""))
    hunks = sum(1 for line in diff if line.startswith("@@"))
    print("\n".join(diff))
    print(f"\nresidual hunks: {hunks}  (old {len(old_text)} lines, new {len(new_text)} lines)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
