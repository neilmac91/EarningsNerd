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
checkout's: gitleaks scans `.` from a new directory of the hook's own, which holds no .gitleaksignore or .gitleaks.toml,
with `-i` holding `git show origin/main:.gitleaksignore` (empty when main or the file cannot be read, the strictest
reading), and with `-c` holding main's `.gitleaks.toml` only when main has one: while it has none, gitleaks runs its own
default rules, as the job does. Its environment holds neither variable gitleaks 8.24.3 reads a config from
(GITLEAKS_CONFIG, GITLEAKS_CONFIG_TOML). A push's scan reaches the repository through GIT_DIR, and a write's files are
staged under a subdirectory of the directory scanned, so no `.gitleaksignore` or `.gitleaks.toml` of the checkout's,
of its git directory's, or one a call sends, is honoured: a pin on a branch counts for nothing until it lands on main
and is fetched, and a reviewed false positive otherwise takes `# gitleaks:allow`.

.claude/settings.json runs it before every Bash command and every call to an MCP server whose name contains "github"
in any case. It scans
- each `git push` a Bash command line runs: a word `git`, or a path ending in `/git`, wherever it stands, then git's
  global options, then `push`, in a line read as the shell reads it (codex_mention_guard.py's reader, imported), less
  its comments. The push runs in the event's working directory as the line's `cd` and `pushd` to a directory it names
  literally move it (a subshell's move ends with the subshell; a command substitution's text is read after the rest of
  its line), then `git -C`. A move counts only where it certainly runs in the line's own shell: first in its and-or
  list (after nothing, `;`, `&`, a newline or a subshell's `(`, with any assignments and redirections before it as its
  prefixes), in no pipeline or background job, and in a line with no if, while, until, for, select, case or function;
  any other leaves the push's directory unknown. The scan is
  `gitleaks git .` with GIT_DIR=<that repository's git directory> and
  `--log-opts="<the log options> <what it sends> --not --remotes=<remote>"`: the commits reachable from what the push
  sends and from no remote-tracking ref of the remote it pushes to, which it finds as git does (the one the line names,
  by its first word or --repo; else the current branch's pushRemote, remote.pushDefault, the current branch's remote,
  then origin). Those refs count only when every URL the remote pushes to names the repository it fetches from (`git
  remote get-url`, which applies pushurl, insteadOf and pushInsteadOf; compared without scheme, user, `.git` or a
  trailing slash, an scp-like `host:path` read as `host/path`, so the https and ssh forms of one repository agree). A
  URL or a path, or a remote that pushes elsewhere than it fetches from (a fork, a mirror), may hold none of what it is
  sent, so its scan drops `--not` and reads every commit the push sends; when that outlasts the hook's time, the refusal
  says to push to a remote that fetches from there. The log options (LOG_FLAGS) and GIT_NO_REPLACE_OBJECTS=1 in
  gitleaks' environment hold `git log -p` to what CI's git prints. The user's or the repository's git config, which CI
  has none of, could otherwise hide an added line (colour, a textconv driver, an external diff, a replace ref, a root
  commit's diff that log.showRoot leaves out) or change its fingerprint (a commit header in another form under
  format.pretty, log.date, log.abbrevCommit or log.showSignature; file names without a/ and b/ under diff.noprefix).
  What it sends: each refspec's source (`tag <name>` too; a deletion or a negative refspec sends nothing), every branch
  for --all, --branches or the matching refspec `:` (of which it pushes those the remote has too), every ref for
  --mirror and every tag for --tags; a dry run and --delete send nothing. A push that names none of these sends what
  git's config says, which the hook reads as git does, with the pushing git's own -c and --config-env: the remote's
  push refspecs (remote.<name>.push), else every branch under push.default=matching, else HEAD; and a remote set to
  mirror (remote.<name>.mirror) sends every ref, as --mirror does. Its options are read in order, as git reads them, so
  a later `--no-` form takes an earlier option back. A push the hook cannot pin down is
  refused before any scan, since it could send any commit in the repository: one whose source does not resolve to a
  commit as the line stands (a variable, a substitution, a wildcard, a name that does not exist yet); one from a
  repository the hook cannot resolve (a variable, a substitution, `cd -`, popd, a move that may not run, --git-dir,
  --work-tree, GIT_DIR=, a directory no repository holds yet); one with a long option push does not take as written,
  since git takes a unique prefix of one for the whole option (`--mirr` for --mirror); and one in a line that also runs
  any other git command but a read (READS: status, log, show, diff, rev-parse and their like), before or after it,
  since a checkout, a reset, a fetch, a remote or config change, a bisect step, an alias or a subcommand the shell
  expands may change what the push sends or where it goes, and the hook resolves the push before the line runs (a
  command substitution runs before its command, though the hook reads its text after the line). Each refusal says
  what to name literally, or to push in a call of its own.
- a line that pushes and also makes commits anywhere (git am, cherry-pick, commit, commit-tree, merge, pull, rebase
  or revert): refused, since a hook runs before the line and cannot read a commit the line has yet to make. The
  commits go in one call and the push in the next.
- the GitHub MCP tools push_files and create_or_update_file: each file's content, written under its path into a new
  temporary subdirectory (a path that leaves it refuses the call), with `gitleaks dir`.
- a Bash line naming a repository's contents or git data endpoint (`repos/<owner>/<repo>/contents`, `git/blobs`,
  `git/trees`, `git/commits`) or GraphQL's createCommitOnBranch, through `gh api` or api.github.com, a read included:
  the line as written, the files its GitHub writes send (codex_mention_guard.py's detection), and, decoded, each
  base64 `content` value in either and each such file that is base64 whole, with `gitleaks dir`. A file it sends
  that the hook cannot read as the line stands (one the line itself makes, one over the reader's 1 MiB, one that is
  no regular file) refuses the call, since what the write sends would go unscanned; so does one named by a relative
  path in a line that changes directory (a cd, pushd or popd anywhere in it), since the hook reads a body file from
  the directory the call starts in.
A finding, a scan that fails (its refusal names gitleaks' error lines first) and one that outlasts the hook's time each
refuse the call. A refusal is a JSON deny on stdout naming the scan, where it found something (file, line and rule;
for a commit, its fingerprint) and what to do next, never the secret (gitleaks runs with --redact and without
--verbose); anything else exits 0 with no output. A crash exits 1, which Claude Code reports as a hook error and lets
through.

The hook stops a session's accidental push or write of a secret-shaped literal. It is no boundary against a session that
means to get past it, which can always push from a script, so it does not read forms that only such a bypass writes.

Not checked: a push or write that another shell or program makes (`bash -c '...'`, a here-document fed to a shell, a
script, a git alias such as `git p`, `gh repo create --push`, a submodule's push), a commit another program makes in the
same line, a directory a command other than cd or pushd enters (`env -C`) or a GIT_DIR the line exports, git
configuration the line sets through the environment (`GIT_CONFIG_COUNT=` before the push, an export), a
remote-tracking ref whose branch the remote has since deleted (`git fetch --prune` drops it), whose commits the scan
still counts as held, a file whose text git leaves out of `git log -p` as binary because of the repository's or the
user's settings (a `-diff` attribute in info/attributes or core.attributesFile, a diff driver set `binary = true`,
core.bigFileThreshold below the file's size; CI has none of them and scans that text; `--text` would scan it, but also
the binary files CI skips, so the hook would refuse pushes CI passes), the other way about a committed `.gitattributes`
that marks files `-diff` (CI's checkout honours it and the hook reads none, so it can refuse a push CI passes), a fork
layout, where CI reads the main of another remote than origin (the pins come from origin/main alone), text a command
builds as it runs (`content="$(base64 -w0 file)"`), a word an ANSI-C escape spells (`$'pu\\x73h'`), a JSON key an
escape spells (`"cont\\u0065nt"`, which no JSON writer emits), a GitHub MCP server registered under a name without
"github", a session that loads no repository hooks, and a person's own push.
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
# git push's long options as `git push -h` lists them (each also as `--no-<name>`), and the help it reads itself. Git
# takes a unique prefix of one for the whole option, which the hook does not complete: such a push is refused.
PUSH_OPTIONS = frozenset({
    "--verbose", "--quiet", "--repo", "--all", "--branches", "--mirror", "--delete", "--tags", "--dry-run",
    "--porcelain", "--force", "--force-with-lease", "--force-if-includes", "--recurse-submodules", "--thin",
    "--receive-pack", "--exec", "--set-upstream", "--progress", "--prune", "--no-verify", "--verify", "--follow-tags",
    "--signed", "--atomic", "--push-option", "--ipv4", "--ipv6", "--help", "--help-all"})
SHORT_OPTIONS = {"v": "--verbose", "q": "--quiet", "d": "--delete", "n": "--dry-run", "f": "--force",
                 "u": "--set-upstream", "4": "--ipv4", "6": "--ipv6"}
ALIASES = {"--branches": "--all"}
SENDS_NOTHING = {"--dry-run", "--delete"}
UNREAD_OPTION = "\x00option "  # a source that marks a push naming a long option git would complete, which is refused
CONTROL = ("if", "then", "else", "elif", "fi", "while", "until", "for", "select", "do", "done", "case", "esac",
           "function")
COMMITTERS = ("am", "cherry-pick", "commit", "commit-tree", "merge", "pull", "rebase", "revert")
# Git subcommands that only read the repository, which a line that pushes may run beside its push. Any other may change
# what the push sends or where it goes after the hook has resolved it (a checkout, a reset, a fetch, a remote or config
# change, a bisect step, an alias, a subcommand the shell expands), so a push beside one is refused.
READS = ("status", "log", "show", "diff", "rev-parse", "rev-list", "ls-files", "ls-tree", "ls-remote", "cat-file",
         "describe", "shortlog", "blame", "annotate", "grep", "show-ref", "show-branch", "for-each-ref", "merge-base",
         "name-rev", "cherry", "range-diff", "diff-tree", "diff-index", "diff-files", "whatchanged", "check-ignore",
         "check-attr", "check-ref-format", "verify-commit", "verify-tag", "count-objects", "var", "version", "help")
MOVED = "\x00moved"  # a source that marks such a push, which is refused: the hook cannot tell what it sends
DEFAULT = "\x00default"  # a source that marks a push naming nothing to send, which sends what git's config says
ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\[[^]]*\])?\+?=")  # `NAME=value` before a command, a prefix
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
CONFIG_VARIABLES = ("GITLEAKS_CONFIG", "GITLEAKS_CONFIG_TOML")  # gitleaks 8.24.3 reads a config from these without -c
# What `git log -p` would otherwise take from the user's or the repository's git config, which CI has none of: colour
# codes that keep gitleaks from reading an added line, a textconv driver's or an external diff's text in its place, a
# root commit's diff left out (log.showRoot), and a header or file names that gitleaks reads another fingerprint from,
# or none (format.pretty, log.date, log.abbrevCommit, log.showSignature, diff.noprefix).
LOG_FLAGS = ("--no-color", "--no-textconv", "--no-ext-diff", "--root", "--pretty=medium", "--date=default",
             "--no-abbrev-commit", "--no-show-signature", "--src-prefix=a/", "--dst-prefix=b/")
STAGED = "files"  # the subdirectory of a files scan's directory that the sent files are written under
PROJECT = Path(__file__).resolve().parents[2]  # the repository whose main a write's scan takes its pins from
PUSH_REMEDY = (
    "Rewrite the commit so the literal is gone (amend it, or rebase and edit it) and push again. For a reviewed false "
    "positive, mark the line `# gitleaks:allow` with its reason, or get its fingerprint pinned on main first (a pull "
    "request to main's .gitleaksignore, then `git fetch origin main`); a pin on this branch does not count, since every "
    "other pull request's `secret-scan` reads main's pins, not this branch's"
)
WRITE_REMEDY = (
    "Take the literal out and send the call again. For a reviewed false positive, mark the line `# gitleaks:allow` with "
    "its reason, or commit the file and push it with git, whose scan reads main's pins (a commit's, and a global "
    "`path:rule:line` one): this scan reads each file under a staging directory, not at the repository path a pin names"
)
LATE = "the scan did not finish inside the hook's time limit"
LATE_PUSH = ("Push fewer commits at a time (`git push origin <older-sha>:refs/heads/<branch>`, then the rest), or ask the "
             "founder to push from their own terminal")
LATE_UNHELD = ("Push to a remote by its name, one that fetches from where it pushes (`git remote add <name> <url>`, "
               "then `git fetch <name>`), so the scan leaves out what that repository holds; to a new repository, "
               "push older commits first (`git push <name> <older-sha>:refs/heads/<branch>`), then the rest")
MOVED_REMEDY = "Run the line without its push, then push in a call of its own"
SOURCE_REMEDY = ("Name each source literally, as a branch, a tag or a commit that exists before the line runs, and "
                 "send the call again")
REPOSITORY_REMEDY = ("Name the directory literally (`git -C <dir> push ...`), in a repository that exists before the "
                     "line runs, and send the call again")
OPTION_REMEDY = "Spell each of `git push`'s options in full, as `git push -h` lists them, and send the call again"
LATE_WRITE = "Send fewer files per call"
COMMIT_REMEDY = "Commit in one call and push in the next, so the push's scan reads the new commits"
SCAN_ERROR_REMEDY = "Fix what gitleaks names (a missing ref, an unreadable repository or file) and send the call again"
STAGE_REMEDY = "Send each file under a path that names one regular file, and send the call again"
MOVED_BODY_REMEDY = ("Name each body file by its absolute path, or change directory in an earlier call (the next call "
                     "starts there), and send the call again")
UNREAD_REMEDY = ("Write the body in an earlier call, keep it to 1 MiB, and send it in a call of its own; for a larger "
                 "file, commit it and push it with git, whose scan reads commits of any size")


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


def _findings(report: Path) -> list[str]:
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
        if not finding.get("Commit"):  # a sent file, which a files scan reads under STAGED
            path = path.removeprefix(f"{STAGED}/")
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


def _gitleaks(args: list[str], where: str, remedy: str, pins_from: Path, source: Path | None = None,
              gitdir: Path | None = None) -> str | None:
    """Run the provisioned gitleaks with the job's flags in `source` (by default a new directory of its own), which
    `args` name as `.` and which holds no .gitleaksignore or .gitleaks.toml, with main's pins (`-i`) and, only when
    main has one, main's config (`-c`; else gitleaks' own default, as the job runs) as `pins_from` holds them, and none
    of CONFIG_VARIABLES; a commit scan reads `gitdir` through GIT_DIR, with replace refs off. Why the call must not
    run, or None."""
    binary, problem = _binary()
    if binary is None:
        return problem
    env = {key: value for key, value in os.environ.items() if key not in CONFIG_VARIABLES}
    if gitdir is not None:
        env.update(GIT_DIR=str(gitdir), GIT_NO_REPLACE_OBJECTS="1")
    with tempfile.TemporaryDirectory() as temporary:
        work = Path(temporary)
        ignore, config, report = work / "main.gitleaksignore", work / "main.gitleaks.toml", work / "report.json"
        ignore.write_text(_main_file(pins_from, ".gitleaksignore") or "", encoding="utf-8")
        options = ["-i", str(ignore)]
        if (main_config := _main_file(pins_from, ".gitleaks.toml")) is not None:
            config.write_text(main_config, encoding="utf-8")
            options += ["-c", str(config)]
        try:
            proc = _run([str(binary), *args, *FLAGS, *options, "--report-format", "json", "--report-path", str(report)],
                        source or work, env)
        except OSError as error:
            return _reason(f"the pinned gitleaks could not run on {where} ({error}).",
                           f"Provision it again with `python3 {setup.SETUP}` and send the call again")
        if proc.returncode == 0:
            return None
        places = _findings(report)
    if places:
        shown = "; ".join(places[:5]) + (f"; and {len(places) - 5} more" if len(places) > 5 else "")
        return _reason(
            f"the pinned gitleaks (CI's `secret-scan`) found a secret-shaped literal in {where}: {shown}. Once it reaches "
            "GitHub, every pull request's `secret-scan` fails until main pins it.", remedy)
    # gitleaks ends a failed scan with three WRN lines (scanned, partial scan, no leaks in it): its ERR and FTL lines
    # name the cause, so they come first, then the last lines.
    lines = [line for line in (LOG_LINE.sub("", ANSI.sub("", line)).strip() for line in proc.stderr.splitlines()) if line]
    causes = [line for line in lines if line.startswith(("ERR", "FTL"))]
    tail = "; ".join(dict.fromkeys(causes[:3] + lines[-3:]))[:600]
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
    repository it names to push to, if any: its first word that is no option, else --repo's value, as git takes it. Its
    options are read in order, as git reads them, so `--no-dry-run` after `--dry-run` takes the dry run back. A long
    option push does not take as written, such as `--mirr`, which git completes to --mirror, leaves only an
    UNREAD_OPTION source, which is refused."""
    words, index = [], 0
    while index < len(args):  # its words less redirections and the shell's grouping
        if args[index] in REDIRECTS:
            index += 2
            continue
        if not (args[index].isdigit() and args[index + 1:index + 2] and args[index + 1] in REDIRECTS):
            if args[index] not in ("(", ")", "{", "}"):
                words.append(args[index])
        index += 1
    positional, flags, ended, index, repo = [], set(), False, 0, None
    while index < len(words):
        word = words[index]
        index += 1
        if ended or not word.startswith("-") or word == "-":
            positional.append(word)
        elif word == "--":
            ended = True
        elif word.startswith("--"):
            name, _, value = word.partition("=")
            negated = "--" + name[5:] if name.startswith("--no-") and name not in PUSH_OPTIONS else None
            if (negated or name) not in PUSH_OPTIONS:  # an abbreviation git would complete, or no option of push's
                return [], [UNREAD_OPTION + name], repo
            if negated:  # it takes the option back
                flags.discard(ALIASES.get(negated, negated))
                repo = None if negated == "--repo" else repo
                continue
            flags.add(ALIASES.get(name, name))
            if word in PUSH_VALUE_OPTIONS:  # its value is the next word
                value = words[index] if index < len(words) else ""
                index += 1
            repo = value if name == "--repo" else repo
        else:  # short options, bundled as -fu; -o takes the rest of the word or the next one
            for at, letter in enumerate(word[1:], 2):
                if letter == "o":
                    index += at == len(word)
                    break
                flags.add(SHORT_OPTIONS.get(letter, "-" + letter))
    if flags & SENDS_NOTHING:
        return [], [], None
    options = ["--branches"] * ("--all" in flags) + ["--all"] * ("--mirror" in flags)
    options += ["--tags"] * ("--tags" in flags)
    specs = positional[1:]  # the first is the repository it pushes to
    more, sources = _specs(specs)
    if not specs and not flags & {"--all", "--mirror", "--tags"}:  # it names nothing: git's config says what it sends
        sources.append(DEFAULT)
    return [*options, *(option for option in more if option not in options)], sources, (
        positional[0] if positional else repo)


def _specs(specs: list[str]) -> tuple[list[str], list[str]]:
    """The rev-list options and the sources these refspecs send: each one's source (`tag <name>` too; a deletion or a
    negative refspec sends nothing), and every branch for the matching refspec `:`, which sends each branch the remote
    has of the same name."""
    options, sources, index = [], [], 0
    while index < len(specs):
        spec = specs[index]
        index += 1
        if spec == "tag" and index < len(specs):
            sources.append("refs/tags/" + specs[index])
            index += 1
        elif spec.removeprefix("+") == ":":
            options = ["--branches"]
        elif not spec.startswith("^") and (source := spec.removeprefix("+").split(":", 1)[0]):
            sources.append(source)
    return options, sources


def _pushes(script: str, base: Path) -> tuple[list[tuple[Path | None, list[str], list[str], str | None, list[str]]],
                                             bool]:
    """Each `git push` the script runs, as (its directory or None, rev-list options, sources, the repository it names,
    the -c and --config-env options its git takes), and whether the script makes commits too. A push in a script that
    runs a command that can move HEAD or a branch, anywhere, carries MOVED: a command substitution runs before the
    command it is part of, though its text is read after the line, so the order the reader sees is not the order the
    shell runs."""
    here: Path | None = base
    stack: list[Path | None] = []
    pushes, commits, moved = [], False, False
    commands = shell._commands(shell._command_tokens(_uncommented(script)))
    branching = any(_branches(words) for _operator, words in commands)
    for at, (operator, words) in enumerate(commands):
        after = commands[at + 1][0] if at + 1 < len(commands) else None
        start, first, skip = True, operator in (None, ";", "&"), 0  # whether it begins its and-or list
        for index, word in enumerate(words):
            if skip:  # a prefix redirection's target
                skip -= 1
                continue
            if word == "(":  # a subshell or a process substitution: a move inside it ends with it
                stack.append(here)
                first = True
                continue
            if word == ")":
                here = stack.pop() if stack else here
                continue
            if start and (word in LEADERS or ASSIGNMENT.match(word)):
                continue
            if start and (word in REDIRECTS or (
                    word.isdigit() and index + 1 < len(words) and words[index + 1] in REDIRECTS)):
                skip = 1 if word in REDIRECTS else 2  # `>file cd ...`, `2>/dev/null cd ...`: the command comes after
                continue
            if word in ("cd", "pushd", "popd") and (start or branching):
                # A move that may not run where it stands (after && or ||, in a pipeline or a background job, or in a
                # line that branches) leaves the directory unknown: the shell may run what follows from either.
                certain = start and first and not branching and after not in ("|", "|&", "&")
                here = _moved(here, word, words[index + 1:]) if certain else None
            start = False
            if word == "git" or word.endswith("/git"):
                subcommand, global_options, rest = _global_options(words, index + 1)
                if subcommand in COMMITTERS:
                    commits = True
                elif subcommand == "push":
                    options, sources, remote = _sent(rest)
                    config = [word for name, value in global_options if name == "-c" or name.startswith("--config-env")
                              for word in (name, value) if word is not None]
                    pushes.append((_repository(here, global_options, words[:index]), options, sources, remote, config))
                elif subcommand is not None and subcommand not in READS:
                    moved = True
    for _directory, options, sources, _remote, _config in pushes if moved else []:  # wherever the move stands
        if options or sources:
            sources.append(MOVED)
    return pushes, commits


def _branches(words: list[str]) -> bool:
    """Whether this command opens, continues or closes an if, while, until, for, select or case, or defines a
    function: a move in a line that has one may run, or not, wherever the line's text puts it."""
    first = next((word for word in words if word not in ("(", "{", "!", "time", "command", "builtin")), None)
    return first in CONTROL or any(word == "(" and words[at + 1:at + 2] == [")"] for at, word in enumerate(words))


def _top(directory: Path, config: list[str]) -> Path | None:
    """The top level of the repository `directory` is in, or its git directory when it is bare."""
    found = (_git(directory, *config, "rev-parse", "--show-toplevel")
             or _git(directory, *config, "rev-parse", "--absolute-git-dir"))
    return Path(found) if found else None


def _destination(top: Path, remote: str | None, config: list[str]) -> str:
    """Where a push goes, found as git finds it: the repository the line names; else the current branch's pushRemote,
    remote.pushDefault, the current branch's remote, then origin."""
    if remote is not None:
        return remote
    branch = _git(top, *config, "symbolic-ref", "--quiet", "--short", "HEAD")
    keys = [f"branch.{branch}.pushRemote", "remote.pushDefault", f"branch.{branch}.remote"]
    if branch is None:  # a detached HEAD: no branch keys
        keys = keys[1:2]
    return next((value for key in keys if (value := _git(top, *config, "config", "--get", key))), "origin")


def _held(top: Path, destination: str, config: list[str]) -> str | None:
    """The remote whose remote-tracking refs show what `destination` holds: itself, when it is a configured remote
    that pushes only to the repository it fetches from. None for a URL or a path, or a remote that pushes elsewhere (a
    fork, a mirror), whose fetched refs say nothing of what the push's destination holds."""
    if destination not in (_git(top, *config, "remote") or "").split():
        return None
    fetched = _git(top, *config, "remote", "get-url", destination)
    pushed = (_git(top, *config, "remote", "get-url", "--push", "--all", destination) or "").splitlines()
    if fetched is None or {_repository_url(url) for url in pushed} != {_repository_url(fetched)}:
        return None
    return destination


def _repository_url(url: str) -> str:
    """The repository a URL or a path names, written so that its forms compare equal: without the scheme, the user,
    `.git` or a trailing slash, an scp-like `host:path` read as `host/path`, and the host in lower case."""
    text, schemed = re.subn(r"^[A-Za-z][A-Za-z0-9+.-]*://", "", url.strip())
    if not schemed and re.match(r"[^/]*:", text):  # scp-like: [user@]host:path
        text = text.replace(":", "/", 1)
    host, _, path = re.sub(r"^[^/@]*@", "", text).partition("/")
    return f"{host.lower()}/{path.rstrip('/').removesuffix('.git')}"


def _scan_push(directory: Path | None, options: list[str], sources: list[str], remote: str | None,
               config: list[str]) -> tuple[Path, Path, str, str | None] | str | None:
    """The repository, its git directory and the log range a push's scan reads, and where the push goes when no
    remote's fetched refs show what that holds (the range then leaves nothing out); a refusal when the hook cannot tell
    what the push sends, which could then be any commit in the repository; None when it sends nothing. Its git reads
    `config`, the pushing git's own -c and --config-env, as that git does."""
    if not options and not sources:
        return None
    unread = next((source.removeprefix(UNREAD_OPTION) for source in sources if source.startswith(UNREAD_OPTION)), None)
    if unread is not None:
        return _reason(
            f"this push names {unread!r}, which `git push` does not take as written: git takes a unique prefix of a "
            "long option for the whole option (`--mirr` for --mirror, `--no-dry` for --no-dry-run), so the hook cannot "
            "tell what the push would send.", OPTION_REMEDY)
    top = _top(directory, config) if directory is not None else None
    gitdir = _git(top, *config, "rev-parse", "--absolute-git-dir") if top is not None else None
    if top is None or gitdir is None:
        return _reason(
            "this line pushes from a repository the hook cannot resolve as the line stands (a variable, a "
            "substitution, `cd -`, popd, a cd or pushd that may not run where it stands, --git-dir, --work-tree, "
            "GIT_DIR=, or a directory no repository holds yet), so it cannot tell what the push would send.",
            REPOSITORY_REMEDY)
    destination, configured = _destination(top, remote, config), []
    if _git(top, *config, "config", "--type=bool", "--get", f"remote.{destination}.mirror") == "true":
        options = [*options, "--all"]  # it mirrors every ref, as --mirror does
    elif DEFAULT in sources:  # it names nothing to send: what the remote's push refspecs say, else push.default's
        configured = (_git(top, *config, "config", "--get-all", f"remote.{destination}.push") or "").splitlines()
        matching = _git(top, *config, "config", "--get", "push.default") == "matching"
        more, named = _specs(configured or [":" if matching else "HEAD"])
        options, sources = [*options, *more], [*sources, *named]
    revisions = list(options)
    for source in (source for source in sources if source not in (MOVED, DEFAULT) and
                   not source.startswith(UNREAD_OPTION)):
        commit = None if source.startswith("-") or any(char in source for char in EXPANDED) else (
            _git(top, *config, "rev-parse", "--verify", "--quiet", f"{source}^{{commit}}"))
        if commit is None:
            given = f" (remote.{destination}.push configures it)" if configured else ""
            return _reason(
                f"this push sends {source!r}{given}, which the hook cannot resolve to a commit as the line stands (a "
                "variable, a substitution, a wildcard, or a name that does not exist yet), so it cannot tell what the "
                "push would send.", SOURCE_REMEDY)
        revisions.append(commit)
    if MOVED in sources:
        return _reason("this line runs another git command beside its push, one that may change what the push sends or "
                       "where it goes (anything but a read such as status, log, show or diff), and the hook resolves "
                       "the push before the line runs, so it cannot tell what this push would send.", MOVED_REMEDY)
    held = _held(top, destination, config)
    log_range = " ".join([*LOG_FLAGS, *dict.fromkeys(revisions), *(["--not", f"--remotes={held}"] if held else [])])
    return top, Path(gitdir), log_range, None if held else destination


def _scan_files(files: list[tuple[str, bytes]], where: str, remedy: str) -> str | None:
    """Write each (path, content) under its path into STAGED in a new temporary directory and scan that directory with
    `gitleaks dir .`, so a finding's path, and its fingerprint, is `files/<path>`."""
    binary, problem = _binary()
    if binary is None:
        return problem
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary).resolve()
        staged = root / STAGED  # under the directory scanned: a sent .gitleaksignore or .gitleaks.toml is only content
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
            return _gitleaks(["dir", "."], where, remedy, PROJECT, root)
        except Late:
            return _reason(f"{LATE}.", LATE_WRITE)


def _decoded(value: str) -> bytes | None:
    """A base64 `content` value decoded, its JSON string escapes (`\\/`, `\\n`, `\\u002f`) read first, as GitHub
    reads them; a value that is no JSON string is read as written."""
    if "\\" in value:
        try:
            value = json.loads(f'"{value}"')
        except ValueError:
            pass
    compact = re.sub(r"\\n|\s", "", value)
    try:
        return base64.b64decode(compact, validate=True) if len(compact) >= 8 else None
    except (binascii.Error, ValueError):
        return None


def _api_refusal(command: str, script: str, cwd: object) -> str | None:
    words = " ".join(shell._tokens(script))
    if CONTENT_WRITE.search(words) is None or (GH_API.search(words) is None and "api.github.com" not in words.lower()):
        return None
    texts, moved = [command], _changes_directory(script)
    for name in shell._names_sent(script):
        if moved and not os.path.isabs(os.path.expanduser(name)):
            return _reason(f"this line changes directory and sends {name!r}, a relative path, as a body, and the hook "
                           "reads a body file from the directory the call starts in, so it cannot tell which file the "
                           "write sends.", MOVED_BODY_REMEDY)
        text = shell._read_sent(name, cwd)
        if text is None:  # a body the scan cannot read would go unscanned
            return _reason(f"this command sends {name!r} as a body, and the hook cannot read it as the line stands "
                           "(the line itself makes it, it is over 1 MiB, or it is no regular file), so what the "
                           "write sends cannot be scanned.", UNREAD_REMEDY)
        texts.append(text)
    files = [(name, text.encode("utf-8", "replace")) for name, text in
             [("command-line", command), *((f"sent-file-{n}", text) for n, text in enumerate(texts[1:], 1))]]
    decoded = []
    for index, text in enumerate(texts):
        values = [match.group(1) for match in CONTENT.finditer(text)] + [text] * bool(index)
        decoded += [data for value in values if (data := _decoded(value))]
    files += [(f"decoded-content-{n}", data) for n, data in enumerate(decoded, 1)]
    return _scan_files(files, "what this command writes to a repository", WRITE_REMEDY)


def _changes_directory(script: str) -> bool:
    """Whether the script may change its directory: a cd, pushd or popd anywhere in it, whatever the order the reader
    gives its commands."""
    commands = shell._commands(shell._command_tokens(_uncommented(script)))
    return any(word in ("cd", "pushd", "popd") for _operator, words in commands for word in words)


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
    scans, unheld = [], None
    try:
        for directory, options, sources, remote, config in pushes:
            scan = _scan_push(directory, options, sources, remote, config)
            if isinstance(scan, str):
                return scan
            if scan is not None and scan not in scans:
                scans.append(scan)
        for top, gitdir, log_range, unheld in scans:
            where = f"the commits this push would add to {top} (`--log-opts=\"{log_range}\"`)"
            if unheld:
                where += f", every one it sends, since no remote's fetched refs show what {unheld!r} holds"
            refusal_reason = _gitleaks(["git", ".", f"--log-opts={log_range}"], where, PUSH_REMEDY, top, gitdir=gitdir)
            if refusal_reason is not None:
                return refusal_reason
    except Late:
        if unheld:
            return _reason(f"{LATE}: it read every commit the push sends, since no remote's fetched refs show what "
                           f"{unheld!r} holds.", LATE_UNHELD)
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
