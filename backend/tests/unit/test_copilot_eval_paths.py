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
cannot fall outside the filter; a non-trigger of a deliberate category the closure starts to import
or name is reported as such, while a named file of a catch-all category becomes an input), or when
a filter pattern matches nothing the eval uses.

The workflow is read as an allowlist, not a denylist (its `on:` block included: pull_request with
types and paths, nothing else), and only tracked files count anywhere: the import walk resolves
modules against `git ls-files`, so a gitignored eval report or an untracked package that shadows an
installed import never moves the gate (a tracked top-level file under `backend/` that shadows a package
only third-party code imports, `backend/certifi.py`, is a stated limit: the walk follows the eval's own
imports). Every argument of an entry command that is not a flag or an
integer is a path (quotes are removed first, as bash removes them, so a quoted `"--opt=value"` is
split like a bare one): a tracked file or directory is an input of the run, a gitignored path or one
under `$RUNNER_TEMP` followed by a plain path is run-local, anything else with a `$` in it is untraced
(a single-quoted argument is literal to bash, so its `$` names a directory, never a variable).
Named-file detection covers every tracked file and directory: a literal is normalised (`a/../b` is
`b`; a `sqlite:///` or `sqlite+<driver>:///` prefix is dropped, any other URL is skipped) and its segments must
end the tracked path. A bare name reaches only `backend/` files, where the run works, so a same-named
copy elsewhere (a font the frontend also ships, an evidence copy of a report under `tasks/`) cannot
turn the gate red, and it never names a directory (`app`, `unit` and `support` occur as ordinary
words), except that in an eval module a literal that builds a path from the module's own location
(`Path(__file__).with_name("questions")`, `Path(__file__).parent / "questions"`, a `Path(dir, "questions")`
constructor or a `join` on that directory, a keyword argument or an f-string part included; the receiver
must be the module file or its directory, written as `Path(__file__).parent`, `parents[0]`,
`os.path.dirname(__file__)` or a name assigned from one of them, by a plain, an annotated, a walrus or a
tuple assignment; the module file
may itself be held in a name (`THIS = Path(__file__).resolve(); THIS.parent / "x"`) and the directory
wrapped in `abspath`, `realpath`, `str`, `os.fspath` or a `Path(...)` constructor, the module file likewise; the
string an expression builds is folded once, as Python builds it, over `+` and `+=`, an f-string, a `%` or `.format`
template, `sep.join([...])`, `os.path.join`, `Path(...)`, `joinpath`, `/` and `with_name`, with `os.sep`, `os.path.sep`
or a `sep` imported from `os` a slash, so `dirname(__file__) + "/*.json"`, `dir + "/" + "*.json"`, `f"{dir}{os.sep}*.json"`,
`"%s/*.json" % dir`, `"{}/*.json".format(dir)`, `os.sep.join([dir, "*.json"])` and `join(dir, "") + "*.json"` all read
`*.json` beside the module; a name assigned the directory with a separator after it (`dir + "/"`, `f"{dir}{os.sep}"`,
`p += os.sep`) is the directory and a literal glued to it needs no slash, `p += "/x"` on the directory name reads `x`
beside the module and leaves `p` mixed, while a suffix without a slash, `dirname(__file__) +
"_backup"`, is another directory and names nothing; so `REPORTS_DIR.joinpath("x")` or
`parents[1] / "x"` names nothing) also names a folder directly beside the module, and a `..` path
anchored there resolves there (`../assets` from `app/services/` is `app/assets`, not every `assets`
directory in the repository), while `iterdir()`, `listdir` or `scandir` of the module's directory
reads what `glob("*")` reads and `walk()` on it or `os.walk` of it what `rglob("*")` reads; `rglob(p)` is `glob("**/" + p)`, and a leading `**` is stripped and remembered, so
`glob("**/name")` is the bare name `name`, except on the module's own directory, where `rglob("name")` or
`glob("**/name")` is every `name` below it and everything under one, as `join(dir, "**", "name")` is; a
glob names the directory before its first pattern
segment (`dir/*.md` spells `dir`, wherever the literal sits and whatever the receiver; the directory
is matched at any depth already, so `**/dir/*.md` is the same read) and the files its pattern matches
there, segment by segment, `**` at any depth; a bare pattern such as `*.md` counts only on the
module's own directory (`Path(__file__).parent.glob("*.md")`), one level for `glob` and every level
for `rglob` or a leading `**`, and a leading `..` climbs that many directories above the module
(`glob("../*.txt")` reads `backend/*.txt`; `rglob("../p")` is
read as the climb and then every `p` below it, more than pathlib's `**/../p` reads, and the excess
is loud, never silent), so
`REPORTS_DIR.glob("*.json")` on the run's report directory is not seen; a folder name held in a variable first (`NAME = "questions"; with_name(NAME)`) is a bare
word to this gate and is not seen, the same limit as a path spelled one segment per literal on another receiver; a path of
two or more segments names files and
directories, prefers `backend/` and otherwise reaches the whole repository
(`Path(__file__).resolve().parents[2]` is the repository root); a path with a leading `..` reaches
it unconditionally, unless it is anchored on the module's own location, where it resolves there
(a lone `..` or `.` so anchored names nothing; a lone `**` so anchored reads what `rglob("*")` reads).
A literal joined to the module's own location by `/`, `with_name`, `join`, `joinpath` or a `Path(...)`
constructor is read where Python reads it (`dir / "README.md"` is the file beside the module, not every
`README.md`), the constant operands of a `join`, a `joinpath` or a constructor, up to its first other
operand, are the one path they build (`join(dir, "baselines", "*.json")` reads `baselines/*.json` there,
and `join(dir, "baselines", "../../app/config.py")` is `../app/config.py` from it), and the literals
after a name or an f-string with a formatted value (`join(dir, sub, "*.json")`) are bare words, the limit of a
variable; a leading `**` in such a path is read at every depth below the module's directory, as a `..` before
it climbs first (`join(dir, "**", "routers")` is every `routers` below it and everything under one;
`join(dir, "..", "**", "baselines", "*.json")` is every `baselines/*.json` below the parent). A name assigned
the module's directory anchors a literal wherever the name is used; where it is also bound to something else
(a parameter, a loop target, `parents[1]` in another function), the literal is read both anchored and as
spelled, since the anchored reading alone could resolve to a path beside the module that does not exist and
go unseen, and the spelled reading alone would lose a bare pattern or a listing on it. A named directory means every tracked file under it but a `.gitignore`. A path spelled one segment per literal
on another receiver (`ROOT / "docs" / "x.md"`) is a bare name each: that is the limit of per-literal matching;
on the module's own directory a `/` chain is the one path it builds. A `.py`
named by path (run by subprocess) is a named file and a module of the closure, so its imports are
followed (a bare `.py` name such as `__init__.py` matches every backend file so named, loudly), and
a dotted module name in a string literal that resolves to a local module joins the closure. The
workflow, each job and each step may
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
its two known keys, column-0 comments and empty lines. The gate guards against drift; a deliberate edit of the workflow is itself in
the filter, pays for one run and is reviewed as a high-risk workflow change: three lenses and two refutation
attempts per blocker or should-fix finding, the review AGENTS.md §5 describes.

Runtime-loaded data the closure cannot see is pinned by enumerating the real files: the prompts,
the golden set and sources, every file under the data directories of `app/` (the directories
there without Python: `app/data` and `app/assets` today; they trigger the run whether or not a
closure module reads them, which costs about one run a month), the files the run steps install or
load, the workflow itself, and every tracked file a closure module names in a string literal under
the rules above (so `with_name("baseline_scores.json")`, `/ "index_membership.json"` or a tests
fixture named in the eval's code makes that file a required input, and naming a deliberate
non-trigger is reported; the artifacts the run writes are exempt only as bare names in `evals/` modules, so a
literal that spells a directory to one of those names points at a committed file and is matched).
Every tracked file under `evals/` is a trigger, a module, Markdown or listed summary-eval data, so a
new data file or directory there is classified deliberately (the filter's `copilot_*` does not cross
a `/`). The non-triggers are of two kinds: the deliberate categories (tests, scripts, migrations,
routers, integrations, top-level files, the summary eval's modules and data), where the eval
importing or naming a file is reported and only dropping the dependency or reclassifying the file
here clears it; and the catch-alls (Markdown under `evals/`, everything outside `backend/` that the
run does not load), where a file the eval names is an input the filter must cover, so the right
filter entry clears the gate. CLAUDE.md rule 12.
"""
from __future__ import annotations

import ast
import fnmatch
import itertools
import posixpath
import re
import string
import subprocess
import sys
from collections import Counter
from typing import NamedTuple
from pathlib import Path
from unittest import mock

import yaml

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "backend"
WORKFLOW = ROOT / ".github/workflows/copilot-eval.yml"
# Only tracked files count: a gitignored eval report or a scratch file must never move the gate.
GIT_PROBLEMS: list[str] = []


def _tracked() -> frozenset[str]:
    try:
        listing = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True)  # noqa: S603, S607
    except (OSError, subprocess.CalledProcessError) as exc:  # a collection error would stop the whole suite
        GIT_PROBLEMS.append(f"git ls-files failed: {exc}")
        return frozenset()
    return frozenset(p for p in listing.stdout.decode().split("\0") if p)


TRACKED = _tracked()
# Tracked Python under backend/, relative to it; the import walk never consults the working tree.
TRACKED_PY = frozenset(p[len("backend/"):] for p in TRACKED if p.startswith("backend/") and p.endswith(".py"))
# Every top-level importable name under backend/: modules, packages and namespace packages (any
# non-hidden directory holding Python at any depth), so no local import is ever dropped as "not local".
LOCAL_TOP_LEVEL = frozenset(
    {p[: -len(".py")] for p in TRACKED_PY if "/" not in p}
    | {p.split("/", 1)[0] for p in TRACKED_PY if "/" in p and not p.startswith(".")}
)
EXPECTED_ENTRY_POINTS = ["evals.copilot_bootstrap", "evals.copilot_runner"]
# Summary-eval modules the copilot modules import; they must stay in the closure to keep triggering.
COPILOT_EVAL_MODULES = {"__init__.py", "schema.py", "scorers.py"}
# Run text is printable ASCII, tab and newline only: a `\v#` reads as a comment to a line splitter and
# as a command to bash, and so does a no-break space before `#`, which Python's strip() removes.
NON_ASCII = re.compile("[^\x20-\x7e\t\n]")
# The only entry form: the bare interpreter, `-m evals.<module>`, then flags, quoted or bare
# arguments and `2>&1`. No other interpreter spelling, no flag before `-m`, no `(`, backtick or `\`.
ENTRY = re.compile(r"^python -m (evals\.[\w.]+)((?:\s+(?:--[\w-]+|\"[^\"`()\\]*\"|'[^'\\]*'|[\w./$:=-]+|2>&1))*)$")
# Commands whose file operands are inputs of the run: each operand must trigger the run.
# Every argument of an entry command is a path unless it is a flag or an integer (`--runs 3`), and a
# `--opt=value` is split at its `=` as argparse reads it, after its quotes are removed as bash removes
# them. The run may read a path, so it must be a tracked file or directory (then an input of the run),
# gitignored (the run writes it) or under `$RUNNER_TEMP` followed by a plain path (no `$`, no `..`);
# anything else with a `$` in it, a flag such as `--preparation$X` included, is untraced. Only an
# unquoted or double-quoted `$` expands: a single-quoted `'$RUNNER_TEMP/x'` is the literal path
# `$RUNNER_TEMP/x` to bash, traced as such. An empty argument is the working directory, as `Path("")`
# reads it; a directory argument means every tracked file under it but a `.gitignore`.
INTEGER = re.compile(r"^\d+$")
# A dotted name in a string literal with a local head joins the closure like an import statement: the longest
# prefix of two or more segments that is a local module (`importlib.import_module("app.x")`; `mock.patch("app.x.Class.method")`
# and `pkgutil.resolve_name("app.x:Class")` import `app.x`; a lazy loader). A bare top-level package is never a
# find: every parent package is in the closure already, and `"app.state"` names nothing.
DOTTED = re.compile(r"^[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+(?::[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)?$")
# A flag of an entry command: `--name`, or `--name=value` with the value checked as a path.
FLAG = re.compile(r"^--[\w-]+$")
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
# setup-python without a literal version reads the repository's `.python-version`, outside the filter.
PYTHON_VERSION = re.compile(r"^\d+(?:\.\d+){1,2}$")
# The environment the workflow is known to set (job and step `env:`); any other key, above all
# one that runs or redirects code (BASH_ENV, PATH, PYTHONPATH, PIP_*), needs a deliberate entry.
WORKFLOW_ENV = {
    "SKIP_REDIS_INIT", "SECRET_KEY", "STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET", "PWNED_PASSWORD_CHECK_ENABLED",
    "USE_STATEMENT_FINANCIALS", "AI_FALLBACK_MODEL", "AI_FALLBACK_BASE_URL", "OPENAI_API_KEY",
}
# The env file is appended to $GITHUB_ENV through `grep -v '^#'`, so only column-0 comments, empty
# lines and `KEY=value` lines for these keys are allowed (an indented comment or a blank line would
# reach the runner's env-file parser; a `KEY<<EOF` heredoc or any other key is refused).
ENV_FILE_KEYS = {"AI_DEFAULT_MODEL", "OPENAI_BASE_URL"}
ENV_FILE_LINE = re.compile(r"^(?:#.*|([A-Z_][A-Z0-9_]*)=.*|)$")
# Requirement-file lines: a nested requirements or constraints file in any pip spelling is traced;
# every other line must be blank, a comment or an exact `name==version` pin (a PEP 440 version, extras
# and a marker allowed; no `1.*` wildcard, no `1.tar.gz` and no `1+a.zip` local label, which pip installs
# as a local archive; a `#` starts a comment only after whitespace, as pip reads it, so `foo==1#.zip` is
# the archive `foo==1#.zip`), so a local path, a `name @ file:` reference, a URL or any other option is refused.
REQ_NESTED = re.compile(r"^\s*(?:(?:-r|-c)\s*|(?:--requirement|--constraint)(?:=|\s+))(\S+)(?:\s+#.*)?\s*$")
REQ_PIN = re.compile(
    r"^\s*[A-Za-z0-9][A-Za-z0-9._-]*(?:\[[A-Za-z0-9,._ -]*\])?=="
    r"\d+(?:\.\d+)*(?:(?:a|b|rc)\d+)?(?:\.post\d+)?(?:\.dev\d+)?"
    r"(?:\s*;[^#]*)?\s*(?:(?<=\s)#.*)?$"
)
# The keys the workflow, a job and a step may carry; anything else (`container:`, `services:`,
# `strategy:`, a job-level `uses:`) can run or redirect code the closure never sees.
TOP_KEYS = {"name", "on", "permissions", "concurrency", "jobs", "defaults", "env"}
# The only event is pull_request, with its types and the paths filter; another event (or a second
# pull_request-shaped one such as pull_request_target) would start the paid run outside the filter.
ON_KEYS = {"types", "paths"}
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
# Every tracked file and directory (stored with a trailing `/`) in the repository, keyed by last
# segment, so a string literal naming one makes it (or every tracked file under it) a required input (a non-trigger so named is reported,
# a `.py` run by path included). The literal is normalised and its segments must end the tracked path.
# A bare name reaches only `backend/` files, where the run works: a copy of the same name elsewhere in
# the repository is not what the run reads, so it cannot turn the gate red, and a bare directory name
# is an ordinary word too often (`app`, `unit`, `support` occur in the closure today). A path of two or
# more segments names files and directories, prefers `backend/` and otherwise reaches the whole
# repository (eval modules anchor on the repository root through `parents[2]`), and a path with a
# leading `..` reaches it unconditionally. A URL's last segment is not a name (a `sqlite:///` or
# `sqlite+<driver>:///` prefix is dropped first, since a relative SQLite URL names a local file), and neither is a bare artifact name the run writes under its
# output directory (and may read back there: `evals/copilot_bootstrap`) in a module under `evals/`;
# a path to such a name is a committed file. Each artifact name must still occur in the closure.
RUN_ARTIFACTS = frozenset({
    "filing.html", "xbrl.json", "sections.json", "excerpt.txt", "preparation.json", "prepared-source.db", "copilot-eval.json", "copilot-eval.md",
})
LOCAL_URL = re.compile(r"^sqlite(?:\+\w+)?:///")
GLOB = re.compile(r"[*?\[]")  # `dir/*.md` names the directory `dir`; a pattern segment itself names nothing
NAMED_CANDIDATES: dict[str, list[str]] = {}
NAMED_DIRS: dict[str, list[str]] = {}
for _p in sorted(TRACKED):
    _parts = _p.split("/")
    NAMED_CANDIDATES.setdefault(_parts[-1], []).append(_p)
    for _i in range(1, len(_parts)):
        _d = "/".join(_parts[:_i]) + "/"
        if _d not in NAMED_DIRS.get(_parts[_i - 1], []):
            NAMED_DIRS.setdefault(_parts[_i - 1], []).append(_d)
# Summary-eval data under evals/ that the Copilot run never reads. Every other tracked file under
# evals/ is a trigger, a module, Markdown or listed here, so a new data file or directory there (a
# `copilot_questions/` the filter's `copilot_*` would not reach, since `*` does not cross `/`) is
# classified deliberately: a Copilot input joins the filter, summary-eval data joins this list.
SUMMARY_EVAL_DATA = ["evals/baseline_scores.json", "evals/golden_set.json", "evals/weekly_cohort.json", "evals/reports/.gitignore"]


def _existing(paths, what: str) -> list[str]:
    """Repo-relative paths; a path that does not exist is an error, never a silent drop."""
    missing = [p for p in paths if not Path(p).is_file()]
    assert not missing, f"{what}: these inputs no longer exist, update the gate: {missing}"
    return sorted(Path(p).relative_to(ROOT).as_posix() for p in paths)


def _glob(pattern: str) -> list[Path]:
    found = [p for p in BACKEND.glob(pattern) if p.is_file() and p.relative_to(ROOT).as_posix() in TRACKED]
    assert found, f"no tracked files match backend/{pattern}; update the gate"
    return found


def _add_chain(node: ast.AST) -> list[ast.AST]:
    """The operands of a left-to-right `+` chain (`a + b + c` is `(a + b) + c`), or `[node]`."""
    operands = [node]
    while isinstance(operands[0], ast.BinOp) and isinstance(operands[0].op, ast.Add):
        operands[0:1] = [operands[0].left, operands[0].right]
    return operands


def _recursive_literals(tree: ast.AST) -> set[int]:
    """ids of the string constants (an f-string's parts included) passed to any `rglob(...)`, positional or
    `pattern=`: `rglob(p)` is `glob("**/" + p)`."""
    return {
        id(part) for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "rglob"
        for a in node.args + [keyword.value for keyword in node.keywords]
        for part in (a.values if isinstance(a, ast.JoinedStr) else [a]) if isinstance(part, ast.Constant)
    }


def _glob_matches(directory: str, pattern: list[str], recursive: bool) -> set[str]:
    """Tracked files under `directory` whose relative path matches `pattern` segment by segment (`fnmatch`); `**`
    matches any run of segments and `recursive` prefixes one, so `glob("*.md")` is one level and `rglob` every level."""
    def matches(parts: list[str], pat: list[str]) -> bool:
        if not pat:
            return not parts
        if pat[0] == "**":
            return any(matches(parts[i:], pat[1:]) for i in range(len(parts) + 1))
        return bool(parts) and fnmatch.fnmatchcase(parts[0], pat[0]) and matches(parts[1:], pat[1:])
    pat = (["**"] if recursive else []) + pattern
    return {p for p in TRACKED if p.startswith(directory) and not p.endswith("/.gitignore") and matches(p[len(directory):].split("/"), pat)}


def _bindings(tree: ast.AST) -> Counter[str]:
    """How many times each name is bound anywhere in the module: an assignment target of any kind (a loop, `with`,
    comprehension or walrus target included), a parameter, an import, a `def`, a `class`, an `except ... as` or a
    `match` capture."""
    bound: Counter[str] = Counter()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            bound[node.id] += 1
        elif isinstance(node, ast.arg):
            bound[node.arg] += 1
        elif isinstance(node, ast.alias):
            bound[(node.asname or node.name).split(".")[0]] += 1
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound[node.name] += 1
        elif isinstance(node, ast.ExceptHandler) and node.name:
            bound[node.name] += 1
        elif isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name:
            bound[node.name] += 1
        elif isinstance(node, ast.MatchMapping) and node.rest:
            bound[node.rest] += 1
    return bound


def _assigned(tree: ast.AST) -> list[tuple[ast.Name, ast.AST]]:
    """(name, value) for every plain, annotated or walrus assignment to a name, a tuple assignment unpacked element by
    element (`HERE, OUT = Path(__file__).parent, None`)."""
    pairs: list[tuple[ast.Name, ast.AST]] = []
    for node in ast.walk(tree):
        if not (isinstance(node, (ast.Assign, ast.AnnAssign, ast.NamedExpr)) and node.value is not None):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        found = [(target, node.value) for target in targets]
        if isinstance(node.value, ast.Tuple):
            found = [(elt, value) for target in targets if isinstance(target, ast.Tuple) and len(target.elts) == len(node.value.elts)
                     for elt, value in zip(target.elts, node.value.elts)]
        pairs.extend((target, value) for target, value in found if isinstance(target, ast.Name))
    return pairs


def _literal(node: ast.AST) -> ast.Constant | None:
    """The string constant `node` is, or the one part of an f-string that holds nothing else (`f"name"`); else None."""
    if isinstance(node, ast.JoinedStr) and len(node.values) == 1:
        node = node.values[0]
    return node if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _sep_names(tree: ast.AST) -> frozenset[str]:
    """Names bound to the separator by an import: `from os import sep`, `from os.path import sep as SEP`."""
    return frozenset(alias.asname or alias.name for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
                     and node.module in {"os", "os.path"} for alias in node.names if alias.name == "sep")


DIR, FILE = "<the module's directory>", "<the module file>"


class _Piece(NamedTuple):
    """A piece of the string an expression builds (`_fold`)."""

    text: str | None  # the text as written, `/` for a separator, `DIR` or `FILE`, None for a part this gate cannot know
    node: ast.Constant | None  # the constant the text came from, whose id `_named_in` reads
    source: str | None  # for `DIR` or `FILE`: the name it was built from (`HERE`, `__file__`), for mixedness


_UNKNOWN = [_Piece(None, None, None)]
_SEPARATOR = [_Piece("/", None, None)]
PERCENT = re.compile(r"(%(?:\(\w*\))?[-+ #0]*\d*(?:\.\d+)?[a-zA-Z%])")  # a `%`-format placeholder


def _fold(node: ast.AST, aliases: set[str] | frozenset[str], files: set[str] | frozenset[str],
          slashed: set[str] | frozenset[str] = frozenset(), seps: frozenset[str] = frozenset()) -> list[_Piece]:
    """The string `node` builds, piece by piece, as Python builds it: a constant as written, `os.sep`, `os.path.sep`,
    a `sep` imported from `os` or a `"/"` as a separator, the module's directory as `DIR` (a name in `aliases`, with
    a separator after it when the name is in `slashed`; `.parent`, `parents[0]` or `dirname` of the module file) and
    the module file as `FILE` (`__file__`, a name in `files`), and None for a part this gate cannot know (another
    name, a call, an f-string part with a conversion or a format spec). Follows `+`, an f-string, a `%` template with
    `%s` fields, a `.format` template with plain positional or keyword fields, `sep.join([...])`, `os.path.join(...)`,
    `Path(a, b, ...)`, `joinpath(...)` and `/` (a separator between the operands), `with_name` on the module file
    (its directory, a separator, the name), and the wrappers `resolve()`, `absolute()`, `abspath()`, `realpath()`,
    `str()`, `os.fspath()` and `Path(x)`."""

    def fold(part: ast.AST) -> list[_Piece]:
        return _fold(part, aliases, files, slashed, seps)

    def joined(parts: list[ast.AST]) -> list[_Piece]:  # `os.path.join(a, b)`: a separator between the operands
        pieces: list[_Piece] = []
        for i, part in enumerate(parts):
            pieces.extend((_SEPARATOR if i else []) + fold(part))
        return pieces

    def directory_of(inner: list[_Piece]) -> list[_Piece]:  # `.parent`, `parents[0]`, `dirname` of the module file
        return [_Piece(DIR, None, inner[0].source)] if [piece.text for piece in inner if piece.text != ""] == [FILE] else _UNKNOWN

    if isinstance(node, ast.Name):
        if node.id == "__file__" or node.id in files:
            return [_Piece(FILE, None, node.id)]
        if node.id in aliases:
            return [_Piece(DIR, None, node.id)] + (_SEPARATOR if node.id in slashed else [])
        return _SEPARATOR if node.id in seps else _UNKNOWN
    if isinstance(node, ast.Constant):
        return [_Piece(node.value, node, None)] if isinstance(node.value, str) else _UNKNOWN
    if isinstance(node, ast.JoinedStr):
        return [piece for part in node.values for piece in fold(part)]
    if isinstance(node, ast.FormattedValue):
        return fold(node.value) if node.conversion == -1 and node.format_spec is None else _UNKNOWN
    if isinstance(node, ast.Attribute):
        if node.attr == "sep" and (isinstance(node.value, ast.Name) and node.value.id == "os"
                                   or isinstance(node.value, ast.Attribute) and node.value.attr == "path"):
            return _SEPARATOR
        return directory_of(fold(node.value)) if node.attr == "parent" else _UNKNOWN
    if isinstance(node, ast.Subscript):  # `parents[0]`
        value, index = node.value, node.slice
        if isinstance(value, ast.Attribute) and value.attr == "parents" and isinstance(index, ast.Constant) and index.value == 0:
            return directory_of(fold(value.value))
        return _UNKNOWN
    if isinstance(node, ast.BinOp):
        if isinstance(node.op, ast.Add):
            return fold(node.left) + fold(node.right)
        if isinstance(node.op, ast.Div):
            return joined([node.left, node.right])
        template = _literal(node.left) if isinstance(node.op, ast.Mod) else None
        if template is None:
            return _UNKNOWN
        args = list(node.right.elts) if isinstance(node.right, ast.Tuple) else [node.right]  # `"%s/*.json" % dir`
        pieces = []
        for i, chunk in enumerate(PERCENT.split(template.value)):
            if i % 2 == 0:
                pieces.append(_Piece(chunk, template, None))
            elif chunk == "%%":
                pieces.append(_Piece("%", template, None))
            else:
                pieces.extend(fold(args.pop(0)) if chunk == "%s" and args else _UNKNOWN)
        return pieces
    if isinstance(node, ast.Call):
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else ""
        receiver = func.value if isinstance(func, ast.Attribute) else None
        args = node.args
        if name in {"resolve", "absolute"} and receiver is not None and not args:
            return fold(receiver)
        if name == "dirname" and len(args) == 1:
            return directory_of(fold(args[0]))
        named = args[0] if len(args) == 1 else next((keyword.value for keyword in node.keywords if keyword.arg == "name"), None)
        if name == "with_name" and receiver is not None and named is not None:  # `Path(__file__).with_name("x")`, `with_name(name="x")`
            directory = directory_of(fold(receiver))
            return directory + _SEPARATOR + fold(named) if directory != _UNKNOWN else _UNKNOWN
        if (name.endswith("Path") or name in {"abspath", "realpath", "str", "fspath"}) and len(args) == 1 and not node.keywords:
            return fold(args[0])
        if name == "joinpath" and receiver is not None and args:
            return joined([receiver, *args])
        if name == "join" and receiver is not None and len(args) == 1 and isinstance(args[0], (ast.List, ast.Tuple)) \
                and [piece.text for piece in fold(receiver)] == ["/"]:  # `os.sep.join([dir, "x"])`, `"/".join(...)`
            return joined(args[0].elts)
        if (name == "join" or name.endswith("Path")) and args:  # `os.path.join(dir, "x")`, `Path(dir, "x")`
            return joined(args)
        template = _literal(receiver) if name == "format" and receiver is not None else None
        if template is None:
            return _UNKNOWN
        keywords = {keyword.arg: keyword.value for keyword in node.keywords if keyword.arg}  # `"{}/*.json".format(dir)`
        try:
            fields = list(string.Formatter().parse(template.value))
        except ValueError:
            return _UNKNOWN
        pieces, auto = [], 0
        for text, field, spec, conversion in fields:
            pieces.append(_Piece(text, template, None))
            if field is None:
                continue
            if field == "":
                value, auto = (args[auto] if auto < len(args) else None), auto + 1
            elif field.isdigit():
                value = args[int(field)] if int(field) < len(args) else None
            else:
                value = keywords.get(field)
            pieces.extend(fold(value) if value is not None and not spec and conversion is None else _UNKNOWN)
        return pieces
    return _UNKNOWN


def _is_module_dir(node: ast.AST, aliases: set[str] | frozenset[str], files: set[str] | frozenset[str] = frozenset(),
                   slashed: set[str] | frozenset[str] = frozenset(), seps: frozenset[str] = frozenset()) -> bool:
    """The module's directory, with or without a trailing separator, in any spelling `_fold` reads
    (`Path(__file__).parent`, `parents[0]`, `os.path.dirname(__file__)`, a wrapper or a name assigned from one of
    them, `dirname(__file__) + "/"`, `f"{HERE}{os.sep}"`, `os.path.join(HERE, "")`); `parents[1]`, `with_name(...)`
    and every other receiver is some other directory."""
    texts = [piece.text for piece in _fold(node, aliases, files, slashed, seps) if piece.text != ""]
    return texts in ([DIR], [DIR, "/"])


def _module_aliases(tree: ast.AST) -> tuple[set[str], set[str], set[str], set[str]]:
    """Names assigned the module's directory (`aliases`), names assigned the module file (`files`), by a plain, an
    annotated, a walrus or a tuple assignment of any spelling `_fold` reads (passes until no new name is found, so a
    name assigned from an alias counts whatever order the module binds them in and `here = abspath(here)` keeps
    `here`; an attribute is not followed); the `mixed` names among them, bound to something else somewhere in the
    module (a parameter, a loop or `with` target, an import, another value), a name assigned from a mixed name among
    them; and the `slashed` names, assigned the directory with a separator after it (`HERE = dirname(__file__) + "/"`,
    `HERE = f"{dir}{os.sep}"`, `p += os.sep`), so a literal glued to them needs no slash. A literal anchored on a
    mixed name is read both anchored and as spelled: its anchored reading alone could resolve to a path beside the
    module that does not exist (the name is `parents[1]` in another function) and go unseen, and the spelled reading
    alone would lose a bare pattern, a listing or a sibling folder on it."""
    bound, seps = _bindings(tree), _sep_names(tree)
    aliases: set[str] = set()
    files: set[str] = set()
    slashed: set[str] = set()
    dirs_bound: Counter[str] = Counter()
    files_bound: Counter[str] = Counter()
    pairs_seen: set[tuple[str, str]] = set()  # (target, the name its value is built from)
    while True:  # a name assigned the module's file or directory, then names assigned from those, until no new one
        known = len(aliases) + len(files) + len(slashed)
        dirs_bound, files_bound = Counter(), Counter()
        for target, value in _assigned(tree):
            pieces = _fold(value, aliases, files, slashed, seps)
            texts = [piece.text for piece in pieces if piece.text != ""]
            if texts == [FILE]:
                files_bound[target.id] += 1
                files.add(target.id)  # known at once, so `A = parent; B = A; C = B` is followed in one pass
            elif texts in ([DIR], [DIR, "/"]):
                dirs_bound[target.id] += 1
                aliases.add(target.id)
                if texts[-1] == "/":
                    slashed.add(target.id)
            else:
                continue
            source = next((piece.source for piece in pieces if piece.text != ""), None)
            if source is not None and source != target.id:
                pairs_seen.add((target.id, source))
        for node in ast.walk(tree):  # `p += os.sep` on a name holding the directory: slash-terminated from here on
            if (isinstance(node, ast.AugAssign) and isinstance(node.op, ast.Add) and isinstance(node.target, ast.Name)
                    and node.target.id in aliases and [piece.text for piece in _fold(node.value, aliases, files, slashed, seps) if piece.text != ""] == ["/"]):
                dirs_bound[node.target.id] += 1
                slashed.add(node.target.id)
        if len(aliases) + len(files) + len(slashed) == known:
            break
    mixed = {name for name, n in dirs_bound.items() if n != bound[name]} | {name for name, n in files_bound.items() if n != bound[name]}
    while True:  # a name assigned from a mixed name is mixed too (`base = root`, with `root` also `parents[1]` elsewhere)
        grown = mixed | {target for target, source in pairs_seen if source in mixed}
        if grown == mixed:
            return aliases, files, mixed, slashed
        mixed = grown


def _listed_dirs(tree: ast.AST) -> set[str]:
    """How the module lists its own directory: `"one"` level (`iterdir()` on it, `listdir`/`scandir` of it, what
    `glob("*")` names) and/or `"all"` levels (`walk()` on it, `os.walk` of it, what `rglob("*")` names)."""
    aliases, files, _, slashed = _module_aliases(tree)  # a mixed name lists loudly too
    seps = _sep_names(tree)
    depths: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else ""
        receiver = func.value if isinstance(func, ast.Attribute) and name in {"iterdir", "walk"} and not node.args else None
        keyed = [keyword.value for keyword in node.keywords if keyword.arg in {"path", "top"}]
        argument = (node.args[0] if node.args else keyed[0] if keyed else None) if name in {"listdir", "scandir", "walk"} else None
        for target in (receiver, argument):
            if target is not None and _is_module_dir(target, aliases, files, slashed, seps):
                depths.add("all" if name == "walk" else "one")
    return depths


def _sibling_literals(tree: ast.AST) -> tuple[set[int], dict[int, str], set[int], set[int]]:
    """ids of the string constants that build a path from the module's own location, read where Python reads them.
    Every string expression is folded once (`_fold`): `+` and `+=`, an f-string, a `%` or `.format` template,
    `sep.join([...])`, `os.path.join`, `Path(...)`, `joinpath`, `/` and `with_name`, with `os.sep` a slash and the
    module's directory or file a token. A fold that starts with the module's directory anchors the string after it,
    up to the first part this gate cannot know (a name, a call: `join(dir, sub, "*.json")` reads a directory this gate
    cannot know, the limit of a variable): the string must begin with a slash (`join(dir, "x")`, `dir + "/x"`,
    `f"{dir}{os.sep}*.json"`, `"%s/*.json" % dir`, `os.sep.join([dir, "x"])`, `HERE + "x"` with `HERE = dir + "/"`),
    since `dir + "_backup"` is another directory; its leading slashes dropped, it is returned in `joined` under the
    first constant it came from (`join(dir, "baselines", "*.json")` is `baselines/*.json`; `dir / "README.md"` is
    `README.md`), the other constants in `skip`, which `_named_in` does not read on their own. A glob (`glob`,
    `rglob`, `iglob`, or `glob.glob` with `root_dir=`) on the module's directory anchors its pattern constants, an
    f-string's parts included, and `join(dir, f"{stem}*.md")` reads as `glob(f"{stem}*.md")` would. A literal built on
    any other receiver (an output directory, `parents[1]`, a parameter) and a bare word anywhere else (a dict key, a
    column name) is not a folder. The ids anchored through a mixed name (one also bound to something else) are
    returned in `loose` too: `_named_in` reads those both anchored and as spelled."""
    aliases, files, mixed, slashed = _module_aliases(tree)
    seps = _sep_names(tree)

    def fold(node: ast.AST) -> list[_Piece]:
        return _fold(node, aliases, files, slashed, seps)

    def head(pieces: list[_Piece]) -> int:  # the first piece with text, past the empty string a template starts with
        return next((i for i, piece in enumerate(pieces) if piece.text != ""), 0)

    def anchored(pieces: list[_Piece]) -> bool:
        return bool(pieces) and pieces[head(pieces)].text == DIR

    def exact(pieces: list[_Piece]) -> bool:
        source = pieces[head(pieces)].source
        return source is None or source not in mixed

    def constants(operand: ast.AST) -> set[int]:  # a glob's pattern, an f-string's parts included
        parts = operand.values if isinstance(operand, ast.JoinedStr) else [operand]
        return {id(part) for part in parts if isinstance(part, ast.Constant)}

    ids: set[int] = set()
    joined: dict[int, str] = {}
    skip: set[int] = set()
    loose: set[int] = set()
    consumed: set[int] = set()  # the parts of a string already read as a whole
    for node in ast.walk(tree):
        if id(node) in consumed:
            continue
        read: set[int] = set()
        if isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else ""
            root_dir = [keyword.value for keyword in node.keywords if keyword.arg == "root_dir"]
        else:
            name, root_dir = "", []
        if name in {"glob", "iglob"} and root_dir:  # `glob.glob(p, root_dir=dir)`, `iglob`, or `glob` imported bare
            pieces = next((fold(r) for r in root_dir if _is_module_dir(r, aliases, files, slashed, seps)), None)
            if pieces is None:
                continue
            for operand in [*node.args, *(keyword.value for keyword in node.keywords if keyword.arg != "root_dir")]:
                read |= constants(operand)
        elif name in {"glob", "rglob"} and isinstance(node.func, ast.Attribute):  # `dir.glob("*.md")`, `rglob`
            pieces = fold(node.func.value)
            if not _is_module_dir(node.func.value, aliases, files, slashed, seps):
                continue
            for operand in [*node.args, *(keyword.value for keyword in node.keywords)]:
                read |= constants(operand)
        else:
            if isinstance(node, ast.AugAssign) and isinstance(node.op, ast.Add):  # `p += "/baselines"` on the directory name
                pieces, operands = fold(node.target) + fold(node.value), _add_chain(node.value)
            elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
                pieces, operands = fold(node), _add_chain(node)[1:]
            elif isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Div, ast.Mod)):
                pieces, operands = fold(node), [node.right]
            elif isinstance(node, ast.JoinedStr):
                pieces, operands = fold(node), node.values[1:]
            elif name in {"join", "joinpath", "with_name", "format"} or name.endswith("Path"):
                pieces, operands = fold(node), (node.args if name in {"joinpath", "with_name"} else node.args[1:])
            else:
                continue
            if not anchored(pieces):
                continue
            tail = list(itertools.takewhile(lambda piece: piece.text is not None, pieces[head(pieces) + 1:]))
            text = "".join(piece.text for piece in tail)
            nodes = [piece.node for piece in tail if piece.node is not None and piece.text]
            if text.startswith("/") and nodes:
                read.add(id(nodes[0]))
                joined[id(nodes[0])] = text.lstrip("/")
                skip.update(id(constant) for constant in nodes[1:] if constant is not nodes[0])
            elif operands and isinstance(operands[0], ast.JoinedStr) and not text.strip("/"):
                read |= constants(operands[0])  # `join(dir, f"{stem}*.md")` reads as `glob(f"{stem}*.md")`
            consumed.update(id(part) for part in ast.walk(node) if part is not node)
        ids |= read
        if not exact(pieces):
            loose |= read
    return ids, joined, skip, loose


def _named_in(tree: ast.AST, module: str = "backend/evals/") -> set[str]:
    """Repo-relative paths of tracked files a string literal in `tree` names (see NAMED_CANDIDATES)."""
    found, (sibling, joined, skip, loose), recursive = set(), _sibling_literals(tree), _recursive_literals(tree)
    listed = _listed_dirs(tree)
    if listed:
        found.update(_glob_matches(posixpath.dirname(module) + "/", ["*"], "all" in listed))
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)) or id(node) in skip:
            continue
        value = LOCAL_URL.sub("", joined.get(id(node), node.value))
        if "://" in value:
            continue
        parts = posixpath.normpath(value).split("/")  # `..` survives only at the start
        segments = [s for s in parts if s not in ("", ".", "..")]
        deep = id(node) in recursive  # `rglob(p)` is `glob("**/" + p)`: a leading `**` is stripped and remembered
        while segments and segments[0] == "**":
            segments, deep = segments[1:], True
        cut = next((i for i, segment in enumerate(segments) if GLOB.search(segment)), len(segments))
        pattern, segments, globbed = segments[cut:], segments[:cut], cut < len(segments)
        climbs = parts[0] == ".."
        # A joined path resolves on the module's directory as Python resolves it; a leading `**` is read at every
        # depth below it, after the climb of a `..` before it.
        anchored = id(node) in sibling and (climbs or id(node) in joined or deep or (not segments and globbed))
        if anchored and not (segments or globbed or deep):  # a lone `..` or `.` joined to the module's directory names nothing
            continue
        if anchored:
            # Anchored on the module's own location: `.glob("*.md")` on its directory, or a `..` path from it
            # (`../assets` from `app/services/` is `app/assets`, not every `assets` directory in the repository).
            base = posixpath.dirname(module)
            for _ in range(parts.count("..")):
                base = posixpath.dirname(base)
            target = posixpath.join(base, "/".join(segments)) if segments else base
            if globbed:  # `../**/baselines/*.json`: the `**` comes before the spelled directory, every level below the climb
                found.update(_glob_matches(base + "/" if base else "", segments + pattern, deep))
            elif deep:  # `rglob("../p")` or a lone `**`: every `p` below the climbed directory, more than pathlib reads, loudly
                found.update(_glob_matches(base + "/" if base else "", segments or ["*"], True))
                found.update(_glob_matches(base + "/" if base else "", segments + ["**"], True) if segments else ())
            elif target in TRACKED:
                found.add(target)
            else:
                found.update(p for p in TRACKED if p.startswith(target + "/") and not p.endswith("/.gitignore"))
            if id(node) not in loose:
                continue
            # Anchored through a name also bound to something else: the reading above may have resolved to a path
            # beside the module that does not exist, so the literal is read as spelled too, loudly.
        if globbed and not segments:  # a bare pattern on some other receiver names nothing
            continue
        if not segments or (len(segments) == 1 and segments[0] in RUN_ARTIFACTS and module.startswith("backend/evals/")):
            continue
        suffix, outside, spelled = "/".join(segments), parts[0] == "..", len(segments) > 1 or globbed  # `docs/*.md` spells `docs`
        dirs = NAMED_DIRS.get(segments[-1], [])
        if not (outside or spelled):  # `Path(__file__).with_name("questions")` in an eval module names a sibling folder
            beside = id(node) in sibling and module.startswith("backend/evals/")
            dirs = [d for d in dirs if beside and d == f"{posixpath.dirname(module)}/{suffix}/"]
        files = [] if globbed else NAMED_CANDIDATES.get(segments[-1], [])  # a glob applies to a directory
        matches = [c for c in files + dirs if c.rstrip("/") == suffix or c.rstrip("/").endswith("/" + suffix)]
        inside = [c for c in matches if c.startswith("backend/")]
        for candidate in matches if outside or (spelled and not inside) else inside:
            if candidate.endswith("/") and globbed:  # the directory is matched at any depth already (`**/dir/*` is `dir/*`)
                found.update(_glob_matches(candidate, pattern, False))
            elif candidate.endswith("/"):  # a `.gitignore` tells git what not to track; the run never reads one
                found.update(p for p in TRACKED if p.startswith(candidate) and not p.endswith("/.gitignore"))
            else:
                found.add(candidate)
    return found


def _module_name(path: str) -> str:
    """`backend/scripts/seed.py` -> `scripts.seed`; a package's `__init__.py` is the package."""
    return ".".join(path[len("backend/") : -len(".py")].removesuffix("/__init__").split("/"))


def named_files(closure: set[str]) -> set[str]:
    found: set[str] = set()
    for path in closure:
        found |= _named_in(ast.parse((ROOT / path).read_text(encoding="utf-8")), path)
    return found


# Loaded at runtime rather than imported, so the closure cannot discover them.
def runtime_inputs(closure: set[str]) -> list[str]:
    return _existing(
        _glob("prompts/*.md") + _glob("evals/copilot_*.json") + [f for d in DATA_DIRS for f in _glob(f"{d}/**/*")]
        + [ROOT / p for p in step_inputs()] + [WORKFLOW] + [ROOT / p for p in named_files(closure)],
        "runtime inputs",
    )


# Must never start the paid run: they cannot change its result. Two kinds. The deliberate categories
# (tests, scripts, migrations, routers, integrations, top-level files, the summary eval's modules and
# data) are so by design: the eval importing or naming one is reported, and the remedy is to drop the
# dependency or to reclassify the file here on purpose, never a filter edit. The catch-alls (Markdown
# under evals/, everything outside backend/ that the run does not load) are non-triggers only until
# the eval names a file there: then it is an input the filter must cover, so the right filter entry
# clears the gate instead of failing a second test.
def non_triggers(closure: set[str]) -> list[str]:
    summary_eval_modules = [
        p for p in _glob("evals/*.py") if not p.name.startswith("copilot_") and p.name not in COPILOT_EVAL_MODULES
    ]
    inputs, named = set(step_inputs()), named_files(closure)
    top_level = [ROOT / p for p in TRACKED if p.startswith("backend/") and p.count("/") == 1 and p not in inputs]
    deliberate = _existing(
        _glob("tests/**/*") + summary_eval_modules + _glob("scripts/*") + _glob("migrations/*")
        + _glob("app/routers/*.py") + _glob("app/integrations/*.py") + top_level + [BACKEND / p for p in SUMMARY_EVAL_DATA]
        + _glob("evals/baselines/*.json"),
        "non-triggers",
    )
    overlap = sorted(set(deliberate) & (closure | named | inputs))
    assert not overlap, (
        "the eval now imports or names these files, which are non-triggers by design: remove the dependency, rename a copy that only shares a file's name, or reclassify "
        f"them in this gate deliberately (a name the eval only writes belongs in RUN_ARTIFACTS): {overlap}"
    )
    used = inputs | named | {WORKFLOW.relative_to(ROOT).as_posix()}
    markdown = _existing(_glob("evals/**/*.md"), "non-triggers")
    return deliberate + [p for p in markdown if p not in used] + sorted(p for p in TRACKED if not p.startswith("backend/") and p not in used)


def _module_path(module: str) -> Path | None:
    rel = "/".join(module.split("."))
    for candidate in (f"{rel}.py", f"{rel}/__init__.py"):
        if candidate in TRACKED_PY:
            return BACKEND / candidate
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
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and DOTTED.match(node.value):
            parts = node.value.split(":")[0].split(".")  # `pkgutil.resolve_name("app.x:Class")` imports `app.x`
            if parts[0] in LOCAL_TOP_LEVEL:  # `mock.patch("app.x.Class.method")` imports `app.x`, the longest module prefix
                found = next((".".join(parts[:n]) for n in range(len(parts), 1, -1) if _module_path(".".join(parts[:n])) is not None), None)
                if found is not None:
                    yield found


def _workflow() -> dict:
    return yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def _simple_commands(run_text: str):
    """Each simple command of a run step: lines split on `&&`, `||`, `;`, `|` and `&` outside quotes
    (`>&` stays a redirection); blank lines and comments skipped."""
    for line in run_text.split("\n"):  # bash breaks lines on \n only; splitlines() would also break on \v, \f, NEL
        line = line.strip(" \t")  # bash blanks; strip() would also eat a no-break space
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
        return ("install" if install else "env"), [posixpath.normpath((Path(workdir) / p).as_posix() if workdir else p) for p in operands]
    if any(p.match(command) for p in SAFE_COMMANDS):
        return "safe", None
    return "untraced", command


def _entry_paths(command: str, workdir: str) -> list[tuple[str, str, bool]]:
    """(repo-relative path, value as written, single-quoted) for every argument of an entry command that
    may be a path; quotes are removed as bash removes them, and a single-quoted value is literal to bash,
    so a `$` in it never expands."""
    found = []
    for token in re.findall(r"\"[^\"]*\"|'[^']*'|\S+", ENTRY.match(command).group(2)):
        bare = token.strip("\"'")
        if bare == "2>&1" or FLAG.match(bare):
            continue
        name, _, value = bare.partition("=")
        raw = value if bare.startswith("--") and FLAG.match(name) else bare
        if INTEGER.match(raw):  # an empty argument stays: `Path("")` is the working directory
            continue
        found.append((posixpath.normpath((Path(workdir) / raw).as_posix() if workdir else raw), raw, token.startswith("'")))
    return found


def _ignored(rel: str) -> bool:
    """Whether the repository's own ignore rules cover `rel` (the user's global excludes are not consulted;
    a per-clone `.git/info/exclude` still is, no git option disables it, and CI's checkout has none, so a
    local one can only make a local run more lenient); a gitignored path is something the run writes,
    never an input."""
    try:
        command = ["git", "-c", "core.excludesFile=/dev/null", "check-ignore", "-q", "--", rel]
        return subprocess.run(command, cwd=ROOT, capture_output=True).returncode == 0  # noqa: S603, S607
    except OSError:
        return False


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
    modules, requirement_files, env_files, entry_files, untraced = set(), set(), set(), set(), []
    untraced += _unknown_keys(workflow, TOP_KEYS, "workflow") + _env_problems(workflow, "workflow")
    if "on" in workflow:  # the probes below omit it; the real workflow always carries it
        on = workflow["on"]
        if not isinstance(on, dict) or set(on) != {"pull_request"} or not isinstance(on["pull_request"], dict):
            untraced.append(f"workflow: `on:` must be exactly pull_request with types and paths, not {on!r}")
        else:
            untraced += _unknown_keys(on["pull_request"], ON_KEYS, "on.pull_request")
    for job_name, job in workflow["jobs"].items():
        untraced += _unknown_keys(job, JOB_KEYS, f"{job_name} job") + _env_problems(job, f"{job_name} job")
        for step in job.get("steps", []):
            untraced += _unknown_keys(step, STEP_KEYS, f"{job_name} step") + _env_problems(step, f"{job_name} step")
            uses = str(step.get("uses", ""))
            if uses and not ALLOWED_ACTIONS.match(uses):
                untraced.append(f"{job_name}: action {uses} is not one of the allowed actions")
            elif uses:
                inputs = step.get("with") or {}
                extra = sorted(set(inputs) - ALLOWED_INPUTS[uses.split("@")[0]])
                if extra:
                    untraced.append(f"{job_name}: action {uses} takes inputs the gate does not know: {extra}")
                if uses.startswith("actions/setup-python@") and not PYTHON_VERSION.match(str(inputs.get("python-version", ""))):
                    untraced.append(f"{job_name}: {uses} must pin a literal python-version; without one it reads the root .python-version")
            if "run" not in step:
                continue
            shell = _run_setting("shell", step, job, workflow)
            if shell and not SHELL.match(shell):
                untraced.append(f"{job_name}: run step under shell: {shell}")
                continue
            workdir = _run_setting("working-directory", step, job, workflow)
            run = str(step["run"])
            if "\\" in run or "${" in run or "${" in workdir or NON_ASCII.search(run):
                untraced.append(f"{job_name}: a backslash, a `${{` or a non-ASCII character in a run step can change what bash runs: {run.strip()[:60]!r}")
                continue
            for command in _simple_commands(run):
                kind, value = _classify(command, workdir)
                if kind == "entry" and workdir != ENTRY_WORKDIR:
                    untraced.append(f"{job_name}: `{command}` runs from {workdir or '.'!r}, not {ENTRY_WORKDIR!r}; python -m would import from there first")
                elif kind == "entry":
                    modules.add(value)
                    for rel, raw, literal in _entry_paths(command, workdir):
                        expands = "$" in raw and not literal
                        if expands and raw.startswith("$RUNNER_TEMP/") and "$" not in raw[len("$RUNNER_TEMP/"):] and ".." not in raw.split("/"):
                            continue
                        tracked = [] if expands else [
                            p for p in TRACKED if (rel == "." or p == rel or p.startswith(rel + "/")) and not p.endswith("/.gitignore")
                        ]
                        if expands or not (tracked or _ignored(rel)):
                            untraced.append(f"{job_name}: `{command}` reads {raw!r}, which is neither tracked, gitignored nor under $RUNNER_TEMP")
                        entry_files.update(tracked)
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
    return sorted(modules), sorted(requirement_files | env_files | entry_files)


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
        # A `.py` the module runs by path (subprocess) is a module too: its own imports are followed.
        named = _named_in(tree, path.relative_to(ROOT).as_posix())
        stack.extend(_module_name(p) for p in named if p.startswith("backend/") and p.endswith(".py"))
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
    assert _classify("pip install -r prompts/../requirements.txt", "backend") == ("install", ["backend/requirements.txt"])
    assert _classify("grep -v '^#' .github/ai-model.env >> \"$GITHUB_ENV\"") == ("env", [".github/ai-model.env"])
    # Path-valued arguments of an entry command: a tracked file or directory is an input of the run, a
    # gitignored path or `$RUNNER_TEMP` is run-local, anything else is untraced.
    assert _entry_paths(
        'python -m evals.copilot_runner --preparation evals/reports/copilot/preparation.json --output evals/reports/copilot --runs 3 2>&1', "backend"
    ) == [
        ("backend/evals/reports/copilot/preparation.json", "evals/reports/copilot/preparation.json", False),
        ("backend/evals/reports/copilot", "evals/reports/copilot", False),
    ]
    assert _entry_paths('python -m evals.copilot_bootstrap --database "$RUNNER_TEMP/copilot fidelity.db" --runs 3 --output=out --quiet', "backend") == [
        ("backend/$RUNNER_TEMP/copilot fidelity.db", "$RUNNER_TEMP/copilot fidelity.db", False), ("backend/out", "out", False),  # `3` is not a path; `--opt=value` is split
    ]
    assert _entry_paths("python -m evals.copilot_runner --preparation=tests/x.json --sources ..", "backend") == [
        ("backend/tests/x.json", "tests/x.json", False), (".", "..", False),
    ]
    # An empty argument is the working directory to `Path("")`, so it is traced as `.` (every tracked file).
    assert _entry_paths("python -m evals.copilot_runner --preparation '' --output=", "backend") == [("backend", "", True), ("backend", "", False)]
    # Quotes come off before the split, as bash removes them; a single-quoted `$` is literal to bash, so the
    # run reads a directory named `$RUNNER_TEMP`, not the runner's.
    assert _entry_paths("python -m evals.copilot_runner \"--preparation=tests/x.json\" '--sources=$RUNNER_TEMP/s' --output '$RUNNER_TEMP/o' \"--runs=3\"", "backend") == [
        ("backend/tests/x.json", "tests/x.json", False), ("backend/$RUNNER_TEMP/s", "$RUNNER_TEMP/s", True), ("backend/$RUNNER_TEMP/o", "$RUNNER_TEMP/o", True),
    ]
    runner = {"working-directory": "backend"}
    assert _read_steps({"jobs": {"j": {"steps": [{"run": 'python -m evals.copilot_runner --output "$RUNNER_TEMP/out" --preparation evals/reports/copilot/preparation.json', **runner}]}}}) == (["evals.copilot_runner"], [])
    # The fixtures are injected, so a cleanup of a live one cannot fail these cases with a message that blames the workflow.
    prep, sources = "backend/tests/fixtures/probe/preparation.json", ["backend/tests/fixtures/probe/sources/a.json", "backend/tests/fixtures/probe/sources/b.json"]
    with mock.patch.object(sys.modules[__name__], "TRACKED", TRACKED | {prep, *sources, "backend/tests/fixtures/probe/sources/.gitignore"}):
        for spelling in ("--preparation tests/fixtures/probe/preparation.json", '"--preparation=tests/fixtures/probe/preparation.json"', "--preparation=tests/fixtures/probe/preparation.json"):
            assert _read_steps({"jobs": {"j": {"steps": [{"run": f"python -m evals.copilot_runner {spelling}", **runner}]}}}) == (["evals.copilot_runner"], [prep]), spelling
        assert _read_steps({"jobs": {"j": {"steps": [{"run": "python -m evals.copilot_runner --sources tests/fixtures/probe/sources", **runner}]}}})[1] == sources  # a directory, but its `.gitignore`
    # A bare directory name and `..` are the same inputs; `requirements.txt` is a tracked file.
    assert len(_read_steps({"jobs": {"j": {"steps": [{"run": "python -m evals.copilot_runner --sources tests", **runner}]}}})[1]) > 100
    assert len(_read_steps({"jobs": {"j": {"steps": [{"run": "python -m evals.copilot_runner --sources ..", **runner}]}}})[1]) > 1000
    assert _read_steps({"jobs": {"j": {"steps": [{"run": "python -m evals.copilot_runner --sources requirements.txt", **runner}]}}})[1] == ["backend/requirements.txt"]


def test_an_untraceable_shell_action_env_or_job_is_rejected():
    step = {"run": "python -m evals.copilot_runner", "working-directory": "backend"}
    checkout = {"uses": "actions/checkout@v7"}
    assert _read_steps({"jobs": {"j": {"steps": [checkout, step]}}}) == (["evals.copilot_runner"], [])
    assert _read_steps({"on": {"pull_request": {"types": ["opened", "ready_for_review"], "paths": ["backend/app/**"]}}, "jobs": {"j": {"steps": [step]}}}) == (["evals.copilot_runner"], [])
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
        {"jobs": {"j": {"steps": [{"run": 'python -m evals.copilot_runner --x "a\\"; bash x.sh"', "working-directory": "backend"}]}}},
        {"jobs": {"j": {"steps": [{"run": 'python -m evals.copilot_runner --output "${{ vars.COPILOT_OUT }}"', "working-directory": "backend"}]}}},
        {"jobs": {"j": {"steps": [{"run": 'python -m evals.copilot_runner --output "${X@P}"', "working-directory": "backend"}]}}},
        {"env": {"BASH_ENV": "scripts/ci_env.sh"}, "jobs": {"j": {"steps": [step]}}},
        {"jobs": {"j": {"env": {"PYTHONPATH": "backend/scripts"}, "steps": [step]}}},
        {"jobs": {"j": {"env": {"PATH": "backend/scripts/bin:/usr/bin"}, "steps": [step]}}},
        {"jobs": {"j": {"env": {"PIP_EDITABLE": "backend/scripts/pkg"}, "steps": [step]}}},
        {"jobs": {"j": {"env": {"HOME": "/tmp/x"}, "steps": [step]}}},
        {"jobs": {"j": {"env": "${{ fromJSON(vars.E) }}", "steps": [step]}}},
        {"jobs": {"j": {"steps": [{"env": {"bash_env": "x.sh"}, **step}]}}},
        {"jobs": {"j": {"steps": [{"uses": "actions/setup-python@v7", "with": {"python-version-file": ".python-version"}}, step]}}},
        {"jobs": {"j": {"steps": [{"uses": "actions/setup-python@v7"}, step]}}},
        {"jobs": {"j": {"steps": [{"uses": "actions/setup-python@v7", "with": {"python-version": "${{ vars.PY }}"}}, step]}}},
        {"jobs": {"j": {"steps": [{"run": "python -m evals.copilot_runner\x0b# ; bash evil.sh", "working-directory": "backend"}]}}},
        {"jobs": {"j": {"steps": [{"run": "python -m evals.copilot_runner\r# ; bash evil.sh", "working-directory": "backend"}]}}},
        {"jobs": {"j": {"steps": [{"run": "python -m evals.copilot_runner\u2028# ; bash evil.sh", "working-directory": "backend"}]}}},
        {"jobs": {"j": {"steps": [{"run": "python -m evals.copilot_runner --output \"x\x0by\"", "working-directory": "backend"}]}}},
        {"jobs": {"j": {"steps": [{"run": "python -m evals.copilot_runner\n\u00a0#x || bash scripts/evil.sh", "working-directory": "backend"}]}}},
        {"jobs": {"j": {"steps": [{"run": "python -m evals.copilot_runner\n\u3000#x || bash scripts/evil.sh", "working-directory": "backend"}]}}},
        {"jobs": {"j": {"steps": [{"run": "python -m evals.copilot_runner --preparation tests/fixtures/prep/preparation.json", "working-directory": "backend"}]}}},
        {"jobs": {"j": {"steps": [{"run": 'python -m evals.copilot_bootstrap --database "$HOME/copilot.db" --output evals/reports/copilot', "working-directory": "backend"}]}}},
        {"jobs": {"j": {"steps": [{"run": "python -m evals.copilot_runner --preparation ../preparation.json", "working-directory": "backend"}]}}},
        {"jobs": {"j": {"steps": [{"run": "python -m evals.copilot_runner --preparation=tests/fixtures/prep/preparation.json", "working-directory": "backend"}]}}},
        {"jobs": {"j": {"steps": [{"run": "python -m evals.copilot_runner --sources $PWD", "working-directory": "backend"}]}}},
        {"jobs": {"j": {"steps": [{"run": "python -m evals.copilot_runner --sources $GITHUB_WORKSPACE/backend", "working-directory": "backend"}]}}},
        {"jobs": {"j": {"steps": [{"run": 'python -m evals.copilot_runner --preparation "$RUNNER_TEMP/../preparation.json"', "working-directory": "backend"}]}}},
        {"jobs": {"j": {"steps": [{"run": "python -m evals.copilot_runner --output outdir-x", "working-directory": "backend"}]}}},
        {"jobs": {"j": {"steps": [{"run": "python -m evals.copilot_runner --preparation$STRIPE_WEBHOOK_SECRET", "working-directory": "backend"}]}}},
        {"jobs": {"j": {"steps": [{"run": "python -m evals.copilot_runner --$X=evals/reports/copilot", "working-directory": "backend"}]}}},
        {"jobs": {"j": {"steps": [{"run": 'python -m evals.copilot_bootstrap --database "$RUNNER_TEMP/$X/../copilot.db" --output evals/reports/copilot', "working-directory": "backend"}]}}},
        {"jobs": {"j": {"steps": [{"run": "python -m evals.copilot_bootstrap --database $RUNNER_TEMP/o$IFS--preparation$IFS../x --output evals/reports/copilot", "working-directory": "backend"}]}}},
        {"jobs": {"j": {"steps": [{"run": "python -m evals.copilot_runner --preparation '$RUNNER_TEMP/preparation.json'", "working-directory": "backend"}]}}},
        {"jobs": {"j": {"steps": [{"run": "python -m evals.copilot_runner '--preparation=$RUNNER_TEMP/preparation.json'", "working-directory": "backend"}]}}},
        {"jobs": {"j": {"steps": [{"run": 'python -m evals.copilot_runner "--preparation=tests/fixtures/prep/preparation.json"', "working-directory": "backend"}]}}},
        {"jobs": {"j": {"steps": [{"run": 'python -m evals.copilot_runner "--preparation=../docs/no-such-file.md"', "working-directory": "backend"}]}}},
        {"jobs": {"j": {"steps": [{"run": "python -m evals.copilot_runner --output evals/reports", "working-directory": "backend"}]}}},  # only a .gitignore is tracked there
        {"on": {"pull_request": {"types": ["ready_for_review"], "paths": ["backend/app/**"]}, "pull_request_target": {"types": ["ready_for_review"]}}, "jobs": {"j": {"steps": [step]}}},
        {"on": {"pull_request": {"types": ["ready_for_review"], "paths": ["backend/app/**"], "paths-ignore": ["backend/tests/**"]}}, "jobs": {"j": {"steps": [step]}}},
        {"on": ["pull_request", "push"], "jobs": {"j": {"steps": [step]}}},
        {"jobs": {"j": {"steps": [{"uses": "actions/checkout@v7", "with": {"repository": "x/y", "path": "z"}}, step]}}},
    ):
        try:
            _read_steps(workflow)
        except AssertionError:
            continue
        raise AssertionError(f"accepted a workflow the gate cannot trace: {workflow}")
    # An expression or a backslash in an otherwise valid entry step is rejected by that check alone.
    for run in (
        'python -m evals.copilot_runner --output "${{ vars.COPILOT_OUT }}"',
        'python -m evals.copilot_runner --output "${X@P}"',
        'python -m evals.copilot_runner --x "a\\"; bash x.sh"',
    ):
        try:
            _read_steps({"jobs": {"j": {"steps": [{"run": run, "working-directory": "backend"}]}}})
        except AssertionError as e:
            assert "`${`" in str(e), str(e)
        else:
            raise AssertionError(f"accepted an expression in a run step: {run}")


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
        "-r d.txt -e ./pkg\nfoo==1.*\nfoo==1.tar.gz\nfoo==1+a.zip\nfoo==1+local\nfoo==1#.zip\n-r d.txt# y\n"
    )
    nested, problems = _requirement_inputs(str(base / "e.txt"))
    assert len(problems) == 18 and nested == [], (nested, problems)
    # `-r=g.txt` names `=g.txt` to pip, so that is the file traced.
    (base / "f.txt").write_text("-r=g.txt\n")
    (base / "=g.txt").write_text("numpy==1\n")
    assert _requirement_inputs(str(base / "f.txt")) == ([str(base / "=g.txt")], [])
    assert REQ_PIN.match("python-dateutil==2.9.0.post0") and REQ_PIN.match("x==1.0rc1 ; python_version < '3.12'  # why")
    (base / "ok.env").write_text("# c\n\nAI_DEFAULT_MODEL=x\nOPENAI_BASE_URL=y\n")
    assert _env_file_problems(str(base / "ok.env")) == []
    (base / "bad.env").write_text("AI_DEFAULT_MODEL=x\nPYTHONPATH<<EOF\nbackend/scripts\nEOF\nFOO=1\n  # indented\n   \n")
    assert len(_env_file_problems(str(base / "bad.env"))) == 6
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


def test_tracked_files_come_from_git():
    assert not GIT_PROBLEMS, GIT_PROBLEMS
    assert "backend/evals/copilot_runner.py" in TRACKED


def test_closure_follows_every_top_level_backend_name():
    assert {"app", "evals", "tests", "main", "task_worker_main", "scripts"} <= LOCAL_TOP_LEVEL, sorted(LOCAL_TOP_LEVEL)
    files = reachable_files()
    assert len(files) > 50, sorted(files)
    assert "backend/app/services/copilot_service.py" in files
    assert "backend/app/services/edgar/__init__.py" in files
    assert not [f for f in files if f.startswith("backend/tests/")], "the eval must not import test code"
    # The summary-eval modules exempted from the non-trigger list must really be in the closure.
    assert {f"backend/evals/{m}" for m in COPILOT_EVAL_MODULES} <= files
    # A `.py` run by path is a module of the closure too, so its own imports are followed.
    assert _module_name("backend/scripts/seed.py") == "scripts.seed" and _module_name("backend/app/edgar/__init__.py") == "app.edgar"
    # The script is chosen for having a local import the closure lacks, whichever script that is today, so the
    # assertion never depends on what the closure happens to hold; the hop must bring at least those imports.
    def _own_imports(path: str) -> set[str]:
        tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
        found = {_module_path(m) for m in _local_imports(_module_name(path), False, tree)}
        return {p.relative_to(ROOT).as_posix() for p in found if p is not None}
    script, lacked = next(
        (p, extra) for p in sorted(TRACKED) if p.startswith("backend/scripts/") and p.endswith(".py")
        for extra in [_own_imports(p) - files - {p}] if extra
    )
    with mock.patch.object(sys.modules[__name__], "_named_in", lambda tree, module="": {script} if module.endswith("copilot_runner.py") else set()):
        hopped = reachable_files(["evals.copilot_runner"])
    assert script in hopped and script not in files
    assert lacked <= hopped, f"the hop did not follow {script}'s own imports: {sorted(lacked - hopped)}"


def test_relative_imports_anchor_on_the_owning_package():
    tree = ast.parse("from .contact import ContactSubmissionCreate\nfrom ..utils import numbers\n")
    assert set(_local_imports("app.schemas", True, tree)) >= {"app.schemas.contact", "app.utils", "app.utils.numbers"}
    assert set(_local_imports("app.schemas.summary", False, tree)) >= {"app.schemas.contact", "app.utils"}
    # A dotted module name in a string literal that resolves to a local module is an import too.
    tree = ast.parse('m = importlib.import_module("app.integrations.sec_api"); x = "sqlalchemy.orm"; y = "app.no_such.module"')
    assert set(_local_imports("app.services.copilot_service", False, tree)) == {"app.integrations.sec_api"}
    # A dotted string naming a module attribute (a `mock.patch` target, a `pkgutil.resolve_name` reference) imports the
    # longest module prefix; a bare top-level package is never a find.
    tree = ast.parse('p = patch("app.integrations.sec_api.SECFullTextSearchClient.search"); q = pkgutil.resolve_name("app.services.copilot_service:CopilotService"); '
                     'r = pkgutil.resolve_name("app.services:thing"); s = "app.state.ready"; u = "companies.id"; v = "uvicorn.error"')
    assert set(_local_imports("evals.copilot_runner", False, tree)) == {"app.integrations.sec_api", "app.services.copilot_service", "app.services"}


def test_every_reachable_module_and_runtime_input_triggers_the_run():
    patterns = workflow_filter()
    closure = reachable_files()
    inputs = runtime_inputs(closure)
    assert len(inputs) > 10, inputs
    missing = sorted(p for p in closure | set(inputs) if not triggers(p, patterns))
    assert not missing, f"copilot-eval.yml paths no longer cover inputs of the eval: {missing}"


def test_files_that_cannot_change_the_result_do_not_trigger_the_run():
    patterns = workflow_filter()
    closure = reachable_files()
    candidates = non_triggers(closure)
    assert len(candidates) > 100, candidates
    wrong = [p for p in candidates if triggers(p, patterns)]
    assert not wrong, f"copilot-eval.yml would pay for a run these paths cannot affect: {wrong}"
    # A catch-all file the eval names (outside backend/, Markdown under evals/) is an input, not a non-trigger;
    # a file in a deliberate category stays reported.
    evals_md = sorted(p for p in TRACKED if p.startswith("backend/evals/") and p.endswith(".md"))
    assert evals_md and "docs/CONFIGURATION.md" in TRACKED, "docs/CONFIGURATION.md has moved; test_configuration_reference.py pins it too"
    pair = {"docs/CONFIGURATION.md", evals_md[0]}
    with mock.patch.object(sys.modules[__name__], "named_files", lambda c: set()):
        unnamed = set(non_triggers(closure))
    with mock.patch.object(sys.modules[__name__], "named_files", lambda c: pair):
        yielded = set(non_triggers(closure))
    assert pair <= unnamed and unnamed - yielded == pair
    with mock.patch.object(sys.modules[__name__], "named_files", lambda c: {"backend/tests/fixtures/companyfacts_sample.json"}):
        try:
            non_triggers(closure)
        except AssertionError as error:
            assert "non-triggers by design" in str(error)
        else:
            raise AssertionError("a tests fixture named by the eval was not reported")


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
    # A URL's last segment is not a name, and neither is an artifact the eval only writes; an app module
    # naming an artifact basename is not writing an artifact, so a tracked file of that name is reported.
    # The candidates are injected, so these hold whether or not the tree has such a file today.
    font = "Inter-Variable-latin.woff2"
    injected = {
        "xbrl.json": ["backend/tests/fixtures/x/xbrl.json"], "baseline_scores.json": ["backend/evals/baseline_scores.json"],
        "copilot-eval.md": ["tasks/review-evidence/probe/copilot-eval.md", "backend/tests/fixtures/copilot-eval.md"],
        font: [f"backend/app/assets/fonts/{font}", f"frontend/scripts/brand/fonts/{font}"],
        "seed.py": ["backend/scripts/seed.py"], "CONFIGURATION.md": ["docs/CONFIGURATION.md"], "seed.db": ["backend/tests/fixtures/seed.db"],
    }
    with mock.patch.dict(NAMED_CANDIDATES, injected):
        assert _named_in(ast.parse('u = "https://example.com/files/baseline_scores.json"')) == set()
        # A relative SQLite URL names its file, driver-qualified or not; any other URL is skipped.
        for url in ("sqlite:///tests/fixtures/seed.db", "sqlite:///./tests/fixtures/seed.db", "sqlite+pysqlite:///tests/fixtures/seed.db"):
            assert _named_in(ast.parse(f'e = create_engine("{url}")'), "backend/app/x.py") == {"backend/tests/fixtures/seed.db"}, url
        assert _named_in(ast.parse('e = "sqlite:///"; m = "sqlite:///:memory:"; f = "file:///tests/fixtures/seed.db"'), "backend/app/x.py") == set()
        assert "xbrl.json" in RUN_ARTIFACTS and _named_in(ast.parse('a = _artifact(folder, "xbrl.json", xbrl)'), "backend/evals/copilot_bootstrap.py") == set()
        assert _named_in(ast.parse('p = "xbrl.json"'), "backend/app/services/copilot_service.py") == {"backend/tests/fixtures/x/xbrl.json"}
        # The artifact exemption covers a bare name only: a path to that name is a committed file, even in evals/.
        assert _named_in(ast.parse('p = "fixtures/x/xbrl.json"'), "backend/evals/copilot_bootstrap.py") == {"backend/tests/fixtures/x/xbrl.json"}
        # A literal is normalised before matching, so a `..` in the middle of a path does not hide the file.
        assert _named_in(ast.parse('p = "evals/../tests/fixtures/x/xbrl.json"'), "backend/app/x.py") == {"backend/tests/fixtures/x/xbrl.json"}
        # A bare name reaches only backend/ files: the frontend copy of the font and a committed evidence copy of
        # the run's report are not what the run reads. A path of two or more segments prefers backend/ and
        # otherwise reaches the whole repository; a leading `..` reaches it unconditionally.
        assert _named_in(ast.parse(f'p = ASSETS / "fonts" / "{font}"'), "backend/app/services/pdf_branding.py") == {f"backend/app/assets/fonts/{font}"}
        assert _named_in(ast.parse(f'p = "fonts/{font}"'), "backend/app/services/pdf_branding.py") == {f"backend/app/assets/fonts/{font}"}
        assert _named_in(ast.parse(f'p = "../frontend/scripts/brand/fonts/{font}"'), "backend/app/x.py") == {f"frontend/scripts/brand/fonts/{font}"}
        assert _named_in(ast.parse("out = output / 'copilot-eval.md'"), "backend/evals/copilot_runner.py") == set()
        assert _named_in(ast.parse("p = 'copilot-eval.md'"), "backend/app/x.py") == {"backend/tests/fixtures/copilot-eval.md"}
        assert _named_in(ast.parse('p = "CONFIGURATION.md"'), "backend/app/x.py") == set()
        assert _named_in(ast.parse('p = ROOT / "docs" / "CONFIGURATION.md"'), "backend/app/x.py") == set()  # one segment per literal: bare names
        for literal in ('"docs/CONFIGURATION.md"', '"/../docs/CONFIGURATION.md"', '"../docs/CONFIGURATION.md"'):
            assert _named_in(ast.parse(f"p = {literal}"), "backend/evals/copilot_runner.py") == {"docs/CONFIGURATION.md"}, literal
        # The segments must end the tracked path: `assets/x.woff2` is not `assets/fonts/x.woff2`.
        assert _named_in(ast.parse(f'p = "assets/{font}"'), "backend/app/x.py") == set()
        # A `.py` run by path is a named file (the closure walk sees only imports).
        assert _named_in(ast.parse('subprocess.run(["python", "scripts/seed.py"])'), "backend/app/x.py") == {"backend/scripts/seed.py"}
        # A spelled directory names every tracked file under it; a bare directory name is an ordinary word. The two
        # directories are real and pinned non-empty (one under backend/, one outside), so each assertion can fail.
        under = {p for p in TRACKED if p.startswith("backend/tests/fixtures/table_units/") and not p.endswith("/.gitignore")}
        workflows = {p for p in TRACKED if p.startswith(".github/workflows/") and not p.endswith("/.gitignore")}
        assert under and workflows, "the directories these cases name have moved; pick two tracked ones"
        assert _named_in(ast.parse('d = "table_units"; e = "workflows"'), "backend/app/x.py") == set()
        assert _named_in(ast.parse('d = "fixtures/table_units"'), "backend/app/x.py") == under
        assert _named_in(ast.parse('d = ".github/workflows"'), "backend/app/x.py") == workflows
        # In an eval module a bare name is also a sibling folder (`with_name`), every tracked file under it
        # except a `.gitignore`; from an app module, or for `evals/` itself, it is not.
        baselines = {p for p in TRACKED if p.startswith("backend/evals/baselines/") and not p.endswith("/.gitignore")}
        assert baselines and "backend/evals/reports/.gitignore" in TRACKED
        assert _named_in(ast.parse('d = Path(__file__).with_name("baselines"); r = Path(__file__).with_name("reports")'), "backend/evals/copilot_runner.py") == baselines
        for spelling in ('Path(__file__).parent / "baselines"', 'Path(__file__).parent.joinpath("baselines")', 'os.path.join(os.path.dirname(__file__), "baselines")'):
            assert _named_in(ast.parse(f"d = {spelling}"), "backend/evals/copilot_runner.py") == baselines, spelling
        # A bare word that builds no path (a dict key, a column name) is not a folder, even in an eval module.
        assert _named_in(ast.parse('rows = report.get("baselines"); cols = {"baselines": 1}; t = "baselines"'), "backend/evals/copilot_runner.py") == set()
        # A glob names the directory before its first pattern segment: spelled, beside the module, or the module's own.
        assert _named_in(ast.parse('fs = Path(__file__).resolve().parents[1].glob("tests/fixtures/table_units/*")'), "backend/evals/copilot_runner.py") == under
        assert _named_in(ast.parse('fs = Path(__file__).parent.glob("baselines/*.md"); gs = Path(__file__).parent.rglob("baselines/**/*.json")'), "backend/evals/copilot_runner.py") == baselines
        # A bare pattern on the module's own directory names what the pattern matches there, one level for `glob` and
        # every level for `rglob`, so a `glob("copilot_*.json")` refactor names the two copilot inputs and nothing else.
        beside_module = {p for p in TRACKED if p.startswith("backend/evals/") and p.count("/") == 2 and p.endswith(".md")}
        all_evals_md = {p for p in TRACKED if p.startswith("backend/evals/") and p.endswith(".md")}
        assert beside_module and all_evals_md - beside_module
        assert _named_in(ast.parse('fs = Path(__file__).parent.glob("*.md")'), "backend/evals/copilot_runner.py") == beside_module
        assert _named_in(ast.parse('fs = Path(__file__).parent.rglob("*.md")'), "backend/evals/copilot_runner.py") == all_evals_md
        copilot_json = {p for p in TRACKED if p.startswith("backend/evals/copilot_") and p.count("/") == 2 and p.endswith(".json")}
        assert copilot_json and copilot_json < {p for p in TRACKED if p.startswith("backend/evals/copilot_")}
        assert _named_in(ast.parse('fs = Path(__file__).parent.glob("copilot_*.json")'), "backend/evals/copilot_runner.py") == copilot_json
        for alias in ("D = H", "D: Path = H", "D: Final[Path] = H", "x = (D := H)"):  # an alias of an alias, however assigned
            assert _named_in(ast.parse("H = Path(__file__).resolve().parent" + chr(10) + alias + chr(10) + "x = list(D.glob('*.md'))"), "backend/evals/copilot_runner.py") == beside_module, alias
        assert _named_in(ast.parse("HERE: Path = Path(__file__).parent" + chr(10) + "Q = HERE / 'baselines'"), "backend/evals/copilot_runner.py") == baselines
        # The module file may be held in a name, and the directory wrapped in `abspath`, `realpath` or `Path(...)`.
        for spelling in ("THIS = Path(__file__).resolve()" + chr(10) + "d = THIS.parent / 'baselines'",
                         "THIS: Path = Path(__file__)" + chr(10) + "d = Path(THIS).with_name('baselines')",
                         "F = __file__" + chr(10) + "d = os.path.join(os.path.dirname(F), 'baselines')",
                         "d = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'baselines')",
                         "d = Path(os.path.dirname(__file__)) / 'baselines'",
                         "HERE = os.path.dirname(__file__)" + chr(10) + "d = Path(os.path.realpath(HERE)) / 'baselines'"):
            assert _named_in(ast.parse(spelling), "backend/evals/copilot_runner.py") == baselines, spelling
        services_py = {p for p in TRACKED if p.startswith("backend/app/services/") and p.count("/") == 3 and p.endswith(".py")}
        assert services_py
        assert _named_in(ast.parse('fs = Path(__file__).parent.glob("*.py")'), "backend/app/services/x.py") == services_py
        assert _named_in(ast.parse('x = "*"; y = "a*b"; r = re.compile("</?[A-Za-z][^>]*>")'), "backend/evals/copilot_runner.py") == set()
        # A glob with a directory part spells that directory wherever the literal sits and whatever the receiver, and names
        # what its pattern matches there.
        top_fixtures = {p for p in TRACKED if p.startswith("backend/tests/fixtures/") and p.count("/") == 3 and not p.endswith("/.gitignore")}
        json_fixtures = {p for p in TRACKED if p.startswith("backend/tests/fixtures/") and p.endswith(".json")}
        assert top_fixtures and json_fixtures - top_fixtures
        assert _named_in(ast.parse('fs = BACKEND.glob("tests/fixtures/*"); z = "baselines/*"'), "backend/evals/copilot_runner.py") == top_fixtures | baselines
        assert _named_in(ast.parse('fs = BACKEND.glob("tests/fixtures/**/*.json")'), "backend/evals/copilot_runner.py") == json_fixtures
        # `rglob(p)` is `glob("**/" + p)`: the recursion comes before the directory, which a spelled directory matches at
        # any depth already, so `rglob("tests/fixtures/*.json")` is the JSON directly under that directory, and
        # `glob("**/name")` is the bare name `name`.
        assert json_fixtures & top_fixtures and json_fixtures - top_fixtures
        assert _named_in(ast.parse('gs = BACKEND.rglob("tests/fixtures/*.json")'), "backend/evals/copilot_runner.py") == json_fixtures & top_fixtures
        assert _named_in(ast.parse('gs = BACKEND.glob("**/tests/fixtures/*.json")'), "backend/evals/copilot_runner.py") == json_fixtures & top_fixtures
        facts = {p for p in NAMED_CANDIDATES.get("companyfacts_sample.json", []) if p.startswith("backend/")}  # a bare name reaches backend/ only
        assert facts
        for spelling in ('BACKEND.glob("**/companyfacts_sample.json")', 'BACKEND.rglob("companyfacts_sample.json")', 'BACKEND.rglob(pattern="companyfacts_sample.json")'):
            assert _named_in(ast.parse(f"f = next({spelling}, None)"), "backend/evals/copilot_runner.py") == facts, spelling
        assert _named_in(ast.parse('fs = Path(__file__).parent.rglob(pattern="*.md")'), "backend/evals/copilot_runner.py") == all_evals_md
        assert _named_in(ast.parse('fs = Path(__file__).parent.rglob(f"{stem}*.md")'), "backend/evals/copilot_runner.py") == all_evals_md
        # A bare pattern with a leading `..` is matched that many directories above the module, not in its own.
        backend_txt = {p for p in TRACKED if p.startswith("backend/") and p.count("/") == 1 and p.endswith(".txt")}
        root_md = {p for p in TRACKED if "/" not in p and p.endswith(".md")}
        assert backend_txt and root_md
        assert _named_in(ast.parse('fs = Path(__file__).parent.glob("../*.txt")'), "backend/evals/copilot_runner.py") == backend_txt
        assert _named_in(ast.parse('fs = os.path.join(os.path.dirname(__file__), "../../*.md")'), "backend/evals/copilot_runner.py") == root_md
        assert _named_in(ast.parse('fs = parents[1].glob("../*.txt")'), "backend/evals/copilot_runner.py") == set()
        # A `..` path anchored on the module's own location resolves there: `../assets` from `app/services/` is
        # `app/assets`, not every `assets` directory in the repository (the frontend ships one too).
        app_assets = {p for p in TRACKED if p.startswith("backend/app/assets/") and not p.endswith("/.gitignore")}
        assert app_assets, "backend/app/assets/ has no tracked files; pick another directory beside app/services/"
        assert _named_in(ast.parse('d = Path(__file__).parent / "../assets"'), "backend/app/services/x.py") == app_assets
        assert _named_in(ast.parse('d = os.path.join(os.path.dirname(__file__), "../requirements.txt"); e = Path(__file__).parent / "../nothing-here.txt"'), "backend/evals/copilot_runner.py") == {"backend/requirements.txt"}
        assert _named_in(ast.parse('fs = Path(__file__).parent.glob("../app/assets/*")'), "backend/evals/copilot_runner.py") == {p for p in app_assets if p.count("/") == 3}
        # The constant operands of a `join` build one path, resolved on the module's directory as Python resolves it:
        # `join(dir, "..", "data", "x.json")` from `app/services/` is `app/data/x.json`. A lone `..` or `.` so joined
        # names nothing: the parent directory is not what the code reads.
        data_file = sorted(p for p in TRACKED if p.startswith("backend/app/data/") and p.count("/") == 3 and not p.endswith("/.gitignore"))
        assert data_file, "backend/app/data/ holds no tracked file; pick another data directory under app/"
        assert _named_in(ast.parse(f'd = os.path.join(os.path.dirname(__file__), "..", "data", "{data_file[0].rsplit("/", 1)[1]}"); e = Path(__file__).parent / ".." / "data"'), "backend/app/services/x.py") == {data_file[0]}
        assert _named_in(ast.parse('d = os.path.join(os.path.dirname(__file__), "..", "requirements.txt"); b = os.path.abspath(os.path.join(os.path.dirname(__file__), "..")); c = Path(__file__).parent / "."'), "backend/evals/copilot_runner.py") == {"backend/requirements.txt"}
        # A `..` in a later operand climbs from the operand before it, as Python resolves the joined path: from
        # `backend/evals/`, `baselines/../../app/config.py` is `backend/app/config.py` (climbing two levels from the
        # module's directory would leave it at the repository root, where it does not exist).
        assert "backend/app/config.py" in TRACKED and "app/config.py" not in TRACKED
        for spelling in ('os.path.join(os.path.dirname(__file__), "baselines", "../../app/config.py")', 'Path(__file__).parent.joinpath("baselines", "../../app/config.py")', 'Path(Path(__file__).parent, "baselines", "../../app/config.py")'):
            assert _named_in(ast.parse(f"d = {spelling}"), "backend/evals/copilot_runner.py") == {"backend/app/config.py"}, spelling
        # A pattern after a sibling folder is matched there, not on the module's directory: `join(dir, "baselines",
        # "*.json")` reads the JSON directly under `baselines/`, neither every file there nor the JSON beside the module
        # (the summary eval's data, deliberate non-triggers, which the code does not read). A `..` before the pattern
        # climbs back: `join(dir, "baselines", "../*.json")` is the JSON beside the module, loudly.
        evals_all = {p for p in TRACKED if p.startswith("backend/evals/") and not p.endswith("/.gitignore")}
        beside_json = {p for p in evals_all if p.count("/") == 2 and p.endswith(".json")}
        baselines_json = {p for p in baselines if p.count("/") == 3 and p.endswith(".json")}
        assert baselines_json and baselines_json < baselines and beside_json & {f"backend/{p}" for p in SUMMARY_EVAL_DATA}
        for spelling in ('glob.glob(os.path.join(os.path.dirname(__file__), "baselines", "*.json"))', 'Path(__file__).parent.joinpath("baselines", "*.json")',
                         'glob.glob(Path(Path(__file__).parent, "baselines", "*.json"))', 'glob.glob(os.path.join(os.path.dirname(__file__), f"baselines", "*.json"))'):
            assert _named_in(ast.parse(f"fs = {spelling}"), "backend/evals/copilot_runner.py") == baselines_json, spelling
        for spelling in ('glob.glob(os.path.join(os.path.dirname(__file__), "baselines", "../*.json"))', 'Path(__file__).parent.joinpath("reports", "../*.json")', 'glob.glob(Path(Path(__file__).parent, "reports", "../*.json"))'):
            assert _named_in(ast.parse(f"fs = {spelling}"), "backend/evals/copilot_runner.py") == beside_json, spelling
        assert _named_in(ast.parse('fs = glob.glob(os.path.join(os.path.dirname(__file__), "reports", "../../*.txt"))'), "backend/evals/copilot_runner.py") == backend_txt
        # A literal joined to the module's own location is read where Python reads it: `join(dir, "probe.md")`,
        # `dir / "probe.md"` and `with_name("probe.md")` are the file beside the module, not every `probe.md` under
        # `backend/`, and `join(dir, "baselines", "probe.md")` or `dir / "baselines" / "probe.md"` is the one under
        # `baselines/`. The probe files are injected, so the case holds whatever the tree holds.
        probe = {"backend/evals/probe.md", "backend/evals/baselines/probe.md", "backend/app/probe.md"}
        with mock.patch.object(sys.modules[__name__], "TRACKED", TRACKED | probe), mock.patch.dict(NAMED_CANDIDATES, {"probe.md": sorted(probe)}):
            for spelling in ('os.path.join(os.path.dirname(__file__), "probe.md")', 'Path(__file__).parent / "probe.md"', 'Path(__file__).with_name("probe.md")'):
                assert _named_in(ast.parse(f"d = {spelling}"), "backend/evals/copilot_runner.py") == {"backend/evals/probe.md"}, spelling
            assert _named_in(ast.parse('d = Path(__file__).parent.joinpath("baselines", "probe.md")'), "backend/evals/copilot_runner.py") == {"backend/evals/baselines/probe.md"}
            assert _named_in(ast.parse('d = Path(__file__).parent / "baselines" / "probe.md"'), "backend/evals/copilot_runner.py") == {"backend/evals/baselines/probe.md"}
            # `here = abspath(here)` keeps `here` exact (a mixed name would read the probe as spelled too, all three copies).
            assert _named_in(ast.parse("here = os.path.dirname(__file__)\nhere = os.path.abspath(here)\nd = os.path.join(here, 'probe.md')"), "backend/evals/copilot_runner.py") == {"backend/evals/probe.md"}
        readmes = {p for p in TRACKED if p.startswith("backend/") and p.endswith("/README.md")}
        assert len(readmes) > 1
        # A name or an f-string operand ends the path: the literals after it are bare words (a directory this gate
        # cannot know), while a first operand that is an f-string reads as a `glob` of it would.
        for spelling in ('glob.glob(os.path.join(os.path.dirname(__file__), sub, "*.json"))', 'Path(__file__).parent.joinpath(f"{sub}", "*.json")'):
            assert _named_in(ast.parse(f"fs = {spelling}"), "backend/evals/copilot_runner.py") == set(), spelling
        assert _named_in(ast.parse('fs = glob.glob(os.path.join(os.path.dirname(__file__), "baselines", f"{stem}.json"))'), "backend/evals/copilot_runner.py") == baselines  # the prefix, every file under it
        assert _named_in(ast.parse('fs = glob.glob(os.path.join(os.path.dirname(__file__), f"{stem}*.md"))'), "backend/evals/copilot_runner.py") == beside_module
        # A `**` operand reads every level below the module's directory, after the climb of a `..` before it:
        # `join(dir, "**", "*.json")` is every JSON under the directory, `join(dir, "**", "baselines", "*.json")` every
        # `baselines/*.json` below it, `join(dir, "..", "**", "baselines", "*.json")` (or the one-literal glob of it)
        # every one below the parent, and `join(dir, "**", "routers")` every `routers` below it and everything under one.
        assert _named_in(ast.parse('fs = glob.glob(os.path.join(os.path.dirname(__file__), "**", "*.json"), recursive=True)'), "backend/evals/copilot_runner.py") == {p for p in evals_all if p.endswith(".json")}
        # (The expected sets follow the reading's own rule, every such directory below the root, so a fixture or a
        # baseline added under another directory of that name elsewhere cannot turn this gate red.)
        def below(root: str, directory: str, suffix: str) -> set[str]:
            return {p for p in TRACKED if p.startswith(root) and p.endswith(suffix) and p.split("/")[-2] == directory}
        assert _named_in(ast.parse('fs = glob.glob(os.path.join(os.path.dirname(__file__), "**", "baselines", "*.json"), recursive=True)'), "backend/evals/copilot_runner.py") == below("backend/evals/", "baselines", ".json")
        assert _named_in(ast.parse('fs = glob.glob(os.path.join(os.path.dirname(__file__), "**", "fixtures", "*.json"), recursive=True)'), "backend/tests/x.py") == below("backend/tests/", "fixtures", ".json")
        for spelling in ('glob.glob(os.path.join(os.path.dirname(__file__), "..", "**", "baselines", "*.json"), recursive=True)', 'Path(__file__).parent.glob("../**/baselines/*.json")'):
            assert _named_in(ast.parse(f"fs = {spelling}"), "backend/evals/copilot_runner.py") == below("backend/", "baselines", ".json"), spelling
        routers = {p for p in TRACKED if p.startswith("backend/app/") and "/routers/" in p[len("backend/app"):] and not p.endswith("/.gitignore")}
        assert routers
        assert _named_in(ast.parse('fs = glob.glob(os.path.join(os.path.dirname(__file__), "**", "routers"), recursive=True)'), "backend/app/x.py") == routers
        # A name also bound to something else (the module's directory in one function and `parents[1]`, a parameter or
        # a loop target elsewhere) anchors its literals still, and they are read as spelled too: the fixture below is
        # reported, not only resolved to a path beside the module that does not exist, while a bare pattern, a listing
        # or a sibling folder on such a name stays loud. A name assigned the module's directory twice, or from itself
        # (`here = abspath(here)`), is exact.
        assert "backend/tests/fixtures/companyfacts_sample.json" in TRACKED and "backend/evals/copilot_golden_set.json" in TRACKED
        shadowed = ("def a():\n    root = Path(__file__).parent\n    return root / 'copilot_golden_set.json'\n"
                    "def b():\n    root = Path(__file__).resolve().parents[1]\n    return root / 'tests/fixtures/companyfacts_sample.json'\n")
        assert {"backend/evals/copilot_golden_set.json", "backend/tests/fixtures/companyfacts_sample.json"} <= _named_in(ast.parse(shadowed), "backend/evals/copilot_runner.py")
        for spelling in ("here = os.path.dirname(__file__)\ndef load(here):\n    return os.path.join(here, 'tests/fixtures/companyfacts_sample.json')\n",
                         "here = os.path.dirname(__file__)\nfor here in dirs:\n    f = os.path.join(here, 'tests/fixtures/companyfacts_sample.json')\n",
                         "here = os.path.dirname(__file__)\nhere = output\nf = os.path.join(here, 'tests/fixtures/companyfacts_sample.json')\n"):
            assert "backend/tests/fixtures/companyfacts_sample.json" in _named_in(ast.parse(spelling), "backend/evals/copilot_runner.py"), spelling
        assert _named_in(ast.parse("HERE = Path(__file__).parent\nHERE = Path(__file__).resolve().parent\nd = HERE / 'baselines'"), "backend/evals/copilot_runner.py") == baselines
        assert _named_in(ast.parse("here = os.path.dirname(__file__)\nhere = os.path.abspath(here)\nfs = glob.glob(os.path.join(here, 'baselines', '*.json'))"), "backend/evals/copilot_runner.py") == baselines_json
        for spelling in ("def a():\n    here = os.path.dirname(__file__)\n    return glob.glob(os.path.join(here, '*.json'))\ndef b(here):\n    return here\n",
                         "here = os.path.dirname(__file__)\nfor here in dirs:\n    fs = glob.glob(os.path.join(here, '*.json'))\n"):
            assert _named_in(ast.parse(spelling), "backend/evals/copilot_runner.py") == beside_json, spelling
        assert _named_in(ast.parse("here = os.path.dirname(__file__)\nfor here in dirs:\n    fs = os.listdir(here)\n"), "backend/evals/copilot_runner.py") == {p for p in evals_all if p.count("/") == 2}
        assert _named_in(ast.parse("def a(root):\n    return root\ndef b():\n    root = Path(__file__).parent\n    return root / 'baselines'\n"), "backend/evals/copilot_runner.py") == baselines
        copied = ("def a():\n    root = Path(__file__).parent\n    return root / 'copilot_golden_set.json'\n"
                  "def b():\n    root = Path(__file__).resolve().parents[1]\n    base = root\n    return base / 'tests/fixtures/companyfacts_sample.json'\n")
        assert {"backend/evals/copilot_golden_set.json", "backend/tests/fixtures/companyfacts_sample.json"} <= _named_in(ast.parse(copied), "backend/evals/copilot_runner.py")  # `base` is mixed through `root`
        assert "backend/tests/fixtures/companyfacts_sample.json" in _named_in(ast.parse("here = os.path.dirname(__file__)\nfor here in dirs:\n    data = here\n    f = os.path.join(data, 'tests/fixtures/companyfacts_sample.json')\n"), "backend/evals/copilot_runner.py")
        assert _named_in(ast.parse("def a():\n    base = Path(__file__).parent\n    return base / 'routers'\ndef b(base):\n    return base\n"), "backend/app/x.py") == routers
        assert _named_in(ast.parse("A = Path(__file__).parent\nB = A\nC = B\nQ = C / 'baselines'"), "backend/evals/copilot_runner.py") == baselines
        nested = "try:\n    try:\n        A = Path(__file__).resolve().parent\n    except NameError:\n        raise\n    B = A\nexcept ImportError:\n    raise\nC = B\nq = C / 'baselines'\n"
        assert _named_in(ast.parse(nested), "backend/evals/copilot_runner.py") == baselines  # whatever order `ast.walk` visits the chain in
        # The directory glued to a literal by `+` or inside an f-string anchors it, its leading slash dropped, as `join`
        # does; `str(...)` or `os.fspath(...)` around the directory is seen through; a suffix without a slash is another
        # directory and names nothing.
        for spelling in ('glob.glob(os.path.dirname(__file__) + "/*.json")', 'glob.glob(str(Path(__file__).parent) + "/*.json")', 'glob.glob(f"{Path(__file__).parent}/*.json")',
                         'glob.glob(f"{os.fspath(Path(__file__).parent)}/*.json")'):
            assert _named_in(ast.parse(f"fs = {spelling}"), "backend/evals/copilot_runner.py") == beside_json, spelling
        for spelling in ("HERE = os.path.dirname(__file__)\nfs = glob.glob(HERE + '/*.json')\n", "HERE = Path(__file__).parent\nfs = glob.glob(f'{HERE}/*.json')\n"):
            assert _named_in(ast.parse(spelling), "backend/evals/copilot_runner.py") == beside_json, spelling
        for spelling in ('Path(f"{Path(__file__).parent}/baselines")', 'os.path.dirname(__file__) + "/baselines"', 'f"{os.path.dirname(__file__)}/baselines/"'):
            assert _named_in(ast.parse(f"d = {spelling}"), "backend/evals/copilot_runner.py") == baselines, spelling
        assert _named_in(ast.parse('d = os.path.dirname(__file__) + "baselines"; e = f"{Path(__file__).parent}baselines"; g = out + "/*.json"; h = f"{out}/baselines"'), "backend/evals/copilot_runner.py") == set()  # `evalsbaselines`, not `evals/baselines`
        # A `+` chain is the one string it builds, `os.sep` a slash; a name assigned the directory with a `/` or `os.sep`
        # appended is the directory, and a literal glued to it needs no slash; `+=` onto the directory name reads its
        # literal beside the module (and leaves the name mixed); `str(...)`/`os.fspath(...)` around the module file are
        # seen through too; a chain that spells only `/`, or a name after the `/`, names nothing.
        for spelling in ('glob.glob(os.path.dirname(__file__) + "/" + "*.json")', 'glob.glob(os.path.dirname(__file__) + os.sep + "*.json")',
                         'glob.glob(os.path.dirname(__file__) + os.path.sep + "*" + ".json")', 'glob.glob(os.path.dirname(os.fspath(Path(__file__).resolve())) + "/*.json")',
                         'glob.glob(os.path.dirname(str(Path(__file__))) + "/*.json")'):
            assert _named_in(ast.parse(f"fs = {spelling}"), "backend/evals/copilot_runner.py") == beside_json, spelling
        for spelling in ("HERE = os.path.dirname(os.path.abspath(__file__)) + '/'\nfs = glob.glob(HERE + '*.json')\n",
                         "HERE = os.path.dirname(__file__) + os.sep\nfs = glob.glob(os.path.join(HERE, '*.json'))\n",
                         "HERE = os.path.dirname(__file__) + '/'\nfs = glob.glob(f'{HERE}*.json')\n",
                         "HERE: str = str(Path(__file__).parent) + '/'\nfs = glob.glob(HERE + '/*.json')\n",
                         "HERE = f'{os.path.dirname(__file__)}/'\nfs = glob.glob(HERE + '*.json')\n",
                         "HERE = f'{Path(__file__).parent}'\nfs = glob.glob(HERE + '/*.json')\n",
                         "HERE = f'{Path(__file__).parent}'\nfs = glob.glob(os.path.join(HERE, '*.json'))\n"):
            assert _named_in(ast.parse(spelling), "backend/evals/copilot_runner.py") == beside_json, spelling
        assert _named_in(ast.parse("HERE = os.path.dirname(__file__) + '/'\nfs = os.listdir(HERE)\n"), "backend/evals/copilot_runner.py") == {p for p in evals_all if p.count("/") == 2}
        assert _named_in(ast.parse("p = os.path.dirname(__file__)\np += '/baselines'\n"), "backend/evals/copilot_runner.py") == baselines
        assert _named_in(ast.parse("def a(root):\n    return root\ndef b():\n    root = Path(__file__).parent\n    HERE = str(root) + '/'\n    return glob.glob(HERE + '*.json')\n"), "backend/evals/copilot_runner.py") == beside_json
        slashed = ("def a():\n    root = Path(__file__).parent\n    return root / 'copilot_golden_set.json'\n"
                   "def b():\n    root = Path(__file__).resolve().parents[1]\n    HERE = str(root) + '/'\n    return glob.glob(HERE + 'tests/fixtures/companyfacts_sample.json')\n")
        assert {"backend/evals/copilot_golden_set.json", "backend/tests/fixtures/companyfacts_sample.json"} <= _named_in(ast.parse(slashed), "backend/evals/copilot_runner.py")  # `HERE` is mixed through `root`, so its literal is read as spelled too
        assert _named_in(ast.parse('d = os.path.dirname(__file__) + "/"; e = os.path.dirname(__file__) + "/" + sub; g = HERE + "baselines"; h = os.path.dirname(__file__) + sep + "*.json"'), "backend/evals/copilot_runner.py") == set()
        assert _named_in(ast.parse("HERE = f'{Path(__file__).parent}'\nfs = glob.glob(HERE + 'baselines')\n"), "backend/evals/copilot_runner.py") == set()  # `evalsbaselines` again
        # `os.sep` inside an f-string is a slash too, and the parts after the directory are one string; the right side of
        # `+=` is a chain as well.
        for spelling in ("fs = glob.glob(f'{os.path.dirname(__file__)}{os.sep}*.json')\n", "fs = glob.glob(f'{Path(__file__).parent}{os.path.sep}*.json')\n",
                         "HERE = f'{os.path.dirname(__file__)}{os.sep}'\nfs = glob.glob(HERE + '*.json')\n", "HERE = f'{os.path.dirname(__file__)}{os.path.sep}'\nfs = os.listdir(HERE)\n"):
            expected = {p for p in evals_all if p.count("/") == 2} if "listdir" in spelling else beside_json
            assert _named_in(ast.parse(spelling), "backend/evals/copilot_runner.py") == expected, spelling
        for spelling in ("B = os.path.dirname(__file__)\nB += os.sep + 'baselines'\n", "B = os.path.dirname(__file__)\nB += '/' + 'baselines'\n", "B = os.path.dirname(__file__)\nB += '/' + 'base' + 'lines'\n"):
            assert _named_in(ast.parse(spelling), "backend/evals/copilot_runner.py") == baselines, spelling
        assert _named_in(ast.parse("B = os.path.dirname(__file__)\nB += os.sep + sub\nfs = glob.glob(f'{os.path.dirname(__file__)}{sep}*.json')\n"), "backend/evals/copilot_runner.py") == set()
        # The string is folded once, whatever builds it: a `%` or `.format` template, `sep.join`, `join(dir, "")`, a
        # `sep` imported from `os`, an f-string ending in a slash as the left operand, `p += os.sep` then `p + x`.
        for spelling in ('glob.glob("%s/*.json" % os.path.dirname(__file__))', 'glob.glob("%s%s*.json" % (os.path.dirname(__file__), os.sep))',
                         'glob.glob("{}/*.json".format(Path(__file__).parent))', 'glob.glob("{0}/{1}".format(os.path.dirname(__file__), "*.json"))',
                         'glob.glob("{here}/*.json".format(here=os.path.dirname(__file__)))', 'glob.glob(os.sep.join([os.path.dirname(__file__), "*.json"]))',
                         'glob.glob("/".join((str(Path(__file__).parent), "*.json")))', 'glob.glob(os.path.join(os.path.dirname(__file__), "") + "*.json")',
                         'glob.glob(f"{os.path.dirname(__file__)}/" + "*.json")', 'glob.glob(f"{os.path.dirname(__file__)}{os.sep}" "*.json")'):
            assert _named_in(ast.parse(f"fs = {spelling}"), "backend/evals/copilot_runner.py") == beside_json, spelling
        for spelling in ("from os import sep\nfs = glob.glob(os.path.dirname(__file__) + sep + '*.json')\n", "from os.path import sep as SEP\nfs = glob.glob(f'{Path(__file__).parent}{SEP}*.json')\n",
                         "p = os.path.dirname(__file__)\np += os.sep\nfs = glob.glob(p + '*.json')\n", "p = os.path.dirname(__file__)\np += '/'\nfs = glob.glob('%s*.json' % p)\n"):
            assert _named_in(ast.parse(spelling), "backend/evals/copilot_runner.py") == beside_json, spelling
        assert _named_in(ast.parse("HERE = os.path.dirname(__file__) + '/'\nHERE += 'baselines'\n"), "backend/evals/copilot_runner.py") == baselines
        assert _named_in(ast.parse('d = "%s/%s" % (os.path.dirname(__file__), sub); e = "%d/*.json" % n; g = "{}/*.json".format(out); h = "{:>3}/x".format(os.path.dirname(__file__)); i = "%s_backup" % os.path.dirname(__file__); j = ", ".join([os.path.dirname(__file__), "*.json"])'),
                         "backend/evals/copilot_runner.py") == set()
        # A `..` or `.` head followed by a name names nothing: a lone `..` names nothing, and the name is the limit of a
        # variable (`join(dir, "..", sub)` reads somewhere under the parent, which the gate cannot narrow without naming
        # all of it).
        for spelling in ('os.path.join(os.path.dirname(__file__), "..", sub)', 'Path(Path(__file__).parent, "..", sub)', 'Path(__file__).parent / ".." / sub'):
            assert _named_in(ast.parse(f"d = {spelling}"), "backend/evals/copilot_runner.py") == set(), spelling
        # `rglob("name")` or `glob("**/name")` on the module's own directory reads every `name` below it and everything
        # under one, as `join(dir, "**", "name")` does; on another receiver `glob("**/name")` is the bare name.
        for spelling in ('Path(__file__).parent.rglob("routers")', 'Path(__file__).parent.glob("**/routers")', 'glob.glob("**/routers", root_dir=os.path.dirname(__file__), recursive=True)'):
            assert _named_in(ast.parse(f"fs = {spelling}"), "backend/app/x.py") == routers, spelling
        backend_all = {p for p in TRACKED if p.startswith("backend/") and not p.endswith("/.gitignore")}
        assert _named_in(ast.parse('fs = glob.glob("../**", root_dir=os.path.dirname(__file__), recursive=True)'), "backend/evals/copilot_runner.py") == backend_all
        fixtures_all = {p for p in TRACKED if p.startswith("backend/tests/fixtures/") and not p.endswith("/.gitignore")}
        assert fixtures_all <= _named_in(ast.parse('fs = Path(__file__).parent.rglob("../tests/fixtures")'), "backend/evals/copilot_runner.py")
        # `parents[0]` is the module's directory; `os.walk` and `Path.walk()` of it read every level, as `rglob("*")` does.
        assert _named_in(ast.parse('d = Path(__file__).resolve().parents[0] / "baselines"'), "backend/evals/copilot_runner.py") == baselines
        every_evals = {p for p in TRACKED if p.startswith("backend/evals/") and not p.endswith("/.gitignore")}
        assert every_evals - {p for p in every_evals if p.count("/") == 2}  # a nested file, so every level differs from one
        for spelling in ("w = os.walk(os.path.dirname(__file__))", "w = Path(__file__).parent.walk()", "w = Path(__file__).resolve().parents[0].walk()"):
            assert _named_in(ast.parse(spelling), "backend/evals/copilot_runner.py") == every_evals, spelling
        assert _named_in(ast.parse('w = os.walk(out); v = output.walk(); u = os.walk(Path(__file__).resolve().parents[1])'), "backend/evals/copilot_runner.py") == set()
        assert _named_in(ast.parse('w = os.walk(top=os.path.dirname(__file__))'), "backend/evals/copilot_runner.py") == every_evals
        # `rglob("../p")` with a plain operand reads every `p` below the climbed directory, more than pathlib's
        # `**/../p` does; the excess is loud, never silent.
        assert _named_in(ast.parse('fs = Path(__file__).parent.rglob("../README.md")'), "backend/evals/copilot_runner.py") == readmes
        # `iterdir()`, `listdir` and `scandir` on the module's directory read what `glob("*")` reads; `glob.glob`
        # with `root_dir=` that directory anchors its pattern there; a tuple assignment creates an alias too.
        one_level = {p for p in TRACKED if p.startswith("backend/evals/") and p.count("/") == 2 and not p.endswith("/.gitignore")}
        for spelling in ("fs = list(Path(__file__).parent.iterdir())", "fs = os.listdir(os.path.dirname(__file__))", "fs = os.scandir(Path(__file__).parent)"):
            assert _named_in(ast.parse(spelling), "backend/evals/copilot_runner.py") == one_level, spelling
        assert _named_in(ast.parse('fs = os.listdir(output); gs = list(out.iterdir())'), "backend/evals/copilot_runner.py") == set()
        assert _named_in(ast.parse('fs = glob.glob("*.md", root_dir=os.path.dirname(__file__)); gs = glob.glob("*.json", root_dir=out)'), "backend/evals/copilot_runner.py") == beside_module
        for spelling in ('fs = glob.iglob("*.md", root_dir=os.path.dirname(__file__))', 'fs = glob("*.md", root_dir=Path(__file__).parent)', 'fs = os.scandir(path=Path(__file__).parent); gs = os.listdir(path=os.path.dirname(__file__))'):
            assert _named_in(ast.parse(spelling), "backend/evals/copilot_runner.py") in (beside_module, one_level), spelling
        assert _named_in(ast.parse("HERE, OUT = Path(__file__).parent, None" + chr(10) + "d = HERE / 'baselines'"), "backend/evals/copilot_runner.py") == baselines
        # Every spelling that builds a path from the module counts: a `Path` constructor, a bare `join` on a name assigned
        # the module's directory, a keyword argument, an f-string.
        for spelling in ('Path(Path(__file__).parent, "baselines")', 'Path(__file__).with_name(name="baselines")', 'Path(__file__).parent / f"baselines"'):
            assert _named_in(ast.parse(f"d = {spelling}"), "backend/evals/copilot_runner.py") == baselines, spelling
        assert _named_in(ast.parse("here = Path(__file__).parent" + chr(10) + "d = join(here, 'baselines')"), "backend/evals/copilot_runner.py") == baselines
        # A literal joined to any other receiver builds no path beside the module: the run's output directory, a parameter,
        # the runner's own `REPORTS_DIR = Path(__file__).with_name("reports")` (a sibling, not the module's directory),
        # `parents[1]`.
        assert _named_in(ast.parse('a = output.joinpath("baselines"); b = out / "baselines"; c = list(output.glob("*.json")); d = Path(out, "baselines")'), "backend/evals/copilot_runner.py") == set()
        assert _named_in(ast.parse('R = Path(__file__).with_name("reports"); x = list(R.glob("*.json")); y = list(Path(__file__).resolve().parents[1].glob("*.py"))'), "backend/evals/copilot_runner.py") == set()
        # `with_name`, `.parent`, `dirname` and `Path(...)` anchor only on the module file itself.
        for spelling in ('output.with_name("baselines")', 'out.parent / "baselines"', 'os.path.join(os.path.dirname(output), "baselines")', 'Path(out).parent / "baselines"', 'Path(output).with_name("baselines")',
                         'Path(os.path.abspath(out)) / "baselines"', 'Path(os.path.realpath(output)).glob("*.md")'):
            assert _named_in(ast.parse(f"d = {spelling}"), "backend/evals/copilot_runner.py") == set(), spelling
        assert _named_in(ast.parse("OTHER = Path(out).resolve()" + chr(10) + "d = OTHER.parent / 'baselines'; e = OTHER.with_name('baselines')"), "backend/evals/copilot_runner.py") == set()
        assert _named_in(ast.parse('d = "baselines"; e = "evals"'), "backend/app/x.py") == set()
        assert _named_in(ast.parse('e = "evals"'), "backend/evals/copilot_runner.py") == set()
        assert _named_in(ast.parse('d = Path(__file__).with_name("baselines")'), "backend/evals/sub/x.py") == set()  # beside the module only
    with mock.patch.dict(NAMED_CANDIDATES, {"package.json": ["frontend/package.json"]}):  # injected: the case holds whatever the frontend tree holds
        assert _named_in(ast.parse('p = "package.json"'), "backend/app/x.py") == set()
        for literal in ('"frontend/package.json"', '"../frontend/package.json"'):
            assert _named_in(ast.parse(f"p = {literal}"), "backend/app/x.py") == {"frontend/package.json"}, literal
    assert _named_in(ast.parse('d = "tests/fixtures"'), "backend/app/x.py") == {p for p in TRACKED if p.startswith("backend/tests/fixtures/") and not p.endswith("/.gitignore")}
    # The live index holds tracked `.py` files too, so a script run by path is named.
    script = next(p for p in sorted(TRACKED) if p.startswith("backend/scripts/") and p.endswith(".py"))
    assert _named_in(ast.parse(f'subprocess.run(["python", "{script[len("backend/"):]}"])'), "backend/app/x.py") == {script}
    # A tests fixture named by a closure module would be reported, because every tracked file counts.
    fixture = next(
        p for p in sorted(TRACKED)
        if p.startswith("backend/tests/fixtures/") and not p.endswith(".py") and len(NAMED_CANDIDATES[p.rsplit("/", 1)[-1]]) == 1
    )
    assert _named_in(ast.parse(f'f = Path("{fixture}")')) == {fixture}
    closure = reachable_files()
    assert "backend/evals/copilot_golden_set.json" in named_files(closure)
    written = {
        node.value.rsplit("/", 1)[-1]
        for path in closure
        for node in ast.walk(ast.parse((ROOT / path).read_text(encoding="utf-8")))
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    stale = sorted(RUN_ARTIFACTS - written)
    assert not stale, f"RUN_ARTIFACTS names artifacts the eval no longer writes: {stale}"


def test_every_file_under_evals_is_classified():
    patterns, closure = workflow_filter(), reachable_files()
    known = set(non_triggers(closure)) | closure
    unclassified = [p for p in sorted(TRACKED) if p.startswith("backend/evals/") and not triggers(p, patterns) and p not in known]
    assert not unclassified, (
        "a new file under backend/evals/ is classified deliberately: a Copilot input joins the filter, summary-eval data joins "
        f"SUMMARY_EVAL_DATA (the filter's `copilot_*` does not cross a `/`): {unclassified}"
    )


def test_every_filter_pattern_matches_an_input_of_the_eval():
    closure = reachable_files()
    used = closure | set(runtime_inputs(closure))
    idle = [raw for raw in workflow_filter() if not raw.startswith("!") and not any(_pattern(raw).match(p) for p in used)]
    assert not idle, f"copilot-eval.yml paths that match nothing the eval uses would pay for runs that cannot change its result: {idle}"


def test_filter_matcher_follows_github_semantics():
    assert triggers("backend/app/services/ai/copilot_chat.py", ["backend/app/services/ai/**"])
    assert not triggers("backend/app/services/ai/x.py", ["backend/app/services/*"])
    # The filter's two `.github/` entries are exact files; a directory glob there would pay for every CI edit.
    assert ".github/workflows/ci.yml" in non_triggers(reachable_files()) and not triggers(".github/workflows/ci.yml", workflow_filter())
    assert triggers(".github/workflows/ci.yml", [".github/**"])
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
