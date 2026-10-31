#!/usr/bin/env python3
"""Which definitions did the branch change in backend/app, and who reads the stamp?

For every backend/app Python file that differs between BASE and HEAD, both versions are parsed and
every function/method (by qualified name) and every module-level assignment is compared by
`ast.dump` (no line numbers). Prints the changed definitions, then every backend/app reader of
SUMMARY_PROMPT_VERSION at HEAD, so the render-only scope can be checked without reading the diff.

Usage (cwd = the worktree root):  python ast_scope.py BASE HEAD
"""
from __future__ import annotations

import ast
import subprocess
import sys


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


def definitions(source: str) -> dict:
    out = {}

    def walk(node, prefix):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = f"{prefix}{child.name}"
                if not isinstance(child, ast.ClassDef):
                    out[f"def {name}"] = ast.dump(child)
                walk(child, f"{name}.")
            elif prefix == "" and isinstance(child, (ast.Assign, ast.AnnAssign)):
                targets = child.targets if isinstance(child, ast.Assign) else [child.target]
                for t in targets:
                    out[f"assign {ast.unparse(t)}"] = ast.dump(child)
    walk(ast.parse(source), "")
    return out


def main() -> int:
    base, head = sys.argv[1], sys.argv[2]
    files = [f for f in git("diff", "--name-only", base, head, "--", "backend/app").split() if f.endswith(".py")]
    print(f"backend/app files changed {base}..{head}: {files}")
    for path in files:
        a, b = definitions(git("show", f"{base}:{path}")), definitions(git("show", f"{head}:{path}"))
        changed = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
        print(f"{path}: changed definitions {changed}")
    print("backend/app readers of SUMMARY_PROMPT_VERSION at HEAD:")
    print(git("grep", "-n", "SUMMARY_PROMPT_VERSION", head, "--", "backend/app").replace(f"{head}:", ""), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
