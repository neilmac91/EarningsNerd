"""The paid Copilot fidelity run triggers only on files that can change what it measures.

`.github/workflows/copilot-eval.yml` runs `evals.copilot_bootstrap` and `evals.copilot_runner`
against DeepSeek whenever a `pull_request` touching its `paths:` filter is marked ready. The
filter used to be `backend/**`, so a tests-only or docs-only backend change paid for a run that
could not change its result. This gate reads the entry points from the workflow's own run steps,
recomputes their transitive import closure, and fails when a reachable module falls outside the
filter (the filter is stale) or when a path that cannot affect the run would trigger it
(`backend/tests/**`, evals Markdown and the summary-eval modules, scripts, migrations).
Runtime-loaded data the closure cannot see (prompts, the golden set and sources, the model env
file, the requirements) is pinned by enumerating the real files. CLAUDE.md rule 12.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "backend"
WORKFLOW = ROOT / ".github/workflows/copilot-eval.yml"
LOCAL_PACKAGES = ("app", "evals", "main", "scripts")
RUN_MODULE = re.compile(r"python -m (evals\.[\w.]+)")


def _rel(paths) -> list[str]:
    return sorted(p.relative_to(ROOT).as_posix() for p in paths if p.is_file())


# Loaded at runtime rather than imported, so the closure cannot discover them.
def runtime_inputs() -> list[str]:
    return _rel(
        list(BACKEND.glob("prompts/*.md"))
        + list(BACKEND.glob("evals/copilot_*.json"))
        + [BACKEND / "requirements.txt", BACKEND / "requirements-dev.txt",
           ROOT / ".github/ai-model.env", WORKFLOW]
    )


# Must never start the paid run: they cannot change its result.
def non_triggers() -> list[str]:
    return _rel(
        list(BACKEND.glob("tests/**/*.py"))
        + list(BACKEND.glob("evals/*.md"))
        + list(BACKEND.glob("scripts/*"))
        + list(BACKEND.glob("migrations/*"))
        + [BACKEND / "evals/runner.py", BACKEND / "evals/regression_gate.py",
           BACKEND / "evals/judge_readout.py", BACKEND / "evals/baseline_scores.json"]
    )


def _module_path(module: str) -> Path | None:
    base = BACKEND.joinpath(*module.split("."))
    if base.with_suffix(".py").is_file():
        return base.with_suffix(".py")
    if (base / "__init__.py").is_file():
        return base / "__init__.py"
    return None


def _local_imports(module: str, is_package: bool, tree: ast.AST):
    """Module names imported by `module`; relative imports anchor on the package that owns the file.

    For a package's own ``__init__.py`` that package is the module itself; for a plain module it
    is the parent. Each further dot climbs one package.
    """
    anchor = module.split(".") if is_package else module.split(".")[:-1]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in LOCAL_PACKAGES:
                    yield alias.name
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                package = ".".join(anchor[: len(anchor) - (node.level - 1)])
                base = f"{package}.{base}".strip(".") if base else package
            if base.split(".")[0] in LOCAL_PACKAGES:
                yield base
                for alias in node.names:
                    yield f"{base}.{alias.name}"


def entry_points() -> list[str]:
    """The `python -m evals.<module>` commands the workflow actually runs."""
    data = yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    steps = data["jobs"]["copilot-eval"]["steps"]
    found = sorted({m for step in steps for m in RUN_MODULE.findall(step.get("run", ""))})
    assert found, "copilot-eval.yml runs no `python -m evals.<module>` step"
    return found


def reachable_files(roots=None) -> set[str]:
    """Repo-relative paths of every local module the entry points import, transitively."""
    seen: set[str] = set()
    stack = list(roots or entry_points())
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
        stack.extend(_local_imports(module, path.name == "__init__.py", tree))
    return {_module_path(m).relative_to(ROOT).as_posix() for m in seen}


def _pattern(glob: str) -> re.Pattern[str]:
    # GitHub Actions path filters: `**` matches any characters (a leading `**/` also matches no
    # directory at all), `*` any run except `/`, `?` one character except `/`, `+` one or more.
    out = ""
    i = 0
    while i < len(glob):
        if glob.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
        elif glob.startswith("**", i):
            out += ".*"
            i += 2
        elif glob[i] == "*":
            out += "[^/]*"
            i += 1
        elif glob[i] == "?":
            out += "[^/]"
            i += 1
        elif glob[i] == "+":
            out += "[^/]+"
            i += 1
        else:
            out += re.escape(glob[i])
            i += 1
    return re.compile(f"^{out}$")


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


def test_entry_points_come_from_the_workflow_run_steps():
    assert entry_points() == ["evals.copilot_bootstrap", "evals.copilot_runner"]


def test_closure_is_nonempty_and_reaches_the_copilot_service():
    files = reachable_files()
    assert len(files) > 50, sorted(files)
    assert "backend/app/services/copilot_service.py" in files
    assert "backend/app/services/edgar/__init__.py" in files
    # Reached only through a relative import inside a package __init__ (app/schemas/__init__.py).
    assert "backend/app/schemas/contact.py" in files


def test_relative_imports_anchor_on_the_owning_package():
    tree = ast.parse("from .contact import ContactSubmissionCreate\nfrom ..utils import numbers\n")
    assert set(_local_imports("app.schemas", True, tree)) >= {"app.schemas.contact", "app.utils", "app.utils.numbers"}
    assert set(_local_imports("app.schemas.summary", False, tree)) >= {"app.schemas.contact", "app.utils"}


def test_every_reachable_module_and_runtime_input_triggers_the_run():
    patterns = workflow_filter()
    inputs = runtime_inputs()
    assert len(inputs) > 10, inputs
    missing = sorted(p for p in reachable_files() | set(inputs) if not triggers(p, patterns))
    assert not missing, f"copilot-eval.yml paths no longer cover inputs of the eval: {missing}"


def test_files_that_cannot_change_the_result_do_not_trigger_the_run():
    patterns = workflow_filter()
    candidates = non_triggers()
    assert len(candidates) > 100, candidates
    wrong = [p for p in candidates if triggers(p, patterns)]
    assert not wrong, f"copilot-eval.yml would pay for a run these paths cannot affect: {wrong}"


def test_filter_matcher_follows_github_semantics():
    assert triggers("backend/app/services/ai/copilot_chat.py", ["backend/app/services/ai/**"])
    assert not triggers("backend/app/services/ai/x.py", ["backend/app/services/*"])
    assert triggers("backend/app/services/x.py", ["backend/app/services/*"])
    assert not triggers("backend/evals/RUNBOOK.md", ["backend/evals/**", "!backend/evals/**.md"])
    assert triggers("backend/evals/copilot_runner.py", ["backend/evals/**", "!backend/evals/**.md"])
    assert triggers("docs/README.md", ["**/docs/**"]) and triggers("a/docs/b/c.md", ["**/docs/**"])
    assert triggers("backend/evals/copilot_x.json", ["backend/evals/copilot_*"])
    assert triggers("a/b1.py", ["a/b?.py"]) and not triggers("a/b12.py", ["a/b?.py"])
    assert triggers("a/b12.py", ["a/b+.py"]) and not triggers("a/b.py", ["a/b+.py"])
