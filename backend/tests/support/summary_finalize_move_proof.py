"""Reassemble O1's phases and compare summarize_filing to its committed pre-move AST.

Run alongside ast_move_proof with --base/--head (HEAD by default). --worktree is for
mutation proofs. The only erased scaffolding is the validated plain SummaryRun
constructor and its state namespace; helper arguments are substituted, including
the explicitly passed snap/logger/fallback seams. Layout is bound once in order.
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
FACADE = "backend/app/services/openai_service.py"
PHASES = "backend/app/services/ai/summary_finalize.py"


def method(tree):
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "OpenAIService")
    return next(n for n in cls.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "summarize_filing")


def dump(node):
    return ast.dump(node, include_attributes=False)


def validate_state(source, state):
    """Reject executable/default state additions that flattening would otherwise hide."""
    cls = next(c for c in symtable.symtable(source, FACADE, "exec").get_children()
               if c.get_name() == "OpenAIService")
    func = next(c for c in cls.get_children() if c.get_name() == "summarize_filing")
    locals_ = {s.get_name() for s in func.get_symbols() if s.is_local()}
    assert not state.bases and not state.keywords
    assert [ast.unparse(d) for d in state.decorator_list] == ["dataclass"]
    inputs = []
    declared = set()
    for node in state.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            continue
        assert isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name), "executable state body"
        name = node.target.id
        assert name in locals_ and name not in declared, f"unexpected state field {name}"
        declared.add(name)
        if node.value is None:
            inputs.append(name)
        else:
            assert ast.unparse(node.value) == "field(init=False, repr=False)", f"state default: {name}"
    return inputs, declared


class Substitute(ast.NodeTransformer):
    def __init__(self, bindings):
        self.bindings = bindings

    def visit_Name(self, node):
        return copy.deepcopy(self.bindings.get(node.id, node))


class Reassemble(ast.NodeTransformer):
    def __init__(self, functions, inputs, declared):
        self.functions, self.inputs, self.declared = functions, inputs, declared
        self.used = set()
        self.constructors = 0

    def visit_Attribute(self, node):
        self.generic_visit(node)
        if isinstance(node.value, ast.Name) and node.value.id == "run":
            assert node.attr in self.declared, f"undeclared state: {node.attr}"
            return ast.copy_location(ast.Name(id=node.attr, ctx=node.ctx), node)
        return node

    def visit_AnnAssign(self, node):
        was_state = isinstance(node.target, ast.Attribute) and isinstance(node.target.value, ast.Name) and node.target.value.id == "run"
        self.generic_visit(node)
        if was_state:
            node.simple = 1
        return node

    def visit_Assign(self, node):
        if isinstance(node.value, ast.Call) and ast.unparse(node.value.func) == "summary_finalize.SummaryRun":
            assert [ast.unparse(t) for t in node.targets] == ["run"]
            assert not node.value.args
            assert [k.arg for k in node.value.keywords] == self.inputs
            assert all(isinstance(k.value, ast.Name) and k.value.id == k.arg for k in node.value.keywords)
            self.constructors += 1
            return None
        return self.generic_visit(node)

    def expand(self, value):
        awaited = isinstance(value, ast.Await)
        call = value.value if awaited else value
        if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Attribute):
            return None
        if not isinstance(call.func.value, ast.Name) or call.func.value.id != "summary_finalize":
            return None
        helper = self.functions[call.func.attr]
        assert not helper.decorator_list and not call.keywords
        assert awaited == isinstance(helper, ast.AsyncFunctionDef), "changed await boundary"
        args = helper.args
        assert not args.defaults and not args.kwonlyargs and not args.posonlyargs and not args.vararg and not args.kwarg
        assert len(args.args) == len(call.args)
        bindings = {p.arg: a for p, a in zip(args.args, call.args)}
        if "run" in bindings:
            assert ast.unparse(bindings.pop("run")) == "run"
        prefix = []
        if "layout" in bindings:
            prefix.append(ast.Assign(targets=[ast.Name(id="layout", ctx=ast.Store())], value=bindings.pop("layout")))
        self.used.add(helper.name)
        body = copy.deepcopy(helper.body)
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
            assert isinstance(body[0].value.value, str)
            body.pop(0)
        return [self.visit(Substitute(bindings).visit(n)) for n in prefix + body]

    def visit_Expr(self, node):
        expanded = self.expand(node.value)
        return expanded if expanded is not None else self.generic_visit(node)

    def visit_Return(self, node):
        expanded = self.expand(node.value)
        return expanded if expanded is not None else self.generic_visit(node)


def compare(old_source, facade_source, phase_source):
    old = method(ast.parse(old_source))
    new = method(ast.parse(facade_source))
    phase_tree = ast.parse(phase_source)
    state = next(n for n in phase_tree.body if isinstance(n, ast.ClassDef) and n.name == "SummaryRun")
    inputs, declared = validate_state(old_source, state)
    functions = {n.name: n for n in phase_tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    assembler = Reassemble(functions, inputs, declared)
    rebuilt = ast.fix_missing_locations(assembler.visit(copy.deepcopy(new)))
    assert assembler.constructors == 1, "expected one per-call state constructor"
    assert assembler.used == functions.keys() - {"_segments_not_applicable"}, "unused or missing phase"
    if dump(old) != dump(rebuilt):
        return "".join(difflib.unified_diff(ast.unparse(old).splitlines(True), ast.unparse(rebuilt).splitlines(True),
                                           fromfile="original method", tofile="reassembled phases"))
    return ""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--worktree", action="store_true")
    args = parser.parse_args()

    def read(ref, path, worktree=False):
        if worktree:
            return (ROOT / path).read_text()
        return subprocess.check_output(["git", "show", f"{ref}:{path}"], cwd=ROOT, text=True)

    try:
        diff = compare(read(args.base, FACADE), read(args.head, FACADE, args.worktree),
                       read(args.head, PHASES, args.worktree))
    except (AssertionError, KeyError, StopIteration) as exc:
        print(f"phase move: FAILED ({exc})")
        return 1
    print(diff or "phase move: OK (reassembled summarize_filing AST identical; state constructor validated)")
    return int(bool(diff))


if __name__ == "__main__":
    raise SystemExit(main())
