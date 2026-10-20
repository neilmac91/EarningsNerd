"""PreToolUse hook: run the pinned gitleaks over what a push or a repository write would send, and refuse it on a
finding (E126).

The gate for lessons/ops-a-secret-shaped-literal-on-any-branch-fails-every-pr.md. CI's `secret-scan` job reads every
branch, so a secret-shaped literal pushed to any branch fails every pull request's scan until main pins it or the
branch drops it. This hook runs the same gitleaks with the job's flags (`--redact=100 --no-banner --exit-code 1`)
before the call: the binary that secret_scan_setup.py, a SessionStart hook, extracted from the archive the job pins
(GITLEAKS_VERSION and GITLEAKS_SHA256 in .github/workflows/ci.yml), after checking it against the SHA-256 recorded
beside it (the job's linux x64 archive; on macOS arm64 or x64 and linux arm64, the same release's archive the setup
pins). With no such binary, or one that does not match, it refuses every call it would scan and names the setup
command; on a platform with no pin the refusal names the platform and how to add one. It fails closed, since a push
let through unscanned is the failure it exists to stop. The registered command (`python3 -I -S`) uses the standard
library only; the script imports its two neighbours in .claude/hooks/ by path.

Every scan reads main's pins and config, as every other pull request's `secret-scan` does, never the pushing
checkout's: gitleaks runs from a new empty directory with `-i` holding `git show origin/main:.gitleaksignore` (empty when
main or the file cannot be read, the strictest reading) and `-c` holding main's `.gitleaks.toml`, or gitleaks' own
rules (`[extend] useDefault = true`) while main has none. A push's scan reads the repository's git directory, which
holds neither file, and a write's files are staged under a subdirectory of the directory scanned, so no
`.gitleaksignore` or `.gitleaks.toml` of the checkout's, or one a call sends, is honoured: a pin on a branch counts for
nothing until it lands on main and is fetched, and a reviewed false positive otherwise takes `# gitleaks:allow`.

.claude/settings.json runs it before every Bash command and every call to an MCP server whose name contains "github"
in any case. It scans
- each `git push` a Bash command line runs: a word `git`, or a path ending in `/git`, wherever it stands, then git's
  global options, then `push`, in a line read as the shell reads it (codex_mention_guard.py's reader, imported), less
  its comments. The push runs in the event's working directory as the line's `cd` and `pushd` to a directory it names
  literally move it (a subshell's move ends with the subshell; a command substitution's text is read after the rest of
  its line), then `git -C`. The scan is `gitleaks git <that repository's git directory> --log-opts="<what it sends>
  --not --remotes=<remote>"`: the commits reachable from what the push sends and from no remote-tracking ref of the
  remote it pushes to (the one it names, when that is a configured remote; else the pushed branch's upstream remote;
  else origin; a URL or a path names none, so every remote's refs count). What it sends: each refspec's source
  (`tag <name>` too; a deletion or a negative refspec sends nothing), HEAD when it names none, every branch for --all
  or --branches, every ref for --mirror and every tag for --tags; a dry run and --delete send nothing. A source it
  cannot resolve (a variable, a substitution, a wildcard, one that does not exist yet) widens the scan to every local
  branch's commits and HEAD's that no such ref holds, and a refusal says so and why. So does a git checkout, switch,
  reset, branch, update-ref, worktree, tag, symbolic-ref or stash earlier in the line, since the hook resolves sources
  before the line moves HEAD or a branch. A repository it cannot resolve (a variable, a substitution, `cd -`, popd,
  --git-dir, --work-tree, GIT_DIR=), or a directory that is in none, widens the scan the same way in the event's
  working directory's repository; with no repository there, an unresolved one refuses.
- a line that pushes and also makes commits anywhere (git am, cherry-pick, commit, commit-tree, merge, pull, rebase
  or revert): refused, since a hook runs before the line and cannot read a commit the line has yet to make. The
  commits go in one call and the push in the next.
- the GitHub MCP tools push_files and create_or_update_file: each file's content, written under its path into a new
  temporary subdirectory (a path that leaves it refuses the call), with `gitleaks dir`.
- a Bash line naming a repository's contents or git data endpoint (`repos/<owner>/<repo>/contents`, `git/blobs`,
  `git/trees`, `git/commits`) or GraphQL's createCommitOnBranch, through `gh api` or api.github.com, a read included:
  the line as written, the files its GitHub writes send (codex_mention_guard.py's detection), and, decoded, each
  base64 `content` value in either and each such file that is base64 whole, with `gitleaks dir`.
A finding, a scan that fails and one that outlasts the hook's time each refuse the call. A refusal is a JSON deny on
stdout naming the scan, where it found something (file, line and rule; for a commit, its fingerprint) and what to do
next, never the secret (gitleaks runs with --redact and without --verbose); anything else exits 0 with no output.
A crash exits 1, which Claude Code reports as a hook error and lets through.

Not checked: a push or write that another shell or program makes (`bash -c '...'`, a here-document fed to a shell, a
script, a git alias such as `git p`, `gh repo create --push`, a submodule's push), a commit another program makes in
the same line, a directory a command other than cd or pushd enters (`env -C`) or a GIT_DIR the line exports, a
repository the hook cannot resolve (`cd "$VAR" && git push`), whose widened scan reads the event's working directory's
repository and not the one pushed, a push that configuration widens beyond its current branch (push.default=matching, a
remote's push refspec), a commit that a move earlier in the line reaches outside every branch, text a command
builds as it runs (`content="$(base64 -w0 file)"`), a word an ANSI-C escape spells (`$'pu\\x73h'`), a GitHub MCP
server registered under a name without "github", a session that loads no repository hooks, and a person's own push.
Tests: backend/tests/unit/test_secret_scan_guard.py.
"""
from __future__ import annotations

import base64
import binascii
import functools
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))  # `python3 -I` leaves the script's directory off the path

import codex_mention_guard as shell  # noqa: E402 - its shell reader and body-file detection, shared
import secret_scan_setup as setup  # noqa: E402 - the pin, the cache and the binary's check, shared

DEADLINE = time.monotonic() + 8.5  # inside the registered 10 seconds, past which Claude Code lets the call through
FLAGS = ("--redact=100", "--no-banner", "--exit-code", "1")  # the `secret-scan` job's
LESSON = "lessons/ops-a-secret-shaped-literal-on-any-branch-fails-every-pr.md"
GIT_VALUE_OPTIONS = ("-C", "-c", "--git-dir", "--work-tree", "--namespace", "--config-env", "--attr-source",
                     "--super-prefix", "--shallow-file")
PUSH_VALUE_OPTIONS = ("--repo", "--receive-pack", "--exec", "--push-option", "--recurse-submodules")
SENDS_NOTHING = {"-n", "--dry-run", "-d", "--delete"}
COMMITTERS = ("am", "cherry-pick", "commit", "commit-tree", "merge", "pull", "rebase", "revert")
# Subcommands that can move HEAD, a branch or a tag: a push after one in the same line sends what the hook cannot resolve.
MOVERS = ("checkout", "switch", "reset", "branch", "update-ref", "worktree", "tag", "symbolic-ref", "stash")
MOVED = "\x00moved"  # a source that marks such a push
LEADERS = ("{", "!", "if", "then", "else", "elif", "do", "while", "until", "time", "command", "builtin")
REDIRECTS = ("<", ">", ">>", ">&", "<&", "&>", ">|")
EXPANDED = ("$", "`", "*", "?", "[", "\x00")  # a word holding one is expanded as the line runs, or names no file
CONTENT_WRITE = re.compile(r"\brepos/[^/\s]+/[^/\s]+/(?:contents\b|git/(?:blobs|trees|commits)\b)|\bcreateCommitOnBranch\b")
GH_API = re.compile(r"(?:^|\s)(?:\S*/)?gh\s+api\b")
CONTENT = re.compile(r"""\bcontents?["']?\s*[:=]\s*["']?([A-Za-z0-9+/=\\]{8,})""")  # a JSON wrap arrives as \n
LOG_LINE = re.compile(r"^(?:\S+\s+)?(?=(?:INF|WRN|ERR|FTL|DBG|TRC)\b)")  # gitleaks' time stamp before its level
ANSI = re.compile(r"\x1b\[[0-9;]*m")
WRITE_TOOLS = ("push_files", "create_or_update_file")
MAIN = "refs/remotes/origin/main"  # main as the repository last fetched it, whose pins every pull request's scan reads
DEFAULT_CONFIG = "[extend]\nuseDefault = true\n"  # gitleaks' own rules, what CI runs while main has no .gitleaks.toml
PROJECT = Path(__file__).resolve().parents[2]  # the repository whose main a write's scan takes its pins from
PUSH_REMEDY = (
    "Rewrite the commit so the literal is gone (amend it, or rebase and edit it) and push again. For a reviewed false "
    "positive, mark the line `# gitleaks:allow` with its reason, or get its fingerprint pinned on main first (a pull "
    "request to main's .gitleaksignore, then `git fetch origin main`); a pin on this branch does not count, since every "
    "other pull request's `secret-scan` reads main's pins, not this branch's"
)
WRITE_REMEDY = (
    "Take the literal out and send the call again. For a reviewed false positive, mark the line `# gitleaks:allow` with "
    "its reason; no .gitleaksignore pin can cover it, since a pin names a commit, this call's commit does not exist yet, "
    "and every other pull request's `secret-scan` reads main's pins alone"
)
LATE = "the scan did not finish inside the hook's time limit"
LATE_PUSH = ("Push fewer commits at a time (`git push origin <older-sha>:refs/heads/<branch>`, then the rest), or ask the "
             "founder to push from their own terminal")
LATE_WIDENED = "Name the source and the repository literally (`git -C <dir> push origin <branch>`) and send the call again"
LATE_WRITE = "Send fewer files per call"
COMMIT_REMEDY = "Commit in one call and push in the next, so the push's scan reads the new commits"
SCAN_ERROR_REMEDY = "Fix what gitleaks names (a missing ref, an unreadable repository or file) and send the call again"
STAGE_REMEDY = "Send each file under a path that names one regular file, and send the call again"


class Late(Exception):
    """The hook's time ran out."""


def _reason(problem: str, remedy: str) -> str:
    return f"Refused by .claude/hooks/secret_scan_guard.py: {problem} {remedy} ({LESSON})."


def _left() -> float:
    left = DEADLINE - time.monotonic()
    if left <= 0:
        raise Late
    return left


def _run(args: list[str], cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, errors="replace",
                              stdin=subprocess.DEVNULL, timeout=_left())
    except subprocess.TimeoutExpired:
        raise Late from None


def _git(directory: Path, *args: str) -> str | None:
    """The output of a git command that succeeds in `directory`, else None."""
    try:
        proc = _run(["git", *args], directory)
    except OSError:  # no such directory, or no git
        return None
    return proc.stdout.strip() if proc.returncode == 0 and proc.stdout.strip() else None


@functools.lru_cache(maxsize=None)
def _binary() -> tuple[Path | None, str | None]:
    """The provisioned gitleaks, or why there is none."""
    remedy = f"Run `python3 {setup.SETUP}` (the SessionStart hook runs it at each session start) and send the call again"
    try:
        version, _archive, sha256 = setup.pin()
    except setup.SetupError as error:
        return None, _reason(
            f"this call sends commits or files that the pinned gitleaks scans first, and there is none to run: {error}.",
            f"Fix the pin as that says, run `python3 {setup.SETUP}`, and send the call again")
    folder = setup.directory(version, sha256)
    binary = setup.verified(folder)
    if binary is None:
        state = "does not match the SHA-256 recorded beside it" if (folder / "gitleaks").exists() else "is not provisioned"
        return None, _reason(
            f"this call sends commits or files that the pinned gitleaks {version} scans first, and its binary {state} "
            f"({folder}).", remedy)
    return binary, None


def _findings(report: Path, relative_to: Path | None) -> list[str]:
    """Where each finding is (file, line, rule; a commit's fingerprint), never what it matched."""
    try:
        findings = json.loads(report.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    places = []
    for finding in findings if isinstance(findings, list) else []:
        if not isinstance(finding, dict):
            continue
        path = str(finding.get("File", "?"))
        if relative_to is not None:
            path = os.path.relpath(path, relative_to)
        place = f"{path}:{finding.get('StartLine', '?')} ({finding.get('RuleID', '?')})"
        if finding.get("Commit"):
            place += f", fingerprint {finding.get('Fingerprint')}"
        places.append(place)
    return places


def _main_file(repository: Path, name: str) -> str | None:
    """`name` as main holds it in `repository`, or None when main or the file cannot be read."""
    try:
        proc = _run(["git", "show", f"{MAIN}:{name}"], repository)
    except OSError:
        return None
    return proc.stdout if proc.returncode == 0 else None


def _gitleaks(args: list[str], where: str, remedy: str, pins_from: Path, relative_to: Path | None = None) -> str | None:
    """Run the provisioned gitleaks with the job's flags, from a new empty directory, with main's pins (`-i`) and config
    (`-c`) as `pins_from` holds them; why the call must not run, or None."""
    binary, problem = _binary()
    if binary is None:
        return problem
    env = {key: value for key, value in os.environ.items() if key not in ("GITLEAKS_CONFIG", "GITLEAKS_CONFIG_TOML")}
    with tempfile.TemporaryDirectory() as temporary:
        work = Path(temporary)
        ignore, config, report = work / ".gitleaksignore", work / "config.toml", work / "report.json"
        ignore.write_text(_main_file(pins_from, ".gitleaksignore") or "", encoding="utf-8")
        config.write_text(_main_file(pins_from, ".gitleaks.toml") or DEFAULT_CONFIG, encoding="utf-8")
        try:
            proc = _run([str(binary), *args, *FLAGS, "-i", str(ignore), "-c", str(config), "--report-format", "json",
                         "--report-path", str(report)], work, env)
        except OSError as error:
            return _reason(f"the pinned gitleaks could not run on {where} ({error}).",
                           f"Provision it again with `python3 {setup.SETUP}` and send the call again")
        if proc.returncode == 0:
            return None
        places = _findings(report, relative_to)
    if places:
        shown = "; ".join(places[:5]) + (f"; and {len(places) - 5} more" if len(places) > 5 else "")
        return _reason(
            f"the pinned gitleaks (CI's `secret-scan`) found a secret-shaped literal in {where}: {shown}. Once it reaches "
            "GitHub, every pull request's `secret-scan` fails until main pins it.", remedy)
    lines = [LOG_LINE.sub("", ANSI.sub("", line)).strip() for line in proc.stderr.splitlines()]
    tail = "; ".join([line for line in lines if line][-3:])[:600]
    return _reason(f"the pinned gitleaks could not finish scanning {where} (exit {proc.returncode}: {tail}).",
                   SCAN_ERROR_REMEDY)


def _uncommented(script: str) -> str:
    """codex_mention_guard._script's output (each quoted string one single-quoted word) less its comments. That reader
    keeps a comment's words, so a commented-out GitHub write still counts there; a push named in a comment runs nothing."""
    out, index, boundary = [], 0, True
    while index < len(script):
        char = script[index]
        if char == "'":  # a single-quoted word, copied whole
            end = script.find("'", index + 1)
            end = len(script) if end < 0 else end
            out.append(script[index:end + 1])
            index, boundary = end + 1, False
        elif char == "\\":  # an escape, copied whole
            out.append(script[index:index + 2])
            index, boundary = index + 2, False
        elif char == "#" and boundary:  # a comment, to the end of its line
            end = script.find("\n", index)
            index = len(script) if end < 0 else end
        else:
            out.append(char)
            index, boundary = index + 1, char in shell.WORD_START
    return "".join(out)


def _join(here: Path | None, target: str) -> Path | None:
    """`target` from `here`, or None when the shell expands it or it starts from an unknown directory."""
    if any(char in target for char in EXPANDED):
        return None
    try:
        path = Path(target).expanduser()
    except RuntimeError:  # ~user names no user
        return None
    if not path.is_absolute():
        if here is None:
            return None
        path = here / path
    return Path(os.path.normpath(path))


def _moved(here: Path | None, verb: str, args: list[str]) -> Path | None:
    """Where `cd`, `pushd` or `popd` with these words leaves the shell; None when the line cannot say."""
    for arg in args if verb != "popd" else []:
        if arg in REDIRECTS or arg in (")", "}"):
            break
        if arg == "-" or arg.startswith("+"):  # the previous directory; a pushd stack entry
            return None
        if not arg.startswith("-"):
            return _join(here, arg)
    return Path.home() if verb == "cd" else None


def _global_options(words: list[str], index: int) -> tuple[str | None, list[tuple[str, str | None]], list[str]]:
    """After the word `git` at `index - 1`: its subcommand, its global options and the words after the subcommand."""
    options: list[tuple[str, str | None]] = []
    while index < len(words) and words[index].startswith("-"):
        if words[index] in GIT_VALUE_OPTIONS:
            options.append((words[index], words[index + 1] if index + 1 < len(words) else ""))
            index += 2
        else:
            options.append((words[index], None))
            index += 1
    return (words[index] if index < len(words) else None), options, words[index + 1:]


def _repository(here: Path | None, options: list[tuple[str, str | None]], before: list[str]) -> Path | None:
    """The directory a git command runs in, or None when its line names one the hook cannot resolve."""
    if any(word.startswith(("GIT_DIR=", "GIT_WORK_TREE=")) for word in before):
        return None
    for name, value in options:
        if name.startswith(("--git-dir", "--work-tree")):
            return None
        if name == "-C" and value:
            here = _join(here, value)
    return here


def _sent(args: list[str]) -> tuple[list[str], list[str], str | None]:
    """What a push with these words sends: rev-list options (--branches, --all, --tags) and sources to resolve; and the
    repository it names to push to, if any."""
    words, index = [], 0
    while index < len(args):  # its words less redirections and the shell's grouping
        if args[index] in REDIRECTS:
            index += 2
            continue
        if not (args[index].isdigit() and args[index + 1:index + 2] and args[index + 1] in REDIRECTS):
            if args[index] not in ("(", ")", "{", "}"):
                words.append(args[index])
        index += 1
    positional, flags, ended, index = [], set(), False, 0
    while index < len(words):
        word = words[index]
        index += 1
        if ended or not word.startswith("-") or word == "-":
            positional.append(word)
        elif word == "--":
            ended = True
        elif word.startswith("--"):
            flags.add(word.split("=", 1)[0])
            index += word in PUSH_VALUE_OPTIONS  # its value is the next word
        else:  # short options, bundled as -fu; -o takes the rest of the word or the next one
            for at, letter in enumerate(word[1:], 2):
                if letter == "o":
                    index += at == len(word)
                    break
                flags.add("-" + letter)
    if flags & SENDS_NOTHING:
        return [], [], None
    options = ["--branches"] * bool(flags & {"--all", "--branches"}) + ["--all"] * ("--mirror" in flags)
    options += ["--tags"] * ("--tags" in flags)
    specs, sources, index = positional[1:], [], 0  # the first is the repository it pushes to
    while index < len(specs):
        spec = specs[index]
        index += 1
        if spec == "tag" and index < len(specs):
            sources.append("refs/tags/" + specs[index])
            index += 1
        elif not spec.startswith("^") and (source := spec.removeprefix("+").split(":", 1)[0]):
            sources.append(source)
    if not specs and not flags & {"--all", "--branches", "--mirror"}:
        sources.append("HEAD")
    return options, sources, positional[0] if positional else None


def _pushes(script: str, base: Path) -> tuple[list[tuple[Path | None, list[str], list[str], str | None]], bool]:
    """Each `git push` the script runs, as (its directory or None, rev-list options, sources, the repository it names),
    and whether the script makes commits too. A push after a command that can move HEAD or a branch carries MOVED."""
    here: Path | None = base
    stack: list[Path | None] = []
    pushes, commits, moved = [], False, False
    for _operator, words in shell._commands(shell._command_tokens(_uncommented(script))):
        start = True
        for index, word in enumerate(words):
            if word == "(":  # a subshell or a process substitution: a move inside it ends with it
                stack.append(here)
                continue
            if word == ")":
                here = stack.pop() if stack else here
                continue
            if start and word in LEADERS:
                continue
            if start and word in ("cd", "pushd", "popd"):
                here = _moved(here, word, words[index + 1:])
            start = False
            if word == "git" or word.endswith("/git"):
                subcommand, global_options, rest = _global_options(words, index + 1)
                if subcommand in COMMITTERS:
                    commits = True
                elif subcommand in MOVERS:
                    moved = True
                elif subcommand == "push":
                    options, sources, remote = _sent(rest)
                    if moved and (options or sources):
                        sources.append(MOVED)
                    pushes.append((_repository(here, global_options, words[:index]), options, sources, remote))
    return pushes, commits


def _top(directory: Path) -> Path | None:
    """The top level of the repository `directory` is in, or its git directory when it is bare."""
    found = _git(directory, "rev-parse", "--show-toplevel") or _git(directory, "rev-parse", "--absolute-git-dir")
    return Path(found) if found else None


def _target(top: Path, remote: str | None) -> str | None:
    """The remote whose remote-tracking refs hold what a push need not send: the one it names, when that is a
    configured remote; else the pushed branch's upstream remote; else origin. None when it names a URL or a path."""
    configured = (_git(top, "remote") or "").split()
    if remote is not None:
        return remote if remote in configured else None
    branch = _git(top, "symbolic-ref", "--quiet", "--short", "HEAD")
    upstream = _git(top, "config", "--get", f"branch.{branch}.remote") if branch else None
    return upstream if upstream in configured else "origin"


def _scan_push(directory: Path | None, options: list[str], sources: list[str], remote: str | None,
               base: Path) -> tuple[Path, Path, str, str | None] | str | None:
    """The repository, its git directory and the log range a push's scan reads, and why it widened to every unpushed
    branch, if it did; a refusal when there is none to read; None for nothing."""
    top = _top(directory) if directory is not None else None
    if top is None:
        top, sources = _top(base), [""]  # read as unresolved: every branch of the working directory's repository
        if top is None:
            if directory is None:
                return _reason(
                    "this line pushes from a repository the hook cannot resolve (a variable, a substitution, `cd -`, "
                    "--git-dir or --work-tree), and the event's working directory is in none.",
                    "Name the directory literally (`git -C <dir> push ...`) and send the call again")
            return None
    revisions, unresolved = list(options), False
    for source in sources:
        commit = None if not source or source.startswith("-") or any(c in source for c in EXPANDED) else (
            _git(top, "rev-parse", "--verify", "--quiet", f"{source}^{{commit}}"))
        unresolved |= commit is None
        revisions += [commit] if commit else []
    why = None
    if unresolved:
        head = _git(top, "rev-parse", "--verify", "--quiet", "HEAD^{commit}")
        revisions += ["--branches", *([head] if head else [])]
        why = ("the line moves HEAD or a branch before it pushes" if MOVED in sources
               else "the line names a source or a repository the hook cannot resolve")
    gitdir = _git(top, "rev-parse", "--absolute-git-dir")
    if not revisions or gitdir is None:
        return None
    target = _target(top, remote)
    held = f"--remotes={target}" if target else "--remotes"
    return top, Path(gitdir), " ".join([*dict.fromkeys(revisions), "--not", held]), why


def _scan_files(files: list[tuple[str, bytes]], where: str, remedy: str) -> str | None:
    """Write each (path, content) under its path into a new temporary directory and scan it with `gitleaks dir`."""
    binary, problem = _binary()
    if binary is None:
        return problem
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary).resolve()
        staged = root / "files"  # under the directory scanned: a sent .gitleaksignore or .gitleaks.toml is only content
        for path, data in files:
            try:
                target = (staged / path).resolve()
                if staged not in target.parents:
                    return _reason(f"the path {path!r} in {where} leaves the directory it would be scanned in.",
                                   "Name each file by a path inside the repository and send the call again")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            except (OSError, ValueError) as error:
                return _reason(f"{where} could not be staged for the scan ({path!r}: {error}).", STAGE_REMEDY)
        try:
            return _gitleaks(["dir", str(root)], where, remedy, PROJECT, relative_to=staged)
        except Late:
            return _reason(f"{LATE}.", LATE_WRITE)


def _decoded(value: str) -> bytes | None:
    compact = re.sub(r"\\n|\s", "", value)
    try:
        return base64.b64decode(compact, validate=True) if len(compact) >= 8 else None
    except (binascii.Error, ValueError):
        return None


def _api_refusal(command: str, script: str, cwd: object) -> str | None:
    words = " ".join(shell._tokens(script))
    if CONTENT_WRITE.search(words) is None or (GH_API.search(words) is None and "api.github.com" not in words.lower()):
        return None
    texts = [command, *shell._files_sent(script, cwd)]
    files = [(name, text.encode("utf-8", "replace")) for name, text in
             [("command-line", command), *((f"sent-file-{n}", text) for n, text in enumerate(texts[1:], 1))]]
    decoded = []
    for index, text in enumerate(texts):
        values = [match.group(1) for match in CONTENT.finditer(text)] + [text] * bool(index)
        decoded += [data for value in values if (data := _decoded(value))]
    files += [(f"decoded-content-{n}", data) for n, data in enumerate(decoded, 1)]
    return _scan_files(files, "what this command writes to a repository", WRITE_REMEDY)


def _bash_refusal(command: str, cwd: object) -> str | None:
    plain = command.replace("\\\n", "").translate(shell.UNQUOTE)  # no quotes, backslashes or continuations
    if "push" not in plain and CONTENT_WRITE.search(plain) is None:
        return None
    script = shell._script(command)
    base = Path(cwd) if isinstance(cwd, str) and cwd else Path.cwd()
    pushes, commits = _pushes(script, base) if "push" in plain else ([], False)
    if pushes and commits:
        return _reason(
            "this line commits and pushes in one call, and a hook runs before the line, so a commit the same line "
            "makes cannot be scanned.", COMMIT_REMEDY)
    scans, why = [], None
    try:
        for directory, options, sources, remote in pushes:
            scan = _scan_push(directory, options, sources, remote, base)
            if isinstance(scan, str):
                return scan
            if scan is not None and scan not in scans:
                scans.append(scan)
        for top, gitdir, log_range, why in scans:
            where = f"the commits this push would add to {top} (`--log-opts=\"{log_range}\"`)"
            if why:
                where += f", widened to every local branch's and HEAD's because {why}; name them literally to narrow it"
            refusal_reason = _gitleaks(["git", str(gitdir), f"--log-opts={log_range}"], where, PUSH_REMEDY, top)
            if refusal_reason is not None:
                return refusal_reason
    except Late:
        if why:
            return _reason(f"{LATE}: it was widened to every local branch's commits and HEAD's, because {why}.",
                           LATE_WIDENED)
        return _reason(f"{LATE}.", LATE_PUSH)
    return _api_refusal(command, script, cwd) if CONTENT_WRITE.search(plain) else None


def _mcp_refusal(tool: str, tool_input: dict) -> str | None:
    parts = tool.split("__")
    if len(parts) < 3 or parts[0] != "mcp" or "github" not in parts[1].lower() or parts[-1] not in WRITE_TOOLS:
        return None
    entries = tool_input.get("files") if parts[-1] == "push_files" else [tool_input]
    if not isinstance(entries, list) or not all(
            isinstance(entry, dict) and isinstance(entry.get("path"), str) and isinstance(entry.get("content"), str)
            for entry in entries):
        return _reason("this GitHub write's files are not the path and content strings the scan reads.",
                       "Send each file as a path and its content and send the call again")
    files = [(entry["path"], entry["content"].encode("utf-8", "replace")) for entry in entries]
    return _scan_files(files, "the files this GitHub write commits", WRITE_REMEDY)


def refusal(event: object) -> str | None:
    """Why this tool call must not run, or None to let it through."""
    if not isinstance(event, dict):
        return None
    tool, tool_input = event.get("tool_name"), event.get("tool_input")
    if not isinstance(tool, str) or not isinstance(tool_input, dict):
        return None
    try:
        if tool == "Bash":
            command = tool_input.get("command")
            return _bash_refusal(command, event.get("cwd")) if isinstance(command, str) else None
        return _mcp_refusal(tool, tool_input)
    except Late:  # past the push and write scans, which say what to do themselves
        return _reason(f"{LATE}.", LATE_PUSH if tool == "Bash" else LATE_WRITE)


def main() -> int:
    reason = refusal(json.load(sys.stdin.buffer))
    if reason is not None:
        decision = {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": reason}
        json.dump({"hookSpecificOutput": decision}, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
