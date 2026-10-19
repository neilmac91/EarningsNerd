"""Gate for `.claude/hooks/secret_scan_guard.py`, the PreToolUse hook that runs CI's pinned gitleaks over what a
push or a GitHub content write would add, and refuses the call on a finding (E126;
lessons/ops-a-secret-shaped-literal-on-any-branch-fails-every-pr.md).

A case runs the hook the way `.claude/settings.json` registers it (the registered command, through the shell, on
the event Claude Code sends) in a scratch project, except the ones on the deadline, an unexpected error, a
recursion, the downloads and the installer, which call its functions in this process. The project is a git
repository holding copies of both hooks and CI's workflow, whose `refs/remotes/origin/main` stands for GitHub's
main, with a branch `work` that carries one commit holding a planted credential-shaped line and a branch `clean`
with one clean commit, neither on GitHub, and beside it a second repository, `elsewhere`, whose own `work` is
clean: a case that moves into the project from there is refused only if the hook follows the move. Each test
process builds the project once and each case runs in a copy. No case reads the machine's own git configuration,
attributes or ignores.

A stub gitleaks, installed where `--install` puts the pinned binary, reads what gitleaks reads (`git log -p -U0`
over --log-opts in the directory it scans, the -i file, and that directory's own .gitleaksignore and
.gitleaks.toml, or the rules GITLEAKS_CONFIG or GITLEAKS_CONFIG_TOML name), honours `gitleaks:allow`, and flags the
planted value, which this file builds at run time so its own text matches no rule. It reads git's plain output
more strictly than gitleaks: a line it cannot place under a full commit header and a `b/` path (colour, another
format, an abbreviated commit, decorations, no prefixes) shows it nothing, where gitleaks still reports the line
under all of them but colour, and under a commit main's pins do not match when the commit is abbreviated or
missing. Each setting the hook holds that can hide a line from the
stub (colour, the big-file threshold, a root commit's lines, an attributes file, copies, a replace ref, the
commit header, decorations, prefixes) or fail the scan (a signature, the graft hint) is planted in the
repository itself, where only the pin keeps the case passing; the rest keep CI's hunks, dates, paths and
encoding and are not. With the pinned binary installed (`--install`), the cases that turn on how gitleaks reads
its files and git's output run against it as well; CI installs none and skips them.

Planted below: the forms a push takes; the pushes the hook must read precisely, which name the clean branch from
the planted one, so a push read whole would be refused; the commands that may and may not come before a push or
run beside it, redirections among them; the moves of the shell's directory it follows, and the ones bash does not
keep; the settings and refs that would blind the scan; the API writes; the MCP writes; and the look-alikes that
must pass. Each gap the hook's header names that a case can stand for is planted as one that passes through, with
the files its command names, so closing it is a deliberate change here; a GIT_DIR, HOME or CDPATH the shell's
profile sets, a push a person or a session that loads no repository hooks makes, and an MCP server named without
"github" are outside what a case here can run.
"""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import random
import re
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


def _load():
    spec = importlib.util.spec_from_file_location("secret_scan_guard", HOOK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SCAN = _load()
VERSION, SHA256 = SCAN._pin()
TARGET = SCAN._platform()


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
pins, ignore = set(), options.get("--gitleaks-ignore-path", ".")
for path in (ignore, os.path.join(ignore, ".gitleaksignore"), os.path.join(source, ".gitleaksignore")):
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as handle:
            pins.update(line.strip() for line in handle if line.strip() and not line.startswith("#"))
# The rules: --config, else GITLEAKS_CONFIG's file, else GITLEAKS_CONFIG_TOML's text, else the directory's own.
config = options.get("--config") or os.environ.get("GITLEAKS_CONFIG")
rules = "" if config else os.environ.get("GITLEAKS_CONFIG_TOML", "")
config = config or ("" if rules else os.path.join(source, ".gitleaks.toml"))
if config and os.path.isfile(config):
    rules = open(config, encoding="utf-8").read()
allow_all = "STUB-ALLOW-ALL" in rules
log = subprocess.run(["git", "-C", source, "log", "-p", "-U0", *options["--log-opts"].split(" ")], capture_output=True, text=True)
if log.returncode or log.stderr:  # anything git says on its stderr fails gitleaks' scan
    print(log.stderr, file=sys.stderr)
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


def _plain_env() -> dict[str, str]:
    """The test's environment without GIT_* (a git hook running pytest sets GIT_DIR) or GITLEAKS_*, and with no
    system or global git configuration, attributes or ignores: the machine's own (a signing key, colours,
    aliases, a global `*.py` ignore) is no case's."""
    env = {key: value for key, value in os.environ.items() if not key.startswith(("GIT_", "GITLEAKS_"))}
    return {**env, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "XDG_CONFIG_HOME": os.devnull}


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


def _event(tool: str, tool_input: object, cwd: Path) -> dict:
    return {"session_id": "s", "transcript_path": "/dev/null", "cwd": str(cwd), "permission_mode": "default",
            "hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input, "tool_use_id": "toolu_1"}


def _make(tmp_path: Path, binary: str = "stub") -> Project:
    """A scratch project built from nothing (the `project` fixture copies one this process built once)."""
    root = tmp_path / "project"
    for source, folder in ((HOOK, ".claude/hooks"), (GUARD, ".claude/hooks"), (CI, ".github/workflows")):
        (root / folder).mkdir(parents=True, exist_ok=True)
        shutil.copy(source, root / folder)
    project = Project(root, tmp_path / "cache", tmp_path / "stub.log")
    project.git("init", "-q", "-b", "main")
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
    "words a command holding git adds": ("echo work | parallel git push origin", [["checkout", "-q", "clean"]]),
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
    "a while loop": ("while true; do git push origin work && break; done", []),
    "in the background": ("git push origin work &", []),
    "a pipeline's second command": ("echo x | git push origin work", []),
    "timeout": ("timeout 60 git push", []),
    "env and an assignment": ("env GIT_TRACE=0 git push", []),
    "nice and its value": ("nice -n 5 git push", []),
    "a command whose own name is not known": ("watch -n 5 git push", []),
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
    "a GIT_DIR before the command": "GIT_DIR=@REPO@/.git git push origin work",
    "an exported GIT_DIR": "export GIT_DIR=@REPO@/.git; git push origin work",
    "sh -lc": "sh -lc 'cd @REPO@ && git push'",
    "env -C": "env -C @REPO@ git push origin work",
    "env --chdir=": "env --chdir=@REPO@ git push origin work",
    "a trap, in the directory its shell ends in": "trap 'git push origin work' EXIT; cd @REPO@",
    "a subshell's trap, where the subshell ends": "(trap 'git push origin work' EXIT; cd @REPO@)",
    "an eval's trap, the shell's around it": "eval \"trap 'git push origin work' EXIT\"; cd @REPO@",
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
}
# Pushes from the project that run in `elsewhere`, whose commits are clean: they pass, scanned there.
MOVED_AWAY = {
    "-C": "git -C @ELSEWHERE@ push origin work",
    "cd": "cd @ELSEWHERE@ && git push origin work",
    "env -C": "env -C @ELSEWHERE@ git push origin work",
    "pushd": "pushd @ELSEWHERE@ && git push origin work",
    "popd -n after pushd, which keeps the directory": "pushd @ELSEWHERE@ && popd -n && git push origin work",
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
}
# Commands that may come before a push, or beside it: read-only or index-only git commands, cd and plain
# builtins; the push of `clean` passes.
BEFORE_ALLOWED = {
    "cd": "cd @REPO@ && git push",
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
    "a directory that is no repository": "git -C /tmp push",
    "a push of nothing new": "git push origin main:refs/heads/copy",
    "a function that pushes, never called": "f() { git push origin work; }",
    "a function named git, which the shell runs instead": "git() { echo no; }; git push origin work",
}
# Pushes the shell never runs that the hook reads anyway, and refuses.
OVER_READ = {
    "a source no ref names, read as every branch": "git push origin no-such-branch",
    "an echo of a push": "echo git push",
    "a git command the hook does not know, named like push": "git push-notes",
    "a `$` in a quoted word, read as a word the shell expands": "git push -o 'note=$5' origin clean",
}
# Read as a command that may move a commit, and so refused before a push: the shell runs none.
OVER_READ_ORDER = {
    "arithmetic": "((n = 1)); git push",
}
# A directory the hook cannot name: refused, whatever the commits hold.
UNNAMED = {
    "a variable": 'cd "$REPO" && git push',
    "a substitution": "cd $(git rev-parse --show-toplevel) && git push",
    "-C and a variable": 'git -C "$REPO" push',
    "a directory that does not exist yet": "cd /does/not/exist && git push",
    "a GIT_DIR from a variable": "GIT_DIR=$X git push",
    "cd - with no directory before": "cd - && git push",
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
# The stated gaps, which pass through with the planted line on `work`.
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
    "a command substitution in an unquoted here-document's text": "cat <<EOF\n$(git push origin work)\nEOF",
    "a `$((` that bash reads as a command substitution": "echo $((git push origin work) )",
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
    reason = project.bash(command, env={"REPO": str(project.root)})
    assert reason is not None and "directory the hook cannot name" in reason


@pytest.mark.parametrize(("command", "what"), OUTRIGHT.values(), ids=OUTRIGHT.keys())
def test_writes_the_hook_cannot_read_first_are_refused_outright(project: Project, command: str, what: str) -> None:
    project.git("checkout", "-q", "clean")
    reason = project.bash(command)
    assert reason is not None and what in reason, reason


@pytest.mark.parametrize("command", API_PASSES.values(), ids=API_PASSES.keys())
def test_api_calls_that_add_no_content_go_through(project: Project, command: str) -> None:
    assert project.bash(command) is None


# The files a stated gap's command names, so that closing the gap turns its case.
GAP_FILES = {
    "a push a script runs": {"push.sh": "#!/bin/sh\ngit push origin work\n"},
    "a GraphQL mutation from standard input": {"m.graphql": MUTATION},
}


@pytest.mark.parametrize(("name", "command"), GAPS.items(), ids=GAPS.keys())
def test_the_stated_gaps_pass_through(project: Project, name: str, command: str) -> None:
    project.write(GAP_FILES.get(name, {}))
    assert project.bash(command) is None


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


# --- what would blind the scan -------------------------------------------------------------------------------

# Settings that change what `git log -p` prints: (where it is set, name, value). Colour and the big-file threshold
# hide the planted line from gitleaks; an abbreviated commit and another format leave it a finding whose commit
# main's pins do not match; decorations and no prefixes gitleaks reads past. The stub, stricter, reads nothing
# under any of them, so each case turns it blind unless the hook holds the setting at git's default.
BLINDERS = {
    "colour, in the repository": ("repository", "color.ui", "always"),
    "colour, in the global file": ("global", "color.ui", "always"),
    "diff colour": ("repository", "color.diff", "always"),
    "an abbreviated commit header": ("repository", "log.abbrevCommit", "true"),
    "a one-line format": ("repository", "format.pretty", "oneline"),
    "decorations": ("repository", "log.decorate", "full"),
    "no prefixes": ("repository", "diff.noprefix", "true"),
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
    # log.showSignature=true makes git log check each signature; one it cannot check fails gitleaks' scan.
    _sign(project, "clean")
    _sign(project, "work")
    project.git("config", "log.showSignature", "true")
    _found(project.bash("git push origin work"))
    assert project.bash("git push origin clean") is None
    assert len(project.scans()) == 2


@pytest.mark.parametrize("scope", ["global", "repository", "git's default file"])
def test_an_attributes_file_that_marks_the_file_binary_does_not_count(project: Project, tmp_path: Path,
                                                                      scope: str) -> None:
    # The global config naming one never reaches the scan's git; the repository's naming one, and the file git
    # reads when none is named ($XDG_CONFIG_HOME/git/attributes), are held off by the pin of core.attributesFile.
    attributes = tmp_path / "xdg" / "git" / "attributes"
    attributes.parent.mkdir(parents=True)
    attributes.write_text("*.py -diff\n", encoding="utf-8")
    env = None
    if scope == "repository":
        project.git("config", "core.attributesFile", str(attributes))
    elif scope == "global":
        env = _global(tmp_path, f"[core]\n\tattributesFile = {attributes}\n")
    else:
        env = {"XDG_CONFIG_HOME": str(tmp_path / "xdg")}
    _found(project.bash("git push origin work", env=env))


def test_a_graft_file_fails_the_scan_closed_whatever_the_repository_says_of_its_hint(project: Project) -> None:
    # A graft gives the planted commit the parent GitHub has with the same tree, so `git log -p` would show it
    # adding nothing; git's hint about the graft file, held on, fails the scan rather than let it read that.
    twin = project.git("commit-tree", project.git("rev-parse", "work^{tree}"), "-p", "main", "-m", "twin")
    project.git("update-ref", "refs/remotes/origin/twin", twin)
    (project.root / ".git" / "info").mkdir(exist_ok=True)
    (project.root / ".git" / "info" / "grafts").write_text(f"{project.leak} {twin}\n", encoding="utf-8")
    project.git("config", "advice.graftFileDeprecated", "false")
    reason = project.bash("git push origin work")
    assert reason is not None and "gitleaks failed" in reason, reason


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
    assert "No main branch is fetched" in reason


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
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
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
