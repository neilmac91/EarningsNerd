"""Gate for `.claude/hooks/secret_scan_guard.py`, the PreToolUse hook that runs CI's pinned gitleaks over what a
push or a GitHub content write would add, and refuses the call on a finding (E126), and git's pre-push hook, which
runs the same scan as git sends a push and stops it on a finding (E134;
lessons/ops-a-secret-shaped-literal-on-any-branch-fails-every-pr.md).

A case runs the hook the way `.claude/settings.json` registers it (the registered command, through the shell, on the
event Claude Code sends) in a scratch project, except the ones on the deadline, an unexpected error, a recursion, a
deep input, git's version strings, a refusal's git lines, a failed scan's errors, the downloads and the installer,
which call its functions in this process. The project is a git repository holding copies of both hooks and CI's
workflow, whose `refs/remotes/origin/main` stands for GitHub's main, with a branch `work` that carries one commit
holding a planted credential-shaped line and a branch `clean` with one clean commit, neither on GitHub, and beside
it a second repository, `elsewhere`, whose own `work` is clean: a case that moves into the project from there is
refused only if the hook follows the move. Each test process builds the project once and each case runs in a copy.
No case reads the machine's own git configuration, attributes or ignores.

A stub gitleaks, installed where `--install` puts the pinned binary, reads what gitleaks reads (`git log -p -U0`
over --log-opts in the directory it scans, the -i file, and that directory's own .gitleaksignore and .gitleaks.toml,
or the rules --config, GITLEAKS_CONFIG or GITLEAKS_CONFIG_TOML name, each as gitleaks takes one: anything there but
a directory, a link to /dev/null among them), honours `gitleaks:allow`, finds nothing under rules that neither
extend gitleaks' own nor define one, and flags the planted value, which this file builds at run time so its own text
matches no rule. It reads git's plain output more strictly than gitleaks: a line it cannot place under a full commit
header and a `b/` path (colour, another format, an abbreviated commit, decorations, no prefixes) shows it nothing,
where gitleaks still reports the line under all of them but colour, and under a commit main's pins do not match when
the commit is abbreviated or missing. The settings the hook holds that can hide a line from the stub (colour, the
big-file threshold, a root commit's lines, attributes from a file, a tree, a worktree, a bare repository's HEAD or
the git directory, a text conversion, copies, a replace ref, the commit header, decorations, prefixes), fail the
scan (shown signatures) or keep a graft from failing it closed (a silenced graft hint) are each planted in the
repository itself, where only the hook's pin (for a text conversion, its --no-textconv) keeps the case passing on a
git that reads it (diff.dstPrefix from 2.45 on, a bare repository's HEAD from 2.43 to 2.45). The rest, which keep
CI's hunks, dates, paths and encoding or let the scan read another user's checkout (safe.directory), are not. On a
git older than 2.43, which knows no attr.tree, or one whose version the hook cannot read, the hook refuses each call
that adds commits, as it does a scan that would read a repository whose objects are not SHA-1. Outside CI, the cases
that build a scratch project skip on a git that this file reads as older than 2.43, or whose version it cannot read;
on CI they run, so a git too old there fails the suite. With the pinned binary installed (`--install`), the cases
that turn on how gitleaks reads its files and git's output run against it as well; CI installs none and skips them.

git's pre-push hook, .claude/hooks/git/pre-push, runs the hook with --pre-push in a clone whose core.hooksPath names
its directory by its absolute path, which .claude/settings.json's SessionStart command sets in a cloud session's
clone. Its cases push for real, outside any Claude Code hook, with origin's pushes sent to a bare repository beside
the project, so git itself runs the hook on the refs it sends: the pushes the PreToolUse reading cannot see (a
script's, a program's, a git a variable names), the places a push runs from where git would miss a relative hooks
path (inside .git, a GIT_DIR or --git-dir from a subdirectory or from outside the worktree) and the forms a push
takes (a branch, HEAD under another name, a source with a space, every branch, a mirror, a tag, a force push), each
stopped before git sends any ref; a clean push, scanned and sent; a delete and a commit GitHub holds, sent unscanned;
a push from a linked worktree; a tag of a tree or a blob; a missing binary; and a line git hands the hook that it
cannot read. `--no-verify`, which skips git's hooks, and a hook git cannot execute are planted as pushes that go
through, so the hook's tracked mode is held. The session's start sets the absolute path in a cloud session only
(CLAUDE_CODE_REMOTE=true), and --turn-on in any clone, saying so: each names the main checkout's directory from a
linked worktree, and from a project below the clone's top, writes its own path spelled otherwise (a relative one, or
a worktree's own copy) as the main checkout's, keeps a hooks path set at any level (the session's environment, the
worktree's, the clone's, the user's and the machine's) and a clone's own hooks (a linked worktree's among them),
sets the path where git keeps no hooks directory, sets none where the main checkout holds no hook or there is no
main checkout to find (a --separate-git-dir or bare clone's linked worktree), and says why the hook is off where git
cannot read the clone or set the path, the start fails or git hangs, and when the pinned binary is missing; the
commands its notes name quote the path, and it reads git in English whatever the session's language.

Planted below: the forms a push takes; the pushes the hook must read precisely, which name the clean branch from the
planted one, so a push read whole would be refused; the commands that may and may not come before a push or run
beside it, redirections among them; the moves of the shell's directory and the variables it follows, the ones bash
does not keep, the ways a command that may or may not run leaves them (a redirection that may fail among them, and
the functions it defines), and the ones that leave a directory it cannot name; the words bash reads as no reserved
word or operator (a quoted one, a case's pattern, a loop's name, one after a process substitution, an array's
assignment); the parameter expansions the shell reader splits, refused (a nested quote or backquote in a
double-quoted one, and a `<<` bash reads in a word, among them); a redirection after two closing words, which belongs
to the outer compound, and a `{name}` descriptor's ambiguous copy and close; a line too long to read in time; the
settings, files and refs that would blind the scan or fail it; the API writes; the MCP writes; and the look-alikes
that must pass. Each gap the hook's header names that a case can stand for is planted as one that passes through,
with the files its command names, so closing it is a deliberate change here; a HOME or CDPATH the shell's profile
sets and a push in a session that loads no repository hooks are outside what a case here can run, and git's hook
stops a person's push, and one a GIT_DIR the profile sets steers, as the PRE_PUSHES cases do.
"""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import random
import re
import shlex
import shutil
import string
import subprocess
import sys
import tarfile
import time
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
SETTINGS = ROOT / ".claude" / "settings.json"
HOOK = ROOT / ".claude" / "hooks" / "secret_scan_guard.py"
GUARD = ROOT / ".claude" / "hooks" / "codex_mention_guard.py"
CI = ROOT / ".github" / "workflows" / "ci.yml"
COMMAND = 'python3 -I -S "$CLAUDE_PROJECT_DIR/.claude/hooks/secret_scan_guard.py" || exit 1'
MATCHER = "^(Bash|mcp__.*[Gg][Ii][Tt][Hh][Uu][Bb].*)$"
LESSON = "lessons/ops-a-secret-shaped-literal-on-any-branch-fails-every-pr.md"
PRE_PUSH = ROOT / ".claude" / "hooks" / "git" / "pre-push"
SESSION_COMMAND = 'python3 -I -S "$CLAUDE_PROJECT_DIR/.claude/hooks/secret_scan_guard.py" --session-start || exit 1'
STOPPED = "Refused by .claude/hooks/secret_scan_guard.py, git's pre-push hook: "


def _load():
    spec = importlib.util.spec_from_file_location("secret_scan_guard", HOOK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SCAN = _load()
VERSION, SHA256 = SCAN._pin()
TARGET = SCAN._platform()
# The hook refuses every scan on a git older than 2.43, or one whose version it cannot read (cases below plant
# both), so a case that builds a scratch project skips on a git this file reads so (_make), except on CI, where the
# suite fails instead. The cases that build none run on any git. The version is read here, not by the hook, so that
# a fault in the hook's own reading fails the cases rather than skipping them.
GIT = subprocess.run(["git", "version"], capture_output=True, text=True).stdout.strip()
_READ = re.match(r"git version (\d+)\.(\d+)", GIT)
OLD_GIT = _READ is None or (int(_READ.group(1)), int(_READ.group(2))) < (2, 43)


def _value(seed: int) -> str:
    rng = random.Random(seed)
    return "Pz" + "".join(rng.choice(string.ascii_letters + string.digits) for _ in range(38))


# A line gitleaks' generic-api-key rule flags, built at run time so that no line of this file matches a rule.
LEAK = "api_" + "token = " + '"' + _value(1) + '"'
MARKED = LEAK + "  # gitleaks:allow (a planted test value)"
# What the stub flags: the planted value's shape, so the stub and the real binary flag the same lines.
STUB = r'''#!/usr/bin/env python3
"""A stand-in for gitleaks: it reads the files gitleaks reads and flags the planted value."""
import json, os, re, subprocess, sys, time

PLANTED = re.compile(r'= "Pz[A-Za-z0-9]{38}"')
args = sys.argv[1:]
if os.environ.get("STUB_LOG"):
    with open(os.environ["STUB_LOG"], "a", encoding="utf-8") as handle:
        handle.write(json.dumps({"argv": args, "cwd": os.getcwd(),
                                 "gitleaks_env": sorted(k for k in os.environ if k.startswith("GITLEAKS_"))}) + "\n")
if args == ["version"]:
    print("@VERSION@")
    sys.exit(0)
time.sleep(float(os.environ.get("STUB_SLEEP", "0")))
if os.environ.get("STUB_FAIL"):
    print("error: told to fail", file=sys.stderr)
    sys.exit(1)
if args[:1] != ["git"]:
    sys.exit(2)
source, flags, options, i = args[1], args[2:], {}, 0
while i < len(flags):
    if flags[i].startswith("--") and "=" in flags[i]:
        key, value = flags[i].split("=", 1)
        options[key], i = value, i + 1
    elif flags[i] in ("--no-banner", "--no-color"):
        i += 1
    else:
        options[flags[i]], i = flags[i + 1], i + 2
if options.get("--report-format") != "json":  # the hook reads the report as JSON, so it asks for JSON
    print("error: no JSON report was asked for", file=sys.stderr)
    sys.exit(1)
def readable(path):  # what gitleaks' fileExists takes: anything that is there and no directory, /dev/null among them
    return os.path.exists(path) and not os.path.isdir(path)
pins, ignore = set(), options.get("--gitleaks-ignore-path", ".")
for path in (ignore, os.path.join(ignore, ".gitleaksignore"), os.path.join(source, ".gitleaksignore")):
    if readable(path):
        with open(path, encoding="utf-8") as handle:
            pins.update(line.strip() for line in handle if line.strip() and not line.startswith("#"))
# The rules: --config (or -c), else GITLEAKS_CONFIG's file, else GITLEAKS_CONFIG_TOML's text, else the directory's own.
config = options.get("--config") or options.get("-c") or os.environ.get("GITLEAKS_CONFIG")
rules = "" if config else os.environ.get("GITLEAKS_CONFIG_TOML", "")
config = config or ("" if rules else os.path.join(source, ".gitleaks.toml"))
read = bool(rules)
if config and readable(config):
    rules, read = open(config, encoding="utf-8").read(), True
allow_all = "STUB-ALLOW-ALL" in rules
# Rules that neither extend gitleaks' own (useDefault) nor define one are none, and gitleaks 8.24.3 then finds nothing.
if read and not re.search(r"(?m)^\s*useDefault\s*=\s*true", rules) and "[[rules]]" not in rules:
    PLANTED = re.compile(r"(?!)")
log = subprocess.run(["git", "-C", source, "log", "-p", "-U0", *options["--log-opts"].split(" ")], capture_output=True, text=True)
if log.returncode or log.stderr:  # the stub fails on anything git says on its stderr, as gitleaks does on most of it
    for line in [*(f"ERR [git] {text}" for text in log.stderr.splitlines()),
                 'ERR failed to scan Git repository error="stderr is not empty"', "WRN partial scan completed in 1ms",
                 "WRN no leaks found in partial scan"]:
        print("6:12PM " + line, file=sys.stderr)
    sys.exit(1)
findings, commit, path, number = [], None, None, 0
for line in log.stdout.splitlines():
    if line.startswith(("commit ", "diff --git ")):
        # A full commit header places the lines after it; any other header leaves them unplaced.
        commit = (line.split()[1] if re.fullmatch(r"commit [0-9a-f]{40}", line) else None) if line[0] == "c" else commit
        path = None
    elif line.startswith("+++ "):  # `+++ b/name`, or `+++ "b/name"` when git quotes the name
        path = line[len("+++ b/"):] if line.startswith("+++ b/") else line[len('+++ "b/'):-1] if line.startswith('+++ "b/') else None
    elif line.startswith("@@ "):
        number = int(re.search(r"\+(\d+)", line).group(1))
    elif line.startswith("+") and path is not None and commit is not None:
        fingerprint = f"{commit}:{path}:generic-api-key:{number}"
        if (PLANTED.search(line) and "gitleaks:allow" not in line and not allow_all
                and fingerprint not in pins and f"{path}:generic-api-key:{number}" not in pins):
            findings.append({"RuleID": "generic-api-key", "File": path, "StartLine": number, "Commit": commit,
                             "Secret": "REDACTED", "Match": "REDACTED", "Fingerprint": fingerprint})
        number += 1
if not os.environ.get("STUB_NO_REPORT"):
    with open(options["--report-path"], "w", encoding="utf-8") as handle:
        json.dump(findings, handle)
sys.exit(int(options.get("--exit-code", "1")) if findings else 0)
'''
# A .gitleaks.toml that allows every finding, to the stub (its marker) and to gitleaks (its allowlist).
ALLOW_ALL = "# STUB-ALLOW-ALL\n[extend]\nuseDefault = true\n\n[allowlist]\ndescription = \"everything\"\npaths = ['''.*''']\n"


def _registered() -> list[dict]:
    """The PreToolUse entries of .claude/settings.json that run this hook."""
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    return [
        entry for entry in settings["hooks"]["PreToolUse"]
        if any("secret_scan_guard.py" in hook.get("command", "") for hook in entry["hooks"])
    ]


_NO_GLOBAL_CONFIG: str | None = None


def _no_global_config() -> str:
    """An empty file for GIT_CONFIG_GLOBAL, so a probe's git reads no global configuration without the null device,
    which a git config write renames a lock over and so, as root, replaces with a file
    (lessons/test-never-point-a-written-file-at-dev-null.md). The probes set git's identity with `-c`, never a
    global write, so the file stays empty; one per test process is enough."""
    global _NO_GLOBAL_CONFIG
    if _NO_GLOBAL_CONFIG is None:
        import atexit
        import tempfile
        fd, _NO_GLOBAL_CONFIG = tempfile.mkstemp(prefix="secret-scan-test-noconfig-")
        os.close(fd)
        atexit.register(lambda path=_NO_GLOBAL_CONFIG: os.path.exists(path) and os.unlink(path))
    return _NO_GLOBAL_CONFIG


def _plain_env() -> dict[str, str]:
    """The test's environment without GIT_* (a git hook running pytest sets GIT_DIR) or GITLEAKS_*, with no system
    or global git configuration, attributes or ignores, and with git's messages in English: the machine's own (a
    signing key, colours, aliases, a global `*.py` ignore, a locale) is no case's."""
    env = {key: value for key, value in os.environ.items() if not key.startswith(("GIT_", "GITLEAKS_"))}
    return {**env, "GIT_CONFIG_GLOBAL": _no_global_config(), "GIT_CONFIG_NOSYSTEM": "1", "GIT_ATTR_NOSYSTEM": "1",
            "XDG_CONFIG_HOME": os.devnull,
            "LC_ALL": "C"}


def _real_binary() -> Path | None:
    cache = os.environ.get("XDG_CACHE_HOME", "")
    base = Path(cache) if os.path.isabs(cache) else Path.home() / ".cache"
    path = base / "earningsnerd" / "gitleaks" / f"{VERSION}-{SHA256[:12]}" / str(TARGET) / "gitleaks"
    return path if path.is_file() else None


class Project:
    """A scratch project: a repository holding both hooks and CI's workflow, its main as GitHub has it, and a
    second repository beside it."""

    def __init__(self, root: Path, cache: Path, log: Path):
        self.root, self.cache, self.log = root, cache, log
        self.elsewhere = root.parent / "elsewhere"
        self.leak = ""

    def git(self, *args: str, cwd: Path | None = None, stdin: str | None = None) -> str:
        proc = subprocess.run(
            ["git", "-C", str(cwd or self.root), "-c", "user.name=probe", "-c", "user.email=probe@example.invalid",
             "-c", "protocol.file.allow=always", *args],
            input=stdin, capture_output=True, text=True, env=_plain_env(), check=True)
        return proc.stdout.strip()

    def write(self, files: dict[str, str], cwd: Path | None = None) -> None:
        for name, text in files.items():
            path = (cwd or self.root) / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

    def commit(self, files: dict[str, str], message: str = "change", cwd: Path | None = None) -> str:
        self.write(files, cwd)
        self.git("add", "-A", cwd=cwd)
        self.git("commit", "-qm", message, cwd=cwd)
        return self.git("rev-parse", "HEAD", cwd=cwd)

    def publish(self, branch: str) -> None:
        """Stand for GitHub holding `branch`: its remote-tracking ref points at it."""
        self.git("update-ref", f"refs/remotes/origin/{branch}", branch)

    def binary(self) -> Path:
        return self.cache / "earningsnerd" / "gitleaks" / f"{VERSION}-{SHA256[:12]}" / str(TARGET) / "gitleaks"

    def run(self, event: dict | str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        """Run the command .claude/settings.json registers, as Claude Code does (`/bin/sh -c`), within its timeout."""
        [hook] = [hook for entry in _registered() for hook in entry["hooks"]]
        full = {**_plain_env(), "CLAUDE_PROJECT_DIR": str(self.root), "XDG_CACHE_HOME": str(self.cache),
                "STUB_LOG": str(self.log), **(env or {})}
        stdin = event if isinstance(event, str) else json.dumps(event)
        return subprocess.run(["sh", "-c", hook["command"]], input=stdin, capture_output=True, text=True, env=full,
                              timeout=hook["timeout"])

    def decide(self, tool: str, tool_input: object, cwd: Path | None = None, env: dict[str, str] | None = None) -> str | None:
        """The hook's refusal of this call, or None when it lets the call through."""
        proc = self.run(_event(tool, tool_input, cwd or self.root), env)
        assert proc.returncode == 0, proc.stderr
        if not proc.stdout:
            return None
        parsed = json.loads(proc.stdout)
        # Nothing beside the decision: a top-level "continue": false, for one, would stop Claude's turn.
        assert list(parsed) == ["hookSpecificOutput"]
        output = parsed["hookSpecificOutput"]
        assert sorted(output) == ["hookEventName", "permissionDecision", "permissionDecisionReason"]
        assert (output["hookEventName"], output["permissionDecision"]) == ("PreToolUse", "deny")
        reason = output["permissionDecisionReason"]
        assert reason.startswith("Refused by .claude/hooks/secret_scan_guard.py: ") and reason.endswith(f"({LESSON}).")
        assert _value(1) not in reason  # a refusal never repeats the value it found
        return reason

    def bash(self, command: str, cwd: Path | None = None, env: dict[str, str] | None = None) -> str | None:
        command = command.replace("@REPO@", str(self.root)).replace("@ELSEWHERE@", str(self.elsewhere))
        return self.decide("Bash", {"command": command, "description": "x"}, cwd, env)

    def scans(self) -> list[dict]:
        """The stub's runs so far: its arguments, directory and GITLEAKS_* variables."""
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]

    def remote(self) -> Path:
        """Send origin's pushes to a bare repository beside the project, which stands for GitHub receiving them."""
        remote = self.root.parent / "remote.git"
        self.git("init", "-q", "--bare", str(remote))
        self.git("remote", "set-url", "--push", "origin", str(remote))
        return remote

    def enable(self) -> Path:
        """Turn git's pre-push hook on, as a cloud session's start does (core.hooksPath names its directory by the
        absolute path), with origin's pushes sent to `remote`."""
        remote = self.remote()
        self.git("config", "core.hooksPath", str(self.root.resolve() / SCAN.HOOKS_PATH))
        return remote

    def push(self, command: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        """Run a command that pushes as a person or a script does, outside any Claude Code hook: git runs its own."""
        env = {**_plain_env(), "XDG_CACHE_HOME": str(self.cache), "STUB_LOG": str(self.log)}
        return subprocess.run(["sh", "-c", command], cwd=cwd or self.root, capture_output=True, text=True, env=env,
                              timeout=120)

    def received(self, rev: str) -> bool:
        """Whether the bare repository the pushes reach holds the object `rev` names."""
        remote = self.root.parent / "remote.git"
        proc = subprocess.run(["git", "--git-dir", str(remote), "cat-file", "-e", rev], capture_output=True,
                              env=_plain_env())
        return proc.returncode == 0


def _event(tool: str, tool_input: object, cwd: Path) -> dict:
    return {"session_id": "s", "transcript_path": "/dev/null", "cwd": str(cwd), "permission_mode": "default",
            "hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input, "tool_use_id": "toolu_1"}


def _make(tmp_path: Path, binary: str = "stub", objects: str = "sha1") -> Project:
    """A scratch project built from nothing (the `project` fixture copies one this process built once)."""
    if OLD_GIT and not os.environ.get("CI"):  # never on CI, where a git too old fails the suite
        pytest.skip(f"the hook's scans need git 2.43 or later, and this machine's git reports {GIT!r}")
    root = tmp_path / "project"
    # shutil.copy keeps the pre-push hook's mode, and git runs only a hook it can execute
    for source, folder in ((HOOK, ".claude/hooks"), (GUARD, ".claude/hooks"), (PRE_PUSH, ".claude/hooks/git"),
                           (CI, ".github/workflows")):
        (root / folder).mkdir(parents=True, exist_ok=True)
        shutil.copy(source, root / folder)
    project = Project(root, tmp_path / "cache", tmp_path / "stub.log")
    project.git("init", "-q", "-b", "main", f"--object-format={objects}")
    project.git("remote", "add", "origin", "https://github.com/neilmac91/EarningsNerd")
    project.commit({"a.py": "x = 1\n"}, "base")
    project.publish("main")
    project.git("checkout", "-qb", "clean")
    project.commit({"c.py": "y = 2\n"}, "clean change")
    project.git("checkout", "-qb", "work", "main")
    project.leak = project.commit({"b.py": LEAK + "\n"}, "plant")
    # A repository whose own `work` is clean: a push read there instead of in the project passes.
    project.elsewhere.mkdir()
    project.git("init", "-q", "-b", "main", cwd=project.elsewhere)
    project.commit({"e.py": "e = 1\n"}, "elsewhere", cwd=project.elsewhere)
    project.git("update-ref", "refs/remotes/origin/main", "main", cwd=project.elsewhere)
    project.git("checkout", "-qb", "work", cwd=project.elsewhere)
    project.commit({"f.py": "f = 1\n"}, "clean elsewhere", cwd=project.elsewhere)
    path = project.binary()
    path.parent.mkdir(parents=True)
    if binary == "stub":
        path.write_text(STUB.replace("@VERSION@", VERSION), encoding="utf-8")
        path.chmod(0o755)
    else:
        real = _real_binary()
        if real is None:
            pytest.skip(f"gitleaks {VERSION} is not installed (python3 .claude/hooks/secret_scan_guard.py --install)")
        path.symlink_to(real)
    return project


@pytest.fixture(scope="session")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One project per test process: its two repositories and their git commands are most of a case's cost."""
    base = tmp_path_factory.mktemp("built")
    _make(base)
    return base


@pytest.fixture
def project(tmp_path: Path, built: Path) -> Project:
    shutil.copytree(built, tmp_path, symlinks=True, dirs_exist_ok=True)
    project = Project(tmp_path / "project", tmp_path / "cache", tmp_path / "stub.log")
    project.leak = project.git("rev-parse", "work")
    return project


def _found(reason: str | None, where: str = "b.py:1") -> None:
    assert reason is not None, "the hook let it through"
    assert "secret-shaped literal" in reason and f"{where} (generic-api-key)" in reason, reason
    assert "`# gitleaks:allow`" in reason and "own .gitleaksignore does not count" in reason


def _ordered(reason: str | None) -> None:
    assert reason is not None, "the hook let it through"
    assert "before a push in the same call" in reason and "Bash call of its own" in reason, reason
    assert "(not git clean, which may remove a directory)" in reason, reason


# Each form a push of the branch `work` takes, its one new commit holding the planted line. Each value is the
# command (`@REPO@` is the project's path) and the git commands that set the case up first.
PUSHES = {
    "git push alone": ("git push", []),
    "a remote and the branch": ("git push origin work", []),
    "-u": ("git push -u origin work", []),
    "a refspec with a destination": ("git push origin work:refs/heads/elsewhere", []),
    "a forced refspec from HEAD": ("git push origin +HEAD:work", []),
    "HEAD": ("git push origin HEAD", []),
    "a commit expression as the source": ("git push origin HEAD~0:refs/heads/x", []),
    "a lease and its expected value": ("git push --force-with-lease=work:0123abc origin work", []),
    "clustered short options": ("git push -fu origin work", []),
    "-o and its value before the remote": ("git push -o ci.skip origin work", []),
    "--push-option and a separate value": ("git push --push-option ci.skip origin work", []),
    "--repo and the branch, read by git as the remote": ("git push --repo=origin work", []),
    "after --": ("git push -- origin work", []),
    "--all from a clean branch": ("git push --all origin", [["checkout", "-q", "clean"]]),
    "--branches from a clean branch": ("git push --branches origin", [["checkout", "-q", "clean"]]),
    "--mirror from a clean branch": ("git push --mirror origin", [["checkout", "-q", "clean"]]),
    "--tags with a tag at the commit": ("git push --tags origin", [["tag", "v1", "work"], ["checkout", "-q", "clean"]]),
    "tag <name>": ("git push origin tag v1", [["tag", "-a", "-m", "v1", "v1", "work"], ["checkout", "-q", "clean"]]),
    "a pattern refspec": ("git push origin 'refs/heads/*:refs/heads/*'", [["checkout", "-q", "clean"]]),
    "`:`, the matching branches": ("git push origin :", [["checkout", "-q", "clean"]]),
    "a source named by its message, split at its last colon": ("git push origin ':/plant:refs/heads/x'", [["checkout", "-q", "clean"]]),
    "--no-dry-run after --dry-run": ("git push --dry-run --no-dry-run origin work", []),
    "--no-delete after -d": ("git push -d --no-delete origin work", []),
    "--all abbreviated": ("git push --al origin", [["checkout", "-q", "clean"]]),
    "--mirror abbreviated": ("git push --mir origin", [["checkout", "-q", "clean"]]),
    "--tags abbreviated": ("git push --tag origin", [["tag", "v1", "work"], ["checkout", "-q", "clean"]]),
    "push.default matching from -c": ("git -c push.default=matching push", [["checkout", "-q", "clean"]]),
    "push.default matching in the config": ("git push", [["config", "push.default", "matching"], ["checkout", "-q", "clean"]]),
    "a remote.origin.push in the config": ("git push", [["config", "remote.origin.push", "refs/heads/*"], ["checkout", "-q", "clean"]]),
    "a remote.origin.push from -c": ("git -c 'remote.origin.push=refs/heads/*' push", [["checkout", "-q", "clean"]]),
    "a remote.origin.mirror in the config": ("git push", [["config", "remote.origin.mirror", "true"], ["checkout", "-q", "clean"]]),
    "a remote.origin.mirror from -c with no value": ("git -c remote.origin.mirror push", [["checkout", "-q", "clean"]]),
    "settings from the environment": (
        "GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=push.default GIT_CONFIG_VALUE_0=matching git push", [["checkout", "-q", "clean"]]),
    "settings from --config-env": ("git --config-env=push.default=MODE push", [["checkout", "-q", "clean"]]),
    "settings from --config-env, its value apart": (
        "git --config-env push.default=MODE push", [["checkout", "-q", "clean"]]),
    "a shell alias's git, which reads the -c values": (
        "git -c push.default=matching ship", [["config", "alias.ship", "!git push"], ["checkout", "-q", "clean"]]),
    "a commit only a tag holds, read whole": (
        "git push $(echo origin)", [["tag", "v9", "work"], ["checkout", "-q", "clean"], ["branch", "-qD", "work"]]),
    "a commit only HEAD holds, read whole": (
        'git push origin "$(git rev-parse HEAD)":refs/heads/x', [["checkout", "-q", "--detach", "work"],
                                                                 ["branch", "-qD", "work"]]),
    "a commit only HEAD holds, with no refspec": (
        "git push $(echo origin clean)", [["checkout", "-q", "--detach", "work"], ["branch", "-qD", "work"]]),
    "--mirror and a commit only a tag holds": (
        "git push --mirror origin", [["tag", "v8", "work"], ["checkout", "-q", "clean"], ["branch", "-qD", "work"]]),
    "a commit only HEAD holds, sent as HEAD": (
        "git push origin HEAD:refs/heads/x", [["checkout", "-q", "--detach", "work"], ["branch", "-qD", "work"]]),
    "a commit a remote other than origin holds": ("git push origin work", [["update-ref", "refs/remotes/pr/work", "work"]]),
    "a source a variable holds": ('git push origin "$BRANCH"', [["checkout", "-q", "clean"]]),
    "a source a substitution builds": ('git push origin "$(git branch --show-current)":work', [["checkout", "-q", "clean"]]),
    "a pattern outside refs/": ("git push origin 'wor*'", [["checkout", "-q", "clean"]]),
    # Words that may expand to more than one, or that another command adds, may name any branch.
    "words a substitution adds": ("git push $(echo origin work)", [["checkout", "-q", "clean"]]),
    "words backquotes add": ("git push `echo origin work`", [["checkout", "-q", "clean"]]),
    "words a variable adds": ("git push $REMOTE_AND_BRANCH", [["checkout", "-q", "clean"]]),
    "words xargs adds": ("echo work | xargs git push origin", [["checkout", "-q", "clean"]]),
    "cd into a subdirectory": ("cd .claude && git push", []),
    "an alias in -c": ("git -c alias.ship=push ship origin work", []),
    "an alias in the repository's config": ("git ship origin work", [["config", "alias.ship", "push"]]),
    "an alias of an alias": ("git yeet", [["config", "alias.yeet", "ship origin work"], ["config", "alias.ship", "push"]]),
    "a shell alias": ("git ship", [["config", "alias.ship", "!git push origin work"]]),
    "bash -c": ("bash -c 'git push origin work'", []),
    "bash -o pipefail -c": ("bash -o pipefail -c 'git push origin work'", []),
    "bash -euo pipefail -c": ("bash -euo pipefail -c 'git push origin work'", []),
    "bash -O extglob -c": ("bash -O extglob -c 'git push origin work'", []),
    "bash +o posix -c": ("bash +o posix -c 'git push origin work'", []),
    "bash --rcfile and its file": ("bash --rcfile /dev/null -c 'git push origin work'", []),
    "eval": ("eval git push origin work", []),
    "eval of a quoted line": ("eval 'git push origin work'", []),
    "five evals deep": ("eval eval eval eval eval git push origin work", []),
    "trap --": ("trap -- 'git push origin work' EXIT", []),
    "a function's body": ("f() { git push origin work; }; f", []),
    "a function by the keyword": ("function f { git push origin work; }; f", []),
    "an if's branch": ("if true; then git push origin work; fi", []),
    "a case's branch": ("case x in x) git push origin work;; esac", []),
    "a case's later arm, from where the case began": (
        "case x in y) cd @ELSEWHERE@;; *) git push origin work;; esac", []),
    "a while loop": ("while true; do git push origin work && break; done", []),
    "in the background": ("git push origin work &", []),
    "a pipeline's second command": ("echo x | git push origin work", []),
    "timeout": ("timeout 60 git push", []),
    "env and an assignment": ("env GIT_TRACE=0 git push", []),
    "nice and its value": ("nice -n 5 git push", []),
    "git by its path": ("/usr/bin/git push", []),
    "git with quotes inside": ("g''it push", []),
    "git with a quoted letter": ('"g"it push', []),
    "git with a backslash inside": ("gi\\t push", []),
    "a trap": ("trap 'git push' EXIT", []),
    "after a newline": ("echo start\ngit push", []),
    "piped into tail": ("git push 2>&1 | tail -n 3", []),
    "redirected": ("git push origin work > push.log 2>&1", []),
    "a retry loop": ("for i in 1 2 3; do git push && break; sleep 1; done", []),
    "an if": ("if git push; then echo ok; fi", []),
    "a negation": ("! git push", []),
    "a group": ("{ git push; }", []),
    "a command substitution": ('echo "$(git push 2>&1)"', []),
    "backquotes": ("echo `git push 2>&1`", []),
    "a process substitution": ("cat <(git push 2>&1)", []),
    # A `#` that goes on a word starts no comment: the push after it runs.
    "after a process substitution and a `#` on its word": ("cat <(echo a)#c; git push origin work", []),
    "after a command substitution and a `#` on its word": ("echo $(echo a)#c; git push origin work", []),
    "after an escaped `;` and a `#` on its word": ("echo \\;#c; git push origin work", []),
    # Backquotes after such a `#` still run: `true` prints nothing, so bash pushes the current branch, not the
    # branch named `true`.
    "backquotes after a `#` on a substitution's word": (
        "echo $(echo a)#c; git push origin `true`", [["branch", "true", "clean"]]),
    "a HOME the call gives git, whose global config may push more": ("HOME=@REPO@ git push", [["checkout", "-q", "clean"]]),
    "a git command the hook does not know, read as a push of every branch": ("git town sync", [["checkout", "-q", "clean"]]),
    "a push whose output a variable keeps": ('out=$(git push origin work 2>&1); echo "$out"', []),
    "a substitution after an export of a variable the hook does not follow": ('export LANG=C; : "$(git push origin work)"', []),
    "a for loop's body, with no list": ("set -- a; for x do git push origin work; done", []),
    # A case in a function's body ends at its `esac`, after a `;;`.
    "a push after a function whose body holds a case": ("f() { case x in x) :;; esac; }; git push origin work", []),
    "a push in a case's arm in a function": (
        'pu() { case "$1" in main) echo no;; *) git push origin "$1";; esac; }; pu work', []),
    "a break count bash cannot read": ("for i in 1; do false && break \u00b2; done; git push origin work", []),
    # A case's patterns, read as bash parses them: a reserved word in one is a word, and an arm's terminator ends it
    # after a closing word before it (`};;`).
    "a pattern's parenthesis after an arm that ends in a group": (
        "case ls in y) { cd @ELSEWHERE@; };; (ls) git push origin work;; esac", []),
    "a push after a function whose case has a reserved word for a pattern": (
        "f() { case x in a) :;; if) :;; esac; }; git push origin work", []),
    "a push after a function whose case has a reserved word in parentheses for a pattern": (
        "f() { case x in (if) :;; esac; }; git push origin work", []),
    "a push after a function whose case tests a reserved word": ("f() { case if in x) :;; esac; }; git push origin work", []),
    "a push after a function whose loop's name is a reserved word": (
        "f() { for case in a; do :; done; }; git push origin work", []),
    "a push after a function whose case's arm opens with a reserved word": (
        "f() { case x in x) if true; then :; fi;; esac; cd @ELSEWHERE@; }; git push origin work", []),
    "a push after a function whose body times a group": (
        "f() { time { :; }; cd @ELSEWHERE@; }; git push origin work", []),
    "a push after a function whose body times a group with -p": (
        "f() { time -p { :; }; cd @ELSEWHERE@; }; git push origin work", []),
    "a push after a function whose loop has no list": (
        "f() { for i do if true; then :; fi; done; cd @ELSEWHERE@; }; git push origin work", []),
    "a push after a function whose body defines one with the keyword": (
        "g() { function f { :; }; cd @ELSEWHERE@; }; git push origin work", []),
    "a push after a function whose body defines one named case": (
        "g() { function case { :; }; cd @ELSEWHERE@; }; git push origin work", []),
    "a push after a function in parentheses whose case's pattern has no (": (
        "f() ( case x in a) cd @ELSEWHERE@;; esac ); git push origin work", []),
    "a push after a case whose esac follows a blank line": ("case x in x) :;;\n\nesac\ngit push origin work", []),
    "a push after a substitution whose case has the word case for a pattern": (
        "x=$(case x in (case) :;; esac); git push origin work", []),
    "a case's third arm, from where the case began": (
        "case x in a) :;; b) export GIT_DIR=@ELSEWHERE@/.git;; x) git push origin work;; esac", []),
    # What the reader must read whole, where an error it does not expect would refuse the call without its finding:
    # bash's time with --, a function named by a reserved word (a syntax error after the push's line), a break
    # count past Python's int.
    "time -- before a function that pushes": ("f() { git push origin work; }; time -- f", []),
    "time -p -- before a function that pushes": ("f() { git push origin work; }; time -p -- f", []),
    "a push, then a line defining time as a function": ("git push origin work\ntime() { :; }", []),
    "a function named if, then a push": ("if() { :; }; git push origin work", []),
    "a break count past Python's own limit": ("for i in 1; do break 100000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000; done; git push origin work", []),
    # A descriptor's digits stand right before their operator, unquoted: these are the refspec `2`.
    "a quoted digit before a redirection, the push's refspec": (
        "git push origin '2'>/dev/null", [["branch", "2", "work"], ["checkout", "-q", "clean"]]),
    "a digit set apart from its redirection, the push's refspec": (
        "git push origin 2 >/dev/null", [["branch", "2", "work"], ["checkout", "-q", "clean"]]),
    "a push after a function whose body times a group with -p and --": (
        "f() { time -p -- { :; }; cd @ELSEWHERE@; }; git push origin work", []),
    "a push after a function whose body times a group with --": (
        "f() { time -- { :; }; cd @ELSEWHERE@; }; git push origin work", []),
    "a push after a function whose body echoes done": ("f() { echo done; cd @ELSEWHERE@; }; git push origin work", []),
    # The branch `cat` (at clean) holds nothing new: a walk that took the process substitution's `cat` for a source
    # of the subshell's push finds no line there, where a source no ref names is read whole, which would find the
    # line however the walk read the push after the subshell.
    "a push after a subshell whose push writes to a process substitution after &>": (
        "(git push origin clean &> >(cat); cd @ELSEWHERE@); git push origin work", [["branch", "cat", "clean"]]),
    "a push after a subshell whose push reads a process substitution that > opens": (
        "(git push origin clean < >(cat); cd @ELSEWHERE@); git push origin work", [["branch", "cat", "clean"]]),
    "a remote.origin.push from -c in double quotes, a glob no shell expands": (
        'git -c "remote.origin.push=refs/heads/*" push', [["checkout", "-q", "clean"]]),
    # An array's assignment is one word, as bash reads it: no function's definition (`failed=()`), and no subshell.
    "a push after an empty array's assignment, then a loop": (
        "failed=(); git push origin work && for b in x; do :; done", []),
    "a push after a function whose body assigns an array a reserved word": (
        "f() { a=(done); cd @ELSEWHERE@; }; git push origin work", []),
    "a source an array holds": ('refs=(clean); git push origin "${refs[@]}"', [["checkout", "-q", "clean"]]),
    # A compound command's redirection is set up before its body runs, from where the compound began.
    "a group's output to a process substitution that pushes": ("{ cd @ELSEWHERE@; } > >(git push origin work)", []),
    "a group's errors to a process substitution that pushes": ("{ cd @ELSEWHERE@; } 2> >(git push origin work)", []),
    "an if's output to a process substitution that pushes": (
        "if true; then cd @ELSEWHERE@; fi > >(git push origin work)", []),
    "a case's output to a process substitution that pushes": (
        "case x in x) cd @ELSEWHERE@;; esac > >(git push origin work)", []),
    "a group's input from a process substitution that pushes": ("{ cd @ELSEWHERE@; } < <(git push origin work)", []),
    "a group that exports a GIT_DIR, its output to a process substitution that pushes": (
        "{ export GIT_DIR=@ELSEWHERE@/.git; } > >(git push origin work)", []),
    "a group that defines git, its output to a process substitution that pushes": (
        "{ git() { :; }; } > >(git push origin work)", []),
    # After a process substitution's `)`, bash is among its command's words, where a reserved word is a word.
    "a push after an echo of a process substitution and the word case": (
        "echo <(true) case x in; git push origin work", []),
    "a loop's push after an echo of a process substitution and the word case": (
        "echo <(true) case; for i in 1; do git push origin work; done", []),
    "a loop's push after an echo to a process substitution and the word case": (
        "echo > >(cat) case; for i in 1; do git push origin work; done", []),
    "a push after a subshell whose substitution echoes a process substitution and the word case": (
        "(cd @ELSEWHERE@; cat <(echo <(true) case x in)); git push origin work", []),
    "a push after a function whose body echoes a process substitution and a }": (
        "f() { echo <(true) }; cd @ELSEWHERE@; }; git push origin work", []),
    "a push after a function whose body reads a process substitution that holds a case": (
        "f() { cat <(case x in x) :;; esac); cd @ELSEWHERE@; }; git push origin work", []),
    "a push after a function whose body runs a group as a coprocess": (
        "f() { coproc { :; }; cd @ELSEWHERE@; }; git push origin work", []),
    "a push after a function whose body runs a named group as a coprocess": (
        "f() { coproc NAME { :; }; cd @ELSEWHERE@; }; git push origin work", []),
    # xargs gives git its words, its command among them.
    # Two closing words before a redirection: it belongs to the compound the last of them closes, and runs from
    # where that compound began (`{ cd x; { :; } } > >(cmd)`), not from the inner one's.
    "a group's output to a process substitution, after a nested group": (
        "{ cd @ELSEWHERE@; { :; } } > >(git push origin work)", []),
    "a group's output to a process substitution, after a nested if": (
        "{ cd @ELSEWHERE@; if true; then :; fi } > >(git push origin work)", []),
    "a nested group's output to a process substitution, in an if": (
        "if true; then cd @ELSEWHERE@; { :; } fi > >(git push origin work)", []),
    "a git command xargs reads from a process substitution": (
        "xargs -a <(echo push origin work) git", [["checkout", "-q", "clean"]]),
    "a git command xargs reads": ("echo push origin work | xargs git", [["checkout", "-q", "clean"]]),
}
# Pushes of `work` from the repository `elsewhere`, whose own `work` is clean: refused only when the hook follows
# the move into the project.
ELSEWHERE = {
    "-C and the path": "git -C @REPO@ push",
    "cd and a literal path": "cd @REPO@ && git push",
    "a subshell": "(cd @REPO@ && git push)",
    "pushd": "pushd @REPO@ && git push",
    "pushd, pushd and popd": "pushd @REPO@ && pushd /tmp && popd && git push",
    "pushd alone, which swaps the top two, then popd": "pushd @REPO@ && pushd && popd && git push origin work",
    "pushd -n, then popd": "pushd -n @REPO@ && popd && git push origin work",
    "popd -n, which keeps the directory": "pushd @REPO@ && popd -n && git push origin work",
    "popd +1, which keeps the directory": "pushd @REPO@ && popd +1 && git push origin work",
    "popd -0, which keeps the directory": "pushd @REPO@ && popd -0 && git push origin work",
    "pushd +1, which turns the stack": "pushd @REPO@ && pushd /tmp && pushd +1 && git push origin work",
    "a HOME the call exports, then cd": "export HOME=@REPO@; cd && git push origin work",
    "a HOME before cd": "HOME=@REPO@ cd && git push origin work",
    "a HOME the call sets, then cd ~": "HOME=@REPO@; cd ~ && git push origin work",
    "an OLDPWD the call sets, then cd -": "OLDPWD=@REPO@; cd - && git push origin work",
    "export -n HOME, which leaves cd the shell's own": "export HOME=@REPO@; export -n HOME; cd && git push origin work",
    "cd - back": "cd @REPO@ && cd /tmp && cd - && git push",
    "--git-dir": "git --git-dir=@REPO@/.git push origin work",
    "--git-dir and a separate value": "git --git-dir @REPO@/.git push origin work",
    "a relative --git-dir before -C, which git reads from there": "git --git-dir=.git -C @REPO@ push origin work",
    "a relative --git-dir and a separate value before -C": "git --git-dir .git -C @REPO@ push origin work",
    "a relative GIT_DIR, which git reads from where -C leaves it": "GIT_DIR=.git git -C @REPO@ push origin work",
    "a GIT_DIR before the command": "GIT_DIR=@REPO@/.git git push origin work",
    "an exported GIT_DIR": "export GIT_DIR=@REPO@/.git; git push origin work",
    "sh -lc": "sh -lc 'cd @REPO@ && git push'",
    "env -C": "env -C @REPO@ git push origin work",
    "env --chdir=": "env --chdir=@REPO@ git push origin work",
    "env --chdir and a separate value": "env --chdir @REPO@ git push origin work",
    "env -C and the value attached": "env -C@REPO@ git push origin work",
    "env -C in a group of short options": "env -iC @REPO@ git push origin work",
    "a wrapper's env -C": "nice env -C @REPO@ git push origin work",
    "a GIT_DIR the command gives a new shell": "GIT_DIR=@REPO@/.git bash -c 'git push origin work'",
    "a GIT_DIR env gives a new shell": "env GIT_DIR=@REPO@/.git bash -c 'git push origin work'",
    "a new shell's popd, with no stack of its own": "pushd @REPO@ && bash -c 'popd; git push origin work'",
    "git -C ~, from the HOME the call sets": "HOME=@REPO@; git -C ~ push origin work",
    "env -C ~, from the HOME the call sets": "HOME=@REPO@; env -C ~ git push origin work",
    "--git-dir and a separate ~": "HOME=@REPO@; git --git-dir ~/.git push origin work",
    "a GIT_DIR's ~, expanded as it is exported": "HOME=@REPO@; export GIT_DIR=~/.git; HOME=/; git push origin work",
    "a GIT_DIR's ~, from a HOME before it in the command": "HOME=@REPO@ GIT_DIR=~/.git git push origin work",
    "export's ~, from the HOME before the command": "HOME=@REPO@; export HOME=@ELSEWHERE@ GIT_DIR=~/.git; git push origin work",
    "env --chdir and a separate ~": "HOME=@REPO@; env --chdir ~ git push origin work",
    "env -C ~, the shell's HOME, not the command's": "HOME=@REPO@; HOME=@ELSEWHERE@ env -C ~ git push origin work",
    "env --chdir ~, the shell's HOME, not the command's": "HOME=@REPO@; HOME=@ELSEWHERE@ env --chdir ~ git push origin work",
    "a GIT_DIR's ~ among env's assignments": "HOME=@REPO@; env GIT_DIR=~/.git git push origin work",
    "a GIT_DIR's ~ after env's own HOME": "HOME=@REPO@; env HOME=@ELSEWHERE@ GIT_DIR=~/.git git push origin work",
    "env -v, --debug and --": "env -v --debug -- git -C @REPO@ push origin work",
    "exec -a and a name holding c": "export GIT_DIR=@REPO@/.git; exec -ac git push origin work",
    "a ~ in a call that quotes another word": "HOME=@REPO@; git -C ~ push -o 'ci.skip' origin work",
    "sudo env -C, to a literal path wherever sudo starts": "sudo env -C @REPO@ git push origin work",
    "a HOME exported again after export -n, which a new shell gets": (
        "export HOME=@REPO@; export -n HOME; export HOME; bash -c 'cd; git push origin work'"),
    "a HOME the command gives a new shell, whatever the shell holds unexported": (
        "export HOME=@ELSEWHERE@; export -n HOME; HOME=@REPO@ bash -c 'cd; git push origin work'"),
    "a HOME env gives a new shell, whatever the shell holds unexported": (
        "export HOME=@ELSEWHERE@; export -n HOME; env HOME=@REPO@ bash -c 'cd; git push origin work'"),
    # What may or may not run leaves the shell as one of its ways does: a condition's move outlasts its branches.
    "a condition's move, and the else branch's push": (
        "if cd @REPO@ && false; then cd @ELSEWHERE@; else git push origin work; fi"),
    "a while's condition, after which its body may not run": (
        "while cd @REPO@ && false; do cd @ELSEWHERE@; done; git push origin work"),
    "eval with an assignment before it": "GIT_DIR=@REPO@/.git eval git push origin work",
    "a GIT_DIR export -n hides and export shows again": (
        "export GIT_DIR=@REPO@/.git; export -n GIT_DIR; export GIT_DIR; git push origin work"),
    "a function defined in a group": "{ ls() { cd @REPO@; }; }; cd @ELSEWHERE@; ls; git push origin work",
    "a function the keyword defines in a group": (
        "{ function ls { cd @REPO@; }; }; cd @ELSEWHERE@; ls; git push origin work"),
    "an EXIT trap an exit runs": "trap 'git push origin work' EXIT; cd @REPO@; [ -d / ] && exit; cd @ELSEWHERE@",
    "env -C after another wrapper's, from where that leaves": "env -C @REPO@ nice env -C .claude git push origin work",
    "a function's OLDPWD prefix, which its body's cd - reads": "f() { cd - && git push origin work; }; OLDPWD=@REPO@ f",
    "an OLDPWD a new shell's command gives it": "OLDPWD=@REPO@ bash -c 'cd - && git push origin work'",
    "unset -f, which leaves the variable": "export GIT_DIR=@REPO@/.git; unset -f GIT_DIR; git push origin work",
    "a function export -f gives a new shell": "f() { cd @REPO@; }; export -f f; bash -c 'f; git push origin work'",
    "an OLDPWD a new shell's cd replaces": "OLDPWD=@ELSEWHERE@ bash -c 'cd @REPO@ && cd /tmp && cd - && git push origin work'",
    "an OLDPWD env gives a new shell, which its cd replaces": (
        "env OLDPWD=@ELSEWHERE@ bash -c 'cd @REPO@ && cd /tmp && cd - && git push origin work'"),
    "an OLDPWD before a function, which its cd replaces": (
        "f() { cd @REPO@; cd /tmp; cd -; git push origin work; }; OLDPWD=@ELSEWHERE@ f"),
    "a trap, in the directory its shell ends in": "trap 'git push origin work' EXIT; cd @REPO@",
    "a subshell's trap, where the subshell ends": "(trap 'git push origin work' EXIT; cd @REPO@)",
    "an eval's trap, the shell's around it": "eval \"trap 'git push origin work' EXIT\"; cd @REPO@",
    "export -n with a value, which it sets": "export -n GIT_DIR=@REPO@/.git; export GIT_DIR; git push origin work",
    "a function a new shell's own new shell gets, exported": (
        "f() { cd @REPO@; }; export -f f; bash -c 'bash -c \"f; git push origin work\"'"),
    "a function's prefix assignment, which what it runs gets though the shell holds it unexported": (
        "export GIT_DIR=@ELSEWHERE@/.git; export -n GIT_DIR; f() { git push origin work; }; GIT_DIR=@REPO@/.git f"),
    "eval's prefix assignment, which its words get though the shell holds it unexported": (
        "export GIT_DIR=@ELSEWHERE@/.git; export -n GIT_DIR; GIT_DIR=@REPO@/.git eval git push origin work"),
    "unset -f in a pipeline, which leaves the shell's function": (
        "ls() { cd @REPO@; }; unset -f ls | cat; ls; git push origin work"),
    "a quoted ; an echo prints": "cd @REPO@; echo ';' cd @ELSEWHERE@; git push origin work",
    "an escaped ; an echo prints": "cd @REPO@; echo \\; cd @ELSEWHERE@; git push origin work",
    "a nested case's first pattern": "case a in a) cd @REPO@; case b in b) git push origin work;; esac;; esac",
    "a function a process substitution removes": "ls() { cd @REPO@; }; cat <(unset -f ls); ls; git push origin work",
    "a function a subshell removes": "ls() { cd @REPO@; }; (unset -f ls); ls; git push origin work",
    "an escaped ;; an echo prints": r"cd @REPO@; echo \;\; cd @ELSEWHERE@; git push origin work",
    "an arithmetic for in a case's arm in a function's body, whose ;; ends no arm": (
        "f() { case x in x) for ((;;)); do break; done;; esac; cd @REPO@; }; f; git push origin work"),
    "a push after an empty array's assignment, a cd and an if": (
        "a=(); cd @REPO@; if true; then :; fi; git push origin work"),
    "a push after an array a loop appends to": (
        'out=() && cd @REPO@ && for f in a.py; do out+=("$f"); done && git push origin work'),
    "a function that assigns an empty array, moves and loops": (
        "f() { arr=(); cd @REPO@; for i in 1; do :; done; }; f; git push origin work"),
    # A definition's redirection is set up at each call, from where it is called.
    "a function whose definition's output goes to a process substitution that pushes, called after a cd": (
        "f() { :; } > >(git push origin work); cd @REPO@; f"),
    "a function whose definition's input comes from a process substitution that pushes, called after a cd": (
        "f() { :; } < <(git push origin work); cd @REPO@; f"),
    # Redirections that do not fail, so the cd runs.
    "a cd whose errors go to /dev/null": "cd @REPO@ 2>/dev/null && git push origin work",
    "a cd whose output and errors go to /dev/null by >& alone": "cd @REPO@ >& /dev/null && git push origin work",
    "a cd whose output and errors go to /dev/null by 1>&": "cd @REPO@ 1>& /dev/null && git push origin work",
    "a cd whose errors go where its output does": "cd @REPO@ 2>&1 && git push origin work",
    "a cd with a here-document": "cd @REPO@ <<EOF\nhi\nEOF\ngit push origin work",
    "a cd with a here-string": "cd @REPO@ <<< hi && git push origin work",
    "a cd whose output goes to a process substitution": "cd @REPO@ > >(cat) && git push origin work",
}
# Pushes of `work` from the project after a move the shell does not keep, or undoes: refused only when the hook
# reads the push in the project.
STAYS = {
    "unset GIT_DIR": "export GIT_DIR=@ELSEWHERE@/.git; unset GIT_DIR; git push origin work",
    "export -n GIT_DIR": "export GIT_DIR=@ELSEWHERE@/.git; export -n GIT_DIR; git push origin work",
    "pushd -n": "pushd -n @ELSEWHERE@ && git push origin work",
    "a cd in a pipeline": "cd @ELSEWHERE@ | cat; git push origin work",
    "a cd in the background": "cd @ELSEWHERE@ & git push origin work",
    "a cd in a piped group": "{ cd @ELSEWHERE@; } | cat; git push origin work",
    "a cd in a subshell": "(cd @ELSEWHERE@); git push origin work",
    "pushd +N past the stack's end": "pushd +3; git push origin work",
    "popd with no stack": "popd; git push origin work",
    "an OLDPWD a later cd replaces": "OLDPWD=@ELSEWHERE@; cd /tmp && cd - && git push origin work",
    "env -u GIT_DIR": "export GIT_DIR=@ELSEWHERE@/.git; env -u GIT_DIR git push origin work",
    "env -u and the name attached": "export GIT_DIR=@ELSEWHERE@/.git; env -uGIT_DIR git push origin work",
    "env --unset=GIT_DIR": "export GIT_DIR=@ELSEWHERE@/.git; env --unset=GIT_DIR git push origin work",
    "env --unset and a separate name": "export GIT_DIR=@ELSEWHERE@/.git; env --unset GIT_DIR git push origin work",
    "env -i": "export GIT_DIR=@ELSEWHERE@/.git; env -i git push origin work",
    "env -i in a group of short options": "export GIT_DIR=@ELSEWHERE@/.git; env -iu X git push origin work",
    "env -": "export GIT_DIR=@ELSEWHERE@/.git; env - git push origin work",
    "env --ignore-environment": "export GIT_DIR=@ELSEWHERE@/.git; env --ignore-environment git push origin work",
    "exec -c": "export GIT_DIR=@ELSEWHERE@/.git; exec -c git push origin work",
    "exec -a and a name, then -c": "export GIT_DIR=@ELSEWHERE@/.git; exec -a name -c git push origin work",
    "unset of an element, which unsets a variable whole": "export GIT_DIR=@ELSEWHERE@/.git; unset 'GIT_DIR[0]'; git push origin work",
    "a list in the background, its cd among it": "cd @ELSEWHERE@ && true & git push origin work",
    "env -C twice, the last from where env starts": "env -C @ELSEWHERE@ -C . git push origin work",
    "env --chdir twice, the last from where env starts": "env --chdir=@ELSEWHERE@ --chdir=. git push origin work",
    "a job in the background first in an else branch": (
        "if false; then cd @ELSEWHERE@; else sleep 0 & git push origin work; fi"),
    "a function whose subshell body holds a case": "f() ( case x in x) cd @ELSEWHERE@;; esac ); f; git push origin work",
    "a process substitution that holds a case": "cat <(case x in x) cd @ELSEWHERE@;; esac); git push origin work",
    "a case that ends just before its subshell does": "(cd @ELSEWHERE@; case x in x) :;; esac); git push origin work",
    "a process substitution whose case has two arms, the first pattern opened": (
        "cat <(case x in (y) :;; x) cd @ELSEWHERE@;; esac); git push origin work"),
    "a function's subshell body: a case after a command, an esac an echo prints, a cd after the case": (
        "f() ( true; case x in (y) echo esac;; x) cd @ELSEWHERE@;; esac; cd @ELSEWHERE@ ); f; git push origin work"),
    "a break a new shell's string holds, which leaves no loop of the shell's": (
        "for i in 1; do cd @ELSEWHERE@; bash -c 'break'; cd @REPO@; done; git push origin work"),
    "a function a pipeline's command exports": (
        "ls() { cd @ELSEWHERE@; }; export -f ls | cat; bash -c 'ls; git push origin work'"),
    "a function a process substitution exports": (
        "ls() { cd @ELSEWHERE@; }; cat <(export -f ls); bash -c 'ls; git push origin work'"),
}
# Pushes from the project that run in `elsewhere`, whose commits are clean: they pass, scanned there.
MOVED_AWAY = {
    "-C": "git -C @ELSEWHERE@ push origin work",
    "cd": "cd @ELSEWHERE@ && git push origin work",
    "env -C": "env -C @ELSEWHERE@ git push origin work",
    "pushd": "pushd @ELSEWHERE@ && git push origin work",
    "popd -n after pushd, which keeps the directory": "pushd @ELSEWHERE@ && popd -n && git push origin work",
    "exec -a, whose name looks like an option": "export GIT_DIR=@ELSEWHERE@/.git; exec -a -c git push origin work",
    "an absolute OLDPWD after a cd the hook cannot name": 'cd "$X"; OLDPWD=@ELSEWHERE@; cd - && git push origin work',
    "cd -- and a directory": "cd -- @ELSEWHERE@ && git push origin work",
    # Read where the shell is whichever way it went.
    "a while's condition that moves the shell, which its body undoes": (
        "while cd @ELSEWHERE@ && false; do cd @REPO@; done; git push origin work"),
    "an if each of whose branches moves to one directory": (
        "if true; then cd @ELSEWHERE@; else cd @ELSEWHERE@; fi && git push origin work"),
    "an if's condition that moves the shell, which no branch undoes": (
        "if cd @ELSEWHERE@; then :; fi; git push origin work"),
    "a function that returns where it moved": "f() { cd @ELSEWHERE@; return; }; f; git push origin work",
    "a cd after a cd in an && list, which runs only after it": (
        "cd @REPO@ && cd @ELSEWHERE@ && git push origin work"),
    "a subshell after a blank line in a case's arm, which no `;;` ends": (
        "case x in\nx) cd @ELSEWHERE@\n\n(cd @REPO@)\ngit push origin work;;\nesac"),
    "an && list, then a push after it": "cd @ELSEWHERE@ && true; git push origin work",
    "a subshell in a case's first arm": "case x in x) cd @ELSEWHERE@; (cd @REPO@); git push origin work;; esac",
    # What only bash reads, in bash's own string, and backquotes git's options do not hold.
    "pushd in bash's string": "bash -c 'pushd @ELSEWHERE@ >/dev/null && git push origin work'",
    "cd -e in bash's string": "bash -c 'cd -e @ELSEWHERE@ && git push origin work'",
    "a $'' quote in bash's string": "bash -c \"cd $'@ELSEWHERE@' && git push origin work\"",
    "backquotes after git's command": "cd @ELSEWHERE@ && git push origin `echo work`",
    "a function an && list's first pipeline defines, which always runs": (
        "f() { cd @ELSEWHERE@; } && true; f; git push origin work"),
    "a quoted ;; in a case's arm, then a subshell": (
        "case x in x) cd @ELSEWHERE@; echo ';;'; (cd @REPO@); git push origin work;; esac"),
    "an empty case, then a subshell": "case x in esac; cd @ELSEWHERE@; (cd @REPO@); git push origin work",
    "time -p, bash's reserved word, before a cd": "time -p cd @ELSEWHERE@ && git push origin work",
    "a function's prefix assignment, unexported again after it": (
        "cd @ELSEWHERE@; export GIT_DIR=@REPO@/.git; export -n GIT_DIR; f() { :; }; GIT_DIR=@REPO@/.git f; "
        "git push origin work"),
    "an arm's background job, from where the arm began": (
        "cd @ELSEWHERE@; case x in y) cd @REPO@;; x) true & git push origin work;; esac"),
    "an arm the case reaches without the functions an arm before defined": (
        "cd @ELSEWHERE@; case x in y) ls() { cd @REPO@; };; x) ls; git push origin work;; esac"),
    "an else the function its then-branch defines does not reach": (
        "cd @ELSEWHERE@; if false; then ls() { cd @REPO@; }; else ls; git push origin work; fi"),
    "eval's prefix assignment, unexported again after it": (
        "cd @ELSEWHERE@; export GIT_DIR=@REPO@/.git; export -n GIT_DIR; GIT_DIR=@REPO@/.git eval :; git push origin work"),
    "a HOME one way of an if unexports, for cd": (
        "export HOME=@ELSEWHERE@; if [ -d /x ]; then export -n HOME; fi; cd; git push origin work"),
}
# Pushes of `clean` from `work`, whose HEAD holds the planted line: each passes, scanned, only if the hook reads
# what the push names and not every branch.
PRECISE = {
    "a remote and the branch": ("git push origin clean", []),
    "-u": ("git push -u origin clean", []),
    "a refspec with a destination": ("git push origin clean:refs/heads/elsewhere", []),
    "a forced refspec": ("git push origin +clean:clean", []),
    "a commit expression as the source": ("git push origin clean~0:refs/heads/x", []),
    "a source named by its message": ("git push origin ':/clean change:refs/heads/x'", []),
    "a lease and its expected value": ("git push --force-with-lease=clean:0123abc origin clean", []),
    "clustered short options": ("git push -fu origin clean", []),
    "-o and its value": ("git push -o ci.skip origin clean", []),
    "-o and its value attached": ("git push -oci.skip origin clean", []),
    "--push-option and its value": ("git push --push-option ci.skip origin clean", []),
    "--push-option abbreviated, and its value": ("git push --push-opt ci.skip origin clean", []),
    "--recurse-submodules and its value": ("git push --recurse-submodules check origin clean", []),
    "--dry-run, then --no-dry-run": ("git push --dry-run --no-dry-run origin clean", []),
    "--all, then --no-all": ("git push --all --no-all origin clean", []),
    "after --": ("git push -- origin clean", []),
    "tag <name>": ("git push origin tag v0", [["tag", "v0", "clean"]]),
    "an alias in -c": ("git -c alias.ship=push ship origin clean", []),
    "an alias in the repository's config": ("git ship origin clean", [["config", "alias.ship", "push"]]),
    "a shell alias": ("git ship", [["config", "alias.ship", "!git push origin clean"]]),
    "bash -c": ("bash -c 'git push origin clean'", []),
    "bash -o pipefail -c": ("bash -o pipefail -c 'git push origin clean'", []),
    "eval": ("eval git push origin clean", []),
    "five evals deep": ("eval eval eval eval eval git push origin clean", []),
    "timeout": ("timeout 60 git push origin clean", []),
    "env -C": ("env -C @REPO@ git push origin clean", []),
    "a trap": ("trap 'git push origin clean' EXIT", []),
    "redirected": ("git push origin clean > push.log 2>&1", []),
    "piped into tail": ("git push origin clean 2>&1 | tail -n 3", []),
    "backquotes in single quotes": ("echo 'a `b` c'; git push origin clean", []),
    "a comment after the push": ("git push origin clean  # costs $0, `nothing` else", []),
    "the push's output a variable keeps": ('out=$(git push origin clean 2>&1); echo "$out"', []),
    "a substitution after another variable's assignment": ('FOO=1; out="$(git push origin clean)"', []),
    "timeout's signal and its value": ("timeout -s KILL 60 git push origin clean", []),
    "stdbuf's -o and its value": ("stdbuf -o L git push origin clean", []),
    "exec -a and its name attached": ("exec -ax git push origin clean", []),
    "a branch whose name ends in a digit, right before a redirection": (
        "git push origin clean2>/dev/null", [["branch", "clean2", "clean"]]),
}
# Commands that may make or move a commit, or run what may, before a push in its call: refused whatever the
# commits hold (here the branch `clean`, whose commit holds nothing).
BEFORE_REFUSED = {
    "a commit": "git commit -qam x && git push",
    "an amend": "git commit --amend --no-edit; git push -f",
    "a merge": "git merge main && git push",
    "a rebase": "git rebase main && git push --force-with-lease",
    "a checkout": "git checkout work && git push",
    "a switch": "git switch -c fresh && git push -u origin fresh",
    "a reset": "git reset --hard HEAD~1 && git push -f",
    "a cherry-pick": "git cherry-pick work && git push",
    "a branch moved": "git branch -f work clean && git push origin work",
    "a tag made": "git tag v2 && git push --tags",
    "a pull": "git pull && git push",
    "a stash, which the hook does not tell apart": "git stash && git push",
    "an alias of commit": "git -c alias.ci=commit ci -qam x && git push",
    "a program": "npm test && git push",
    "a script": "./scripts/release.sh && git push",
    "an interpreter": "python3 tool.py; git push",
    "a shell given a string": "bash -c 'git commit -qam x' && git push",
    "a function": "f() { git commit -qam x; }; f; git push",
    "a commit between two pushes": "git push && git commit -qam x && git push",
    "a commit after a push in a loop": "for i in 1 2; do git push; git commit -qam x; done",
    "a commit in a substitution": 'git push origin "$(git commit -qam x && git rev-parse HEAD)":refs/heads/x',
    "a commit in a pipeline beside the push": "git commit -qam x | git push",
    "a commit in the background": "git commit -qam x & git push",
    "a commit before a trap's push": "trap 'git push' EXIT; git commit -qam x",
    "an alias the call defines": "git config alias.ship push && git ship",
    "a fetch into a branch": "git fetch . work:clean && git push origin clean",
    "a fetch": "git fetch origin && git push",
    "a fetch of a branch": "git fetch origin main && git push",
    "a fetch, then what it fetched": "git fetch . work && git push origin FETCH_HEAD:refs/heads/x",
    "a ref moved by update-ref": "git update-ref refs/heads/clean work && git push origin clean",
    "a revert": "git revert --no-edit HEAD && git push",
    "a patch applied as a commit": "git am < change.patch && git push",
    "HEAD moved by symbolic-ref": "git symbolic-ref HEAD refs/heads/work && git push",
    "a remote added": "git remote add copy https://example.invalid/r.git && git push copy clean",
    "a remote's refs pruned": "git remote prune origin && git push",
    "a setting written": "git config push.default matching && git push",
    "sed, which can run a program": "sed -n 1p a.py && git push",
    "tee, which can write a ref": "echo x | tee .git/refs/heads/clean; git push",
    "another program's git command": "git absorb && git push",
    "a checkout beside a push in the background": "git push & git checkout -q work",
    "a reset in the push's pipeline": "git push | git reset -q --hard HEAD~1",
    "a commit in a while loop around the push": "while true; do git push && break; git commit -qam x; done",
    "a commit beside the push in a nested shell's background": "bash -c 'git push & git commit -qam x'",
    "a commit in a nested shell's pipeline": "bash -c 'git push | git commit -qam x'",
    "a commit beside a group in the background": "{ git push; } & git commit -qam x",
    "a commit beside a subshell in the background": "(git push) & git commit -qam x",
    "a commit in a subshell's pipeline": "(git push) | git commit -qam x",
    "a commit in a loop the push pipes into": "git push | while read l; do git commit -qam x; done",
    "a commit beside a loop in the background": "for i in 1; do git push; done & git commit -qam x",
    "a commit beside an if in the background": "if true; then git push; fi & git commit -qam x",
    "a commit in a process substitution": "cat <(git commit -qam x) && git push",
    "a function by the keyword": "function f { git commit -qam x; }; f; git push",
    "a function that pushes, called after a commit": "f() { git push; }; git commit -qam x; f",
    "a function named cd that commits": "cd() { git commit -qam x; }; cd /tmp; git push",
    "a subshell's trap": "(trap 'git commit -qam x' EXIT; git push)",
    # A file a command writes may be a ref, a config or a script: a redirection's, or one an option names.
    "a redirection that writes a ref": "git rev-parse work > .git/refs/heads/clean; git push origin clean",
    "an appending redirection": "echo x >> notes.txt; git push",
    "&>": "git status &> status.txt; git push",
    "&>>": "git status &>> status.txt; git push",
    "<>": "cat <> notes.txt; git push",
    ">& and a file": "git status >& status.txt; git push",
    ">|": "git status >| status.txt; git push",
    "a redirection with no command": "> notes.txt; git push",
    "exec sending the shell's output to a file": "exec > .git/refs/heads/clean; git rev-parse work; git push",
    "a redirection on a group": "{ git rev-parse work; } > .git/refs/heads/clean; git push origin clean",
    "a redirection on a subshell": "(git rev-parse work) > .git/refs/heads/clean; git push origin clean",
    "a redirection on a loop": "for b in work; do git rev-parse $b; done > .git/refs/heads/clean; git push",
    "a redirection on a group around the push": "{ git rev-parse work; git push origin clean; } > .git/refs/heads/clean",
    "a redirection on a subshell around the push": "(git rev-parse work; git push origin clean) > .git/refs/heads/clean",
    "a redirection on a function that pushes": "f() { git rev-parse work; git push origin clean; }; f > .git/refs/heads/clean",
    "sort, which can write a file and run a program": "git branch | sort -o .git/refs/heads/clean; git push",
    "uniq, which writes its second file": "uniq refs.txt .git/refs/heads/clean; git push",
    "curl, which can write a file": "curl -so .git/refs/heads/clean https://example.invalid/sha; git push origin clean",
    "a git read given -c": "git -c diff.external=./move.sh diff; git push",
    "a git read given a GIT_* variable": "GIT_EXTERNAL_DIFF=./move.sh git diff; git push",
    "a git read after the call exports a GIT_* variable": "export GIT_EXTERNAL_DIFF=./move.sh; git diff; git push",
    "a git read after the call sets HOME": "export HOME=/tmp; git status; git push",
    "a git read writing a file": "git log -1 --format=%H work --output=.git/refs/heads/clean; git push origin clean",
    "a git read writing a file, its option abbreviated": "git show -s --format=%H work --outp=.git/refs/heads/clean; git push",
    "git grep running a pager": "git grep -O./move.sh x; git push",
    "git ls-remote running a program": "git ls-remote --upload-pack=./move.sh .; git push",
    "git archive running a program": "git archive --remote=. --exec=./move.sh HEAD; git push",
    "git add running an editor": "git add -e; git push",
    # A builtin is the shell's only by its own name: `CD` or a path to a program named cd moves no shell.
    "cd in capitals, another command": "CD @ELSEWHERE@; git push",
    "a program named cd": "/usr/bin/cd @ELSEWHERE@; git push",
    "export in capitals, another command": "EXPORT GIT_DIR=@ELSEWHERE@/.git; git push",
    # A function the shell no longer has is a program by that name.
    "a function unset removes, then its name": "f() { cd @ELSEWHERE@; }; unset f; f; git push",
    "a function a new shell does not get": "f() { cd @ELSEWHERE@; }; bash -c 'f; git push'",
    "an exported function sh may not import, as dash does not": "f() { cd @ELSEWHERE@; }; export -f f; sh -c 'f; git push'",
    "a function a subshell defined": "(f() { cd @ELSEWHERE@; }); f; git push",
    # A function the call may define otherwise, or not at all, is one the hook cannot read.
    "a function unset may keep, a variable by its name the hook holds unknown": (
        "ls() { cd @ELSEWHERE@; }; ls=1; unset ls; ls; git push"),
    "a function an if's branch defines": "if true; then ls() { cd @ELSEWHERE@; }; fi; ls; git push",
    "functions an if defines either way": (
        "if true; then ls() { :; }; else ls() { cd @ELSEWHERE@; }; fi; ls; git push"),
    "a function a skipped pipeline defines": "false && ls() { cd @ELSEWHERE@; }; ls; git push",
    "a function its line redefines after a substitution calls it": (
        "f() { :; }; x=$(f; git push); f() { cd @ELSEWHERE@; }"),
    "a function its line defines after a substitution calls it": "x=$(f; git push); f() { cd @ELSEWHERE@; }",
    "a file ENV gives sh": "ENV=rc.sh sh -c 'git push'",
    "a directory ZDOTDIR gives zsh": "ZDOTDIR=d zsh -c 'git push'",
    "a function a new shell defines, gone after it": "bash -c 'f() { cd @ELSEWHERE@; }'; f; git push",
    "a function a piped group defines": "{ f() { cd @ELSEWHERE@; }; } | cat; f; git push",
    "a function a background job defines": "f() { cd @ELSEWHERE@; } & f; git push",
    "a function its line removes after a substitution calls it": (
        "f() { cd @ELSEWHERE@; }; eval 'x=$(f; git push); unset f'"),
    # A new shell given a startup file or a function runs it before its string.
    "a file BASH_ENV gives a new shell": "BASH_ENV=rc.sh bash -c 'git push'",
    "a function env gives a new shell": """env 'BASH_FUNC_git%%=() { command git "$@"; }' bash -c 'git push'""",
    "a new shell after an export of a name a variable holds, which may be its startup file": (
        "n=BASH_ENV; export $n=rc.sh; bash -c 'git push'"),
    # A function a subshell defines, changes or exports stays there.
    "a function a definition in a pipeline makes": "f() { cd @ELSEWHERE@; } | cat; f; git push",
    "a function a piped call defines": "f() { g() { cd @ELSEWHERE@; }; }; f | cat; g; git push",
    "a function a process substitution defines": "cat <(f() { cd @ELSEWHERE@; }); f; git push",
    "a function a piped eval defines": "eval 'f() { cd @ELSEWHERE@; }' | cat; f; git push",
    "a function a subshell exports": "f() { cd @ELSEWHERE@; }; (export -f f); bash -c 'f; git push'",
    "a function export -fn stops exporting": "f() { cd @ELSEWHERE@; }; export -f f; export -fn f; bash -c 'f; git push'",
    "a function an && list may export": "f() { cd @ELSEWHERE@; }; true && export -f f; bash -c 'f; git push'",
    "a function unset may keep, after a variable read sets by its name": (
        "ls() { cd @ELSEWHERE@; }; read ls <<< x; unset ls; ls; git push"),
    "a function a loop's later turn calls": "for i in 1 2; do f; f() { git push origin work; }; done",
    "a quoted reserved word, a program by that name": "'function' x; git push",
    "a function one substitution defines, which another does not have": (
        "x=$(f() { cd @ELSEWHERE@; }); y=$(f; git push)"),
    "a push a function holds, which a substitution on its line calls": 'f() { git push origin work; }; x=$(f); echo "$x"',
    "time in sh, a program there": "sh -c 'time cd @ELSEWHERE@ && git push origin work'",
    "a function the keyword defines in a piped group": "{ function f { cd @ELSEWHERE@; }; } | cat; f; git push",
    "an escaped reserved word, a program by that name": "\\time cd @ELSEWHERE@; git push",
    "a quoted {, a program by that name": "'{' cd @ELSEWHERE@; git push",
    "a quoted fi, a program by that name": "'fi' cd @ELSEWHERE@; git push",
    "a quoted then, a program by that name": "'then' cd @ELSEWHERE@; git push",
    "a function the || after an && list may get from where the list began": (
        "f() { cd @ELSEWHERE@; }; true && { f() { cd @REPO@; }; false; } || { f; git push; }"),
    "a function a definition after a pipe makes": "cat /dev/null | f() { cd @ELSEWHERE@; }; f; git push",
    "a function a shell alias does not get": "f() { cd @ELSEWHERE@; }; git -c 'alias.x=!f; git push' x",
    "a function defined again after unset -f, which no export marks": (
        "f() { :; }; export -f f; unset -f f; f() { cd @ELSEWHERE@; }; bash -c 'f; git push'"),
    "a function a background list defines": "true && eval 'f() { cd @ELSEWHERE@; }' && true & f; git push",
    "a function unset -f removes": "f() { cd @ELSEWHERE@; }; unset -f f; f; git push",
    "a function an and-or list's skipped pipeline redefines": (
        "f() { :; }; f() { cd @ELSEWHERE@; } || f() { :; }; f; git push"),
    "a function a piped definition with a redirection keeps to its subshell": (
        "f() { cd @ELSEWHERE@; } >/dev/null | true; f; git push"),
    "a function a piped definition with an input process substitution keeps to its subshell": (
        "f() { cd @ELSEWHERE@; } < <(true) | true; f; git push"),
    "a function a piped definition with a descriptor's redirection keeps to its subshell": (
        "f() { cd @ELSEWHERE@; } 2>/dev/null | true; f; git push"),
    "a commit in a process substitution the push writes to": "git push > >(git commit -qam x)",
    "a commit in a process substitution the push reads": "git push < <(git commit -qam x)",
    "a commit in a process substitution the push's errors go to": "git push 2> >(git commit -qam x)",
    "a commit in a process substitution after &>": "git push &> >(git commit -qam x)",
    "a tee in a process substitution the push's errors go to": "git push 2> >(tee push.log)",
    "a function a piped definition with a process substitution after &> keeps to its subshell": (
        "f() { cd @ELSEWHERE@; } &> >(cat) | true; f; git push"),
    "a function a piped definition with a process substitution after < keeps to its subshell": (
        "f() { cd @ELSEWHERE@; } < >(cat) | true; f; git push"),
    "a program a function a loop's later turn redefines runs, before a push": (
        "f() { :; }; for i in 1 2; do f; f() { make; }; done; git push origin work"),
    "a function declare -fx exports to a new shell": "f() { git push origin work; }; declare -fx f; bash -c f",
    "a function typeset -fx exports to a new shell": "f() { git push origin work; }; typeset -fx f; bash -c f",
    "a git clean, which may remove the directory a cd after it enters": "git clean -fdq; git push",
    "a commit a process substitution among an array's words runs": "a=(<(git commit -qam x)); git push",
    "a file a function's definition writes at each call": "f() { :; } > log; f; git push",
    "a function a piped definition that appends to a device keeps to its subshell": (
        "f() { cd @ELSEWHERE@; } &>>/dev/null | true; f; git push"),
    "a function a piped definition that opens a device to read and write keeps to its subshell": (
        "f() { cd @ELSEWHERE@; } <>/dev/null | true; f; git push"),
    "a function a piped definition with a process substitution after > keeps to its subshell": (
        "f() { cd @ELSEWHERE@; } > >(cat) | true; f; git push"),
}
# Commands that may come before a push, or beside it: read-only or index-only git commands, cd and plain
# builtins; the push of `clean` passes.
BEFORE_ALLOWED = {
    "cd": "cd @REPO@ && git push",
    "an and-or list, then a cd that names the directory again": "true && cd @ELSEWHERE@; cd @REPO@; git push",
    "timeout's duration with a unit": "timeout 1m git push",
    "a break in a function, which leaves no loop of its caller's": (
        "f() { break; }; for i in 1; do cd @ELSEWHERE@; f; cd @REPO@; done; git push"),
    "status": "git status && git push",
    "add": "git add -A && git push",
    "log and diff": "git log -1 && git diff --stat && git push",
    "set -e": "set -e; git push",
    "echo": "echo pushing; git push",
    "sleep": "sleep 0 && git push",
    "branch --show-current": "git branch --show-current && git push",
    "config --get": "git config --get push.default; git push",
    "rev-parse": "git rev-parse HEAD && git push",
    "remote -v": "git remote -v && git push",
    "stash list": "git stash list && git push",
    "tag -l": "git tag -l && git push",
    "a push before a push": "git push origin clean && git push origin clean:refs/heads/copy",
    "a retry loop of reads": "for i in 1 2 3; do git push && break; sleep 0; done",
    "gh after the push": "git push -u origin clean && gh pr create --fill",
    "a reading gh api": "gh api repos/o/r/pulls && git push",
    "an export": "export LANG=C; git push",
    "type and which": "type git && which git && git push",
    "a retry loop with arithmetic": "for i in 1 2 3; do git push && break; sleep $((2**i)); done",
    "a pull request after a retry loop": "for i in 1 2; do git push && break; done; gh pr create --fill",
    "a pull request after a piped push": "git push 2>&1 | tail -n 3; gh pr create --fill",
    "a commit after the push": "git push && git commit -qam x",
    "a nested shell that pushes, then commits": "bash -c 'git push; git commit -qam x'",
    "a case whose other branch commits": "case x in x) git push;; y) git commit -qam y;; esac",
    "a push in a case's later branch, after a pattern": "case x in y) echo y;; x) git push;; esac",
    "exec redirecting the shell's output": "exec 2>&1; git push",
    "a pipe into cat, and read": "git branch -r | cat; read -r x <<< y; git push",
    "redirections to /dev/null and duplicates": "git status > /dev/null 2>&1; git log -1 &>/dev/null; git push",
    "a closed descriptor and standard error": "git status 2>&-; echo x >&2; echo y > /dev/stderr; git push",
    "the push's output appended to a file": "git push origin clean >> push.log 2>&1",
    "a redirection with no command, after the push": "git push; > notes.txt",
    "a group of reads in a pipeline": "{ git status; } | cat; git push",
    "symbolic-ref reading HEAD": "git symbolic-ref HEAD && git symbolic-ref --short -q HEAD && git push",
    "remote show and get-url": "git remote show origin && git remote get-url origin && git push",
    "unset and export -n": "unset FOO; export -n BAR; git push",
    "pushd -n": "pushd -n /tmp && git push",
    "backquotes in single quotes": "echo 'a `b` c'; git push",
    "a function's definition, never called": "f() { git commit -qam x; }; git push",
    "a function of reads, called first": "f() { git status; }; f; git push",
    "a function of reads by the keyword, called first": "function f { git status; }; f; git push",
    "a function that unsets its own prefix assignment": "f() { unset GIT_DIR; git status; }; GIT_DIR=@REPO@/.git f; git push",
    "a cd whose failure ends the call": "cd @REPO@ || exit 1; git push",
    "a cd whose failure runs a group that ends the call": "cd @REPO@ || { echo no; exit 1; }; git push",
    "a -c value with a space, which no shell splits": "git -c 'user.name=a b' push origin clean",
    "a substitution inside a push's, which moves nothing": 'out=$(: $(true); git push origin clean 2>&1); echo "$out"',
    "a pattern's | after the first arm, which runs nothing": "case x in y) :;; a|b) git push;; esac",
    "a quoted > an echo prints": "echo '>' x; git push origin clean",
    "an escaped > an echo prints": r"echo \> x; git push origin clean",
    "a process substitution an echo writes to, which only reads": "echo hi > >(cat); git push origin clean",
    "a process substitution an echo writes to after &>, which only reads": "echo hi &> >(cat); git push origin clean",
    "a whole case in a substitution, its pattern opened, a case word in its arm": (
        "out=$(case x in (x) echo case;; esac); git push origin clean"),
    "a break in an inner loop, which leaves the outer one running": (
        "for i in 1; do for j in 1; do cd @ELSEWHERE@; break; done; cd @REPO@; done; git push"),
    "a function whose definition writes a file, never called": "f() { :; } > log; git push origin clean",
    "a process substitution the push's errors go to, which only reads": "git push origin clean 2> >(cat)",
    "a device a read appends to before a push": "git status &>>/dev/null; git push origin clean",
    "an array of file names before a push": "files=(a.py c.py); git push origin clean",
    "an addition to a variable the hook does not follow, before a push": (
        "PATH+=:/usr/local/bin; git push origin clean"),
    "an element's assignment before a push": "a[1]=x; git push origin clean",
    "a function whose body starts on the next line, called before a push": (
        "f()\n{ git status; }\nf; git push origin clean"),
}
# Look-alikes on the branch `work`, whose new commit holds the planted line: none sends it to GitHub.
PASSES = {
    "a dry run": "git push --dry-run",
    "a dry run abbreviated": "git push --dry origin work",
    "-n": "git push -n origin work",
    "-n in a cluster": "git push -fn origin work",
    "a delete and a dry run in a cluster": "git push -dn origin work",
    "a delete": "git push origin --delete work",
    "-d": "git push -d origin work",
    "a delete refspec": "git push origin :work",
    "a negative refspec alone": "git push origin '^refs/heads/work'",
    "main, already on GitHub": "git push origin main",
    "a log that greps for push": "git log --grep push",
    "a quoted phrase": "grep -rn 'git push' .",
    "an echoed string": 'echo "git push"',
    "a file named push": "cat push.log",
    "a push of nothing new": "git push origin main:refs/heads/copy",
    "a function that pushes, never called": "f() { git push origin work; }",
    "a function named git, which the shell runs instead": "git() { echo no; }; git push origin work",
    # A function the hook cannot read pushes only when a body the call defines names git or gh.
    "a loop whose turn defines a function, in a call that pushes nothing": "for i in 1 2; do g() { :; }; done; git status",
    # A body's word holds git or gh inside a longer one, which names neither.
    "a function the call may define otherwise, whose body says high": "true && f() { echo high; }; f; git log -1",
    "functions an if defines either way, whose bodies say right and up": (
        "if [ -f x ]; then say() { echo right; }; else say() { echo up; }; fi; say; git status"),
    "a function the call may define otherwise, whose body names github": (
        "true && f() { echo https://github.com; }; f; git status"),
    "a function the call may define otherwise, none of whose bodies names git": "true && f() { :; }; f; git log -1",
    "functions an if defines either way, called in a call that pushes nothing": (
        "if [ -f x ]; then log() { echo a; }; else log() { echo b; }; fi; log hi; git status"),
    "an empty array's assignment, in a call that pushes nothing": "files=(); git status",
    "a comment that holds a parameter expansion with an operator character": "git status # ${x%)}",
    "a default that runs a substitution holding a ;": "echo ${x:-$(git rev-parse HEAD; true)}; git status",
    "a parameter expansion with an operator character in single quotes": "echo '${x%)}'; git status",
    "a parameter expansion with an operator character in double quotes": 'echo "${x%)}"; git status',
    "a double-quoted default that holds a quote": """echo "${x:-it's}"; git status""",
    "a here-document whose text holds a parameter expansion with an operator character": (
        "cat <<'EOF'\n${x%)}\nEOF\ngit status"),
    "a comment in a substitution that holds a parameter expansion with an operator character": (
        "x=$(git status # ${y%)}\n); git log -1"),
    "a double-quoted default that holds a paired single-quoted word": '''echo "${x:-'a'}"; git status''',
    "a double-quoted default that holds a paired quote inside, a push of nothing after": (
        '''echo "${x:-'a' b}"; git push origin clean'''),
    "an array holding a process substitution, in a call that pushes nothing": (
        "a=(<(true)); git push origin clean"),
    "xargs running a program that reads, before a git argument": "git ls-files | xargs grep -l git",
    "xargs running echo with a git argument": "printf 'a\\n' | xargs echo git",
    "a function the call may define otherwise, whose body names variables whose names hold gh and git": (
        "true && f() { echo $GH_TOKEN $USE_GIT; }; f; git status"),
}
# Pushes the shell never runs that the hook reads anyway, and refuses.
OVER_READ = {
    "a source no ref names, read as every branch": "git push origin no-such-branch",
    "an echo of a push": "echo git push",
    "a git command the hook does not know, named like push": "git push-notes",
    "a `$` in a quoted word, read as a word the shell expands": "git push -o 'note=$5' origin clean",
    "a push after a function whose case holds an extended pattern, which bash parses only under extglob": (
        "f() ( case x in @(a|b)) cd @ELSEWHERE@;; esac ); git push origin work"),
    "a push after a function whose body echoes an extended pattern and a }, which bash parses only under extglob": (
        "f() { echo @(a|b) }; cd @ELSEWHERE@; }; git push origin work"),
}
# Read as a command that may move a commit, and so refused before a push: the shell runs none.
OVER_READ_ORDER = {
    "arithmetic": "((n = 1)); git push",
}
# A directory the hook cannot name: refused, whatever the commits hold.
UNNAMED = {
    "a function the call may define otherwise, whose body runs git by its path": (
        "true && f() { /usr/bin/git push origin work; }; f"),
    "a function the call may define otherwise, whose body runs git in capitals": (
        "true && f() { GIT push origin work; }; f"),
    "a variable": 'cd "$REPO" && git push',
    "a substitution": "cd $(git rev-parse --show-toplevel) && git push",
    "-C and a variable": 'git -C "$REPO" push',
    "a directory that does not exist yet": "cd /does/not/exist && git push",
    "a GIT_DIR from a variable": "GIT_DIR=$X git push",
    "cd - with no directory before": "cd - && git push",
    "a substitution after moves that leave OLDPWD as the call found it": (
        'cd "$REPO"; cd @ELSEWHERE@; : "$(git push)"'),
    # What may or may not run leaves the shell where its ways agree, and nowhere the hook can name otherwise.
    "an if whose else moves back": "if true; then cd @ELSEWHERE@; else cd @REPO@; fi; git push",
    "an elif chain whose else moves back": (
        "if false; then cd /tmp; elif true; then cd @ELSEWHERE@; else cd @REPO@; fi; git push"),
    "a case whose last arm moves back": "case x in x) cd @ELSEWHERE@;; *) cd @REPO@;; esac; git push",
    "a case whose patterns stand in parentheses": "case x in (x) cd @ELSEWHERE@;; (*) cd @REPO@;; esac; git push",
    "an arm a fallthrough reaches": "case x in x) cd @ELSEWHERE@;& y) git push;; esac",
    "a condition's move a skipped branch undoes": "if cd @ELSEWHERE@ && false; then cd @REPO@; fi; git push",
    "a return in a function's body": "f() { cd @ELSEWHERE@; return; cd @REPO@; }; f; git push",
    "a break in a loop's body": "for i in 1; do cd @ELSEWHERE@; break; cd @REPO@; done; git push",
    "a continue in a loop's body": "for i in 1; do cd @ELSEWHERE@; continue; cd @REPO@; done; git push",
    "a break an eval runs": "for i in 1; do cd @ELSEWHERE@; eval break; cd @REPO@; done; git push",
    "a loop whose later turn moves": "for i in 1 2; do popd; pushd -n @ELSEWHERE@; done; git push",
    "a list whose operator changes before a cd -": (
        "cd @REPO@; cd @ELSEWHERE@; true || OLDPWD=@ELSEWHERE@ && cd -; git push"),
    "an addition to GIT_DIR": "export GIT_DIR=@ELSEWHERE@/.git; export GIT_DIR+=x; git push",
    "an addition to HOME": "export HOME=@ELSEWHERE@; export HOME+=/x; cd; git push",
    "an addition to OLDPWD": "cd /tmp; export OLDPWD+=/x; cd -; git push",
    "an assignment a special builtin may keep": "GIT_DIR=@ELSEWHERE@/.git :; git push",
    "a substitution in a function another shell runs": (
        """f() { : "$(git push)"; }; export -f f; env -C @ELSEWHERE@ bash -c f"""),
    "a function a loop's turn redefines": "f() { :; }; for i in 1 2; do f; git push; f() { cd @ELSEWHERE@; }; done",
    "read -a's array, attached": "read -aGIT_DIR <<< x; git push",
    "read -ra's array, attached": "read -raGIT_DIR <<< x; git push",
    # Each variable, part of the state and signal the reader handles, on its own.
    # Each with its GIT_DIR named again, which the same unknown name makes one the hook cannot read.
    "a HOME a name another holds sets": "n=HOME; export $n=@ELSEWHERE@; cd; GIT_DIR=.git git push",
    "a CDPATH a name another holds sets": "n=CDPATH; export $n=@ELSEWHERE@; cd .claude; GIT_DIR=../.git git push",
    "an OLDPWD a name another holds sets": (
        "cd @ELSEWHERE@; cd @REPO@; n=OLDPWD; export $n=/tmp; cd -; GIT_DIR=.git git push"),
    "a PWD a name another holds sets, then cd -": (
        "n=PWD; export $n=@ELSEWHERE@; cd /tmp; cd -; GIT_DIR=.git git push"),
    "a DEBUG trap that sets a variable": "trap 'export GIT_DIR=@ELSEWHERE@/.git' DEBUG; cd @REPO@; git push",
    "a RETURN trap": "trap 'cd @ELSEWHERE@' RETURN; f() { :; }; f; git push",
    "a HOME env -i drops, then a new shell's cd": "env -i bash -c 'cd; git push'",
    "an OLDPWD sudo drops, then a new shell's cd -": (
        "OLDPWD=@ELSEWHERE@ sudo env -C @REPO@ bash -c 'cd - && git push'"),
    "printf -v's name, attached": "printf -vGIT_DIR %s @ELSEWHERE@/.git; git push",
    "an expansion that assigns an element": ": ${GIT_DIR[0]:=@ELSEWHERE@/.git}; git push",
    "a loop whose turn sets a variable it follows": "for i in 1 2; do git push; export GIT_DIR=@ELSEWHERE@/.git; done",
    "an OLDPWD the ways of an if leave apart": "cd @REPO@; if true; then cd @ELSEWHERE@; cd @REPO@; fi; cd -; git push",
    "a stack the ways of an if leave apart": "if true; then pushd -n @ELSEWHERE@; fi; popd; git push",
    "a variable one way of an if sets": "if [ -d /nonexistent ]; then export GIT_DIR=@ELSEWHERE@/.git; fi; git push",
    "a variable an else sets": "if true; then :; else export GIT_DIR=@ELSEWHERE@/.git; fi; git push",
    "an elif with no else, whose conditions may all fail": (
        "if false; then cd @ELSEWHERE@; elif false; then cd @ELSEWHERE@; fi; git push"),
    "a loop whose turn moves OLDPWD, which its cd - reads": (
        "cd @ELSEWHERE@; cd @REPO@; for i in 1 2; do cd -; git push; cd /tmp; cd @REPO@; done"),
    "a DEBUG trap's move, with GIT_DIR named again": "trap 'cd @ELSEWHERE@' DEBUG; GIT_DIR=.git git push",
    "a sudo another wrapper runs, then a new shell's cd -": (
        "OLDPWD=@ELSEWHERE@ nice sudo env -C @REPO@ bash -c 'cd - && git push'"),
    "env's long --unset of a name a variable holds": (
        'export GIT_DIR=@ELSEWHERE@/.git; n=GIT_DIR; env --unset="$n" git push'),
    "a loop's variable named HOME": "for HOME in @ELSEWHERE@; do cd; GIT_DIR=.git git push; done",
    "an unexported HOME a piped new shell does not get": (
        "export HOME=@ELSEWHERE@; export -n HOME; true | bash -c 'cd; GIT_DIR=.git git push'"),
    "a function's OLDPWD prefix, gone after the call": "f() { :; }; OLDPWD=@ELSEWHERE@ f; cd - && git push",
    "a break out of two loops": (
        "for i in 1; do for j in 1; do cd @ELSEWHERE@; break 2; done; cd @REPO@; done; git push"),
    "an OLDPWD a loop's turn may leave elsewhere": (
        "cd @ELSEWHERE@; cd @REPO@; while false; do cd /tmp; cd @REPO@; done; cd -; git push"),
    "a variable one way of an if unexports": (
        "export GIT_DIR=@ELSEWHERE@/.git; if [ -d /x ]; then export -n GIT_DIR; fi; git push"),
    "a for loop that may run no turn": "for f in; do cd @ELSEWHERE@; done; git push",
    "a substitution after a move": 'cd .claude && echo "$(git push)"',
    "a cd along a CDPATH the call sets": "CDPATH=@REPO@; cd .claude && git push",
    "cd after the call unsets HOME": "unset HOME; cd; git push",
    "a GIT_DIR read from input": "export GIT_DIR=@REPO@/.git; read -r GIT_DIR <<< x; git push",
    "a GIT_DIR printf -v sets": "export GIT_DIR=@REPO@/.git; printf -v GIT_DIR %s x; git push",
    "pushd -n and a relative directory, then popd": "pushd -n .claude && popd && git push",
    "pushd -n +1, which bash carries out oddly": "pushd /tmp && pushd -n +1 && git push",
    "popd and two words": "pushd /tmp && popd -- +1 && git push",
    "a GIT_DIR assigned alone, which the shell may export": "GIT_DIR=@REPO@/.git; git push",
    "GIT_COMMON_DIR": "GIT_COMMON_DIR=@REPO@/.git git push",
    "GIT_OBJECT_DIRECTORY": "GIT_OBJECT_DIRECTORY=/tmp/objects git push",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES": "GIT_ALTERNATE_OBJECT_DIRECTORIES=/tmp/objects git push",
    "GIT_NAMESPACE": "GIT_NAMESPACE=x git push",
    "an exported GIT_NAMESPACE": "export GIT_NAMESPACE=x; git push",
    "--namespace": "git --namespace=x push",
    "--namespace and a separate value": "git --namespace x push",
    "cd -P through a file and up, which fails": "cd -P @ELSEWHERE@/e.py/..; git push origin work",
    "cd through a directory that does not exist and up": "cd @ELSEWHERE@/missing/..; git push origin work",
    "cd -L through a directory that does not exist and up": "cd -L @ELSEWHERE@/missing/..; git push origin work",
    "cd --, then a word like an option, a directory": "cd -- -P; git push origin work",
    "cd and an option bash refuses": "cd -x @ELSEWHERE@; git push origin work",
    "a quoted ~": "cd '~'; git push origin work",
    "a ~ and a quoted slash": "cd ~'/'; git push origin work",
    "--git-dir= and a ~, which git takes as written": "git --git-dir=~/.git push origin work",
    "sudo, whose options or policy may move it": "sudo git push origin work",
    "a wrapper's sudo": "nice sudo git push origin work",
    "env and an option the hook does not read": "env --ch @REPO@ git push origin work",
    "a substitution between a GIT_DIR's export and its unset": (
        'export GIT_DIR=@REPO@/.git; : "$(git push origin work)"; unset GIT_DIR'),
    "a substitution's move to a literal path, with the line's GIT_DIR": (
        'export GIT_DIR=@REPO@/.git; : "$(cd @ELSEWHERE@ && git push origin work)"; unset GIT_DIR'),
    # FOLLOWED's other names: a subshell or an eval undoes the change, so only the line's text tells.
    "a substitution after a subshell's HOME": '(export HOME=@ELSEWHERE@; : "$(git push origin work)")',
    "a substitution after a subshell's CDPATH": '(CDPATH=@ELSEWHERE@; : "$(cd .claude && git push origin work)")',
    "a substitution after an eval's OLDPWD": "cd /tmp && eval 'OLDPWD=@ELSEWHERE@; : \"$(cd - && git push origin work)\"'",
    "a substitution after a subshell's XDG_CONFIG_HOME": '(export XDG_CONFIG_HOME=/tmp; : "$(git push origin work)")',
    "a substitution after a subshell's GIT_CONFIG_*": (
        '(export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=push.default GIT_CONFIG_VALUE_0=matching; : "$(git push)")'),
    # QUOTED_TILDE's first alternative, a quote before the ~ alone (`'~'` matches both).
    "a quoted ~ and a path": "cd '~/.claude'; git push origin work",
    "an escaped ~": "cd \\~; git push origin work",
    "cd -L through a file and up, which fails": "cd -L @ELSEWHERE@/e.py/..; git push origin work",
    "a relative OLDPWD after a cd the hook cannot name": 'cd "$X"; OLDPWD=.@REPO@; cd - && git push origin work',
    "cd and an option after its directory, which bash takes as a second one": "cd @ELSEWHERE@ -P; git push origin work",
    # A variable the call names by another's value may be any the hook follows.
    "an export of a name a variable holds": "n=GIT_DIR; export $n=@REPO@/.git; git push origin work",
    "an unset of a name a variable holds": "export GIT_DIR=@ELSEWHERE@/.git; n=GIT_DIR; unset $n; git push origin work",
    "env -u and a name a variable holds": 'export GIT_DIR=@ELSEWHERE@/.git; n=GIT_DIR; env -u "$n" git push origin work',
    "read and a name a variable holds": "n=GIT_DIR; read -r $n <<< x; git push origin work",
    # Variables the call sets in other forms.
    "read -a's array": "export GIT_DIR=@ELSEWHERE@/.git; read -a GIT_DIR <<< x; git push origin work",
    "read -ra's array, the value of a group's last option": (
        "export GIT_DIR=@ELSEWHERE@/.git; read -ra GIT_DIR <<< x; git push origin work"),
    "read of an element, which makes the variable an array": (
        "export GIT_DIR=@ELSEWHERE@/.git; read 'GIT_DIR[0]' <<< x; git push origin work"),
    "wait -p, which unsets its variable first": (
        "export GIT_DIR=@ELSEWHERE@/.git; sleep 0 & wait -n -p GIT_DIR; git push origin work"),
    "a for loop's variable": "for GIT_DIR in @ELSEWHERE@/.git; do git push origin work; done",
    "a select loop's variable": "select GIT_DIR in @ELSEWHERE@/.git; do git push origin work; break; done",
    "a parameter expansion that assigns": ": ${GIT_DIR:=@ELSEWHERE@/.git}; export GIT_DIR; git push origin work",
    "one that assigns when the variable is unset": ": ${GIT_DIR=@ELSEWHERE@/.git}; export GIT_DIR; git push origin work",
    "one that assigns the variable another names": "n=GIT_DIR; : ${!n:=@ELSEWHERE@/.git}; git push origin work",
    "an arithmetic expansion that assigns": "HOME=@REPO@; : $((HOME = 0)); cd; git push origin work",
    # A move that may or may not run, or that a trap makes between commands.
    "a cd after a command that may fail": "false && cd @ELSEWHERE@; git push origin work",
    "a cd after one that may fail": "cd @REPO@ || cd @ELSEWHERE@; git push origin work",
    "a cd a test guards": "[ -d /nonexistent ] && cd @ELSEWHERE@; git push origin work",
    "an if's cd": "if [ -d /nonexistent ]; then cd @ELSEWHERE@; fi; git push origin work",
    "an else's cd": "if [ -d /tmp ]; then :; else cd @ELSEWHERE@; fi; git push origin work",
    "a case's cd": "case x in y) cd @ELSEWHERE@;; esac; git push origin work",
    "a while loop's cd": "while false; do cd @ELSEWHERE@; done; git push origin work",
    "a loop's later turn, after its cd": "for i in 1 2; do git push origin work; cd @ELSEWHERE@; done",
    "a function's return before its cd": "f() { return; cd @ELSEWHERE@; }; f; git push origin work",
    "an export that may not run": "false && export GIT_DIR=@ELSEWHERE@/.git; git push origin work",
    "an unset that may not run": "export GIT_DIR=@REPO@/.git; true || unset GIT_DIR; git push origin work",
    "a DEBUG trap, between the commands after it": "trap 'cd @ELSEWHERE@' DEBUG; git push origin work",
    "an ERR trap, named in any case": "trap 'cd @ELSEWHERE@' err; git push origin work",
    # PWD, from which bash's cd takes OLDPWD, and a new shell its directory.
    "an exported PWD before a substitution": 'export PWD=@ELSEWHERE@; : "$(git push origin work)"',
    "cd - to a PWD the call sets": "PWD=@ELSEWHERE@; cd /tmp; cd -; git push origin work",
    "cd - after the call unsets PWD": "unset PWD; cd /tmp; cd -; git push origin work",
    "a new shell given a PWD": "PWD=/tmp bash -c 'cd .. && git push origin work'",
    "popd to the - pushd -n put on the stack, which it reads then": (
        "cd /tmp && pushd -n - && cd @ELSEWHERE@ && cd /tmp && popd && git push origin work"),
    "an eval's cd before a substitution": 'eval cd @ELSEWHERE@; : "$(git push origin work)"',
    # sudo's policy keeps or drops the variables the call gave.
    "sudo's policy, which may drop a GIT_DIR the call exports": (
        "export GIT_DIR=@ELSEWHERE@/.git; sudo env -C @REPO@ git push origin work"),
    # What a program the command runs gets: the variables the shell exports.
    "a HOME export -n keeps from a new shell": "export HOME=@ELSEWHERE@; export -n HOME; bash -c 'cd; git push origin work'",
    "a HOME assigned after unset, which a new shell does not get": (
        "unset HOME; HOME=@ELSEWHERE@; bash -c 'cd; git push origin work'"),
    "a new shell's cd -, to an OLDPWD it may not get": "OLDPWD=@ELSEWHERE@; bash -c 'cd -; git push origin work'",
    "a HOME export -n may keep from a new shell": (
        "export HOME=@ELSEWHERE@; false || export -n HOME; bash -c 'cd; git push origin work'"),
    # A push another program holds, which it may run anywhere.
    "a push watch runs": "watch -n 5 git push",
    "words parallel adds to a push it runs": "echo work | parallel git push origin",
    "a push find runs in each directory it finds": "find @REPO@/.git -maxdepth 0 -execdir git push origin work \\;",
    "a program a wrapper runs, holding a push": "nice find @REPO@/.git -maxdepth 0 -execdir git push origin work \\;",
    # A word up to git's command that bash may expand to other words may be an option the hook would read.
    "an option a variable holds, before git's command": "o=-C; git $o @ELSEWHERE@ push origin work",
    "a command a variable holds, with options in it": "o='-C @ELSEWHERE@ push'; git $o origin work",
    "a -c value a variable holds, which may split into options": "git -c $c push origin work",
    "an option a substitution prints": "git $(echo -C) @ELSEWHERE@ push origin work",
    "an option in backquotes": "git `echo -C` @ELSEWHERE@ push origin work",
    "backquotes in a value before git's command": "git -c x=`echo 1 -C @ELSEWHERE@` push origin work",
    "backquotes in a shell's string": "bash -c 'git `echo -C` @ELSEWHERE@ push origin work'",
    "an option an escape spells": "git $'\\x2dC' @ELSEWHERE@ push origin work",
    "an option a brace expansion spells": "git {-C,@ELSEWHERE@} push origin work",
    "an option a brace sequence spells": "git -{C..C} @ELSEWHERE@ push origin work",
    # A shell other than bash (sh may be dash) reads these otherwise, and git runs a shell alias with sh.
    "pushd in sh, which dash does not have": "sh -c 'pushd @ELSEWHERE@ >/dev/null; git push origin work'",
    "popd in sh": "sh -c 'popd; git push origin work'",
    "a shell alias's pushd": "git -c 'alias.ship=!pushd @ELSEWHERE@ >/dev/null; git push origin work' ship",
    "cd -e in sh, which dash refuses": "sh -c 'cd -e @ELSEWHERE@; git push origin work'",
    "a ~ in env's word in sh, which dash leaves as written": (
        "HOME=@ELSEWHERE@ sh -c 'env GIT_DIR=~/.git git push origin work'"),
    "a ~ in env's word in bash's POSIX mode, which leaves it as written": (
        "HOME=@ELSEWHERE@ bash --posix -c 'env GIT_DIR=~/.git git push origin work'"),
    "a $'' quote in sh, which dash reads as $ and a string": "sh -c \"cd $'@ELSEWHERE@'; git push origin work\"",
    'a $"" quote in sh': """sh -c 'cd $"@ELSEWHERE@"; git push origin work'""",
    # A function the hook cannot read may push.
    "a push a function an && list may define holds": "true && f() { git push origin work; }; f",
    "a push a function sh may keep after unset holds": "sh -c 'f() { git push origin work; }; unset f; f'",
    "a push a function a loop's turn redefines holds": "g() { g() { git push origin work; }; }; for i in 1 2; do g; done",
    "a push with a relative GIT_DIR a function a loop's turn redefines holds": (
        "g() { g() { GIT_DIR=.git git push origin work; }; }; for i in 1 2; do g; done"),
    # Where a case's arm and an and-or list's pipeline may start.
    "an arm after one ;;& ended, past a pattern between": (
        "case x in x) cd @ELSEWHERE@;;& y) :;; *) git push origin work;; esac"),
    "a pipeline after an && run that may fail at any of its pipelines": (
        "false && cd @ELSEWHERE@ && true || git push origin work"),
    "a pipeline after an || run that may succeed at any of its pipelines": (
        "true || cd @ELSEWHERE@ || cd @ELSEWHERE@ && git push origin work"),
    "a substitution inside one that moves first": ': "$(cd @ELSEWHERE@ && : "$(git push origin work)")"',
    # A for that may run no turn, and a continue's turn, each where nothing else in its case masks it.
    "a variable a for that may run no turn sets": (
        "for i in $X; do export GIT_DIR=@ELSEWHERE@/.git; done; cd @REPO@; git push origin work"),
    "a push in a loop whose continue leaves the shell elsewhere": (
        "for i in 1 2; do git push origin work; cd @ELSEWHERE@; continue; cd @REPO@; done"),
    "a fallthrough after an arm that ends in fi": "case x in x) if true; then cd @ELSEWHERE@; fi;& y) git push;; esac",
    "a ;;& after an arm that ends in done": (
        "case x in x) for i in 1; do cd @ELSEWHERE@; done;;& *) git push;; esac"),
    "a fallthrough from a group the case may skip": "case z in (x) { cd @ELSEWHERE@; };& (z) git push;; esac",
    "a fallthrough after an arm an inner case ends": (
        "case a in a) case b in b) cd @ELSEWHERE@;; esac;& c) git push;; esac"),
    "a case whose in follows a newline": "case x\nin x) cd @ELSEWHERE@;; esac; git push",
    "a pattern esac in parentheses": "case esac in (esac) cd @ELSEWHERE@;; esac; git push",
    "a pattern esac after a |": "case x in y) :;; x|esac) cd @ELSEWHERE@;; esac; git push",
    "an until whose condition moves the shell before its next turn": "until git push; cd @ELSEWHERE@ && false; do :; done",
    "a variable a while's turn sets, which a push after it reads": (
        "while [ -d /x ]; do export GIT_DIR=@ELSEWHERE@/.git; done; cd @REPO@; git push"),
    "an OLDPWD a loop's later turn moves": "cd @REPO@; for i in 1 2; do cd @ELSEWHERE@; done; cd -; git push",
    "a stack a loop's later turn changes": (
        "pushd -n @REPO@; for i in 1 2; do popd -n; pushd @ELSEWHERE@; done; popd; git push"),
    "a loop whose turn unexports a variable it follows": (
        "export GIT_DIR=@ELSEWHERE@/.git; for i in 1 2; do git push; export -n GIT_DIR; done"),
    "a break count the hook cannot read, which may leave both loops": (
        "for i in 1; do for j in 1; do cd @ELSEWHERE@; break $n; done; cd @REPO@; done; git push"),
    "a substitution inside one that exports GIT_DIR first": (
        ': "$(export GIT_DIR=@ELSEWHERE@/.git; : "$(git push origin work)")"'),
    "backquotes inside a substitution that moves first": ': "$(cd @ELSEWHERE@ && : `git push origin work`)"',
    "a substitution inside one that redefines its function first": (
        """f() { :; }; eval ': "$(f() { cd @ELSEWHERE@; }; : "$(f; git push origin work)")"'"""),
    "a substitution inside one whose cd the hook cannot follow": ': "$(cd a b; : "$(git push origin work)")"',
    "pushd in sh after a bash -c in it": "sh -c 'bash -c true; pushd @ELSEWHERE@ >/dev/null; git push origin work'",
    "an and-or list whose operator changes twice": "true && cd @ELSEWHERE@ || cd @REPO@ && git push",
    "an addition to a relative GIT_DIR": "export GIT_DIR=x; export GIT_DIR+=@REPO@/.git; git push",
    "an unexported addition to a relative GIT_DIR, exported again": (
        "export -n GIT_DIR=x; export -n GIT_DIR+=@REPO@/.git; export GIT_DIR; git push"),
    "an assignment eval may keep": "GIT_DIR=@ELSEWHERE@/.git eval true; git push",
    "an option a glob may spell, before git's command": "git -? @ELSEWHERE@ push origin work",
    "an option a star may spell, before git's command": "git -* @ELSEWHERE@ push origin work",
    "an option a bracket may spell, before git's command": "git -[C] @ELSEWHERE@ push origin work",
    "a function the call may define otherwise, whose body runs gh": "true && f() { gh pr create; }; f",
    "a push a function a loop's turn defines before its continue holds": (
        "f() { :; }; for i in 1 2; do f; if [ -e a.py ]; then f() { git push origin work; }; continue; fi; "
        "f() { :; }; done"),
    "a push in an inner loop whose continue count the hook cannot read": (
        "for i in 1; do cd @ELSEWHERE@; for j in 1 2; do git push origin work; cd @REPO@; continue $n; "
        "cd @ELSEWHERE@; done; cd @REPO@; done"),
    "a push in an outer loop an inner continue 2 turns from elsewhere": (
        "for i in 1 2; do git push origin work; for j in 1; do cd @ELSEWHERE@; continue 2; done; cd @REPO@; done"),
    "a function set -a exports to a new shell": "set -a; f() { git push origin work; }; bash -c f",
    "a function set -o allexport exports to a new shell": "set -o allexport; f() { git push origin work; }; bash -c f",
    "time in sh before a function that pushes, which dash runs as a program": (
        "sh -c 'f() { git push origin work; }; time f'"),
    "an option in backquotes in double quotes": 'git "`echo -C`" @ELSEWHERE@ push origin work',
    # A process substitution among a command's words is one of them: the cd then has two.
    "a cd given a process substitution as well": "cd @ELSEWHERE@ <(true); git push origin work",
    "a cd given a process substitution after one its output goes to": (
        "cd @ELSEWHERE@ > >(cat) <(true); git push origin work"),
    "a pushd given a process substitution as well": "pushd @ELSEWHERE@ <(true); git push origin work",
    # A redirection that may fail runs no command it belongs to.
    "a cd whose input file may be missing": "cd @ELSEWHERE@ < missing; git push origin work",
    "a cd whose errors go to a descriptor the shell may not hold open": "cd @ELSEWHERE@ 2>&3; git push origin work",
    "a cd whose input copies a descriptor from a word, an ambiguous redirect": (
        "cd @ELSEWHERE@ <& missing; git push origin work"),
    "a cd whose errors copy a descriptor from /dev/null, an ambiguous redirect": (
        "cd @ELSEWHERE@ 2>& /dev/null; git push origin work"),
    "a cd whose input copies a descriptor from a process substitution": (
        "cd @ELSEWHERE@ <& <(true); git push origin work"),
    "a cd whose errors copy a descriptor to a process substitution": "cd @ELSEWHERE@ 2>& >(true); git push origin work",
    "a cd whose output goes to a terminal the shell may not have": "cd @ELSEWHERE@ > /dev/tty; git push origin work",
    "a group whose input file may be missing": "{ cd @ELSEWHERE@; } < missing; git push origin work",
    "a function whose definition's input file may be missing": (
        "f() { cd @ELSEWHERE@; } < missing; f; git push origin work"),
    "an export whose errors copy a descriptor from /dev/null": (
        "export GIT_DIR=@ELSEWHERE@/.git 2>& /dev/null; git push origin work"),
    "a GIT_DIR an addition changes": "export GIT_DIR=@REPO@/.git; GIT_DIR+=x; git push origin work",
    "a HOME an addition changes, then cd": "HOME+=@ELSEWHERE@; cd; git push origin work",
    "a GIT_DIR an element's assignment changes": (
        "export GIT_DIR=@ELSEWHERE@/.git; GIT_DIR[0]=@REPO@/.git; git push origin work"),
    # A loop whose turn moves runs its pushes from a directory the hook cannot name, a process substitution its
    # redirection names among them, though bash runs that once, from where the loop began.
    "a loop whose turn moves, its input from a process substitution that pushes": (
        "while false; do cd @ELSEWHERE@; done < <(git push origin work)"),
    "a group whose input file may be missing, after a nested group": (
        "{ cd @ELSEWHERE@; { :; } } < missing; git push origin work"),
    "an if whose input file may be missing, after its nested group": (
        "{ cd @ELSEWHERE@; if true; then :; fi } < missing; git push origin work"),
    "a descriptor a name holds, copied onto a word": (
        "export GIT_DIR=@ELSEWHERE@/.git {fd}>&/dev/null; git push origin work"),
    "a descriptor a name holds, closed": (
        "export GIT_DIR=@ELSEWHERE@/.git {fd}>&-; git push origin work"),
    "a function the call may define otherwise, whose body runs git in a string a shell runs": (
        "true && f() { bash -c 'cd @REPO@;git push origin work'; }; f"),
}
# Writes the hook refuses outright: git builds the commits as it runs, or GitHub's API takes the content.
OUTRIGHT = {
    "git subtree push": ("git subtree push --prefix=docs origin docs", "git subtree push"),
    "git subtree -P, then push": ("git subtree -P docs push origin docs", "git subtree push"),
    "a push nested six deep": ("eval eval eval eval eval eval git push", "more than five levels deep"),
    "process substitutions nested six deep": (
        "cat <(cat <(cat <(cat <(cat <(cat <(git push))))))", "more than five levels deep"),
    "a function that calls itself": ("f() { git push origin work; f; }; f", "more than five levels deep"),
    "functions nested six deep": ("f1() { f2; }; f2() { f3; }; f3() { f4; }; f4() { f5; }; f5() { f6; }; "
                                  "f6() { git push; }; f1", "more than five levels deep"),
    "gh api -X=PUT": ("gh api -X=PUT repos/o/r/contents/f.txt -f content=Zm9v", "PUT repos/o/r/contents/f.txt"),
    "curl to the host's port": ("curl -X PUT https://api.github.com:443/repos/o/r/contents/x -d @b.json",
                                "PUT repos/o/r/contents/x"),
    "curl to the host in capitals": ("curl -X PUT https://API.GITHUB.COM/repos/o/r/contents/x -d @b.json",
                                     "PUT repos/o/r/contents/x"),
    "git send-pack": ("git send-pack origin refs/heads/work", "git send-pack"),
    "git http-push": ("git http-push https://example.com/repo.git work", "git http-push"),
    "gh api PUT to contents": ("gh api -X PUT repos/o/r/contents/f.txt -f message=m -f content=Zm9v", "PUT repos/o/r/contents/f.txt"),
    "gh api --method PUT, placeholders, --input": (
        "gh api --method PUT /repos/{owner}/{repo}/contents/f.txt --input body.json", "a file to a repository's contents"),
    "gh api --method=PUT": ("gh api --method=PUT repos/o/r/contents/f.txt --input body.json", "PUT repos/o/r/contents/f.txt"),
    "gh api -XPUT attached": ("gh api -XPUT repos/o/r/contents/f.txt -fcontent=Zm9v", "PUT repos/o/r/contents/f.txt"),
    "a blob by fields (a POST)": ("gh api repos/o/r/git/blobs -f content=x", "POST repos/o/r/git/blobs"),
    "a tree by --input (a POST)": ("gh api repos/o/r/git/trees --input tree.json", "POST repos/o/r/git/trees"),
    "a commit by -F": ("gh api repos/o/r/git/commits -F message=m -F tree=abc", "POST repos/o/r/git/commits"),
    "createCommitOnBranch": (
        "gh api graphql -f query='mutation { createCommitOnBranch(input: {}) { commit { oid } } }'",
        "createCommitOnBranch"),
    "curl -X PUT": ("curl -X PUT -H 'Authorization: token x' https://api.github.com/repos/o/r/contents/f.txt -d @body.json",
                    "PUT repos/o/r/contents/f.txt"),
    "curl -XPUT": ("curl -sS -XPUT https://api.github.com/repos/o/r/contents/f.txt --data-binary @body.json",
                   "PUT repos/o/r/contents/f.txt"),
    "curl --request=PUT": ("curl --request=PUT api.github.com/repos/o/r/contents/f.txt -d @b.json", "PUT repos/o/r/contents/f.txt"),
    "curl -T (a PUT)": ("curl -T body.json https://api.github.com/repos/o/r/contents/f.txt", "PUT repos/o/r/contents/f.txt"),
    "curl -d to blobs (a POST)": ("curl https://api.github.com/repos/o/r/git/blobs -d '{}'", "POST repos/o/r/git/blobs"),
    "curl to graphql": ("curl -sS https://api.github.com/graphql -d '{\"query\": \"mutation { createCommitOnBranch }\"}'",
                        "createCommitOnBranch"),
    "a wrapper": ("sudo gh api -X PUT repos/o/r/contents/f.txt -f content=Zm9v", "PUT repos/o/r/contents/f.txt"),
    "a shell given a string": ('bash -c "gh api -X PUT repos/o/r/contents/f.txt -f content=Zm9v"', "PUT repos/o/r/contents/f.txt"),
    "after a push": ("git push origin main && gh api -X PUT repos/o/r/contents/f.txt -f content=Zm9v", "PUT repos/o/r/contents/f.txt"),
    "a case in a substitution, with a pattern no ( opens": (
        ': "$(case x in x) git push origin work;; esac)"', "a case in a command substitution"),
    "a function's body with no end": ("f() { :; git push origin work", "whose end the hook cannot find"),
    "a function the keyword defines with no end": ("function f { :; git push origin work", "whose end the hook cannot find"),
    "a process substitution with no end": ("cat <(case x in (x) :;;); git push origin work",
                                           "whose end the hook cannot find"),
    "a case after a command in a substitution": (
        ': "$(true; case x in x) git push origin work;; esac)"', "a case in a command substitution"),
    "a subshell's case in a substitution, whose pattern ends the substitution early": (
        "x=$( (case a in a) :;; esac); cd @ELSEWHERE@ ); git push origin work", "a case in a command substitution"),
    # A `${...}` whose word holds an operator character, which the shell reader splits where bash reads one word.
    "a default of ) in a subshell": (
        "(echo ${x:-)}; cd @ELSEWHERE@); git push origin work", "a parameter expansion the shell reader splits"),
    "a suffix of ) stripped in a subshell": (
        "(v=${x%)}; cd @ELSEWHERE@); git push origin work", "a parameter expansion the shell reader splits"),
    "a default that holds a cd": (
        "echo ${x:-;cd @ELSEWHERE@;}; git push origin work", "a parameter expansion the shell reader splits"),
    "a prefix of ( stripped in a subshell": (
        "(v=${x#(}; cd @ELSEWHERE@); git push origin work", "a parameter expansion the shell reader splits"),
    "a parameter expansion with no end": (
        "echo ${x; git push origin work", "a parameter expansion the shell reader splits"),
    "a prefix of ( and a suffix of ) stripped": (
        "v=${x#(}; cd @REPO@; w=${v%)}; git push origin work", "a parameter expansion the shell reader splits"),
    "a default in double quotes that holds a quoted )": (
        '(v="${x:-")"}"; cd @ELSEWHERE@); git push origin work', "a parameter expansion the shell reader splits"),
    "a suffix of ) stripped, in a call that pushes nothing": (
        "echo ${x%)}; git status", "a parameter expansion the shell reader splits"),
    # Read as the shell reader reads each line: past its quotes and here-documents, in each string it reads.
    "a suffix of ) stripped after a $'...' that escapes a quote": (
        r"echo $'it\'s'; (v=${x%)}; cd @ELSEWHERE@); git push origin work",
        "a parameter expansion the shell reader splits"),
    "a suffix of ) stripped after an escaped quote": (
        r"echo it\'s; (v=${x%)}; cd @ELSEWHERE@); git push origin work", "a parameter expansion the shell reader splits"),
    "a suffix of ) stripped after a here-document whose text holds a quote": (
        "cat <<'EOF'\nit's\nEOF\n(v=${x%)}; cd @ELSEWHERE@); git push origin work",
        "a parameter expansion the shell reader splits"),
    "a suffix of ) stripped in a new shell's string": (
        "bash -c '(v=${x%)}; cd @ELSEWHERE@); git push origin work'", "a parameter expansion the shell reader splits"),
    "a suffix of ) stripped in an eval's string": (
        "eval '(v=${x%)}; cd @ELSEWHERE@)'; git push origin work", "a parameter expansion the shell reader splits"),
    "a double-quoted default that nests a quoted word, in a call that pushes nothing": (
        'echo "${x:-"a"}"; git status', "a parameter expansion the shell reader splits"),
    "a double-quoted default that nests a quoted word with a quote in it": (
        '(v="${x:-"it\'s)"}"; cd @ELSEWHERE@); git push origin work', "a parameter expansion the shell reader splits"),
    "a push after a double-quoted default that nests a quoted word with a quote in it": (
        'v="${x:-"it\'s"}"; (cd @ELSEWHERE@); git push origin work', "a parameter expansion the shell reader splits"),
    "a suffix of ) stripped in a command substitution": (
        "out=$( (v=${x%)}; cd @ELSEWHERE@); git push origin work )", "a parameter expansion the shell reader splits"),
    # A function's body that is no compound command the hook reads.
    "a function whose body is a [[ ]] test": (
        "f() [[ -n x ]]; cd @REPO@; { :; }; git push origin work", "whose end the hook cannot find"),
    "a function whose body is a [[ ]] test, in a group": (
        "{ f() [[ -n x ]]; cd @REPO@; }; git push origin work", "whose end the hook cannot find"),
    "a double-quoted default that nests a quote after an escaped brace": (
        "(v=\"${x:-\\}\"it's\"}\"; cd @ELSEWHERE@); git push origin work",
        "a parameter expansion the shell reader splits"),
    "a double-quoted default that nests a quote after a quoted brace": (
        "(v=\"${x:-'}'\"it's\"}\"; cd @ELSEWHERE@); git push origin work",
        "a parameter expansion the shell reader splits"),
    "a double-quoted default that nests a backquote": (
        "(v=\"${x:-`echo }`\"a\"}\"; cd @ELSEWHERE@); git push origin work",
        "a parameter expansion the shell reader splits"),
    "a here-document word in a parameter expansion": (
        "printf '%s\\n' ${x:-<<EOF}\n(cd @ELSEWHERE@); git push origin work\nEOF",
        "it reads as a here-document"),
    "a here-document word in an arithmetic expansion": (
        "echo $[1<<2]\n(cd @ELSEWHERE@); git push origin work\n2", "it reads as a here-document"),
    "a here-document word in a subscript": (
        "a[1<<2]=x\n(cd @ELSEWHERE@); git push origin work\n2", "it reads as a here-document"),
    "a function whose body dash reads as a simple command": (
        "sh -c 'f() cd /; cd @REPO@; if true; then :; fi; git push origin work'", "whose end the hook cannot find"),
}
# API calls that add no content to a repository's history.
API_PASSES = {
    "a read of contents": "gh api repos/o/r/contents/README.md",
    "a read with a field and GET": "gh api -X GET repos/o/r/contents/x -f ref=main",
    "a delete of a file": "gh api -X DELETE repos/o/r/contents/x -f message=m -f sha=abc",
    "a ref read": "gh api repos/o/r/git/refs/heads/main",
    "a ref moved to a commit GitHub has": "gh api -X PATCH repos/o/r/git/refs/heads/x -f sha=abc",
    "a GraphQL query": "gh api graphql -f query='{ viewer { login } }'",
    "a pull request": "gh pr create --title x --body y",
    "curl reading contents": "curl https://api.github.com/repos/o/r/contents/x",
    "curl deleting a file": "curl -X DELETE https://api.github.com/repos/o/r/contents/x -d @d.json",
    "curl to another host": "curl -X PUT https://example.com/repos/o/r/contents/x -d @b.json",
}
MUTATION = "mutation { createCommitOnBranch(input: {}) { commit { oid } } }"
# GraphQL writes and reads whose text a file the command names holds, written first: (files, command, refused).
API_FILES = {
    "a mutation in the file -F names": ({"m.graphql": MUTATION}, "gh api graphql -F query=@m.graphql", True),
    "a mutation in the file --input names": (
        {"body.json": json.dumps({"query": MUTATION})}, "gh api graphql --input body.json", True),
    "a mutation in the file curl's -d names": (
        {"body.json": json.dumps({"query": MUTATION})}, "curl -sS https://api.github.com/graphql -d @body.json", True),
    "a mutation in a file in a directory the call moves to": (
        {"sub/body.json": json.dumps({"query": MUTATION})},
        "cd sub && curl -sS https://api.github.com/graphql --data-binary @body.json", True),
    "a query in the file -F names": ({"q.graphql": "{ viewer { login } }"}, "gh api graphql -F query=@q.graphql", False),
}
# The stated gaps, which pass through with the planted line on `work`. They are the PreToolUse reading's: git's
# pre-push hook stops each push among them as git sends it, in a clone that turns it on (PRE_PUSHES, below).
GAPS = {
    "a push a script runs": "./push.sh",
    "a push under a shell alias or function": "g push",
    "a push a variable holds": "$PUSH",
    "a git a variable names": "$GIT push",
    "a git a substitution names": "$(which git) push",
    "a git an escape spells": "$'\\x67it' push",
    "a push in a here-document fed to a shell": "bash <<'EOF'\ngit push\nEOF",
    "content another program sends through GitHub's API": (
        "wget --method=PUT --body-file=b.json https://api.github.com/repos/o/r/contents/x"),
    "content httpie sends": "http PUT api.github.com/repos/o/r/contents/x content=Zm9v",
    "a URL a variable holds": 'curl -X PUT "$URL" -d @b.json',
    "a GraphQL mutation from standard input": "gh api graphql -F query=@- < m.graphql",
    "a GraphQL mutation a variable holds": 'gh api graphql -f query="$MUTATION"',
    "a push a program runs": """python3 -c 'import subprocess; subprocess.run(["git", "push", "origin", "work"])'""",
    "a push env -S splits from one word": "env -S 'git push origin work'",
    "a command substitution in an unquoted here-document's text": "cat <<EOF\n$(git push origin work)\nEOF",
    "a `$((` that bash reads as a command substitution": "echo $((git push origin work) )",
    "a git a brace expansion spells": "{g..g}it push origin work",
    "a git a glob spells": "/usr/bin/[g]it push origin work",
    "a break an older bash compatibility level lets leave its caller's loop": (
        "cd @ELSEWHERE@; BASH_COMPAT=43; f() { break; }; for i in 1; do cd @REPO@; f; cd @ELSEWHERE@; done; "
        "git push origin work"),
    "set -k's assignment among a command's arguments": "set -k; git -C @ELSEWHERE@ push origin work GIT_DIR=@REPO@/.git",
    "a variable another arithmetic expression assigns": "HOME=@ELSEWHERE@; : $[HOME = 0]; cd; git push origin work",
    "a push in an EXIT trap when set -e stops the shell before its end": (
        "cd @ELSEWHERE@; trap 'git push origin work' EXIT; set -e; cd @REPO@; false; cd @ELSEWHERE@"),
}


def _setup(project: Project, steps: list[list[str]]) -> None:
    for step in steps:
        project.git(*step)


@pytest.mark.parametrize(("command", "steps"), PUSHES.values(), ids=PUSHES.keys())
def test_each_form_of_a_push_is_scanned_and_refused(project: Project, command: str, steps: list[list[str]]) -> None:
    _setup(project, steps)
    _found(project.bash(command))


@pytest.mark.parametrize("command", BEFORE_REFUSED.values(), ids=BEFORE_REFUSED.keys())
def test_a_push_after_what_may_move_its_commits_is_refused(project: Project, command: str) -> None:
    project.git("checkout", "-q", "clean")
    _ordered(project.bash(command))


@pytest.mark.parametrize("command", BEFORE_ALLOWED.values(), ids=BEFORE_ALLOWED.keys())
def test_reads_may_come_before_a_push(project: Project, command: str) -> None:
    project.git("checkout", "-q", "clean")
    assert project.bash(command) is None
    assert project.scans(), "the push of the clean commit was never scanned"


@pytest.mark.parametrize("command", PASSES.values(), ids=PASSES.keys())
def test_what_sends_nothing_new_goes_through(project: Project, command: str) -> None:
    assert project.bash(command) is None


@pytest.mark.parametrize("command", OVER_READ.values(), ids=OVER_READ.keys())
def test_what_the_shell_never_pushes_is_read_anyway(project: Project, command: str) -> None:
    _found(project.bash(command))


@pytest.mark.parametrize("command", OVER_READ_ORDER.values(), ids=OVER_READ_ORDER.keys())
def test_what_the_shell_never_runs_as_a_command_is_read_as_one(project: Project, command: str) -> None:
    project.git("checkout", "-q", "clean")
    _ordered(project.bash(command))


@pytest.mark.parametrize("command", UNNAMED.values(), ids=UNNAMED.keys())
def test_a_push_from_a_directory_the_hook_cannot_name_is_refused(project: Project, command: str) -> None:
    project.git("checkout", "-q", "clean")
    # The session's HOME is the project, so a `~` the hook took where bash leaves it as written reads the finding.
    reason = project.bash(command, env={"REPO": str(project.root), "HOME": str(project.root)})
    assert reason is not None and "directory the hook cannot name" in reason, reason
    assert "an exported function it may not import" in reason and "and not through a function" in reason, reason


@pytest.mark.parametrize(("command", "what"), OUTRIGHT.values(), ids=OUTRIGHT.keys())
def test_writes_the_hook_cannot_read_first_are_refused_outright(project: Project, command: str, what: str) -> None:
    project.git("checkout", "-q", "clean")
    reason = project.bash(command)
    assert reason is not None and what in reason, reason


@pytest.mark.parametrize("command", API_PASSES.values(), ids=API_PASSES.keys())
def test_api_calls_that_add_no_content_go_through(project: Project, command: str) -> None:
    assert project.bash(command) is None


def test_a_line_too_long_to_read_in_time_is_refused(project: Project) -> None:
    # One long word reads in time that grows as its square; a line past the floor is refused before it is read, and
    # a here-document as large passes, since the hook reads its body line by line.
    reason = project.bash("echo '" + "a" * 400_001 + "'; git push origin work")
    assert reason is not None and "more than 400,000 characters" in reason, reason
    big = "x" * 300 + "\n"
    assert project.bash("cat <<EOF\n" + big * 2000 + "EOF\ngit status") is None


# The files a stated gap's command names, so that closing the gap turns its case.
GAP_FILES = {
    "a push a script runs": {"push.sh": "#!/bin/sh\ngit push origin work\n"},
    "a GraphQL mutation from standard input": {"m.graphql": MUTATION},
}


@pytest.mark.parametrize(("name", "command"), GAPS.items(), ids=GAPS.keys())
def test_the_stated_gaps_pass_through(project: Project, name: str, command: str) -> None:
    project.write(GAP_FILES.get(name, {}))
    assert project.bash(command) is None


def test_a_tag_of_a_tree_is_a_stated_gap_of_the_reading_before_a_call(project: Project) -> None:
    # No commit holds what the tag sends, so a scan of commits finds nothing; git's pre-push hook stops the push
    # (test_the_pre_push_hook_stops_a_tag_of_a_tree_or_a_blob).
    project.publish("work")  # every commit here is on GitHub
    blob = project.git("hash-object", "-w", "--stdin", stdin=LEAK + "\n")
    project.git("tag", "tree", project.git("mktree", stdin=f"100644 blob {blob}\tleak.py\n"))
    assert project.bash("git push origin tree") is None


@pytest.mark.parametrize("command", ELSEWHERE.values(), ids=ELSEWHERE.keys())
def test_a_push_the_call_moves_into_the_project_is_read_there(project: Project, command: str) -> None:
    _found(project.bash(command, cwd=project.elsewhere))


@pytest.mark.parametrize("command", STAYS.values(), ids=STAYS.keys())
def test_a_move_the_shell_does_not_keep_is_not_followed(project: Project, command: str) -> None:
    _found(project.bash(command))


@pytest.mark.parametrize("command", MOVED_AWAY.values(), ids=MOVED_AWAY.keys())
def test_a_push_the_call_moves_away_is_read_where_it_runs(project: Project, command: str) -> None:
    assert project.bash(command) is None
    assert [scan["argv"][1] for scan in project.scans()] == [str(project.elsewhere / ".git")]


@pytest.mark.parametrize(("command", "steps"), PRECISE.values(), ids=PRECISE.keys())
def test_a_push_is_read_as_sending_what_it_names(project: Project, command: str, steps: list[list[str]]) -> None:
    _setup(project, steps)
    assert project.bash(command) is None
    assert project.scans(), "the push of the clean commit was never scanned"


@pytest.mark.parametrize(("files", "command", "refused"), API_FILES.values(), ids=API_FILES.keys())
def test_a_graphql_write_is_read_from_the_file_the_command_names(project: Project, files: dict[str, str], command: str,
                                                                 refused: bool) -> None:
    project.write(files)
    reason = project.bash(command)
    assert (reason is not None and "createCommitOnBranch" in reason) if refused else reason is None, reason


def test_an_alias_is_read_from_the_repository_git_runs_in(project: Project) -> None:
    # From `elsewhere`, whose own `ship` is a read, `git -C <project> ship` runs the project's alias.
    project.git("config", "alias.ship", "push origin work")
    project.git("config", "alias.ship", "status", cwd=project.elsewhere)
    _found(project.bash("git -C @REPO@ ship", cwd=project.elsewhere))


def test_a_mirror_set_with_no_value_in_the_config_is_read(project: Project) -> None:
    with (project.root / ".git" / "config").open("a", encoding="utf-8") as config:
        config.write('[remote "origin"]\n\tmirror\n')  # a key with no value is a boolean set
    project.git("checkout", "-q", "clean")
    _found(project.bash("git push"))


def test_a_push_read_whole_says_so(project: Project) -> None:
    project.git("checkout", "-q", "clean")
    reason = project.bash("git push $(echo origin work)")
    _found(reason)
    assert "sending more than literal refspecs name" in reason and "push literal refspecs" in reason


# --- what would blind the scan or fail it --------------------------------------------------------------------

# Settings that change what `git log -p` prints: (where it is set, name, value). Colour and the big-file threshold
# hide the planted line from gitleaks; an abbreviated commit and another format leave it a finding whose commit
# main's pins do not match; decorations and prefixes gitleaks reads past. The stub, stricter, reads nothing under
# any of them, so each case turns it blind unless the hook holds the setting at git's default. git reads
# diff.dstPrefix from 2.45 on; an older one ignores it, and that case passes either way.
BLINDERS = {
    "colour, in the repository": ("repository", "color.ui", "always"),
    "colour, in the global file": ("global", "color.ui", "always"),
    "diff colour": ("repository", "color.diff", "always"),
    "an abbreviated commit header": ("repository", "log.abbrevCommit", "true"),
    "a one-line format": ("repository", "format.pretty", "oneline"),
    "decorations": ("repository", "log.decorate", "full"),
    "no prefixes": ("repository", "diff.noprefix", "true"),
    "another prefix": ("repository", "diff.dstPrefix", "x/"),
    "every file binary by its size": ("repository", "core.bigFileThreshold", "1"),
}


def _global(tmp_path: Path, settings: str) -> dict[str, str]:
    """A global git configuration where a machine keeps one, in the home directory, which GIT_CONFIG_GLOBAL names
    too: the environment of a call that the machine's own settings reach."""
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    (home / ".gitconfig").write_text(settings, encoding="utf-8")
    return {"HOME": str(home), "GIT_CONFIG_GLOBAL": str(home / ".gitconfig")}


@pytest.mark.parametrize(("scope", "name", "value"), BLINDERS.values(), ids=BLINDERS.keys())
def test_a_setting_that_would_blind_the_scan_is_held_at_git_s_default(project: Project, tmp_path: Path, scope: str,
                                                                     name: str, value: str) -> None:
    env = None
    if scope == "repository":
        project.git("config", name, value)
    else:
        section, key = name.split(".")
        env = _global(tmp_path, f"[{section}]\n\t{key} = {value}\n")
    _found(project.bash("git push origin work", env=env))


def _sign(project: Project, branch: str) -> None:
    """Give the tip of `branch` an SSH signature header, as a machine that signs every commit does; git cannot
    check it without an allowed-signers file, and says so on its stderr when told to show signatures."""
    commit = project.git("cat-file", "commit", branch)
    head, _, message = commit.partition("\n\n")
    signature = "gpgsig -----BEGIN SSH SIGNATURE-----\n U1NIU0lHAAAAAQ==\n -----END SSH SIGNATURE-----"
    signed = project.git("hash-object", "-t", "commit", "-w", "--stdin", stdin=f"{head}\n{signature}\n\n{message}\n")
    project.git("update-ref", f"refs/heads/{branch}", signed)


def test_signed_commits_are_scanned_without_checking_their_signatures(project: Project) -> None:
    # log.showSignature=true makes git log check each signature; an SSH one, with no allowed-signers file set, has
    # git complain on its stderr, which fails gitleaks' scan.
    _sign(project, "clean")
    _sign(project, "work")
    project.git("config", "log.showSignature", "true")
    _found(project.bash("git push origin work"))
    assert project.bash("git push origin clean") is None
    assert len(project.scans()) == 2


def _binary_tree(project: Project) -> str:
    """A tree whose .gitattributes marks every Python file binary, for attr.tree to name."""
    blob = project.git("hash-object", "-w", "--stdin", stdin="*.py -diff\n")
    return project.git("mktree", stdin=f"100644 blob {blob}\t.gitattributes\n")


ATTRIBUTE_SOURCES = ("a tree the repository names", "the worktree core.worktree names", "a bare repository's HEAD",
                     "a .gitattributes in the git directory")


def _plant_attributes(project: Project, source: str) -> None:
    """A .gitattributes that marks every Python file binary, where git run in the project's git directory reads it:
    a tree the repository's attr.tree names, the worktree around the git directory that its core.worktree names, a
    bare repository's HEAD (git 2.43 to 2.45 read its .gitattributes; CI's later git does not) or the git directory
    itself."""
    if source == "a tree the repository names":
        project.git("config", "attr.tree", _binary_tree(project))
    elif source == "the worktree core.worktree names":
        project.write({".gitattributes": "*.py -diff\n"})
        project.git("config", "core.worktree", str(project.root))
    elif source == "a bare repository's HEAD":
        project.commit({".gitattributes": "*.py -diff\n"}, "attributes on the branch HEAD names")
        project.git("config", "core.bare", "true")
    else:
        (project.root / ".git" / ".gitattributes").write_text("*.py -diff\n", encoding="utf-8")


@pytest.mark.parametrize("scope", ["global", "repository", "git's default file", *ATTRIBUTE_SOURCES])
def test_attributes_that_mark_the_file_binary_do_not_count(project: Project, tmp_path: Path, scope: str) -> None:
    # The global config naming a file never reaches the scan's git; the repository's naming one, and the file git
    # reads when none is named ($XDG_CONFIG_HOME/git/attributes), are held off by the pin of core.attributesFile. The
    # four sources _plant_attributes plants, each of which git run in the git directory reads, are held off by the
    # pin of attr.tree to the empty tree.
    attributes = tmp_path / "xdg" / "git" / "attributes"
    attributes.parent.mkdir(parents=True)
    attributes.write_text("*.py -diff\n", encoding="utf-8")
    env = None
    if scope == "repository":
        project.git("config", "core.attributesFile", str(attributes))
    elif scope == "global":
        env = _global(tmp_path, f"[core]\n\tattributesFile = {attributes}\n")
    elif scope == "git's default file":
        env = {"XDG_CONFIG_HOME": str(tmp_path / "xdg")}
    else:
        _plant_attributes(project, scope)
    _found(project.bash("git push origin work", env=env))


def _old_git(tmp_path: Path, version: str = "git version 2.42.0") -> dict[str, str]:
    """A PATH whose git reports `version` and runs the real git for everything else, taking `--path-format`, for a
    version before 2.31, as an option it does not know, which rev-parse prints back, as those gits do."""
    shim = tmp_path / "old-git"
    shim.mkdir(parents=True)
    real = shutil.which("git")
    read = re.match(r"git version (\d+)\.(\d+)", version)
    unknown = read is not None and (int(read.group(1)), int(read.group(2))) < (2, 31)
    rename = ('for arg; do shift; case "$arg" in --path-format=*) arg=--no-such-option;; esac; set -- "$@" "$arg"; '
              'done\n') if unknown else ""
    (shim / "git").write_text(f'#!/bin/sh\ncase "$*" in *version) echo "{version}"; exit 0;; esac\n{rename}'
                              f'exec {real} "$@"\n', encoding="utf-8")
    (shim / "git").chmod(0o755)
    return {"PATH": f"{shim}{os.pathsep}{os.environ['PATH']}"}


def test_a_git_older_than_attr_tree_refuses_a_call_that_adds_commits(project: Project, tmp_path: Path) -> None:
    # A git before 2.43 knows no attr.tree, so a tree's or worktree's .gitattributes could hide a line from its scan.
    env = _old_git(tmp_path)
    reason = project.bash("git push origin work", env=env)
    assert reason is not None and "(git version 2.42.0) is older than 2.43" in reason, reason
    reason = project.decide("mcp__github__create_or_update_file", {"owner": "neilmac91", "repo": "EarningsNerd",
                            "message": "m", "branch": "main", "path": "x.py", "content": "x = 1\n"}, env=env)
    assert reason is not None and "older than 2.43" in reason, reason
    assert project.bash("git push origin main", env=env) is None  # a push that adds no commit runs no scan
    for tool, extra in (("mcp__github__add_issue_comment", {"issue_number": 1, "body": "x"}),
                        ("mcp__github__get_file_contents", {"path": "a.py"})):  # nor a GitHub call that sends no file
        assert project.decide(tool, {"owner": "neilmac91", "repo": "EarningsNerd", **extra}, env=env) is None
    # A version the hook cannot read is refused as well: it may be a git that knows no attr.tree.
    reason = project.bash("git push origin work", env=_old_git(tmp_path / "unread", "git version unknown"))
    assert reason is not None and "cannot read this machine's git version ('git version unknown')" in reason, reason
    # A git before 2.31 knows no --path-format either, and the hook's reads ask for nothing it does not know.
    env = _old_git(tmp_path / "2.30", "git version 2.30.2")
    assert project.bash("git push origin main", env=env) is None
    reason = project.bash("git push origin work", env=env)
    assert reason is not None and "(git version 2.30.2) is older than 2.43" in reason, reason


def test_a_scan_that_would_read_a_repository_whose_objects_are_not_sha1_is_refused(tmp_path: Path) -> None:
    # The empty tree attr.tree is held at is SHA-1's, which names no tree in a SHA-256 repository. A push reads that
    # repository, and so does a GitHub write the hook builds on its branch as fetched there.
    project = _make(tmp_path, objects="sha256")
    write = {"path": "x.py", "content": LEAK + "\n"}
    for reason in (project.bash("git push origin work"),
                   _mcp(project, "mcp__github__create_or_update_file", branch="main", **write)):
        assert reason is not None and "objects are sha256, not SHA-1" in reason, reason
    assert project.bash("git push origin main") is None  # a push that adds no commit runs no scan
    # A write to a branch not fetched here is built in a fresh scratch repository, which is SHA-1, and scanned.
    _found(_mcp(project, "mcp__github__create_or_update_file", branch="not-fetched", **write), "x.py:1")


@pytest.mark.parametrize("how", ["a file", "a link to /dev/null"])
@pytest.mark.parametrize("name", [".gitleaks.toml", ".gitleaksignore"])
def test_rules_or_pins_in_the_git_directory_do_not_count(project: Project, name: str, how: str) -> None:
    # gitleaks reads the scanned directory's own .gitleaksignore always, and its .gitleaks.toml when no --config names
    # one, as here, where main has no rules: a call whose git directory holds either is refused, whatever kind of file
    # it is. gitleaks reads a .gitleaks.toml that links to /dev/null as rules that find nothing.
    planted = project.root / ".git" / name
    if how == "a file":
        planted.write_text(ALLOW_ALL if name == ".gitleaks.toml" else
                           f"{project.leak}:b.py:generic-api-key:1\nx.py:generic-api-key:1\n", encoding="utf-8")
    else:
        planted.symlink_to(os.devnull)
    write = {"branch": "main", "path": "x.py", "content": LEAK + "\n"}
    for reason in (project.bash("git push origin work"), _mcp(project, "mcp__github__create_or_update_file", **write)):
        assert reason is not None and f"git directory holds a {name}" in reason, reason


def _shadow(project: Project, shadow: Path) -> Path:
    """A repository at `shadow` that borrows the project's objects, holds the planted commit as fetched and marks
    Python files binary, so a scan that read it in the project's place would let a push and a GitHub write through."""
    project.git("init", "-q", "--bare", str(shadow))
    (shadow / "objects" / "info" / "alternates").write_text(f"{project.root / '.git' / 'objects'}\n", encoding="utf-8")
    (shadow / "info").mkdir(exist_ok=True)  # git's templates make it, and a git may have none
    (shadow / "info" / "attributes").write_text("*.py -diff\n", encoding="utf-8")
    project.git("--git-dir", str(shadow), "update-ref", "refs/remotes/origin/work", project.leak)
    return shadow


@pytest.mark.parametrize("how", ["a gitfile", "a link", "a directory", "a file git cannot read"])
def test_a_git_directory_git_takes_for_another_is_refused(project: Project, tmp_path: Path, how: str) -> None:
    # git run in the git directory, as the scan's reads and gitleaks' own git are, takes a .git there that is or
    # names a repository for the repository, and fails on one it cannot read, while the call, from the worktree,
    # reads the git directory itself.
    planted = project.root / ".git" / ".git"
    if how == "a directory":
        _shadow(project, planted)
    else:
        shadow = _shadow(project, tmp_path / "shadow.git")
        if how == "a link":
            planted.symlink_to(shadow)
        else:
            planted.write_text(f"gitdir: {shadow}\n" if how == "a gitfile" else "not a gitfile\n", encoding="utf-8")
    write = {"branch": "main", "path": "x.py", "content": LEAK + "\n"}
    for reason in (project.bash("git push origin work"), _mcp(project, "mcp__github__create_or_update_file", **write)):
        assert reason is not None and "git run in this repository's git directory (" in reason, reason


@pytest.mark.parametrize("plant", ["a commondir file", "a HEAD git cannot read"])
def test_a_git_directory_git_leaves_is_refused_for_a_linked_worktree_s_push(project: Project, tmp_path: Path,
                                                                            plant: str) -> None:
    # A linked worktree's own git directory names this one in its commondir, which git follows one step and no further,
    # and keeps its own HEAD, so its push reads this git directory whatever its HEAD holds. The scan's git, run here,
    # would follow a commondir planted here in turn, and on a HEAD it cannot read would walk up to a repository above.
    linked = tmp_path / "linked"
    project.git("worktree", "add", "-q", "--detach", str(linked), "work")
    if plant == "a commondir file":
        (project.root / ".git" / "commondir").write_text(f"{_shadow(project, tmp_path / 'shadow.git')}\n",
                                                          encoding="utf-8")
    else:
        _shadow(project, tmp_path)  # the directory the project is in
        (project.root / ".git" / "HEAD").write_text("not a ref\n", encoding="utf-8")
    reason = project.bash(f"cd {linked} && git push origin work")
    assert reason is not None and "git run in this repository's git directory (" in reason, reason


def test_a_push_from_a_linked_directory_scans_its_repository(project: Project, tmp_path: Path) -> None:
    # git answers from the directory a link leads to, so the hook joins git's relative answer to that directory's
    # real path, not to the path the shell took.
    deep = project.root / "a" / "b" / "c"
    deep.mkdir(parents=True)
    link = tmp_path / "link"
    link.symlink_to(deep)
    _found(project.bash(f"cd {link} && git push origin work"))


@pytest.mark.parametrize("link", ["the checkout's .git", "the temporary directory"])
def test_a_git_directory_named_through_a_link_is_its_own_repository(project: Project, tmp_path: Path,
                                                                    link: str) -> None:
    # git names a git directory by its real path, while a GitHub write's scan reaches the one it reads through the
    # checkout's .git, or builds it in the temporary directory, either of which may be a link (macOS's is).
    env: dict[str, str] = {}
    if link == "the checkout's .git":
        moved = tmp_path / "moved.git"
        (project.root / ".git").rename(moved)
        (project.root / ".git").symlink_to(moved)
        branch = "main"  # built on the branch as fetched, in the checkout's git directory
    else:
        (tmp_path / "tmp-real").mkdir()
        (tmp_path / "tmp-link").symlink_to(tmp_path / "tmp-real")
        env["TMPDIR"] = str(tmp_path / "tmp-link")
        branch = "not-fetched"  # built in a scratch repository in the temporary directory
    write = {"owner": "neilmac91", "repo": "EarningsNerd", "message": "m", "branch": branch, "path": "x.py",
             "content": LEAK + "\n"}
    _found(project.decide("mcp__github__create_or_update_file", write, env=env), "x.py:1")
    _found(project.bash("git push origin work", env=env))


@pytest.mark.parametrize("how", ["an empty directory", "a dangling link"])
def test_a_git_that_git_ignores_in_the_git_directory_is_scanned_through(project: Project, tmp_path: Path,
                                                                       how: str) -> None:
    # git takes the git directory itself when the .git in it is neither a repository nor a gitfile, so the call is
    # scanned, not refused.
    planted = project.root / ".git" / ".git"
    planted.mkdir() if how == "an empty directory" else planted.symlink_to(tmp_path / "nowhere")
    _found(project.bash("git push origin work"))
    _found(_mcp(project, "mcp__github__create_or_update_file", branch="main", path="x.py", content=LEAK + "\n"),
           "x.py:1")


def test_the_session_s_git_dir_does_not_vouch_for_the_git_directory(project: Project, tmp_path: Path) -> None:
    # The scan's git reads no GIT_* variable of the session, so neither does the check of what it takes for the
    # repository: a GIT_DIR naming the git directory would answer for it while the scan follows the .git inside.
    shadow = _shadow(project, tmp_path / "shadow.git")
    (project.root / ".git" / ".git").write_text(f"gitdir: {shadow}\n", encoding="utf-8")
    env = {"GIT_DIR": str(project.root / ".git")}
    write = {"owner": "neilmac91", "repo": "EarningsNerd", "message": "m", "branch": "main", "path": "x.py",
             "content": LEAK + "\n"}
    for reason in (project.bash("git push origin work", env=env),
                   project.decide("mcp__github__create_or_update_file", write, env=env)):
        assert reason is not None and "git run in this repository's git directory (" in reason, reason


def _hop(project: Project) -> str:
    """elsewhere/hop, a link to a directory in the project: `hop/..` is `elsewhere` by the path's text, whose own
    `work` is clean, and the project through the link."""
    (project.root / "deep").mkdir()
    (project.elsewhere / "hop").symlink_to(project.root / "deep")
    return str(project.elsewhere / "hop")


# Moves through a link and then up from it, which the system takes through the link (to the parent of the directory
# it leads to) where the text of the path names the parent of the link: each pushes the project's `work` from
# `elsewhere`, and is refused only when the hook follows it as the system does.
THROUGH_A_LINK = {
    "-C": "git -C @HOP@/.. push origin work",
    "env -C": "env -C @HOP@/.. git push origin work",
    "env --chdir=": "env --chdir=@HOP@/.. git push origin work",
    "cd -P": "cd -P @HOP@/.. && git push origin work",
    "cd -LP, whose last option wins": "cd -LP @HOP@/.. && git push origin work",
    "cd -Pe, whose -e takes neither way": "cd -Pe @HOP@/.. && git push origin work",
    "cd -P -, to an OLDPWD the call sets": "OLDPWD=@HOP@/..; cd -P - && git push origin work",
    "cd -P -, to an OLDPWD before it in the command": "OLDPWD=@HOP@/.. cd -P - && git push origin work",
    "cd -P alone, to a HOME the call sets": "HOME=@HOP@/..; cd -P && git push origin work",
    "--git-dir": "git --git-dir=@HOP@/../.git push origin work",
    "a GIT_DIR": "GIT_DIR=@HOP@/../.git git push origin work",
}


@pytest.mark.parametrize("command", THROUGH_A_LINK.values(), ids=THROUGH_A_LINK.keys())
def test_a_move_through_a_link_and_up_is_read_as_the_system_takes_it(project: Project, command: str) -> None:
    _found(project.bash(command.replace("@HOP@", _hop(project)), cwd=project.elsewhere))


# The same moves by cd -L, which takes `..` from the path's text whatever bash's physical option says: from the
# project, each lands in `elsewhere`, where the push passes, scanned there.
BY_THE_TEXT = {
    "cd -L": "cd -L @HOP@/.. && git push origin work",
    "cd -PL, whose last option wins": "cd -PL @HOP@/.. && git push origin work",
    "cd -L after set -P, which it overrides": "set -P; cd -L @HOP@/.. && git push origin work",
    "cd -L -, to an OLDPWD the call sets": "OLDPWD=@HOP@/..; cd -L - && git push origin work",
}


@pytest.mark.parametrize("command", BY_THE_TEXT.values(), ids=BY_THE_TEXT.keys())
def test_cd_l_through_a_link_and_up_is_read_by_the_path_s_text(project: Project, command: str) -> None:
    assert project.bash(command.replace("@HOP@", _hop(project))) is None
    assert [scan["argv"][1] for scan in project.scans()] == [str(project.elsewhere / ".git")]


# The same moves by a cd or pushd with neither -L nor -P, which bash takes by the path's text unless its physical
# option is on (a `set -P` in the call or the shell's profile, an exported SHELLOPTS, a new shell's own -P), which
# the hook does not follow: each is refused as a push from a directory the hook cannot name. From the project, the
# text leads to `elsewhere` (a clean push) and the link into the project (its finding), so a hook that took either
# way would decide otherwise.
AMBIGUOUS = {
    "cd": "cd @HOP@/.. && git push origin work",
    "pushd": "pushd @HOP@/.. && git push origin work",
    "cd -e, an option that names neither way": "cd -e @HOP@/.. && git push origin work",
    "cd -, to an OLDPWD the call sets": "OLDPWD=@HOP@/..; cd - && git push origin work",
    "cd ~, to a HOME the call sets": "HOME=@HOP@/..; cd ~ && git push origin work",
    "cd alone, to a HOME the call sets": "HOME=@HOP@/..; cd && git push origin work",
    "popd, back to what pushd -n put on the stack": "pushd -n @HOP@/.. && popd && git push origin work",
    "cd after set -P": "set -P; cd @HOP@/.. && git push origin work",
    "cd after set -eP, a group of options": "set -eP; cd @HOP@/.. && git push origin work",
    "cd after set -o physical": "set -o physical; cd @HOP@/.. && git push origin work",
    "cd after set -eo physical": "set -eo physical; cd @HOP@/.. && git push origin work",
    "cd after set -P and set +P": "set -P; set +P; cd @HOP@/.. && git push origin work",
    "cd after set x -P, which sets the arguments": "set x -P; cd @HOP@/.. && git push origin work",
    "cd after set -- -P, which sets the arguments": "set -- -P; cd @HOP@/.. && git push origin work",
    "a subshell's cd after set -P": "set -P; (cd @HOP@/.. && git push origin work)",
    "cd after a subshell's set -P": "(set -P); cd @HOP@/.. && git push origin work",
    "a substitution's cd after set -P": 'set -P; : "$(cd @HOP@/.. && git push origin work)"',
    "a process substitution's cd after set -P": "set -P; cat <(cd @HOP@/.. && git push origin work)",
    "a trap's cd after set -P": "set -P; trap 'cd @HOP@/.. && git push origin work' EXIT",
    "a new shell's cd": "bash -c 'cd @HOP@/.. && git push origin work'",
    "a new shell's cd after set -P": "set -P; bash -c 'cd @HOP@/.. && git push origin work'",
    "a new shell started with -P": "bash -P -c 'cd @HOP@/.. && git push origin work'",
    "a new shell given SHELLOPTS": "env SHELLOPTS=physical bash -c 'cd @HOP@/.. && git push origin work'",
    # bash holds the directory a cd with neither option enters by its real path under set -P, from which cd -L's
    # `..` leads elsewhere than from the path's text.
    "cd -L after a cd with neither, from the link it entered": "cd @HOP@ && cd -L .. && git push origin work",
}


@pytest.mark.parametrize("command", AMBIGUOUS.values(), ids=AMBIGUOUS.keys())
def test_a_move_through_a_link_and_up_that_bash_s_physical_option_decides_is_refused(project: Project,
                                                                                    command: str) -> None:
    reason = project.bash(command.replace("@HOP@", _hop(project)))
    assert reason is not None and "directory the hook cannot name" in reason, reason


def test_a_tilde_is_the_shell_s_home_not_the_command_s(project: Project) -> None:
    # bash expands a `~` before the command's own HOME takes effect, so `HOME=x cd ~` goes to the shell's HOME, and
    # `HOME=x cd` to x: here the shell's HOME is the project, and the command's names `elsewhere`.
    env = {"HOME": str(project.root)}
    _found(project.bash("HOME=@ELSEWHERE@ cd ~ && git push origin work", env=env))
    _found(project.bash("HOME=@ELSEWHERE@ git -C ~ push origin work", env=env))
    assert project.bash("HOME=@ELSEWHERE@ cd && git push origin work", env=env) is None
    # cd alone, with no HOME in the call, goes to the session's.
    _found(project.bash("cd && git push origin work", cwd=project.elsewhere, env=env))


def test_a_quoted_tilde_in_a_shell_alias_is_one_the_hook_cannot_read(project: Project) -> None:
    # The alias's text comes from the repository's config, not the call: bash leaves its quoted ~ as written, the cd
    # fails, and the push runs from the top directory.
    project.git("config", "alias.ship", "!cd '~'; git push origin work")
    project.git("checkout", "-q", "clean")
    reason = project.bash("git ship", env={"HOME": str(project.root)})
    assert reason is not None and "directory the hook cannot name" in reason, reason


def test_a_shell_alias_gets_no_home_the_shell_holds_unexported(project: Project) -> None:
    # git passes a shell alias the environment it got, which holds no HOME the call's shell has unexported: the
    # alias's cd then fails, and its push runs from the top directory.
    project.git("config", "alias.ship", "!cd; git push origin work")
    project.git("checkout", "-q", "clean")
    reason = project.bash("export HOME=@ELSEWHERE@; export -n HOME; git ship")
    assert reason is not None and "directory the hook cannot name" in reason, reason


def test_a_git_dir_naming_a_gitfile_is_read_in_the_repository_it_names(project: Project) -> None:
    # git takes a GIT_DIR or --git-dir that names a gitfile (a linked worktree's or a submodule's .git) to the
    # repository the file names.
    (project.elsewhere / "link.git").write_text(f"gitdir: {project.root / '.git'}\n", encoding="utf-8")
    _found(project.bash("GIT_DIR=@ELSEWHERE@/link.git git push origin work", cwd=project.elsewhere))
    _found(project.bash("git --git-dir=@ELSEWHERE@/link.git push origin work", cwd=project.elsewhere))


def test_a_tilde_and_a_user_s_name_is_that_user_s_home_directory(project: Project) -> None:
    # bash takes `~name` from the password database, whatever HOME holds: here the call's HOME names `elsewhere`.
    import pwd

    try:
        entry = pwd.getpwuid(os.getuid())
    except KeyError:
        pytest.skip("this process's user has no entry in the password database")
    if not os.path.isdir(entry.pw_dir):
        pytest.skip(f"this user's home directory ({entry.pw_dir}) does not exist")
    path = os.path.relpath(project.root, os.path.realpath(entry.pw_dir))
    _found(project.bash(f"HOME=@ELSEWHERE@; git -C ~{entry.pw_name}/{path} push origin work", cwd=project.elsewhere))


@pytest.mark.parametrize(("how", "said"), [("no repository", "not a git repository"),
                                           ("a core.worktree git cannot enter", "cannot chdir to '../missing'")])
def test_a_push_whose_repository_git_cannot_read_is_refused(project: Project, how: str, said: str) -> None:
    # The hook reads a push's repository where it runs, without the settings the call gives git. Where that read
    # finds none, the push may still read one (here the call's GIT_WORK_TREE stands in for a core.worktree git
    # cannot enter, as a removed submodule's is; a -c safe.directory does the same for another user's checkout),
    # so the call is refused, not let through, with what git said.
    if how == "no repository":
        command = "git -C /tmp push"
    else:
        project.git("config", "core.worktree", "../missing")
        command = "GIT_WORK_TREE=@REPO@ git push origin work"
    reason = project.bash(command)
    assert reason is not None and "git cannot read a repository where this push runs" in reason and said in reason, \
        reason


@pytest.mark.parametrize(("command", "name"), [
    ("unset GIT_DIR; git push origin work", "GIT_DIR"),
    ("export -n GIT_DIR; git push origin work", "GIT_DIR"),
    ("env -u GIT_DIR git push origin work", "GIT_DIR"),
    ("env -i git push origin work", "GIT_DIR"),
    ("exec -c git push origin work", "GIT_DIR"),
    ("env -u HOME bash -c 'cd; git push origin work'", "HOME"),
    ("sudo env -C @REPO@ git push origin work", "GIT_DIR"),
    ("env - git push origin work", "GIT_DIR"),
    ("env --ignore-environment git push origin work", "GIT_DIR"),
    ("env --unset=GIT_DIR git push origin work", "GIT_DIR"),
], ids=["unset", "export -n", "env -u", "env -i", "exec -c", "a HOME env -u drops", "sudo", "env -",
        "env --ignore-environment", "env --unset"])
def test_a_session_location_variable_the_call_drops_leaves_a_push_unnamed(project: Project, command: str,
                                                                           name: str) -> None:
    # The hook's own reads run in the session's environment, whose GIT_DIR (or HOME) names `elsewhere`: a call that
    # drops it pushes from the project, where those reads do not look, so its directory is one the hook cannot name.
    env = {"GIT_DIR": str(project.elsewhere / ".git")} if name == "GIT_DIR" else {"HOME": str(project.elsewhere)}
    reason = project.bash(command, env=env)
    assert reason is not None and "directory the hook cannot name" in reason, reason


def test_a_push_is_read_in_the_repository_the_session_s_git_dir_names(project: Project) -> None:
    # The push's git reads the session's GIT_DIR, so the read that finds the push's repository does too: from
    # `elsewhere`, this push sends the project's commits.
    _found(project.bash("git push origin work", cwd=project.elsewhere, env={"GIT_DIR": str(project.root / ".git")}))


def test_rules_in_the_git_directory_are_refused_whatever_main_holds(project: Project) -> None:
    # Under the rules main names, gitleaks reads no .gitleaks.toml in the git directory, but one there is refused all
    # the same, so it never starts to count the day main's rules go.
    project.git("checkout", "-q", "main")
    project.commit({".gitleaks.toml": "[extend]\nuseDefault = true\n"}, "rules on main")
    project.publish("main")
    project.git("checkout", "-q", "work")
    project.git("rebase", "-q", "main")
    (project.root / ".git" / ".gitleaks.toml").write_text(ALLOW_ALL, encoding="utf-8")
    reason = project.bash("git push origin work")
    assert reason is not None and "git directory holds a .gitleaks.toml" in reason, reason


@pytest.mark.parametrize(("version", "refused"), [
    ("git version 2.43.0", False), ("git version 2.55.0", False), ("git version 3.0.1", False),
    ("git version 2.43.0.windows.1", False), ("git version 2.39.5 (Apple Git-154)", True),
    ("git version 2.42.4", True), ("git version 1.99.9", True), ("", True), ("not git", True),
])
def test_the_scan_needs_git_2_43_or_later(version: str, refused: bool) -> None:
    assert (SCAN._too_old(version) is not None) == refused


def _graft(project: Project) -> None:
    """Graft the planted commit onto a twin GitHub has with the same tree, so `git log -p` shows it adding nothing,
    and silence git's hint about the graft file in the repository's config."""
    twin = project.git("commit-tree", project.git("rev-parse", "work^{tree}"), "-p", "main", "-m", "twin")
    project.git("update-ref", "refs/remotes/origin/twin", twin)
    (project.root / ".git" / "info").mkdir(exist_ok=True)
    (project.root / ".git" / "info" / "grafts").write_text(f"{project.leak} {twin}\n", encoding="utf-8")
    project.git("config", "advice.graftFileDeprecated", "false")


def _failed_for_the_graft(reason: str | None) -> None:
    """A refusal of a scan the graft's hint failed: it names the hint, which gitleaks logs first, and not the closing
    lines that report a partial scan with no leaks found."""
    assert reason is not None and "gitleaks failed" in reason, reason
    assert "info/grafts is deprecated" in reason and "no leaks found" not in reason, reason


def test_a_graft_file_fails_the_scan_closed_whatever_the_repository_says_of_its_hint(project: Project) -> None:
    # git's hint about the graft file, held on, fails the scan rather than let it read the graft's view.
    _graft(project)
    _failed_for_the_graft(project.bash("git push origin work"))


def test_a_refusal_names_git_s_lines_without_its_blank_ones() -> None:
    # git's longer errors (a checkout another user owns) hold a blank line before the command that fixes them.
    stderr = b"fatal: detected dubious ownership in repository at '/r'\nTo add an exception, call:\n\n\tgit x\n"
    assert SCAN._tail(stderr) == ("fatal: detected dubious ownership in repository at '/r' / To add an exception, "
                                  "call: / git x")


def test_a_failed_scan_is_refused_with_the_errors_gitleaks_logged() -> None:
    # gitleaks 8.24.3's stderr when git's own stderr fails its scan, abridged from what it logged for a graft: the
    # refusal names the first error (git's) and the last (gitleaks' own), each without its time and level.
    stderr = (b"6:12PM ERR [git] hint: Support for <GIT_DIR>/info/grafts is deprecated\n"
              b"6:12PM ERR [git] hint: and will be removed in a future Git version.\n"
              b"6:12PM ERR [git] hint: \n"
              b'6:12PM ERR failed to scan Git repository error="stderr is not empty"\n'
              b"6:12PM WRN scanned ~0 bytes (0)\n6:12PM WRN partial scan completed in 149ms\n"
              b"6:12PM WRN no leaks found in partial scan\n")
    assert SCAN._logged(stderr) == ("[git] hint: Support for <GIT_DIR>/info/grafts is deprecated / failed to scan "
                                    'Git repository error="stderr is not empty"')
    # Its fatal lines come in colour even under --no-color, as for a main .gitleaks.toml it cannot parse.
    fatal = (b"\x1b[90m6:52PM\x1b[0m \x1b[31mFTL\x1b[0m \x1b[1munable to load gitleaks config, err: While parsing "
             b"config: toml: expected character ]\x1b[0m\n")
    assert SCAN._logged(fatal) == "unable to load gitleaks config, err: While parsing config: toml: expected character ]"
    # A line git left empty names nothing, so the next one is named.
    assert SCAN._logged(b"6:12PM ERR [git] \n6:12PM ERR [git] fatal: bad object\n6:12PM ERR failed to scan\n") == (
        "[git] fatal: bad object / failed to scan")
    # A panic logs nothing at an error level: its own line names it, not the stack after it (main's .gitleaks.toml
    # with the regex `(`).
    panic = (b"WARNING: All log messages before absl::InitializeLog() is called are written to STDERR\n"
             b"E0000 00:00:1792435675.663074  145936 re2.cc:237] Error parsing '(': missing ): (\n"
             b"panic: regexp: Compile(`(`): error parsing regexp: missing closing ): `(`\n\ngoroutine 1 [running]:\n"
             b"main.main()\n\t/Users/zrice/code/gitleaks-org/gitleaks/main.go:18 +0x9d\n")
    assert SCAN._logged(panic) == "panic: regexp: Compile(`(`): error parsing regexp: missing closing ): `(`"
    # So does a Go runtime fatal error.
    assert SCAN._logged(b"fatal error: concurrent map writes\n\ngoroutine 7 [running]:\nmain.main()\n") == (
        "fatal error: concurrent map writes")
    assert SCAN._logged(b"error: told to fail\n") == "error: told to fail"  # no level and no crash: its last lines


def test_a_copy_the_repository_detects_does_not_hide_a_copied_line(project: Project) -> None:
    # With diff.renames=copies, a file copied from one changed beside it shows only what differs; CI's runner, at
    # git's default, shows the copy whole and finds the line, so the scan holds the default.
    seed = LEAK + "\n" + "".join(f"s{n} = {n}\n" for n in range(20))
    project.git("checkout", "-q", "main")
    project.commit({"seed.py": seed}, "a seed GitHub already has")
    project.publish("main")
    project.git("checkout", "-q", "-b", "copy")
    project.commit({"seed.py": seed + "more = 1\n", "copy.py": seed}, "a copy beside a change")
    project.git("config", "diff.renames", "copies")
    _found(project.bash("git push origin copy"), "copy.py:1")


def test_a_diff_driver_the_machine_s_global_config_defines_does_not_reach_the_scan(project: Project,
                                                                                   tmp_path: Path) -> None:
    # info/attributes names a driver, which hides nothing until a config defines it: a machine's global config that
    # made it binary would hide the planted line, and no pin holds every driver, so only reading no global config
    # keeps it out.
    (project.root / ".git" / "info").mkdir(exist_ok=True)
    (project.root / ".git" / "info" / "attributes").write_text("b.py diff=opaque\n", encoding="utf-8")
    _found(project.bash("git push origin work", env=_global(tmp_path, '[diff "opaque"]\n\tbinary = true\n')))


def test_attributes_the_branch_commits_do_not_hide_its_lines(project: Project) -> None:
    # CI's other pull requests' runs check out their own trees, which do not hold this branch's attributes.
    project.commit({".gitattributes": "*.py -diff\n"}, "attributes")
    _found(project.bash("git push origin work"))


def test_a_text_conversion_the_repository_names_does_not_hide_the_text(project: Project) -> None:
    (project.root / ".git" / "info").mkdir(exist_ok=True)
    (project.root / ".git" / "info" / "attributes").write_text("b.py diff=hide\n", encoding="utf-8")
    project.git("config", "diff.hide.textconv", "true")  # converts every version to nothing
    _found(project.bash("git push origin work"))


def test_attributes_in_info_attributes_are_a_stated_gap(project: Project) -> None:
    (project.root / ".git" / "info").mkdir(exist_ok=True)
    (project.root / ".git" / "info" / "attributes").write_text("b.py -diff\n", encoding="utf-8")
    assert project.bash("git push origin work") is None


@pytest.mark.parametrize("scope", ["repository", "global"])
def test_a_root_commit_s_lines_are_read(project: Project, tmp_path: Path, scope: str) -> None:
    # log.showRoot=false would hide them: a branch that starts afresh pushes its first commit whole.
    project.git("checkout", "-q", "--orphan", "solo")
    project.git("rm", "-rq", "--cached", ".")  # the files stay in the worktree, the hooks among them
    project.write({"solo.py": LEAK + "\n"})
    project.git("add", "solo.py")
    project.git("commit", "-qm", "a fresh start")
    env = None
    if scope == "repository":
        project.git("config", "log.showRoot", "false")
    else:
        env = _global(tmp_path, "[log]\n\tshowRoot = false\n")
    _found(project.bash("git push origin solo", env=env), "solo.py:1")


def test_a_source_named_through_a_replace_ref_is_scanned_as_git_push_names_it(project: Project) -> None:
    # git push follows replace refs to name `clean~1`: past the replacement of clean's commit, whose parent is the
    # planted commit, it sends that one.
    replacement = project.git("commit-tree", project.git("rev-parse", "clean^{tree}"), "-p", project.leak, "-m", "r")
    project.git("replace", project.git("rev-parse", "clean"), replacement)
    project.git("checkout", "-q", "clean")
    _found(project.bash("git push origin clean~1:refs/heads/x"))


def test_a_replace_ref_does_not_hide_the_commit_a_push_sends(project: Project) -> None:
    # A push sends the commit itself; git log would show its replacement, and rev-list count that one's history.
    project.git("replace", project.leak, project.git("rev-parse", "clean"))
    _found(project.bash("git push origin work"))
    project.git("replace", "-f", project.leak, project.git("rev-parse", "main"))
    _found(project.bash("git push origin work"))


def test_a_ref_under_another_remote_does_not_hide_a_commit(project: Project) -> None:
    project.git("update-ref", "refs/remotes/pr/work", "work")  # a pull request fetched under its own name
    project.git("update-ref", "refs/remotes/peek/work", "work")
    _found(project.bash("git push origin work"))


def test_a_commit_a_stale_origin_ref_holds_is_a_stated_gap(project: Project) -> None:
    project.git("update-ref", "refs/remotes/origin/gone", "work")  # a branch GitHub no longer holds, still fetched
    assert project.bash("git push origin work") is None


def test_the_commits_a_git_command_the_hook_does_not_know_makes_are_a_stated_gap(project: Project) -> None:
    # Read as a push of HEAD and every branch and tag, it is scanned before it runs; what it commits as it runs
    # is not.
    project.git("checkout", "-q", "clean")
    project.git("branch", "-qD", "work")
    assert project.bash("git commit-and-push") is None
    assert project.scans(), "the push it may make was never scanned"


def test_a_program_the_repository_s_configuration_runs_for_a_git_read_is_a_stated_gap(project: Project) -> None:
    # git status runs the fsmonitor the repository's config names; one that moved `clean` would have the push send
    # a commit the hook never read.
    project.git("config", "core.fsmonitor", str(project.root / "move.sh"))
    project.git("checkout", "-q", "clean")
    assert project.bash("git status && git push origin clean") is None


def test_a_push_scans_only_the_commits_it_adds(project: Project) -> None:
    project.git("checkout", "-q", "clean")
    clean = project.git("rev-parse", "HEAD")
    assert project.bash("git push origin clean") is None
    [scan] = project.scans()
    assert scan["argv"][:2] == ["git", str(project.root / ".git")]  # the git directory, not the worktree
    assert f"--log-opts={clean} --not --remotes=origin --no-textconv --no-ext-diff" in scan["argv"]
    # Once GitHub has the commit, a push of it adds nothing and runs no scan.
    project.publish("clean")
    assert project.bash("git push origin clean:refs/heads/copy") is None
    assert len(project.scans()) == 1


def test_a_commit_github_already_has_is_not_this_push_s(project: Project) -> None:
    project.publish("work")  # CI already reads it: this push adds nothing
    assert project.bash("git push origin work:refs/heads/copy") is None


def test_a_marked_line_passes(project: Project) -> None:
    project.git("checkout", "-q", "clean")
    project.commit({"d.py": MARKED + "\n"}, "marked")
    assert project.bash("git push") is None


def test_a_pin_on_main_lets_the_push_through(project: Project) -> None:
    project.git("checkout", "-q", "main")
    project.commit({".gitleaksignore": f"{project.leak}:b.py:generic-api-key:1\n"}, "pin")
    project.publish("main")
    project.git("checkout", "-q", "work")
    assert project.bash("git push origin work") is None


def test_a_global_pin_on_main_lets_the_push_through(project: Project) -> None:
    project.git("checkout", "-q", "main")
    project.commit({".gitleaksignore": "b.py:generic-api-key:1\n"}, "pin")
    project.publish("main")
    project.git("checkout", "-q", "work")
    assert project.bash("git push origin work") is None


@pytest.mark.parametrize("where", ["in the worktree", "committed on the branch"])
def test_a_pin_only_the_branch_carries_does_not_count(project: Project, where: str) -> None:
    pin = {".gitleaksignore": f"{project.leak}:b.py:generic-api-key:1\nb.py:generic-api-key:1\n"}
    project.write(pin) if where == "in the worktree" else project.commit(pin, "pin on the branch")
    _found(project.bash("git push origin work"))


def test_rules_only_the_branch_carries_do_not_count(project: Project) -> None:
    project.commit({".gitleaks.toml": ALLOW_ALL}, "rules on the branch")
    _found(project.bash("git push origin work"))
    # Nor do rules the environment names: a file GITLEAKS_CONFIG names, or the text GITLEAKS_CONFIG_TOML holds.
    config = project.root.parent / "allow.toml"
    config.write_text(ALLOW_ALL, encoding="utf-8")
    _found(project.bash("git push origin work", env={"GITLEAKS_CONFIG": str(config)}))
    _found(project.bash("git push origin work", env={"GITLEAKS_CONFIG_TOML": ALLOW_ALL}))
    assert {tuple(scan["gitleaks_env"]) for scan in project.scans()} == {()}


def test_main_s_pins_come_from_origin_head_then_main_then_master(project: Project) -> None:
    project.git("checkout", "-q", "main")
    pin = project.commit({".gitleaksignore": f"{project.leak}:b.py:generic-api-key:1\n"}, "pin")
    project.git("checkout", "-q", "work")
    # origin/main is the unpinned base, and origin/HEAD names the default branch, which holds the pin.
    project.git("update-ref", "refs/remotes/origin/trunk", pin)
    project.git("symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/trunk")
    assert project.bash("git push origin work") is None
    project.git("symbolic-ref", "--delete", "refs/remotes/origin/HEAD")
    _found(project.bash("git push origin work"))  # then origin/main, which does not pin it
    for ref in ("refs/remotes/origin/main", "refs/remotes/origin/trunk"):
        project.git("update-ref", "-d", ref)
    project.git("update-ref", "refs/remotes/origin/master", pin)
    assert project.bash("git push origin work") is None  # then origin/master


def test_with_no_rules_on_main_the_scan_names_none(project: Project) -> None:
    # gitleaks then reads its built-in config, as CI's scan does. No rules the hook could name stand in for it: those
    # that extend it (`[extend] useDefault = true`) drop its global allowlist's stopwords, as the pinned binary's case
    # below shows. A push, a write to a fetched branch, one to a branch not fetched and one to another repository each
    # run a scan.
    write = {"path": "x.py", "content": LEAK + "\n"}
    _found(project.bash("git push origin work"))
    _found(_mcp(project, "mcp__github__create_or_update_file", branch="main", **write), "x.py:1")
    _found(_mcp(project, "mcp__github__create_or_update_file", branch="not-fetched", **write), "x.py:1")
    _found(project.decide("mcp__github__create_or_update_file", {"owner": "someone", "repo": "else", "branch": "main",
                                                                "message": "m", **write}), "x.py:1")
    scans = [scan["argv"] for scan in project.scans() if scan["argv"][:1] == ["git"]]
    # --config or -c, either with =, or c in a group of short flags (-vc): gitleaks reads each as naming rules
    named = [arg for argv in scans for arg in argv if re.match(r"--config|-[a-z]*c", arg)]
    assert len(scans) == 4 and not named, scans


def test_rules_main_carries_count(project: Project) -> None:
    project.git("checkout", "-q", "main")
    project.commit({".gitleaks.toml": ALLOW_ALL}, "rules on main")
    project.publish("main")
    project.git("checkout", "-q", "work")
    project.git("rebase", "-q", "main")
    assert project.bash("git push origin work") is None


def test_with_no_main_fetched_no_pin_counts(project: Project) -> None:
    project.git("checkout", "-q", "main")
    project.commit({".gitleaksignore": f"{project.leak}:b.py:generic-api-key:1\n"}, "pin")
    project.publish("main")
    project.git("checkout", "-q", "work")
    project.git("update-ref", "-d", "refs/remotes/origin/main")
    project.git("update-ref", "refs/remotes/origin/other", "clean")  # a remote ref, but no main
    reason = project.bash("git push origin work")
    _found(reason)
    assert "No main branch is fetched" in reason and "`git remote rename <name> origin` first" in reason


def test_a_linked_worktree_pushes_its_own_head(project: Project) -> None:
    linked = project.root.parent / "linked"
    project.git("worktree", "add", "-q", str(linked), "clean")
    assert project.bash("git push origin HEAD", cwd=linked) is None  # its HEAD is clean
    _found(project.bash("git push origin work", cwd=linked))


def test_a_submodule_push_is_a_stated_gap(project: Project) -> None:
    library = project.root.parent / "library"
    library.mkdir()
    project.git("init", "-q", "-b", "main", cwd=library)
    project.commit({"lib.py": "z = 3\n"}, "library", cwd=library)
    project.git("checkout", "-q", "clean")
    project.git("submodule", "add", "-q", str(library), "library")
    project.git("commit", "-qm", "submodule")
    project.commit({"leak.py": LEAK + "\n"}, "a leak in the submodule", cwd=project.root / "library")
    # The superproject records the submodule's new commit, so an on-demand push would send it to the
    # submodule's remote: the scan reads the superproject's commits alone.
    project.git("add", "library")
    project.git("commit", "-qm", "the submodule's new commit")
    assert project.bash("git push --recurse-submodules=on-demand origin clean") is None
    assert project.scans(), "the superproject's commits were never scanned"


# --- GitHub MCP writes ---------------------------------------------------------------------------------------

def _mcp(project: Project, tool: str, **tool_input: object) -> str | None:
    return project.decide(tool, {"owner": "neilmac91", "repo": "EarningsNerd", "message": "m", **tool_input})


@pytest.mark.parametrize(("tool", "tool_input", "where"), [
    ("mcp__github__create_or_update_file", {"branch": "main", "path": "x.py", "content": LEAK + "\n"}, "x.py:1"),
    ("mcp__github__push_files", {"branch": "main", "files": [{"path": "a.md", "content": "hello\n"},
                                                            {"path": "deep/b.py", "content": "x = 1\n" + LEAK + "\n"}]}, "deep/b.py:2"),
    ("mcp__github__push_files", {"branch": "not-fetched", "files": [{"path": "x.py", "content": LEAK}]}, "x.py:1"),
    ("mcp__github__push_files", {"files": [{"path": "x.py", "content": LEAK}]}, "x.py:1"),
    ("mcp__github__future_commit_tool", {"branch": "main", "changes": [{"change": {"path": "y.py", "content": LEAK}}]}, "y.py:1"),
    ("mcp__plugin_gh_github__push_files", {"branch": "main", "files": [{"path": "x.py", "content": LEAK}]}, "x.py:1"),
    ("mcp__GitHub__create_or_update_file", {"branch": "main", "path": "./x.py", "content": LEAK}, "x.py:1"),
    ("mcp__github__create_or_update_file", {"branch": "main", "path": "a.py", "content": "x = 1\n" + LEAK + "\n"}, "a.py:2"),
    ("mcp__github__push_files", {"branch": "main", "files": [{"path": ".gitleaksignore", "content": "x.py:generic-api-key:1\n"},
                                                            {"path": "x.py", "content": LEAK}]}, "x.py:1"),
], ids=["a new file", "the second of two files", "a branch not fetched", "no branch: the default",
        "content nested in a future tool", "a plugin's GitHub server", "a GitHub server in capitals",
        "a line added to a file", "a pin the write sends itself"])
def test_a_github_write_of_a_planted_line_is_refused(project: Project, tool: str, tool_input: dict, where: str) -> None:
    _found(_mcp(project, tool, **tool_input), where)


def _legacy_on_main(project: Project, pins: str = "") -> None:
    """main's legacy.py holds the planted line, as a fixture main already pins by its commit does."""
    project.git("checkout", "-q", "main")
    project.commit({"legacy.py": LEAK + "\n", **({".gitleaksignore": pins} if pins else {})}, "legacy")
    project.publish("main")


def test_another_repository_s_write_is_scanned_whole(project: Project) -> None:
    # Its lines on its own branch are not this checkout's to read, and main's pins are not its pins.
    _legacy_on_main(project, "x.py:generic-api-key:1\n")
    for path, content, where in (("legacy.py", LEAK + "\nmore = 1\n", "legacy.py:1"), ("x.py", LEAK, "x.py:1")):
        reason = project.decide("mcp__github__create_or_update_file", {
            "owner": "someone", "repo": "else", "branch": "main", "path": path, "content": content, "message": "m"})
        _found(reason, where)


def test_the_repository_is_named_in_any_case(project: Project) -> None:
    _legacy_on_main(project)
    assert project.decide("mcp__github__create_or_update_file", {
        "owner": "NEILMAC91", "repo": "earningsnerd", "branch": "main", "path": "legacy.py",
        "content": LEAK + "\nmore = 1\n", "message": "m"}) is None


def test_a_github_write_that_names_no_branch_builds_on_main(project: Project) -> None:
    # GitHub commits it to the default branch: main's legacy.py already holds the planted line, so a write that
    # keeps it adds nothing CI finds.
    _legacy_on_main(project)
    assert _mcp(project, "mcp__github__create_or_update_file", path="legacy.py", content=LEAK + "\nmore = 1\n") is None


def test_a_write_to_a_branch_not_fetched_scans_its_files_whole(project: Project) -> None:
    _legacy_on_main(project)
    reason = _mcp(project, "mcp__github__create_or_update_file", branch="not-fetched", path="legacy.py",
                  content=LEAK + "\nmore = 1\n")
    _found(reason, "legacy.py:1")
    assert "'not-fetched' is not fetched here" in reason and "`git fetch origin not-fetched`" in reason


def test_a_github_write_builds_on_its_own_branch(project: Project) -> None:
    project.git("checkout", "-q", "-b", "feature", "main")
    project.commit({"legacy.py": LEAK + "\n"}, "legacy on the feature")
    project.publish("feature")
    assert _mcp(project, "mcp__github__create_or_update_file", branch="feature", path="legacy.py",
                content=LEAK + "\nmore = 1\n") is None
    _found(_mcp(project, "mcp__github__create_or_update_file", branch="main", path="legacy.py",
                content=LEAK + "\nmore = 1\n"), "legacy.py:1")


def test_a_write_to_a_branch_fetched_before_it_changed_is_a_stated_gap(project: Project) -> None:
    # The write builds on the branch's tip as last fetched: had GitHub's branch dropped the planted line since,
    # this write would add it back there, and the hook, reading the old tip, sees no line added.
    project.git("checkout", "-q", "-b", "feature", "main")
    project.commit({"legacy.py": LEAK + "\n"}, "a line GitHub's branch has dropped since")
    project.publish("feature")
    assert _mcp(project, "mcp__github__create_or_update_file", branch="feature", path="legacy.py",
                content=LEAK + "\n") is None


def test_a_path_sent_twice_is_refused(project: Project) -> None:
    reason = _mcp(project, "mcp__github__push_files", branch="main",
                  files=[{"path": "x.py", "content": "x = 1\n"}, {"path": "./x.py", "content": LEAK}])
    assert reason is not None and "'x.py' more than once" in reason


@pytest.mark.parametrize("path", ["a\x00b.py", "\udc80.py", "\ud800.py"],
                         ids=["a NUL", "a byte that is no UTF-8", "a lone surrogate no file system takes"])
def test_a_path_git_cannot_take_whole_still_refuses(project: Project, path: str) -> None:
    assert _mcp(project, "mcp__github__create_or_update_file", branch="main", path=path, content=LEAK + "\n") is not None


def test_a_repository_that_signs_every_commit_still_has_its_github_writes_scanned(project: Project) -> None:
    # The scratch commit is git commit-tree's, which signs only when told to (-S), never by these settings.
    for name, value in (("commit.gpgSign", "true"), ("gpg.format", "ssh"), ("user.signingKey", "/no/such/key")):
        project.git("config", name, value)
    assert _mcp(project, "mcp__github__create_or_update_file", branch="main", path="x.py", content="x = 1\n") is None
    _found(_mcp(project, "mcp__github__create_or_update_file", branch="main", path="x.py", content=LEAK), "x.py:1")


@pytest.mark.parametrize("setting", [*ATTRIBUTE_SOURCES, "color.diff"])
def test_a_github_write_s_scan_holds_the_repository_s_settings_at_git_s_defaults(project: Project, setting: str) -> None:
    # A write to a fetched branch is built and scanned in the repository's own git directory, so its settings reach
    # that scan as they reach a push's, and SCAN_CONFIG holds them there too.
    if setting == "color.diff":
        project.git("config", "color.diff", "always")
    else:
        _plant_attributes(project, setting)
    _found(_mcp(project, "mcp__github__create_or_update_file", branch="main", path="x.py", content=LEAK + "\n"),
           "x.py:1")


def test_a_github_write_scans_only_the_lines_it_adds(project: Project) -> None:
    # main's file already holds the planted line (pinned by its commit, unmarked, as legacy fixtures are); a write
    # that adds a clean line commits a diff CI's scan finds nothing in, and so does the hook's.
    _legacy_on_main(project)
    assert _mcp(project, "mcp__github__create_or_update_file", branch="main", path="legacy.py",
                content=LEAK + "\nmore = 1\n") is None
    _found(_mcp(project, "mcp__github__create_or_update_file", branch="main", path="legacy.py",
                content=LEAK + "\n" + LEAK.replace("api_", "new_") + "\n"), "legacy.py:2")


@pytest.mark.parametrize(("tool", "tool_input"), [
    ("mcp__github__create_or_update_file", {"branch": "main", "path": "x.py", "content": "x = 1\n"}),
    ("mcp__github__create_or_update_file", {"branch": "main", "path": "x.py", "content": MARKED + "\n"}),
    ("mcp__github__add_issue_comment", {"issue_number": 1, "body": LEAK}),
    ("mcp__github__create_pull_request", {"title": "x", "body": LEAK, "head": "work", "base": "main"}),
    ("mcp__github__merge_pull_request", {"pullNumber": 1, "merge_method": "squash"}),
    ("mcp__gh__push_files", {"branch": "main", "files": [{"path": "x.py", "content": LEAK}]}),
], ids=["a clean file", "a marked line", "a comment (no file content)", "a pull request's body",
        "a squash merge, a stated gap", "a GitHub server named otherwise, a stated gap"])
def test_other_github_calls_go_through(project: Project, tool: str, tool_input: dict) -> None:
    assert _mcp(project, tool, **tool_input) is None


def test_a_global_pin_on_main_covers_a_github_write(project: Project) -> None:
    project.git("checkout", "-q", "main")
    project.commit({".gitleaksignore": "x.py:generic-api-key:1\n"}, "pin")
    project.publish("main")
    assert _mcp(project, "mcp__github__create_or_update_file", branch="main", path="x.py", content=LEAK) is None


def test_a_github_write_leaves_the_repository_s_objects_alone(project: Project) -> None:
    def objects() -> list[str]:
        return sorted(str(path) for path in (project.root / ".git" / "objects").rglob("*") if path.is_file())

    before = objects()
    _found(_mcp(project, "mcp__github__create_or_update_file", branch="main", path="x.py", content=LEAK), "x.py:1")
    assert objects() == before


# --- failing closed ------------------------------------------------------------------------------------------

def test_a_missing_binary_refuses_what_adds_commits_and_says_how_to_install(project: Project) -> None:
    project.binary().unlink()
    reason = project.bash("git push origin work")
    assert reason is not None and f"gitleaks {VERSION}" in reason and "is not installed" in reason
    assert f"python3 {project.root / '.claude' / 'hooks' / 'secret_scan_guard.py'} --install" in reason
    assert _mcp(project, "mcp__github__create_or_update_file", branch="main", path="x.py", content="x\n") is not None
    # A call that adds nothing needs no binary.
    assert project.bash("git push origin main") is None
    assert project.bash("git status") is None


@pytest.mark.parametrize(("env", "said"), [
    ({"STUB_FAIL": "1"}, "gitleaks failed (exit 1: error: told to fail)"),
    ({"STUB_NO_REPORT": "1"}, "gitleaks left no report"),
], ids=["gitleaks fails", "gitleaks writes no report"])
def test_a_scan_that_fails_refuses(project: Project, env: dict[str, str], said: str) -> None:
    project.git("checkout", "-q", "clean")
    reason = project.bash("git push", env=env)
    assert reason is not None and said in reason, reason


@pytest.mark.parametrize("pin", ["", "      GITLEAKS_VERSION: 8.24.3\n      GITLEAKS_VERSION: 8.25.0\n"],
                         ids=["no pin", "two versions"])
def test_a_pin_the_hook_cannot_read_refuses(project: Project, pin: str) -> None:
    workflow = project.root / ".github" / "workflows" / "ci.yml"
    workflow.write_text(re.sub(r"^\s*GITLEAKS_VERSION:.*\n", pin, workflow.read_text(encoding="utf-8"), flags=re.M),
                        encoding="utf-8")
    project.git("checkout", "-q", "clean")
    reason = project.bash("git push")
    assert reason is not None and "cannot read CI's gitleaks pin" in reason


def test_a_dangling_origin_ref_refuses(project: Project) -> None:
    # git cannot list the commits the push adds, so the hook cannot tell what to scan.
    (project.root / ".git" / "refs" / "remotes" / "origin" / "broken").write_text("1" * 40 + "\n", encoding="utf-8")
    reason = project.bash("git push origin work")
    assert reason is not None and "git could not list the commits this push adds" in reason


def test_a_branch_ref_that_names_no_commit_does_not_hide_the_others(project: Project) -> None:
    # git push --all skips such a ref and sends the other branches, `work` among them.
    project.git("checkout", "-q", "clean")
    (project.root / ".git" / "refs" / "heads" / "junk").write_text("not a commit\n", encoding="utf-8")
    assert project.bash("git push --all origin") is not None


def _in_process(project: Project, monkeypatch: pytest.MonkeyPatch) -> None:
    """The environment the hook runs in, for a case that calls it in this process: the project's cache, and no
    GIT_* variable or machine-wide git configuration."""
    monkeypatch.setenv("XDG_CACHE_HOME", str(project.cache))
    for key in [key for key in os.environ if key.startswith(("GIT_", "GITLEAKS_"))]:
        monkeypatch.delenv(key)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", _no_global_config())
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def test_an_error_the_hook_does_not_expect_refuses_what_adds_commits(project: Project,
                                                                     monkeypatch: pytest.MonkeyPatch) -> None:
    _in_process(project, monkeypatch)

    def broken(*args: object, **kwargs: object) -> None:
        raise RuntimeError("planted")

    monkeypatch.setattr(SCAN, "_sends", broken)
    reason = SCAN.refusal(_event("Bash", {"command": "git push origin work"}, project.root), time.monotonic() + 30)
    assert reason is not None and "an error the hook does not expect (RuntimeError: planted)" in reason
    monkeypatch.setattr(SCAN, "_scan_content", broken)
    reason = SCAN.refusal(_event("mcp__github__create_or_update_file", {"path": "x.py", "content": "x = 1\n"},
                                 project.root), time.monotonic() + 30)
    assert reason is not None and "an error the hook does not expect (RuntimeError: planted)" in reason


@pytest.mark.parametrize("opener", ["<(cat ", "$(cat "], ids=["process substitutions", "command substitutions"])
def test_a_line_nested_past_python_s_own_limit_refuses(project: Project, opener: str) -> None:
    # Far past MAX_DEPTH and Python's recursion limit: the reader stops at its depth, or reads the line as written.
    command = "cat " + opener * 1500 + "git push origin work" + ")" * 1500
    assert project.bash(command) is not None


@pytest.mark.parametrize(("depth", "where"), [(900, "x.py:1"), (100_000, None)], ids=["deep", "past the decoder"])
def test_an_input_nested_past_python_s_own_limit_still_refuses(project: Project, depth: int, where: str | None) -> None:
    # The files are read without recursion however deep they sit; JSON the decoder cannot take refuses whole.
    tool_input = {"owner": "neilmac91", "repo": "EarningsNerd", "message": "m", "branch": "main", "deep": "@DEEP@"}
    event = json.dumps(_event("mcp__github__push_files", tool_input, project.root))
    file = json.dumps({"files": [{"path": "x.py", "content": LEAK}]})
    proc = project.run(event.replace('"@DEEP@"', '{"a": ' * depth + file + "}" * depth))
    assert proc.returncode == 0, proc.stderr
    reason = json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
    if where:
        _found(reason, where)
    else:
        assert "more than five levels deep" in reason, reason


def test_the_files_of_a_github_write_are_read_however_deep_they_sit() -> None:
    tool_input: dict = {"path": "x.py", "content": "x = 1\n"}
    for _ in range(5000):  # past Python's recursion limit, built without recursion
        tool_input = {"a": [tool_input]}
    assert SCAN._contents(tool_input) == [("x.py", "x = 1\n")]


def test_a_recursion_past_python_s_own_limit_refuses(monkeypatch: pytest.MonkeyPatch) -> None:
    def deep(*args: object) -> None:
        raise RecursionError("planted")

    monkeypatch.setattr(SCAN, "_bash_refusal", deep)
    reason = SCAN.refusal(_event("Bash", {"command": "git push"}, ROOT), time.monotonic() + 30)
    assert reason is not None and "more than five levels deep" in reason


def test_a_call_whose_reading_outlasts_the_deadline_refuses() -> None:
    # Functions that call each other many times over can take the reader past the hook's time, which the
    # registration would then end, letting the call through: the reader refuses it first.
    event = _event("Bash", {"command": "f() { :; }; f; git push origin work"}, ROOT)
    reason = SCAN.refusal(event, time.monotonic() - 1)
    assert reason is not None and "reading this call took the hook past" in reason, reason
    assert "does not expect" not in reason, reason


def test_an_error_reading_a_call_refuses_it(monkeypatch: pytest.MonkeyPatch) -> None:
    # A Bash call that names git or gh may push: a reading of it that fails refuses it, as one that recurses past
    # Python's own limit does.
    def broken(*args: object, **kwargs: object) -> None:
        raise RuntimeError("planted")

    monkeypatch.setattr(SCAN._Reader, "read", broken)
    reason = SCAN.refusal(_event("Bash", {"command": "git status"}, ROOT), time.monotonic() + 30)
    assert reason is not None and "an error the hook does not expect (RuntimeError: planted)" in reason, reason

    def deep(*args: object, **kwargs: object) -> None:
        raise RecursionError("planted")

    monkeypatch.setattr(SCAN._Reader, "read", deep)
    reason = SCAN.refusal(_event("Bash", {"command": "git status"}, ROOT), time.monotonic() + 30)
    assert reason is not None and "more than five levels deep" in reason, reason


def test_a_refusal_shows_a_quoted_word_as_written(project: Project) -> None:
    project.git("checkout", "-q", "clean")
    reason = project.bash("'function' x; git push")
    _ordered(reason)
    assert "runs `function x`" in reason, reason


def test_a_scan_past_its_deadline_refuses(project: Project, monkeypatch: pytest.MonkeyPatch) -> None:
    _in_process(project, monkeypatch)
    monkeypatch.setenv("STUB_SLEEP", "5")
    project.git("checkout", "-q", "clean")
    # The branch is clean, so a stub that ran its five seconds out would report nothing and the push would
    # pass: only the deadline refuses it.
    reason = SCAN.refusal(_event("Bash", {"command": "git push"}, project.root), time.monotonic() + 1.5)
    assert reason is not None and "outlasted" in reason
    # The registration gives the hook more time than the scan takes, so the scan, not Claude Code, ends it.
    [hook] = [hook for entry in _registered() for hook in entry["hooks"]]
    assert SCAN.DEADLINE < hook["timeout"]


def test_the_hook_gives_its_scan_the_deadline(project: Project, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    _in_process(project, monkeypatch)
    monkeypatch.setenv("STUB_SLEEP", "5")
    monkeypatch.setattr(SCAN, "DEADLINE", 1.5)
    monkeypatch.setattr(sys, "argv", [str(HOOK)])
    project.git("checkout", "-q", "clean")
    event = json.dumps(_event("Bash", {"command": "git push"}, project.root)).encode()
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(event)))
    assert SCAN.main() == 0
    decision = json.loads(capsys.readouterr().out)["hookSpecificOutput"]
    assert decision["permissionDecision"] == "deny" and "outlasted" in decision["permissionDecisionReason"]


def test_the_hook_never_downloads(project: Project, monkeypatch: pytest.MonkeyPatch) -> None:
    _in_process(project, monkeypatch)
    fetched: list[str] = []
    monkeypatch.setattr(SCAN, "_download", lambda url, limit: fetched.append(url) or b"")
    project.binary().unlink()
    for event in (_event("Bash", {"command": "git push origin work"}, project.root),
                  _event("mcp__github__push_files", {"files": [{"path": "x.py", "content": "x = 1\n"}]}, project.root)):
        reason = SCAN.refusal(event, time.monotonic() + 30)
        assert reason is not None and "is not installed" in reason
    assert fetched == []


@pytest.mark.parametrize("event", [
    json.dumps([]),
    json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Bash"}),
    json.dumps(_event("Bash", None, ROOT)),
    json.dumps(_event("Bash", {"command": None}, ROOT)),
    json.dumps(_event("mcp__github__push_files", {"files": None}, ROOT)),
], ids=["a list", "no tool input", "a null tool input", "a null command", "null files"])
def test_an_event_of_another_shape_goes_through(project: Project, event: str) -> None:
    proc = project.run(event)
    assert (proc.returncode, proc.stdout) == (0, "")


def test_a_hook_that_cannot_run_is_a_hook_error_never_a_refusal(project: Project, tmp_path: Path) -> None:
    # Python exits 2 when it cannot open its script, and exit 2 from a PreToolUse hook blocks the call; the
    # registered command maps it to 1, a hook error Claude Code reports without blocking.
    (project.root / ".claude" / "hooks" / "secret_scan_guard.py").unlink()
    missing = project.run(_event("Bash", {"command": "git push"}, project.root))
    assert (missing.returncode, missing.stdout) == (1, "")
    crash = _make(tmp_path / "again").run("not json")
    assert (crash.returncode, crash.stdout) == (1, "")


# --- the binary and its pin ----------------------------------------------------------------------------------

def test_the_pin_is_the_one_ci_s_secret_scan_job_runs() -> None:
    job = yaml.safe_load(CI.read_text(encoding="utf-8"))["jobs"]["secret-scan"]
    assert (VERSION, SHA256) == (str(job["env"]["GITLEAKS_VERSION"]), job["env"]["GITLEAKS_SHA256"])
    step = next(step["run"] for step in job["steps"] if "gitleaks" in step.get("run", ""))
    assert "${GITLEAKS_SHA256}  gitleaks.tgz" in step and "linux_x64.tar.gz" in step


def test_the_binary_lives_under_the_cache_one_directory_per_pin(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    assert SCAN._installed(VERSION, SHA256, "linux_x64") == (
        tmp_path / "earningsnerd" / "gitleaks" / f"{VERSION}-{SHA256[:12]}" / "linux_x64" / "gitleaks")
    monkeypatch.setenv("XDG_CACHE_HOME", "relative/cache")  # not absolute: the XDG spec says to ignore it
    assert SCAN._installed(VERSION, SHA256, "linux_x64") == (
        Path.home() / ".cache" / "earningsnerd" / "gitleaks" / f"{VERSION}-{SHA256[:12]}" / "linux_x64" / "gitleaks")


def _archive(member: str = "gitleaks", text: str | None = None) -> bytes:
    """A release archive holding a `gitleaks` that prints the pinned version."""
    payload = (text or f"#!/bin/sh\necho {VERSION}\n").encode()
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        info = tarfile.TarInfo(member)
        info.size, info.mode = len(payload), 0o755
        tar.addfile(info, io.BytesIO(payload))
    return buffer.getvalue()


@pytest.fixture
def installer(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """The installer with its downloads served from a dict, never the network."""
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    served: dict[str, bytes] = {}
    fetched: list[str] = []

    def download(url: str, limit: int) -> bytes:
        fetched.append(url)
        if url not in served:
            raise OSError(f"404 {url}")
        return served[url]

    monkeypatch.setattr(SCAN, "_download", download)
    return served, fetched


def _release(name: str) -> str:
    return f"https://github.com/gitleaks/gitleaks/releases/download/v{VERSION}/{name}"


def test_install_checks_the_linux_archive_against_ci_s_pin(installer, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    served, fetched = installer
    archive = _archive()
    monkeypatch.setattr(SCAN, "_platform", lambda: "linux_x64")
    served[_release(f"gitleaks_{VERSION}_linux_x64.tar.gz")] = archive
    monkeypatch.setattr(SCAN, "_pin", lambda: (VERSION, hashlib.sha256(b"another archive").hexdigest()))
    assert SCAN.install() == 1
    assert "not the" in capsys.readouterr().err
    pin = hashlib.sha256(archive).hexdigest()
    monkeypatch.setattr(SCAN, "_pin", lambda: (VERSION, pin))
    path = SCAN._installed(VERSION, pin, "linux_x64")
    assert not path.exists()
    assert SCAN.install() == 0
    assert path.read_text() == f"#!/bin/sh\necho {VERSION}\n" and os.access(path, os.X_OK)
    assert [url for url in fetched if "checksums" in url] == []  # the pin alone vouches for the linux archive
    assert SCAN.install() == 0 and "already installed" in capsys.readouterr().out


def test_install_takes_another_platform_s_hash_from_a_checksums_file_that_lists_the_pin(
        installer, monkeypatch: pytest.MonkeyPatch) -> None:
    served, _ = installer
    archive, pin = _archive(), hashlib.sha256(b"the linux archive").hexdigest()
    monkeypatch.setattr(SCAN, "_platform", lambda: "darwin_arm64")
    monkeypatch.setattr(SCAN, "_pin", lambda: (VERSION, pin))
    served[_release(f"gitleaks_{VERSION}_darwin_arm64.tar.gz")] = archive
    listed = f"{hashlib.sha256(archive).hexdigest()}  gitleaks_{VERSION}_darwin_arm64.tar.gz\n"
    served[_release(f"gitleaks_{VERSION}_checksums.txt")] = listed.encode()
    assert SCAN.install() == 1  # the file does not list CI's pin for the linux archive
    served[_release(f"gitleaks_{VERSION}_checksums.txt")] = (listed + f"{pin}  gitleaks_{VERSION}_linux_x64.tar.gz\n").encode()
    assert SCAN.install() == 0
    assert SCAN._installed(VERSION, pin, "darwin_arm64").is_file()


@pytest.mark.parametrize("archive", [_archive("bin/gitleaks"), _archive(text="#!/bin/sh\necho 0.0.1\n"), b"not a tar"],
                         ids=["no gitleaks at the top", "another version", "not an archive"])
def test_install_refuses_an_archive_that_is_not_the_release_s(installer, monkeypatch: pytest.MonkeyPatch, archive: bytes) -> None:
    served, _ = installer
    pin = hashlib.sha256(archive).hexdigest()
    monkeypatch.setattr(SCAN, "_platform", lambda: "linux_x64")
    monkeypatch.setattr(SCAN, "_pin", lambda: (VERSION, pin))
    served[_release(f"gitleaks_{VERSION}_linux_x64.tar.gz")] = archive
    assert SCAN.install() == 1
    assert not SCAN._installed(VERSION, pin, "linux_x64").exists()  # nothing is left where the hook would run it


# --- the real binary -----------------------------------------------------------------------------------------

def test_the_real_binary_reads_its_files_as_the_stub_does(tmp_path: Path) -> None:
    """The cases that turn on how gitleaks reads its files and git's output, against the pinned binary when it is
    installed."""
    project = _make(tmp_path, binary="real")
    _found(project.bash("git push origin work"))
    # The settings and refs that would blind it are held at git's defaults, as on CI's runner.
    blinders = (("color.ui", "always"), ("log.abbrevCommit", "true"), ("core.bigFileThreshold", "1"))
    for name, value in blinders:
        project.git("config", name, value)
    project.git("replace", project.leak, project.git("rev-parse", "clean"))
    _found(project.bash("git push origin work"))
    project.git("replace", "-d", project.leak)
    for name, _ in blinders:
        project.git("config", "--unset", name)
    # gitleaks reads rules in the directory it scans when no --config names any, as with no rules on main, which is
    # why the hook refuses a git directory that holds them.
    rules = project.root / ".git" / ".gitleaks.toml"
    for planted, exit_code in ((False, SCAN.LEAKS), (True, 0)):
        if planted:
            rules.write_text(ALLOW_ALL, encoding="utf-8")
        direct = subprocess.run([str(project.binary()), "git", str(project.root / ".git"), "--log-opts=main..work",
                                 "--no-banner", f"--exit-code={SCAN.LEAKS}"], cwd=tmp_path, env=_plain_env(),
                                capture_output=True)
        assert direct.returncode == exit_code, direct.stderr
    assert "git directory holds a .gitleaks.toml" in (project.bash("git push origin work") or "")
    rules.unlink()
    project.write({".gitleaksignore": f"{project.leak}:b.py:generic-api-key:1\nb.py:generic-api-key:1\n"})
    _found(project.bash("git push origin work"))  # the worktree's own pins do not reach the scan
    (project.root / ".gitleaksignore").unlink()
    project.commit({".gitleaks.toml": ALLOW_ALL}, "rules on the branch")
    _found(project.bash("git push origin work"))  # nor do its own rules
    project.git("checkout", "-q", "clean")
    project.commit({"d.py": MARKED + "\n"}, "marked")
    assert project.bash("git push origin clean") is None
    _found(_mcp(project, "mcp__github__create_or_update_file", branch="main", path="x.py", content=LEAK), "x.py:1")
    project.git("checkout", "-q", "main")
    project.commit({".gitleaksignore": f"{project.leak}:b.py:generic-api-key:1\n", "legacy.py": LEAK + "\n"}, "pin")
    project.publish("main")
    assert project.bash("git push origin work") is None  # main's pin counts
    assert _mcp(project, "mcp__github__create_or_update_file", branch="main", path="legacy.py",
                content=LEAK + "\nmore = 1\n") is None  # an unchanged line is no new finding
    project.commit({".gitleaks.toml": ALLOW_ALL}, "rules on main")
    project.publish("main")
    assert _mcp(project, "mcp__github__create_or_update_file", branch="main", path="x.py", content=LEAK) is None


def test_the_real_binary_s_built_in_allowlist_lets_its_stopwords_through(tmp_path: Path) -> None:
    # With no rules on main the scan names none, so gitleaks reads its built-in config, as CI's scan does: a
    # placeholder token its global allowlist's stopwords let through goes through, where rules that only extend that
    # config would refuse it.
    project = _make(tmp_path, binary="real")
    placeholder = 'GITHUB = "ghp_' + string.ascii_lowercase + '0123456789"\n'
    project.git("checkout", "-q", "clean")
    project.commit({"s.py": placeholder}, "a placeholder token")
    assert project.bash("git push origin clean") is None
    assert _mcp(project, "mcp__github__create_or_update_file", branch="main", path="s.py", content=placeholder) is None


@pytest.mark.parametrize("source", ATTRIBUTE_SOURCES)
def test_the_real_binary_reads_no_attributes_the_repository_points_it_at(tmp_path: Path, source: str) -> None:
    project = _make(tmp_path, binary="real")
    _plant_attributes(project, source)
    _found(project.bash("git push origin work"))
    _found(_mcp(project, "mcp__github__create_or_update_file", branch="main", path="x.py", content=LEAK + "\n"),
           "x.py:1")


def test_the_real_binary_s_failed_scan_is_refused_with_the_error_it_logged(tmp_path: Path) -> None:
    project = _make(tmp_path, binary="real")
    _graft(project)
    _failed_for_the_graft(project.bash("git push origin work"))


# --- git's pre-push hook -------------------------------------------------------------------------------------
# .claude/hooks/git/pre-push runs the hook with --pre-push once a clone's core.hooksPath names its directory. Each
# case pushes for real, outside any Claude Code hook, with origin's pushes sent to a bare repository beside the
# project, so git itself runs the hook on the refs the push sends, whoever runs it.

def _stopped(proc: subprocess.CompletedProcess[str], project: Project, *also: str) -> None:
    """git sent nothing: the hook stopped the push on the planted line, read as a push of literal refspecs, and the
    remote holds no commit of it."""
    assert proc.returncode != 0, "git sent the push"
    assert STOPPED in proc.stderr, proc.stderr
    # the hook's own lines, before the one git adds after them (`error: failed to push some refs ...`)
    own = proc.stderr[proc.stderr.find(STOPPED):].split("\nerror: failed to push some refs")[0]
    assert own.endswith(f"({LESSON})."), own  # a finding's refusal names no way around the scan
    assert "b.py:1 (generic-api-key)" in own and "this push would add" in own and "literal refspecs" not in own, own
    assert "--no-verify" not in proc.stderr and _value(1) not in proc.stderr, proc.stderr
    for rev in (project.leak, *also):
        assert not project.received(rev), f"the remote received {rev}"


# Pushes that send the planted commit, each stopped as git sends it: (command, files it names, git steps first).
# The PreToolUse hook lets the first three through, as stated gaps; git runs this hook whoever runs the push, and,
# by the absolute path a cloud session's start sets, wherever it runs: git reads a relative one from the directory
# it runs hooks in, and from .git or with a GIT_DIR from elsewhere would miss it.
SUB = {"sub/x.txt": "x\n"}  # a subdirectory of the worktree
PRE_PUSHES = {
    "a push a script runs": ("sh push.sh", {"push.sh": "git push origin work\n"}, []),
    "a push a program runs": (
        """python3 -c 'import subprocess, sys; sys.exit(subprocess.run(["git", "push", "origin", "work"]).returncode)'""",
        {}, []),
    "a git a variable names": ("GIT=git; $GIT push origin work", {}, []),
    "a push of the branch": ("git push origin work", {}, []),
    "a push from a subdirectory": ("cd sub && git push origin work", SUB, []),
    "a push from inside .git": ("cd .git && git push origin work", {}, []),
    "a push from the git directory a script finds": ('cd "$(git rev-parse --git-dir)" && git push origin work', {}, []),
    "a GIT_DIR from a subdirectory": ("cd sub && GIT_DIR=../.git git push origin work", SUB, []),
    "--git-dir from a subdirectory": ("cd sub && git --git-dir=../.git push origin work", SUB, []),
    "a GIT_DIR from outside the worktree": ("cd .. && GIT_DIR=project/.git git push origin work", {}, []),
    "GIT_DIR and GIT_WORK_TREE from outside the worktree": (
        "cd .. && GIT_DIR=project/.git GIT_WORK_TREE=project git push origin work", {}, []),
    "-C and --work-tree from outside the worktree": (
        "git -C .. --git-dir=project/.git --work-tree=project push origin work", {}, []),
    "HEAD under a new name": ("git push origin HEAD:refs/heads/renamed", {}, [["checkout", "-q", "work"]]),
    "a source with a space": ("git push origin 'work^{/plant|no such message}:refs/heads/spaced'", {}, []),
    "every branch": ("git push --all origin", {}, []),
    "a mirror": ("git push --mirror origin", {}, []),
    "an annotated tag of the commit": ("git push origin planted", {}, [["tag", "-a", "planted", "-m", "t", "work"]]),
    "a lightweight tag of the commit": ("git push origin light", {}, [["tag", "light", "work"]]),
    "a force push over a branch GitHub holds": ("git push origin clean && git push -f origin work:clean", {}, []),
}


@pytest.mark.parametrize(("command", "files", "steps"), PRE_PUSHES.values(), ids=PRE_PUSHES.keys())
def test_git_s_pre_push_hook_stops_each_push_of_the_planted_commit(project: Project, command: str,
                                                                   files: dict[str, str], steps: list) -> None:
    project.enable()
    project.write(files)
    _setup(project, steps)
    _stopped(project.push(command), project)


@pytest.mark.parametrize("refspecs", ["clean work", "work clean"])
def test_a_push_the_hook_stops_sends_none_of_its_refs(project: Project, refspecs: str) -> None:
    project.enable()
    _stopped(project.push(f"git push origin {refspecs}"), project, project.git("rev-parse", "clean"))


def test_git_s_pre_push_hook_scans_a_clean_push_and_lets_it_through(project: Project) -> None:
    project.enable()
    proc = project.push("git push origin clean")
    assert proc.returncode == 0, proc.stderr
    assert project.received(project.git("rev-parse", "clean"))
    assert len(project.scans()) == 1  # it ran the scan, over the one commit GitHub does not hold


def test_git_s_pre_push_hook_reads_a_push_from_a_linked_worktree(project: Project) -> None:
    # git runs the hook at the linked worktree's top, with GIT_DIR exported; the hooks path names the main worktree's
    project.enable()
    linked = project.root.parent / "linked"
    project.git("worktree", "add", "-q", "-b", "linked", str(linked), "work")
    _stopped(project.push("git push origin linked", cwd=linked), project)


def test_a_delete_and_a_commit_github_holds_are_not_scanned(project: Project) -> None:
    project.enable()
    assert project.push("git push --no-verify origin work").returncode == 0  # the remote holds the planted commit
    # and no ref here does, so a delete read as sending what the remote holds would scan it
    project.git("update-ref", "-d", "refs/remotes/origin/work")
    proc = project.push("git push origin :work")  # a delete sends nothing
    assert proc.returncode == 0, proc.stderr
    project.publish("work")  # GitHub holds `work`, as last fetched
    proc = project.push("git push origin work")
    assert proc.returncode == 0, proc.stderr
    assert project.scans() == []


def test_no_verify_skips_git_s_hooks_a_stated_gap(project: Project) -> None:
    project.enable()
    proc = project.push("git push --no-verify origin work")
    assert proc.returncode == 0 and project.received(project.leak), proc.stderr


def test_git_skips_a_pre_push_hook_it_cannot_execute(project: Project) -> None:
    # Why the tracked hook's mode is held below: git runs no hook it cannot execute, and sends the push.
    project.enable()
    (project.root / SCAN.HOOKS_PATH / "pre-push").chmod(0o644)
    proc = project.push("git push origin work")
    assert proc.returncode == 0 and project.received(project.leak), proc.stderr
    assert project.scans() == []


def test_the_pre_push_hook_is_tracked_executable_and_runs_the_scan() -> None:
    listed = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-s", "--", ".claude/hooks/git/pre-push"],
                            capture_output=True, text=True, env=_plain_env(), check=True).stdout
    assert listed.startswith("100755 "), listed or "the hook is not tracked"
    assert os.access(PRE_PUSH, os.X_OK)
    text = PRE_PUSH.read_text(encoding="utf-8")
    assert text.startswith("#!/bin/sh\n")
    assert text.rstrip().endswith('exec python3 -I -S "$(dirname "$0")/../secret_scan_guard.py" --pre-push "$@"')
    assert PRE_PUSH.parent == ROOT / SCAN.HOOKS_PATH


def test_the_pre_push_hook_stops_a_tag_of_a_tree_or_a_blob(project: Project) -> None:
    # git sends the object itself, which no commit holds, and the scan reads what commits add
    project.enable()
    project.git("tag", "tree", "work^{tree}")
    project.git("tag", "-a", "blob", "-m", "the planted file", "work:b.py")
    for tag, kind, rev in (("tree", "a tree", "work^{tree}"), ("blob", "a blob", "work:b.py")):
        proc = project.push(f"git push origin {tag}")
        assert proc.returncode != 0 and STOPPED in proc.stderr, proc.stderr
        assert f"this push sends refs/tags/{tag}, which names {kind}, not a commit" in proc.stderr, proc.stderr
        assert "`git push --no-verify` skips git's hooks" in proc.stderr, proc.stderr
        assert not project.received(project.git("rev-parse", rev))


def test_the_pre_push_hook_fails_closed_without_the_binary(project: Project) -> None:
    project.enable()
    project.binary().unlink()
    for branch in ("work", "clean"):
        proc = project.push(f"git push origin {branch}")
        assert proc.returncode != 0 and STOPPED in proc.stderr, proc.stderr
        assert "is not installed" in proc.stderr and "--install" in proc.stderr, proc.stderr
        assert "`git push --no-verify` skips git's hooks" in proc.stderr, proc.stderr
    assert not project.received(project.leak)
    proc = project.push("git push origin main")  # it adds no commit GitHub lacks, so there is nothing to scan
    assert proc.returncode == 0, proc.stderr


def test_the_pre_push_hook_reads_git_s_lines_and_refuses_one_it_cannot(project: Project,
                                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    _in_process(project, monkeypatch)
    deadline, here, zero = time.monotonic() + 30, str(project.root), "0" * 40
    assert SCAN.pre_push("", deadline, here) is None
    assert SCAN.pre_push(f"(delete) {zero} refs/heads/work {project.leak}\n", deadline, here) is None
    _found(SCAN.pre_push(f"refs/heads/work {project.leak} refs/heads/work {zero}\n", deadline, here))
    # git hands a source as the push names it, spaces and all
    _found(SCAN.pre_push(f"work^{{/plant|no such message}} {project.leak} refs/heads/spaced {zero}\n", deadline,
                         here))
    for line in ("refs/heads/work", f"refs/heads/work {project.leak} refs/heads/work",
                 f"refs/heads/work {project.leak[:12]} refs/heads/work {zero}",
                 f"refs/heads/work {project.leak} refs/heads/a b {zero}"):
        with pytest.raises(SCAN._Unscannable, match="a line the hook cannot read"):
            SCAN.pre_push(line + "\n", deadline, here)


def test_an_error_the_pre_push_hook_does_not_expect_stops_the_push(project: Project, monkeypatch: pytest.MonkeyPatch,
                                                                   capsys: pytest.CaptureFixture[str]) -> None:
    _in_process(project, monkeypatch)

    def broken(*args: object, **kwargs: object) -> None:
        raise RuntimeError("planted")

    monkeypatch.setattr(SCAN, "pre_push", broken)
    monkeypatch.setattr(sys, "stdin", io.StringIO(f"refs/heads/work {project.leak} refs/heads/work {'0' * 40}\n"))
    assert SCAN._pre_push_main() == 1
    err = capsys.readouterr().err
    assert err.startswith(STOPPED) and "an error the hook does not expect (RuntimeError: planted)" in err, err
    assert "`git push --no-verify` skips git's hooks" in err


def test_the_real_binary_stops_a_pre_push_of_the_planted_commit(tmp_path: Path) -> None:
    project = _make(tmp_path, binary="real")
    project.enable()
    _stopped(project.push("git push origin work"), project)


# --- a session's start, and --turn-on ------------------------------------------------------------------------

def _session_registered() -> list[dict]:
    """The SessionStart entries of .claude/settings.json that run this file."""
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    return [entry for entry in settings["hooks"].get("SessionStart", [])
            if any("secret_scan_guard.py" in hook.get("command", "") for hook in entry["hooks"])]


def _start_env(project: Project, env: dict[str, str | None] | None, root: Path) -> dict[str, str]:
    """The environment a session's start, or a person's --turn-on, runs in: git finds no repository above the case's
    directory, and reads a global file of the case's own. A variable `env` gives None is unset."""
    own = project.root.parent / "global.gitconfig"
    own.touch()
    # A cloud session running this suite has CLAUDE_CODE_REMOTE set; a case gives it only where it means one.
    plain = {key: value for key, value in _plain_env().items() if key != "CLAUDE_CODE_REMOTE"}
    full = {**plain, "CLAUDE_PROJECT_DIR": str(root), "GIT_CONFIG_GLOBAL": str(own),
            "XDG_CACHE_HOME": str(project.cache), "GIT_CEILING_DIRECTORIES": str(project.root.parent), **(env or {})}
    return {key: value for key, value in full.items() if value is not None}


def _session_start(project: Project, env: dict[str, str | None] | None = None, root: Path | None = None,
                   cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Run the command .claude/settings.json registers for a session's start, as Claude Code does, in the project (or
    the worktree `root`, from `cwd` in it), within the time it registers, leaving the case's global file as it was."""
    [hook] = [hook for entry in _session_registered() for hook in entry["hooks"]]
    root = root or project.root
    full = _start_env(project, env, root)
    read = Path(full["GIT_CONFIG_GLOBAL"])
    before = read.read_bytes()
    event = json.dumps({"session_id": "s", "hook_event_name": "SessionStart", "source": "startup", "cwd": str(root)})
    proc = subprocess.run(["sh", "-c", hook["command"]], input=event, capture_output=True, text=True, env=full,
                          cwd=cwd or root, timeout=hook["timeout"])
    assert read.read_bytes() == before, "the session's start wrote git's global configuration"
    return proc


def _turned_on(project: Project, env: dict[str, str | None] | None = None,
               root: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Run --turn-on as a person does, in the project (or the worktree `root`) with its own copy of this file and in no
    cloud session, leaving the case's global file as it was."""
    root = root or project.root
    full = _start_env(project, env, root)
    read = Path(full["GIT_CONFIG_GLOBAL"])
    before = read.read_bytes()
    proc = subprocess.run(["python3", "-I", "-S", ".claude/hooks/secret_scan_guard.py", "--turn-on"], cwd=root,
                          capture_output=True, text=True, env=full, timeout=30)
    assert read.read_bytes() == before, "--turn-on wrote git's global configuration"
    return proc


def _hooks_path(project: Project) -> str | None:
    """core.hooksPath as the clone's own configuration sets it."""
    proc = subprocess.run(["git", "-C", str(project.root), "config", "--local", "--get", "core.hooksPath"],
                          capture_output=True, text=True, env=_plain_env())
    return proc.stdout.strip() if proc.returncode == 0 else None


def _ours(project: Project) -> str:
    """The hooks path a cloud session's start sets: the clone's own hooks directory, absolute."""
    return str(project.root.resolve() / SCAN.HOOKS_PATH)


def _git_wrapper(folder: Path, body: str) -> dict[str, str]:
    """A PATH whose git is a shell script running `body`, with $REAL the real git."""
    folder.mkdir()
    wrapper = folder / "git"
    wrapper.write_text(f"#!/bin/sh\nREAL={shlex.quote(shutil.which('git') or 'git')}\n{body}\n", encoding="utf-8")
    wrapper.chmod(0o755)
    return {"PATH": f"{folder}{os.pathsep}{os.environ['PATH']}"}


def _plain(tmp_path: Path) -> Project:
    """A folder holding this file in no repository."""
    folder = tmp_path / "plain"
    (folder / ".claude" / "hooks").mkdir(parents=True)
    shutil.copy(HOOK, folder / ".claude" / "hooks")
    return Project(folder, tmp_path / "cache", tmp_path / "stub.log")


CLOUD = {"CLAUDE_CODE_REMOTE": "true"}
OFF = "the secret-scan pre-push hook is off in this clone: "
AGAIN = "`python3 .claude/hooks/secret_scan_guard.py --turn-on` turns it on once that is fixed"


def test_a_cloud_session_s_start_turns_the_pre_push_hook_on(project: Project) -> None:
    project.remote()
    proc = _session_start(project, CLOUD)
    assert (proc.returncode, proc.stdout, proc.stderr) == (0, "", "")
    assert _hooks_path(project) == _ours(project)
    _stopped(project.push("git push origin work"), project)
    _stopped(project.push("cd .git && git push origin work"), project)  # where git would miss a relative path
    again = _session_start(project, CLOUD)
    assert (again.returncode, again.stdout) == (0, "") and _hooks_path(project) == _ours(project)
    project.git("config", "--unset", "core.hooksPath")
    below = _session_start(project, CLOUD, cwd=project.root / ".github")  # git names its directories from there
    assert (below.returncode, below.stdout) == (0, "") and _hooks_path(project) == _ours(project)


def test_a_session_start_writes_its_own_hooks_path_absolute(project: Project) -> None:
    # A relative path, as an earlier start or a person wrote it, names the directory but misses a push from .git; one
    # from ~ names it only while HOME does
    project.remote()
    home = {"HOME": str(project.root.parent)}  # git expands a leading ~ from it
    for spelling in (SCAN.HOOKS_PATH, f"./{SCAN.HOOKS_PATH}/", f"~/project/{SCAN.HOOKS_PATH}"):
        project.git("config", "core.hooksPath", spelling)
        proc = _session_start(project, {**CLOUD, **home})
        assert (proc.returncode, proc.stdout) == (0, "") and _hooks_path(project) == _ours(project), spelling
    _stopped(project.push("cd .git && git push origin work"), project)
    # An absolute one naming it otherwise, which git reads alike wherever it runs hooks, stays as it is written: a
    # symlink through which another view of the clone (a container's) reads its own path among them
    link = project.root.parent / "hooks-link"
    link.symlink_to(_ours(project), target_is_directory=True)
    for spelling in (_ours(project) + "/", str(link)):
        project.git("config", "core.hooksPath", spelling)
        proc = _session_start(project, CLOUD)
        assert (proc.returncode, proc.stdout) == (0, "") and _hooks_path(project) == spelling, spelling
        _stopped(project.push("cd .git && git push origin work"), project)


@pytest.mark.parametrize("variable", ["GIT_DIR", "GIT_COMMON_DIR"])
def test_a_session_start_sets_the_clone_it_is_in_whatever_the_session_s_git_dir_names(project: Project,
                                                                                     tmp_path: Path,
                                                                                     variable: str) -> None:
    proc = _session_start(project, {**CLOUD, variable: str(project.elsewhere / ".git")})
    assert (proc.returncode, proc.stdout) == (0, "") and _hooks_path(project) == _ours(project)
    elsewhere = subprocess.run(["git", "-C", str(project.elsewhere), "config", "--local", "--get", "core.hooksPath"],
                               capture_output=True, text=True, env=_plain_env())
    assert elsewhere.returncode == 1, elsewhere.stdout
    # GIT_CONFIG has `git config` read one file alone, and write none
    project.git("config", "--unset", "core.hooksPath")
    other = tmp_path / "other.gitconfig"
    other.write_text("[core]\n\thooksPath = /etc/githooks\n", encoding="utf-8")
    proc = _session_start(project, {**CLOUD, "GIT_CONFIG": str(other)})
    assert (proc.returncode, proc.stdout) == (0, "") and _hooks_path(project) == _ours(project)


@pytest.mark.parametrize("remote", [None, "false", "1"])
def test_a_session_start_outside_the_cloud_changes_nothing(project: Project, remote: str | None) -> None:
    proc = _session_start(project, {"CLAUDE_CODE_REMOTE": remote})
    assert (proc.returncode, proc.stdout) == (0, "") and _hooks_path(project) is None


def test_a_session_start_keeps_a_hooks_path_set_at_any_level(project: Project, tmp_path: Path) -> None:
    project.git("config", "core.hooksPath", ".husky")
    proc = _session_start(project, CLOUD)
    assert proc.returncode == 0 and _hooks_path(project) == ".husky"
    assert proc.stdout == (f"{OFF}core.hooksPath is .husky at the local level, which this leaves as it is. "
                           f"`git config core.hooksPath {_ours(project)}` turns it on, in place of .husky\n"), proc.stdout
    project.git("config", "--unset", "core.hooksPath")
    other = tmp_path / "other" / SCAN.HOOKS_PATH  # another checkout's copy, there: not a moved clone's old path
    other.mkdir(parents=True)
    for spelling, env in ((str(other), CLOUD), (f"~/other/{SCAN.HOOKS_PATH}", {**CLOUD, "HOME": str(tmp_path)})):
        project.git("config", "core.hooksPath", spelling)
        proc = _session_start(project, env)
        assert proc.returncode == 0 and _hooks_path(project) == spelling
        assert proc.stdout.startswith(f"{OFF}core.hooksPath is {spelling} at the local level, which this leaves as it "
                                      "is. "), proc.stdout
    project.git("config", "--unset", "core.hooksPath")
    machine = tmp_path / "machine.gitconfig"  # a hooks path every clone reads
    machine.write_text("[core]\n\thooksPath = /etc/githooks\n", encoding="utf-8")
    levels = {
        "global": {"GIT_CONFIG_GLOBAL": str(machine)},
        "system": {"GIT_CONFIG_SYSTEM": str(machine), "GIT_CONFIG_NOSYSTEM": None},
        "command": {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.hooksPath",
                    "GIT_CONFIG_VALUE_0": "/etc/githooks"},
    }
    for level, env in levels.items():
        proc = _session_start(project, {**CLOUD, **env})
        assert proc.returncode == 0 and _hooks_path(project) is None, level
        assert f"{OFF}core.hooksPath is /etc/githooks at the {level} level, which this leaves as it is. " in \
            proc.stdout, (level, proc.stdout)
        # the clone's own setting outranks the user's and the machine's, not the session's environment
        fix = (f"`git config core.hooksPath {_ours(project)}` turns it on, in place of /etc/githooks" if level != "command"
               else "The session's environment sets it (GIT_CONFIG_COUNT or GIT_CONFIG_PARAMETERS), which outranks "
                    f"the clone's configuration; without it, `git config core.hooksPath {_ours(project)}` turns it on")
        assert proc.stdout.endswith(f"{fix}\n"), (level, proc.stdout)
    # A worktree's own setting outranks the clone's too: the note's two commands turn the hook on
    project.git("config", "extensions.worktreeConfig", "true")
    project.git("config", "--worktree", "core.hooksPath", "/etc/githooks")
    proc = _session_start(project, CLOUD)
    assert proc.stdout == (f"{OFF}core.hooksPath is /etc/githooks at the worktree level, which this leaves as it is. "
                           "`git config --worktree --unset core.hooksPath` and "
                           f"`git config core.hooksPath {_ours(project)}` turn it on, in place of /etc/githooks\n"), \
        proc.stdout
    project.git("config", "--worktree", "--unset", "core.hooksPath")
    project.git("config", "core.hooksPath", _ours(project))
    project.remote()
    _stopped(project.push("git push origin work"), project)
    project.git("config", "--unset", "core.hooksPath")
    # where the hook stays off, the session still learns the PreToolUse hook's binary is missing
    project.binary().unlink()
    proc = _session_start(project, {**CLOUD, **levels["global"]})
    assert "core.hooksPath is /etc/githooks" in proc.stdout and "is not installed" in proc.stdout, proc.stdout


def test_a_session_start_keeps_a_clone_s_own_hooks(project: Project) -> None:
    own = project.root / ".git" / "hooks" / "pre-commit"
    own.write_text("#!/bin/sh\n", encoding="utf-8")
    own.chmod(0o755)
    linked = project.root.parent / "linked"
    project.git("worktree", "add", "-q", "-b", "linked", str(linked), "work")
    for root in (project.root, linked):  # a linked worktree's hooks are its main worktree's (`--git-path hooks`)
        proc = _session_start(project, CLOUD, root)
        assert proc.returncode == 0 and _hooks_path(project) is None, proc.stdout
        assert proc.stdout == (f"{OFF}it has hooks of its own in {project.root.resolve() / '.git' / 'hooks'} "
                               "(pre-commit), which this leaves as they are. "
                               f"`git config core.hooksPath {_ours(project)}` turns it on, and git then runs none of "
                               "them\n"), proc.stdout
    # a clone whose git directory is elsewhere (`--separate-git-dir`): its hooks are there
    apart = project.root.parent / "apart"
    project.git("clone", "-q", "--separate-git-dir", str(project.root.parent / "apart.git"), str(project.root),
                str(apart))
    (project.root.parent / "apart.git" / "hooks" / "pre-commit").write_text("#!/bin/sh\n", encoding="utf-8")
    (project.root.parent / "apart.git" / "hooks" / "pre-commit").chmod(0o755)
    proc = _session_start(Project(apart, project.cache, project.log), CLOUD)
    assert proc.returncode == 0 and "(pre-commit), which this leaves as they are" in proc.stdout, proc.stdout
    assert _hooks_path(Project(apart, project.cache, project.log)) is None
    own.chmod(0o644)  # a file git would not run is no hook of its own
    proc = _session_start(project, CLOUD)
    assert (proc.returncode, proc.stdout) == (0, "") and _hooks_path(project) == _ours(project)


def test_a_session_start_in_a_linked_worktree_names_the_main_checkout_s_hooks(project: Project) -> None:
    # Every worktree reads the clone's one path, and one naming the linked worktree's directory would go with it.
    project.remote()
    linked = project.root.parent / "linked"
    project.git("worktree", "add", "-q", "-b", "linked", str(linked), "clean")
    proc = _session_start(project, CLOUD, linked)
    assert (proc.returncode, proc.stdout, proc.stderr) == (0, "", "") and _hooks_path(project) == _ours(project)
    again = _session_start(project, CLOUD, linked)  # the main checkout's path, set already: nothing to say
    assert (again.returncode, again.stdout) == (0, "") and _hooks_path(project) == _ours(project)
    # Spelled otherwise, each written as the main checkout's: relative, read from the main checkout's top as git reads
    # it for a push there; and the linked worktree's own copy, an earlier start's, from either worktree.
    own_copy = str(linked.resolve() / SCAN.HOOKS_PATH)
    for spelling, root in ((SCAN.HOOKS_PATH, linked), (own_copy, project.root), (own_copy, linked)):
        project.git("config", "core.hooksPath", spelling)
        proc = _session_start(project, CLOUD, root)
        assert (proc.returncode, proc.stdout) == (0, "") and _hooks_path(project) == _ours(project), (spelling, root)
    project.git("config", "--unset", "core.hooksPath")  # a GIT_WORK_TREE the session sets names no other top
    proc = _session_start(project, {**CLOUD, "GIT_WORK_TREE": str(project.elsewhere)}, linked)
    assert (proc.returncode, proc.stdout) == (0, "") and _hooks_path(project) == _ours(project)
    # The pin that counts is the one the main checkout's copy reads, as git runs that copy for every worktree
    ci = project.root / ".github" / "workflows" / "ci.yml"
    pinned = ci.read_bytes()
    ci.write_bytes(pinned + b"\n# \xff\n")
    proc = _session_start(project, CLOUD, linked)
    assert proc.stdout.startswith("each push that adds commits is refused until this is fixed: the hooks cannot "
                                  "check their gitleaks (UnicodeDecodeError: "), proc.stdout
    ci.write_bytes(pinned)
    stub = project.binary().read_bytes()
    project.binary().unlink()  # and its --install is that copy's, which installs the pin the note read
    proc = _session_start(project, CLOUD, linked)
    assert f"`python3 {project.root.resolve() / '.claude' / 'hooks' / 'secret_scan_guard.py'} --install`" in \
        proc.stdout, proc.stdout
    project.binary().write_bytes(stub)
    project.binary().chmod(0o755)
    project.git("worktree", "remove", "--force", str(linked))
    _stopped(project.push("git push origin work"), project)


def test_a_session_start_in_a_linked_worktree_sets_no_path_it_cannot_keep(project: Project) -> None:
    linked = project.root.parent / "linked"
    project.git("worktree", "add", "-q", "-b", "linked", str(linked), "clean")
    project.binary().unlink()  # where nothing is set, the session still learns the binary is missing
    shim = project.root / SCAN.HOOKS_PATH / "pre-push"
    note = (f"{OFF}the main checkout holds no executable {_ours(project)}/pre-push, the hook every worktree's pushes "
            "would run")
    shim.chmod(0o644)  # a file git would not run, as in a checkout that keeps no file modes
    proc = _session_start(project, CLOUD, linked)
    assert proc.returncode == 0 and _hooks_path(project) is None
    assert proc.stdout.splitlines()[0] == note and "is not installed" in proc.stdout, proc.stdout
    shim.unlink()  # the main checkout at a commit from before E134
    proc = _session_start(project, CLOUD, linked)
    assert proc.returncode == 0 and _hooks_path(project) is None
    assert proc.stdout.splitlines()[0] == note and "is not installed" in proc.stdout, proc.stdout
    # A checkout's copy set by hand by its absolute path runs for every push all the same: only the binary's note. A
    # relative one names each worktree's own copy, which the main checkout does not hold.
    by_hand = str(linked.resolve() / SCAN.HOOKS_PATH)
    project.git("config", "core.hooksPath", by_hand)
    proc = _session_start(project, CLOUD, linked)
    assert proc.returncode == 0 and _hooks_path(project) == by_hand
    assert proc.stdout.startswith("each push that adds commits is refused until this is fixed: gitleaks ") and \
        proc.stdout.count("\n") == 1, proc.stdout
    project.git("config", "core.hooksPath", SCAN.HOOKS_PATH)
    proc = _session_start(project, CLOUD, linked)
    assert proc.stdout.splitlines()[0] == note and _hooks_path(project) == SCAN.HOOKS_PATH, proc.stdout
    # Set by hand in one worktree's own configuration, or the session's environment, it reaches no other worktree
    project.git("config", "--unset", "core.hooksPath")
    project.git("config", "extensions.worktreeConfig", "true")
    project.git("config", "--worktree", "core.hooksPath", by_hand, cwd=linked)
    proc = _session_start(project, CLOUD, linked)
    assert proc.stdout.splitlines()[0] == note and _hooks_path(project) is None, proc.stdout
    project.git("config", "--worktree", "--unset", "core.hooksPath", cwd=linked)
    proc = _session_start(project, {**CLOUD, "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.hooksPath",
                                    "GIT_CONFIG_VALUE_0": by_hand}, linked)
    assert proc.stdout.splitlines()[0] == note and _hooks_path(project) is None, proc.stdout


def test_a_session_start_in_a_clone_without_a_main_checkout_sets_none(project: Project, tmp_path: Path) -> None:
    # A git directory with no checkout of its own above it, named .git: none this can name for every worktree.
    apart, apart_git = tmp_path / "apart", tmp_path / "apart.git"
    project.git("clone", "-q", "--separate-git-dir", str(apart_git), str(project.root), str(apart))
    project.git("worktree", "add", "-q", "-b", "apart-linked", str(tmp_path / "apart-linked"), cwd=apart)
    bare = tmp_path / "bare.git"
    project.git("clone", "-q", "--bare", str(project.root), str(bare))
    project.git("worktree", "add", "-q", "-b", "bare-linked", str(tmp_path / "bare-linked"), cwd=bare)
    named = tmp_path / "named"  # a bare repository where a checkout's .git would be
    project.git("clone", "-q", "--bare", str(project.root), str(named / ".git"))
    project.git("worktree", "add", "-q", "-b", "named-linked", str(named / "linked"), cwd=named / ".git")
    host = tmp_path / "host"  # another repository's checkout, holding this clone's git directory
    project.git("init", "-q", str(host))
    hosted, hosted_git = tmp_path / "hosted", host / "hosted.git"
    project.git("clone", "-q", "--separate-git-dir", str(hosted_git), str(project.root), str(hosted))
    project.git("worktree", "add", "-q", "-b", "hosted-linked", str(tmp_path / "hosted-linked"), cwd=hosted)
    for git_dir, linked in ((apart_git, tmp_path / "apart-linked"), (bare, tmp_path / "bare-linked"),
                            (named / ".git", named / "linked"), (hosted_git, tmp_path / "hosted-linked")):
        clone = Project(linked, project.cache, project.log)
        proc = _session_start(clone, CLOUD)
        assert proc.returncode == 0 and _hooks_path(clone) is None, git_dir
        assert proc.stdout == (
            "the secret-scan pre-push hook may be off in this clone: this is a linked worktree of a clone with no main "
            f"checkout the hook can find above its git directory ({git_dir.resolve()}), so it sets no core.hooksPath. "
            "`git config core.hooksPath <checkout>/.claude/hooks/git`, naming by its absolute path a checkout of the "
            "clone that stays, turns it on for every worktree\n"), proc.stdout
    # A checkout's own copy, set by hand by its absolute path as the note says, runs for every push: nothing more to
    # say. A hook of another kind set so is no scan, nor is a relative path, which git reads from each worktree's own
    # top, and the note stays.
    husky = tmp_path / ".husky"
    husky.mkdir()
    (husky / "pre-push").write_text("#!/bin/sh\n", encoding="utf-8")
    (husky / "pre-push").chmod(0o755)
    for by_hand in (str(husky), SCAN.HOOKS_PATH):
        project.git("config", "core.hooksPath", by_hand, cwd=apart)
        proc = _session_start(Project(tmp_path / "apart-linked", project.cache, project.log), CLOUD)
        assert proc.stdout.startswith("the secret-scan pre-push hook may be off in this clone: "), (by_hand, proc.stdout)
    project.git("config", "core.hooksPath", str(apart.resolve() / SCAN.HOOKS_PATH), cwd=apart)
    proc = _session_start(Project(tmp_path / "apart-linked", project.cache, project.log), CLOUD)
    assert (proc.returncode, proc.stdout) == (0, ""), proc.stdout
    project.git("config", "core.hooksPath", f"~/apart/{SCAN.HOOKS_PATH}", cwd=apart)  # git expands a leading ~
    proc = _session_start(Project(tmp_path / "apart-linked", project.cache, project.log),
                          {**CLOUD, "HOME": str(tmp_path.resolve())})
    assert (proc.returncode, proc.stdout) == (0, ""), proc.stdout
    # set at the user's level it counts too; at one worktree's, or in the session's environment, it reaches no other
    project.git("config", "--unset", "core.hooksPath", cwd=apart)
    copy = str(apart.resolve() / SCAN.HOOKS_PATH)
    user = tmp_path / "user.gitconfig"
    user.write_text(f"[core]\n\thooksPath = {copy}\n", encoding="utf-8")
    linked = Project(tmp_path / "apart-linked", project.cache, project.log)
    proc = _session_start(linked, {**CLOUD, "GIT_CONFIG_GLOBAL": str(user)})
    assert (proc.returncode, proc.stdout) == (0, ""), proc.stdout
    project.git("config", "extensions.worktreeConfig", "true", cwd=apart)
    project.git("config", "--worktree", "core.hooksPath", copy, cwd=tmp_path / "apart-linked")
    proc = _session_start(linked, CLOUD)
    assert proc.stdout.startswith("the secret-scan pre-push hook may be off in this clone: "), proc.stdout
    project.git("config", "--worktree", "--unset", "core.hooksPath", cwd=tmp_path / "apart-linked")
    proc = _session_start(linked, {**CLOUD, "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.hooksPath",
                                   "GIT_CONFIG_VALUE_0": copy})
    assert proc.stdout.startswith("the secret-scan pre-push hook may be off in this clone: "), proc.stdout


def test_a_session_start_names_a_project_below_the_clone_s_top(project: Project, tmp_path: Path) -> None:
    # The project's .claude in a subdirectory of the clone: the main checkout's subdirectory, from a linked worktree too
    outer = tmp_path / "outer"
    shutil.copytree(project.root, outer / "app", symlinks=True, ignore=shutil.ignore_patterns(".git"))
    project.git("init", "-q", "-b", "main", cwd=outer)
    project.git("add", "-A", cwd=outer)
    project.git("commit", "-qm", "nested", cwd=outer)
    project.git("worktree", "add", "-q", "-b", "nested", str(tmp_path / "outer-linked"), cwd=outer)
    app = Project(outer / "app", project.cache, project.log)
    above = {**CLOUD, "GIT_CEILING_DIRECTORIES": str(tmp_path)}  # git looks above the project for the clone
    proc = _session_start(app, above, tmp_path / "outer-linked" / "app")
    assert (proc.returncode, proc.stdout) == (0, "") and _hooks_path(app) == _ours(app)
    project.git("config", "--unset", "core.hooksPath", cwd=outer)
    proc = _session_start(app, above)
    assert (proc.returncode, proc.stdout) == (0, "") and _hooks_path(app) == _ours(app)
    # the linked worktree's own copy, there too, is written as the main checkout's
    project.git("config", "core.hooksPath", str((tmp_path / "outer-linked" / "app").resolve() / SCAN.HOOKS_PATH),
                cwd=outer)
    proc = _session_start(app, above)
    assert (proc.returncode, proc.stdout) == (0, "") and _hooks_path(app) == _ours(app)
    # and a clone with no main checkout names the subdirectory in its command
    bare = tmp_path / "outer-bare.git"
    project.git("clone", "-q", "--bare", str(outer), str(bare))
    project.git("worktree", "add", "-q", "-b", "bare-nested", str(tmp_path / "bare-nested"), cwd=bare)
    nested = Project(tmp_path / "bare-nested" / "app", project.cache, project.log)
    proc = _session_start(nested, above)
    assert proc.stdout == (
        "the secret-scan pre-push hook may be off in this clone: this is a linked worktree of a clone with no main "
        f"checkout the hook can find above its git directory ({bare.resolve()}), so it sets no core.hooksPath. "
        "`git config core.hooksPath <checkout>/app/.claude/hooks/git`, naming by its absolute path a checkout of the "
        "clone that stays, turns it on for every worktree\n"), proc.stdout


def test_a_session_start_reads_a_hooks_path_that_is_no_utf_8(project: Project) -> None:
    with (project.root / ".git" / "config").open("ab") as config:
        config.write(b"[core]\n\thooksPath = /opt/hooks-\xff\n")
    proc = _session_start(project, CLOUD)
    assert proc.returncode == 0 and proc.stderr == "", proc.stderr
    assert f"{OFF}core.hooksPath is /opt/hooks-� at the local level, which this leaves as it is" in proc.stdout, \
        proc.stdout


def test_a_session_start_takes_no_name_that_is_no_utf_8_for_one_not_there(project: Project, tmp_path: Path) -> None:
    # another checkout's copy, there, whose name git reads as no UTF-8, is not taken for one that is not there
    other = os.fsencode(tmp_path) + b"/other-\xff/" + SCAN.HOOKS_PATH.encode()
    try:
        os.makedirs(other)
    except OSError as error:  # a file system that holds only UTF-8 names (APFS, HFS+) makes none
        pytest.skip(f"this file system makes no directory whose name is no UTF-8 ({error})")
    with (project.root / ".git" / "config").open("ab") as config:
        config.write(b"[core]\n\thooksPath = " + other + b"\n")
    proc = _session_start(project, CLOUD)
    assert ", which this leaves as it is. " in proc.stdout and "not there from here" not in proc.stdout, proc.stdout


def test_a_session_start_says_when_git_cannot_read_the_clone(project: Project) -> None:
    project.git("config", "core.repositoryformatversion", "99")  # a format this git does not know
    proc = _session_start(project, CLOUD)
    assert proc.returncode == 0
    assert proc.stdout.startswith(f"{OFF}git cannot read the clone (fatal: "), proc.stdout
    assert proc.stdout.endswith(f". {AGAIN}\n") and proc.stdout.count("\n") == 1, proc.stdout


def test_a_session_start_says_when_a_setting_above_the_clone_s_keeps_another_path(project: Project) -> None:
    # The session's environment, or the worktree's own configuration, keeps its relative path in effect over the
    # absolute one the start writes, and the note gives that level's commands
    command = {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.hooksPath", "GIT_CONFIG_VALUE_0": SCAN.HOOKS_PATH}
    proc = _session_start(project, {**CLOUD, **command})
    assert proc.returncode == 0 and _hooks_path(project) == _ours(project)
    assert proc.stdout == (f"{OFF}core.hooksPath is {SCAN.HOOKS_PATH} at the command level, which outranks the "
                           f"{_ours(project)} this set in the clone's own configuration. The session's environment "
                           "sets it (GIT_CONFIG_COUNT or GIT_CONFIG_PARAMETERS), which outranks the clone's "
                           f"configuration; without it, `git config core.hooksPath {_ours(project)}` turns it on\n"), \
        proc.stdout
    project.git("config", "--unset", "core.hooksPath")
    project.git("config", "extensions.worktreeConfig", "true")
    project.git("config", "--worktree", "core.hooksPath", SCAN.HOOKS_PATH)
    proc = _session_start(project, CLOUD)
    assert proc.returncode == 0 and _hooks_path(project) == _ours(project)
    assert proc.stdout == (f"{OFF}core.hooksPath is {SCAN.HOOKS_PATH} at the worktree level, which outranks the "
                           f"{_ours(project)} this set in the clone's own configuration. "
                           "`git config --worktree --unset core.hooksPath` and "
                           f"`git config core.hooksPath {_ours(project)}` turn it on, in place of {SCAN.HOOKS_PATH}\n"), \
        proc.stdout
    # The main checkout's path by its absolute path, spelled otherwise, names it wherever git runs hooks: on, at either
    # level, with the clone's own configuration holding it too
    link = project.root.parent / "hooks-link"
    link.symlink_to(_ours(project), target_is_directory=True)
    for spelling in (_ours(project) + "/", str(project.root.resolve() / "." / SCAN.HOOKS_PATH), str(link)):
        project.git("config", "--worktree", "core.hooksPath", spelling)
        project.git("config", "--unset", "core.hooksPath")
        proc = _session_start(project, CLOUD)
        assert (proc.returncode, proc.stdout) == (0, "") and _hooks_path(project) == _ours(project), spelling
        project.git("config", "--worktree", "--unset", "core.hooksPath")
        project.git("config", "--unset", "core.hooksPath")
        proc = _session_start(project, {**CLOUD, **command, "GIT_CONFIG_VALUE_0": spelling})
        assert (proc.returncode, proc.stdout) == (0, "") and _hooks_path(project) == _ours(project), spelling


def test_a_session_start_turns_the_hook_on_when_it_cannot_read_the_pin(project: Project) -> None:
    ci = project.root / ".github" / "workflows" / "ci.yml"
    ci.write_bytes(ci.read_bytes() + b"\n# \xff\n")
    proc = _session_start(project, CLOUD)
    assert proc.returncode == 0 and _hooks_path(project) == _ours(project)  # on, whatever the pin
    assert proc.stdout.startswith("each push that adds commits is refused until this is fixed: the hooks cannot "
                                  "check their gitleaks (UnicodeDecodeError: "), proc.stdout


def test_a_session_start_turns_the_hook_on_where_git_keeps_no_hooks_directory(project: Project) -> None:
    project.remote()
    shutil.rmtree(project.root / ".git" / "hooks")  # a clone made without git's templates
    proc = _session_start(project, CLOUD)
    assert (proc.returncode, proc.stdout, proc.stderr) == (0, "", "") and _hooks_path(project) == _ours(project)
    _stopped(project.push("git push origin work"), project)


def test_a_session_start_says_when_git_cannot_set_the_hooks_path(project: Project) -> None:
    (project.root / ".git" / "config.lock").write_text("", encoding="utf-8")  # another git writing the configuration
    proc = _session_start(project, CLOUD)
    assert proc.returncode == 0 and _hooks_path(project) is None
    assert proc.stdout.startswith(f"{OFF}git could not set core.hooksPath (error: could not lock config file "), \
        proc.stdout
    assert proc.stdout.endswith(f". {AGAIN}\n") and proc.stdout.count("\n") == 1, proc.stdout


def test_a_session_start_that_fails_says_why_and_the_session_starts(project: Project, tmp_path: Path) -> None:
    path = tmp_path / "bin"  # a PATH that holds no git
    path.mkdir()
    for name, target in (("sh", shutil.which("sh")), ("python3", os.path.realpath(sys.executable))):
        (path / name).symlink_to(target)
    linked = project.root.parent / "linked"
    project.git("worktree", "add", "-q", "-b", "linked", str(linked), "clean")
    for root in (project.root, linked):  # its command names no worktree's own path, which a linked one's would be
        proc = _session_start(project, {**CLOUD, "PATH": str(path)}, root)
        assert proc.returncode == 0 and _hooks_path(project) is None
        assert proc.stdout.startswith(f"{OFF}setting it failed (FileNotFoundError: "), proc.stdout
        assert proc.stdout.endswith(f". {AGAIN}\n") and proc.stdout.count("\n") == 1, proc.stdout


@pytest.mark.parametrize("call", ["*--show-toplevel*", '*--show-toplevel*) sleep 6;; *" version"'])
def test_a_session_start_ends_in_its_time_when_git_hangs(project: Project, tmp_path: Path, call: str) -> None:
    hangs = _git_wrapper(tmp_path / "bin", f'case "$*" in {call}) exec sleep 60;; esac\nexec "$REAL" "$@"')
    proc = _session_start(project, {**CLOUD, **hangs})  # within the time the registration allows, or this raises
    assert proc.returncode == 0 and _hooks_path(project) is None
    assert proc.stdout.startswith(f"{OFF}setting it failed (TimeoutExpired: "), proc.stdout


def test_a_session_start_s_git_calls_share_one_budget(project: Project, tmp_path: Path) -> None:
    # Three seconds a call: each inside 8, but all of them past the 10 the registration allows
    slow = _git_wrapper(tmp_path / "bin", 'sleep 3\nexec "$REAL" "$@"')
    proc = _session_start(project, {**CLOUD, **slow})  # within the time the registration allows, or this raises
    assert proc.returncode == 0 and _hooks_path(project) is None
    assert proc.stdout.startswith(f"{OFF}setting it failed (TimeoutExpired: "), proc.stdout


def test_a_session_start_says_when_git_names_no_git_directory(project: Project, tmp_path: Path) -> None:
    mute = _git_wrapper(tmp_path / "bin", 'case "$*" in *--git-common-dir*) exit 0;; esac\nexec "$REAL" "$@"')
    proc = _session_start(project, {**CLOUD, **mute})
    assert proc.returncode == 0 and _hooks_path(project) is None
    assert proc.stdout.startswith(f"{OFF}git cannot read the clone's git directory. {AGAIN}\n"), proc.stdout


def test_a_session_start_says_when_the_pinned_binary_is_missing(project: Project) -> None:
    project.binary().unlink()
    proc = _session_start(project, CLOUD)
    assert proc.returncode == 0 and _hooks_path(project) == _ours(project)  # the hook is on all the same
    assert proc.stdout.startswith("each push that adds commits is refused until this is fixed: gitleaks "), proc.stdout
    assert "is not installed" in proc.stdout and "--install" in proc.stdout, proc.stdout


def test_a_session_start_quotes_the_path_its_commands_name(project: Project, tmp_path: Path) -> None:
    spaced = Project(tmp_path / "my project", project.cache, project.log)
    project.git("clone", "-q", str(project.root), str(spaced.root))
    spaced.git("config", "core.hooksPath", ".husky")
    proc = _session_start(spaced, CLOUD)
    quoted = shlex.quote(_ours(spaced))
    assert quoted.startswith("'") and f"`git config core.hooksPath {quoted}` turns it on, in place" in proc.stdout, \
        proc.stdout
    spaced.git("config", "--unset", "core.hooksPath")
    proc = _session_start(spaced, {**CLOUD, "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.hooksPath",
                                   "GIT_CONFIG_VALUE_0": ".husky"})
    assert f"; without it, `git config core.hooksPath {quoted}` turns it on" in proc.stdout, proc.stdout
    spaced.git("config", "extensions.worktreeConfig", "true")
    spaced.git("config", "--worktree", "core.hooksPath", ".husky")
    proc = _session_start(spaced, CLOUD)
    assert f" and `git config core.hooksPath {quoted}` turn it on, in place of .husky" in proc.stdout, proc.stdout
    spaced.git("config", "--worktree", "core.hooksPath", SCAN.HOOKS_PATH)  # above the path the start writes
    proc = _session_start(spaced, CLOUD)
    assert f"which outranks the {_ours(spaced)} this set" in proc.stdout and \
        f" and `git config core.hooksPath {quoted}` turn it on, in place of {SCAN.HOOKS_PATH}" in proc.stdout, proc.stdout
    spaced.git("config", "--worktree", "--unset", "core.hooksPath")
    spaced.git("config", "--unset", "core.hooksPath")
    stub = project.binary().read_bytes()
    project.binary().unlink()  # the binary note's --install too
    proc = _session_start(spaced, CLOUD)
    guard = shlex.quote(str(spaced.root.resolve() / ".claude" / "hooks" / "secret_scan_guard.py"))
    assert f"Install it once with `python3 {guard} --install`" in proc.stdout, proc.stdout
    project.binary().write_bytes(stub)
    project.binary().chmod(0o755)
    spaced.git("config", "--unset", "core.hooksPath")
    own = spaced.root / ".git" / "hooks" / "pre-commit"
    own.write_text("#!/bin/sh\n", encoding="utf-8")
    own.chmod(0o755)
    proc = _session_start(spaced, CLOUD)
    assert f"`git config core.hooksPath {quoted}` turns it on, and git then runs none" in proc.stdout, proc.stdout


def test_a_session_start_outside_a_repository_does_nothing(tmp_path: Path) -> None:
    proc = _session_start(_plain(tmp_path), CLOUD)
    assert (proc.returncode, proc.stdout) == (0, "")


def test_a_session_start_reads_git_in_english_whatever_the_session_s_language(tmp_path: Path) -> None:
    # git in the session's language: the start reads "not a git repository" in git's own words
    translated = _git_wrapper(tmp_path / "bin", '[ "${LC_ALL-}" = C ] && exec "$REAL" "$@"\n'
                              'err=$(mktemp) || exit 1\nLC_ALL=C "$REAL" "$@" 2>"$err"; code=$?\n'
                              'sed "s/not a git repository/kein Git-Repository/" "$err" >&2; rm -f "$err"; exit $code')
    german = {**translated, "LC_ALL": "de_DE.UTF-8", "LANGUAGE": "de"}
    plain = _plain(tmp_path)
    shown = subprocess.run(["git", "-C", str(plain.root), "rev-parse"], capture_output=True, text=True,
                           env=_start_env(plain, german, plain.root))
    assert "kein Git-Repository" in shown.stderr, shown.stderr  # the stand-in git does speak German
    proc = _session_start(plain, {**CLOUD, **german})
    assert (proc.returncode, proc.stdout) == (0, "")


def test_turn_on_turns_the_hook_on_in_any_clone_and_says_so(project: Project) -> None:
    project.remote()
    on = f"the secret-scan pre-push hook is on in this clone: core.hooksPath names {_ours(project)}\n"
    proc = _turned_on(project)  # a person's clone: no cloud session
    assert (proc.returncode, proc.stdout, proc.stderr) == (0, on, "") and _hooks_path(project) == _ours(project)
    _stopped(project.push("git push origin work"), project)
    again = _turned_on(project)
    assert (again.returncode, again.stdout) == (0, on)
    linked = project.root.parent / "linked"
    project.git("worktree", "add", "-q", "-b", "linked", str(linked), "clean")
    project.git("config", "--unset", "core.hooksPath")
    proc = _turned_on(project, root=linked)  # from a linked worktree, the main checkout's path
    assert (proc.returncode, proc.stdout) == (0, on) and _hooks_path(project) == _ours(project)


def test_turn_on_says_why_the_hook_is_not_on_and_exits_1(project: Project, tmp_path: Path) -> None:
    own = project.root / ".git" / "hooks" / "pre-commit"
    own.write_text("#!/bin/sh\n", encoding="utf-8")
    own.chmod(0o755)
    proc = _turned_on(project)
    assert proc.returncode == 1 and _hooks_path(project) is None
    assert proc.stdout.startswith(f"{OFF}it has hooks of its own in "), proc.stdout
    own.unlink()
    project.binary().unlink()
    proc = _turned_on(project)  # set, though each push that adds commits is refused until --install
    assert proc.returncode == 1 and _hooks_path(project) == _ours(project)
    assert proc.stdout.startswith("each push that adds commits is refused until this is fixed: gitleaks "), proc.stdout
    proc = _turned_on(_plain(tmp_path))
    assert (proc.returncode, proc.stdout) == (1, "the secret-scan pre-push hook is off: this file is in no git "
                                                 "repository\n")


def _gone_note(configured: str, project: Project, scope: str = "local") -> str:
    """The note for a hooks path to a .claude/hooks/git that is not there from here, which the start leaves as it is."""
    fix = (f"`git config --worktree --unset core.hooksPath` and `git config core.hooksPath {_ours(project)}` turn it on"
           if scope == "worktree" else f"`git config core.hooksPath {_ours(project)}` turns it on")
    return (f"{OFF}core.hooksPath is {configured} at the {scope} level, which is not there from here: a moved clone's "
            "old path, a removed worktree's, or one that another machine, or a container reading this clone at another "
            f"path, runs, whose pushes would run no hook were it replaced. This leaves it as it is. {fix}, in place of "
            f"{configured}\n")


def test_turn_on_names_a_moved_clone_s_old_path_and_leaves_it(project: Project, tmp_path: Path) -> None:
    # The old path is not there from here, but another view of the clone (a container's, another machine's) may read
    # it: --turn-on and a cloud session's start leave it, and give the command that names this one
    project.remote()
    assert _turned_on(project).returncode == 0
    moved = Project(tmp_path / "moved", project.cache, project.log)
    moved.leak = project.leak
    project.root.rename(moved.root)
    stale = _hooks_path(moved)
    assert stale == _ours(project) and stale != _ours(moved)
    proc = _turned_on(moved)
    assert (proc.returncode, proc.stdout) == (1, _gone_note(stale, moved)) and _hooks_path(moved) == stale
    proc = _session_start(moved, CLOUD)
    assert (proc.returncode, proc.stdout) == (0, _gone_note(stale, moved)) and _hooks_path(moved) == stale
    # at a worktree's level, or the user's, the same note, with that level's commands
    moved.git("config", "--unset", "core.hooksPath")
    moved.git("config", "extensions.worktreeConfig", "true")
    moved.git("config", "--worktree", "core.hooksPath", stale)
    proc = _session_start(moved, CLOUD)
    assert (proc.returncode, proc.stdout) == (0, _gone_note(stale, moved, "worktree")) and _hooks_path(moved) is None
    moved.git("config", "--worktree", "--unset", "core.hooksPath")
    moved.git("config", "--unset", "extensions.worktreeConfig")
    user = tmp_path / "user.gitconfig"
    user.write_text(f"[core]\n\thooksPath = {stale}\n", encoding="utf-8")
    proc = _session_start(moved, {**CLOUD, "GIT_CONFIG_GLOBAL": str(user)})
    assert (proc.returncode, proc.stdout) == (0, _gone_note(stale, moved, "global")) and _hooks_path(moved) is None
    moved.git("config", "core.hooksPath", _ours(moved))  # the note's command
    proc = _turned_on(moved)
    assert (proc.returncode, proc.stdout) == (0, "the secret-scan pre-push hook is on in this clone: core.hooksPath "
                                                 f"names {_ours(moved)}\n")
    _stopped(moved.push("git push origin work"), moved)
    # any .claude/hooks/git that is not there, a removed worktree's among them, gets the same note
    removed = str(tmp_path / "removed" / SCAN.HOOKS_PATH)
    moved.git("config", "core.hooksPath", removed)
    proc = _session_start(moved, CLOUD)
    assert (proc.returncode, proc.stdout) == (0, _gone_note(removed, moved)) and _hooks_path(moved) == removed
    # and a worktree's own copy where git still lists the worktree, removed without its knowing, as it lists another
    # view's at the path that view made it at
    worn = tmp_path / "worn"
    moved.git("worktree", "add", "-q", "-b", "worn", str(worn), "clean")
    copy = str(worn.resolve() / SCAN.HOOKS_PATH)
    moved.git("config", "core.hooksPath", copy)
    shutil.rmtree(worn)
    proc = _session_start(moved, CLOUD)
    assert (proc.returncode, proc.stdout) == (0, _gone_note(copy, moved)) and _hooks_path(moved) == copy
    moved.git("worktree", "prune")
    moved.git("config", "core.hooksPath", _ours(moved))
    # A linked worktree outside the moved clone names its old git directory: git cannot read it, and the note says so
    linked = tmp_path / "linked"
    moved.git("worktree", "add", "-q", "-b", "linked", str(linked), "clean")
    moved.git("config", "core.hooksPath", removed)  # before the move, from the linked worktree: the same note
    proc = _session_start(moved, CLOUD, linked)
    assert (proc.returncode, proc.stdout) == (0, _gone_note(removed, moved)) and _hooks_path(moved) == removed
    moved.git("config", "core.hooksPath", _ours(moved))
    again = Project(tmp_path / "again", project.cache, project.log)
    moved.root.rename(again.root)
    proc = _turned_on(again, root=linked)
    assert proc.returncode == 1 and proc.stdout.startswith(f"{OFF}git cannot read the clone (fatal: not a git "
                                                           "repository: "), proc.stdout
    proc = _session_start(again, CLOUD, linked)
    assert proc.returncode == 0 and proc.stdout.startswith(f"{OFF}git cannot read the clone (fatal: "), proc.stdout


def test_turn_on_writes_the_clone_s_own_where_a_level_above_it_names_the_hook(project: Project) -> None:
    # A worktree's own setting, or the session's environment's, reaches no other worktree or session: the clone's own
    # configuration holds the path too, so a push from the main checkout runs the hook
    project.remote()
    linked = project.root.parent / "linked"
    project.git("worktree", "add", "-q", "-b", "linked", str(linked), "clean")
    project.git("config", "extensions.worktreeConfig", "true")
    project.git("config", "--worktree", "core.hooksPath", _ours(project), cwd=linked)
    proc = _turned_on(project, root=linked)
    assert (proc.returncode, proc.stdout) == (0, "the secret-scan pre-push hook is on in this clone: core.hooksPath names "
                                                 f"{_ours(project)}\n") and _hooks_path(project) == _ours(project)
    _stopped(project.push("git push origin work"), project)
    project.git("config", "--unset", "core.hooksPath")
    command = {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.hooksPath", "GIT_CONFIG_VALUE_0": _ours(project)}
    proc = _session_start(project, {**CLOUD, **command})
    assert (proc.returncode, proc.stdout) == (0, "") and _hooks_path(project) == _ours(project)
    project.git("config", "--unset", "core.hooksPath")  # the user's level reaches every clone, and leaves this one's
    user = project.root.parent / "user.gitconfig"
    user.write_text(f"[core]\n\thooksPath = {_ours(project)}\n", encoding="utf-8")
    proc = _session_start(project, {**CLOUD, "GIT_CONFIG_GLOBAL": str(user)})
    assert (proc.returncode, proc.stdout) == (0, "") and _hooks_path(project) == _ours(project)


def test_turn_on_gives_a_slow_git_longer_than_a_session_s_start(project: Project, tmp_path: Path) -> None:
    # Run by hand, --turn-on has no 10-second limit to end within: a git call slower than the start's 8 seconds ends
    slow = _git_wrapper(tmp_path / "bin", 'case "$*" in *--git-common-dir*) sleep 9;; esac\nexec "$REAL" "$@"')
    proc = _turned_on(project, slow)
    assert (proc.returncode, proc.stdout) == (0, "the secret-scan pre-push hook is on in this clone: core.hooksPath names "
                                                 f"{_ours(project)}\n"), proc.stdout


@pytest.mark.parametrize("version", ["git version 2.42.0", "git version 2.39.5 (Apple Git-154)",
                                     "git version 2.30.2"])
def test_turn_on_sets_nothing_on_a_git_too_old_to_scan(project: Project, tmp_path: Path, version: str) -> None:
    # git's hook would refuse every push that adds commits, and a git before 2.31 reads no --path-format
    env = _old_git(tmp_path, version)
    note = ("the secret-scan pre-push hook cannot scan with this machine's git, so this leaves core.hooksPath as it "
            f"is: this machine's git ({version}) is older than 2.43: ")
    proc = _turned_on(project, env)
    assert proc.returncode == 1 and _hooks_path(project) is None
    assert proc.stdout.startswith(note) and proc.stdout.count("\n") == 1, proc.stdout
    proc = _session_start(project, {**CLOUD, **env})
    assert proc.returncode == 0 and _hooks_path(project) is None
    assert proc.stdout.startswith(note) and proc.stdout.count("\n") == 1, proc.stdout


def test_session_start_is_registered() -> None:
    assert _session_registered() == [{"hooks": [{"type": "command", "command": SESSION_COMMAND, "timeout": 10}]}]
    # its git calls end with time left to start Python before them and to print the note after
    [hook] = [hook for entry in _session_registered() for hook in entry["hooks"]]
    assert SCAN.TURN_ON <= hook["timeout"] - 2
    assert SCAN.TURN_ON_BY_HAND >= 60  # --turn-on, run by hand, waits for a slow git as the records say


# --- the registration ----------------------------------------------------------------------------------------

def test_the_hook_is_registered_before_bash_and_every_github_tool() -> None:
    assert _registered() == [{"matcher": MATCHER, "hooks": [{"type": "command", "command": COMMAND, "timeout": 60}]}]
    assert HOOK.is_file()
    assert "disableAllHooks" not in json.loads(SETTINGS.read_text(encoding="utf-8"))
    # Claude Code tests the matcher as an unanchored JavaScript RegExp, which Python's re.search reads the same
    # way for this pattern (test_codex_mention_guard.py's registration test names the live checks).
    matcher = re.compile(MATCHER)
    reached = ("Bash", "mcp__github__push_files", "mcp__github__create_or_update_file",
               "mcp__plugin_gh_github__push_files", "mcp__GitHub__create_or_update_file", "mcp__claude_ai_GitHub__push_files")
    assert [tool for tool in reached if not matcher.search(tool)] == []
    assert [tool for tool in ("Edit", "Write", "BashOutput", "mcp__Claude_Docs__update") if matcher.search(tool)] == []
