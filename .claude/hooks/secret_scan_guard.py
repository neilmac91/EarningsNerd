"""PreToolUse hook: refuse a push or a GitHub content write when CI's pinned gitleaks finds a secret-shaped
literal in the commits it would add (E126).

The gate for lessons/ops-a-secret-shaped-literal-on-any-branch-fails-every-pr.md. CI's `secret-scan` job reads
every branch, so a secret-shaped literal pushed to any branch fails every pull request's scan until it leaves
the branch history or main pins it. This hook runs the job's gitleaks first (the version and archive SHA-256
that its GITLEAKS_VERSION and GITLEAKS_SHA256 name in .github/workflows/ci.yml) over the commits a call would
add to GitHub, and refuses the call on a finding.

.claude/settings.json runs it before every Bash command and every call to an MCP server whose name contains
"github" in any case. It reads
- each `git push` in a Bash command, as codex_mention_guard.py's shell reader reads the line: `git` as a word
  or a path ending in `/git`, in any case, wherever it stands (among a wrapper's words, `env -C` followed, or
  another command's), its global options, an alias (from `-c alias.<name>=...` or the config of the repository
  git runs in; a `!` alias as the commands it runs), and the strings that `bash -c` (its other options
  skipped), `eval` and `trap` run (a trap's at the end of its shell), each function where it is called and
  each command substitution, as commands of their own. The scan reads the commits the push would add: those
  reachable from what it sends and from no ref under refs/remotes/origin, which stands for GitHub as last
  fetched. It sends each refspec's source (`+` dropped, the part before the last `:`; `tag <name>` is that
  tag), named as git push names it, through replace refs and past them, in the repository the push runs in
  (`cd` with the HOME, CDPATH and OLDPWD the call sets, `pushd` and `popd` with their stack, `-C`,
  `--git-dir` and an exported or prefixed GIT_DIR with a literal path are followed); `--all`, `--branches`,
  `--mirror` and `--tags` their refs (abbreviated or negated as git reads them); with no refspec, HEAD, or
  every branch when `push.default` is matching or a `remote.<name>.push` or `remote.<name>.mirror` is set. A
  push whose words the hook cannot read whole (a source no ref names, a pattern outside refs/, a word holding
  `$`, backquotes in the call, settings the call gives git through a GIT_CONFIG* variable, --config-env, HOME
  or XDG_CONFIG_HOME, the words xargs or another command may add, a chain of more than five plain aliases) is
  read as sending HEAD and every branch and tag, and so is a git command it does not know (another program's
  `git-<name>`, an alias the call defines first), which may also make commits. A dry run, a delete and a
  refspec with no source send nothing.
- what comes before a push in its call. The hook runs before the call and reads the commits as they stand then,
  so before a push, or beside it (in its pipeline, after it while it runs in the background, in a loop around it,
  in a trap or a substitution; a subshell, group, loop, if or case counts as one command of the pipeline it
  stands in, as does a nested shell), only cd, pushd, popd, the shell's plain builtins, reads and filters that
  write no file and run no other program (cat, head, tail, grep, cut, wc, ls, jq and the like) and git commands
  that change no commit, ref or setting may run. A redirection that writes a file (one that is no device such as
  /dev/null; the push's own output may go to a file) makes its command a write, and so do settings or an option
  with which a git read may run a program or write a file (`-c`, a GIT_* variable or HOME the call sets,
  `--output`, grep's `-O`, ls-remote's `--upload-pack`, archive's `--remote`, `add -e`). A push after anything
  else (`git commit ... && git push`, a test run, a fetch), a push from a directory the hook cannot name (or with
  a ref store, object store or namespace the call moves: GIT_COMMON_DIR, GIT_OBJECT_DIRECTORY,
  GIT_ALTERNATE_OBJECT_DIRECTORIES, GIT_NAMESPACE, --namespace), the pushes it does not read (`git subtree push`,
  `git send-pack`, `git http-push`) and a line nested more than five levels deep (shells, evals, traps,
  functions, `!` aliases, process substitutions) are refused.
- each `content` string a GitHub MCP call sends (push_files, create_or_update_file), at any depth, with the
  `path` beside it: the hook builds the commit the call would make on the tip of its branch as last fetched
  (main's when it names none), in a scratch object store, and scans that commit as CI will, its added lines
  alone. A branch not fetched, or another repository, gets the files committed whole; a path sent twice is
  refused.
- a write to a repository's contents or git data through GitHub's API (`gh api`, or curl to api.github.com:
  a PUT to contents, a POST to git/blobs, git/trees or git/commits, a GraphQL createCommitOnBranch, inline or
  in a file the command names), which it refuses outright: its content takes too many forms to read before it
  runs, and git push and the MCP tools carry the same change through the scan.
The scan is `gitleaks git` over the repository's git directory with main's .gitleaksignore and, if main has
one, its .gitleaks.toml (main: origin/HEAD, else origin/main, else origin/master; with none fetched, no pin
reaches the scan). Its git and gitleaks read none of the session's GITLEAKS_* or GIT_* variables, no system
or global git configuration and no replace ref, and hold the settings that change what `git log -p` prints
at git's defaults, as on CI's runner (SCAN_CONFIG). gitleaks also reads the scanned directory's own
.gitleaksignore and .gitleaks.toml, and the git directory holds neither, so a pin or rule only the branch
carries reaches this scan no more than it reaches other pull requests' runs.

The binary is installed once per machine and pin with `python3 .claude/hooks/secret_scan_guard.py --install`
under ~/.cache (or XDG_CACHE_HOME): the linux x64 release archive checked against that SHA-256, another
platform's against the release's checksums file once that file lists the pin for the linux archive. The hook
never downloads. A refusal is a JSON deny on stdout; a call the hook lets through exits 0 with no output.
Once the hook knows a call adds commits, it fails closed: a missing binary, an unreadable pin, a scan that
fails, errs or outlasts 50 seconds (the registration allows 60) refuses the call. So does a line or an input
nested past Python's own limits. Any other error in reading the command exits 1, which Claude Code reports
as a hook error and lets the call through, as it does for codex_mention_guard.py: a guardrail, not a boundary.

Not checked: a push a script, a program or a shell's standard input runs; a git that a variable, a
substitution, an escape or a shell alias or function names (`$GIT push`, `$(which git) push`,
`$'\\x67it' push`, `g push`); a GIT_DIR, HOME or CDPATH the shell's profile sets; a command substitution
inside an unquoted here-document's text, and a `$((` that bash reads as a command substitution; the commits
a git command the hook does not know makes as it runs, and a program the repository's own configuration has
a git read run (an fsmonitor, a textconv or clean filter); the commits a push sends to submodules
(--recurse-submodules); a commit a stale ref under refs/remotes/origin still holds (one a force-push took off
GitHub), and an MCP write to a branch fetched before it changed; attributes the repository's own
info/attributes sets; a squash or rebase merge of a pull request whose net change still holds a line pinned
only by its branch commit; content another program sends through GitHub's API, a URL a variable holds, and a
GraphQL mutation read from standard input or a variable; a GitHub MCP server registered under a name without
"github"; a session that loads no repository hooks; and a person's own push.
Tests: backend/tests/unit/test_secret_scan_guard.py.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import NamedTuple

# The hook runs before every Bash command, so the modules only a scan or --install needs load where they are used.

ROOT = Path(__file__).resolve().parents[2]
CI = ROOT / ".github" / "workflows" / "ci.yml"
LESSON = "lessons/ops-a-secret-shaped-literal-on-any-branch-fails-every-pr.md"
RELEASE = "https://github.com/gitleaks/gitleaks/releases/download/v{0}/{1}"
ARCHES = {"x86_64": "x64", "amd64": "x64", "aarch64": "arm64", "arm64": "arm64"}
# The whole check's time: .claude/settings.json allows the hook 60 seconds, past which Claude Code
# reports a hook error and lets the call through, so the scan ends first and refuses.
DEADLINE = 50.0
LEAKS = 3  # the exit code gitleaks is given for a finding; its own error is 1
REMOTE = "origin"  # the remote that stands for GitHub: its refs are GitHub's branches as last fetched
MAIN_REFS = (f"refs/remotes/{REMOTE}/HEAD", f"refs/remotes/{REMOTE}/main", f"refs/remotes/{REMOTE}/master")
MAX_FINDINGS = 10  # listed in a refusal; the rest are counted
MAX_DEPTH = 5  # levels of shells, evals, traps, functions, `!` aliases and process substitutions; a deeper line is
# refused, and a longer chain of plain aliases is read whole
MAX_FILE_BYTES = 1 << 20  # a file a GraphQL write reads its mutation from is read up to this size
SCRATCH = {  # who the scratch commit of an MCP write is by: commit-tree needs a name
    "GIT_AUTHOR_NAME": "secret-scan-guard", "GIT_AUTHOR_EMAIL": "secret-scan-guard@localhost",
    "GIT_COMMITTER_NAME": "secret-scan-guard", "GIT_COMMITTER_EMAIL": "secret-scan-guard@localhost",
}
# The scan's own git reads no system or global configuration file, and holds these settings at git's defaults, as
# CI's runner has them, over the repository's own. Each changes what `git log -p` prints: colour, a binary file by
# its size (core.bigFileThreshold), a root commit's lines (log.showRoot), an attributes file, copies shown as
# differences (diff.renames) and a replace ref hide lines; an abbreviated or missing commit gives a finding a
# fingerprint main's pins do not match; a signature git cannot check, and a graft file's hint, fail the scan, as
# they should. The rest (decorations and prefixes among them, which gitleaks reads past) keep the output as CI's
# scan sees it. safe.directory lets the scan read a checkout another user owns, which the global configuration it
# does not read may have listed.
SCAN_CONFIG = (
    ("color.diff", "never"), ("log.showSignature", "false"), ("log.decorate", "no"),
    ("log.abbrevCommit", "false"), ("log.date", "default"), ("log.showRoot", "true"), ("format.pretty", "medium"),
    ("i18n.logOutputEncoding", "UTF-8"), ("diff.noprefix", "false"), ("diff.mnemonicPrefix", "false"),
    ("diff.srcPrefix", "a/"), ("diff.dstPrefix", "b/"), ("diff.relative", "false"), ("diff.renames", "true"),
    ("diff.renameLimit", "1000"), ("diff.algorithm", "myers"), ("diff.indentHeuristic", "true"),
    ("diff.interHunkContext", "0"), ("diff.submodule", "short"), ("core.bigFileThreshold", "512m"),
    ("core.useReplaceRefs", "false"), ("advice.graftFileDeprecated", "true"), ("core.attributesFile", os.devnull),
    ("core.quotePath", "true"), ("safe.directory", "*"),
)

SHELLS = ("sh", "bash", "zsh", "dash", "ksh")
# Words that run the command after them; a push they hold is read wherever its git word stands.
WRAPPERS = ("sudo", "env", "command", "exec", "time", "nice", "nohup", "timeout", "stdbuf", "xargs", "builtin")
# The shell's words that open and close a compound command, and the ones that only part it.
OPENERS = ("{", "if", "while", "until", "for", "select", "case")
CLOSERS = ("}", "fi", "done", "esac")
PARTS = ("!", "then", "else", "elif", "do")
LOOPS = ("while", "until", "for", "select")
HEADERS = ("for", "select", "case")  # the rest of a header's words run no command
REDIRECTS = ("<", ">", ">>", ">&", "<&", "&>", ">|", "<>", "<<", "<<<")
# The redirections that open a file to write (any command given one is a write, unless it is the push itself), and
# the files they may name and still write nothing a push reads.
WRITES = (">", ">>", ">|", "&>", "&>>", "<>", ">&")
DEVICES = ("/dev/null", "/dev/stdout", "/dev/stderr", "/dev/tty")
# Commands that cannot make or move a commit, a ref or HEAD, write a file or run another program, so they may run
# before a push in its call. sed, awk, tee, sort and uniq are not among them: sed, awk and sort can run a program,
# and tee, sort and uniq can write a ref.
INERT = (
    ":", "true", "false", "test", "[", "[[", "echo", "printf", "set", "sleep", "pwd", "break", "continue", "wait",
    "exit", "return", "type", "which", "read", "cat", "head", "tail", "grep", "egrep", "fgrep", "wc", "ls", "date",
    "cut", "tr", "column", "nl", "basename", "dirname", "realpath", "readlink", "jq", "diff", "cmp", "sha256sum",
    "md5sum", "stat", "du", "df", "id", "whoami", "hostname", "uname",
)
# Git commands that cannot make or move a commit, a ref or HEAD (the index and the worktree may change).
GIT_READS = (
    "status", "log", "diff", "show", "rev-parse", "rev-list", "ls-remote", "ls-files", "ls-tree",
    "cat-file", "describe", "merge-base", "shortlog", "blame", "grep", "for-each-ref", "show-ref",
    "show-branch", "name-rev", "cherry", "range-diff", "whatchanged", "count-objects", "version", "help",
    "check-ignore", "check-attr", "check-ref-format", "diff-tree", "diff-index", "diff-files", "verify-commit",
    "verify-tag", "fsck", "add", "rm", "mv", "restore", "clean", "reflog", "format-patch", "archive", "var",
)
# Git commands that read or write by their arguments, and the arguments that make them a read. A fetch is a
# write: it can bring in what a push after it sends (`git fetch <url> && git push origin FETCH_HEAD:x`).
GIT_READ_FORMS = {
    "remote": lambda args: args[:1] in ([], ["-v"], ["--verbose"], ["show"], ["get-url"]),
    "branch": lambda args: set(args) <= {"-a", "--all", "-r", "--remotes", "-v", "-vv", "--verbose",
                                         "--show-current", "-l", "--list", "--no-color", "--color"},
    "tag": lambda args: not args or args[0] in ("-l", "--list"),
    "config": lambda args: bool({"--get", "--get-all", "--get-regexp", "-l", "--list", "get", "list"} & set(args))
    and not {"--add", "--unset", "--unset-all", "--replace-all", "--rename-section", "--remove-section", "set",
             "unset", "-e", "--edit"} & set(args),
    "stash": lambda args: args[:1] in (["list"], ["show"]),
    "worktree": lambda args: args[:1] == ["list"],
    "notes": lambda args: args[:1] in (["list"], ["show"]),
    "submodule": lambda args: args[:1] in (["status"], ["summary"]),
    "symbolic-ref": lambda args: len([arg for arg in args if not arg.startswith("-")]) == 1
    and not {"-d", "--delete"} & set(args),
}
# Git's own commands that a call commonly runs. git never runs an alias of its own command's name; for a name
# not here, the hook asks git (`git --list-cmds=main`).
GIT_COMMANDS = {
    *GIT_READS, *GIT_READ_FORMS, "push", "send-pack", "http-push", "subtree", "fetch", "commit", "merge",
    "rebase", "reset", "checkout", "switch", "cherry-pick", "revert", "am", "apply", "pull", "update-ref", "init",
    "clone", "gc", "bisect", "filter-branch", "replace", "commit-tree", "write-tree", "read-tree", "update-index",
    "hash-object", "mktree", "sparse-checkout", "maintenance", "prune", "repack", "fast-import", "bundle",
}
PLUMBING_PUSHES = ("send-pack", "http-push")  # pushes the hook does not read: refused, with git push named
# Git's global options that take the next word as their value.
GIT_VALUE_OPTIONS = ("-C", "-c", "--git-dir", "--work-tree", "--namespace", "--super-prefix", "--config-env",
                     "--attr-source")
# git push's long options, which git also takes abbreviated (`--dry` for --dry-run) and negated (`--no-tags`).
PUSH_LONG = (
    "--all", "--branches", "--mirror", "--dry-run", "--porcelain", "--delete", "--tags", "--follow-tags", "--signed",
    "--atomic", "--force", "--force-with-lease", "--force-if-includes", "--repo", "--set-upstream", "--thin",
    "--receive-pack", "--exec", "--prune", "--verify", "--progress", "--quiet", "--verbose", "--recurse-submodules",
    "--push-option", "--ipv4", "--ipv6",
)
PUSH_VALUES = ("--repo", "--receive-pack", "--exec", "--push-option", "--recurse-submodules")  # their value may follow
PUSH_SWITCHES = {"--all": "all", "--branches": "all", "--mirror": "mirror", "--dry-run": "dry", "--delete": "delete",
                 "--tags": "tags"}
# Variables that move where git finds refs or objects for a push; the hook follows GIT_DIR alone.
RELOCATING = {"GIT_COMMON_DIR", "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_NAMESPACE"}
# Where git finds its global configuration: a push in a call that sets one is read whole, as for GIT_CONFIG*.
CONFIG_HOMES = ("HOME", "XDG_CONFIG_HOME")
CD_VARIABLES = ("HOME", "CDPATH")  # what cd reads besides its words, exported or not; OLDPWD is the state's `old`
# The options with which a git read writes a file or runs a program, by command (a long one also abbreviated, a
# short one also in a cluster): `--output` is a diff option of log, show, diff and the rest.
READ_RISKS = {"": ("--output",), "grep": ("-O", "--open-files-in-pager"), "ls-remote": ("-u", "--upload-pack"),
              "archive": ("--remote", "--exec"), "add": ("-e", "--edit")}
STACK_INDEX = re.compile(r"[+-][0-9]+")  # pushd's and popd's +N and -N: an entry of the stack `dirs -v` lists
DEEP = ("this call nests its commands more than five levels deep (shells, evals, traps, functions, `!` aliases, "
        "process substitutions), past what the hook reads, so it cannot tell what the call pushes or commits. Run "
        "it less deeply nested")
ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
UNQUOTE = str.maketrans("", "", "'\"\\")
API_HOST = re.compile(r"^(?:https?://)?api\.github\.com(?::\d+)?(?=/|$)", re.IGNORECASE)
# A write to a repository's contents or git data through GitHub's REST API, by path, and the methods
# that make one (contents: PUT creates or updates a file; git data: POST creates an object).
CONTENT_PATHS = (
    (re.compile(r"repos/[^/]+/[^/]+/contents(?:/|$)", re.IGNORECASE), ("PUT", "POST", "PATCH"),
     "a file to a repository's contents"),
    (re.compile(r"repos/[^/]+/[^/]+/git/(?:blobs|trees|commits)/?$", re.IGNORECASE), ("POST", "PUT", "PATCH"),
     "git objects to a repository"),
)
GRAPHQL_COMMIT = "createCommitOnBranch"
GH_API_VALUE_OPTIONS = ("-X", "--method", "-H", "--header", "-f", "--raw-field", "-F", "--field", "--input",
                        "-q", "--jq", "-t", "--template", "--hostname", "-p", "--preview", "--cache")
GH_API_BODY_OPTIONS = ("-f", "--raw-field", "-F", "--field", "--input")
# curl's short options that take a value, and the ones that send a body (a POST unless -G) or upload one (a PUT).
CURL_VALUE_SHORTS = "AbcCdDeEFHKmoPQrtTuUwxXyYz"
CURL_DATA = ("-d", "--data", "--data-raw", "--data-binary", "--data-ascii", "--data-urlencode", "--json", "-F",
             "--form", "--form-string")
CURL_LONG_VALUES = (*CURL_DATA, "--request", "--upload-file", "--header", "--output", "--user", "--url", "--cookie",
                    "--user-agent", "--referer", "--config", "--max-time", "--connect-timeout", "--retry", "--proxy")


class _Unscannable(Exception):
    """A call that adds commits the hook cannot scan; its text is the refusal's reason."""


class _Arithmetic(str):
    """The text of a `$((...))`, which runs no command (its own substitutions are read apart)."""


class _Where(NamedTuple):
    """Where a git command runs: a directory and, when one is named, the git directory."""

    dir: str
    git_dir: str | None


class _Push(NamedTuple):
    where: _Where | None  # None: the hook cannot name the directory the push runs in
    args: list[str]
    overrides: dict[str, str]  # the `-c name=value` the git command line sets
    text: str
    open: bool = False  # words the hook cannot read may add refspecs: xargs's, a substitution's, a variable's


class _Pipeline:
    """A pipeline the call runs, whose commands run at once; the call goes on beside it when it runs in the
    background."""

    __slots__ = ("background",)

    def __init__(self) -> None:
        self.background = False


class _Step(NamedTuple):
    kind: str  # "push", "write" (a command that may make or move a commit), "refuse", "read"
    text: str
    push: _Push | None = None
    sub: bool = False  # it runs in a substitution or a trap, whose order against the line the hook does not keep
    loops: tuple[int, ...] = ()  # the loops around it: a loop runs its body again after a push in it
    # Where it runs, outermost first: each pipeline and the command in it. A compound command (a subshell, a
    # group, a loop, an if, a case) and a line read inside a command (a shell's string, an eval, an alias)
    # hold pipelines of their own.
    path: tuple[tuple[_Pipeline, int], ...] = ()
    invocation: int = 0  # the git command it comes from, which may push and then commit


class _State:
    """The shell's directory as the command moves it (None once the hook cannot name it), its pushd stack,
    the directory `cd -` returns to, and the variables the command sets (`$` once the hook cannot read one)."""

    def __init__(self, dir: str | None, dirs: list | None = None, old: str | None = None, env: dict | None = None):
        self.dir, self.dirs, self.old, self.env = dir, dirs or [], old, env or {}

    def copy(self) -> _State:
        return _State(self.dir, list(self.dirs), self.old, dict(self.env))

    def set(self, name: str, value: str) -> None:
        """A variable the call sets, `$` when the hook cannot read its value; OLDPWD is where `cd -` goes."""
        if name == "OLDPWD":
            self.old = _join(self.dir, value)
        else:
            self.env[name] = value


def _shell_reader():
    """codex_mention_guard.py's shell reader, so both hooks read a command the way the shell does. This copy of
    the module, which no other process shares, marks the text of an arithmetic `$((...))` so it is not read
    as commands."""
    import importlib.util

    path = Path(__file__).with_name("codex_mention_guard.py")
    spec = importlib.util.spec_from_file_location("codex_mention_guard", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    substitution = module._substitution

    def marked(command: str, i: int, extra: list, read: object, arith: bool = False) -> tuple[str, int]:
        text, end = substitution(command, i, extra, read, arith)
        return (_Arithmetic(text) if arith else text), end

    module._substitution = marked
    return module


def _left(deadline: float) -> float:
    left = deadline - time.monotonic()
    if left <= 0:
        raise _Unscannable(f"the scan before this call outlasted its {DEADLINE:.0f} seconds")
    return left


def _git(where: _Where, args: list[str], deadline: float, env: dict | None = None, data: bytes | None = None,
         reading: bool = False, replacing: bool = False) -> subprocess.CompletedProcess:
    """Run git where a command runs it, past any replace ref (a push sends the objects themselves), or through
    them when `replacing`, as a push names its sources. A failure to start or a timeout ends the scan, unless
    `reading`."""
    command = ["git", *([] if replacing else ["--no-replace-objects"]), "-C", where.dir,
               *(["--git-dir", where.git_dir] if where.git_dir else []), *args]
    try:
        return subprocess.run(command, input=data, capture_output=True, env=env, timeout=min(_left(deadline), 15))
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:  # ValueError: a NUL in a word
        if reading:
            return subprocess.CompletedProcess(command, 1, b"", b"")
        raise _Unscannable(f"git did not answer the scan ({error})") from error


def _out(proc: subprocess.CompletedProcess) -> str:
    return proc.stdout.decode("utf-8", "replace").strip()


def _tail(stderr: bytes) -> str:
    lines = re.sub(r"\x1b\[[0-9;]*m", "", stderr.decode("utf-8", "replace")).strip().splitlines()[-3:]
    return " / ".join(lines) or "no output"


def _scan_env(extra: dict | None = None) -> dict:
    """The environment of the scan's own git and gitleaks: no GIT_* or GITLEAKS_* variable (they would move the
    repository or replace the rules) and no system or global git configuration, with SCAN_CONFIG over the
    repository's own."""
    env = {key: value for key, value in os.environ.items() if not key.startswith(("GIT_", "GITLEAKS_"))}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_ATTR_NOSYSTEM="1",
               GIT_CONFIG_COUNT=str(len(SCAN_CONFIG)))
    for index, (key, value) in enumerate(SCAN_CONFIG):
        env[f"GIT_CONFIG_KEY_{index}"], env[f"GIT_CONFIG_VALUE_{index}"] = key, value
    return {**env, **(extra or {})}


def _join(base: str | None, value: str) -> str | None:
    """The directory `value` names from `base`, or None when the hook cannot name it."""
    if not value or "$" in value or "`" in value or "\n" in value:
        return None
    path = os.path.expanduser(value)
    if not os.path.isabs(path):
        if base is None:
            return None
        path = os.path.join(base, path)
    return os.path.normpath(path)


def _closing(tokens: list[str], i: int) -> int:
    """The index of the `)` that closes the `(` at `i`, or the last index when none does."""
    depth = 0
    for j in range(i, len(tokens)):
        depth += {"(": 1, ")": -1}.get(tokens[j], 0)
        if depth == 0:
            return j
    return len(tokens) - 1


def _uncommented(text: str) -> str:
    """The shell reader's text without its comments. The reader keeps a comment's words, and writes every quoted
    string single-quoted, so a `#` that starts a word outside single quotes starts a comment, to the line's end. A
    word starts after a blank, an operator or a subshell's `)`; a process substitution's `)` and an escaped
    character go on with theirs (`<(cmd)#x` and `\\;#x` are words)."""
    out: list[str] = []
    quote, i, opened, boundary = False, 0, [], True  # opened: per open `(`, whether a substitution opened it
    while i < len(text):
        char = text[i]
        if not quote and char == "\\":
            out.append(text[i:i + 2])
            i, boundary = i + 2, False
            continue
        if not quote and char == "#" and boundary:
            end = text.find("\n", i)
            i = len(text) if end < 0 else end
            continue
        if char == "'":
            quote = not quote
        elif not quote and char == "(":
            opened.append(i > 0 and text[i - 1] in "$<>")
        substituted = not quote and char == ")" and bool(opened) and opened.pop()
        boundary = not quote and (char in " \t\n;&|(" or (char == ")" and not substituted))
        out.append(char)
        i += 1
    return "".join(out)


def _compound_end(tokens: list[str], j: int) -> int:
    """The index past the compound command that starts at `j`, a function's body: its keywords counted where a
    command starts, so a quoted `done` in an argument closes nothing."""
    if tokens[j:j + 1] == ["("]:
        return _closing(tokens, j) + 1
    depth, start = 0, True
    for k in range(j, len(tokens)):
        if start and tokens[k] in OPENERS:
            depth += 1
        elif start and tokens[k] in CLOSERS:
            depth -= 1
            if depth <= 0:
                return k + 1
        start = tokens[k] in (";", "&&", "||", "|", "|&", "&", "(", ")") or tokens[k] in OPENERS + CLOSERS + PARTS
    return len(tokens)


def _backquoted(command: str) -> bool:
    """Whether the shell may run a backquoted command in this text: a backquote neither escaped, nor in single
    quotes, nor in a comment (read as _uncommented reads one, `$(cmd)#x` a word too). The shell reader leaves
    such a command's text as the word it stands for, unseen in a push's words."""
    quote, i, opened, boundary = None, 0, [], True
    while i < len(command):
        char = command[i]
        if char == "\\" and quote != "'":
            i, boundary = i + 2, False
            continue
        if quote == "'":
            quote = None if char == "'" else quote
        elif char == "'" and quote is None:
            quote = "'"
        elif char == '"':
            quote = None if quote == '"' else '"'
        elif char == "`":
            return True
        elif char == "#" and quote is None and boundary:
            end = command.find("\n", i)
            i = len(command) if end < 0 else end
            continue
        elif char == "(" and quote is None:
            opened.append(i > 0 and command[i - 1] in "$<>")
        substituted = quote is None and char == ")" and bool(opened) and opened.pop()
        boundary = quote is None and (char in " \t\n;&|(" or (char == ")" and not substituted))
        i += 1
    return False


class _Reader:
    """What one Bash call does that the scan must know, each command a step in the order the shell runs it."""

    def __init__(self, base: str, deadline: float, backquoted: bool = False):
        self.shell = _shell_reader()
        self.base, self.deadline, self.backquoted = base, deadline, backquoted
        self.steps: list[_Step] = []
        self.commands: set[str] | None = None  # git's own command names, asked once
        self.loops: list[int] = []  # the loops the walk is in
        self.traps: list[list[str]] = []  # per shell read, the commands its traps run when it exits
        self.ids = 0
        self.path: tuple[tuple[_Pipeline, int], ...] = ()  # the pipelines around the command being read
        self.at: tuple[_Pipeline, int] = (_Pipeline(), 0)  # its own pipeline and place in it
        self.functions: dict[str, list[str]] = {}  # the functions the call defines, by name: their bodies

    def _id(self) -> int:
        self.ids += 1
        return self.ids

    def _deep(self, sub: bool) -> None:
        self._step("refuse", DEEP, sub=sub)

    def _step(self, kind: str, text: str, push: _Push | None = None, sub: bool = False, invocation: int = 0) -> None:
        self.steps.append(_Step(kind, text, push, sub, tuple(self.loops), (*self.path, self.at),
                                invocation or self._id()))

    def _own(self, name: str, where: _Where | None) -> bool:
        """Whether `name` is one of git's own commands, which no alias stands for."""
        if name in GIT_COMMANDS:
            return True
        if self.commands is None:
            proc = _git(where or _Where(self.base, None), ["--list-cmds=main"], self.deadline, reading=True)
            self.commands = set(_out(proc).split())
        return name in self.commands

    def read(self, command: str, state: _State, depth: int = 0, sub: bool = False, shell: bool = True) -> None:
        """Read a command line. A nested one (a shell's string, an eval, an alias, a trap) runs inside the command
        that reads it. `shell` when the line is a shell of its own, whose traps run as it exits (an eval's run in
        the shell around it)."""
        if depth > MAX_DEPTH:
            self._deep(sub)
            return
        extra: list[str] = []
        text = command if command.endswith("\n") else command + "\n"
        try:
            text = _uncommented(self.shell._scan(text, 0, "", extra, self.shell._Input())[0])
        except RecursionError:  # substitutions nested past Python's limit: read the line as written
            extra = []
        if shell:
            self.traps.append([])
        start = state.copy()
        moved = self._walk(self.shell._command_tokens(text), state, depth, sub)
        # A substitution runs in the directory and with the GIT_DIR its command has, which the line may change.
        changed = moved or state.env.get("GIT_DIR") != start.env.get("GIT_DIR")
        for part in extra:
            if not isinstance(part, _Arithmetic):
                inner = _State(None) if changed else start.copy()
                self.traps.append([])
                self._walk(self.shell._command_tokens(_uncommented(part)), inner, depth, True)
                self._exit(inner, depth)
        if shell:
            self._exit(state, depth)

    def _exit(self, state: _State, depth: int) -> None:
        """Read the traps of a shell or subshell as it exits, in the state it leaves."""
        for script in self.traps.pop():
            self.read(script, state.copy(), depth + 1, True)

    def _walk(self, tokens: list[str], state: _State, depth: int, sub: bool) -> bool:
        """Read a line's commands, inside the command that reads it; whether a cd, pushd or popd moved its
        directory. A compound command is a command of the pipeline it stands in, holding pipelines of its own;
        one that runs in a subshell (a `(...)`, or one in a pipeline or the background) keeps its cd, and a
        subshell, a pipeline's command, a background job and a process substitution run their own traps."""
        saved = (self.path, self.at)
        self.path = (*self.path, self.at)
        frames: list[tuple] = []  # the compound commands open: opener, state at the open, place, path, piped
        words: list[str] = []
        previous, moved, pipe, member = None, False, None, 0

        def place() -> None:  # a command after `|` joins the pipeline before it; any other starts one
            nonlocal pipe, member
            pipe, member = (pipe, member + 1) if previous in ("|", "|&") and pipe else (_Pipeline(), 0)
            self.at = (pipe, member)

        def close(state_: _State, token: str) -> None:  # end the innermost compound command
            nonlocal pipe, member
            opener, start, (pipe, member), self.path, piped = frames.pop()
            self.at = (pipe, member)
            if opener in LOOPS and self.loops:
                self.loops.pop()
            if opener == "(":
                self._exit(state_, depth)
            if opener == "(" or piped or token in ("|", "|&", "&"):  # it ran in a subshell
                state_.__dict__.update(start.__dict__)

        def open_(opener: str) -> None:
            nonlocal pipe, member, previous
            piped = previous in ("|", "|&")
            place()
            frames.append((opener, state.copy(), (pipe, member), self.path, piped))
            self.path = (*self.path, (pipe, member))
            pipe, member, previous = None, 0, None
            if opener in LOOPS:  # a while's or until's condition runs on each turn, so it is inside the loop
                self.loops.append(self._id())
            if opener == "(":
                self.traps.append([])

        tokens = [*tokens, ";"]
        i, written = 0, []  # the files the command being read opens to write, as `> file`
        while i < len(tokens):
            token = tokens[i]
            i += 1
            if token in REDIRECTS:
                if token in ("<", ">") and tokens[i:i + 1] == ["("]:  # a process substitution runs beside its command
                    end = _closing(tokens, i)
                    if depth >= MAX_DEPTH:
                        self._deep(True)
                    else:
                        inner = state.copy()
                        self.traps.append([])
                        self._walk(tokens[i + 1:end], inner, depth + 1, True)
                        self._exit(inner, depth + 1)
                    i = end + 1
                    continue
                if words and words[-1].isdigit():
                    words.pop()  # the descriptor of 2>file or 1>&2
                if token in ("<", "&>") and tokens[i:i + 1] == [">"]:  # `<>` and `&>>`, which the tokens split
                    token, i = token + ">", i + 1
                target = tokens[i] if i < len(tokens) else ""
                if token in WRITES and target not in DEVICES and not target.startswith("/dev/fd/") \
                        and not (token == ">&" and (target.isdigit() or target == "-")):
                    written.append(f"{token} {target}")
                i += 1  # the redirection's target, or a here-string's text
                continue
            if token in self.shell.OPERATORS or token in ("(", ")"):
                if token == "(" and tokens[i:i + 1] == [")"] and len(words) == 1:
                    # `name ()`: a function's definition, whose body runs where the function is called
                    end = _compound_end(tokens, i + 1)
                    self.functions[words[0]] = tokens[i + 1:end]
                    words, i = [], end
                    continue
                if token == ")" and frames and frames[-1][0] == "case":
                    words = []  # a case's pattern
                # A redirection with no command of its own after a `)` or a closing word is the compound's.
                bare = not words and previous != ")"
                while words and words[0] in OPENERS + CLOSERS + PARTS:
                    word = words.pop(0)
                    if word in OPENERS:
                        open_(word)
                        if word in HEADERS:  # `for i in ...`, `case x in`
                            words = []
                    elif word in CLOSERS and frames and frames[-1][0] != "(":
                        close(state, token)
                ran = None
                if words:
                    place()
                    # A pipeline's commands and a background job run in subshells: their cd stays there.
                    piped = previous in ("|", "|&") or token in ("|", "|&", "&")
                    start = len(self.steps)
                    moved |= self._command(words, state.copy() if piped else state, depth, sub)
                    ran = self.steps[start:]
                elif written and bare:
                    place()
                if written:
                    # A file the command writes may be a ref, a config or a script; a push's own output is not.
                    if not ran or any(step.kind != "push" for step in ran):
                        self._step("write", " ".join([*words, *written]), sub=sub)
                    written = []
                words = []
                if token == "&" and pipe:
                    pipe.background = True
                if token == "(":
                    open_("(")
                elif token == ")" and frames and frames[-1][0] == "(":
                    close(state, tokens[i] if i < len(tokens) else ";")
                previous = token if token != "(" else previous
                continue
            if not words and token == "function" and i < len(tokens):  # `function name [()] body`, a definition
                name, j = tokens[i], i + 1
                j += 2 if tokens[j:j + 2] == ["(", ")"] else 0
                end = _compound_end(tokens, j)
                self.functions[name] = tokens[j:end]
                i = end
                continue
            words.append(token)
        while frames:  # a compound command left open ends with the line
            close(state, ";")
        self.path, self.at = saved
        return moved

    def _command(self, words: list[str], state: _State, depth: int, sub: bool) -> bool:
        """Read one command into steps; whether it moved the directory."""
        text = " ".join(words)
        env = dict(state.env)
        assigned = []
        while words and ASSIGNMENT.match(words[0]):
            name, _, value = words[0].partition("=")
            env[name] = value
            assigned.append(name)
            words = words[1:]
        if not words:
            # Assignments alone set shell variables, which reach git only if exported, and the hook cannot see
            # whether they are: a GIT_* variable set this way is one whose value the hook does not know. cd reads
            # HOME, CDPATH and OLDPWD exported or not.
            for name in assigned:
                state.set(name, env[name] if name in (*CD_VARIABLES, "OLDPWD") else "$")
            return False
        if words[0] in self.functions:  # a function the call defines runs its body here, in this shell
            if depth >= MAX_DEPTH:
                self._deep(sub)
                return False
            before = {name: state.env.get(name) for name in assigned}
            state.env.update((name, env[name]) for name in assigned)  # its assignments last while it runs
            moved = self._walk(self.functions[words[0]], state, depth + 1, sub)
            for name, value in before.items():
                if value is None:
                    state.env.pop(name, None)  # the body may have unset it
                else:
                    state.env[name] = value
            return moved
        name, start, directory = words[0].rsplit("/", 1)[-1].lower(), 0, state.dir
        if name in WRAPPERS:  # the command a wrapper runs: its first git, gh, curl, shell or eval word
            k = 1
            while k < len(words):
                word, base = words[k], words[k].rsplit("/", 1)[-1].lower()
                if ASSIGNMENT.match(word):
                    key, _, value = word.partition("=")
                    env[key] = value
                elif words[0].rsplit("/", 1)[-1] == "env" and word in ("-C", "--chdir") and k + 1 < len(words):
                    directory = _join(directory, words[k + 1])  # env -C runs its command in that directory
                    k += 1
                elif words[0].rsplit("/", 1)[-1] == "env" and word.startswith("--chdir="):
                    directory = _join(directory, word[len("--chdir="):])
                elif base in ("git", "gh", "curl", "eval", *SHELLS):
                    name, start = base, k
                    break
                k += 1
        if directory is not None and not os.path.isdir(directory):
            directory = None
        inner = state if directory == state.dir else _State(directory, list(state.dirs), state.old, dict(state.env))
        args = words[start + 1:]
        if name == "git":  # xargs adds the words it reads to the command it runs
            xargs = "xargs" in [word.rsplit("/", 1)[-1] for word in words[:start]]
            self._git(args, inner, env, depth, sub, text, appended=xargs)
            return False
        if name in ("cd", "pushd", "popd"):
            self._move(name, args, state, env)
            return True
        if name == "eval":  # its words run in this shell, whose traps they may set
            self.read(" ".join(args), state, depth + 1, sub, shell=False)
        elif name == "trap":
            args = args[1:] if args[:1] == ["--"] else args
            if args and not args[0].startswith("-"):
                self.traps[-1].append(args[0])
            self._step("read", text, sub=sub)
        elif name in SHELLS:
            script = _shell_string(args)
            if script is None:  # a script file or standard input: what it runs is not read
                self._step("write", text, sub=sub)
            else:
                self.read(script, inner.copy(), depth + 1, sub)
        elif name == "gh":
            write = _gh_api_write(args, text, directory)
            kind = "refuse" if write else "read" if args[:1] == ["api"] else "write"
            self._step(kind, write or text, sub=sub)
        elif name == "curl":  # curl can write any file (-o, -O, -D, -c and more), a ref among them
            write = _curl_write(args, text, directory)
            self._step("refuse" if write else "write", write or text, sub=sub)
        elif name in ("export", "unset"):
            unexport = name == "unset" or "-n" in args
            for word in args:
                key, eq, value = word.partition("=")
                if name == "unset" and key in ("HOME", "OLDPWD"):
                    state.set(key, "$")  # cd alone, or cd -, then fails, which the hook does not follow
                elif unexport:
                    if name == "unset" or key not in CD_VARIABLES:  # export -n leaves the shell's own variable
                        state.env.pop(key, None)
                elif eq:
                    state.set(key, value)
            self._step("read", text, sub=sub)
        elif name in ("read", "printf"):  # read's names and printf's -v name take values the hook does not read
            named = args if name == "read" else [args[k + 1] for k in range(len(args) - 1) if args[k] == "-v"] + \
                [arg[2:] for arg in args if arg.startswith("-v") and len(arg) > 2]
            for key in named:
                if key.startswith("GIT_") or key in (*CD_VARIABLES, *CONFIG_HOMES, "OLDPWD"):
                    state.set(key, "$")
            self._step("read", text, sub=sub)
        else:
            # A push another command holds, wherever its git word stands (`watch git push`, `echo git push`), is
            # read as that push, with the words that command may add.
            held = len(self.steps)
            for k, word in enumerate(args):
                if word.rsplit("/", 1)[-1].lower() == "git":
                    self._git(args[k + 1:], inner, env, depth, sub, text, only_pushes=True, appended=True)
                    break
            if len(self.steps) == held:
                self._step("read" if name in INERT or (name == "exec" and not args) else "write", text, sub=sub)
        return False

    def _move(self, name: str, args: list[str], state: _State, env: dict) -> None:
        """Follow a cd, pushd or popd as bash does, with the HOME, CDPATH and OLDPWD the call gives it; the
        directory, or an entry of the stack, becomes None when the hook cannot name it. The stack is the one
        `dirs -v` lists: entry 0 the shell's directory, then state.dirs from its end."""
        keep = name != "cd" and "-n" in args  # pushd -n and popd -n change the stack, not the directory
        if name == "cd":
            words = [arg for arg in args if arg == "-" or not arg.startswith("-")]
        else:
            words = [arg for arg in args if arg != "-n"]
        if name != "cd" and len(words) == 1 and STACK_INDEX.fullmatch(words[0]):
            _rotate(name, words[0], keep, state)
            return
        if name == "popd" or (name == "pushd" and not words):
            if words:  # popd with a word that is not +N or -N
                state.dir = None
            elif not state.dirs or (keep and name == "pushd"):
                pass  # with no stack the builtin fails, and pushd -n alone does nothing
            elif keep:
                state.dirs.pop()  # popd -n drops the entry under the shell's directory
            elif name == "popd":
                state.old, state.dir = state.dir, state.dirs.pop()
            else:  # pushd alone swaps the top two entries
                state.old, state.dir, state.dirs[-1] = state.dir, state.dirs[-1], state.dir
            return
        if len(words) > 1:  # bash refuses more than one directory; the hook does not follow what it does
            state.dir = None
            return
        word, home = (words[0] if words else "~"), env.get("HOME")
        if word == "-":
            target = _join(state.dir, env["OLDPWD"]) if "OLDPWD" in env else state.old
        elif home is not None and (word == "~" or word.startswith("~/")):
            target = _join(state.dir, home + word[1:])
        elif env.get("CDPATH") and not word.startswith(("/", "~", "./", "../")) and word not in (".", ".."):
            target = None  # bash looks the name up along CDPATH before the shell's directory
        else:
            target = _join(state.dir, word)
        if target is not None and not os.path.isdir(target):
            target = None  # the cd fails or enters a directory the call makes first
        if keep:  # pushd -n puts the directory under the shell's own, and popd later enters it from there
            state.dirs.append(target if word == "-" or word.startswith(("/", "~")) else None)
            return
        if name == "pushd":
            state.dirs.append(state.dir)
        state.old, state.dir = state.dir, target

    def _git(self, words: list[str], state: _State, env: dict, depth: int, sub: bool, text: str,
             only_pushes: bool = False, overrides: dict | None = None, aliases: int = 0,
             appended: bool = False) -> None:
        """Read a git command line (the words after `git`) into steps."""
        directory = state.dir
        git_dir = _join(directory, env["GIT_DIR"]) if env.get("GIT_DIR") else None
        # A ref store, object store or namespace the call moves is one the hook does not follow, and settings the
        # call gives git through the environment may change what a push sends.
        unknown = directory is None or (bool(env.get("GIT_DIR")) and git_dir is None) or bool(RELOCATING & set(env))
        opaque = any(key.startswith("GIT_CONFIG") or key in CONFIG_HOMES for key in env)
        overrides = dict(overrides or {})
        i = 0
        while i < len(words):
            word = words[i]
            if word in GIT_VALUE_OPTIONS and i + 1 < len(words):
                value = words[i + 1]
                if word == "-C":
                    directory = _join(directory, value)
                    unknown |= directory is None or not os.path.isdir(directory)
                elif word == "-c":
                    key, eq, setting = value.partition("=")
                    overrides[key.lower()] = setting if eq else "true"  # `-c name` alone sets a boolean
                elif word == "--git-dir":
                    git_dir = _join(directory, value)
                    unknown |= git_dir is None
                unknown |= word == "--namespace"
                opaque |= word == "--config-env"
                i += 2
                continue
            if word.startswith("--git-dir="):
                git_dir = _join(directory, word[len("--git-dir="):])
                unknown |= git_dir is None
            elif not word.startswith("-"):
                break
            unknown |= word.startswith("--namespace=")
            opaque |= word.startswith("--config-env=")
            i += 1
        if i >= len(words):  # `git` alone, `git --version`
            if not only_pushes:
                self._step("read", text, sub=sub)
            return
        command, args = words[i], words[i + 1:]
        where = None if unknown or directory is None else _Where(directory, git_dir)
        if not self._own(command, where):
            import shlex

            alias = overrides.get(f"alias.{command.lower()}")
            if alias is None:
                proc = _git(where or _Where(self.base, None), ["config", "--get", f"alias.{command}"], self.deadline,
                            reading=True)
                alias = proc.stdout.decode("utf-8", "replace").rstrip("\n") if proc.returncode == 0 else None
            if (alias is None or aliases >= MAX_DEPTH) and not only_pushes:
                # Another program's git-<name>, an alias the call defines first, or an alias chain past five: it
                # may push what stands now (every branch: an open push) and then make commits.
                invocation = self._id()
                self._step("push", text, _Push(where, [], overrides, text, True), sub, invocation)
                self._step("write", text, sub=sub, invocation=invocation)
                return
            if alias is not None and aliases < MAX_DEPTH:
                # What the alias runs inherits this git's environment, with the GIT_DIR its options name; a shell
                # alias's own git also reads this git's -c values, which its words do not show.
                inherited = {key: value for key, value in env.items() if key != "GIT_DIR"}
                inherited.update({"GIT_DIR": git_dir} if git_dir else {})
                if opaque or (overrides and alias.startswith("!")):
                    inherited["GIT_CONFIG_PARAMETERS"] = "$"
                if alias.startswith("!"):  # a shell alias runs from the repository's top directory
                    top = _out(_git(where, ["rev-parse", "--show-toplevel"], self.deadline, reading=True)) \
                        if where else ""
                    script = alias[1:] + "".join(" " + shlex.quote(arg) for arg in args)
                    self.read(script, _State(top or (where.dir if where else None), env=inherited), depth + 1, sub)
                    return
                try:
                    expanded = shlex.split(alias)
                except ValueError:
                    expanded = alias.split()
                self._git([*expanded, *args], _State(None if unknown else directory), inherited, depth, sub, text,
                          only_pushes, overrides, aliases + 1, appended)
                return
        if command == "push":
            # A word holding `$` may expand to several (`git push $(echo origin work)`), as may a backquoted one.
            open_ = appended or opaque or self.backquoted or any("$" in word for word in words)
            self._step("push", text, _Push(where, args, overrides, text, open_), sub)
        elif command in PLUMBING_PUSHES or (command == "subtree" and "push" in args):
            self._step("refuse", (
                "this command runs `git subtree push`, whose commits git builds as it runs, so the hook cannot "
                "scan them first. Split them into a branch (`git subtree split --prefix=<dir> -b <branch>`) and "
                "push that with git push, which the hook scans" if command == "subtree" else
                f"this command runs `git {command}`, a push the hook does not read. Push with git push, which it "
                "scans"), sub=sub)
        elif not only_pushes:
            reads = command in GIT_READS or GIT_READ_FORMS.get(command, lambda _: False)(args)
            # Settings the call gives git, or an option that writes a file or runs a program, let a read run what
            # makes or moves a commit (`-c diff.external=...`, `--output=.git/refs/heads/x`).
            steered = overrides or opaque or any(key.startswith("GIT_") and key not in ("GIT_DIR", "GIT_WORK_TREE")
                                                 for key in env)
            self._step("read" if reads and not steered and not _risky(command, args) else "write", text, sub=sub)


def _risky(command: str, args: list[str]) -> bool:
    """Whether a git read's words give it one of the options READ_RISKS names for it."""
    for word in args:
        if word == "--":
            break
        name = word.split("=", 1)[0]
        for option in (*READ_RISKS[""], *READ_RISKS.get(command, ())):
            if option.startswith("--"):
                if name.startswith("--") and len(name) > 3 and option.startswith(name):
                    return True
            elif name.startswith("-") and not name.startswith("--") and option[1] in name[1:]:
                return True
    return False


def _rotate(name: str, word: str, keep: bool, state: _State) -> None:
    """pushd +N or -N turns the stack until that entry is the shell's directory; popd +N or -N drops it."""
    entries = [state.dir, *reversed(state.dirs)]
    n = int(word[1:])
    index = n if word[0] == "+" else len(entries) - 1 - n
    if not 0 <= index < len(entries):
        return  # past the stack's end: the builtin fails and nothing moves
    if name == "pushd" and not keep:
        turned = entries[index:] + entries[:index]
        state.old, state.dir, state.dirs = state.dir, turned[0], turned[:0:-1]
    elif name == "popd" and index:
        del state.dirs[-index]  # the directory stays
    elif name == "popd" and not keep:
        if state.dirs:  # popd +0 is popd
            state.old, state.dir = state.dir, state.dirs.pop()
    else:  # pushd -n +N and popd -n +0, which bash carries out in ways the hook does not follow
        state.dir, state.dirs = None, [None] * len(state.dirs)


def _shell_string(words: list[str]) -> str | None:
    """The command string a shell's `-c` runs (`bash -c`, `-lc`, `-euo pipefail -c`, `--rcfile f -c`), or None
    for a shell given a script or standard input."""
    command, i = False, 0
    while i < len(words):
        word = words[i]
        if word in ("--rcfile", "--init-file"):
            i += 2
        elif word == "--":
            i += 1
            break
        elif word.startswith("--"):
            i += 1
        elif word[:1] in ("-", "+") and len(word) > 1:
            command |= word[0] == "-" and "c" in word[1:]
            i += 2 if word[-1] in "oO" else 1  # -o, +o, -O and +O take the next word: `-euo pipefail`
        else:
            break
    if not command:
        return None
    return words[i] if i < len(words) else ""


def _endpoint(value: str) -> str:
    return API_HOST.sub("", value).split("?", 1)[0].strip("/")


def _sent(value: str, directory: str | None) -> str:
    """The text a field sends: its value, or the file an `@file` names (up to 1 MiB), as the command would read
    it; standard input (`@-`) and a file the hook cannot read send nothing it can see."""
    if not value.startswith("@"):
        return value
    if value == "@-" or directory is None:
        return ""
    try:
        path = Path(directory, os.path.expanduser(value[1:])).resolve()
        if str(path).startswith(("/proc/", "/sys/", "/dev/")) or not path.is_file():
            return ""
        if path.stat().st_size > MAX_FILE_BYTES:
            return ""
        return path.read_text(encoding="utf-8", errors="replace")
    except (OSError, RuntimeError, ValueError):
        return ""


def _content_write(path: str, method: str, text: str) -> str | None:
    """What a request to GitHub's API with this path and method writes to a repository, or None."""
    if path.lower() == "graphql" and GRAPHQL_COMMIT in text:
        return f"a commit (the GraphQL {GRAPHQL_COMMIT} mutation)"
    for pattern, methods, what in CONTENT_PATHS:
        if pattern.match(path) and method in methods:
            return f"{what} ({method} {path})"
    return None


def _gh_api_write(words: list[str], text: str, directory: str | None) -> str | None:
    """The repository write a `gh api` command (the words after `gh`) makes, as a refusal's reason, or None."""
    if words[:1] != ["api"]:
        return None
    method, body, endpoint, sent = None, False, None, [text]
    i = 1
    while i < len(words):
        word = words[i]
        i += 1
        if word in GH_API_VALUE_OPTIONS and i < len(words):  # -X PUT, --method PUT, -f key=value
            name, value = word, words[i]
            i += 1
        elif word.startswith("--") and "=" in word:  # --method=PUT
            name, _, value = word.partition("=")
        elif not word.startswith("--") and word[:2] in GH_API_VALUE_OPTIONS and len(word) > 2:  # -XPUT, -X=PUT
            name, value = word[:2], word[2:]
            value = value[1:] if value.startswith("=") else value
        else:
            if not word.startswith("-") and endpoint is None:
                endpoint = word
            continue
        if name in ("-X", "--method"):
            method = value.upper()
        elif name in ("-F", "--field"):
            sent.append(_sent(value.partition("=")[2], directory))
        elif name == "--input":
            sent.append(_sent("@" + value, directory))
        body |= name in GH_API_BODY_OPTIONS
    if endpoint is None:
        return None
    write = _content_write(_endpoint(endpoint), method or ("POST" if body else "GET"), "\n".join(sent))
    return _api_reason(write) if write else None


def _curl_write(words: list[str], text: str, directory: str | None) -> str | None:
    """The repository write a curl command (the words after `curl`) makes, as a refusal's reason, or None."""
    method, data, upload, get, urls, sent = None, False, False, False, [], [text]
    i = 0
    while i < len(words):
        word = words[i]
        i += 1
        if word.startswith("--"):
            name, eq, value = word.partition("=")
            if name in CURL_LONG_VALUES and not eq and i < len(words):
                value = words[i]
                i += 1
            if name == "--request":
                method = value.upper()
            elif name == "--upload-file":
                upload = True
            elif name in CURL_DATA:
                data = True
                sent.append(_sent(value, directory))
            elif name == "--get":
                get = True
            elif name == "--url":
                urls.append(value)
        elif word.startswith("-") and len(word) > 1:
            for k, char in enumerate(word[1:], 1):
                if char == "G":
                    get = True
                if char in CURL_VALUE_SHORTS:
                    value = word[k + 1:]
                    if not value and i < len(words):
                        value = words[i]
                        i += 1
                    if char == "X":
                        method = value.upper()
                    elif char == "T":
                        upload = True
                    elif "-" + char in CURL_DATA:
                        data = True
                        sent.append(_sent(value, directory))
                    break
        else:
            urls.append(word)
    method = method or ("PUT" if upload else "GET" if get else "POST" if data else "GET")
    for url in urls:
        if API_HOST.match(url):
            write = _content_write(_endpoint(url), method, "\n".join(sent))
            if write:
                return _api_reason(write)
    return None


def _api_reason(write: str) -> str:
    return (
        f"this command writes {write} through GitHub's API, whose content the hook cannot read before it "
        "runs. Commit the change and push it with git push, or send it with the GitHub MCP push_files or "
        "create_or_update_file tool; the hook scans both with CI's pinned gitleaks"
    )


def _pin() -> tuple[str, str]:
    """The gitleaks version and archive SHA-256 that CI's secret-scan job pins."""
    try:
        text = CI.read_text(encoding="utf-8")
    except OSError as error:
        raise _Unscannable(f"the hook cannot read CI's gitleaks pin in .github/workflows/ci.yml ({error})") from error
    versions = set(re.findall(r"^\s*GITLEAKS_VERSION:\s*['\"]?([0-9][0-9A-Za-z.-]*)['\"]?\s*$", text, re.MULTILINE))
    hashes = set(re.findall(r"^\s*GITLEAKS_SHA256:\s*['\"]?([0-9a-f]{64})['\"]?\s*$", text, re.MULTILINE))
    if len(versions) != 1 or len(hashes) != 1:
        raise _Unscannable(
            "the hook cannot read CI's gitleaks pin: .github/workflows/ci.yml must set GITLEAKS_VERSION and "
            f"GITLEAKS_SHA256 once each (it sets {len(versions)} versions and {len(hashes)} hashes)")
    return versions.pop(), hashes.pop()


def _platform() -> str | None:
    """The release's name for this platform (linux_x64, darwin_arm64, ...), or None for one it has no build for."""
    import platform

    system = {"Linux": "linux", "Darwin": "darwin"}.get(platform.system())
    arch = ARCHES.get(platform.machine().lower())
    return f"{system}_{arch}" if system and arch else None


def _installed(version: str, sha256: str, target: str) -> Path:
    """Where --install puts the binary: one directory per pin, so a new pin needs a new install."""
    cache = os.environ.get("XDG_CACHE_HOME", "")
    base = Path(cache) if os.path.isabs(cache) else Path.home() / ".cache"
    return base / "earningsnerd" / "gitleaks" / f"{version}-{sha256[:12]}" / target / "gitleaks"


def _binary() -> tuple[str, Path]:
    """The pinned version and the installed binary, or a refusal saying how to install it."""
    version, sha256 = _pin()
    target = _platform()
    if target is None:
        import platform

        raise _Unscannable(
            f"gitleaks publishes no build the hook installs for {platform.system()} on {platform.machine()}, so it "
            "cannot scan what this call adds; push from a Linux or macOS machine")
    path = _installed(version, sha256, target)
    if not (path.is_file() and os.access(path, os.X_OK)):
        raise _Unscannable(
            f"gitleaks {version}, which the hook runs before a call that adds commits, is not installed ({path}). "
            f"Install it once with `python3 {Path(__file__).resolve()} --install`, which downloads the release "
            "archive and checks its SHA-256, then run the call again")
    return version, path


def _blob(where: _Where, rev: str | None, name: str, deadline: float, env: dict | None = None) -> bytes | None:
    """A file's bytes at a commit, or None when the commit or the file is missing."""
    if rev is None:
        return None
    proc = _git(where, ["cat-file", "blob", f"{rev}:{name}"], deadline, env=env)
    return proc.stdout if proc.returncode == 0 else None


def _commit(where: _Where, rev: str, deadline: float, env: dict | None = None, replacing: bool = False) -> str | None:
    """The commit `rev` names, or None. It is named first and peeled after: `:/<text>` takes no suffix."""
    proc = _git(where, ["rev-parse", "--verify", "--quiet", "--end-of-options", rev], deadline, env=env,
                replacing=replacing)
    sha = _out(proc) if proc.returncode == 0 else ""
    if not re.fullmatch(r"[0-9a-f]{40,64}", sha):
        return None
    proc = _git(where, ["rev-parse", "--verify", "--quiet", f"{sha}^{{commit}}"], deadline, env=env,
                replacing=replacing)
    return _out(proc) or None if proc.returncode == 0 else None


def _main(where: _Where, deadline: float, env: dict | None = None) -> str | None:
    """Main's tip as the remote-tracking refs have it, or None when none is fetched."""
    for ref in MAIN_REFS:
        sha = _commit(where, ref, deadline, env)
        if sha:
            return sha
    return None


def _gitleaks(binary: Path, git_dir: str, revs: list[str], main: tuple[_Where, str] | None, tmp: Path,
              env: dict, deadline: float) -> list[dict]:
    """What gitleaks finds in the commits `revs` select, with main's pins and rules alone."""
    where, tip = main if main else (None, None)
    pins = _blob(where, tip, ".gitleaksignore", deadline, env) if where else None
    ignore = tmp / "main.gitleaksignore"
    ignore.write_bytes(pins or b"")
    report = tmp / "report.json"
    # A diff driver the repository's own config names would show gitleaks a conversion, not the text: git log
    # runs textconv unless told not to, and an external diff only when told to.
    log_opts = " ".join([*revs, "--no-textconv", "--no-ext-diff"])
    command = [str(binary), "git", git_dir, "--log-opts=" + log_opts, "--no-banner", "--no-color", "--redact=100",
               "--exit-code", str(LEAKS), "--report-format", "json", "--report-path", str(report),
               "--gitleaks-ignore-path", str(ignore)]
    rules = _blob(where, tip, ".gitleaks.toml", deadline, env) if where else None
    if rules is not None:
        (tmp / "main.gitleaks.toml").write_bytes(rules)
        command += ["--config", str(tmp / "main.gitleaks.toml")]
    try:
        proc = subprocess.run(command, cwd=tmp, env=env, capture_output=True, timeout=_left(deadline))
    except subprocess.TimeoutExpired as error:
        raise _Unscannable(f"gitleaks outlasted the scan's {DEADLINE:.0f} seconds") from error
    except OSError as error:
        raise _Unscannable(f"gitleaks did not start ({error})") from error
    if proc.returncode not in (0, LEAKS):
        raise _Unscannable(f"gitleaks failed (exit {proc.returncode}: {_tail(proc.stderr)})")
    try:
        findings = json.loads(report.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise _Unscannable(f"gitleaks left no report the hook can read ({error})") from error
    if not isinstance(findings, list) or (proc.returncode == LEAKS and not findings):
        raise _Unscannable("gitleaks reported leaks its report does not list")
    return [finding for finding in findings if isinstance(finding, dict)]


def _listed(findings: list[dict], with_commit: bool) -> str:
    lines = [
        "- " + (f"{str(finding.get('Commit', ''))[:12]} " if with_commit else "")
        + f"{finding.get('File')}:{finding.get('StartLine')} ({finding.get('RuleID')})"
        for finding in findings[:MAX_FINDINGS]
    ]
    if len(findings) > MAX_FINDINGS:
        lines.append(f"- and {len(findings) - MAX_FINDINGS} more")
    return "\n".join(lines)


def _found(version: str, findings: list[dict], where: str, with_commit: bool, unpinned: bool, hint: str = "") -> str:
    count = f"{len(findings)} secret-shaped literal{'s' if len(findings) != 1 else ''}"
    text = (
        f"gitleaks {version} (the pin of CI's secret-scan job) finds {count} in {where}, which main's "
        f".gitleaksignore, as this checkout last fetched it, does not pin:\n{_listed(findings, with_commit)}\n"
        "CI's secret-scan reads every branch, so once on GitHub each one fails every pull request's scan until "
        "it leaves the branch history or main pins it. Remove a real credential (then rotate it). Mark a test "
        "vector's, fixture's or sample value's line `# gitleaks:allow` with the reason, or build the value so no "
        "rule matches, in the commit that adds it. A pin in this branch's own .gitleaksignore does not count: "
        "it reaches this branch's runs alone"
    )
    if unpinned:
        text += (". No main branch is fetched (origin/HEAD, origin/main or origin/master), so no pin reached the "
                 "scan: `git fetch origin main` and run the call again if main pins these")
    return text + (". " + hint if hint else "")


def _sends(push: _Push, where: _Where, deadline: float) -> tuple[list[str], bool]:
    """The commits a push sends, as object names (none for a dry run, a delete, or no source), and whether the
    hook read it as sending every branch and tag."""
    switches = dict.fromkeys(PUSH_SWITCHES.values(), False)
    positional: list[str] = []
    args = push.args
    i = 0
    while i < len(args):
        arg = args[i]
        i += 1
        if arg == "--":
            positional += args[i:]
            break
        if arg.startswith("--"):
            name, eq, _ = arg.partition("=")
            negated = name.startswith("--no-")
            option = "--" + name[len("--no-"):] if negated else name
            if option not in PUSH_LONG:  # git takes an abbreviation that names one option
                matches = [whole for whole in PUSH_LONG if whole.startswith(option)]
                option = matches[0] if len(matches) == 1 else option
            if option in PUSH_SWITCHES:
                switches[PUSH_SWITCHES[option]] = not negated  # the last one written wins, as in git
            elif option in PUSH_VALUES and not eq and not negated:
                i += 1  # its value
        elif arg.startswith("-") and len(arg) > 1:
            for k, char in enumerate(arg[1:], 1):
                if char in "nd":
                    switches["dry" if char == "n" else "delete"] = True
                elif char == "o":  # -o takes a value: the rest of the word, or the next word
                    i += 0 if arg[k + 1:] else 1
                    break
        else:
            positional.append(arg)
    if switches["dry"] or switches["delete"]:  # a delete names the refs it removes, not what it sends
        return [], False
    words, refspecs = positional[1:], []  # the first is the repository
    while words:
        word = words.pop(0)
        refspecs.append(f"refs/tags/{words.pop(0)}" if word == "tag" and words else word)
    if switches["tags"]:
        refspecs.append("refs/tags/*")
    revs: list[str] = []
    broad = push.open

    def refs(*options: str) -> list[str]:
        proc = _git(where, ["rev-parse", *options], deadline)
        if proc.returncode != 0:
            raise _Unscannable(f"git could not list this repository's refs ({_tail(proc.stderr)})")
        return _out(proc).split()

    if switches["all"] or switches["mirror"]:
        revs += refs("--branches")
    if switches["mirror"]:
        revs += refs("--tags")
    for spec in refspecs:
        spec = spec[1:] if spec.startswith("+") else spec
        if spec.startswith("^"):  # a negative refspec sends nothing
            continue
        source = spec.rpartition(":")[0] if ":" in spec else spec  # git splits a refspec at its last colon
        if ":" in spec and not source:
            broad |= spec == ":"  # `:` alone pushes the matching branches; `:dst` deletes
            continue
        literal = not set(source) & set("$`")  # a word the shell expands names no ref the hook can read now
        if "*" in source and source.startswith("refs/") and literal:
            revs += refs(f"--glob={source}")
            continue
        # git push names a source through replace refs (`work~1` may reach a replacement's parent) unless its
        # environment turns them off, so both namings are scanned.
        named = [_commit(where, source, deadline, replacing=replacing) for replacing in (False, True) if literal]
        named = [sha for sha in dict.fromkeys(named) if sha]
        if named:
            revs += named
        else:
            broad = True
    if not refspecs and not switches["all"] and not switches["mirror"]:
        # With no refspec git pushes HEAD, unless push.default, a remote's push refspecs or its mirror say more.
        settings: dict[str, str] = {}
        listed = _git(where, ["config", "--get-regexp", r"^(push\.default|remote\..*\.(push|mirror))$"], deadline)
        for line in _out(listed).splitlines():
            key, space, value = line.partition(" ")
            settings[key] = value if space else "true"  # a key with no value is a boolean set
        settings.update((key, value) for key, value in push.overrides.items()
                        if key == "push.default" or key.startswith("remote."))
        mirrored = any(key.endswith(".mirror") and value.lower() in ("true", "yes", "on", "1")
                       for key, value in settings.items())
        refspecs_set = any(key.endswith(".push") for key in settings)
        head = _commit(where, "HEAD", deadline)
        revs += [head] if head else []
        broad |= settings.get("push.default") == "matching" or mirrored or refspecs_set
    if broad:
        head = _commit(where, "HEAD", deadline)
        revs += [*([head] if head else []), *refs("--branches"), *refs("--tags")]
    return list(dict.fromkeys(revs)), broad


def _scan_pushes(pushes: list[_Push], deadline: float) -> str | None:
    """Scan the commits each push would add, one gitleaks run per repository."""
    import tempfile

    repos: dict[str, list] = {}
    for push in pushes:
        # What a push sends is read where it runs, with the configuration its git reads.
        where = push.where
        proc = _git(where, ["rev-parse", "--git-common-dir"], deadline)
        if proc.returncode != 0:  # not a repository: the push fails there too
            continue
        git_dir = os.path.normpath(os.path.join(where.dir, _out(proc)))
        revs, broad = _sends(push, where, deadline)
        if revs:
            entry = repos.setdefault(git_dir, [[], False])
            entry[0] += revs
            entry[1] |= broad
    env = _scan_env()
    for git_dir, (revs, broad) in repos.items():
        # The commits it adds, main's pins and the scan are read in the git directory gitleaks reads, as it does.
        scan = _Where(git_dir, None)
        revs = [*dict.fromkeys(revs), "--not", f"--remotes={REMOTE}"]
        proc = _git(scan, ["rev-list", "--count", *revs], deadline, env=env)
        if proc.returncode != 0:
            raise _Unscannable(f"git could not list the commits this push adds ({_tail(proc.stderr)})")
        count = _out(proc)
        if count == "0":
            continue
        version, binary = _binary()
        tip = _main(scan, deadline, env)
        with tempfile.TemporaryDirectory(prefix="secret-scan-") as tmp:
            findings = _gitleaks(binary, git_dir, revs, (scan, tip) if tip else None, Path(tmp), env, deadline)
        if findings:
            plural = "s" if count != "1" else ""
            if broad:
                return _found(version, findings, f"the {count} commit{plural} not on GitHub that this push may send",
                              True, tip is None,
                              "The hook read this push as sending more than literal refspecs name (a source no ref "
                              "names, a word holding `$`, backquotes in the call, words another command adds, "
                              "settings that push matching or mirrored branches, a git command it does not know), "
                              "so it scanned HEAD and every local branch and tag; push literal refspecs to scan only "
                              "what they send")
            return _found(version, findings, f"the {count} commit{plural} this push would add", True, tip is None)
    return None


def _before(write: _Step, w: int, push: _Step, p: int) -> bool:
    """Whether a write may run before a push (at index w and p), or beside it, so the push may send what it made."""
    if w < p or write.sub or push.sub or set(write.loops) & set(push.loops):
        return True
    if write.invocation == push.invocation:  # a git command the hook does not know, which may push and then commit
        return False
    for (write_pipe, write_member), (push_pipe, push_member) in zip(write.path, push.path):
        if write_pipe is not push_pipe:
            # Pipelines one after the other: the write runs beside the push only if the push's runs in the background.
            return push_pipe.background
        if write_member != push_member:
            return True  # a pipeline's commands run at once
    return True  # one runs inside the other's command


def _bash_refusal(command: str, cwd: object, deadline: float) -> str | None:
    # Every write this hook reads names git or gh, once the shell takes out quotes and backslashes (`g''it`).
    plain = command.replace("\\\n", "").translate(UNQUOTE).lower()
    if "git" not in plain and "gh" not in plain:
        return None
    base = cwd if isinstance(cwd, str) and os.path.isabs(cwd) and os.path.isdir(cwd) else os.getcwd()
    reader = _Reader(base, deadline, backquoted=_backquoted(command))
    reader.read(command, _State(base))
    steps = reader.steps
    for step in steps:
        if step.kind == "refuse":
            return step.text
    pushes = [(index, step) for index, step in enumerate(steps) if step.kind == "push"]
    if not pushes:
        return None
    for w, step in enumerate(steps):
        if step.kind == "write" and any(_before(step, w, push, p) for p, push in pushes):
            shown = step.text if len(step.text) <= 80 else step.text[:77] + "..."
            return (
                f"this command runs `{shown}` before a push in the same call, or beside it, and the hook reads what "
                "a push sends before the call runs, so it would scan the commits as they stood before. Run the push "
                "as a Bash call of its own, after the commands that make or move its commits: before or beside a "
                "push, its call may run only cd, pushd, popd, the shell's plain builtins, reads and filters that "
                "write no file and run no other program (cat, head, tail, grep, cut, wc, ls, jq and the like), and "
                "git commands that change no commit, ref or setting and take no settings from the call. A "
                "redirection may write /dev/null or another device, and the push's own output may go to a file "
                "(`git push ... > push.log 2>&1`). Run tests, lints, scripts, fetches and commits in an earlier call"
            )
    if any(step.push.where is None for _, step in pushes):
        return (
            "this command pushes from a directory the hook cannot name (one a variable or a substitution names, "
            "one that does not exist yet, a GIT_DIR it cannot read, or a ref store, object store or namespace the "
            "call moves), so it cannot tell which commits the push sends. Push from a literal path: "
            "`cd /path/to/repository && git push ...` or `git -C /path/to/repository push ...`"
        )
    try:
        return _scan_pushes([step.push for _, step in pushes], deadline)
    except _Unscannable:
        raise
    except Exception as error:  # the call adds commits: an error the hook does not expect refuses it
        raise _Unscannable(f"the scan hit an error the hook does not expect ({type(error).__name__}: {error})") \
            from error


def _contents(value: object) -> list[tuple[str, str]]:
    """Each file a GitHub MCP call sends: every `content` string at any depth, with the `path` beside it, in the
    order the call lists them (read without recursion, however deep the input nests)."""
    files: list[tuple[str, str]] = []
    nodes = [value]
    while nodes:
        node = nodes.pop()
        if isinstance(node, dict):
            content, path = node.get("content"), node.get("path")
            if isinstance(content, str):
                parts = path.split("/") if isinstance(path, str) else []
                path = "/".join(part for part in parts if part not in ("", "."))
                files.append((path or f"content-{len(files) + 1}", content))
            nodes += reversed([item for key, item in node.items() if key != "content"])
        elif isinstance(node, list):
            nodes += reversed(node)
    return files


def _same_repository(where: _Where, tool_input: dict, deadline: float, env: dict) -> bool:
    """Whether the call writes to the repository this checkout's origin names (or names none)."""
    owner, name = tool_input.get("owner"), tool_input.get("repo")
    if not isinstance(owner, str) or not isinstance(name, str):
        return True
    url = _out(_git(where, ["config", "--get", f"remote.{REMOTE}.url"], deadline, env=env))
    parts = re.sub(r"\.git/?$", "", url).replace(":", "/").rstrip("/").split("/")
    return [part.lower() for part in parts[-2:]] == [owner.lower(), name.lower()]


def _content_refusal(tool_input: dict, deadline: float) -> str | None:
    files = _contents(tool_input)
    if not files:
        return None
    paths = [path for path, _ in files]
    twice = sorted({path for path in paths if paths.count(path) > 1})
    if twice:
        raise _Unscannable(f"this GitHub write sends {', '.join(map(repr, twice))} more than once, and the hook "
                           "cannot tell which content lands; send each file once")
    try:
        return _scan_content(tool_input, files, deadline)
    except _Unscannable:
        raise
    except Exception as error:  # the call adds commits: an error the hook does not expect refuses it
        raise _Unscannable(f"the scan hit an error the hook does not expect ({type(error).__name__}: {error})") \
            from error


def _scan_content(tool_input: dict, files: list[tuple[str, str]], deadline: float) -> str | None:
    import tempfile

    version, binary = _binary()
    # The checkout this hook stands in reads as GitHub's repository as last fetched, in the scan's environment.
    project, plain = _Where(str(ROOT), None), _scan_env()
    common = _git(project, ["rev-parse", "--git-common-dir"], deadline, env=plain)
    ours = common.returncode == 0 and _same_repository(project, tool_input, deadline, plain)
    tip = _main(project, deadline, plain) if ours else None
    base, hint = None, ""
    branch = tool_input.get("branch")
    if ours and isinstance(branch, str) and branch:
        base = _commit(project, f"refs/remotes/{REMOTE}/{branch}", deadline, plain)
        if base is None:
            hint = (f"Its branch {branch!r} is not fetched here, so the hook scanned these files whole: "
                    f"`git fetch {REMOTE} {branch}` and send it again if a listed line is already on that branch")
    elif ours:
        base = tip  # the tools write to the default branch when they name none
    with tempfile.TemporaryDirectory(prefix="secret-scan-") as tmp:
        scratch = Path(tmp)
        env = _scan_env({**SCRATCH, "GIT_INDEX_FILE": str(scratch / "index")})
        if base:  # new objects go to a scratch store; the repository's own are read through it
            git_dir = os.path.normpath(os.path.join(str(ROOT), _out(common)))
            (scratch / "objects").mkdir()
            env.update(GIT_OBJECT_DIRECTORY=str(scratch / "objects"),
                       GIT_ALTERNATE_OBJECT_DIRECTORIES=os.path.join(git_dir, "objects"))
        else:  # another repository's write, or a branch not fetched: a scratch repository, the files committed whole
            git_dir = str(scratch / "scratch.git")
            _staged(_Where(tmp, None), ["init", "--quiet", "--bare", git_dir], "a scratch repository", env, deadline)
        where = _Where(tmp, git_dir)
        _staged(where, ["read-tree", base] if base else ["read-tree", "--empty"], "the branch's files", env, deadline)
        for path, content in files:
            blob = _staged(where, ["hash-object", "-w", "--stdin"], path, env, deadline,
                           content.encode("utf-8", "replace"))
            _staged(where, ["update-index", "--add", "--replace", "--cacheinfo", f"100644,{blob},{path}"], path, env,
                    deadline)
        tree = _staged(where, ["write-tree"], "the tree", env, deadline)
        commit = _staged(where, ["commit-tree", tree, *(["-p", base] if base else []), "-m", "scan"],
                         "the commit", env, deadline)
        del env["GIT_INDEX_FILE"]
        findings = _gitleaks(binary, git_dir, [commit, *(["--not", base] if base else [])],
                             (project, tip) if tip else None, scratch, env, deadline)
    if not findings:
        return None
    return _found(version, findings, "what this GitHub write sends", False, ours and tip is None, hint)


def _staged(where: _Where, args: list[str], what: str, env: dict, deadline: float, data: bytes | None = None) -> str:
    """Run one step of building the scratch commit; its output, or a refusal naming what it could not build."""
    proc = _git(where, args, deadline, env=env, data=data)
    if proc.returncode != 0:
        raise _Unscannable(f"the hook could not build {what!r} into the commit it scans ({_tail(proc.stderr)})")
    return _out(proc)


def refusal(event: object, deadline: float) -> str | None:
    """Why this tool call must not run, or None to let it through."""
    if not isinstance(event, dict):
        return None
    tool, tool_input = event.get("tool_name"), event.get("tool_input")
    if not isinstance(tool, str) or not isinstance(tool_input, dict):
        return None
    try:
        if tool == "Bash":
            command = tool_input.get("command")
            reason = _bash_refusal(command, event.get("cwd"), deadline) if isinstance(command, str) else None
        else:  # an MCP tool is mcp__<server>__<tool>, and the server's name may hold `__` itself
            server = tool[len("mcp__"):].rsplit("__", 1)[0] if tool.startswith("mcp__") else ""
            reason = _content_refusal(tool_input, deadline) if "github" in server.lower() else None
    except _Unscannable as error:
        reason = str(error)
    except RecursionError:  # a line or an input nested past Python's own limit, as no call needs
        reason = DEEP
    return None if reason is None else f"Refused by .claude/hooks/secret_scan_guard.py: {reason} ({LESSON})."


def _download(url: str, limit: int) -> bytes:
    import urllib.request

    request = urllib.request.Request(url, headers={"User-Agent": "earningsnerd-secret-scan-guard"})
    with urllib.request.urlopen(request, timeout=60) as response:  # a fixed https URL on github.com
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError(f"{url} is larger than {limit} bytes")
    return data


def _runs(path: Path, version: str) -> bool:
    try:
        proc = subprocess.run([str(path), "version"], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0 and proc.stdout.strip() == version


def install() -> int:
    """Download the pinned release archive, check its SHA-256, and put its gitleaks where the hook runs it."""
    import hashlib
    import io
    import platform
    import tarfile
    import tempfile

    try:
        version, sha256 = _pin()
    except _Unscannable as error:
        print(error, file=sys.stderr)
        return 1
    target = _platform()
    if target is None:
        print(f"gitleaks publishes no build this installs for {platform.system()} on {platform.machine()}",
              file=sys.stderr)
        return 1
    path = _installed(version, sha256, target)
    if _runs(path, version):
        print(f"gitleaks {version} is already installed at {path}")
        return 0
    archive = f"gitleaks_{version}_{target}.tar.gz"
    try:
        expected = sha256
        if target != "linux_x64":  # CI pins the linux archive; the release's checksums file vouches for the rest
            listed = {}
            sums = _download(RELEASE.format(version, f"gitleaks_{version}_checksums.txt"), 1 << 20)
            for line in sums.decode().splitlines():
                parts = line.split()
                if len(parts) == 2 and re.fullmatch(r"[0-9a-f]{64}", parts[0]):
                    listed[parts[1].lstrip("*")] = parts[0]
            if listed.get(f"gitleaks_{version}_linux_x64.tar.gz") != sha256:
                raise ValueError("the release's checksums file does not list CI's SHA-256 for the linux archive")
            if archive not in listed:
                raise ValueError(f"the release's checksums file lists no {archive}")
            expected = listed[archive]
        data = _download(RELEASE.format(version, archive), 64 << 20)
        actual = hashlib.sha256(data).hexdigest()
        if actual != expected:
            raise ValueError(f"{archive} has SHA-256 {actual}, not the {expected} its pin names")
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
            member = tar.getmember("gitleaks")
            handle = tar.extractfile(member) if member.isfile() else None
            if handle is None:
                raise ValueError(f"{archive} holds no regular file named gitleaks")
            binary = handle.read()
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp = tempfile.mkstemp(dir=path.parent, prefix=".gitleaks-")
        try:
            with os.fdopen(fd, "wb") as out:
                out.write(binary)
            os.chmod(temp, 0o755)  # an executable the owner installs for themselves
            os.replace(temp, path)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
    except (OSError, ValueError, KeyError, tarfile.TarError) as error:
        print(f"gitleaks {version} was not installed: {error}", file=sys.stderr)
        return 1
    if not _runs(path, version):
        path.unlink()  # the hook would run whatever stands there
        print(f"{archive}'s gitleaks does not report version {version}, so it was removed", file=sys.stderr)
        return 1
    print(f"installed gitleaks {version} ({target}, SHA-256 {expected} checked) at {path}")
    return 0


def main() -> int:
    if sys.argv[1:] == ["--install"]:
        return install()
    deadline = time.monotonic() + DEADLINE
    try:
        reason = refusal(json.load(sys.stdin.buffer), deadline)
    except RecursionError:  # an input nested past the JSON decoder's limit
        reason = f"Refused by .claude/hooks/secret_scan_guard.py: {DEEP} ({LESSON})."
    if reason is not None:
        decision = {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": reason}
        json.dump({"hookSpecificOutput": decision}, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
