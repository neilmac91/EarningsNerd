"""Gate for lessons/test-never-point-a-written-file-at-dev-null.md: no tracked code gives git the null device
as a file it writes.

Git writes its config and its index through a lock file that it renames over the target. As root, which cloud
sessions are, a write through GIT_CONFIG_GLOBAL, GIT_CONFIG_SYSTEM, GIT_CONFIG or GIT_INDEX_FILE naming the null
device, or through `git config --file` naming it, therefore replaces the device with an ordinary file.
tests/conftest.py's null-device checks see that only in a root run, after the damage; this gate finds the
pattern in source on any runner, CI's included.

A Python file is read as its syntax tree, so formatting cannot hide the pattern: a mapping, a subscript assignment,
a keyword or a pair of call arguments that gives one of those variables the device, or a `git config` sequence that
gives it as the file, where the device is `os.devnull`, "/dev/null", a name the file binds to either (plainly,
annotated, by unpacking or with `:=`) or imports under a name of its own (`from os import devnull as NULL`), or any
of those inside calls (`str(os.devnull)`), an f-string or a conditional; and a string, literal or built with an
f-string or `+`, that holds the shell form. Every other tracked program is searched for the shell form: a code
file by its suffix, a build or container file by its name (`Makefile`, `Dockerfile`), a dotenv file, and any file
in the executable mode or opening with `#!`, whatever whitespace
separates its parts and whatever comes between `config` and its file option in one command. The file option is read
as git's option parser reads it: `--file` or its abbreviation `--fil`, and `-f` alone or after other short options,
the file after `=`, attached or next. A device that reaches git from another module, a string built any other way
(`%`, `str.format`, a join) or out of variables, a linker's `-o` and an atomic writer's target stay review-checked,
with conftest's process guard and null-device checks behind them; curl's `-o` writes in place and leaves the device
alone.
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
    # git config's file option later in the same command (a continued line counts; `;`, `&` or `|` ends it).
    rf"|\bconfig\b(?:[^\n;&|]|\\\n)*?(?<![\w-])(?:--fil(?:e)?(?:=|[\s\"',]+)|-[a-eg-zA-Z]*f[\s\"',]*)[\"'(]*{NULL}"
)
# One word of git config's file option, as conftest's process guard reads it: `--file` or `--fil`, the file after
# `=` or in the next word; `-f` alone or after other short options (`-zf`), the file attached or in the next word.
CONFIG_FILE_OPTION = re.compile(r"--fil(?:e)?(?:=(?P<long>.*))?|-[a-eg-zA-Z]*f(?P<short>.*)")
CODE = {".py", ".sh", ".bash", ".yml", ".yaml", ".toml", ".cfg", ".ini", ".json", ".js", ".mjs", ".cjs", ".ts", ".tsx"}
# Files that run commands or set their environment by name rather than by suffix.
PROGRAM_NAMES = {"Dockerfile", "Containerfile", "Makefile", "GNUmakefile", "makefile", "Justfile", "justfile",
                 "Procfile"}


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
        """The names this node binds to the device: `NAME = ...`, `NAME: str = ...`, `(NAME := ...)`, each
        name of an unpacking whose matching value is the device (`NULL, OTHER = os.devnull, path`), and the device
        imported under a name of its own (`from os import devnull as NULL`)."""
        if isinstance(node, ast.ImportFrom) and node.module in ("os", "os.path"):
            return [alias.asname or alias.name for alias in node.names if alias.name == "devnull"]
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
        value = node.value if isinstance(node, ast.Constant) else None
        return (value.decode(errors="replace") if isinstance(value, bytes) else value) in GIT_VARIABLES

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
        if isinstance(node.value, (str, bytes)) and id(node) not in self.docstrings \
                and SHELL_FORM.search(self._text(node)):
            self.lines.append(node.lineno)

    def visit_JoinedStr(self, node: ast.JoinedStr) -> None:
        self._built_shell_form(node)

    def visit_BinOp(self, node: ast.BinOp) -> None:
        self._built_shell_form(node)

    def _built_shell_form(self, node: ast.JoinedStr | ast.BinOp) -> None:
        if SHELL_FORM.search(self._text(node)):
            self.lines.append(node.lineno)
        self.generic_visit(node)

    def _text(self, node: ast.AST | None) -> str:
        """The text a string expression builds, the device written `/dev/null` and any part it cannot read a
        NUL: a literal (a byte string decoded), an f-string, a `+` of them, or the device itself."""
        if isinstance(node, ast.Constant) and isinstance(node.value, (str, bytes)):
            return node.value if isinstance(node.value, str) else node.value.decode(errors="replace")
        if isinstance(node, ast.JoinedStr):
            return "".join(self._text(part.value if isinstance(part, ast.FormattedValue) else part)
                           for part in node.values)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return self._text(node.left) + self._text(node.right)
        return NULL_PATH if self._null(node) else "\0"

    def _config_file(self, items: list[ast.expr]) -> None:
        """`git config`, or the `git-config` program git keeps for it, given the device as its file in a sequence
        of arguments."""
        words = [self._text(item) for item in items]
        if not any(word == "config" or word.rsplit("/", 1)[-1] == "git-config" for word in words):
            return
        for index, word in enumerate(words):
            option = CONFIG_FILE_OPTION.fullmatch(word)
            attached = option and (option["long"] or option["short"])
            if option and (attached or (words[index + 1] if index + 1 < len(words) else None)) == NULL_PATH:
                self.lines.append(items[index].lineno)


def _hits(path: Path, text: str) -> list[int]:
    if path.suffix == ".py":
        try:
            return _NullTargets(ast.parse(text)).lines
        except SyntaxError:
            pass  # read it as text instead
    return [text.count("\n", 0, match.start()) + 1 for match in SHELL_FORM.finditer(text)]


def _is_program(path: Path, mode: str, head: bytes) -> bool:
    """Whether a tracked file is a program the gate reads: a code suffix, a build or container file by name, a
    `.mk` file, a dotenv file, the executable mode (`git ls-files -s`'s 100755) or a `#!` line. Prose and records
    (Markdown, text, logs) may describe the pattern."""
    return (path.suffix in CODE or path.name in PROGRAM_NAMES or path.suffix == ".mk" or path.name.startswith(".env")
            or mode == "100755" or head.startswith(b"#!"))


def _tracked_code() -> list[Path]:
    """Every tracked program but this file, whose cases name the pattern on purpose."""
    listed = subprocess.run(["git", "ls-files", "-s", "-z"], cwd=ROOT, capture_output=True, check=True).stdout
    found = []
    for entry in listed.decode("utf-8").split("\0"):
        info, _, name = entry.partition("\t")  # <mode> <object> <stage>, then the path
        path = ROOT / name
        if not name or path.resolve() == Path(__file__).resolve() or not path.is_file():
            continue
        with path.open("rb") as handle:
            head = handle.read(2)
        if _is_program(path, info.split(" ", 1)[0], head):
            found.append(path)
    return found


@pytest.mark.parametrize(("name", "mode", "head", "program"), [
    ("tools/run", "100755", b"set -e\n", True),  # executable, without a suffix or a #! line
    ("tools/run", "100644", b"#!/bin/sh\n", True),
    ("Makefile", "100644", b"all:\n", True),
    ("build/rules.mk", "100644", b"x:\n", True),
    ("frontend/.env.local", "100644", b"A=1\n", True),
    ("backend/Dockerfile", "100644", b"FROM x\n", True),
    ("scripts/sync.sh", "100644", b"set -e\n", True),
    ("tasks/notes", "100644", b"plain\n", False),
    ("lessons/a.md", "100644", b"# a\n", False),
    ("tasks/run.log", "100644", b"$ git\n", False),
])
def test_the_gate_reads_every_tracked_program(name, mode, head, program):
    assert _is_program(Path(name), mode, head) is program


def test_no_tracked_code_gives_git_the_null_device_to_write():
    hits = []
    for path in _tracked_code():
        text = path.read_text(encoding="utf-8", errors="replace")
        hits += [f"{path.relative_to(ROOT)}:{line}" for line in sorted(set(_hits(path, text)))]
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
    'subprocess.run(["git", "config", "-f/dev/null", "a.b", "c"])',  # the file attached to -f
    'subprocess.run(["git", "config", "-zf", os.devnull, "a.b", "c"])',  # -f after another short option
    'subprocess.run(["git", "config", "--fil", os.devnull, "a.b", "c"])',  # git takes the abbreviation
    'subprocess.run(["git", "config", f"--file={os.devnull}", "a.b", "c"])',  # built by an f-string
    'subprocess.run(["git", "config", "-f" + os.devnull, "a.b", "c"])',  # or by +
    'subprocess.run("GIT_CONFIG_GLOBAL=/dev/null git config a.b c", shell=True)',  # the shell form in a string
    'os.system(f"git config -f{os.devnull} a.b c")',  # a shell line built by an f-string
    'os.system("GIT_CONFIG_GLOBAL=" + os.devnull + " git config a.b c")',  # or by +
    'env = {b"GIT_CONFIG_GLOBAL": b"/dev/null"}',  # byte strings
    'env[b"GIT_INDEX_FILE"] = os.devnull',
    'subprocess.run([b"git", b"config", b"-f", os.fsencode(os.devnull), b"a.b", b"c"])',
    'subprocess.run(b"GIT_CONFIG_SYSTEM=/dev/null git config a.b c", shell=True)',
    'subprocess.run([f"{programs}/git-config", "-f", os.devnull, "a.b", "c"])',  # the git-config program
    'subprocess.run(["/usr/lib/git-core/git-config", "--file=/dev/null", "a.b", "c"])',
    'from os import devnull as NULL\nos.execv("/usr/bin/git", ["git", "config", "-f", NULL, "a.b", "c"])',  # imported
    'from os.path import devnull as SINK\nenv["GIT_CONFIG_GLOBAL"] = SINK',
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
    'subprocess.run(["git", "config", f"--file={tmp_path / \'c\'}", "a.b", "c"])',  # a file of its own
    'subprocess.run(["git", "config", "--global", "core.excludesFile", os.devnull])',  # the device as a value
    'os.system("git status > " + os.devnull)',  # a redirect
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
    "git config -f/dev/null a.b c",  # the file attached to -f
    "git config -zf /dev/null a.b c",  # -f after another short option
    "git config --fil=/dev/null a.b c",  # git takes the abbreviation
    "git config --type bool -f /dev/null a.b true",  # other options first
    "git config \\\n  --file /dev/null a.b c",  # a continued line
    '["git", "config", "-f/dev/null", "a.b", "c"]',
    '"$(git --exec-path)/git-config" -f /dev/null a.b c',  # the git-config program
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
    "git config --global core.excludesFile /dev/null",  # the device as a value, in the global config
    "git config -f ./c a.b c 2>/dev/null",  # a redirect after a file of its own
    "git config a.b c && ln -sf /dev/null x",  # another command on the line
    "git config alias.x-f /dev/null",  # a key that ends in -f, given the device as its value
])
def test_the_gate_passes_shell_that_leaves_the_device_alone(text):
    assert not SHELL_FORM.search(text)
