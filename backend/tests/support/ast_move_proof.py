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
read as module-level. A name bound more than once in one file (a ``try``/``except`` fallback, an
``if``/``else`` pair, a property and its setter) keeps every definition in source order, so a change to
any one of them is CHANGED. Import statements and module docstrings are not symbols: a move rewrites
them by design.

Verdicts: MISSING (defined before, nowhere after), CHANGED (the normalised text differs), DUPLICATE
(defined in more than one new file, e.g. a ``logger`` per sub-module, whose logger NAME changes with
the module), SIDE EFFECT (a NEW ``effect:`` or ``expr:`` statement: code that runs at import, which a
move never adds) and ADDED (other new symbols, such as the helpers a split introduces, or a façade's
``__all__``). The exit status is 0 only when nothing is MISSING, CHANGED, DUPLICATE or SIDE EFFECT
beyond the symbols passed with ``--allow``; each allowed symbol is a disclosed delta the PR body must
list, and its diff is printed with it.
"""
from __future__ import annotations

import argparse
import ast
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


def _is_side_effect(name: str) -> bool:
    return name.startswith(("effect:", "expr:"))


def symbols(source: str) -> dict[str, str]:
    """Map every symbol the source defines to its normalised (``ast.unparse``) text."""
    tree = ast.parse(source)
    found: dict[str, str] = {}

    def put(key: str, text: str) -> None:
        found[key] = f"{found[key]}\n{text}" if key in found else text  # every definition, in source order

    body = list(tree.body)
    if body and _is_docstring(body[0]):
        body = body[1:]  # the module docstring is rewritten by a move by design
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
        elif _is_side_effect(name):
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
