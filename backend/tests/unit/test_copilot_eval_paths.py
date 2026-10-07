"""The paid Copilot fidelity run triggers only on files that can change what it measures.

`.github/workflows/copilot-eval.yml` runs `evals.copilot_bootstrap` and `evals.copilot_runner`
against DeepSeek whenever a `pull_request` touching its `paths:` filter is marked ready. The
filter used to be `backend/**`, so a tests-only or docs-only backend change paid for a run that
could not change its result. This gate reads the entry points from the workflow's own run steps,
recomputes their transitive import closure over every top-level package and module under
`backend/` (tests and task_worker_main included, so the eval cannot quietly depend on code the
filter excludes), and fails when a reachable module falls outside the filter (the filter is
stale) or when a path that cannot affect the run would trigger it (routers, integrations,
`main.py`, `task_worker_main.py`, `dependencies.py`, the Dockerfile, scripts, migrations, tests,
evals Markdown and the summary-eval modules). Runtime-loaded data the closure cannot see
(prompts, the golden set and sources, `app/data`, `app/assets`, the model env file, the
requirements) is pinned by enumerating the real files, and a missing one is an error, never a
silent drop. CLAUDE.md rule 12.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "backend"
WORKFLOW = ROOT / ".github/workflows/copilot-eval.yml"
# Every top-level importable name under backend/: modules, packages and namespace packages (any
# directory holding Python), so no local import is ever dropped as "not local".
LOCAL_TOP_LEVEL = frozenset(
    {p.stem for p in BACKEND.glob("*.py")}
    | {d.name for d in BACKEND.iterdir() if d.is_dir() and any(d.glob("*.py"))}
)
PYTHON_INVOCATION = re.compile(r"\bpython3?\s+(-m\s+[\w.]+|\S+\.py)")
RUN_MODULE = re.compile(r"\bpython3?\s+-m\s+(evals\.[\w.]+)")
EXPECTED_ENTRY_POINTS = ["evals.copilot_bootstrap", "evals.copilot_runner"]
COPILOT_EVAL_MODULES = {"__init__.py", "schema.py", "scorers.py"}


def _existing(paths, what: str) -> list[str]:
    """Repo-relative paths; a path that does not exist is an error, never a silent drop."""
    missing = [p for p in paths if not Path(p).is_file()]
    assert not missing, f"{what}: these inputs no longer exist, update the gate: {missing}"
    return sorted(Path(p).relative_to(ROOT).as_posix() for p in paths)


def _glob(pattern: str) -> list[Path]:
    found = [p for p in BACKEND.glob(pattern) if p.is_file()]
    assert found, f"no files match backend/{pattern}; update the gate"
    return found


# Loaded at runtime rather than imported, so the closure cannot discover them.
def runtime_inputs() -> list[str]:
    return _existing(
        _glob("prompts/*.md") + _glob("evals/copilot_*.json") + _glob("app/data/**/*") + _glob("app/assets/**/*")
        + [BACKEND / "requirements.txt", BACKEND / "requirements-dev.txt", ROOT / ".github/ai-model.env", WORKFLOW],
        "runtime inputs",
    )


# Must never start the paid run: they cannot change its result.
def non_triggers() -> list[str]:
    summary_eval_modules = [
        p for p in _glob("evals/*.py") if not p.name.startswith("copilot_") and p.name not in COPILOT_EVAL_MODULES
    ]
    return _existing(
        _glob("tests/**/*.py") + _glob("evals/*.md") + summary_eval_modules + _glob("scripts/*") + _glob("migrations/*")
        + _glob("app/routers/*.py") + _glob("app/integrations/*.py")
        + [BACKEND / "main.py", BACKEND / "task_worker_main.py", BACKEND / "app/dependencies.py",
           BACKEND / "Dockerfile", BACKEND / "evals/baseline_scores.json"],
        "non-triggers",
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
                if alias.name.split(".")[0] in LOCAL_TOP_LEVEL:
                    yield alias.name
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                package = ".".join(anchor[: len(anchor) - (node.level - 1)])
                base = f"{package}.{base}".strip(".") if base else package
            if base.split(".")[0] in LOCAL_TOP_LEVEL:
                yield base
                for alias in node.names:
                    yield f"{base}.{alias.name}"


def _workflow() -> dict:
    return yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def entry_points() -> list[str]:
    """Every Python program the workflow's run steps execute; all of them must be `-m evals.<module>`."""
    steps = _workflow()["jobs"]["copilot-eval"]["steps"]
    runs = [step.get("run", "") for step in steps]
    invocations = sorted({m for run in runs for m in PYTHON_INVOCATION.findall(run)})
    modules = sorted({m for run in runs for m in RUN_MODULE.findall(run)})
    unknown = [i for i in invocations if not i.startswith("-m evals.")]
    assert not unknown, f"copilot-eval.yml runs Python the gate cannot trace: {unknown}"
    assert modules, "copilot-eval.yml runs no `python -m evals.<module>` step"
    return modules


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
    """GitHub Actions path-filter globs: `**` matches any characters (a leading `**/` also matches
    no directory at all) and `*` any run except `/`. GitHub also defines `?`, `+` and `[…]` as
    quantifiers and character classes of the preceding character; the filter uses none of them,
    and the gate refuses them so a future pattern forces a deliberate matcher update instead of
    being matched wrongly."""
    unsupported = sorted(set(glob) & set("?+[]"))
    if unsupported:
        raise ValueError(f"pattern {glob!r} uses {unsupported}; teach _pattern GitHub's semantics first")
    out, i = "", 0
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
        else:
            out += re.escape(glob[i])
            i += 1
    return re.compile(f"^{out}$")


def workflow_filter() -> list[str]:
    return list(_workflow()["on"]["pull_request"]["paths"])


def triggers(path: str, patterns: list[str]) -> bool:
    """GitHub's rule: the last matching pattern wins; a `!` pattern cancels an earlier match."""
    matched = False
    for raw in patterns:
        negate = raw.startswith("!")
        if _pattern(raw.lstrip("!")).match(path):
            matched = not negate
    return matched


def test_entry_points_come_from_the_workflow_run_steps():
    assert entry_points() == EXPECTED_ENTRY_POINTS


def test_closure_follows_every_top_level_backend_name():
    assert {"app", "evals", "tests", "main", "task_worker_main", "scripts"} <= LOCAL_TOP_LEVEL, sorted(LOCAL_TOP_LEVEL)
    files = reachable_files()
    assert len(files) > 50, sorted(files)
    assert "backend/app/services/copilot_service.py" in files
    assert "backend/app/services/edgar/__init__.py" in files
    # Reached only through a relative import inside a package __init__ (app/schemas/__init__.py).
    assert "backend/app/schemas/contact.py" in files
    assert not [f for f in files if f.startswith("backend/tests/")], "the eval must not import test code"


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
    for unsupported in ("a/b?.py", "a/b+.py", "a/[bc].py"):
        try:
            _pattern(unsupported)
        except ValueError:
            continue
        raise AssertionError(f"_pattern accepted {unsupported!r} without GitHub's quantifier semantics")
