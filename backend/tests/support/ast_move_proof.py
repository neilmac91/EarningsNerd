"""AST per-symbol proof that a refactor PR only MOVES code (``lessons/test-pure-move-ast-proof.md``).

A "pure move" claim is a proof, not an assertion: parse the old file and every new file, normalise
each symbol with ``ast.unparse`` (formatting and comments stop mattering; every token of code and
every docstring still counts), and diff per symbol name. Run it from ``backend/`` on COMMITTED state
(``lessons/test-proofs-run-on-committed-state.md``), with paths relative to ``backend/``::

    python -m tests.support.ast_move_proof --base origin/main \\
        --old app/services/facts_service.py \\
        --new app/services/facts_service.py app/services/facts/concepts.py app/services/facts/transport.py

The old file is read from ``--base`` (a git ref) and the new files from ``--head`` (default ``HEAD``),
or from the working tree with ``--worktree``. A symbol is a module-level function, class (its header:
decorators, bases and keywords), class member (method or class attribute, keyed ``Class.member``),
assignment (keyed by its target names; one that sets an attribute or item, such as
``settings.FLAG = False``, keys as ``effect:<target>``) or other module-level expression statement
(``expr:<text>``). Statements inside module-level ``if``/``try``/``with``/``for``/``while`` blocks are
read as module-level, and each such block that holds more than imports is a symbol of its own as well:
keyed by the condition it runs under (``guard:<test, iterable, context or handled exceptions>``), its text
is the whole block with its imports dropped, so changing a condition or an exception type, or moving a
statement into or out of the block, is MISSING or CHANGED. A name bound more than once in one file (a
``try``/``except`` fallback, an ``if``/``else`` pair, a property and its setter) keeps every definition
in source order, so a change to any one of them is CHANGED. Import statements and module docstrings are
not symbols: a move rewrites them by design.

Verdicts: MISSING (defined before, nowhere after), CHANGED (the normalised text differs), DUPLICATE
(defined in more than one new file, e.g. a ``logger`` per sub-module, whose logger NAME changes with
the module), SIDE EFFECT (a NEW symbol that runs code at import, which a move never adds; default
deny, at the statement and the expression level: only a docstring or literal, an assignment of a
literal, a name, or a display of those to plain names, and a def or class whose decorators, defaults,
annotations and bases are inert, is inert. Defaults must be such values and annotations and bases type
expressions; a def's or lambda's body runs later and is not read. ``property``, ``staticmethod``,
``classmethod``, ``dataclass`` and the like are inert decorators; a class keyword such as ``metaclass=``
is not; a call, subscript, attribute read, operator or unpacking in a value is not) and ADDED (other
new symbols, such as the helpers a split introduces, or a façade's ``__all__``). Limit: code that a new
class runs through a BASE (an inherited metaclass, or the base's ``__init_subclass__``) is not visible in
the AST, so a new class with bases is ADDED; read every ADDED class's bases. The exit status is 0 only
when nothing is MISSING, CHANGED, DUPLICATE or SIDE EFFECT beyond the symbols passed with ``--allow``;
each allowed symbol is a disclosed delta the PR body must list, and its diff is printed with it.
"""
from __future__ import annotations

import argparse
import ast
import copy
import difflib
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent

_COMPOUND = (ast.If, ast.Try, ast.With, ast.AsyncWith, ast.For, ast.AsyncFor, ast.While)
if hasattr(ast, "TryStar"):  # Python 3.11+
    _COMPOUND = (*_COMPOUND, ast.TryStar)


def _flatten(body: list[ast.stmt]) -> list[ast.stmt]:
    """Statements at module level, reading through module-level compound blocks."""
    out: list[ast.stmt] = []
    for node in body:
        if isinstance(node, _COMPOUND):
            for name in ("body", "orelse", "finalbody"):
                out.extend(_flatten(getattr(node, name, []) or []))
            for handler in getattr(node, "handlers", []) or []:
                out.extend(_flatten(handler.body))
        else:
            out.append(node)
    return out


def _target_names(target: ast.expr) -> list[str]:
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, (ast.Tuple, ast.List)):
        return [n for elt in target.elts for n in _target_names(elt)]
    if isinstance(target, ast.Starred):
        return _target_names(target.value)
    return [ast.unparse(target)]


def _is_docstring(node: ast.stmt) -> bool:
    return isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)


def _assignment_key(targets: list[ast.expr]) -> str:
    """Key an assignment by its target names; one that sets an attribute or an item is a side effect."""
    names = [n for t in targets for n in _target_names(t)]
    key = ",".join(names)
    return key if all(n.isidentifier() for n in names) else "effect:" + key


# Decorators that only wrap the function in a descriptor or generate methods: applying one has no effect
# outside the class or module, so a new method or class may carry them (a property's setter included).
_INERT_DECORATORS = frozenset({"property", "staticmethod", "classmethod", "cached_property", "abstractmethod",
                               "functools.cached_property", "abc.abstractmethod", "dataclass",
                               "dataclasses.dataclass"})


def _inert_value(node: ast.expr | None) -> bool:
    """A value whose evaluation runs no code of its own: a literal, a name, a signed number, a tuple or list
    of those, a set or dict keyed by literals, or a lambda (its body runs later) with inert defaults. A
    call, subscript, attribute read, operator, comprehension, f-string or unpacking can run a
    user-defined method (``__getitem__``, ``__iter__``, ``__add__``, ``__getattr__``) at import."""
    if node is None or isinstance(node, (ast.Constant, ast.Name)):
        return True
    if isinstance(node, ast.UnaryOp):
        return isinstance(node.op, (ast.USub, ast.UAdd)) and isinstance(node.operand, ast.Constant)
    if isinstance(node, (ast.Tuple, ast.List)):
        return all(_inert_value(elt) for elt in node.elts)
    if isinstance(node, ast.Set):
        return all(isinstance(elt, ast.Constant) for elt in node.elts)
    if isinstance(node, ast.Dict):  # a None key is a ** unpacking
        return all(isinstance(key, ast.Constant) for key in node.keys) and all(map(_inert_value, node.values))
    if isinstance(node, ast.Lambda):
        return _inert_arguments(node.args)
    return False


def _type_expression(node: ast.expr | None) -> bool:
    """An annotation or base built from names, attribute reads, subscripts, literals, ``|`` unions and
    tuples. It runs only typing machinery (``__class_getitem__``, ``__or__``), which is taken as inert."""
    if node is None or isinstance(node, (ast.Constant, ast.Name)):
        return True
    if isinstance(node, ast.Attribute):
        return _type_expression(node.value)
    if isinstance(node, ast.Subscript):
        return _type_expression(node.value) and _type_expression(node.slice)
    if isinstance(node, (ast.Tuple, ast.List)):
        return all(_type_expression(elt) for elt in node.elts)
    if isinstance(node, ast.BinOp):
        return isinstance(node.op, ast.BitOr) and _type_expression(node.left) and _type_expression(node.right)
    return False


def _inert_arguments(args: ast.arguments) -> bool:
    """A def's or lambda's defaults (evaluated at definition) are inert values, its annotations type expressions."""
    params = [*args.posonlyargs, *args.args, *args.kwonlyargs, *(a for a in (args.vararg, args.kwarg) if a)]
    defaults = [*args.defaults, *(d for d in args.kw_defaults if d is not None)]
    return all(map(_inert_value, defaults)) and all(_type_expression(p.annotation) for p in params)


def _inert_decorator(decorator: ast.expr) -> bool:
    """Applying a decorator calls it at import; only the descriptor-making ones, with inert arguments, are inert."""
    call = decorator if isinstance(decorator, ast.Call) else None
    name = ast.unparse(call.func if call else decorator)
    if not (name in _INERT_DECORATORS or name.endswith((".setter", ".getter", ".deleter"))):
        return False
    return call is None or all(_inert_value(arg) for arg in (*call.args, *(kw.value for kw in call.keywords)))


def _plain_target(target: ast.expr) -> bool:
    if isinstance(target, (ast.Tuple, ast.List)):
        return all(_plain_target(elt) for elt in target.elts)
    return isinstance(target, ast.Name)


def _inert(stmt: ast.stmt) -> bool:
    """Whether a NEW statement runs no code at import beyond binding names (default deny). Inert: ``pass``,
    a docstring or bare literal, an assignment of an inert value to plain names, and a def or class whose
    decorators, defaults, annotations and bases are inert (a def's body runs later; a class body must be
    inert too, and a class keyword such as ``metaclass=`` runs class-creation code)."""
    if isinstance(stmt, ast.Pass):
        return True
    if isinstance(stmt, ast.Expr):
        return isinstance(stmt.value, ast.Constant)
    if isinstance(stmt, ast.Assign):
        return all(map(_plain_target, stmt.targets)) and _inert_value(stmt.value)
    if isinstance(stmt, ast.AnnAssign):
        return isinstance(stmt.target, ast.Name) and _type_expression(stmt.annotation) and _inert_value(stmt.value)
    if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return (all(map(_inert_decorator, stmt.decorator_list)) and _inert_arguments(stmt.args)
                and _type_expression(stmt.returns))
    if isinstance(stmt, ast.ClassDef):
        return (not stmt.keywords and all(map(_inert_decorator, stmt.decorator_list))
                and all(map(_type_expression, stmt.bases)) and all(map(_inert, stmt.body)))
    return False


def _runs_at_import(name: str, text: str) -> bool:
    """A NEW symbol that executes code when its module is imported: anything that is not ``_inert``. An
    attribute or item assignment (``effect:``) and a guard block (``guard:``) always do. Class members
    (keyed ``Class.member``) follow the same rule."""
    owner, _, member = name.partition(".")
    if not (member and owner.isidentifier()):
        member = name
    if member.startswith(("effect:", "guard:")):
        return True
    return not all(_inert(stmt) for stmt in ast.parse(text).body)


def _guards(body: list[ast.stmt]) -> list[ast.stmt]:
    """Every compound block at this level and inside one (never inside a def or class)."""
    out: list[ast.stmt] = []
    for node in body:
        if isinstance(node, _COMPOUND):
            out.append(node)
            for name in ("body", "orelse", "finalbody"):
                out.extend(_guards(getattr(node, name, []) or []))
            for handler in getattr(node, "handlers", []) or []:
                out.extend(_guards(handler.body))
    return out


def _holds_code(node: ast.stmt) -> bool:
    """Whether a block holds a statement other than an import or ``pass``, at any depth."""
    return any(isinstance(inner, ast.stmt) and not isinstance(inner, (*_COMPOUND, ast.Import, ast.ImportFrom, ast.Pass))
               for inner in ast.walk(node) if inner is not node)


def _guard_header(node: ast.stmt) -> str:
    """The condition a block runs under: its test, iterable, context or handled exceptions."""
    if isinstance(node, (ast.If, ast.While)):
        return f"{'if' if isinstance(node, ast.If) else 'while'} {ast.unparse(node.test)}"
    if isinstance(node, (ast.For, ast.AsyncFor)):
        word = "async for" if isinstance(node, ast.AsyncFor) else "for"
        return f"{word} {ast.unparse(node.target)} in {ast.unparse(node.iter)}"
    if isinstance(node, (ast.With, ast.AsyncWith)):
        word = "async with" if isinstance(node, ast.AsyncWith) else "with"
        return f"{word} {', '.join(ast.unparse(item) for item in node.items)}"
    handled = ", ".join((ast.unparse(h.type) if h.type is not None else "everything")
                        + (f" as {h.name}" if h.name else "") for h in node.handlers)
    word = "try" if isinstance(node, ast.Try) else "try*"
    return f"{word} except {handled}" + (" else" if node.orelse else "") + (" finally" if node.finalbody else "")


def _without_imports(node: ast.stmt) -> ast.stmt:
    """A copy of the block with its import statements dropped: a move rewrites imports by design."""
    node = copy.deepcopy(node)
    for inner in ast.walk(node):
        for name in ("body", "orelse", "finalbody"):
            stmts = getattr(inner, name, None)
            if isinstance(stmts, list) and stmts and isinstance(stmts[0], ast.stmt):
                kept = [stmt for stmt in stmts if not isinstance(stmt, (ast.Import, ast.ImportFrom))]
                setattr(inner, name, kept or ([ast.Pass()] if name == "body" else []))
    return node


def symbols(source: str) -> dict[str, str]:
    """Map every symbol the source defines to its normalised (``ast.unparse``) text."""
    tree = ast.parse(source)
    found: dict[str, str] = {}

    def put(key: str, text: str) -> None:
        found[key] = f"{found[key]}\n{text}" if key in found else text  # every definition, in source order

    body = list(tree.body)
    if body and _is_docstring(body[0]):
        body = body[1:]  # the module docstring is rewritten by a move by design
    for guard in _guards(body):
        if _holds_code(guard):
            put("guard:" + _guard_header(guard), ast.unparse(_without_imports(guard)))
    for node in _flatten(body):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            put(node.name, ast.unparse(node))
        elif isinstance(node, ast.ClassDef):
            members = [m for m in _flatten(node.body) if not isinstance(m, (ast.Import, ast.ImportFrom))]
            header = ast.ClassDef(
                name=node.name, bases=node.bases, keywords=node.keywords,
                body=[ast.Pass()], decorator_list=node.decorator_list,
                **({"type_params": node.type_params} if hasattr(node, "type_params") else {}),
            )
            put(node.name, ast.unparse(ast.fix_missing_locations(header)))
            for guard in _guards(node.body):
                if _holds_code(guard):
                    put(f"{node.name}.guard:{_guard_header(guard)}", ast.unparse(_without_imports(guard)))
            for member in members:
                if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    key = member.name
                elif isinstance(member, ast.Assign):
                    key = ",".join(n for t in member.targets for n in _target_names(t))
                elif isinstance(member, (ast.AnnAssign, ast.AugAssign)):
                    key = ",".join(_target_names(member.target))
                elif isinstance(member, ast.Pass):
                    continue
                else:
                    key = "expr:" + ast.unparse(member)
                put(f"{node.name}.{key}", ast.unparse(member))
        elif isinstance(node, ast.Assign):
            put(_assignment_key(node.targets), ast.unparse(node))
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            put(_assignment_key([node.target]), ast.unparse(node))
        elif isinstance(node, ast.Pass):
            continue
        else:
            text = ast.unparse(node)
            put("expr:" + text, text)
    return found


@dataclass
class Report:
    moved: int = 0
    missing: list[str] = field(default_factory=list)
    changed: dict[str, str] = field(default_factory=dict)  # symbol -> unified diff
    duplicate: dict[str, list[str]] = field(default_factory=dict)  # symbol -> new files
    side_effects: dict[str, str] = field(default_factory=dict)  # new import-time statement -> new file
    added: dict[str, str] = field(default_factory=dict)  # symbol -> new file
    allowed: dict[str, str] = field(default_factory=dict)  # disclosed symbol -> what changed

    @property
    def ok(self) -> bool:
        return not (self.missing or self.changed or self.duplicate or self.side_effects)


def _delta(name: str, text: str | None, homes: list[str], new_by_file: dict[str, dict[str, str]]) -> str:
    """What happened to one symbol, for a disclosed (allowed) delta."""
    if text is None:
        return f"added in {', '.join(homes)}"
    if not homes:
        return "missing"
    if len(homes) > 1:
        return f"defined in {', '.join(homes)}"
    new_text = new_by_file[homes[0]][name]
    if new_text == text:
        return "unchanged"
    return "\n".join(difflib.unified_diff(text.splitlines(), new_text.splitlines(), "old", homes[0], lineterm="", n=1))


def compare(old_source: str, new_sources: dict[str, str], allow: frozenset[str] = frozenset()) -> Report:
    """Diff the old file's symbols against the union of the new files' symbols."""
    old = symbols(old_source)
    new_by_file = {path: symbols(src) for path, src in new_sources.items()}
    where: dict[str, list[str]] = {}
    for path, syms in new_by_file.items():
        for name in syms:
            where.setdefault(name, []).append(path)
    report = Report()
    for name, text in old.items():
        homes = where.get(name, [])
        if name in allow:
            report.allowed[name] = _delta(name, text, homes, new_by_file)
            continue
        if not homes:
            report.missing.append(name)
            continue
        if len(homes) > 1:
            report.duplicate[name] = homes
            continue
        new_text = new_by_file[homes[0]][name]
        if new_text != text:
            diff = difflib.unified_diff(text.splitlines(), new_text.splitlines(), "old", homes[0], lineterm="", n=1)
            report.changed[name] = "\n".join(diff)
            continue
        report.moved += 1
    for name, homes in where.items():
        if name in old:
            continue
        if name in allow:
            report.allowed[name] = _delta(name, None, homes, new_by_file)
        elif len(homes) > 1:
            report.duplicate[name] = homes
        elif _runs_at_import(name, new_by_file[homes[0]][name]):
            report.side_effects[name] = homes[0]
        else:
            report.added[name] = homes[0]
    return report


def _git_show(ref: str, rel_path: str) -> str:
    repo_path = (BACKEND_DIR / rel_path).resolve().relative_to(REPO_ROOT).as_posix()
    result = subprocess.run(  # nosec B603 B607 - fixed git argv, read-only, developer tool
        ["git", "-C", str(REPO_ROOT), "show", f"{ref}:{repo_path}"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        raise SystemExit(f"cannot read {repo_path} at {ref}: {result.stderr.strip()}")
    return result.stdout


def render(report: Report) -> str:
    lines = []
    for name in sorted(report.missing):
        lines.append(f"MISSING    {name}")
    for name, diff in sorted(report.changed.items()):
        lines.append(f"CHANGED    {name}\n{diff}")
    for name, homes in sorted(report.duplicate.items()):
        lines.append(f"DUPLICATE  {name}: {', '.join(homes)}")
    for name, home in sorted(report.side_effects.items()):
        lines.append(f"SIDE EFFECT {name} ({home}): runs at import; a move never adds one")
    for name, home in sorted(report.added.items()):
        lines.append(f"ADDED      {name} ({home})")
    for name, delta in sorted(report.allowed.items()):
        lines.append(f"ALLOWED    {name} (disclosed delta)\n{delta}")
    verdict = "OK" if report.ok else "FAILED"
    lines.append(
        f"pure move: {verdict} ({report.moved} symbols identical, {len(report.missing)} missing, "
        f"{len(report.changed)} changed, {len(report.duplicate)} duplicated, "
        f"{len(report.side_effects)} side effects, {len(report.added)} added, {len(report.allowed)} allowed)"
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--base", required=True, help="git ref holding the file before the move")
    parser.add_argument("--old", required=True, help="the file before the move, relative to backend/")
    parser.add_argument("--new", required=True, nargs="+", help="every file the code lives in after the move")
    parser.add_argument("--head", default="HEAD", help="git ref holding the new files (default HEAD)")
    parser.add_argument("--worktree", action="store_true", help="read the new files from the working tree instead")
    parser.add_argument("--allow", action="append", default=[], help="a disclosed delta (repeatable)")
    args = parser.parse_args(argv)
    old_source = _git_show(args.base, args.old)
    new_sources = {
        path: (BACKEND_DIR / path).read_text() if args.worktree else _git_show(args.head, path)
        for path in args.new
    }
    report = compare(old_source, new_sources, frozenset(args.allow))
    print(render(report))
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
