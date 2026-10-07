"""The paid Copilot fidelity run triggers only on files that can change what it measures.

`.github/workflows/copilot-eval.yml` runs `evals.copilot_bootstrap` and `evals.copilot_runner`
against DeepSeek whenever a `pull_request` touching its `paths:` filter is marked ready. The
filter used to be `backend/**`, so a tests-only or docs-only backend change paid for a run that
could not change its result. This gate recomputes the transitive import closure of the two eval
entry points and fails when a reachable module falls outside the filter (the filter is stale) or
when a path that cannot affect the run would trigger it (`backend/tests/**`, evals Markdown).
Runtime-loaded data the closure cannot see (prompts, the golden set and sources, the model env
file, the requirements) is pinned explicitly. CLAUDE.md rule 12.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "backend"
WORKFLOW = ROOT / ".github/workflows/copilot-eval.yml"
ENTRY_POINTS = ("evals.copilot_runner", "evals.copilot_bootstrap")
LOCAL_PACKAGES = ("app", "evals")

# Loaded at runtime rather than imported, so the closure cannot discover them.
RUNTIME_INPUTS = (
    "backend/prompts/10k-analyst-agent.md",
    "backend/evals/copilot_golden_set.json",
    "backend/evals/copilot_sources.json",
    "backend/requirements.txt",
    "backend/requirements-dev.txt",
    ".github/ai-model.env",
    ".github/workflows/copilot-eval.yml",
)
# Must never start the paid run: they cannot change its result.
NON_TRIGGERS = (
    "backend/tests/unit/test_copilot_eval_paths.py",
    "backend/tests/integration/test_anything.py",
    "backend/evals/RUNBOOK.md",
    "backend/scripts/review_gate.py",
    "backend/migrations/999_anything.sql",
)


def _module_path(module: str) -> Path | None:
    base = BACKEND.joinpath(*module.split("."))
    if base.with_suffix(".py").is_file():
        return base.with_suffix(".py")
    if (base / "__init__.py").is_file():
        return base / "__init__.py"
    return None


def _local_imports(module: str, tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in LOCAL_PACKAGES:
                    yield alias.name
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                package = module.rsplit(".", node.level)[0] if "." in module else ""
                base = f"{package}.{base}".strip(".") if base else package
            if base.split(".")[0] in LOCAL_PACKAGES:
                yield base
                for alias in node.names:
                    yield f"{base}.{alias.name}"


def reachable_files() -> set[str]:
    """Repo-relative paths of every local module the eval entry points import, transitively."""
    seen: set[str] = set()
    stack = list(ENTRY_POINTS)
    while stack:
        module = stack.pop()
        if module in seen:
            continue
        path = _module_path(module)
        if path is None:
            continue
        seen.add(module)
        # Importing a submodule executes every parent package's __init__ too.
        parts = module.split(".")
        stack.extend(".".join(parts[:i]) for i in range(1, len(parts)))
        tree = ast.parse(path.read_text(encoding="utf-8"))
        stack.extend(_local_imports(module, tree))
    return {_module_path(m).relative_to(ROOT).as_posix() for m in seen}


def _pattern(glob: str) -> re.Pattern[str]:
    # GitHub Actions path filters: `**` matches any characters, `*` any except `/`.
    escaped = re.escape(glob).replace(r"\*\*", ".*").replace(r"\*", "[^/]*")
    return re.compile(f"^{escaped}$")


def workflow_filter() -> list[str]:
    data = yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    return list(data["on"]["pull_request"]["paths"])


def triggers(path: str, patterns: list[str]) -> bool:
    """GitHub's rule: the last matching pattern wins; a `!` pattern cancels an earlier match."""
    matched = False
    for raw in patterns:
        negate = raw.startswith("!")
        if _pattern(raw.lstrip("!")).match(path):
            matched = not negate
    return matched


def test_closure_is_nonempty_and_reaches_the_copilot_service():
    files = reachable_files()
    assert len(files) > 50, sorted(files)
    assert "backend/app/services/copilot_service.py" in files
    assert "backend/app/services/edgar/__init__.py" in files


def test_every_reachable_module_and_runtime_input_triggers_the_run():
    patterns = workflow_filter()
    missing = sorted(p for p in reachable_files() | set(RUNTIME_INPUTS) if not triggers(p, patterns))
    assert not missing, f"copilot-eval.yml paths no longer cover inputs of the eval: {missing}"


def test_files_that_cannot_change_the_result_do_not_trigger_the_run():
    patterns = workflow_filter()
    wrong = [p for p in NON_TRIGGERS if triggers(p, patterns)]
    assert not wrong, f"copilot-eval.yml would pay for a run these paths cannot affect: {wrong}"


def test_filter_matcher_follows_github_semantics():
    assert triggers("backend/app/services/ai/copilot_chat.py", ["backend/app/services/ai/**"])
    assert not triggers("backend/app/services/ai/x.py", ["backend/app/services/*"])
    assert triggers("backend/app/services/x.py", ["backend/app/services/*"])
    assert not triggers("backend/evals/RUNBOOK.md", ["backend/evals/**", "!backend/evals/**.md"])
    assert triggers("backend/evals/copilot_runner.py", ["backend/evals/**", "!backend/evals/**.md"])
