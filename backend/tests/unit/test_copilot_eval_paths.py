"""The paid Copilot fidelity run triggers only on files that can change what it measures.

`.github/workflows/copilot-eval.yml` runs `evals.copilot_bootstrap` and `evals.copilot_runner`
against DeepSeek whenever a `pull_request` touching its `paths:` filter is marked ready. The
filter used to be `backend/**`, so a tests-only or docs-only backend change paid for a run that
could not change its result. This gate reads the entry points from the workflow's own run steps,
recomputes their transitive import closure over every top-level package and module under
`backend/` (tests and task_worker_main included, so the eval cannot quietly depend on code the
filter excludes), and fails when a reachable module falls outside the filter (the filter is
stale), when a path that cannot affect the run would trigger it (routers, integrations,
`main.py`, `task_worker_main.py`, the Dockerfile, scripts, migrations, tests, evals Markdown and
the summary-eval modules; files directly under `app/` trigger as a group so a new top-level module
cannot fall outside the filter; a non-trigger the closure starts to import or name is reported as
such), or when a filter pattern matches nothing the eval uses.

The workflow is read as an allowlist, not a denylist, and only its tracked files count (a local
eval run's gitignored reports never turn the gate red). The workflow, each job and each step may
carry only known keys (so a `container:`, `services:` or `strategy:` needs a deliberate entry).
Every simple command of every `run:` step (split on `&&`, `||`, `;`, `|` and `&` outside quotes; a
backslash or a `${` anywhere is refused) must be exactly `python -m evals.<module>` with plain
arguments, run from `backend/` exactly (`python -m` puts the working directory first on
`sys.path`), one of the few fixed shell commands the workflow uses, or an install / env-load command
whose file operands become required inputs below (requirement files are followed through
`-r`/`-c`/`--requirement`/`--constraint` at every depth, and every other line in them must be a
blank, a comment or an exact `name==version` pin, so a local path, a `name @ file:` reference, a
URL or any other option is refused). The shell must be bare `bash`/`sh` (flags and `{0}` only) at
step, job and workflow level; every step `uses:` must be one of three pinned GitHub actions with
only its known `with:` inputs; no job may `uses:` a reusable workflow; `env:` at every level may
set only the keys the workflow is known to use, and the loaded env file only `KEY=value` lines for
its two known keys. The gate guards against drift; a deliberate edit of the workflow is itself in
the filter, pays for one run and is reviewed as a high-tier change.

Runtime-loaded data the closure cannot see is pinned by enumerating the real files: the prompts,
the golden set and sources, every file under the data directories of `app/` (the directories
there without Python: `app/data` and `app/assets` today; they trigger the run whether or not a
closure module reads them, which costs about one run a month), the files the run steps install or
load, the workflow itself, and every tracked non-Python file under `backend/` whose basename a
closure module names in a string literal (so `with_name("baseline_scores.json")`,
`/ "index_membership.json"` or a tests fixture named in the eval's code makes that file a required
input, whatever the path spelling around it, and naming a non-trigger is reported). CLAUDE.md
rule 12.
"""
from __future__ import annotations

import ast
import re
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "backend"
WORKFLOW = ROOT / ".github/workflows/copilot-eval.yml"
# Only tracked files count: a gitignored eval report or a scratch file must never move the gate.
TRACKED = frozenset(
    p for p in subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout.decode().split("\0") if p  # noqa: S603, S607
)
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
# arguments and `2>&1`. No other interpreter spelling, no flag before `-m`, no `(`, backtick or `\`.
ENTRY = re.compile(r"^python -m (evals\.[\w.]+)((?:\s+(?:--[\w-]+|\"[^\"`()\\]*\"|'[^'\\]*'|[\w./$:=-]+|2>&1))*)$")
# Commands whose file operands are inputs of the run: each operand must trigger the run.
INSTALL = re.compile(r"^pip install((?: -r [\w./-]+)+)$")
LOAD_ENV = re.compile(r"^grep -v '[^']*' ([\w./-]+) >> \"\$GITHUB_ENV\"$")
# The fixed shell commands the workflow uses; a new one needs a deliberate entry here.
SAFE_COMMANDS = (
    re.compile(r"^mkdir -p [\w./-]+$"),
    re.compile(r"^tee [\w./-]+$"),
    re.compile(r"^if \[ -f [\w./-]+ \]$"),
    re.compile(r"^then cat [\w./-]+ >> \"\$GITHUB_STEP_SUMMARY\"$"),
    re.compile(r"^fi$"),
)
# A bare shell with flags and the `{0}` script placeholder only; `bash scripts/x.sh {0}` is a program.
SHELL = re.compile(r"^(bash|sh)(?: -[A-Za-z]+)*(?: \{0\})?$")
# The only actions a step may use, pinned to a major version, each with the `with:` inputs it may
# take; a job-level `uses:` (a reusable workflow), a local action, a docker or command-running action
# and a file-naming input (`python-version-file`, checkout's `repository`/`path`) can run or overlay
# code the closure never sees.
ALLOWED_ACTIONS = re.compile(r"^actions/(checkout|setup-python|upload-artifact)@v\d+$")
ALLOWED_INPUTS = {
    "actions/checkout": set(),
    "actions/setup-python": {"python-version"},
    "actions/upload-artifact": {"name", "path", "if-no-files-found", "retention-days"},
}
# The environment the workflow is known to set (job and step `env:`); any other key, above all
# one that runs or redirects code (BASH_ENV, PATH, PYTHONPATH, PIP_*), needs a deliberate entry.
WORKFLOW_ENV = {
    "SKIP_REDIS_INIT", "SECRET_KEY", "STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET", "PWNED_PASSWORD_CHECK_ENABLED",
    "USE_STATEMENT_FINANCIALS", "AI_FALLBACK_MODEL", "AI_FALLBACK_BASE_URL", "OPENAI_API_KEY",
}
# The env file is appended to $GITHUB_ENV verbatim, so only comment, blank and `KEY=value` lines for
# these keys are allowed (a `KEY<<EOF` heredoc or any other key is refused).
ENV_FILE_KEYS = {"AI_DEFAULT_MODEL", "OPENAI_BASE_URL"}
ENV_FILE_LINE = re.compile(r"^(?:\s*(?:#.*)?|([A-Z_][A-Z0-9_]*)=.*)$")
# Requirement-file lines: a nested requirements or constraints file in any pip spelling is traced;
# every other line must be blank, a comment or an exact `name==version` pin (extras and a marker
# allowed), so a local path, a `name @ file:` reference, a URL or any other option is refused.
REQ_NESTED = re.compile(r"^\s*(?:-r|-c|--requirement|--constraint)(?:=|\s+|(?=[^\s=-]))\s*(\S+)")
REQ_PIN = re.compile(r"^\s*[A-Za-z0-9][A-Za-z0-9._-]*(?:\[[A-Za-z0-9,._ -]*\])?==[A-Za-z0-9.*+!-]+(?:\s*;[^#]*)?\s*(?:#.*)?$")
# The keys the workflow, a job and a step may carry; anything else (`container:`, `services:`,
# `strategy:`, a job-level `uses:`) can run or redirect code the closure never sees.
TOP_KEYS = {"name", "on", "permissions", "concurrency", "jobs", "defaults", "env"}
JOB_KEYS = {"name", "if", "runs-on", "timeout-minutes", "env", "steps", "defaults", "permissions"}
STEP_KEYS = {"name", "id", "if", "uses", "with", "run", "shell", "working-directory", "env"}
# `python -m` puts the working directory first on sys.path, so an entry step runs from here exactly.
ENTRY_WORKDIR = "backend"
# Every directory under app/ that holds tracked data rather than Python: always an input of the run.
DATA_DIRS = sorted({
    p.split("/")[2] for p in TRACKED if p.startswith("backend/app/") and p.count("/") >= 3
} & {
    d for d in {p.split("/")[2] for p in TRACKED if p.startswith("backend/app/") and p.count("/") >= 3}
    if not any(p.startswith(f"backend/app/{d}/") and p.endswith(".py") for p in TRACKED)
})
DATA_DIRS = [f"app/{d}" for d in DATA_DIRS]
# Every tracked non-Python file under backend/, keyed by basename, so a string literal naming one
# makes it a required input whatever the path spelling around it.
NAMED_CANDIDATES: dict[str, list[str]] = {}
for _p in sorted(p for p in TRACKED if p.startswith("backend/") and not p.endswith(".py")):
    NAMED_CANDIDATES.setdefault(_p.rsplit("/", 1)[-1], []).append(_p)


def _existing(paths, what: str) -> list[str]:
    """Repo-relative paths; a path that does not exist is an error, never a silent drop."""
    missing = [p for p in paths if not Path(p).is_file()]
    assert not missing, f"{what}: these inputs no longer exist, update the gate: {missing}"
    return sorted(Path(p).relative_to(ROOT).as_posix() for p in paths)


def _glob(pattern: str) -> list[Path]:
    found = [p for p in BACKEND.glob(pattern) if p.is_file() and p.relative_to(ROOT).as_posix() in TRACKED]
    assert found, f"no tracked files match backend/{pattern}; update the gate"
    return found


def _named_in(tree: ast.AST) -> set[str]:
    """Repo-relative paths of candidate files whose basename a string literal in `tree` names."""
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            base = node.value.rsplit("/", 1)[-1]
            found.update(NAMED_CANDIDATES.get(base, []))
    return found


def named_files(closure: set[str]) -> set[str]:
    found: set[str] = set()
    for path in closure:
        found |= _named_in(ast.parse((ROOT / path).read_text(encoding="utf-8")))
    return found


# Loaded at runtime rather than imported, so the closure cannot discover them.
def runtime_inputs(closure: set[str]) -> list[str]:
    return _existing(
        _glob("prompts/*.md") + _glob("evals/copilot_*.json") + [f for d in DATA_DIRS for f in _glob(f"{d}/**/*")]
        + [ROOT / p for p in step_inputs()] + [WORKFLOW] + [ROOT / p for p in named_files(closure)],
        "runtime inputs",
    )


# Must never start the paid run: they cannot change its result. A candidate the closure imports or
# names is reported, so the two lists cannot silently contradict each other.
def non_triggers(closure: set[str]) -> list[str]:
    summary_eval_modules = [
        p for p in _glob("evals/*.py") if not p.name.startswith("copilot_") and p.name not in COPILOT_EVAL_MODULES
    ]
    top_level = [ROOT / p for p in TRACKED if p.startswith("backend/") and p.count("/") == 1 and p not in step_inputs()]
    candidates = _existing(
        _glob("tests/**/*") + _glob("evals/**/*.md") + summary_eval_modules + _glob("scripts/*") + _glob("migrations/*")
        + _glob("app/routers/*.py") + _glob("app/integrations/*.py") + top_level + [BACKEND / "evals/baseline_scores.json"],
        "non-triggers",
    )
    overlap = sorted(set(candidates) & (closure | named_files(closure)))
    assert not overlap, f"the eval now imports or names these non-triggers; they can change its result, so the filter must name them: {overlap}"
    return candidates


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


def _classify(command: str, workdir: str = "") -> tuple[str, object]:
    """("entry", module) | ("install" | "env", [repo-relative files]) | ("safe", None) | ("untraced", command)."""
    entry = ENTRY.match(command)
    if entry:
        return "entry", entry.group(1)
    install, load = INSTALL.match(command), LOAD_ENV.match(command)
    if install or load:
        operands = re.findall(r"-r ([\w./-]+)", install.group(1)) if install else [load.group(1)]
        return ("install" if install else "env"), [(Path(workdir) / p).as_posix() if workdir else p for p in operands]
    if any(p.match(command) for p in SAFE_COMMANDS):
        return "safe", None
    return "untraced", command


def _run_setting(key: str, *levels: dict) -> str:
    """A run setting (`shell`, `working-directory`) from the step, else the job's or the workflow's `defaults.run`."""
    for level in levels:
        value = str(level.get(key, "") or level.get("defaults", {}).get("run", {}).get(key, ""))
        if value:
            return value
    return ""


def _unknown_keys(obj: dict, allowed: set[str], where: str) -> list[str]:
    unknown = sorted(str(k) for k in obj if str(k) not in allowed)
    return [f"{where} carries keys the gate does not know: {unknown}"] if unknown else []


def _env_problems(scope: dict, where: str) -> list[str]:
    env = scope.get("env", None)
    if env is None:
        return []
    if not isinstance(env, dict):
        return [f"{where}: env is not a mapping ({str(env)[:40]!r})"]
    unknown = sorted(k for k in env if str(k) not in WORKFLOW_ENV)
    return [f"{where}: env sets keys the gate does not know: {unknown}"] if unknown else []


def _file(path: str) -> Path:
    return Path(path) if Path(path).is_absolute() else ROOT / path


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path.as_posix()


def _requirement_inputs(path: str) -> tuple[list[str], list[str]]:
    """(every requirements/constraints file `path` pulls in, at any depth; problems found)."""
    seen, problems, stack = [], [], [path]
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.append(current)
        file = _file(current)
        if not file.is_file():
            continue
        for line in file.read_text(encoding="utf-8").splitlines():
            nested = REQ_NESTED.match(line)
            if nested:
                stack.append(_rel((file.parent / nested.group(1)).resolve()))
            elif line.strip() and not line.lstrip().startswith("#") and not REQ_PIN.match(line):
                problems.append(f"{current}: {line.strip()[:60]}")
    return seen[1:], problems


def _env_file_problems(path: str) -> list[str]:
    file = _file(path)
    if not file.is_file():
        return []
    problems = []
    for line in file.read_text(encoding="utf-8").splitlines():
        m = ENV_FILE_LINE.match(line)
        if not m or (m.group(1) and m.group(1) not in ENV_FILE_KEYS):
            problems.append(f"{path}: {line.strip()[:60]}")
    return problems


def _read_steps(workflow: dict) -> tuple[list[str], list[str]]:
    """(modules the run steps execute, files they install or load), with everything else rejected."""
    modules, requirement_files, env_files, untraced = set(), set(), set(), []
    untraced += _unknown_keys(workflow, TOP_KEYS, "workflow") + _env_problems(workflow, "workflow")
    for job_name, job in workflow["jobs"].items():
        untraced += _unknown_keys(job, JOB_KEYS, f"{job_name} job") + _env_problems(job, f"{job_name} job")
        for step in job.get("steps", []):
            untraced += _unknown_keys(step, STEP_KEYS, f"{job_name} step") + _env_problems(step, f"{job_name} step")
            uses = str(step.get("uses", ""))
            if uses and not ALLOWED_ACTIONS.match(uses):
                untraced.append(f"{job_name}: action {uses} is not one of the allowed actions")
            elif uses:
                extra = sorted(set(step.get("with", {})) - ALLOWED_INPUTS[uses.split("@")[0]])
                if extra:
                    untraced.append(f"{job_name}: action {uses} takes inputs the gate does not know: {extra}")
            if "run" not in step:
                continue
            shell = _run_setting("shell", step, job, workflow)
            if shell and not SHELL.match(shell):
                untraced.append(f"{job_name}: run step under shell: {shell}")
                continue
            workdir = _run_setting("working-directory", step, job, workflow)
            run = str(step["run"])
            if "\\" in run or "${" in run or "${" in workdir:
                untraced.append(f"{job_name}: a backslash or `${{` in a run step can change what bash runs: {run.strip()[:60]}")
                continue
            for command in _simple_commands(run):
                kind, value = _classify(command, workdir)
                if kind == "entry" and workdir != ENTRY_WORKDIR:
                    untraced.append(f"{job_name}: `{command}` runs from {workdir or '.'!r}, not {ENTRY_WORKDIR!r}; python -m would import from there first")
                elif kind == "entry":
                    modules.add(value)
                elif kind == "install":
                    requirement_files.update(value)
                elif kind == "env":
                    env_files.update(value)
                elif kind == "untraced":
                    untraced.append(f"{job_name}: {command}")
    for path in sorted(requirement_files):
        nested, problems = _requirement_inputs(path)
        requirement_files.update(nested)
        untraced += problems
    for path in sorted(env_files):
        untraced += _env_file_problems(path)
    assert not untraced, f"copilot-eval.yml runs programs the gate cannot trace: {untraced}"
    assert modules, "copilot-eval.yml runs no `python -m evals.<module>` step"
    return sorted(modules), sorted(requirement_files | env_files)


def entry_points() -> list[str]:
    return _read_steps(_workflow())[0]


def step_inputs() -> list[str]:
    return _read_steps(_workflow())[1]


def reachable_files(roots=None) -> set[str]:
    """Repo-relative paths of every local module the entry points import, transitively."""
    seen: set[str] = set()
    stack = list(roots or entry_points())
    # `python -m pkg` runs pkg/__main__.py as well as the package's __init__.
    stack += [f"{m}.__main__" for m in list(stack)]
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


def test_entry_points_and_inputs_come_from_the_workflow_run_steps():
    assert entry_points() == EXPECTED_ENTRY_POINTS
    assert step_inputs() == [".github/ai-model.env", "backend/requirements-dev.txt", "backend/requirements.txt"]


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
        "pip install requests", "pip install -e backend", "pip install -r backend/requirements.txt -e .",
        "grep -v '^#' x.env | bash", "cat x.env >> \"$GITHUB_ENV\"",
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
    # Install and env-load operands become required inputs, resolved against the step's working directory.
    assert _classify("pip install -r backend/requirements.txt -r backend/requirements-eval.txt") == (
        "install", ["backend/requirements.txt", "backend/requirements-eval.txt"],
    )
    assert _classify("pip install -r requirements.txt", "backend") == ("install", ["backend/requirements.txt"])
    assert _classify("grep -v '^#' .github/ai-model.env >> \"$GITHUB_ENV\"") == ("env", [".github/ai-model.env"])


def test_an_untraceable_shell_action_env_or_job_is_rejected():
    step = {"run": "python -m evals.copilot_runner", "working-directory": "backend"}
    checkout = {"uses": "actions/checkout@v7"}
    assert _read_steps({"jobs": {"j": {"steps": [checkout, step]}}}) == (["evals.copilot_runner"], [])
    assert _read_steps({"jobs": {"j": {"steps": [{"shell": "bash -e {0}", **step}]}}})[0] == ["evals.copilot_runner"]
    assert _read_steps({"jobs": {"j": {"steps": [{"shell": "sh", **step}]}}})[0] == ["evals.copilot_runner"]
    assert _read_steps({"jobs": {"j": {"defaults": {"run": {"working-directory": "backend"}}, "steps": [{"run": "python -m evals.copilot_runner"}]}}})[0] == ["evals.copilot_runner"]
    assert _read_steps({"jobs": {"j": {"env": {"SECRET_KEY": "x"}, "steps": [{"uses": "actions/setup-python@v7", "with": {"python-version": "3.11"}}, {"env": {"OPENAI_API_KEY": "k"}, **step}]}}})[0] == ["evals.copilot_runner"]
    for workflow in (
        {"jobs": {"j": {"steps": [{"run": "python -m evals.copilot_runner"}]}}},
        {"jobs": {"j": {"steps": [{"run": "python -m evals.copilot_runner", "working-directory": "backend/scripts"}]}}},
        {"jobs": {"j": {"defaults": {"run": {"working-directory": "backend/tests"}}, "steps": [{"run": "python -m evals.copilot_runner"}]}}},
        {"jobs": {"j": {"steps": [{"run": "python -m evals.copilot_runner", "working-directory": "${{ vars.EVAL_DIR }}"}]}}},
        {"jobs": {"j": {"container": {"image": "python:3.11", "env": {"PYTHONPATH": "scripts"}}, "steps": [step]}}},
        {"jobs": {"j": {"services": {"db": {"image": "postgres"}}, "steps": [step]}}},
        {"jobs": {"j": {"strategy": {"matrix": {"x": [1]}}, "steps": [step]}}},
        {"jobs": {"j": {"steps": [{"continue-on-error": "true", **step}]}}},
        {"on": "pull_request", "jobs": {"j": {"steps": [step]}}, "run-name": "x"},
        {"jobs": {"j": {"steps": [{"shell": "python {0}", **step}]}}},
        {"jobs": {"j": {"defaults": {"run": {"shell": "python"}}, "steps": [step]}}},
        {"defaults": {"run": {"shell": "python {0}"}}, "jobs": {"j": {"steps": [step]}}},
        {"jobs": {"j": {"steps": [{"shell": "/usr/bin/env python3 {0}", **step}]}}},
        {"jobs": {"j": {"steps": [{"shell": "pwsh", **step}]}}},
        {"jobs": {"j": {"steps": [{"shell": "bash scripts/wrapper.sh {0}", **step}]}}},
        {"jobs": {"j": {"steps": [{"shell": "bash -c 'python scripts/x.py' _ {0}", **step}]}}},
        {"jobs": {"j": {"steps": [{"uses": "./.github/actions/seed"}, step]}}},
        {"jobs": {"j": {"steps": [{"uses": "docker://python:3.11", "with": {"args": "scripts/x.py"}}, step]}}},
        {"jobs": {"j": {"steps": [{"uses": "nick-fields/retry@v3", "with": {"command": "python scripts/x.py"}}, step]}}},
        {"jobs": {"j": {"steps": [{"uses": "actions/github-script@v7", "with": {"script": "x"}}, step]}}},
        {"jobs": {"j": {"steps": [{"uses": "actions/checkout@main"}, step]}}},
        {"jobs": {"j": {"steps": [step]}, "k": {"uses": "./.github/workflows/extra.yml"}}},
        {"jobs": {"j": {"steps": [{"run": 'python -m evals.copilot_runner --x "a\\"; bash x.sh"'}]}}},
        {"jobs": {"j": {"steps": [{"run": 'python -m evals.copilot_runner --output "${{ vars.COPILOT_OUT }}"'}]}}},
        {"jobs": {"j": {"steps": [{"run": 'python -m evals.copilot_runner --output "${X@P}"'}]}}},
        {"env": {"BASH_ENV": "scripts/ci_env.sh"}, "jobs": {"j": {"steps": [step]}}},
        {"jobs": {"j": {"env": {"PYTHONPATH": "backend/scripts"}, "steps": [step]}}},
        {"jobs": {"j": {"env": {"PATH": "backend/scripts/bin:/usr/bin"}, "steps": [step]}}},
        {"jobs": {"j": {"env": {"PIP_EDITABLE": "backend/scripts/pkg"}, "steps": [step]}}},
        {"jobs": {"j": {"env": {"HOME": "/tmp/x"}, "steps": [step]}}},
        {"jobs": {"j": {"env": "${{ fromJSON(vars.E) }}", "steps": [step]}}},
        {"jobs": {"j": {"steps": [{"env": {"bash_env": "x.sh"}, **step}]}}},
        {"jobs": {"j": {"steps": [{"uses": "actions/setup-python@v7", "with": {"python-version-file": ".python-version"}}, step]}}},
        {"jobs": {"j": {"steps": [{"uses": "actions/checkout@v7", "with": {"repository": "x/y", "path": "z"}}, step]}}},
    ):
        try:
            _read_steps(workflow)
        except AssertionError:
            continue
        raise AssertionError(f"accepted a workflow the gate cannot trace: {workflow}")


def test_requirement_and_env_files_are_traced(tmp_path):
    base = tmp_path
    (base / "a.txt").write_text("requests==1\n-r b.txt\n")
    (base / "b.txt").write_text("--requirement=c.txt\n-cd.txt\n")
    (base / "c.txt").write_text("--constraint d.txt\nnumpy==1  # pinned\nfoo[extra]==2; python_version < '3.12'\n")
    (base / "d.txt").write_text("numpy==1\n")
    nested, problems = _requirement_inputs(str(base / "a.txt"))
    assert sorted(nested) == [str(base / "b.txt"), str(base / "c.txt"), str(base / "d.txt")] and problems == []
    (base / "e.txt").write_text(
        "-e ../local-pkg\n./vendored\ngit+https://x/y.git\n--index-url https://x\nhttps://x/y.whl\nbackend/scripts/vendored_pkg\n"
        "pkg @ file:///x/pkg\n${GITHUB_WORKSPACE}/backend/scripts/pkg\ndist/pkg-1.0-py3-none-any.whl\nrequests>=1\nrequests\nrequests==1\n"
    )
    assert len(_requirement_inputs(str(base / "e.txt"))[1]) == 11
    (base / "ok.env").write_text("# c\n\nAI_DEFAULT_MODEL=x\nOPENAI_BASE_URL=y\n")
    assert _env_file_problems(str(base / "ok.env")) == []
    (base / "bad.env").write_text("AI_DEFAULT_MODEL=x\nPYTHONPATH<<EOF\nbackend/scripts\nEOF\nFOO=1\n")
    assert len(_env_file_problems(str(base / "bad.env"))) == 4
    # An env file is checked as an env file whatever its name, because the command decides.
    (base / "model.txt").write_text("PYTHONPATH=backend/scripts\n")
    wf = {"jobs": {"j": {"steps": [
        {"run": f"grep -v '^#' {base.as_posix()}/model.txt >> \"$GITHUB_ENV\""},
        {"run": "python -m evals.copilot_runner", "working-directory": "backend"},
    ]}}}
    try:
        _read_steps(wf)
    except AssertionError as e:
        assert "PYTHONPATH" in str(e)
    else:
        raise AssertionError("an env file named .txt escaped the env-file check")
    assert _requirement_inputs("backend/requirements.txt") == ([], [])
    assert _requirement_inputs("backend/requirements-dev.txt") == ([], [])
    assert _env_file_problems(".github/ai-model.env") == []


def test_closure_follows_every_top_level_backend_name():
    assert {"app", "evals", "tests", "main", "task_worker_main", "scripts"} <= LOCAL_TOP_LEVEL, sorted(LOCAL_TOP_LEVEL)
    files = reachable_files()
    assert len(files) > 50, sorted(files)
    assert "backend/app/services/copilot_service.py" in files
    assert "backend/app/services/edgar/__init__.py" in files
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


def test_data_directories_and_named_files_are_inputs():
    assert DATA_DIRS == ["app/assets", "app/data"], f"a new data directory under app/ joins the filter: {DATA_DIRS}"
    # The reports the eval writes locally are gitignored, so they can never become candidates.
    assert "backend/evals/copilot_runner.py" in TRACKED
    assert [p for p in TRACKED if p.startswith("backend/evals/reports/")] == ["backend/evals/reports/.gitignore"]
    # A string literal naming a candidate file makes it an input, whatever the path spelling around it.
    for source in (
        'BASELINE = Path(__file__).with_name("baseline_scores.json")',
        'p = os.path.join(\n    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "evals", "baseline_scores.json"\n)',
        'p = "../evals/baseline_scores.json"', "p = f'{base}/baseline_scores.json'",
    ):
        assert _named_in(ast.parse(source)) == {"backend/evals/baseline_scores.json"}, source
    assert _named_in(ast.parse('x = "baseline"; y = "scores.json"; z = "metadata"')) == set()
    # A gitignored report the eval writes and names (`copilot-eval.json`) is not a candidate.
    assert _named_in(ast.parse('out = output / "copilot-eval.json"')) == set()
    # A tests fixture named by a closure module would be reported, because every tracked file counts.
    fixture = next(
        p for p in sorted(TRACKED)
        if p.startswith("backend/tests/fixtures/") and not p.endswith(".py") and len(NAMED_CANDIDATES[p.rsplit("/", 1)[-1]]) == 1
    )
    assert _named_in(ast.parse(f'f = Path("{fixture}")')) == {fixture}
    closure = reachable_files()
    assert "backend/evals/copilot_golden_set.json" in named_files(closure)


def test_every_filter_pattern_matches_an_input_of_the_eval():
    closure = reachable_files()
    used = closure | set(runtime_inputs(closure))
    idle = [raw for raw in workflow_filter() if not raw.startswith("!") and not any(_pattern(raw).match(p) for p in used)]
    assert not idle, f"copilot-eval.yml paths that match nothing the eval uses would pay for runs that cannot change its result: {idle}"


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
