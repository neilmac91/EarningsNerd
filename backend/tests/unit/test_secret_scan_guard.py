"""Gate for `.claude/hooks/secret_scan_guard.py` and `secret_scan_setup.py` (E126;
lessons/ops-a-secret-shaped-literal-on-any-branch-fails-every-pr.md): a session's push, and a GitHub write that
commits without one, is scanned with the pinned gitleaks before it runs and refused on a finding.

Each guard case runs the hook the way `.claude/settings.json` registers it: the registered command, through the shell,
with CLAUDE_PROJECT_DIR set, on the event Claude Code sends. A refusal is a JSON deny on stdout with exit 0; a call let
through exits 0 with no output. The network gate keeps the real gitleaks out of reach, so a stub stands where the
setup provisions the binary, under a HOME of the test's own, with its SHA-256 recorded beside it as the setup records
it. The stub reads what it is asked to scan as gitleaks 8.24.3 does (`git -C <source> log -p -U0` over the range, in
the environment the hook gives it; every file under a directory, named as the walk from the source as given names it),
takes its ignore files, its config and inline allows where and as gitleaks takes them, computes fingerprints as
gitleaks does, logs each call with the pins, config and environment it read, and reports a finding, in gitleaks' JSON
report, for each added line holding a planted marker. Throwaway repositories with fake remote-tracking refs pin the
range, and a commit moved onto origin/main stands for a pin or a config that landed on main; a write's scan reads the
main of a copy of the hooks in a project of the case's own. The registration is pinned too: the guard beside
codex_mention_guard.py, before Bash and every GitHub MCP server, within 10 seconds, and the setup as a SessionStart
hook. The setup's own logic runs in-process with a fake download, and its failure path through the registered command
with the proxy pointed at a closed loopback port.
"""
from __future__ import annotations

import base64
import hashlib
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SETTINGS = ROOT / ".claude" / "settings.json"
GUARD = ROOT / ".claude" / "hooks" / "secret_scan_guard.py"
SETUP = ROOT / ".claude" / "hooks" / "secret_scan_setup.py"
CI = ROOT / ".github" / "workflows" / "ci.yml"
COMMAND = 'python3 -I -S "$CLAUDE_PROJECT_DIR/.claude/hooks/secret_scan_guard.py" || exit 1'
SETUP_COMMAND = 'python3 -I -S "$CLAUDE_PROJECT_DIR/.claude/hooks/secret_scan_setup.py" || exit 1'
FLAGS = ["--redact=100", "--no-banner", "--exit-code", "1"]  # the secret-scan job's
# Ahead of every commit scan's range, against the config CI lacks.
LOG_OPTIONS = ("--no-color --no-textconv --no-ext-diff --root --pretty=medium --date=default --no-abbrev-commit "
               "--no-show-signature --src-prefix=a/ --dst-prefix=b/")
LESSON = "lessons/ops-a-secret-shaped-literal-on-any-branch-fails-every-pr.md"
# What the stub reports, standing in for a secret: no file in this repository may carry a real one.
MARKER = "planted-leak-marker"
LEAKY = f"TOKEN = '{MARKER}'\n"
MAIN = "refs/remotes/origin/main"
GIT_ENV = {
    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.com",
}
STUB = '''#!/usr/bin/env python3
\"\"\"A stand-in for gitleaks 8.24.3: it logs each call and reports every added line holding a flagged word, reading the
ignore files, the config and inline allows as gitleaks does. Ignores: -i (a file, or a directory holding
.gitleaksignore; the working directory by default) and the source's own .gitleaksignore. A finding's fingerprint is
`<commit>:<file>:<rule>:<line>` in a commit scan and `<file>:<rule>:<line>` in a directory scan, a file named as the
walk from the source as given names it (relative for `.`); a pin of either, or of `<file>:<rule>:<line>` for a commit's
finding, drops it. Config: -c, else the file GITLEAKS_CONFIG names, else GITLEAKS_CONFIG_TOML's text, else the
source's .gitleaks.toml, else gitleaks' own default (logged as null). A config line `# stub: allow everything` stands
for an allowlist that drops every finding, and `# stub: also flag <word>` for a rule of the config's own; a line holding
gitleaks:allow is no finding, unless --ignore-gitleaks-allow is given.\"\"\"
import json
import os
import re
import subprocess
import sys
from pathlib import Path

args = sys.argv[1:]


def option(name):
    return args[args.index(name) + 1] if name in args else None


source, given = Path(args[1]), Path(option("-i") or ".")
ignores = set()
for path in (given, given / ".gitleaksignore", source / ".gitleaksignore"):
    if path.is_file():
        ignores |= {line.strip() for line in path.read_text().splitlines() if line.strip() and line[0] != "#"}
if option("-c"):
    config = Path(option("-c")).read_text()
elif os.environ.get("GITLEAKS_CONFIG"):
    config = Path(os.environ["GITLEAKS_CONFIG"]).read_text()
elif os.environ.get("GITLEAKS_CONFIG_TOML"):
    config = os.environ["GITLEAKS_CONFIG_TOML"]
else:
    config = (source / ".gitleaks.toml").read_text() if (source / ".gitleaks.toml").is_file() else None
words = ["planted-leak-marker"] + [line.split("also flag ", 1)[1].strip() for line in (config or "").splitlines()
                                   if line.startswith("# stub: also flag ")]
environment = {key: value for key, value in os.environ.items() if key.startswith(("GIT_", "GITLEAKS_"))}
entry, findings = {"cwd": os.getcwd(), "args": args, "ignore": sorted(ignores), "config": config, "env": environment}, []


def flagged(line):
    return any(word in line for word in words) and ("--ignore-gitleaks-allow" in args or "gitleaks:allow" not in line)


def found(file, number, line, commit=""):
    fingerprint = f"{file}:stub-rule:{number}"
    findings.append({"RuleID": "stub-rule", "File": file, "StartLine": number, "Commit": commit, "Match": line,
                     "Fingerprint": f"{commit}:{fingerprint}" if commit else fingerprint})


if os.environ.get("GITLEAKS_STUB_FAIL"):  # as gitleaks 8.24.3 fails on a bad revision: ERR lines, then its WRN trailer
    for line in ("ERR [git] fatal: bad revision", 'ERR failed to scan Git repository error="stderr is not empty"',
                 "WRN scanned ~0 bytes (0)", "WRN partial scan completed in 185ms", "WRN no leaks found in partial scan"):
        print("6:01AM " + line, file=sys.stderr)
    sys.exit(1)
if args[0] == "git":
    log_opts = next(arg for arg in args if arg.startswith("--log-opts="))[len("--log-opts="):]
    out = subprocess.run(["git", "-C", str(source), "log", "-p", "-U0", *log_opts.split(" ")],  # as gitleaks runs it
                         capture_output=True, text=True, check=True).stdout
    commit = path = None
    number = 0
    for line in out.splitlines():
        if line.startswith("commit "):
            commit = line.split()[1]
        elif line.startswith("+++ "):
            path = line[6:]
        elif line.startswith("@@ "):  # a hunk: its added lines start at the new file's line +<number>
            number = int(re.match(r"@@ -\\S+ \\+(\\d+)", line).group(1))
        elif line.startswith("+"):
            if flagged(line):
                found(path, number, line[1:], commit)
            number += 1
else:
    entry["files"] = {str(p): p.read_text(errors="replace") for p in sorted(source.rglob("*")) if p.is_file()}
    for name, text in entry["files"].items():
        for number, line in enumerate(text.splitlines(), 1):
            if flagged(line):
                found(name, number, line)
if "# stub: allow everything" in (config or ""):
    findings = []
findings = [finding for finding in findings
            if not {finding["Fingerprint"], f"{finding['File']}:stub-rule:{finding['StartLine']}"} & ignores]
with open(os.environ["GITLEAKS_STUB_LOG"], "a", encoding="utf-8") as log:
    log.write(json.dumps(entry) + "\\n")
Path(option("--report-path")).write_text(json.dumps(findings), encoding="utf-8")
sys.exit(1 if findings else 0)
'''


@pytest.fixture(autouse=True)
def _own_git_config(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    """Every git a case runs, the hook's included, reads an empty global config of the case's own: never the user's,
    and never /dev/null, over which a config write would rename its lock file."""
    config = tmp_path_factory.mktemp("git") / "config"
    config.write_text("", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def _setup_module():
    spec = importlib.util.spec_from_file_location("secret_scan_setup", SETUP)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _registered(event: str, script: str) -> list[dict]:
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    return [entry for entry in settings["hooks"].get(event, [])
            if any(script in hook.get("command", "") for hook in entry["hooks"])]


class Scanner:
    """The stub where the guard looks for the provisioned gitleaks, and the log of its calls."""

    def __init__(self, root: Path) -> None:
        version, _archive, sha256 = _setup_module().pin()
        self.home = root / "home"
        self.folder = self.home / ".cache" / "earningsnerd" / "gitleaks" / f"{version}-{sha256}"
        self.folder.mkdir(parents=True)
        self.binary = self.folder / "gitleaks"
        self.binary.write_text(STUB, encoding="utf-8")
        self.binary.chmod(0o755)
        (self.folder / "gitleaks.sha256").write_text(
            f"{hashlib.sha256(self.binary.read_bytes()).hexdigest()}  gitleaks\n", encoding="utf-8")
        self.log = root / "gitleaks-calls.jsonl"

    def calls(self) -> list[dict]:
        return [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()] if self.log.exists() else []


@pytest.fixture
def scanner(tmp_path: Path) -> Scanner:
    return Scanner(tmp_path)


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
                          env={**os.environ, **GIT_ENV}).stdout.strip()


def _commit(repo: Path, name: str, text: str) -> str:
    (repo / name).write_text(text, encoding="utf-8")
    _git(repo, "add", name)
    _git(repo, "commit", "-q", "-m", name)
    return _git(repo, "rev-parse", "HEAD")


def _new_repo(path: Path) -> Path:
    path.mkdir()
    _git(path, "init", "-q", "-b", "main")
    return path.resolve()


def _main_with(repo: Path, files: dict[str, str]) -> None:
    """Move origin/main to a commit on top of it, off the pushed branch, that adds these files: as a pin or a config
    lands on main and is fetched."""
    env = {**os.environ, **GIT_ENV, "GIT_INDEX_FILE": str(repo / ".git" / "main-index")}

    def git(*args: str, stdin: str | None = None) -> str:
        return subprocess.run(["git", *args], cwd=repo, env=env, input=stdin, check=True, capture_output=True,
                              text=True).stdout.strip()

    git("read-tree", MAIN)
    for name, text in files.items():
        git("update-index", "--add", "--cacheinfo", f"100644,{git('hash-object', '-w', '--stdin', stdin=text)},{name}")
    git("update-ref", MAIN, git("commit-tree", git("write-tree"), "-p", MAIN, "-m", "main's pins"))


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """main: `base.txt` holding the marker, which origin/main holds, then a clean commit (HEAD). Branch `side`: a
    commit holding the marker that no remote-tracking ref holds."""
    path = _new_repo(tmp_path / "repo")
    _git(path, "remote", "add", "origin", str(tmp_path / "origin.git"))  # never fetched: its refs are planted
    _commit(path, "base.txt", LEAKY)
    _git(path, "update-ref", MAIN, "HEAD")
    _git(path, "branch", "side")
    _commit(path, "clean.txt", "nothing to see\n")
    _git(path, "checkout", "-q", "side")
    _commit(path, "side.txt", LEAKY)
    _git(path, "checkout", "-q", "main")
    return path


@pytest.fixture
def elsewhere(tmp_path: Path) -> Path:
    (tmp_path / "elsewhere").mkdir()
    return (tmp_path / "elsewhere").resolve()


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A copy of the hooks and ci.yml in a repository of the case's own, run as CLAUDE_PROJECT_DIR: a write's scan takes
    its pins and config from this project's main, which a case can move."""
    path = _new_repo(tmp_path / "project")
    for source in (GUARD, SETUP, GUARD.parent / "codex_mention_guard.py", CI):
        target = path / source.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    _git(path, "commit", "-q", "--allow-empty", "-m", "main")
    _git(path, "update-ref", MAIN, "HEAD")
    return path


def _event(tool: str, tool_input: object, cwd: Path) -> str:
    return json.dumps({
        "session_id": "s", "transcript_path": "/dev/null", "cwd": str(cwd), "permission_mode": "default",
        "hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input, "tool_use_id": "toolu_1",
    })


def _run(scanner: Scanner, stdin: str, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    """Run the command .claude/settings.json registers, as Claude Code does (`/bin/sh -c`), within its timeout."""
    [hook] = [hook for entry in _registered("PreToolUse", "secret_scan_guard.py") for hook in entry["hooks"]]
    env = {**os.environ, **GIT_ENV, "HOME": str(scanner.home), "CLAUDE_PROJECT_DIR": str(ROOT),
           "GITLEAKS_STUB_LOG": str(scanner.log), **(extra_env or {})}
    return subprocess.run(["sh", "-c", hook["command"]], input=stdin, capture_output=True, text=True, env=env,
                          timeout=hook["timeout"])


def _decision(scanner: Scanner, tool: str, tool_input: object, cwd: Path,
              extra_env: dict[str, str] | None = None) -> dict | None:
    proc = _run(scanner, _event(tool, tool_input, cwd), extra_env)
    assert proc.returncode == 0, proc.stderr
    if not proc.stdout:
        return None
    parsed = json.loads(proc.stdout)
    assert list(parsed) == ["hookSpecificOutput"]
    output = parsed["hookSpecificOutput"]
    assert sorted(output) == ["hookEventName", "permissionDecision", "permissionDecisionReason"]
    assert output["hookEventName"] == "PreToolUse"
    return output


def _refused(decision: dict | None, *found: str) -> str:
    assert decision is not None, "the hook let it through"
    assert decision["permissionDecision"] == "deny"
    reason = decision["permissionDecisionReason"]
    assert reason.startswith("Refused by .claude/hooks/secret_scan_guard.py: ") and LESSON in reason
    for text in found:
        assert text in reason
    return reason


def _bash(scanner: Scanner, command: str, cwd: Path) -> dict | None:
    return _decision(scanner, "Bash", {"command": command, "description": "x"}, cwd)


def _b64(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


# --- git push ------------------------------------------------------------------------------------------------------

def test_a_push_whose_new_commit_holds_a_finding_is_refused(scanner: Scanner, repo: Path) -> None:
    leak = _commit(repo, "settings.py", LEAKY)
    reason = _refused(_bash(scanner, "git push -u origin main", repo), "found a secret-shaped literal",
                      f"settings.py:1 (stub-rule), fingerprint {leak}:settings.py:stub-rule:1", "# gitleaks:allow",
                      ".gitleaksignore")
    assert MARKER not in reason  # where, never what


def test_a_clean_push_reads_only_the_commits_no_remote_tracking_ref_holds(scanner: Scanner, repo: Path) -> None:
    # base.txt holds the marker, but origin/main holds its commit: the push adds only the clean one.
    assert _bash(scanner, "git push -u origin main", repo) is None
    [call] = scanner.calls()
    head = _git(repo, "rev-parse", "HEAD")
    assert call["args"][:7] == ["git", ".", f"--log-opts={LOG_OPTIONS} {head} --not --remotes=origin", *FLAGS]
    # Its source is a new directory of its own, the repository reached through GIT_DIR with replace refs off, and it
    # reads main's pins alone: no -c while main has no config, so gitleaks runs its own default, as the job does.
    work = Path(call["cwd"]).resolve()
    assert work not in (repo, repo / ".git") and repo not in work.parents
    assert (call["env"]["GIT_DIR"], call["env"]["GIT_NO_REPLACE_OBJECTS"]) == (str(repo / ".git"), "1")
    assert call["args"][7:] == ["-i", call["args"][8], "--report-format", "json", "--report-path", call["args"][12]]
    assert Path(call["args"][8]).resolve().parent == work
    assert (call["ignore"], call["config"]) == ([], None)


# Each pushes main's clean commit alone, from the repository or from elsewhere: passes, with exactly that range.
PRECISE = {
    "a bare push": ("git push", "repo"),
    "a path to git": ("/usr/bin/git push origin main", "repo"),
    "HEAD": ("git push origin HEAD", "repo"),
    "a forced refspec to another name": ("git push origin +main:refs/heads/other", "repo"),
    "git -C from elsewhere": ("git -C {repo} push origin main", "elsewhere"),
    "a relative git -C": ("git -C repo push origin main", "parent"),
    "cd and push in a compound line": ("cd {repo} && git push", "elsewhere"),
    "cd and push in a subshell": ("(cd {repo} && git push origin main); echo done", "elsewhere"),
    "pushd": ("pushd {repo} > /dev/null && git push origin main", "elsewhere"),
    "a redirected, piped push": ("git push origin main 2>&1 | tail -3", "repo"),
    "a push in a command substitution": ('OUT="$(git push origin main 2>&1)"', "repo"),
    "a push in an if": ("if git push; then echo ok; fi", "repo"),
    "git's global options": ("git -c push.default=current --no-pager push origin main", "repo"),
    "push options that take values": ("git push -o ci.skip --repo origin --force-with-lease origin main", "repo"),
    "a line whose here-document text names another push": (
        "cat > /dev/null <<'EOF'\ngit push origin side\nEOF\ngit push origin main", "repo"),
    "a push after a comment line": ("# push the branch\ngit push origin main", "repo"),
}


@pytest.mark.parametrize(("command", "where"), PRECISE.values(), ids=PRECISE.keys())
def test_a_push_reads_what_it_sends_from_where_it_runs(scanner: Scanner, repo: Path, elsewhere: Path,
                                                        command: str, where: str) -> None:
    cwd = {"repo": repo, "elsewhere": elsewhere, "parent": repo.parent}[where]
    assert _bash(scanner, command.format(repo=repo), cwd) is None
    [call] = scanner.calls()
    assert call["args"][2] == f"--log-opts={LOG_OPTIONS} {_git(repo, 'rev-parse', 'main')} --not --remotes=origin"
    assert call["env"]["GIT_DIR"] == str(repo / ".git")


# Each reaches side's commit: by naming it, or, when the line names something the hook cannot resolve, through the
# scan of every local branch and HEAD that no remote-tracking ref holds, which the refusal says it widened to.
REACHES_SIDE = {
    "the side branch by name": ("git push origin side", False),
    "every branch": ("git push --all origin", False),
    "every branch, by --branches": ("git push --branches origin", False),
    "every ref": ("git push --mirror origin", False),
    "a branch held in a variable": ('git push origin "$BRANCH"', True),
    "a branch a substitution names": ("git push origin $(git branch --show-current)", True),
    "a directory held in a variable": ('cd "$DIR" && git push origin main', True),
    "the previous directory": ("cd - && git push origin main", True),
    "a wildcard refspec": ("git push origin 'refs/heads/*:refs/heads/*'", True),
    "a source that does not exist yet": ("git push origin feature", True),
    "--git-dir": ("git --git-dir=.git push origin main", True),
    "GIT_DIR=": ("GIT_DIR=.git git push origin main", True),
}


@pytest.mark.parametrize(("command", "widened"), REACHES_SIDE.values(), ids=REACHES_SIDE.keys())
def test_a_push_the_hook_cannot_resolve_reads_every_unpushed_branch(scanner: Scanner, repo: Path, command: str,
                                                                   widened: bool) -> None:
    reason = _refused(_bash(scanner, command, repo), "side.txt:1 (stub-rule)")
    assert ("widened to every local branch's and HEAD's" in reason) is widened
    assert ("the hook cannot resolve; name them literally to narrow it" in reason) is widened


@pytest.mark.parametrize(("command", "refused"), [
    ("git push origin main", True),
    ("cd {repo} && git push origin main", False),
    ("(cd {repo}) && git push origin main", True),  # the subshell's cd ends with it
    ("git -C {repo} push origin main", False),
    ("cd {repo}; cd {other} && git push origin main", True),
    ("pushd {repo} && popd && git push origin main", True),  # back where it started
    ("cd {other}/not-yet && git push origin main", True),  # a directory no repository holds yet
])
def test_the_push_runs_in_the_directory_the_line_moves_to(scanner: Scanner, repo: Path, tmp_path: Path,
                                                         command: str, refused: bool) -> None:
    other = _new_repo(tmp_path / "other")  # no remote-tracking ref: its one commit, which holds the marker, is new
    _commit(other, "other.txt", LEAKY)
    decision = _bash(scanner, command.format(repo=repo, other=other), other)
    if refused:
        _refused(decision, "other.txt:1 (stub-rule)")
    else:
        assert decision is None


@pytest.mark.parametrize("committed", [True, False], ids=["committed", "uncommitted"])
def test_a_pin_on_the_pushed_branch_gets_nothing_past_the_scan(scanner: Scanner, repo: Path, committed: bool) -> None:
    leak = _commit(repo, "settings.py", LEAKY)
    (repo / ".gitleaksignore").write_text(f"{leak}:settings.py:stub-rule:1\n", encoding="utf-8")
    if committed:
        _commit(repo, ".gitleaksignore", f"{leak}:settings.py:stub-rule:1\n")
    _refused(_bash(scanner, "git push", repo), f"fingerprint {leak}:settings.py:stub-rule:1",
             "a pin on this branch does not count", "every other pull request's `secret-scan` reads main's pins")
    [call] = scanner.calls()
    assert call["ignore"] == []


@pytest.mark.parametrize("pin", ["{leak}:settings.py:stub-rule:1", "settings.py:stub-rule:1"],
                         ids=["a commit's pin", "a global path:rule:line pin"])
def test_a_pin_on_main_clears_the_scan(scanner: Scanner, repo: Path, pin: str) -> None:
    pin = pin.format(leak=_commit(repo, "settings.py", LEAKY))
    _main_with(repo, {".gitleaksignore": f"# reviewed by hand\n{pin}\n"})
    assert _bash(scanner, "git push", repo) is None
    [call] = scanner.calls()
    assert call["ignore"] == [pin]


@pytest.mark.parametrize("tool", ["Bash", "mcp__github__push_files"], ids=["a push", "a write"])
def test_an_inline_gitleaks_allow_clears_the_scan(scanner: Scanner, repo: Path, tool: str) -> None:
    # The stub honours gitleaks:allow unless it is passed --ignore-gitleaks-allow, as gitleaks does.
    allowed = f"TOKEN = '{MARKER}'  # gitleaks:allow\n"
    if tool == "Bash":
        _commit(repo, "settings.py", allowed)
        assert _bash(scanner, "git push", repo) is None
    else:
        assert _decision(scanner, tool, {"files": [{"path": "settings.py", "content": allowed}]}, repo) is None
    assert len(scanner.calls()) == 1


@pytest.mark.parametrize("committed", [True, False], ids=["committed", "uncommitted"])
def test_a_gitleaks_toml_in_the_checkout_gets_nothing_past_the_scan(scanner: Scanner, repo: Path,
                                                                    committed: bool) -> None:
    _commit(repo, "settings.py", LEAKY)
    (repo / ".gitleaks.toml").write_text("# stub: allow everything\n", encoding="utf-8")
    if committed:
        _commit(repo, ".gitleaks.toml", "# stub: allow everything\n")
    _refused(_bash(scanner, "git push", repo), "settings.py:1 (stub-rule)")
    [call] = scanner.calls()
    assert call["config"] is None


# Where gitleaks also takes a pin or a config, none of it main's: the git directory, which the scan once read as its
# source, and the variables gitleaks reads a config from. Each would clear the finding if the scan read it.
OUTSIDE_MAIN = {
    "a pin in the git directory": ({".gitleaksignore": "{leak}:settings.py:stub-rule:1\n"}, {}),
    "a global pin in the git directory": ({".gitleaksignore": "settings.py:stub-rule:1\n"}, {}),
    "a config in the git directory": ({".gitleaks.toml": "# stub: allow everything\n"}, {}),
    "GITLEAKS_CONFIG": ({}, {"GITLEAKS_CONFIG": "{allow}"}),
    "GITLEAKS_CONFIG_TOML": ({}, {"GITLEAKS_CONFIG_TOML": "# stub: allow everything\n"}),
}


@pytest.mark.parametrize(("planted", "variables"), OUTSIDE_MAIN.values(), ids=OUTSIDE_MAIN.keys())
def test_a_pin_or_config_outside_mains_files_gets_nothing_past_the_scan(scanner: Scanner, repo: Path, tmp_path: Path,
                                                                        planted: dict, variables: dict) -> None:
    leak = _commit(repo, "settings.py", LEAKY)
    allow = tmp_path / "allow.toml"
    allow.write_text("# stub: allow everything\n", encoding="utf-8")
    for name, text in planted.items():
        (repo / ".git" / name).write_text(text.format(leak=leak), encoding="utf-8")
    extra_env = {name: value.format(allow=allow) for name, value in variables.items()}
    _refused(_decision(scanner, "Bash", {"command": "git push"}, repo, extra_env), "settings.py:1 (stub-rule)")
    [call] = scanner.calls()
    assert (call["ignore"], call["config"]) == ([], None)
    assert not {"GITLEAKS_CONFIG", "GITLEAKS_CONFIG_TOML"} & set(call["env"])


def test_mains_gitleaks_toml_is_the_scans_config(scanner: Scanner, repo: Path) -> None:
    _main_with(repo, {".gitleaks.toml": "# stub: also flag a-word-only-mains-rule-knows\n"})
    _commit(repo, "notes.txt", "a-word-only-mains-rule-knows\n")
    _refused(_bash(scanner, "git push", repo), "notes.txt:1 (stub-rule)")
    [call] = scanner.calls()
    assert call["config"] == "# stub: also flag a-word-only-mains-rule-knows\n"


def test_without_origin_main_the_scan_reads_no_pins(scanner: Scanner, repo: Path) -> None:
    leak = _commit(repo, "settings.py", LEAKY)
    (repo / ".gitleaksignore").write_text(f"{leak}:settings.py:stub-rule:1\n", encoding="utf-8")
    _git(repo, "update-ref", "refs/remotes/origin/stable", MAIN)  # origin still holds base.txt's commit
    _git(repo, "update-ref", "-d", MAIN)
    _refused(_bash(scanner, "git push", repo), "settings.py:1 (stub-rule)")
    [call] = scanner.calls()
    assert (call["ignore"], call["config"]) == ([], None)


@pytest.mark.parametrize("on_main", [False, True], ids=["sent with the write", "on main"])
@pytest.mark.parametrize(("name", "content"), [
    (".gitleaks.toml", "# stub: allow everything\n"),
    (".gitleaksignore", "files/src/app/settings.py:stub-rule:1\n"),  # the fingerprint gitleaks gives the sent file
], ids=[".gitleaks.toml", ".gitleaksignore"])
def test_a_gitleaks_file_clears_a_writes_scan_from_main_never_from_the_write(
        scanner: Scanner, project: Path, elsewhere: Path, name: str, content: str, on_main: bool) -> None:
    files = [{"path": "src/app/settings.py", "content": LEAKY}]
    if on_main:
        _main_with(project, {name: content})
    else:
        files.insert(0, {"path": name, "content": content})
    decision = _decision(scanner, "mcp__github__push_files", {"files": files}, elsewhere,
                         {"CLAUDE_PROJECT_DIR": str(project)})
    [call] = scanner.calls()
    if on_main:
        assert decision is None
    else:
        _refused(decision, "src/app/settings.py:1 (stub-rule)")
        assert call["files"][f"files/{name}"] == content and (call["ignore"], call["config"]) == ([], None)


MOVES = {
    "switch": "git switch side && git push -u origin HEAD",
    "checkout": "git checkout side && git push",
    "reset": "git reset --hard side && git push -f origin HEAD:cleanbr",
    "branch -f": "git branch -f cleanbr side && git push -f origin cleanbr",
    # Read as moves though they move nothing: the push alone would send main's clean commit, and no name narrows it.
    "a checkout of a file": "git checkout -- base.txt && git push origin main",
    "stash": "git stash && git push origin main",
    "branch --show-current": "git branch --show-current && git push origin main",
}


@pytest.mark.parametrize("command", MOVES.values(), ids=MOVES.keys())
def test_a_line_that_moves_head_or_a_branch_before_it_pushes_widens_the_scan(scanner: Scanner, repo: Path,
                                                                            command: str) -> None:
    _git(repo, "branch", "cleanbr", "main")  # clean as it stands: the line points it, or HEAD, at side first
    reason = _refused(_bash(scanner, command, repo), "side.txt:1 (stub-rule)",
                      "widened to every local branch's and HEAD's because the line moves HEAD or a branch before it "
                      "pushes; push in a call of its own to narrow it")
    assert "name them literally" not in reason


# Git configuration CI does not have, each of which hides the new commit's added line from `git log -p` unless the scan
# turns it off: colour codes before the line's `+`, a textconv driver's text in its place, a replace ref's commit.
BLINDERS = {
    "color.ui=always": lambda repo, leak: _git(repo, "config", "color.ui", "always"),
    "color.diff=always": lambda repo, leak: _git(repo, "config", "color.diff", "always"),
    "a textconv driver": lambda repo, leak: (
        (repo / ".git" / "info").mkdir(exist_ok=True),
        (repo / ".git" / "info" / "attributes").write_text("*.py diff=hidden\n", encoding="utf-8"),
        _git(repo, "config", "diff.hidden.textconv", f"sed s/{MARKER}/hidden/")),
    "a replace ref": lambda repo, leak: _git(repo, "replace", leak, f"{leak}~1"),
    # These leave the line in view but change the fingerprint gitleaks reads, so main's pins stop clearing it.
    "format.pretty=oneline": lambda repo, leak: _git(repo, "config", "format.pretty", "oneline"),
    "log.abbrevCommit": lambda repo, leak: _git(repo, "config", "log.abbrevCommit", "true"),
    "diff.noprefix": lambda repo, leak: _git(repo, "config", "diff.noprefix", "true"),
}


@pytest.mark.parametrize("configure", BLINDERS.values(), ids=BLINDERS.keys())
def test_git_configuration_ci_lacks_hides_no_added_line_from_the_scan(scanner: Scanner, repo: Path, configure) -> None:
    leak = _commit(repo, "settings.py", LEAKY)
    configure(repo, leak)
    _refused(_bash(scanner, "git push", repo), f"settings.py:1 (stub-rule), fingerprint {leak}:settings.py:stub-rule:1")
    # The stub's git renders what each case hides or changes, so each fails without its option or variable. Three
    # options have no such case: `git log` runs an external diff only when asked (--no-ext-diff), the stub reads no
    # dates (--date=default) and this suite signs nothing (--no-show-signature). What gitleaks is handed is pinned
    # whole.
    [call] = scanner.calls()
    assert call["args"][2] == f"--log-opts={LOG_OPTIONS} {leak} --not --remotes=origin"
    assert call["env"]["GIT_NO_REPLACE_OBJECTS"] == "1"


def test_a_root_commit_is_scanned_whatever_log_show_root_says(scanner: Scanner, repo: Path) -> None:
    _git(repo, "config", "log.showRoot", "false")  # git log would show no diff for a root commit
    _git(repo, "checkout", "-q", "--orphan", "pages")  # a new history: its first commit is a root
    _git(repo, "rm", "-rq", "--cached", ".")
    leak = _commit(repo, "page.txt", LEAKY)
    _refused(_bash(scanner, "git push origin pages", repo),
             f"page.txt:1 (stub-rule), fingerprint {leak}:page.txt:stub-rule:1")


@pytest.mark.parametrize(("command", "config"), [
    ("git push -u origin feature", {}),
    ("git push", {"branch.feature.remote": "backup", "remote.pushDefault": "origin"}),
    ("git push", {"branch.feature.remote": "backup", "remote.pushDefault": "backup", "branch.feature.pushRemote": "origin"}),
    ("git push --repo origin", {"branch.feature.remote": "backup", "branch.feature.pushRemote": "backup"}),
], ids=["named on the line", "by remote.pushDefault over the upstream", "by the branch's pushRemote over pushDefault",
        "named by --repo over pushRemote"])
def test_commits_another_remote_holds_are_scanned_on_their_way_to_origin(scanner: Scanner, repo: Path, tmp_path: Path,
                                                                        command: str, config: dict[str, str]) -> None:
    _git(repo, "remote", "add", "backup", str(tmp_path / "backup.git"))
    _git(repo, "checkout", "-q", "-b", "feature")
    leak = _commit(repo, "feature.txt", LEAKY)
    _git(repo, "update-ref", "refs/remotes/backup/feature", "feature")  # backup holds it; origin does not
    for key, value in config.items():
        _git(repo, "config", key, value)
    _refused(_bash(scanner, command, repo), "feature.txt:1 (stub-rule)")
    [call] = scanner.calls()
    assert call["args"][2] == f"--log-opts={LOG_OPTIONS} {leak} --not --remotes=origin"


@pytest.mark.parametrize(("command", "config", "held"), [
    ("git push origin main", {}, "--remotes=origin"),
    ("git push backup main", {"branch.main.pushRemote": "origin"}, "--remotes=backup"),
    ("git push", {}, "--remotes=origin"),
    ("git push", {"branch.main.remote": "backup"}, "--remotes=backup"),
    ("git push", {"branch.main.remote": "origin", "remote.pushDefault": "backup"}, "--remotes=backup"),
    ("git push", {"remote.pushDefault": "origin", "branch.main.pushRemote": "backup"}, "--remotes=backup"),
    ("git push https://example.com/o/r.git main", {}, "--remotes"),
], ids=["a named remote", "a named remote over pushRemote", "no remote named", "the branch's upstream remote",
        "remote.pushDefault", "the branch's pushRemote", "a URL"])
def test_the_scan_leaves_out_what_the_remote_it_pushes_to_holds(scanner: Scanner, repo: Path, tmp_path: Path,
                                                               command: str, config: dict[str, str], held: str) -> None:
    _git(repo, "remote", "add", "backup", str(tmp_path / "backup.git"))
    _git(repo, "update-ref", "refs/remotes/backup/main", "main")
    for key, value in config.items():
        _git(repo, "config", key, value)
    assert _bash(scanner, command, repo) is None
    [call] = scanner.calls()
    assert call["args"][2].endswith(f" --not {held}")


@pytest.mark.parametrize("command", ["git push origin tag v1", "git push --tags origin"])
def test_a_tag_push_reads_the_tags_commits(scanner: Scanner, repo: Path, command: str) -> None:
    _git(repo, "tag", "v1", "side")
    assert "widened" not in _refused(_bash(scanner, command, repo), "side.txt:1 (stub-rule)")


def test_a_push_from_a_repository_the_hook_cannot_resolve_or_fall_back_on_is_refused(scanner: Scanner,
                                                                                   elsewhere: Path) -> None:
    _refused(_bash(scanner, 'cd "$WORKTREE" && git push', elsewhere), "cannot resolve", "git -C <dir> push")
    assert scanner.calls() == []


@pytest.mark.parametrize("command", [
    "git push --dry-run origin side",
    "git push -n origin side",
    "git push origin --delete side",
    "git push origin :side",
], ids=["--dry-run", "-n", "--delete", "a deletion refspec"])
def test_a_push_that_sends_nothing_is_not_scanned(scanner: Scanner, repo: Path, command: str) -> None:
    assert _bash(scanner, command, repo) is None
    assert scanner.calls() == []


@pytest.mark.parametrize("command", [
    "git add -A && git commit -m wip && git push",
    "git pull --rebase && git push origin main",
    "git commit -m \"$(cat <<'EOF'\nfix: a thing\nEOF\n)\" && git push",
    "git push origin main && git cherry-pick side",
    "git merge side && git push",
    "git rebase origin/main && git push --force-with-lease",
    "git revert --no-edit HEAD && git push",
    "git am fix.patch && git push",
], ids=["commit", "pull", "a commit message from a here-document", "a commit after the push", "merge", "rebase",
        "revert", "am"])
def test_a_line_that_makes_commits_and_pushes_is_refused(scanner: Scanner, repo: Path, command: str) -> None:
    _refused(_bash(scanner, command, repo), "commits and pushes in one call", "a hook runs before the line",
             "Commit in one call and push in the next")
    assert scanner.calls() == []


def test_a_scan_that_fails_refuses_the_push_and_says_what_to_do(scanner: Scanner, repo: Path) -> None:
    decision = _decision(scanner, "Bash", {"command": "git push"}, repo, {"GITLEAKS_STUB_FAIL": "1"})
    reason = _refused(decision, "could not finish scanning", "Fix what gitleaks names", "send the call again")
    assert "(exit 1: ERR [git] fatal: bad revision; ERR failed to scan Git repository" in reason  # the cause, first


@pytest.mark.parametrize("command", [
    "git status && ls -la",
    "git log --grep push --oneline",
    "git stash push -m wip",
    "pushd /tmp && popd",
    'echo "git push"',
    "git commit -m 'push later'",
    "gh pr create --title 'push the fix' --body x",
    "git commit -m wip  # then git push",
    "git status  # before git push",
], ids=["status", "a log that names push", "stash push", "pushd", "a quoted git push", "a commit alone", "gh pr create",
        "a commit whose comment names a push", "a status whose comment names a push"])
def test_a_bash_command_that_pushes_nothing_runs_no_scan(scanner: Scanner, repo: Path, command: str) -> None:
    assert _bash(scanner, command, repo) is None
    assert scanner.calls() == []


# --- the binary ----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("state", ["missing", "tampered", "unrecorded"])
def test_without_a_verified_binary_a_scan_is_refused(scanner: Scanner, repo: Path, state: str) -> None:
    if state == "missing":
        scanner.binary.unlink()
    elif state == "tampered":
        scanner.binary.write_text(STUB + "# changed after it was recorded\n", encoding="utf-8")
    else:
        (scanner.folder / "gitleaks.sha256").unlink()
    expected = "is not provisioned" if state == "missing" else "does not match the SHA-256 recorded beside it"
    for tool, tool_input in [
        ("Bash", {"command": "git push"}),
        ("mcp__github__create_or_update_file", {"path": "a.md", "content": "clean", "message": "m"}),
    ]:
        _refused(_decision(scanner, tool, tool_input, repo), expected, f"python3 {SETUP}")
    assert scanner.calls() == []


# --- writes that commit without a push -----------------------------------------------------------------------------

WRITE_TOOLS = {
    "push_files": ("mcp__github__push_files", lambda files: {"owner": "o", "repo": "r", "branch": "b", "message": "m",
                                                               "files": files}),
    "create_or_update_file": ("mcp__github__create_or_update_file", lambda files: {
        "owner": "o", "repo": "r", "branch": "b", "message": "m", **files[-1]}),
    "a plugin's GitHub server": ("mcp__plugin_gh_github__push_files", lambda files: {"files": files}),
    "a server named in capitals": ("mcp__GitHub__create_or_update_file", lambda files: files[-1]),
}


@pytest.mark.parametrize(("tool", "build"), WRITE_TOOLS.values(), ids=WRITE_TOOLS.keys())
def test_a_github_mcp_write_is_scanned_under_its_paths(scanner: Scanner, project: Path, elsewhere: Path, tool: str,
                                                       build) -> None:
    clean = [{"path": "docs/notes.md", "content": "notes"}, {"path": "src/app/settings.py", "content": "DEBUG = False\n"}]
    env = {"CLAUDE_PROJECT_DIR": str(project)}
    assert _decision(scanner, tool, build(clean), elsewhere, env) is None
    leaky = [*clean[:1], {"path": "src/app/settings.py", "content": LEAKY}]
    env["GITLEAKS_CONFIG_TOML"] = "# stub: allow everything\n"  # left out of gitleaks' environment
    _refused(_decision(scanner, tool, build(leaky), elsewhere, env), "src/app/settings.py:1 (stub-rule)",
             "# gitleaks:allow", "commit the file and push it with git")
    first, second = scanner.calls()
    # `gitleaks dir .` from the directory scanned, which holds the sent files alone, under files/; main's pins are
    # elsewhere, and no -c while main has no config.
    assert first["args"][:6] == ["dir", ".", *FLAGS] and "-c" not in first["args"] and first["config"] is None
    assert Path(first["args"][first["args"].index("-i") + 1]).resolve().parent != Path(first["cwd"]).resolve()
    sent = clean if tool.endswith("__push_files") else clean[-1:]
    assert first["files"] == {f"files/{entry['path']}": entry["content"] for entry in sent}
    assert "GITLEAKS_CONFIG_TOML" not in second["env"]


@pytest.mark.parametrize("path", ["../escape.txt", "/etc/escape.txt", "docs/../../escape.txt", ""])
def test_a_path_that_leaves_the_scan_directory_is_refused(scanner: Scanner, elsewhere: Path, path: str) -> None:
    files = [{"path": "docs/notes.md", "content": "notes"}, {"path": path, "content": "x"}]
    _refused(_decision(scanner, "mcp__github__push_files", {"files": files}, elsewhere), "leaves the directory")
    assert scanner.calls() == []


@pytest.mark.parametrize(("tool", "tool_input"), [
    ("mcp__github__get_file_contents", {"owner": "o", "repo": "r", "path": "a.py"}),
    ("mcp__github__create_pull_request", {"title": "x", "body": LEAKY, "head": "b", "base": "main"}),
    ("mcp__github__delete_file", {"path": "a.py", "message": "m", "branch": "b"}),
    ("mcp__gh__push_files", {"files": [{"path": "a.py", "content": LEAKY}]}),  # stated gap: no "github" in the name
], ids=["a read", "a pull request", "a deletion", "a server named without github"])
def test_an_mcp_call_that_commits_no_content_runs_no_scan(scanner: Scanner, elsewhere: Path, tool: str,
                                                         tool_input: dict) -> None:
    assert _decision(scanner, tool, tool_input, elsewhere) is None
    assert scanner.calls() == []


@pytest.fixture
def payloads(tmp_path: Path) -> Path:
    folder = tmp_path / "payloads"
    folder.mkdir()
    (folder / "payload.json").write_text(json.dumps({"message": "m", "content": _b64(LEAKY)}), encoding="utf-8")
    (folder / "content.b64").write_text(_b64(LEAKY) + "\n", encoding="utf-8")
    (folder / "tree.json").write_text(json.dumps({"tree": [{"path": "a.py", "content": LEAKY}]}), encoding="utf-8")
    (folder / "secret.txt").write_text(LEAKY, encoding="utf-8")
    return folder


API_WRITES = {
    "a contents write with base64 content": (
        f"gh api -X PUT repos/o/r/contents/src/a.py -f message=add -f content={_b64(LEAKY)} -f branch=b",
        "decoded-content-1:1"),
    # Padded, so a value run on into the next line's words would no longer decode.
    "a base64 content value before another line": (
        f"gh api -X PUT repos/o/r/contents/k.py -f content={_b64(LEAKY + '#')}\necho done", "decoded-content-1:1"),
    "a blob of raw text": (f"gh api repos/o/r/git/blobs -f content=\"{LEAKY}\" -f encoding=utf-8", "command-line:1"),
    "a payload file with a base64 content field": (
        "gh api -X PUT 'repos/{owner}/{repo}/contents/a.py' --input payload.json", "decoded-content-1:1"),
    "a content field read from a base64 file": (
        "gh api -X PUT repos/o/r/contents/a.py -f message=m -F content=@content.b64", "decoded-content-1:1"),
    "a tree sent to api.github.com": (
        "curl -X POST https://api.github.com/repos/o/r/git/trees -d @tree.json", "sent-file-1:1"),
    "a GraphQL commit": (
        "gh api graphql -f query='mutation { createCommitOnBranch(input: {fileChanges: {additions: "
        f"[{{path: \"a.py\", contents: \"{_b64(LEAKY)}\"}}]}}}}) {{ commit {{ oid }} }} }}'", "decoded-content-1:1"),
}


@pytest.mark.parametrize(("command", "found"), API_WRITES.values(), ids=API_WRITES.keys())
def test_a_gh_api_contents_write_is_scanned_with_its_content_decoded(scanner: Scanner, payloads: Path, command: str,
                                                                   found: str) -> None:
    _refused(_bash(scanner, command, payloads), f"{found} (stub-rule)", "# gitleaks:allow")


@pytest.mark.parametrize("command", [
    "gh api -X PUT repos/o/r/contents/src/a.py -f message=add -f content=" + _b64("print('hello')\n"),
    "gh api repos/o/r/contents/README.md --jq .content",
], ids=["a clean write", "a read"])
def test_a_clean_gh_api_contents_call_passes(scanner: Scanner, payloads: Path, command: str) -> None:
    assert _bash(scanner, command, payloads) is None
    [call] = scanner.calls()
    assert call["args"][0] == "dir" and call["files"]["files/command-line"] == command


@pytest.mark.parametrize("command", [
    "gh api repos/o/r/git/blobs --input big.json",
    "gh api repos/o/r/git/blobs --input later.json",
    "printf '{}' > made.json && gh api repos/o/r/git/blobs --input made.json",
    "gh api -X PUT repos/o/r/contents/a.py -f message=m -F content=@folder",
], ids=["over the reader's 1 MiB", "not there", "made by the same line", "no regular file"])
def test_a_repository_write_whose_body_the_hook_cannot_read_is_refused(scanner: Scanner, payloads: Path,
                                                                       command: str) -> None:
    (payloads / "big.json").write_text(json.dumps({"content": _b64(LEAKY) + "=" * (1 << 20)}), encoding="utf-8")
    (payloads / "folder").mkdir()
    _refused(_bash(scanner, command, payloads), "the hook cannot read it as the line stands", "1 MiB")
    assert scanner.calls() == []  # refused before any scan


def test_a_call_that_writes_no_repository_content_may_name_a_missing_file(scanner: Scanner, payloads: Path) -> None:
    assert _bash(scanner, "gh api repos/o/r/issues/1/comments -F body=@later.md", payloads) is None


def test_content_a_command_builds_as_it_runs_is_a_stated_gap(scanner: Scanner, payloads: Path) -> None:
    command = 'gh api -X PUT repos/o/r/contents/a.py -f message=m -f content="$(base64 -w0 secret.txt)"'
    assert _bash(scanner, command, payloads) is None


@pytest.mark.parametrize("event", [
    json.dumps([]),
    json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Bash"}),
    _event("Bash", {"command": None}, ROOT),
], ids=["a list", "no tool input", "a null command"])
def test_an_event_of_another_shape_goes_through(scanner: Scanner, event: str) -> None:
    proc = _run(scanner, event)
    assert (proc.returncode, proc.stdout) == (0, "")


def test_a_scan_that_outlasts_the_hooks_time_is_refused(guard, scanner: Scanner, repo: Path,
                                                         monkeypatch: pytest.MonkeyPatch) -> None:
    scanner.binary.write_text("#!/bin/sh\nexec sleep 5\n", encoding="utf-8")
    (scanner.folder / "gitleaks.sha256").write_text(
        f"{hashlib.sha256(scanner.binary.read_bytes()).hexdigest()}  gitleaks\n", encoding="utf-8")
    monkeypatch.setenv("HOME", str(scanner.home))
    monkeypatch.setattr(guard, "DEADLINE", time.monotonic() + 1)  # in-process, where the 8.5 s can be cut
    reason = guard.refusal({"tool_name": "Bash", "tool_input": {"command": "git push"}, "cwd": str(repo)})
    assert reason is not None and "did not finish inside the hook's time limit" in reason
    assert "Push fewer commits at a time" in reason


def test_a_scan_out_of_time_says_what_can_work(guard, scanner: Scanner, repo: Path,
                                              monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(scanner.home))
    monkeypatch.setenv("GITLEAKS_STUB_LOG", str(scanner.log))

    def refusal(tool: str, tool_input: dict) -> str:
        reason = guard.refusal({"tool_name": tool, "tool_input": tool_input, "cwd": str(repo)})
        assert reason.startswith("Refused by .claude/hooks/secret_scan_guard.py: the scan did not finish inside the hook's")
        return reason

    guard.DEADLINE = 0.0  # spent: the first subprocess runs out of time
    assert "Push fewer commits at a time" in refusal("Bash", {"command": "git push"})
    assert "Send fewer files per call" in refusal("mcp__github__push_files", {"files": [{"path": "a.md", "content": "x"}]})
    guard.DEADLINE = time.monotonic() + 60  # time runs out in gitleaks, once the scan has widened

    def late(*args: object, **kwargs: object) -> None:
        raise guard.Late

    monkeypatch.setattr(guard, "_gitleaks", late)
    reason = refusal("Bash", {"command": 'git push origin "$BRANCH"'})
    assert "because the line names a source or a repository the hook cannot resolve" in reason
    assert "Name the source and the repository literally" in reason
    reason = refusal("Bash", {"command": "git checkout -- base.txt && git push origin main"})  # no name narrows it
    assert "because the line moves HEAD or a branch before it pushes" in reason
    assert "Run the line without its push, then push in a call of its own" in reason
    assert "literally" not in reason


# --- registration --------------------------------------------------------------------------------------------------

def test_the_guard_and_its_setup_are_registered() -> None:
    # Beside the codex guard, with its matcher, which test_codex_mention_guard.py proves reaches Bash and every GitHub
    # MCP server (and that settings.json switches no hook off).
    [codex] = _registered("PreToolUse", "codex_mention_guard.py")
    assert _registered("PreToolUse", "secret_scan_guard.py") == [
        {"matcher": codex["matcher"], "hooks": [{"type": "command", "command": COMMAND, "timeout": 10}]}]
    assert _registered("SessionStart", "secret_scan_setup.py") == [
        {"hooks": [{"type": "command", "command": SETUP_COMMAND, "timeout": 60}]}]
    assert GUARD.is_file() and SETUP.is_file()


def test_the_guard_scans_with_the_secret_scan_jobs_flags(guard) -> None:
    job = re.search(r"^  secret-scan:\n(?:(?: {4}.*)?\n)*", CI.read_text(encoding="utf-8"), re.MULTILINE).group(0)
    assert f" {' '.join(guard.FLAGS)}\n" in job
    assert list(guard.FLAGS) == FLAGS  # what the cases here expect the hook to pass


# --- the setup -----------------------------------------------------------------------------------------------------

def _on(monkeypatch: pytest.MonkeyPatch, system: str, machine: str) -> None:
    monkeypatch.setattr("platform.system", lambda: system)
    monkeypatch.setattr("platform.machine", lambda: machine)


def test_the_setup_reads_the_pin_where_the_secret_scan_job_sets_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    setup = _setup_module()
    _on(monkeypatch, "Linux", "x86_64")  # the job's runner
    version, archive, sha256 = setup.pin()
    text = CI.read_text(encoding="utf-8")
    job = re.search(r"^  secret-scan:\n(?:(?: {4}.*)?\n)*", text, re.MULTILINE).group(0)
    assert f"GITLEAKS_VERSION: {version}\n" in job and f"GITLEAKS_SHA256: {sha256}\n" in job
    # It downloads the archive the job downloads.
    [url] = re.findall(r'"(https://github\.com/gitleaks/[^"]+)"', job)
    assert archive == f"gitleaks_{version}_{setup.CI_PLATFORM}.tar.gz"
    assert url.replace("${GITLEAKS_VERSION}", version) == setup.RELEASE.format(version=version, archive=archive)
    # A pin that is missing or written twice provisions nothing.
    missing, twice = tmp_path / "missing.yml", tmp_path / "twice.yml"
    missing.write_text(re.sub(r"^[ \t]+GITLEAKS_SHA256:.*\n", "", text, flags=re.MULTILINE), encoding="utf-8")
    twice.write_text(text + f"      GITLEAKS_SHA256: {'0' * 64}\n", encoding="utf-8")
    for ci in (missing, twice):
        with pytest.raises(setup.SetupError, match="GITLEAKS_SHA256"):
            setup.pin(ci)


def test_the_platform_pins_follow_ci_yml() -> None:
    # A version bump in ci.yml fails here until CHECKSUMS moves with it: each platform PLATFORMS maps has exactly one
    # SHA-256, for ci.yml's version, each archive its own, and the linux_x64 line, copied from the release's checksums
    # file like the rest, is ci.yml's own GITLEAKS_SHA256, which CI checks on every run.
    setup = _setup_module()
    version, ci_sha256 = setup.ci_pin()
    names = sorted(set(setup.PLATFORMS.values()))
    assert setup.CI_PLATFORM in names
    assert sorted(setup.CHECKSUMS) == [setup.ARCHIVE.format(version=version, platform=name) for name in names]
    assert setup.CHECKSUMS[setup.ARCHIVE.format(version=version, platform=setup.CI_PLATFORM)] == ci_sha256
    assert all(re.fullmatch(r"[0-9a-f]{64}", sha256) for sha256 in setup.CHECKSUMS.values())
    assert len(set(setup.CHECKSUMS.values())) == len(setup.CHECKSUMS)


@pytest.mark.parametrize(("system", "machine", "name"), [
    ("Linux", "x86_64", "linux_x64"),
    ("Linux", "aarch64", "linux_arm64"),
    ("Linux", "arm64", "linux_arm64"),
    ("Darwin", "arm64", "darwin_arm64"),
    ("Darwin", "x86_64", "darwin_x64"),
])
def test_each_mapped_platform_gets_its_own_archive_and_pin(monkeypatch: pytest.MonkeyPatch, system: str, machine: str,
                                                           name: str) -> None:
    setup = _setup_module()
    _on(monkeypatch, system, machine)
    version, ci_sha256 = setup.ci_pin()
    archive = f"gitleaks_{version}_{name}.tar.gz"
    assert setup.pin() == (version, archive, ci_sha256 if name == "linux_x64" else setup.CHECKSUMS[archive])


@pytest.mark.parametrize(("system", "machine"), [("Windows", "AMD64"), ("Linux", "riscv64"), ("FreeBSD", "amd64")])
def test_any_other_platform_has_no_pin_and_is_told_how_to_add_one(monkeypatch: pytest.MonkeyPatch, system: str,
                                                                 machine: str) -> None:
    setup = _setup_module()
    _on(monkeypatch, system, machine)
    with pytest.raises(setup.SetupError) as raised:
        setup.pin()
    message = str(raised.value)
    assert f"this platform ({system} {machine})" in message
    assert "map it in PLATFORMS" in message and "checksums.txt into CHECKSUMS" in message and str(SETUP) in message


def test_a_mapped_platform_without_a_pin_for_ci_ymls_version_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    setup = _setup_module()
    _on(monkeypatch, "Darwin", "arm64")
    monkeypatch.setattr(setup, "CHECKSUMS", {})  # as if ci.yml's version moved and the pins did not
    with pytest.raises(setup.SetupError, match=r"no SHA-256 is pinned for gitleaks_.*_darwin_arm64\.tar\.gz"):
        setup.pin()


@pytest.fixture
def guard(monkeypatch: pytest.MonkeyPatch):
    """The guard loaded in-process, where a platform can be faked; its two neighbours leave sys.modules afterwards."""
    monkeypatch.setattr(sys, "path", list(sys.path))
    spec = importlib.util.spec_from_file_location("secret_scan_guard", GUARD)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    yield module
    for name in ("codex_mention_guard", "secret_scan_setup"):
        sys.modules.pop(name, None)


def test_on_a_platform_without_a_pin_the_guard_refuses_and_says_how_to_add_one(guard, monkeypatch: pytest.MonkeyPatch) -> None:
    _on(monkeypatch, "Windows", "AMD64")
    reason = guard.refusal({"tool_name": "mcp__github__create_or_update_file", "tool_input": {"path": "a.md", "content": "x"}})
    assert reason.startswith("Refused by .claude/hooks/secret_scan_guard.py: ") and LESSON in reason
    assert "this platform (Windows AMD64)" in reason and "map it in PLATFORMS" in reason
    assert f"Fix the pin as that says, run `python3 {SETUP}`" in reason


def _archive(members: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as bundle:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size, info.mode = len(data), 0o755
            bundle.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def test_the_setup_installs_only_the_pinned_archives_gitleaks_and_records_its_digest(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    setup = _setup_module()
    monkeypatch.setenv("HOME", str(tmp_path))
    binary_bytes = b"#!/bin/sh\nexit 0\n"
    archive = _archive({"LICENSE": b"license", "gitleaks": binary_bytes, "../outside": b"escape"})
    sha256, urls = hashlib.sha256(archive).hexdigest(), []
    name = "gitleaks_8.24.3_darwin_arm64.tar.gz"
    binary, downloaded = setup.provision("8.24.3", name, sha256, download=lambda url: urls.append(url) or archive)
    folder = tmp_path / ".cache" / "earningsnerd" / "gitleaks" / f"8.24.3-{sha256}"
    assert (binary, downloaded) == (folder / "gitleaks", True)
    assert urls == [f"https://github.com/gitleaks/gitleaks/releases/download/v8.24.3/{name}"]
    assert sorted(path.name for path in tmp_path.rglob("*") if path.is_file()) == ["gitleaks", "gitleaks.sha256"]
    assert binary.read_bytes() == binary_bytes and os.access(binary, os.X_OK)
    assert (folder / "gitleaks.sha256").read_text() == f"{hashlib.sha256(binary_bytes).hexdigest()}  gitleaks\n"
    # A verified binary in place: nothing is downloaded again.
    assert setup.provision("8.24.3", name, sha256, download=lambda url: pytest.fail("downloaded again")) == (binary, False)


def test_the_setup_refuses_an_archive_the_pin_does_not_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    setup = _setup_module()
    monkeypatch.setenv("HOME", str(tmp_path))
    archive = _archive({"gitleaks": b"#!/bin/sh\nexit 0\n"})
    with pytest.raises(setup.SetupError, match="does not match its pinned SHA-256"):
        setup.provision("8.24.3", "gitleaks_8.24.3_linux_x64.tar.gz", hashlib.sha256(b"another archive").hexdigest(),
                        download=lambda url: archive)
    assert list(tmp_path.iterdir()) == []


def test_a_setup_that_fails_never_blocks_the_session(tmp_path: Path) -> None:
    [hook] = [hook for entry in _registered("SessionStart", "secret_scan_setup.py") for hook in entry["hooks"]]
    closed = "http://127.0.0.1:9"  # nothing listens there, so the download fails at once and never leaves the host
    env = {**os.environ, "HOME": str(tmp_path), "CLAUDE_PROJECT_DIR": str(ROOT), "HTTPS_PROXY": closed,
           "https_proxy": closed, "NO_PROXY": "", "no_proxy": ""}
    proc = subprocess.run(["sh", "-c", hook["command"]], input=json.dumps({"hook_event_name": "SessionStart"}),
                          capture_output=True, text=True, env=env, timeout=hook["timeout"])
    assert proc.returncode == 0
    [line] = proc.stdout.splitlines()
    assert line.startswith("secret_scan_setup: the pinned gitleaks is not provisioned (")
    assert "secret_scan_guard.py refuses every push and repository write it would scan" in line
    assert line.endswith(f"run it by hand with: python3 {SETUP}")
    assert not [path for path in tmp_path.rglob("gitleaks*")]
