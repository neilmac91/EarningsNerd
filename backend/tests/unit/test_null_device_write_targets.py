"""Gate for lessons/test-never-point-a-written-file-at-dev-null.md: no tracked code gives git the null device
as a file it writes.

Git writes its config and its index through a lock file that it renames over the target. As root, which cloud
sessions are, a write through GIT_CONFIG_GLOBAL, GIT_CONFIG_SYSTEM, GIT_CONFIG or GIT_INDEX_FILE naming the null
device, or through `git config --file` naming it, therefore replaces the device with an ordinary file.
tests/conftest.py's `_null_device_survives` sees that only in a root run, after the damage; this gate finds the
pattern in source on any runner, CI's included.

A Python file is read as its syntax tree, so formatting cannot hide the pattern: a mapping, a subscript
assignment, a keyword or a pair of call arguments that gives one of those variables the device, or a
`git config --file` sequence that names it, where the device is `os.devnull`, "/dev/null", a name the file binds
to either (plainly, annotated, by unpacking or with `:=`), or any of those inside calls (`str(os.devnull)`), an
f-string or a conditional; and a string that holds the shell form. Other code files are searched for the shell
form, whatever whitespace separates its parts. A device that reaches git from another
module, a linker's `-o` and an atomic writer's target stay review-checked, with `_null_device_survives` behind
them in a root run; curl's `-o` writes in place and leaves the device alone.
"""
from __future__ import annotations

import ast
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
GIT_VARIABLES = {"GIT_CONFIG_GLOBAL", "GIT_CONFIG_SYSTEM", "GIT_CONFIG", "GIT_INDEX_FILE"}
NULL_PATH = "/dev/null"
NULL = r"(?:[\w.]+\(\s*['\"]?)*(?:os\.devnull|/dev/null)"  # wrapped in calls or not: str(os.devnull)
SHELL_FORM = re.compile(
    # A variable naming a file git writes: `NAME=`, `NAME: ` (YAML, JSON), `"NAME", ` (an argument pair).
    rf"GIT_(?:CONFIG(?:_GLOBAL|_SYSTEM)?|INDEX_FILE)[\s\"'\])]*[:=,][\s\"'(\[]*{NULL}"
    rf"|\bconfig\b[\s\"',]*(?:--file|-f)(?:=|[\s\"',]+)[\"'(]*{NULL}"  # git config --file
)
CODE = {".py", ".sh", ".bash", ".yml", ".yaml", ".toml", ".cfg", ".ini", ".json", ".js", ".mjs", ".cjs", ".ts", ".tsx"}


class _NullTargets(ast.NodeVisitor):
    """The lines where a Python syntax tree gives git the null device as a file it writes."""

    def __init__(self, tree: ast.AST) -> None:
        self.lines: list[int] = []
        self.names: set[str] = set()
        while True:  # a name bound to the device, or to such a name, however long the chain
            bound = {name for node in ast.walk(tree) for name in self._bound(node)}
            if bound <= self.names:
                break
            self.names |= bound
        self.docstrings = {id(node.body[0].value) for node in ast.walk(tree)
                           if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                           and node.body and isinstance(node.body[0], ast.Expr)
                           and isinstance(node.body[0].value, ast.Constant)}
        self.visit(tree)

    def _bound(self, node: ast.AST) -> list[str]:
        """The names this node binds to the device: `NAME = ...`, `NAME: str = ...`, `(NAME := ...)`, and each
        name of an unpacking whose matching value is the device (`NULL, OTHER = os.devnull, path`)."""
        if isinstance(node, ast.Assign):
            pairs = [(target, node.value) for target in node.targets]
        elif isinstance(node, (ast.AnnAssign, ast.NamedExpr)):
            pairs = [(node.target, node.value)]
        else:
            return []
        names = []
        while pairs:
            target, value = pairs.pop()
            if isinstance(target, ast.Name) and self._null(value):
                names.append(target.id)
            elif isinstance(target, (ast.Tuple, ast.List)) and isinstance(value, (ast.Tuple, ast.List)):
                pairs += list(zip(target.elts, value.elts))
        return names

    def _null(self, node: ast.AST | None) -> bool:
        if isinstance(node, ast.Constant):
            return node.value in (NULL_PATH, NULL_PATH.encode())
        if isinstance(node, ast.Attribute):
            return node.attr == "devnull"
        if isinstance(node, ast.Name):
            return node.id == "devnull" or node.id in self.names
        if isinstance(node, ast.Call):
            return any(self._null(arg) for arg in node.args)
        if isinstance(node, ast.JoinedStr):
            return any(self._null(part.value if isinstance(part, ast.FormattedValue) else part) for part in node.values)
        if isinstance(node, ast.IfExp):
            return self._null(node.body) or self._null(node.orelse)
        return False

    @staticmethod
    def _git_variable(node: ast.AST | None) -> bool:
        return isinstance(node, ast.Constant) and node.value in GIT_VARIABLES

    def visit_Dict(self, node: ast.Dict) -> None:
        self.lines += [value.lineno for key, value in zip(node.keys, node.values)
                       if self._git_variable(key) and self._null(value)]
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        if any(isinstance(target, ast.Subscript) and self._git_variable(target.slice) for target in node.targets) \
                and self._null(node.value):
            self.lines.append(node.lineno)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if isinstance(node.target, ast.Subscript) and self._git_variable(node.target.slice) \
                and self._null(node.value):
            self.lines.append(node.lineno)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        self.lines += [keyword.value.lineno for keyword in node.keywords
                       if keyword.arg in GIT_VARIABLES and self._null(keyword.value)]
        self.lines += [value.lineno for name, value in zip(node.args, node.args[1:])
                       if self._git_variable(name) and self._null(value)]  # setenv("GIT_CONFIG_GLOBAL", ...)
        self._config_file(node.args)
        self.generic_visit(node)

    def visit_List(self, node: ast.List) -> None:
        self._config_file(node.elts)
        self.generic_visit(node)

    def visit_Tuple(self, node: ast.Tuple) -> None:
        self._config_file(node.elts)
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, str) and id(node) not in self.docstrings and SHELL_FORM.search(node.value):
            self.lines.append(node.lineno)

    def _config_file(self, items: list[ast.expr]) -> None:
        """`git config --file <the device>` written as a sequence of arguments."""
        words = [item.value if isinstance(item, ast.Constant) and isinstance(item.value, str) else None
                 for item in items]
        if "config" not in words:
            return
        for index, word in enumerate(words):
            if (word in ("--file", "-f") and index + 1 < len(items) and self._null(items[index + 1])) or \
                    word == f"--file={NULL_PATH}":
                self.lines.append(items[index].lineno)


def _hits(path: Path, text: str) -> list[int]:
    if path.suffix == ".py":
        try:
            return _NullTargets(ast.parse(text)).lines
        except SyntaxError:
            pass  # read it as text instead
    return [text.count("\n", 0, match.start()) + 1 for match in SHELL_FORM.finditer(text)]


def _tracked_code() -> list[Path]:
    """Every tracked code file but this one, whose cases name the pattern on purpose. Prose (Markdown) may
    describe it."""
    listed = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout
    paths = [ROOT / name for name in listed.decode("utf-8").split("\0") if name]
    return [path for path in paths if (path.suffix in CODE or path.name == "Dockerfile")
            and path.resolve() != Path(__file__).resolve() and path.is_file()]


def test_no_tracked_code_gives_git_the_null_device_to_write():
    hits = []
    for path in _tracked_code():
        text = path.read_text(encoding="utf-8", errors="replace")
        hits += [f"{path.relative_to(ROOT)}:{line}" for line in _hits(path, text)]
    assert not hits, (
        "Git renames its lock file over a config or index file it writes, which as root replaces the null "
        "device. Give git an empty file in the test's own temp directory instead "
        "(lessons/test-never-point-a-written-file-at-dev-null.md):\n" + "\n".join(hits))


@pytest.mark.parametrize("code", [
    'env = {"GIT_CONFIG_GLOBAL": os.devnull}',
    "env = {**os.environ, 'GIT_CONFIG_SYSTEM': '/dev/null'}",
    'env = {\n    "GIT_CONFIG_GLOBAL": (\n        str(os.devnull)\n    ),\n}',  # formatting
    'env["GIT_INDEX_FILE"] = os.devnull',
    'monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)',
    "env = dict(os.environ, GIT_CONFIG=os.fspath(Path('/dev/null')))",
    'NULL = os.devnull\nCONFIG = NULL\nenv["GIT_CONFIG_GLOBAL"] = CONFIG',  # a name the file binds
    'A = os.devnull\nB = A\nC = B\nD = C\nenv["GIT_CONFIG_GLOBAL"] = D',  # however long the chain
    'NULL: str = os.devnull\nenv["GIT_CONFIG_GLOBAL"] = NULL',  # annotated
    'NULL, OTHER = os.devnull, "x"\nenv["GIT_CONFIG_GLOBAL"] = NULL',  # unpacked
    'if (NULL := os.devnull):\n    env["GIT_CONFIG_GLOBAL"] = NULL',  # bound with :=
    'env["GIT_INDEX_FILE"]: str = os.devnull',  # an annotated subscript
    'env = {"GIT_CONFIG_GLOBAL": f"{os.devnull}"}',
    'env = {"GIT_CONFIG_GLOBAL": os.devnull if fast else str(tmp_path / "config")}',
    'subprocess.run(["git", "config", "--file", str(os.devnull), "a.b", "c"])',
    'subprocess.run(("git", "config", "-f", "/dev/null", "a.b", "c"))',
    'subprocess.run(["git", "config", "--file=/dev/null", "a.b", "c"])',
    'subprocess.run("GIT_CONFIG_GLOBAL=/dev/null git config a.b c", shell=True)',  # the shell form in a string
])
def test_the_gate_finds_each_python_form(code):
    assert _NullTargets(ast.parse(code)).lines, code


@pytest.mark.parametrize("code", [
    "subprocess.run(cmd, stdout=subprocess.DEVNULL)",
    'with open(os.devnull, "w") as sink:\n    pass',
    'env["GIT_CONFIG_GLOBAL"] = str(tmp_path / "gitconfig")',
    'env = {"GIT_CONFIG_NOSYSTEM": "1", "NULL": os.devnull}',
    'subprocess.run(["git", "-c", "core.hooksPath=/dev/null", "commit", "-m", "x"])',  # a path git reads
    'subprocess.run(["git", "config", "--file", str(tmp_path / "c"), "a.b", "c"], stdout=open(os.devnull, "w"))',
    'def f():\n    """GIT_CONFIG_GLOBAL=/dev/null would replace the device."""\n',  # a docstring describes it
    "# GIT_CONFIG_GLOBAL=/dev/null in a comment\nx = 1",
])
def test_the_gate_passes_python_that_leaves_the_device_alone(code):
    assert not _NullTargets(ast.parse(code)).lines, code


@pytest.mark.parametrize("text", [
    "GIT_CONFIG=/dev/null git config user.name x",
    "GIT_CONFIG_GLOBAL: /dev/null",  # a workflow step's env
    "git config -f /dev/null a.b c",
    "git config --file=/dev/null a.b c",
    "GIT_CONFIG_GLOBAL:          /dev/null",  # any whitespace between the parts
    "git config --file          /dev/null a.b c",
    "env:\n  GIT_CONFIG_GLOBAL:\n    /dev/null",  # a YAML value on the next line
    'process.env.GIT_INDEX_FILE = "/dev/null";',
    "export GIT_CONFIG_SYSTEM='/dev/null'",
    '["git", "config", "--file", "/dev/null", "a.b", "c"]',  # an argument list in another language
])
def test_the_gate_finds_each_shell_form(text):
    assert SHELL_FORM.search(text)


@pytest.mark.parametrize("text", [
    "curl -sS -o /dev/null -w '%{http_code}' https://example.com",  # writes in place
    "GIT_CONFIG_NOSYSTEM=1 git status",
    "git -c core.hooksPath=/dev/null commit -m x",  # a path git reads
    "GIT_CONFIG_KEY_0=core.excludesFile GIT_CONFIG_VALUE_0=/dev/null git check-ignore x",  # a value, not a file
    "make build > /dev/null 2>&1",
    "GIT_CONFIG_NOSYSTEM: '1'\nOUT:          /dev/null",
    "curl -sS -o          /dev/null https://example.com",
])
def test_the_gate_passes_shell_that_leaves_the_device_alone(text):
    assert not SHELL_FORM.search(text)
