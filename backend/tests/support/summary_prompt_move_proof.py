"""Reassemble O2's primary request and compare its AST with the committed original.

Run alongside ast_move_proof with --base/--head (HEAD by default); --worktree
reads current edits for mutation proofs. Only the exact, validated O2 scaffold
is erased: three synchronous helper boundaries, a literal schema binding, and
service/facade namespaces. No application modules are imported or executed.
"""
from __future__ import annotations

import argparse
import ast
import builtins
import copy
import difflib
import subprocess
import symtable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FACADE = "backend/app/services/openai_service.py"
PROMPT = "backend/app/services/ai/summary_prompt.py"
METHOD = "generate_structured_summary"

# Pin everything reconstruction would otherwise discard, including postponed
# annotations, parameter order, defaults, decorators and extra module statements.
SCAFFOLD = '''
from __future__ import annotations
from types import ModuleType
from typing import Any, Dict, Optional
SCHEMA_TEMPLATE = ""
def _build_context(financial_data: Dict, xbrl_section: str, filing_type_key: str) -> tuple[str, list[str]]:
    pass
def build_primary_request(
    service: Any, facade: ModuleType, filing_type_key: str, sixk_class: Optional[str],
    xbrl_metrics: Optional[Dict], financial_data: Dict, company_name: str,
    filing_type: str, filing_sample: str,
) -> Dict[str, Any]:
    pass
def _request_kwargs(
    service: Any, filing_type_key: str, prompt: str, structured_mode: bool, config: Dict,
) -> Dict[str, Any]:
    pass
'''
PRIMARY = '''create_kwargs: Dict[str, Any] = summary_prompt.build_primary_request(
    self, sys.modules[__name__], filing_type_key, sixk_class, xbrl_metrics,
    financial_data, company_name, filing_type, filing_sample,
)'''
CONTEXT = "data_summary, analysis_focus_lines = _build_context(financial_data, xbrl_section, filing_type_key)"
REQUEST = "return _request_kwargs(service, filing_type_key, prompt, structured_mode, config)"


def dump(node: ast.AST) -> str:
    return ast.dump(node, include_attributes=False)


def statement(source: str) -> ast.stmt:
    return ast.parse(source).body[0]


def without_docstring(body: list[ast.stmt]) -> list[ast.stmt]:
    if (body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)):
        return body[1:]
    return body


def method(tree: ast.Module) -> ast.AsyncFunctionDef:
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "OpenAIService"]
    assert len(classes) == 1, "expected one OpenAIService"
    methods = [n for n in classes[0].body
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == METHOD]
    assert len(methods) == 1 and isinstance(methods[0], ast.AsyncFunctionDef), "method boundary changed"
    return methods[0]


def validate_prompt(source: str) -> tuple[dict[str, ast.FunctionDef], ast.Constant]:
    tree = ast.parse(source)
    shell = copy.deepcopy(tree)
    shell.body = without_docstring(shell.body)
    functions = {}
    schema = None
    for node in shell.body:
        if isinstance(node, ast.FunctionDef):
            assert node.name not in functions, f"duplicate helper: {node.name}"
            functions[node.name] = copy.deepcopy(node)
            node.body = [ast.Pass()]
        elif isinstance(node, ast.Assign):
            assert schema is None, "extra constant or module side effect"
            assert isinstance(node.value, ast.Constant) and isinstance(node.value.value, str), "schema must be a literal string"
            schema = copy.deepcopy(node.value)
            node.value = ast.Constant(value="")
    assert dump(shell) == dump(ast.parse(SCAFFOLD)), "prompt scaffold/signature/default/decorator changed"
    assert schema is not None, "missing schema literal"
    return functions, schema


def remove_facade_imports(tree: ast.Module) -> None:
    """Erase only the two correct new imports; other facade edits remain visible."""
    found = {"sys": 0, "summary_prompt": 0}
    body = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            aliases = []
            for alias in node.names:
                is_sys = isinstance(node, ast.Import) and alias.name == "sys"
                is_prompt = (isinstance(node, ast.ImportFrom) and node.level == 0
                             and node.module == "app.services.ai" and alias.name == "summary_prompt")
                if (is_sys or is_prompt) and alias.asname is None:
                    found[alias.name] += 1
                else:
                    aliases.append(alias)
            node.names = aliases
            if not aliases:
                continue
        body.append(node)
    assert found == {"sys": 1, "summary_prompt": 1}, "facade module identity/import changed"
    tree.body = body


def global_reads(scope: symtable.SymbolTable) -> set[str]:
    names = {s.get_name() for s in scope.get_symbols() if s.is_global() and s.is_referenced()}
    for child in scope.get_children():
        names.update(global_reads(child))
    return names


def validate_globals(old_source: str, prompt_source: str) -> set[str]:
    """A bare moved collaborator would look identical after expansion but resolve elsewhere."""
    old = symtable.symtable(old_source, FACADE, "exec")
    cls = next(s for s in old.get_children() if s.get_name() == "OpenAIService")
    scope = next(s for s in cls.get_children() if s.get_name() == METHOD)
    bound = {s.get_name() for s in old.get_symbols() if s.is_assigned() or s.is_imported()}
    reads = global_reads(scope)
    facade_names = reads & bound
    builtin_names = (reads - bound) & set(dir(builtins))
    prompt = symtable.symtable(prompt_source, PROMPT, "exec")
    for helper in prompt.get_children():
        unexpected = global_reads(helper) - builtin_names - {"SCHEMA_TEMPLATE", "_build_context", "_request_kwargs"}
        assert not unexpected, f"unqualified helper globals: {sorted(unexpected)}"
    return facade_names


class RestoreNamespaces(ast.NodeTransformer):
    def __init__(self, facade_names: set[str]):
        self.facade_names = facade_names

    def visit_Attribute(self, node: ast.Attribute) -> ast.AST:
        if isinstance(node.value, ast.Name) and node.value.id == "facade":
            assert isinstance(node.ctx, ast.Load) and node.attr in self.facade_names, "unexpected facade member"
            return ast.copy_location(ast.Name(id=node.attr, ctx=node.ctx), node)
        return self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> ast.AST:
        assert node.id != "facade", "facade used outside a validated member lookup"
        if node.id == "service":
            return ast.copy_location(ast.Name(id="self", ctx=node.ctx), node)
        return node


def helper_body(function: ast.FunctionDef) -> list[ast.stmt]:
    body = without_docstring(copy.deepcopy(function.body))
    assert body and isinstance(body[-1], ast.Return), f"{function.name}: missing final return"
    returns = [n for stmt in body for n in ast.walk(stmt) if isinstance(n, ast.Return)]
    assert len(returns) == 1, f"{function.name}: changed return boundary"
    return body


def expand_once(body: list[ast.stmt], source: str, replacement: list[ast.stmt]) -> list[ast.stmt]:
    expected = dump(statement(source))
    matches = [i for i, node in enumerate(body) if dump(node) == expected]
    assert len(matches) == 1, f"expected exactly one unchanged boundary: {source}"
    index = matches[0]
    return body[:index] + replacement + body[index + 1:]


def compare(old_source: str, facade_source: str, prompt_source: str) -> str:
    old, rebuilt = ast.parse(old_source), ast.parse(facade_source)
    old_method, new_method = method(old), method(rebuilt)
    functions, schema = validate_prompt(prompt_source)
    facade_names = validate_globals(old_source, prompt_source)
    remove_facade_imports(rebuilt)

    context = helper_body(functions["_build_context"])
    assert dump(context[-1]) == dump(statement("return data_summary, analysis_focus_lines")), "context return tuple changed"
    request = helper_body(functions["_request_kwargs"])
    assert len(request) == 1, "request helper has extra executable code"
    primary = helper_body(functions["build_primary_request"])
    assert dump(primary[-1]) == dump(statement(REQUEST)), "request helper arguments/return changed"
    primary = expand_once(primary, CONTEXT, context[:-1])
    literal = statement("schema_template = SCHEMA_TEMPLATE")
    literal.value = schema
    primary = expand_once(primary, "schema_template = SCHEMA_TEMPLATE", [literal])

    # Retain the facade assignment's annotation and context. Only its validated
    # call value becomes the request helper's exact returned expression.
    assignment = statement(PRIMARY)
    assignment.value = request[0].value
    primary[-1:] = [assignment]
    restore = RestoreNamespaces(facade_names)
    primary = [restore.visit(node) for node in primary]
    new_method.body = expand_once(new_method.body, PRIMARY, primary)
    ast.fix_missing_locations(rebuilt)

    # In addition to method equality, retain the rest of the facade verbatim in
    # AST form: rebinding sys, __name__, summary_prompt or a seam cannot hide in
    # scaffolding. All three helpers and the sole constant were expanded above.
    if dump(old) != dump(rebuilt):
        diff = "".join(difflib.unified_diff(
            ast.unparse(old).splitlines(True), ast.unparse(rebuilt).splitlines(True),
            fromfile="original facade", tofile="reassembled primary request",
        ))
        return diff or "AST differs (including method signature/annotation metadata)\n"
    assert dump(old_method) == dump(new_method)
    return ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--worktree", action="store_true")
    args = parser.parse_args(argv)

    def read(ref: str, path: str, worktree: bool = False) -> str:
        if worktree:
            return (ROOT / path).read_text()
        return subprocess.check_output(["git", "show", f"{ref}:{path}"], cwd=ROOT, text=True)

    try:
        diff = compare(read(args.base, FACADE), read(args.head, FACADE, args.worktree),
                       read(args.head, PROMPT, args.worktree))
    except (AssertionError, KeyError, StopIteration, SyntaxError, OSError, subprocess.CalledProcessError) as exc:
        print(f"prompt move: FAILED ({exc})")
        return 1
    print(diff or "prompt move: OK (reassembled generate_structured_summary AST identical; scaffold validated)")
    return int(bool(diff))


if __name__ == "__main__":
    raise SystemExit(main())
