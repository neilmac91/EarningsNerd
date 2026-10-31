"""Reassemble T4's three phase splits against their committed pre-split modules.

Only validated same-name helper arguments/returns, plain per-call narrative state,
and closing-protected synchronous event delegation are erased. Provider iteration
and await boundaries remain in the original async generator. Run with --base REF;
--worktree exists solely for pre-commit diagnostics and mutation proofs.
"""
from __future__ import annotations

import argparse
import ast
import copy
import difflib
import subprocess
import symtable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MODULES = {
    "dataset": "build_dataset",
    "observations": "build_observation_catalogue",
    "narrative": "stream_trend_narrative",
}
STATE = '''
class _NarrativeRun:
    company_id: int
    mode: str
    start_period: str
    end_period: str
    force: bool
    user_id: Optional[int]
    ticker: Any
    dataset: Any
    fingerprint: Any
    key: Any
    invalidated: Any
    catalogue: Any
    base_messages: Any
    index: Any
    model_name: Any
    total_usage: Any
    selection: Any
    assembled: bool

    def __init__(
        self, company_id: int, mode: str, start_period: str, end_period: str,
        force: bool, user_id: Optional[int],
    ) -> None:
        self.company_id = company_id
        self.mode = mode
        self.start_period = start_period
        self.end_period = end_period
        self.force = force
        self.user_id = user_id
        self.assembled = False
'''
CONSTRUCTOR = 'run = _NarrativeRun(company_id, mode, start_period, end_period, force, user_id)'
ASSEMBLED = 'run.assembled = True'
STOP = 'if not run.assembled:\n    return'
BRIDGE = '''with closing(HELPER) as events:
    for event in events:
        yield event
'''
EXTRA_IMPORTS = {
    "dataset": set(),
    "observations": {("typing", "Callable")},
    "narrative": {("contextlib", "closing")},
}


def dump(node):
    return ast.dump(node, include_attributes=False)


def statement(source):
    return ast.parse(source).body[0]


def no_doc(body):
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        if isinstance(body[0].value.value, str):
            return body[1:]
    return body


def scoped_nodes(body):
    """Walk one execution scope, excluding nested function/class bodies."""
    for node in body:
        yield node
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            yield from scoped_nodes(ast.iter_child_nodes(node))


def global_reads(table):
    result = {s.get_name() for s in table.get_symbols() if s.is_global() and s.is_referenced()}
    for child in table.get_children():
        result.update(global_reads(child))
    return result


class StateNames(ast.NodeTransformer):
    def visit_Attribute(self, node):
        if isinstance(node.value, ast.Name) and node.value.id == "run":
            assert node.attr in self.fields, f"unexpected state member {node.attr}"
            return ast.copy_location(ast.Name(id=node.attr, ctx=node.ctx), node)
        return self.generic_visit(node)

    def visit_AnnAssign(self, node):
        is_state = isinstance(node.target, ast.Attribute) and ast.unparse(node.target).startswith("run.")
        self.generic_visit(node)
        if is_state:
            node.simple = 1
        return node

    def __init__(self):
        self.fields = {n.target.id for n in ast.parse(STATE).body[0].body if isinstance(n, ast.AnnAssign)}


class Expand(ast.NodeTransformer):
    def __init__(self, helpers, narrative):
        self.helpers, self.narrative = helpers, narrative
        self.used = []
        self.constructors = self.bridges = self.stops = 0

    def body(self, call):
        assert isinstance(call.func, ast.Name) and call.func.id in self.helpers
        helper = self.helpers[call.func.id]
        args = helper.args
        assert isinstance(helper, ast.FunctionDef) and not helper.decorator_list, "helper execution boundary"
        assert not (args.defaults or args.kw_defaults or args.kwonlyargs or args.posonlyargs
                    or args.vararg or args.kwarg or call.keywords), "helper parameter scaffold"
        assert [ast.unparse(a) for a in call.args] == [a.arg for a in args.args], "changed helper argument"
        assert helper.name not in self.used, "repeated helper call"
        self.used.append(helper.name)
        body = copy.deepcopy(no_doc(helper.body))
        if helper.name == "_assemble":
            assert dump(body[-1]) == dump(statement(ASSEMBLED)), "assembly completion flag"
            body.pop()
        return body

    def helper_call(self, node):
        return (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id in self.helpers)

    def visit_Assign(self, node):
        if self.narrative and isinstance(node.value, ast.Call) and ast.unparse(node.value.func) == "_NarrativeRun":
            assert dump(node) == dump(statement(CONSTRUCTOR)), "state constructor changed"
            self.constructors += 1
            return None
        if self.helper_call(node.value):
            body = self.body(node.value)
            assert len(node.targets) == 1 and isinstance(body[-1], ast.Return), "missing helper result"
            assert ast.unparse(node.targets[0]) == ast.unparse(body[-1].value), "changed helper result"
            body.pop()
            # Nested function returns retain their original scope.
            assert not any(isinstance(n, (ast.Return, ast.Yield, ast.YieldFrom))
                           for n in scoped_nodes(body)), "early helper result or generator"
            return self.expand_body(body)
        return self.generic_visit(node)

    def expand_body(self, body):
        wrapper = ast.Module(body=body, type_ignores=[])
        return self.visit(wrapper).body

    def visit_Expr(self, node):
        if self.helper_call(node.value):
            body = self.body(node.value)
            assert not any(isinstance(n, (ast.Return, ast.Yield, ast.YieldFrom))
                           for n in scoped_nodes(body)), "void helper changes control flow"
            return self.expand_body(body)
        return self.generic_visit(node)

    def visit_Yield(self, node):
        if self.helper_call(node.value):
            body = self.body(node.value)
            assert len(body) == 1 and isinstance(body[0], ast.Return), "event helper must return one literal"
            node.value = body[0].value
        return self.generic_visit(node)

    def visit_With(self, node):
        if self.narrative:
            assert len(node.items) == 1
            call = node.items[0].context_expr
            assert isinstance(call, ast.Call) and ast.unparse(call.func) == "closing"
            assert len(call.args) == 1 and not call.keywords
            helper = call.args[0]
            assert self.helper_call(helper) and helper.func.id in {"_assemble", "_publish"}
            expected = statement(BRIDGE.replace("HELPER", ast.unparse(helper)))
            assert dump(node) == dump(expected), "event delegation must close on every exit"
            self.bridges += 1
            return self.expand_body(self.body(helper))
        return self.generic_visit(node)

    def visit_If(self, node):
        if self.narrative and ast.unparse(node.test) == "not run.assembled":
            assert dump(node) == dump(statement(STOP)), "assembly termination guard changed"
            self.stops += 1
            return None
        return self.generic_visit(node)


def compare(old_source, new_source, module):
    old, new = ast.parse(old_source), ast.parse(new_source)
    parent_name = MODULES[module]
    old_functions = {n.name: n for n in old.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    functions = {n.name: n for n in new.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    assert len(functions) == sum(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) for n in new.body), "duplicate function"
    helpers = {name: n for name, n in functions.items() if name not in old_functions}
    assert helpers, "missing split"
    # A helper must not accidentally read an original local as a module global.
    old_table = next(t for t in symtable.symtable(old_source, module, "exec").get_children() if t.get_name() == parent_name)
    old_locals = {s.get_name() for s in old_table.get_symbols() if s.is_local()}
    for table in symtable.symtable(new_source, module, "exec").get_children():
        if table.get_name() in helpers:
            leaked = global_reads(table) & old_locals
            assert not leaked, f"helper lost local inputs: {leaked}"
    narrative = module == "narrative"
    if narrative:
        states = [n for n in new.body if isinstance(n, ast.ClassDef)]
        assert len(states) == 1
        state = copy.deepcopy(states[0])
        state.body = no_doc(state.body)
        assert dump(state) == dump(ast.parse(STATE).body[0]), "state class/defaults changed"
        for node in ast.walk(new):
            if isinstance(node, ast.comprehension):
                assert not any(isinstance(n, ast.Attribute) for n in ast.walk(node.target)), "state escapes comprehension scope"
    if narrative:
        entry = no_doc(functions[parent_name].body)
        assert dump(entry[3]) == dump(statement(CONSTRUCTOR)), "constructor position changed"
        assert isinstance(entry[5], ast.With) and ast.unparse(entry[5].items[0].context_expr) == "closing(_assemble(run, SessionLocal))"
        assert dump(entry[6]) == dump(statement(STOP)), "assembly stop position changed"
        assert isinstance(entry[-1], ast.With) and ast.unparse(entry[-1].items[0].context_expr) == "closing(_publish(run))"
    expander = Expand(helpers, narrative)
    parent = expander.visit(copy.deepcopy(functions[parent_name]))
    assert set(expander.used) == set(helpers), "unexpanded helper"
    if narrative:
        assert (expander.constructors, expander.bridges, expander.stops) == (1, 2, 1), "missing narrative scaffold"
        parent = StateNames().visit(parent)
        parent.body = no_doc(parent.body)
        old_functions[parent_name].body = no_doc(old_functions[parent_name].body)
        old.body = no_doc(old.body)
        new.body = no_doc(new.body)
    restored = []
    removed = set()
    for node in new.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name in helpers:
                continue
            if node.name == parent_name:
                node = parent
        if narrative and isinstance(node, ast.ClassDef):
            continue
        if isinstance(node, ast.ImportFrom):
            keep = []
            for alias in node.names:
                key = (node.module, alias.name)
                if key in EXTRA_IMPORTS[module]:
                    assert node.level == 0 and alias.asname is None and key not in removed
                    removed.add(key)
                else:
                    keep.append(alias)
            node.names = keep
            if not keep:
                continue
        restored.append(node)
    assert removed == EXTRA_IMPORTS[module], "missing/changed helper imports"
    new.body = restored
    ast.fix_missing_locations(new)
    if dump(old) != dump(new):
        return "".join(difflib.unified_diff(ast.unparse(old).splitlines(True), ast.unparse(new).splitlines(True),
                                           fromfile=f"original {module}", tofile=f"reassembled {module}"))
    return ""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--worktree", action="store_true")
    args = parser.parse_args()
    for module in MODULES:
        path = f"backend/app/services/trend_analysis/{module}.py"
        old = subprocess.check_output(["git", "show", f"{args.base}:{path}"], cwd=ROOT, text=True)
        new = (ROOT / path).read_text() if args.worktree else subprocess.check_output(
            ["git", "show", f"{args.head}:{path}"], cwd=ROOT, text=True)
        try:
            diff = compare(old, new, module)
        except (AssertionError, KeyError, StopIteration) as exc:
            print(f"phase move: FAILED ({module}: {exc})")
            return 1
        if diff:
            print(diff)
            return 1
        print(f"phase move: OK ({module}: expanded module AST identical)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
