"""The paid Copilot fidelity run triggers only on files that can change what it measures.

`.github/workflows/copilot-eval.yml` runs `evals.copilot_bootstrap` and `evals.copilot_runner`
against DeepSeek whenever a `pull_request` touching its `paths:` filter is marked ready. The
filter used to be `backend/**`, so a tests-only or docs-only backend change paid for a run that
could not change its result. This gate reads the entry points from the workflow's own run steps,
recomputes their transitive import closure over every top-level package and module under
`backend/` (tests and task_worker_main included, so the eval cannot quietly depend on code the
filter excludes), and fails when a reachable module falls outside the filter (the filter is
stale) or when a path that cannot affect the run would trigger it (routers, integrations,
`main.py`, `task_worker_main.py`, the Dockerfile, scripts, migrations, tests, evals Markdown and
the summary-eval modules; files directly under `app/` trigger as a group so a new top-level module
cannot fall outside the filter).

The run steps are read as an allowlist, not a denylist: every simple command of every `run:` step
(split on `&&`, `||`, `;` and `|` outside quotes) must be exactly `python -m evals.<module>` with
plain arguments or one of the few fixed shell commands the workflow uses, under a bash or sh shell
at every level. Anything else (a chained `python -c`, an interpreter or shell called by path, a
script executed directly, a versioned interpreter, `pytest`, `uv run`, `node`, `source`, a command
substitution, a Python `shell:` on the step, the job or the workflow, a local action) is a program
whose imports the closure cannot see, so it fails the gate until it is traced or allowed here.

Runtime-loaded data the closure cannot see is pinned by enumerating the real files (prompts, the
golden set and sources, the model env file, the requirements), and a missing one is an error, never
a silent drop. `app/data` and `app/assets` are read by services the gate finds through their
`/ "data"` and `/ "assets"` path components; each directory triggers the run only while one of
its readers is in the closure, and is a non-trigger otherwise. CLAUDE.md rule 12.
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
# non-hidden directory holding Python at any depth), so no local import is ever dropped as "not local".
LOCAL_TOP_LEVEL = frozenset(
    {p.stem for p in BACKEND.glob("*.py")}
    | {d.name for d in BACKEND.iterdir() if d.is_dir() and not d.name.startswith(".") and any(d.rglob("*.py"))}
)
EXPECTED_ENTRY_POINTS = ["evals.copilot_bootstrap", "evals.copilot_runner"]
# Summary-eval modules the copilot modules import; they must stay in the closure to keep triggering.
COPILOT_EVAL_MODULES = {"__init__.py", "schema.py", "scorers.py"}
# The only entry form: the bare interpreter, `-m evals.<module>`, then flags, quoted or bare
# arguments and `2>&1`. No other interpreter spelling, no flag before `-m`, no `(` or backtick.
ENTRY = re.compile(r"^python -m (evals\.[\w.]+)((?:\s+(?:--[\w-]+|\"[^\"`()]*\"|'[^']*'|[\w./$:=-]+|2>&1))*)$")
# The fixed shell commands the workflow uses; a new one needs a deliberate entry here.
SAFE_COMMANDS = (
    re.compile(r"^mkdir -p [\w./-]+$"),
    re.compile(r"^tee [\w./-]+$"),
    re.compile(r"^pip install(?: -r [\w./-]+)+$"),
    re.compile(r"^grep -v '[^']*' [\w./-]+ >> \"\$GITHUB_ENV\"$"),
    re.compile(r"^if \[ -f [\w./-]+ \]$"),
    re.compile(r"^then cat [\w./-]+ >> \"\$GITHUB_STEP_SUMMARY\"$"),
    re.compile(r"^fi$"),
)
SHELL = re.compile(r"^(bash|sh)(\s|$)")
# Directories a service reads at run time, located by a `/ "<name>"` path component; the gate finds
# their readers by that literal, so the map cannot go stale silently.
DATA_DIRS = {"app/data": re.compile(r'/\s*"data"'), "app/assets": re.compile(r'/\s*"assets"')}


def _existing(paths, what: str) -> list[str]:
    """Repo-relative paths; a path that does not exist is an error, never a silent drop."""
    missing = [p for p in paths if not Path(p).is_file()]
    assert not missing, f"{what}: these inputs no longer exist, update the gate: {missing}"
    return sorted(Path(p).relative_to(ROOT).as_posix() for p in paths)


def _glob(pattern: str) -> list[Path]:
    found = [p for p in BACKEND.glob(pattern) if p.is_file()]
    assert found, f"no files match backend/{pattern}; update the gate"
    return found


def _data_dir_readers() -> dict[str, set[str]]:
    readers: dict[str, set[str]] = {d: set() for d in DATA_DIRS}
    for p in (BACKEND / "app").rglob("*.py"):
        text = p.read_text(encoding="utf-8")
        for d, pattern in DATA_DIRS.items():
            if pattern.search(text):
                readers[d].add("backend/" + p.relative_to(BACKEND).as_posix())
    for d, found in readers.items():
        assert found, f"no module locates backend/{d} by its path component; update DATA_DIRS"
    return readers


def _data_dirs_read_by(closure: set[str]) -> tuple[list[str], list[str]]:
    """(directories a closure module reads, directories none does)."""
    readers = _data_dir_readers()
    read = sorted(d for d, found in readers.items() if found & closure)
    unread = sorted(d for d in readers if d not in read)
    return read, unread


# Loaded at runtime rather than imported, so the closure cannot discover them.
def runtime_inputs(closure: set[str]) -> list[str]:
    read, _ = _data_dirs_read_by(closure)
    return _existing(
        _glob("prompts/*.md") + _glob("evals/copilot_*.json") + [f for d in read for f in _glob(f"{d}/**/*")]
        + [BACKEND / "requirements.txt", BACKEND / "requirements-dev.txt", ROOT / ".github/ai-model.env", WORKFLOW],
        "runtime inputs",
    )


# Must never start the paid run: they cannot change its result.
def non_triggers(closure: set[str]) -> list[str]:
    _, unread = _data_dirs_read_by(closure)
    summary_eval_modules = [
        p for p in _glob("evals/*.py") if not p.name.startswith("copilot_") and p.name not in COPILOT_EVAL_MODULES
    ]
    return _existing(
        _glob("tests/**/*") + _glob("evals/**/*.md") + summary_eval_modules + _glob("scripts/*") + _glob("migrations/*")
        + _glob("app/routers/*.py") + _glob("app/integrations/*.py") + [f for d in unread for f in _glob(f"{d}/**/*")]
        + [BACKEND / "main.py", BACKEND / "task_worker_main.py", BACKEND / "Dockerfile", BACKEND / "evals/baseline_scores.json"],
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


def _simple_commands(run_text: str):
    """Each simple command of a run step: lines split on `&&`, `||`, `;`, `|` and `&` outside quotes
    (`>&` stays a redirection); blank lines and comments skipped."""
    for line in run_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts, quote, start, i = [], None, 0, 0
        while i < len(line):
            ch = line[i]
            if quote:
                if ch == quote:
                    quote = None
            elif ch in "'\"":
                quote = ch
            elif ch in "|&;" and not (ch == "&" and i > 0 and line[i - 1] == ">"):
                parts.append(line[start:i])
                if i + 1 < len(line) and line[i + 1] in "|&":
                    i += 1
                start = i + 1
            i += 1
        parts.append(line[start:])
        for part in parts:
            if part.strip():
                yield part.strip()


def _classify(command: str) -> tuple[str, str | None]:
    entry = ENTRY.match(command)
    if entry:
        return "entry", entry.group(1)
    if any(p.match(command) for p in SAFE_COMMANDS):
        return "safe", None
    return "untraced", command


def _shell_of(*levels: dict) -> str:
    for level in levels:
        shell = str(level.get("shell", "") or level.get("defaults", {}).get("run", {}).get("shell", ""))
        if shell:
            return shell
    return ""


def _entry_points(workflow: dict) -> list[str]:
    """Every Python module the run steps execute, with everything else rejected (see the docstring)."""
    modules, untraced = set(), []
    for job_name, job in workflow["jobs"].items():
        for step in job.get("steps", []):
            uses = str(step.get("uses", ""))
            if uses.startswith("."):
                untraced.append(f"{job_name}: local action {uses} can run anything")
            if "run" not in step:
                continue
            shell = _shell_of(step, job, workflow)
            if shell and not SHELL.match(shell):
                untraced.append(f"{job_name}: run step under shell: {shell}")
                continue
            for command in _simple_commands(str(step["run"])):
                kind, value = _classify(command)
                if kind == "entry":
                    modules.add(value)
                elif kind == "untraced":
                    untraced.append(f"{job_name}: {command}")
    assert not untraced, f"copilot-eval.yml runs programs the gate cannot trace: {untraced}"
    assert modules, "copilot-eval.yml runs no `python -m evals.<module>` step"
    return sorted(modules)


def entry_points() -> list[str]:
    return _entry_points(_workflow())


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


def test_run_commands_outside_the_allowlist_are_rejected():
    rejected = (
        'python -c "import scripts.x"', "python - <<'PY'", "python3.11 -m scripts.seed", "python3.11 -m evals.copilot_runner",
        "python -u -m evals.copilot_runner", "PYTHONPATH=. pytest tests/x", "bash scripts/x.sh", "sh -c 'python scripts/x.py'",
        '/usr/bin/python3 -c "import scripts.x"', ".venv/bin/python -m scripts.seed", "./scripts/post.sh", "scripts/post.py",
        "uv run evals/x.py", "source scripts/env.sh", "node scripts/x.js", "ipython -m evals.copilot_runner",
        'python -m evals.copilot_runner --runs 3 && python -c "import scripts.seed"',
        "python -m evals.copilot_runner | python3 scripts/x.py", "python -m evals.copilot_runner; bash x.sh",
        "python -m evals.copilot_runner || ./fallback.sh", "mkdir -p x & python scripts/x.py",
        'python -m evals.copilot_runner --output "$(cat x)"', "python -m evals.copilot_runner `cat x`",
        "python -m evals.copilot_runner $(cat flags)", "tee x.log | python scripts/x.py",
    )
    for line in rejected:
        assert "untraced" in [_classify(c)[0] for c in _simple_commands(line)], line
    accepted = (
        "mkdir -p evals/reports/copilot",
        'python -m evals.copilot_bootstrap --database "$RUNNER_TEMP/copilot-fidelity.db" --output evals/reports/copilot 2>&1 | tee evals/reports/copilot/preparation.log',
        'if [ -f evals/reports/copilot/copilot-eval.md ]; then cat evals/reports/copilot/copilot-eval.md >> "$GITHUB_STEP_SUMMARY"; fi',
        "# a comment\n\npip install -r backend/requirements.txt -r backend/requirements-dev.txt",
    )
    for line in accepted:
        assert all(_classify(c)[0] != "untraced" for c in _simple_commands(line)), line
    assert [_classify(c) for c in _simple_commands("python -m evals.copilot_runner --runs 3 2>&1 | tee x.log")] == [
        ("entry", "evals.copilot_runner"), ("safe", None),
    ]


def test_an_inherited_python_shell_or_a_local_action_is_rejected():
    step = {"run": "python -m evals.copilot_runner"}
    assert _entry_points({"jobs": {"j": {"steps": [step]}}}) == ["evals.copilot_runner"]
    assert _entry_points({"jobs": {"j": {"steps": [{"shell": "bash -e {0}", **step}]}}}) == ["evals.copilot_runner"]
    for workflow in (
        {"jobs": {"j": {"steps": [{"shell": "python {0}", **step}]}}},
        {"jobs": {"j": {"defaults": {"run": {"shell": "python"}}, "steps": [step]}}},
        {"defaults": {"run": {"shell": "python {0}"}}, "jobs": {"j": {"steps": [step]}}},
        {"jobs": {"j": {"steps": [{"shell": "/usr/bin/env python3 {0}", **step}]}}},
        {"jobs": {"j": {"steps": [{"shell": "pwsh", **step}]}}},
        {"jobs": {"j": {"steps": [{"uses": "./.github/actions/seed"}, step]}}},
    ):
        try:
            _entry_points(workflow)
        except AssertionError:
            continue
        raise AssertionError(f"accepted a workflow the gate cannot trace: {workflow}")


def test_closure_follows_every_top_level_backend_name():
    assert {"app", "evals", "tests", "main", "task_worker_main", "scripts"} <= LOCAL_TOP_LEVEL, sorted(LOCAL_TOP_LEVEL)
    files = reachable_files()
    assert len(files) > 50, sorted(files)
    assert "backend/app/services/copilot_service.py" in files
    assert "backend/app/services/edgar/__init__.py" in files
    # Reached only through a relative import inside a package __init__ (app/schemas/__init__.py).
    assert "backend/app/schemas/contact.py" in files
    assert not [f for f in files if f.startswith("backend/tests/")], "the eval must not import test code"
    # The summary-eval modules exempted from the non-trigger list must really be in the closure.
    assert {f"backend/evals/{m}" for m in COPILOT_EVAL_MODULES} <= files


def test_relative_imports_anchor_on_the_owning_package():
    tree = ast.parse("from .contact import ContactSubmissionCreate\nfrom ..utils import numbers\n")
    assert set(_local_imports("app.schemas", True, tree)) >= {"app.schemas.contact", "app.utils", "app.utils.numbers"}
    assert set(_local_imports("app.schemas.summary", False, tree)) >= {"app.schemas.contact", "app.utils"}


def test_every_reachable_module_and_runtime_input_triggers_the_run():
    patterns = workflow_filter()
    closure = reachable_files()
    inputs = runtime_inputs(closure)
    assert len(inputs) > 10, inputs
    missing = sorted(p for p in closure | set(inputs) if not triggers(p, patterns))
    assert not missing, f"copilot-eval.yml paths no longer cover inputs of the eval: {missing}"


def test_files_that_cannot_change_the_result_do_not_trigger_the_run():
    patterns = workflow_filter()
    candidates = non_triggers(reachable_files())
    assert len(candidates) > 100, candidates
    wrong = [p for p in candidates if triggers(p, patterns)]
    assert not wrong, f"copilot-eval.yml would pay for a run these paths cannot affect: {wrong}"


def test_data_directories_follow_their_readers():
    readers = _data_dir_readers()
    assert "backend/app/services/index_membership_service.py" in readers["app/data"]
    assert "backend/app/services/pdf_branding.py" in readers["app/assets"]
    read, unread = _data_dirs_read_by(reachable_files())
    assert sorted(read + unread) == sorted(DATA_DIRS)
    # Today no closure module reads either directory, so both are non-triggers; a closure module
    # that starts reading one moves it into the required inputs and the filter must name it.
    assert read == [], read


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
