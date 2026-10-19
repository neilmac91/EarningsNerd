"""PreToolUse hook: refuse a push or a GitHub content write when CI's pinned gitleaks finds a secret-shaped
literal in the commits it would add (E126).

The gate for lessons/ops-a-secret-shaped-literal-on-any-branch-fails-every-pr.md. CI's `secret-scan` job reads
every branch, so a secret-shaped literal pushed to any branch fails every pull request's scan until it leaves
the branch history or main pins it. This hook runs the job's gitleaks first (the version and archive SHA-256
that its GITLEAKS_VERSION and GITLEAKS_SHA256 name in .github/workflows/ci.yml) over the commits a call would
add to GitHub, and refuses the call on a finding.

.claude/settings.json runs it before every Bash command and every call to an MCP server whose name contains
"github" in any case. It reads
- each `git push` in a Bash command, as the hook's own copy of codex_mention_guard.py's shell reader reads the
  line (a word the call quotes or escapes reads as no operator or reserved word; an array's assignment,
  `a=(x y)`, as one word whose value it does not read, the process substitutions among its words beside its
  command; a process substitution among a command's words as the word bash gives it, `/dev/fd/63`) and as the
  hook's scanner reads its compounds (a case's pattern, its `(`, `|` and `)` with it, the word a case tests, the
  name a loop or the function keyword gives, and a command's words after a process substitution or an extended
  pattern read as no reserved word: `if)`, `for case in ...`, `echo <(true) done`, `@(a|b) done`; after `coproc`
  a command starts, past its NAME): `git` as a word or a path ending in `/git`, in any case, wherever it stands
  (among a wrapper's words, `env -C` followed, or another command's: one that runs nothing, as echo, is read from
  the shell's directory, and one that may run it anywhere, as find with -execdir, from one the hook cannot name),
  its global options, an alias (from `-c alias.<name>=...` or the config of the repository git runs in; a `!`
  alias as the commands it runs), and the strings that `bash -c` (its other options skipped), `eval` and `trap`
  run (a trap's at the end of its shell), each function where it is called, its definition's redirections with
  it, which bash sets up at each call (in the shell that defines it, not in the subshell a pipeline's command or
  a process substitution runs in: a new shell has only the ones `export -f` exports, or any of them in a call
  that may export one as declare -fx, typeset -fx or set -a do, which one other than bash may not import; one the
  call may define otherwise, or not at all, or that `unset` may remove, is a program the hook cannot read, which
  may push, when a body the call defines names git or gh, from a directory it cannot name) and each command
  substitution, as commands of their own. The scan reads the commits the push would add: those reachable from
  what it sends and from no ref under refs/remotes/origin, which stands for GitHub as last fetched. It sends each
  refspec's source (`+` dropped, the part before the last `:`; `tag <name>` is that tag), named as git push names
  it, through replace refs and past them, in the repository the push runs in; `--all`, `--branches`, `--mirror`
  and `--tags` their refs (abbreviated or negated as git reads them); with no refspec, HEAD, or every branch when
  `push.default` is matching or a `remote.<name>.push` or `remote.<name>.mirror` is set. A push whose words the
  hook cannot read whole (a source no ref names, a pattern outside refs/, a word holding `$`, backquotes in the
  call, settings the call gives git through a GIT_CONFIG* variable, --config-env, HOME or XDG_CONFIG_HOME, the
  words xargs or another command may add, a chain of more than five plain aliases) is read as sending HEAD and
  every branch and tag, and so is a git command it does not know (another program's `git-<name>`, an alias the
  call defines first, one xargs gives git from what it reads: `... | xargs git`), which may also make commits. A
  dry run, a delete and a refspec with no source send nothing.
- where a push runs, as bash's moves and variables leave it: `cd` with the HOME, CDPATH and OLDPWD the call sets,
  `pushd` and `popd` with their stack, `-C`, `--git-dir` and an exported or prefixed GIT_DIR with a literal path
  (a word up to git's command that bash may expand to others, one holding `$`, an escape, a brace expansion or,
  in a call that holds an unquoted `*`, `?` or `[`, a glob, or any there in a call with backquotes, may hide an
  option: a push after one is from a directory the hook cannot name), a `~` as bash expands it (one the hook
  cannot read anywhere in a call that may quote a `~` or run bash in POSIX mode), with the variables a command's
  `env -u` or `-i`, `exec -c` or new shell keeps (a new shell gets the ones its shell exports, and OLDPWD only
  from its command); `cd -L` by the path's text, as bash's own cd does (but for a `..` after a link, below), and
  `cd -P`, `-C`, `env -C`, `--git-dir` and GIT_DIR through its links, as the system does; a relative GIT_DIR or
  `--git-dir` from the directory git's `-C` options leave. What a command may or may not do (a move, a variable,
  a function it defines) leaves what each way the shell may go agrees on: after `&&` or `||` (the pipeline after
  `&&` from where the list before it may have succeeded, the one after `||` from where it may have failed); each
  branch of an if from where its condition left the shell, and with no `else`, none run; each arm of a case from
  where the case began, or where the arm just before ended if `;&` ended it, or where any arm before it ended if
  `;;&` ended that one, and none run; a loop at its end after its condition (a while's or an until's), with no
  turn (a for's or a select's), after a turn, or at a break or continue (one an eval runs too); a function at its
  end or a return; a command or a compound whose redirection may fail as one that may not run (a redirection that
  opens a file, as `< missing` or `> /dev/tty` with no terminal, or copies a descriptor the shell may not hold
  open, `2>&3`, or one from a word, an ambiguous redirect: `<& file`, `2>& /dev/null`, `<& <(cmd)`, `{fd}>& x`,
  or a `{name}` descriptor's close, `{fd}>&-`, as the name may hold none); and an EXIT trap at an `exit` as at
  the shell's end. A process substitution a compound command's redirection names runs from where the compound
  began (the outer one, when two closing words, as `} }` or `fi }`, end it), and one a function definition's
  names from where the function is called, as bash sets them up (a loop's, whose turn moves, among the pushes the
  loop runs from a directory the hook cannot name). The hook cannot name the directory that bash's `set -P`
  decides (a `..` after a link, by `cd -L` or by a `cd` or `pushd` with neither option, where the path's text and
  the real path part, since bash may hold the directory by either), nor the one sudo or another program a push
  runs under picks, one a PWD the call sets decides (cd takes OLDPWD from it, a new shell its directory), or one
  a trap on DEBUG, ERR or RETURN, which runs between commands, may change. A variable the call sets in a way the
  hook does not read (a name another variable holds; one read, printf -v or wait -p assigns; a for or select
  loop's variable; an addition or an element's assignment, `NAME+=value` or `NAME[1]=value`; an assignment before
  a special builtin, which sh and bash in POSIX mode keep) is one whose value it cannot read, as is every one it
  follows once a parameter or arithmetic expansion may assign one (`${GIT_DIR:=...}`), and a location variable or
  the HOME the session has that the call drops (unset, export -n, env -u or -i, exec -c, sudo), since the hook's
  own reads run in the session's environment. A loop whose turn leaves the shell otherwise than it found it
  (moved, or with a variable it follows or a function changed; OLDPWD aside when no cd - in the loop reads it)
  runs its pushes' later turns, and ends, in a directory the hook cannot name, and a function a turn defines,
  changes, removes or exports is read once more, as a later turn may call it, from such a directory. A string a
  shell other than bash runs (sh, which may be dash; zsh; ksh; a `!` alias, which git runs with sh) is read as
  bash reads it, but where the two part: there pushd, popd, a cd option but -L and -P, a `~`, `$'...'` and
  `$"..."` (which dash reads as `$` and a string), an exported function, which it may not import, and `time`
  before a function (which zsh and ksh run as the function, dash as a program by its name) leave what the hook
  cannot name.
- what comes before a push in its call. The hook runs before the call and reads the commits as they stand then,
  so before a push, or beside it (in its pipeline, after it while it runs in the background, in a loop around it,
  in a trap or a substitution, a process substitution a redirection names among them (`> >(cmd)`); a subshell,
  group, loop, if or case counts as one command of the pipeline it stands in, as does a nested shell), only cd,
  pushd, popd, the builtins the hook reads (echo, printf, test, read, set, export, unset, trap, eval and the
  like; any other, as declare, local, alias or source, it takes for a program), reads and filters that write no
  file and run no other program (cat, head, tail, grep, cut, wc, ls, jq and the like) and git commands that
  change no commit, ref or setting (but `git clean`, which may remove a directory a later cd enters) may run. A
  redirection that writes a file (one that is no device such as /dev/null; the push's own output may go to a
  file) makes its command a write, and so do settings or an option with which a git read may run a program or
  write a file (`-c`, a GIT_* variable or HOME the call sets, `--output`, grep's `-O`, ls-remote's
  `--upload-pack`, archive's `--remote`, `add -e`) and a file or a function a new shell may run before its string
  (BASH_ENV, ENV, which sh reads when interactive, ZDOTDIR, or an imported BASH_FUNC_*). A push after anything
  else (`git commit ... && git push`, a test run, a fetch), a push from a directory the hook cannot name (or with
  a ref store, object store or namespace the call moves: GIT_COMMON_DIR, GIT_OBJECT_DIRECTORY,
  GIT_ALTERNATE_OBJECT_DIRECTORIES, GIT_NAMESPACE, --namespace), the pushes it does not read (`git subtree push`,
  `git send-pack`, `git http-push`), a line nested more than five levels deep (shells, evals, traps, functions,
  `!` aliases, process substitutions), a case in a command substitution with a pattern no `(` opens, which the
  shell reader takes for the substitution's end, a parameter expansion the shell reader splits where bash reads
  one word (one with an operator character in it outside quotes, as `${x%)}` or `${x:-a;b}`, one in double
  quotes that nests a quote or a backquote, as `"${x:-"a"}"`, or a `<<` in a `${...}`, a `$[...]` or a subscript,
  as `${x:-<<E}` or `a[1<<2]=x`, which the reader takes for a here-document), a function's body (one that is no
  group, subshell or compound a reserved word opens, as `f() [[ -n x ]]`, among them) or a process substitution
  whose end the hook cannot find, a call the hook takes more than its 50 seconds to read, and a call with a line
  of more than 400,000 characters outside its here-documents (one long word reads in time that grows as its
  square) are refused, the last six whether or not the call pushes.
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
or global git configuration, no replace ref and no attributes but the repository's own info/attributes, and
hold the settings that change what `git log -p` prints at git's defaults, as on CI's runner (SCAN_CONFIG).
With no .gitleaks.toml on main, the scan names no rules and gitleaks reads its built-in ones, as CI's scan
does. gitleaks also reads the scanned directory's own .gitleaksignore, and its .gitleaks.toml when no --config
names one, so the scan refuses a call whose git directory holds either. A branch's own files stay in its
worktree, so a pin or rule only the branch carries reaches this scan no more than it reaches other pull
requests' runs.

The binary is installed once per machine and pin with `python3 .claude/hooks/secret_scan_guard.py --install`
under ~/.cache (or XDG_CACHE_HOME): the linux x64 release archive checked against that SHA-256, another
platform's against the release's checksums file once that file lists the pin for the linux archive. The hook
never downloads. A refusal is a JSON deny on stdout; a call the hook lets through exits 0 with no output.
Once the hook knows a call adds commits, it fails closed: a missing binary, an unreadable pin, a git older than
2.43 (the first to read attr.tree) or one whose version it cannot read, a scan that would read a repository whose
objects are not SHA-1, a git directory that holds a .gitleaksignore or a .gitleaks.toml, or a scan that fails,
errs or outlasts 50 seconds (the registration allows 60) refuses the call. So does a line or an input nested past
Python's own limits, and, before the hook counts a push's commits, a push whose repository git cannot read where
the push runs (none is there, and the push fails too, or the call's own settings let the push read one) and a git
directory that git, run there as the scan's reads are, does not take for the repository (a .git or a commondir
file in it, or a HEAD git cannot read, sends git elsewhere). So does an error the hook does not expect in reading
a Bash call that names git or gh. Any other error exits 1, which Claude Code reports as a hook error and lets the
call through, as it does for codex_mention_guard.py: a guardrail, not a boundary.

Not checked: a push a script, a program (env -S's string among them) or a shell's standard input runs; a git that
a variable, a substitution, an escape, a brace expansion, a glob or a shell alias or function names (`$GIT push`,
`$(which git) push`, `$'\\x67it' push`, `{g..g}it push`, `/usr/bin/[g]it push`, `g push`); a GIT_DIR, HOME or
CDPATH the shell's profile sets; a break in a function that an older bash compatibility level (BASH_COMPAT,
`shopt -s compat43`) lets leave its caller's loop; an assignment that set -k makes of a command's argument, and a
variable an arithmetic expression assigns outside `$((...))` (in `$[...]`, a subscript, an offset, [[ ]]'s -eq);
a command substitution inside an unquoted here-document's text, and a `$((` that bash reads as a command
substitution; the commits a git command the hook does not know makes as it runs, and a program the repository's
own configuration has a git read run (an fsmonitor, a textconv or clean filter); the commits a push sends to
submodules (--recurse-submodules); a commit a stale ref under refs/remotes/origin still holds (one a force-push
took off GitHub), and an MCP write to a branch fetched before it changed; attributes the repository's own
info/attributes sets; a squash or rebase merge of a pull request whose net change still holds a line pinned only
by its branch commit; content another program sends through GitHub's API, a URL a variable holds, and a GraphQL
mutation read from standard input or a variable; a GitHub MCP server registered under a name without "github"; a
session that loads no repository hooks; and a person's own push.
Tests: backend/tests/unit/test_secret_scan_guard.py.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from collections.abc import Iterator
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
# The longest line the hook reads outside its here-documents: the shell reader builds one long word in time that
# grows as its square, and checks no deadline while it does (400,000 characters take about ten seconds)
LONGEST = 400_000
LEAKS = 3  # the exit code gitleaks is given for a finding; its own error is 1
LOGGED = re.compile(r"\S+ (?:ERR|FTL) (.*)")  # a line gitleaks logs at an error level: its time, level and text
MIN_GIT = (2, 43)  # the first git to read attr.tree (GIT_CONFIG_COUNT, which carries SCAN_CONFIG, came in 2.31)
GIT_VERSION = re.compile(r"git version (\d+)\.(\d+)")
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
# its size (core.bigFileThreshold), a root commit's lines (log.showRoot), attributes, copies shown as differences
# (diff.renames) and a replace ref hide lines; an abbreviated or missing commit gives a finding a fingerprint main's
# pins do not match; shown signatures (log.showSignature) fail a scan whose git cannot run a signature's check (an
# SSH signature with no allowed-signers file set, or one whose program is missing); and a silenced graft hint
# (advice.graftFileDeprecated) would let a graft hide a commit's lines, where the hint fails the scan closed. The
# rest (decorations and prefixes among them, which gitleaks reads past) keep the output as CI's scan sees it.
# safe.directory lets the scan read a checkout another user owns, which the global configuration it does not read
# may have listed. Attributes would reach the scan from a file the repository names (core.attributesFile, held at
# none), from a tree it names (attr.tree), from the worktree around the git directory that its core.worktree names,
# from a bare repository's HEAD (which git 2.43 to 2.45 read) and from a .gitattributes in the git directory itself.
# attr.tree held at the empty tree takes the place of the last four, so only the repository's own info/attributes
# is read. A git older than 2.43, which knows no attr.tree, and a repository whose objects are not SHA-1, where
# EMPTY_TREE names no tree, refuse the scan (_new_enough). CI's checkout reads its own .gitattributes, and main holds
# none.
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"  # git's empty tree in SHA-1, the object format GitHub hosts
SCAN_CONFIG = (
    ("color.diff", "never"), ("log.showSignature", "false"), ("log.decorate", "no"),
    ("log.abbrevCommit", "false"), ("log.date", "default"), ("log.showRoot", "true"), ("format.pretty", "medium"),
    ("i18n.logOutputEncoding", "UTF-8"), ("diff.noprefix", "false"), ("diff.mnemonicPrefix", "false"),
    ("diff.srcPrefix", "a/"), ("diff.dstPrefix", "b/"), ("diff.relative", "false"), ("diff.renames", "true"),
    ("diff.renameLimit", "1000"), ("diff.algorithm", "myers"), ("diff.indentHeuristic", "true"),
    ("diff.interHunkContext", "0"), ("diff.submodule", "short"), ("core.bigFileThreshold", "512m"),
    ("core.useReplaceRefs", "false"), ("advice.graftFileDeprecated", "true"), ("core.attributesFile", os.devnull),
    ("attr.tree", EMPTY_TREE), ("core.quotePath", "true"), ("safe.directory", "*"),
)

SHELLS = ("sh", "bash", "zsh", "dash", "ksh")
# Words that run the command after them; a push they hold is read wherever its git word stands.
WRAPPERS = ("sudo", "env", "command", "exec", "time", "nice", "nohup", "timeout", "stdbuf", "xargs", "builtin")
# The wrappers' options that take the next word as their value, and the numbers and durations (nice's, timeout's,
# xargs') their words may be: any other word a wrapper runs as a program, which may run its git anywhere.
WRAPPER_VALUES = {
    "xargs": ("-a", "-d", "-E", "-I", "-L", "-n", "-P", "-s", "--arg-file", "--delimiter", "--max-args",
              "--max-procs", "--max-chars", "--process-slot-var"),
    "timeout": ("-s", "-k", "--signal", "--kill-after"),
    "stdbuf": ("-i", "-o", "-e", "--input", "--output", "--error"),
    "nice": ("-n", "--adjustment"),
}
NUMBER = re.compile(r"[0-9][0-9.]*[smhd]?")
# The shell's words that open and close a compound command, and the ones that only part it.
OPENERS = ("{", "if", "while", "until", "for", "select", "case")
CLOSERS = ("}", "fi", "done", "esac")
PARTS = ("!", "then", "else", "elif", "do")
TERMINATORS = (";;", ";&", ";;&")  # each ends a case's arm
SEPARATORS = (";", *TERMINATORS, "&&", "||", "|", "|&", "&", "(", ")")  # after one, a command starts
# The kinds of token _kinds tells apart: a reserved word that opens, parts or closes a compound command, a case's
# `in`, and a part of a case's pattern.
RESERVED, IN, PATTERN = "reserved", "in", "pattern"
LOOPS = ("while", "until", "for", "select")
HEADERS = ("for", "select", "case")  # the rest of a header's words run no command
REDIRECTS = ("<", ">", ">>", ">&", "<&", "&>", ">|", "<>", "<<", "<<<")
# The words a quoted word must not read as once its quotes go (`';'`, `'if'`, `\\time`)
COLLIDING = {*SEPARATORS, *REDIRECTS, *OPENERS, *CLOSERS, *PARTS, "function", "in", "time", "\n"}
# The redirections that open a file to write (any command given one is a write, unless it is the push itself), and
# the files they may name and still write nothing a push reads.
WRITES = (">", ">>", ">|", "&>", "&>>", "<>", ">&")
DEVICES = ("/dev/null", "/dev/stdout", "/dev/stderr", "/dev/tty")
SUBSTITUTED = "/dev/fd/63"  # the word bash gives a process substitution among a command's words
# What a redirection may open without failing: /dev/null, and the standard three by either name, which the hook
# takes as open
OPENED = ("/dev/null", "/dev/stdin", "/dev/stdout", "/dev/stderr", "/dev/fd/0", "/dev/fd/1", "/dev/fd/2")
# Commands that cannot make or move a commit, a ref or HEAD, write a file or run another program, so they may run
# before a push in its call. sed, awk, tee, sort and uniq are not among them: sed, awk and sort can run a program,
# and tee, sort and uniq can write a ref.
INERT = (
    ":", "true", "false", "test", "[", "[[", "echo", "printf", "set", "sleep", "pwd", "break", "continue", "wait",
    "exit", "return", "type", "which", "read", "cat", "head", "tail", "grep", "egrep", "fgrep", "wc", "ls", "date",
    "cut", "tr", "column", "nl", "basename", "dirname", "realpath", "readlink", "jq", "diff", "cmp", "sha256sum",
    "md5sum", "stat", "du", "df", "id", "whoami", "hostname", "uname",
)
# The special builtins, after which bash in POSIX mode, and sh, keep the assignments before them in the shell.
SPECIAL = (":", ".", "break", "continue", "eval", "exec", "exit", "export", "readonly", "return", "set", "shift",
           "times", "trap", "unset")
# Git commands that cannot make or move a commit, a ref or HEAD (the index and the worktree may change).
GIT_READS = (
    "status", "log", "diff", "show", "rev-parse", "rev-list", "ls-remote", "ls-files", "ls-tree",
    "cat-file", "describe", "merge-base", "shortlog", "blame", "grep", "for-each-ref", "show-ref",
    "show-branch", "name-rev", "cherry", "range-diff", "whatchanged", "count-objects", "version", "help",
    "check-ignore", "check-attr", "check-ref-format", "diff-tree", "diff-index", "diff-files", "verify-commit",
    "verify-tag", "fsck", "add", "rm", "mv", "restore", "reflog", "format-patch", "archive", "var",
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
# The variables by which the hook names where a command runs and what a push sends, named anywhere in a line.
FOLLOWED_NAMES = r"GIT_\w+|HOME|CDPATH|OLDPWD|PWD|XDG_CONFIG_HOME"
FOLLOWED = re.compile(rf"\b(?:{FOLLOWED_NAMES})\b")
# A parameter expansion that assigns one of them (`${GIT_DIR:=.git}`, `${HOME=x}`) or the variable another names
# (`${!ref:=x}`): where in the call it assigns, and what, the hook does not follow.
ASSIGNING = re.compile(rf"\$\{{(?:!\w+|{FOLLOWED_NAMES})(?:\[[^]}}]*\])?:?=")
# The builtins that assign the variables their words name, as bash's getopt reads their options: the letters that
# take a value, the ones whose value is a variable's name, and whether the words after the options are names too.
NAMING = {"read": ("adinNptu", "a", True), "printf": ("v", "v", False), "wait": ("p", "p", False)}
# The variables that name what a new shell runs before its string: a file, or a function it imports.
STARTUP = ("BASH_ENV", "ENV", "ZDOTDIR")
# The variables by which git finds a push's repository: one the hook cannot read, the session's own among them once
# the call drops it (the hook's reads run in the session's environment), leaves a push it cannot place.
LOCATING = ("GIT_DIR", "GIT_WORK_TREE", "GIT_CEILING_DIRECTORIES", "GIT_DISCOVERY_ACROSS_FILESYSTEM", *RELOCATING)
CD_VARIABLES = ("HOME", "CDPATH")  # what cd reads besides its words, exported or not; OLDPWD is the state's `old`
# The options with which a git read writes a file or runs a program, by command (a long one also abbreviated, a
# short one also in a cluster): `--output` is a diff option of log, show, diff and the rest.
READ_RISKS = {"": ("--output",), "grep": ("-O", "--open-files-in-pager"), "ls-remote": ("-u", "--upload-pack"),
              "archive": ("--remote", "--exec"), "add": ("-e", "--edit")}
STACK_INDEX = re.compile(r"[+-][0-9]+")  # pushd's and popd's +N and -N: an entry of the stack `dirs -v` lists
CUT = ("this call holds a case in a command substitution with a pattern that no `(` opens, which the hook's shell "
       "reader takes for the substitution's end, so it cannot read what the substitution runs. Write the pattern "
       "as `(pattern)`")
BRACED = ("this call holds a parameter expansion the shell reader splits where bash reads one word, or a `<<` "
          "it reads as a here-document where bash reads it in a word, so it cannot tell what the call runs: an "
          "expansion with an operator character in it outside quotes (`${x%)}`, `${x:-a;b}`), one in double quotes "
          "that nests a quote or a backquote (`\"${x:-\"a\"}\"`, `\"${x:-\\}\"a\"}\"`), or a `<<` in a "
          "`${...}`, a `$[...]` or a subscript (`${x:-<<E}`, `a[1<<2]=x`). Quote the first (`\"${x%)}\"`), take the "
          "inner quotes out of the second, or write it more plainly")
UNENDED = ("this call holds a function's body or a process substitution whose end the hook cannot find (a body "
           "that is no `{ ...; }` group, `( ... )` subshell or other compound command it reads, as `f() [[ -n x ]]`, "
           "among them), so it cannot tell what runs after it. Write it more plainly")
DEEP = ("this call nests its commands more than five levels deep (shells, evals, traps, functions, `!` aliases, "
        "process substitutions), past what the hook reads, so it cannot tell what the call pushes or commits. Run "
        "it less deeply nested")
ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
SUBSCRIPTED = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\[")  # a word's start that opens a subscript, as `a[1]=x` does
# The head of a word bash takes for an assignment at a command's start: a name, a subscript and a `+`, up to its
# `=` (`a=`, `a[1]=`, `a+=`). One that is all of a word before a `(`, which the shell reader splits off, begins an
# array's assignment (`a=(x y)`).
ASSIGNS = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)(\[[^]]*\])?(\+?)=")
# A `~` the call may quote (`'~'`, `\~`, `~"/x"`), which bash leaves as written but the shell reader shows bare.
QUOTED_TILDE = re.compile(r"""['"\\]~|~[^/\s;&|()<>'"\\]*['"\\]""")
# A call that may run bash in POSIX mode (`--posix`, `set -o posix`, POSIXLY_CORRECT, SHELLOPTS), which leaves a `~`
# after `=` in a command's word as written.
POSIX_MODE = re.compile("posix", re.IGNORECASE)
# A word bash may expand to other words, or to an option the shell reader shows otherwise: a variable or a
# substitution, an escape (`$'\\x2dC'` reaches the hook as written), a brace expansion (`{-C,<dir>}`).
EXPANDS = re.compile(r"[$\\]|\{[^{}]*(?:,|\.\.)[^{}]*\}")
# A word that holds git or gh as a word of its own, in any case: alone, at a path's end or beside punctuation
# (`git`, `/usr/bin/git`, `GIT=git`, `git-lfs`, `cd x;git`), not inside a longer word (`github`, `high`, `right`). It
# is broader than how the hook reads a program's name, so that a body which may run git in a way it does not read
# still counts.
NAMES_GIT = re.compile(r"(?<![a-z0-9_])(?:git|gh)(?![a-z0-9_])")
GLOB = re.compile(r"[*?[]")  # in a call that holds one unquoted, a glob (`-?`, which a file named `-C` matches)
# A command that may export a function the hook does not follow: declare or typeset with -x (`-fx`), set with -a or
# -o allexport, which exports each function defined after it.
EXPORTING = re.compile(r"\b(?:declare|typeset)\b[^\n;&|]*\s-[A-Za-z]*x"
                       r"|\bset\b[^\n;&|]*\s(?:-[A-Za-z]*a|-o\s*allexport)")
# A quote dash reads as `$` and a quoted string (`$'x'`, `$"x"`), where bash reads one word.
DOLLAR_QUOTE = re.compile(r"""\$['"]""")
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


class _Cut(str):
    """The text of a substitution the shell reader ended at a case pattern's `)`, which bash reads as the
    pattern's: what the substitution runs, the hook cannot read, nor where the line goes on."""


# The operator characters a quote or a backslash holds, kept in their word as characters no shell word holds, and
# the mark before what a quote or a backslash held: a word that would read as an operator or a reserved word once
# its quotes go keeps the mark, as the shell reads neither in it.
HELD = {char: chr(0xE001 + k) for k, char in enumerate("();<>|&\n")}
UNHELD = {ord(value): key for key, value in HELD.items()}
MARK = "\ue000"
# the mark before a run of digits, or a `{name}`, the shell takes for a redirection's descriptor (`2>file`, `1>&2`,
# `{fd}>file`): one quoted, or set apart from its operator (`'2'>file`, `2 >file`), is a word
FD = "\ue009"
# a run of digits, or a `{name}`, the shell takes for a redirection's descriptor (`2>file`, `{fd}>file`)
DESCRIPTOR = re.compile(r"([0-9]+|\{[A-Za-z_][A-Za-z0-9_]*\})[<>]")
# the token before a process substitution lifted from an array's words, which runs beside its command, no word of it
LIFTED = "\ue00a"


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
    the directory `cd -` returns to, the variables the command sets (`$` once the hook cannot read one), and the
    ones of cd's it holds unexported, which no program it runs gets."""

    def __init__(self, dir: str | None, dirs: list | None = None, old: str | None = None, env: dict | None = None,
                 hidden: set | None = None):
        self.dir, self.dirs, self.old, self.env, self.hidden = dir, dirs or [], old, env or {}, set(hidden or ())

    def copy(self) -> _State:
        return _State(self.dir, list(self.dirs), self.old, dict(self.env), self.hidden)

    def followed(self) -> tuple:
        """What a push reads of the state besides its directory: OLDPWD, the variables FOLLOWED names and the ones
        the shell holds unexported."""
        return self.old, {name: value for name, value in self.env.items() if FOLLOWED.fullmatch(name)}, self.hidden

    def same(self, other: _State, old: bool = True) -> bool:
        """Whether a push reads this state as it reads `other` (leaving OLDPWD aside unless `old`)."""
        return (self.dir, self.dirs, self.followed()[not old:]) == (other.dir, other.dirs, other.followed()[not old:])

    def obscure(self) -> None:
        """The call sets or unsets a variable by a name the hook cannot read, which may be any variable it follows."""
        for name in ("GIT_DIR", *CD_VARIABLES, *CONFIG_HOMES, "OLDPWD", "PWD", *STARTUP):
            self.set(name, "$")

    def blend(self, other: _State) -> None:
        """Keep what this state and `other` agree on, and make the rest unknown: the shell is in one or the other, as
        a command between them ran or did not."""
        if self.dir != other.dir:
            self.dir = None
        if self.old != other.old:
            self.old = None
        if self.dirs != other.dirs:
            self.dirs = [None] * max(len(self.dirs), len(other.dirs))
        for name in {*self.env, *other.env}:
            if self.env.get(name) != other.env.get(name):
                self.env[name] = "$"
        # One the shell holds unexported one way and not the other is one a program may or may not get. A program
        # gets none of cd's the shell holds unexported, whose value the hook's own reads then cannot read either.
        mixed = (self.hidden ^ other.hidden) - set(CD_VARIABLES)
        for name in mixed:
            self.env[name] = "$"
        self.hidden = (self.hidden | other.hidden) - mixed

    def set(self, name: str, value: str) -> None:
        """A variable the call sets, `$` when the hook cannot read its value; OLDPWD is where `cd -` goes, kept as
        written (from the shell's directory), since cd takes it by its text or through its links."""
        if name == "OLDPWD":
            readable = bool(value) and not set(value) & set("$`\n") and (os.path.isabs(value) or self.dir is not None)
            self.old = os.path.join(self.dir or "/", value) if readable else None
        else:
            self.env[name] = value


class _List:
    """An and-or list being read: the state and functions it began with and, once an `&&` or `||` follows a
    pipeline, the ways the pipelines read so far may leave the shell (each a state and its functions, the ways
    blended), by the status the list then has: the pipeline after `&&` runs where it may have succeeded, the one
    after `||` where it may have failed."""

    def __init__(self, start: _State, functions: dict):
        self.start, self.functions = start, dict(functions)
        self.operator: str | None = None  # the one before the pipeline being read
        self.succeeded: tuple[_State, dict] | None = None
        self.failed: tuple[_State, dict] | None = None

    def ended(self, state: _State, functions: dict) -> None:
        """The pipeline being read left the shell in `state`, with either status; it ran only where the operator
        before it let it, so the list may also have the status it had before."""
        way = (state.copy(), dict(functions))
        if self.operator is None:
            self.succeeded = self.failed = way
        elif self.operator == "&&":
            self.succeeded, self.failed = way, _either(self.failed, way)
        else:
            self.succeeded, self.failed = _either(self.succeeded, way), way


def _either(one: tuple[_State, dict], other: tuple[_State, dict]) -> tuple[_State, dict]:
    """The shell after one of two ways: what they agree on, and the rest unknown."""
    state = one[0].copy()
    state.blend(other[0])
    return state, _merged([one[1], other[1]])


def _merged(tables: list[dict]) -> dict:
    """The functions each of `tables` defines: one they define otherwise, or one some leave out, is one the hook
    cannot read (None)."""
    names = {name for table in tables for name in table}
    return {name: tables[0].get(name) if all(table.get(name) == tables[0].get(name) for table in tables) else None
            for name in names}


class _Flow:
    """The ways out of a compound command (an if, a case, a loop): the state and the functions each branch, break
    or continue leaves, and those after its condition (an if's or a while's, or a for's header), which the next
    branch, condition or turn starts from."""

    def __init__(self, start: _State, functions: dict):
        self.cond, self.functions = start.copy(), dict(functions)
        self.ways: list[tuple[_State, dict]] = []  # an if's or a case's branches before the last, a loop's breaks
        self.turns: list[tuple[_State, dict]] = []  # a loop's continues, each the end of a turn
        self.otherwise = False  # an if's `else`: one of its branches always runs
        self.olds = 0  # a loop's: the reader's count of cd - when it opened
        self.through: str | None = None  # a case's: the `;;`, `;&` or `;;&` that ended the arm before
        self.tested: list[tuple[_State, dict]] = []  # a case's: where arms `;;&` ended, for each later arm

    def after(self, state: _State, functions: dict) -> None:
        self.cond, self.functions = state.copy(), dict(functions)


def _emptied(env: dict) -> None:
    """A command `env -i`, `env -` or `exec -c` starts afresh: none of the variables the call gave it, the session's
    own location variables, which the hook's reads would still take, dropped too, and HOME, which cd and `~` read,
    one the hook cannot read."""
    env.clear()
    env.update({name: "$" for name in LOCATING if name in os.environ}, HOME="$")


def _held(script: str) -> str:
    """The shell reader's text (each quoted string single-quoted) with what its quotes and backslashes hold
    marked: an operator character as HELD's, and MARK before each held string."""
    out, i, quoted = [], 0, False
    while i < len(script):
        char = script[i]
        if quoted:
            quoted = char != "'"
            out.append(HELD.get(char, char) if quoted else char)
        elif char == "'":
            quoted = True
            out.append("'" + MARK)
        elif char == "\\" and i + 1 < len(script):
            following = script[i + 1]
            out.append(MARK + (HELD[following] if following in HELD else script[i:i + 2]))
            i += 1
        elif (match := DESCRIPTOR.match(script, i)) and (not out or out[-1][-1:] in " \t\n;&|()<>"):
            out.append(FD + match.group(1))  # a descriptor that starts a word, right before `<` or `>`
            i = match.end(1)
            continue
        else:
            out.append(char)
        i += 1
    return "".join(out)


def _arrays(tokens: list[str]) -> list[str]:
    """The tokens with each array's assignment (`files=(a b)`, `out+=()`) one word whose value the hook does not
    read (`files=$`), as bash reads it where the shell reader splits it at its `(`, and the process substitutions
    among its words after it, which run beside its command."""
    out, k = [], 0
    while k < len(tokens):
        opens = bool(ASSIGNS.fullmatch(tokens[k])) and tokens[k + 1:k + 2] == ["("]
        end = _closing(tokens, k + 1) if opens else None
        if opens and end is None:  # one no `)` closes, which bash rejects: the rest as the shell reader split it
            return out + tokens[k:]
        if end is None:
            out.append(tokens[k])
            k += 1
            continue
        out.append(tokens[k] + "$")
        j = k + 2
        while j < end:  # `<(...)` or `>(...)` among its words: it runs, and is no word of its command
            close = _closing(tokens, j + 1) if tokens[j] in ("<", ">") and tokens[j + 1:j + 2] == ["("] else None
            if close is not None and close < end:
                out += [LIFTED, *tokens[j:close + 1]]
                j = close + 1
            else:
                j += 1
        k = end + 1
    return out


def _kinds(tokens: list[str], i: int = 0) -> Iterator[str | None]:
    """The kind of each token from `i`, as bash parses it: RESERVED for one of OPENERS, CLOSERS or PARTS where a
    command starts (after `time` too), but for the name a for, a select or the function keyword gives and the word
    a case tests (`for case in ...`); IN for a case's `in`; PATTERN for each part of a case's pattern, its `(`, its
    words, its `|`s and its `)`, where a reserved word is a word (`if)`, `(esac)`, `a|done)`) and only an `esac`
    that begins one with no `(` closes the case; None for any other. A `(` among a command's words opens an
    extended pattern (`@(a|b)`), whose words are words; after it, or after a process substitution's `)`, the
    command's words go on (`echo <(true) done`). After coproc a command starts, past its NAME."""
    cases: list[str] = []  # each open case's place: "word", "in", "pattern" (one is next), "more" (after its `(` or
    # a `|`), "words" (after a word of it) or "arm"
    want, group = "command", 0  # what the next token is; how deep in an extended pattern's `@(...)` a pattern is
    nest: list[int] = []  # per open case, how deep its arm is in parentheses (a subshell's, `for ((;;))`)
    # each `(` open outside a case's pattern: "ps" (a process substitution's), "glob" (an extended pattern's, among
    # a command's words) or "" (a subshell's); and what the token before was read as
    parens: list[str] = []
    last = None
    for k in range(i, len(tokens)):
        token, at, kind = tokens[k], cases[-1] if cases else "arm", None
        reading = want
        if parens and parens[-1] == "glob":  # an extended pattern's words: no command, operator or case
            if token in ("(", ")"):
                parens.append("glob") if token == "(" else parens.pop()
            last = reading
            yield None
            continue
        if at == "arm" and token == "(" and last == "word" and not (k > i and tokens[k - 1] in ("<", ">")):
            parens.append("glob")  # a `(` among a command's words, which bash reads as no other: `@(a|b)`, `*(x)`
            last = reading
            yield None
            continue
        if at == "word":
            cases[-1] = "in"
        elif at == "in":
            if token == "in":
                kind, cases[-1] = IN, "pattern"
        elif at != "arm":
            if at == "pattern" and token == "esac":
                kind = RESERVED
                cases.pop()
                nest.pop()
            elif at != "pattern" or token != ";":  # a blank line may stand before a pattern
                kind = PATTERN
                if token == "(" and (at == "words" or group):
                    group += 1
                elif token == ")" and group:
                    group -= 1
                else:
                    cases[-1] = "more" if token in ("(", "|") else "arm" if token == ")" else "words"
        elif token in OPENERS + CLOSERS + PARTS and (want in ("command", "time", "timed", "coproc")
                                                     or (want == "loop" and token == "do")):  # `for i do ...`
            kind = RESERVED
            if token == "case":
                cases.append("word")
                nest.append(0)
            elif token == "esac" and cases:
                cases.pop()
                nest.pop()
        elif cases and token in ("(", ")"):
            nest[-1] = max(nest[-1] + (1 if token == "(" else -1), 0)
        elif token in TERMINATORS and cases and not nest[-1]:
            cases[-1] = "pattern"
        substituted = False  # a process substitution's `)`, after which its command's words go on
        if at == "arm" and kind is None and token in ("(", ")"):
            if token == "(":
                parens.append("ps" if k > i and tokens[k - 1] in ("<", ">") else "")
            elif parens:
                substituted = parens.pop() == "ps"
        if kind == RESERVED:
            want = token if token in ("for", "select") else "command"
        elif kind is not None or at != "arm":
            want = "command" if cases and cases[-1] == "arm" and token == ")" else "word"
        elif want in ("for", "select"):
            want = "loop"  # its name came: `in`, `do` or a separator is next
        elif want == "time" and token == "-p":
            want = "timed"  # `--` may follow
        elif want == "function" or token in SEPARATORS or (want in ("time", "timed") and token == "--"):
            want = "command"
        elif want == "command" and token in ("time", "function", "coproc"):
            want = token
        elif want == "coproc":  # its NAME, before a compound command, or the simple command it runs
            want = "command" if tokens[k + 1:k + 2] and tokens[k + 1] in OPENERS else "word"
        else:
            want = "word"
        if substituted:
            want = "word"
        last = reading
        yield kind


def _cut_short(tokens: list[str]) -> bool:
    """Whether the shell reader may have ended a command substitution at a case pattern's `)`: a case the tokens
    begin has no `esac`, or a `(` before such a pattern stays open (`$( (case x in x) ...;; esac); ... )`)."""
    cases = depth = 0
    for token, kind in zip(tokens, _kinds(tokens)):
        if kind == RESERVED and token in ("case", "esac"):
            cases += 1 if token == "case" else -1
        elif kind is None and token in ("(", ")"):
            depth += 1 if token == "(" else -1
    return cases > 0 or depth > 0


def _shell_reader():
    """codex_mention_guard.py's shell reader, so both hooks read a command the way the shell does. This copy of
    the module, which no other process shares, marks the text of an arithmetic `$((...))` so it is not read
    as commands, and that of a substitution it ends at a case pattern's `)`; gives the `;;`, `;&` and `;;&` that
    end a case's arm tokens of their own, which a blank line's `;`s are not; and keeps a quoted or escaped
    operator or reserved word a word (`echo ';'`, `'if'`), where the reader takes its quotes off first."""
    import importlib.util

    path = Path(__file__).with_name("codex_mention_guard.py")
    spec = importlib.util.spec_from_file_location("codex_mention_guard", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    substitution = module._substitution

    def marked(command: str, i: int, extra: list, read: object, arith: bool = False) -> tuple[str, int]:
        text, end = substitution(command, i, extra, read, arith)
        if arith:
            return _Arithmetic(text), end
        return (_Cut(text) if _cut_short(module._command_tokens(text)) else text), end

    def held(script: str) -> list[str]:
        words = []
        for token in tokens(_held(script)):
            plain = token.replace(MARK, "").translate(UNHELD)
            words.append(MARK + plain if plain != token and plain in COLLIDING else plain)
        return _arrays(words)

    module._substitution, tokens, module._command_tokens = marked, module._command_tokens, held
    module.SHELL_OPERATORS = (";;&", ";;", ";&", *module.SHELL_OPERATORS)
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
    text = re.sub(r"\x1b\[[0-9;]*m", "", stderr.decode("utf-8", "replace"))
    lines = [line.strip() for line in text.splitlines() if line.strip()][-3:]
    return " / ".join(lines) or "no output"


def _logged(stderr: bytes) -> str:
    """Why gitleaks failed: the first error it logged (git's own complaint, when git's stderr failed the scan) and
    the last (what gitleaks made of it), or the line of a panic or a Go runtime fatal error, since its closing lines
    report only how much of the scan it finished; else what _tail shows."""
    text = re.sub(r"\x1b\[[0-9;]*m", "", stderr.decode("utf-8", "replace"))  # its fatal lines are coloured always
    logged = [match.group(1).strip() for match in map(LOGGED.match, text.splitlines()) if match]
    # A line git left empty names nothing; a crash logs no error, and its own line names it.
    errors = [error for error in logged if (error[len("[git]"):] if error.startswith("[git]") else error).strip()]
    crashed = [line.strip() for line in text.splitlines() if line.startswith(("panic: ", "fatal error: "))]
    errors = errors or crashed[:1]
    return " / ".join(dict.fromkeys((errors[0], errors[-1]))) if errors else _tail(stderr)


def _too_old(version: str) -> str | None:
    """Why a git that reports `version` (`git version` prints it) cannot run the scan, or None when it can."""
    found = GIT_VERSION.match(version)
    if found and tuple(map(int, found.groups())) >= MIN_GIT:
        return None
    needed = ".".join(map(str, MIN_GIT))
    shown = (f"this machine's git ({version[:60]}) is older than {needed}" if found else
             f"the hook cannot read this machine's git version ({version[:60]!r})")
    return (f"{shown}: git {needed} is the first to read attr.tree, which the scan holds at the empty tree so that "
            f"no tree's or worktree's .gitattributes hides a line from it. Install git {needed} or later, then run "
            "the call again")


def _new_enough(where: _Where, env: dict, deadline: float, repository: bool = True) -> None:
    """Refuse a scan by a git older than MIN_GIT, which reads no attr.tree, or, when the scan reads `where`'s
    repository, one whose objects are not SHA-1, where EMPTY_TREE names no tree: either way the attributes attr.tree
    stands in for would reach the scan."""
    reason = _too_old(_out(_git(where, ["version"], deadline, env=env)))
    if reason is None and repository:
        kind = _out(_git(where, ["rev-parse", "--show-object-format"], deadline, env=env))
        if kind != "sha1":
            reason = (f"this repository's objects are {kind or 'of a format git does not name'}, not SHA-1, so the "
                      "empty tree the scan holds attr.tree at names no tree here, and a tree's or worktree's "
                      ".gitattributes could hide a line from it. Run the call from a SHA-1 clone")
    if reason is not None:
        raise _Unscannable(reason)


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


def _join(base: str | None, value: str, real: bool = False) -> str | None:
    """The directory `value` names from `base`, or None when the hook cannot name it: by the path's text, as bash's
    own cd takes it, where each directory a `..` leaves exists, as bash checks; or, when `real`, as the system takes
    it, through each link before a `..`, where the path exists. A `~` here is a name like any other: the shell
    expands one before a command sees it (_Reader._tilde)."""
    if not value or "$" in value or "`" in value or "\n" in value:
        return None
    path = value
    if not os.path.isabs(path):
        if base is None:
            return None
        path = os.path.join(base, path)
    if real:
        return os.path.realpath(path) if os.path.exists(path) else None
    parts: list[str] = []
    for part in path.split("/"):
        if part == "..":
            if not os.path.isdir("/" + "/".join(parts)):
                return None
            parts = parts[:-1]
        elif part not in ("", "."):
            parts.append(part)
    return "/" + "/".join(parts)


def _landing(base: str | None, value: str | None, option: str) -> str | None:
    """Where a cd or pushd to `value` lands: by the path's text with cd's -L, through its links with -P, and with
    neither where the two agree. Where they differ, bash's set -P (the call's, a profile's, an exported SHELLOPTS)
    chooses, which the hook does not follow, so it cannot name the directory. bash may hold `base` by its real path
    rather than its text, as a cd with neither option under set -P does, so a path's text must land in one directory
    from either."""
    if not value:
        return None
    text = _join(base, value)
    if option != "P" and text is not None and base is not None:
        other = _join(os.path.realpath(base), value)
        if other is None or os.path.realpath(other) != os.path.realpath(text):
            return None
    if option == "L":
        return text
    real = _join(base, value, real=True)
    if option == "P":
        return real
    return text if text is not None and real is not None and os.path.realpath(text) == real else None


def _unset(env: dict, name: str) -> None:
    """Drop a variable from what a command passes on: the session's own location variable or HOME, which the hook's
    reads and `~` would still take, becomes one it cannot read."""
    if name == "HOME" or (name in LOCATING and name in os.environ):
        env[name] = "$"
    else:
        env.pop(name, None)


def _policed(env: dict) -> None:
    """sudo keeps or drops each variable as its policy says: the ones the hook follows become ones it cannot read."""
    for name in {*env, *os.environ}:
        if name in (*LOCATING, *CD_VARIABLES, *CONFIG_HOMES, "OLDPWD", "PWD"):
            env[name] = "$"
    env["HOME"] = "$"


def _named(name: str, args: list[str]) -> list[str]:
    """The variables a read, a printf -v or a wait -p assigns (wait -p unsets its variable first), each by the
    variable's own name: `NAME[sub]` is an element of NAME, which an exported NAME then no longer passes on."""
    values, naming, operands = NAMING[name]
    names, k = [], 0
    while k < len(args) and args[k].startswith("-") and args[k] != "-":
        if args[k] == "--":
            k += 1
            break
        letters = args[k][1:]
        for at, letter in enumerate(letters):
            if letter in values:  # its value is the rest of the group, or the next word
                value = letters[at + 1:]
                if not value and k + 1 < len(args):
                    k, value = k + 1, args[k + 1]
                if letter in naming:
                    names.append(value)
                break
        k += 1
    return [word.split("[", 1)[0] for word in names + (args[k:] if operands else [])]


def _closed(words: list[str], frames: list) -> int:
    """How many compound commands the closing words that begin `words` close (`} }`, `fi }`): each the innermost one
    still open, as the walk closes them. A subshell closes with a `)`, no closing word, so every one these count is a
    reserved-word compound (`{ }`, if, case, a loop), never a subshell."""
    count = 0
    while count < min(len(words), len(frames)) and words[count] in CLOSERS:
        count += 1
    return count


def _closing(tokens: list[str], i: int) -> int | None:
    """The index of the `)` that closes the `(` at `i`, or None when none does. A case pattern's parentheses close
    nothing (`( case x in a) ...;; esac )`)."""
    depth = 0
    for j, kind in enumerate(_kinds(tokens, i), i):
        if kind is None and tokens[j] in ("(", ")"):
            depth += 1 if tokens[j] == "(" else -1
            if depth == 0:
                return j
    return None


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


def _compound_end(tokens: list[str], j: int) -> int | None:
    """The index past the compound command that starts at `j` (or on a later line), a function's body, or None when
    it has no end or is none the hook reads: its reserved words counted as _kinds finds them, so a quoted `done` in
    an argument closes nothing, nor a pattern's (`if)`) or a loop's name (`for case in ...`)."""
    while tokens[j:j + 1] == [";"]:  # a body on a later line (`f()`, then `{`): bash reads no `;` there
        j += 1
    if tokens[j:j + 1] == ["("]:
        end = _closing(tokens, j)
        return None if end is None else end + 1
    depth = 0
    for k, kind in enumerate(_kinds(tokens, j), j):
        if k == j and not (kind == RESERVED and tokens[k] in OPENERS):
            return None  # a body that is no compound command the hook reads: `f() [[ -n x ]]`, dash's `f() cd /`
        if kind == RESERVED and tokens[k] in OPENERS:
            depth += 1
        elif kind == RESERVED and tokens[k] in CLOSERS:
            depth -= 1
            if depth <= 0:
                return k + 1
    return None


def _redirected(tokens: list[str], k: int) -> int:
    """The index past the redirections from `k` on (`> file`, `2>&1`, `<(cmd)`): where what follows the command they
    belong to stands."""
    while k < len(tokens) and (tokens[k].startswith(FD) or tokens[k] in REDIRECTS):
        if tokens[k].startswith(FD):
            k += 1
        elif tokens[k] in ("<", ">") and tokens[k + 1:k + 2] == ["("]:  # a process substitution
            end = _closing(tokens, k + 1)
            k = len(tokens) if end is None else end + 1
        else:  # the operator (`<>` and `&>>` come as two tokens, `&> >(cmd)` as `&>` and a process substitution),
            # then its target: a word, or a process substitution
            k += 1 + (tokens[k] in ("<", "&>") and tokens[k + 1:k + 2] == [">"] and tokens[k + 2:k + 3] != ["("])
            if tokens[k:k + 1] in (["<"], [">"]) and tokens[k + 1:k + 2] == ["("]:  # `< <(cmd)`
                end = _closing(tokens, k + 1)
                k = len(tokens) if end is None else end + 1
            else:
                k += 1
    return k


def _may_fail(operator: str, descriptor: str, target: str | None) -> bool:
    """Whether a redirection may fail, so that bash runs no command it belongs to. One that copies a descriptor may
    when it names one the shell may not hold open (`2>&3`), or a word bash takes for none, an ambiguous redirect
    (`<& file`, `2>& /dev/null`, `<& <(cmd)`, `{fd}>& /dev/null`); `>&` alone or after 1 takes a word for `&>`'s
    file. One that closes the descriptor a `{name}` holds (`{fd}>&-`) may, as the name may hold none. Any other may
    when it opens a file (`< missing`, `> /dev/tty` with no terminal), but not /dev/null, the standard three or a
    process substitution (target None: `2>/dev/null`, `> >(cmd)`). A here-document or here-string never fails."""
    if operator in (">&", "<&"):
        if target in ("0", "1", "2") or (target == "-" and not descriptor.startswith("{")):
            return False
        if operator == "<&" or descriptor not in ("", "1"):
            return True
    return not operator.startswith("<<") and target is not None and target not in OPENED


def _braced(script: str) -> bool:
    """Whether a line the shell reader has scanned (`script`: each quoted string one single-quoted word, `'\\''`
    for a quote in it, with no here-document's text and no comment) holds a `${...}` it splits where bash reads one
    word: one outside quotes with an operator character in it that nothing it nests holds (`${x%)}`,
    `${x:-;cd y;}`), or a quoted string that ends inside one, as a double-quoted one does at a quote bash nests
    there (`"${x:-")"}"` reads as `'${x:-'`), past which the reader's quotes are no longer bash's."""
    i = 0
    while i < len(script):
        if script[i] == "\\":
            i += 2
        elif script[i] == "'":
            quoted, i = _single(script, i + 1)
            if _unended(quoted):
                return True
        elif script.startswith("${", i):
            i, operator = _brace(script, i + 2)
            if operator:
                return True
        else:
            i += 1
    return False


def _single(script: str, i: int) -> tuple[str, int]:
    """The text of the single-quoted word whose text starts at `i` (`'\\''` is a quote in it), and past its end."""
    parts = []
    while True:
        end = script.find("'", i)
        end = len(script) if end < 0 else end
        parts.append(script[i:end])
        if not script.startswith("'\\''", end):
            return "".join(parts), end + 1
        parts.append("'")
        i = end + 4


def _unended(text: str) -> bool:
    """Whether a `${` in `text` has no `}` to end it."""
    depth, i = 0, 0
    while i < len(text):
        if text.startswith("${", i):
            depth, i = depth + 1, i + 2
            continue
        if text[i] == "}" and depth:
            depth -= 1
        i += 1
    return depth > 0


def _brace(script: str, i: int) -> tuple[int, bool]:
    """From just inside a `${` in a scanned line: past its `}`, and whether an operator character stands in it
    outside the quoted words and other `${...}` it nests (True when no `}` ends it)."""
    operator = False
    while i < len(script):
        char = script[i]
        if char == "}":
            return i + 1, operator
        if char == "\\":
            i += 2
        elif char == "'":
            i = _single(script, i + 1)[1]
        elif script.startswith("${", i):
            i, inner = _brace(script, i + 2)
            operator |= inner
        else:
            operator |= char in ";&|()<>\n"
            i += 1
    return i, True


def _heredoc_in_word(command: str) -> bool:
    """Whether a `<<` the shell reader would open a here-document for stands where bash reads it as part of a word:
    inside a `${...}`, a `$[...]` or a subscript (`${x:-<<E}`, `$[1<<2]`, `a[1<<2]=x`), so that the reader would
    skip lines bash runs. Read outside quotes and the command substitutions the reader reads on their own."""
    closers: list[str] = []  # a `}` or `]` per open `${`, `$[` or subscript
    i, n, start = 0, len(command), True
    while i < n:
        char = command[i]
        if char == "\\":
            i, start = i + 2, False
        elif char == "'":
            end = command.find("'", i + 1)
            i, start = (n if end < 0 else end + 1), False
        elif char == '"':
            i += 1
            while i < n and command[i] != '"':
                i += 2 if command[i] == "\\" else 1
            i, start = i + 1, False
        elif char == "`":
            end = command.find("`", i + 1)
            i, start = (n if end < 0 else end + 1), False
        elif command.startswith("$(", i):  # a substitution the reader reads apart, with its own here-documents
            depth, i = 0, i + 1
            while i < n:
                depth += command[i] == "("
                depth -= command[i] == ")"
                i += 1
                if depth == 0:
                    break
            start = False
        elif command.startswith(("${", "$["), i):
            closers.append("}" if command[i + 1] == "{" else "]")
            i, start = i + 2, False
        elif start and (match := SUBSCRIPTED.match(command, i)):
            closers.append("]")
            i, start = match.end(), False
        elif command.startswith("<<<", i):
            i, start = i + 3, False
        elif command.startswith("<<", i):
            if closers:
                return True
            i, start = i + 2, False
        else:
            if closers and char == closers[-1]:
                closers.pop()
            start = char in " \t\n;&|()<>{}"
            i += 1
    return False


def _split_brace(command: str) -> bool:
    """Whether a double-quoted `${...}` nests a quote or a backquote the shell reader reads as the outer quote's end
    (`"${x:-"a"}"`, `"${x:-\}"it's"}"`, `"${x:-`cmd`}"`), so the reader splits the line where bash reads one word.
    An apostrophe bash reads literally there (`"${x:-'a'}"`, valid) does not, and an unpaired one bash rejects as a
    bad substitution (`"${x:-it's}"`) the reader reads as a word that bash never runs."""
    i, n, dquote, depth = 0, len(command), False, 0  # depth: open `${` inside the current double quote
    while i < n:
        char = command[i]
        if char == "\\":
            i += 2
        elif not dquote:
            if char == '"':
                dquote = True
            elif char == "'":
                end = command.find("'", i + 1)
                i = n if end < 0 else end
            i += 1
        elif command.startswith("${", i):
            depth, i = depth + 1, i + 2
        elif char == "'" and depth:  # bash reads `'...'` in a `${...}` as a span; skip it so its `}` is no end
            end = command.find("'", i + 1)
            i = n if end < 0 else end + 1
        elif char == "}" and depth:
            depth, i = depth - 1, i + 1
        elif char in '"`':
            if depth:
                return True  # a nested quote or backquote inside the `${...}`, which the reader reads as an end
            dquote, i = False, i + 1
        else:
            i += 1
    return False


def _backquoted(command: str) -> bool:
    """Whether the shell may run a backquoted command in this text: a backquote neither escaped, nor in single
    quotes, nor in a comment. The shell reader leaves such a command's text as the word it stands for, unseen in a
    push's words."""
    return _unquoted(command, "`", double=False)


def _globbed(command: str) -> bool:
    """Whether the shell may expand a glob in this text: a `*`, `?` or `[` in no quotes, not escaped and not in a
    comment."""
    return _unquoted(command, "*?[", double=True)


def _unquoted(command: str, chars: str, double: bool) -> bool:
    """Whether one of `chars` stands in this text where the shell reads it: not escaped, not in single quotes (nor
    in double quotes, when `double`), and not in a comment (read as _uncommented reads one, `$(cmd)#x` a word
    too)."""
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
        elif char in chars and (quote is None or not double):
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
        self.globbed = False  # whether a line it has read may expand a glob (_globbed)
        self.steps: list[_Step] = []
        self.commands: set[str] | None = None  # git's own command names, asked once
        self.loops: list[int] = []  # the loops the walk is in
        self.flows: list[_Flow] = []  # theirs, which a break or continue leaves (none of a caller's, as in bash)
        self.returns: list[list[tuple[_State, dict]]] = []  # per function call, where its returns leave the shell
        self.traps: list[list[str]] = []  # per shell read, the commands its traps run when it exits
        self.ids = 0
        self.path: tuple[tuple[_Pipeline, int], ...] = ()  # the pipelines around the command being read
        self.at: tuple[_Pipeline, int] = (_Pipeline(), 0)  # its own pipeline and place in it
        # the functions the call defines, by name: their bodies (None for one the hook cannot read), and
        # ("export", name) for each export -f exports, which a new shell runs too
        self.functions: dict = {}
        # whether a line it has read may quote a `~` (QUOTED_TILDE) or run bash in POSIX mode (POSIX_MODE)
        self.quoted_tilde = False
        # whether a line it has read may assign a variable it follows by an expansion (ASSIGNING, or an arithmetic
        # `$((...))` that names one), or quote one as a shell other than bash may not (DOLLAR_QUOTE), so that no
        # push from there on has a directory or variables the hook can name
        self.assigning = False
        # whether bash runs the line being read: another shell (sh may be dash, which has no pushd and expands
        # a `~` by its own rules) reads it as bash does only where the hook does not follow the words
        self.bash = True
        self.moves = 0  # the cd, pushd and popd read so far
        self.olds = 0  # the cd - read so far, the only reads of OLDPWD the hook follows
        # whether a function body the call defines names git or gh: only such a body (or a program, whose push the
        # hook does not read) may push, so a function the hook cannot read counts as a push only then
        self.pushers = False
        # whether the call may export a function in a way the hook does not follow (EXPORTING), so that a new shell
        # may have any of them
        self.exports = False

    def _id(self) -> int:
        self.ids += 1
        return self.ids

    def _tilde(self, word: str, home: str | None) -> str:
        """`word` with a leading `~` as bash expands it in a word of its own or an assignment's value: `~` from
        `home` (the HOME the call has set by then, else the hook's own), `~user` from that user's entry; `$`, a
        value the hook cannot read, when the call may quote a `~` or run bash in POSIX mode, or another shell runs
        the line."""
        if not word.startswith("~"):
            return word
        prefix, slash, rest = word.partition("/")
        if self.quoted_tilde or not self.bash:
            return "$"
        if prefix == "~":
            return (os.path.expanduser("~") if home is None else home) + slash + rest
        return os.path.expanduser(prefix) + slash + rest

    def _env_option(self, words: list[str], k: int, directory: str | None, started: str | None, env: dict,
                    state: _State) -> tuple[int, str | None]:
        """Read env's option at words[k] as GNU env's getopt does: -i, -u and -C in each form it takes (alone or in
        a group, the value attached or the next word; --ignore-environment, and --unset and --chdir with `=` or the
        next word), and -v, -0 and `--`. The last -C wins, from the directory env starts in (`started`). Any other
        option, an abbreviated one among them, leaves the directory one the hook cannot name. The index of the
        option's last word, and the directory its command runs in."""
        word, home = words[k], state.env.get("HOME")
        if word.startswith("--"):
            option, eq, value = word[2:].partition("=")
            if option in ("chdir", "unset") and not eq:
                if k + 1 == len(words):
                    return k, None
                k, value = k + 1, self._tilde(words[k + 1], home)  # a word of its own, which bash expands
            if option == "chdir":
                return k, _join(started, value, real=True)
            if option == "unset":
                _unset(env, value)
                if set(value) & set("$`"):
                    return k, None
            elif option == "ignore-environment" and not eq:
                _emptied(env)
            elif option not in ("", "debug", "null") or eq:
                return k, None
            return k, directory
        for at, letter in enumerate(word[1:], 2):
            if letter == "i":
                _emptied(env)
            elif letter in "uC":
                value = word[at:]
                if not value:
                    if k + 1 == len(words):
                        return k, None
                    k, value = k + 1, self._tilde(words[k + 1], home)
                if letter == "u":
                    _unset(env, value)
                    return k, None if set(value) & set("$`") else directory
                return k, _join(started, value, real=True)
            elif letter not in "v0":
                return k, None
        return k, directory

    def _deep(self, sub: bool) -> None:
        self._step("refuse", DEEP, sub=sub)

    def _step(self, kind: str, text: str, push: _Push | None = None, sub: bool = False, invocation: int = 0) -> None:
        text = text.replace(MARK, "").replace(FD, "").replace(LIFTED, "")  # a refusal shows a word as written
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
        self.quoted_tilde |= bool(QUOTED_TILDE.search(command) or POSIX_MODE.search(command))
        self.exports |= bool(EXPORTING.search(command))
        self.backquoted |= _backquoted(command)  # a shell's string or an eval's may hold one the call quotes
        self.globbed |= _globbed(command)
        if any(len(line) > LONGEST for line in command.split("\n")):
            raise _Unscannable(f"this call holds a line of more than {LONGEST:,} characters outside its "
                               f"here-documents, more than the hook reads within its {DEADLINE:.0f} seconds. "
                               "Split it into shorter calls")
        if _heredoc_in_word(command) or _split_brace(command):  # a `<<` or a nested quote the reader misreads
            self._step("refuse", BRACED, sub=sub)
            return
        extra: list[str] = []
        text = command if command.endswith("\n") else command + "\n"
        try:
            text = _uncommented(self.shell._scan(text, 0, "", extra, self.shell._Input())[0])
        except RecursionError:  # substitutions nested past Python's limit: read the line as written
            extra = []
        if _braced(text) or any(_braced(_uncommented(part)) for part in extra if not isinstance(part, _Arithmetic)):
            self._step("refuse", BRACED, sub=sub)  # what the walk would read past such a `${...}`, it cannot trust
            return
        self.assigning |= bool(ASSIGNING.search(command) or (not self.bash and DOLLAR_QUOTE.search(command))) or any(
            isinstance(part, _Arithmetic) and FOLLOWED.search(part) for part in extra)
        if shell:
            self.traps.append([])
        start, moves, functions = state.copy(), self.moves, dict(self.functions)
        self._walk(self.shell._command_tokens(text), state, depth, sub)
        # A substitution runs in the directory and with the variables and functions its command has, which the line
        # may change before it and change back after (an eval's or a function's move among them): then each
        # variable the line has or names is one the hook cannot read, and stays so after a move to a literal path.
        changed = self.moves != moves or state.followed() != start.followed() or bool(FOLLOWED.search(text)) \
            or self.functions != functions
        unknown = dict.fromkeys({*start.env, *state.env, *FOLLOWED.findall(text)}, "$")
        # a function the line defines, changes or removes may be either in a substitution, so it reads neither
        table, self.functions = self.functions, {name: body if functions.get(name) == body else None
                                                 for name, body in {**functions, **self.functions}.items()}
        for name in set(functions) - set(table):
            self.functions[name] = None
        parts = [part for part in extra if not isinstance(part, _Arithmetic)]
        first, moved, within = len(self.steps), False, self.functions
        for part in parts:
            if isinstance(part, _Cut):
                self._step("refuse", CUT, sub=True)
                continue
            inner = _State(None, None, None, dict(unknown)) if changed else start.copy()
            begun, moves, self.functions = inner.copy(), self.moves, dict(within)  # each in a subshell of its own
            self.traps.append([])
            self._walk(self.shell._command_tokens(_uncommented(part)), inner, depth, True)
            self._exit(inner, depth)
            moved |= self.moves != moves or inner.followed() != begun.followed() or self.functions != within
        # One inside another (read apart, before it) runs from where the commands before it there left the shell.
        if moved and (any("$()" in part for part in parts) or (self.backquoted and len(parts) > 1)):
            self.steps[first:] = [step._replace(push=step.push._replace(where=None)) if step.push is not None
                                  else step for step in self.steps[first:]]
        self.functions = table
        if shell:
            self._exit(state, depth)

    def _new_shell(self, script: str, state: _State, depth: int, sub: bool, bash: bool) -> None:
        """Read the string a new shell runs, bash or another: with the functions its shell exports, which only
        bash is sure to import, and none of the loops or function calls the command stands in."""
        # one the call may or may not export (by export -f, or as EXPORTING does), it may or may not get
        exported = {key: body if bash and self.functions.get(("export", key)) else None
                    for key, body in self.functions.items()
                    if not isinstance(key, tuple) and (("export", key) in self.functions or self.exports)}
        functions, self.functions = self.functions, {
            **exported, **{key: value for key, value in self.functions.items() if isinstance(key, tuple)}}
        kept = self.flows, self.returns, self.bash
        self.flows, self.returns, self.bash = [], [], bash
        self.read(script, state, depth + 1, sub)
        self.functions, (self.flows, self.returns, self.bash) = functions, kept

    def _unknown(self, text: str, state: _State, sub: bool) -> None:
        """A function the hook cannot read runs: it may move the shell, set a variable it follows and make commits,
        and push, from a directory the hook cannot name, when a body the call defines names git or gh."""
        invocation = self._id()
        if self.pushers:
            self._step("push", text, _Push(None, [], {}, text, True), sub, invocation)
        self._step("write", text, sub=sub, invocation=invocation)
        state.dir = None
        state.obscure()

    def _turned(self, defined: dict, tables: list[dict], state: _State, depth: int, sub: bool) -> None:
        """What a loop's later turn runs that the hook, reading the first, did not: each function a turn defined,
        changed, removed or exported, called as that turn left the functions, from a directory the hook cannot
        name and with every variable it follows unknown."""
        functions = self.functions
        for table in tables:
            for name in sorted({key[1] if isinstance(key, tuple) else key for key in {*table, *defined}
                                if table.get(key) != defined.get(key)}):
                later = state.copy()
                later.dir = None
                later.obscure()
                self.functions = dict(table)
                self._command([name], later, depth, sub)
        self.functions = functions

    def _exit(self, state: _State, depth: int) -> None:
        """Read the traps of a shell or subshell as it exits, in the state it leaves."""
        for script in self.traps.pop():
            self.read(script, state.copy(), depth + 1, True)

    def _join(self, state: _State, ways: list[tuple[_State, dict]]) -> None:
        """The shell goes on by one of `ways`, each a state and the functions defined there: keep what they agree
        on, and make the rest one the hook cannot read."""
        state.__dict__.update(ways[0][0].copy().__dict__)
        for other, _ in ways[1:]:
            state.blend(other)
        self.functions = _merged([functions for _, functions in ways])

    def _jump(self, words: list[str], state: _State) -> None:
        """A break or a continue: the loops it leaves may end here, and a continue's own loop start a turn from here
        (any of them, when its count is not a number)."""
        here = (state.copy(), dict(self.functions))
        known = not words[1:] or (words[1].isascii() and words[1].isdigit())
        count = int(words[1].lstrip("0")[:9] or 0) if words[1:] and known else 1  # one past the loops leaves all
        loops = self.flows[-max(count, 1):] if known else self.flows
        for flow in loops:
            flow.ways.append(here)
        if words[0] == "continue":
            for flow in loops[:1] if known else loops:
                flow.turns.append(here)

    def _walk(self, tokens: list[str], state: _State, depth: int, sub: bool) -> bool:
        """Read a line's commands, inside the command that reads it; whether a cd, pushd or popd moved its
        directory. A compound command is a command of the pipeline it stands in, holding pipelines of its own;
        one that runs in a subshell (a `(...)`, or one in a pipeline or the background) keeps its cd, and a
        subshell, a pipeline's command, a background job and a process substitution run their own traps."""
        saved = (self.path, self.at)
        self.path = (*self.path, self.at)
        # The compound commands open: opener, state at the open, place, path, piped, the functions defined then,
        # and its ways out
        frames: list[tuple] = []
        # the and-or list being read at each depth: the line's, then each compound's
        lists = [_List(state.copy(), self.functions)]
        words: list[str] = []
        previous, moved, pipe, member = None, False, None, 0

        def place() -> None:  # a command after `|` joins the pipeline before it; any other starts one
            nonlocal pipe, member
            pipe, member = (pipe, member + 1) if previous in ("|", "|&") and pipe else (_Pipeline(), 0)
            self.at = (pipe, member)

        def close(state_: _State, token: str) -> None:  # end the innermost compound command
            nonlocal pipe, member
            opener, start, (pipe, member), self.path, piped, functions, flow = frames.pop()
            ended = lists.pop()
            if ended.operator is not None:  # a list its closing word ends
                ended.ended(state_, self.functions)
                self._join(state_, [ended.succeeded, ended.failed])
            self.at = (pipe, member)
            here = (state_.copy(), dict(self.functions))
            if opener in ("if", "case"):
                # It leaves the shell as one of its branches does, or as its conditions left it (an if with no
                # `else`), or as it found it (a case none of whose patterns matched).
                self._join(state_, [*flow.ways, here, *([] if flow.otherwise else [(flow.cond, flow.functions)])])
            elif opener in LOOPS and self.loops:
                loop = self.loops.pop()
                self.flows.pop()
                turns = [here, *flow.turns]
                # A while's or an until's turn starts where the loop began, with its condition; a for's or a
                # select's, after its header.
                first, defined = (start, functions) if opener in ("while", "until") else (flow.cond, flow.functions)
                # A turn that leaves the shell as it found it, but for an OLDPWD no cd - in the loop reads, makes the
                # next turn run as this one did.
                olds = self.olds != flow.olds
                fixed = all(way.same(first, old=olds) and table == defined for way, table in turns)
                # A later turn may call a function an earlier one defined, changed or removed, which the hook read
                # as the first turn found it: read each as such a turn runs it.
                self._turned(defined, [table for _, table in turns], state_, depth, sub)
                if not fixed:
                    # A later turn runs the body from where this one ended: its pushes run from a directory the
                    # hook cannot name.
                    self.steps[:] = [step._replace(push=step.push._replace(where=None))
                                     if step.push is not None and loop in step.loops else step for step in self.steps]
                if opener in ("while", "until"):  # it ends when its condition fails, or at a break
                    self._join(state_, [(flow.cond, flow.functions), *flow.ways,
                                        *([] if fixed else [(start, functions), *turns])])
                else:  # a for or a select may run no turn, and ends after any, or at a break
                    self._join(state_, [(flow.cond, flow.functions), *turns, *flow.ways])
                if not fixed:  # a later turn, run from elsewhere, may move the shell where the first did not
                    state_.dir, state_.old, state_.dirs = None, None, [None] * len(state_.dirs)
                elif any(way.old != first.old for way, _ in turns):
                    state_.old = None  # where a later turn leaves OLDPWD
            if opener == "(":
                self._exit(state_, depth)
            if opener == "(" or piped or token in ("|", "|&", "&"):  # it ran in a subshell, its functions too
                state_.__dict__.update(start.__dict__)
                self.functions = functions

        def open_(opener: str) -> None:
            nonlocal pipe, member, previous
            piped = previous in ("|", "|&")
            place()
            frames.append((opener, state.copy(), (pipe, member), self.path, piped, dict(self.functions),
                           _Flow(state, self.functions)))
            lists.append(_List(state.copy(), self.functions))
            self.path = (*self.path, (pipe, member))
            pipe, member, previous = None, 0, None
            if opener in LOOPS:  # a while's or until's condition runs on each turn, so it is inside the loop
                self.loops.append(self._id())
                self.flows.append(frames[-1][6])
                frames[-1][6].olds = self.olds
            if opener == "(":
                self.traps.append([])

        def define(name: str, begin: int, end: int) -> int:
            """A function's definition: its body from `begin` to `end`, with the redirections after it, which bash
            sets up at each call, from where it is called (one a pipeline or `&` runs is its subshell's). Where the
            walk goes on: past them (`f() { ...; } >log | cat`)."""
            after = _redirected(tokens, end)
            body = tokens[begin:after]
            self.pushers |= any(NAMES_GIT.search(word.lower()) for word in body)
            if previous not in ("|", "|&") and tokens[after:after + 1] not in (["|"], ["|&"], ["&"]):
                self.functions[name] = body
            return after

        def keywords(token: str) -> None:  # the reserved words a command begins with: they open, part or close
            nonlocal words
            while words and (words[0] in OPENERS + CLOSERS + PARTS or (words[0] == "time" and self.bash)):
                word = words.pop(0)
                if word == "time":  # bash's reserved word: it times the pipeline after it, which runs as it would
                    words = words[1:] if words[:1] == ["-p"] else words
                    words = words[1:] if words[:1] == ["--"] else words
                elif word in OPENERS:
                    open_(word)
                    if word in HEADERS:  # `for i in ...`, `case x in`
                        if word != "case" and words and FOLLOWED.fullmatch(words[0]):
                            state.set(words[0], "$")  # the loop's variable takes each word in turn
                        # `for i do ...`, with no list, runs its body from the `do`
                        words = words[1:] if word != "case" and words[1:2] == ["do"] else []
                elif word in CLOSERS and frames and frames[-1][0] != "(":
                    close(state, token)
                elif word in ("then", "do") and frames and frames[-1][0] in (("if",) if word == "then" else LOOPS):
                    frames[-1][6].after(state, self.functions)  # its branch, or a turn's body, runs from here
                elif word in ("elif", "else") and frames and frames[-1][0] == "if":
                    # The branch before ends, and this one's condition, or its body, runs after the conditions
                    # before failed: from where the last of them left the shell.
                    flow = frames[-1][6]
                    flow.ways.append((state.copy(), dict(self.functions)))
                    self._join(state, [(flow.cond, flow.functions)])
                    flow.otherwise = word == "else"
                    lists[-1] = _List(state.copy(), self.functions)  # its first list starts here too

        tokens = [*tokens, ";"]
        kinds = list(_kinds(tokens))
        i, written = 0, []  # the files the command being read opens to write, as `> file`
        # whether the next process substitution is a redirection's target; whether a redirection of the command
        # being read may fail
        targeted = failing = False
        while i < len(tokens):
            token, kind = tokens[i], kinds[i]
            i += 1
            if token == LIFTED:  # the process substitution after it, lifted from an array's words, is no word
                targeted = True
                continue
            if kind == IN:  # a case's `in` ends its header, and the case opens
                if words:
                    words.append(token)
                    keywords(token)
                continue
            if kind == PATTERN:  # a case's pattern runs nothing; its `)` starts the arm (`(a|b)`, `if)`, `(esac)`)
                if token == ")" and frames and frames[-1][0] == "case":
                    # The arm before ends here, and this one runs from where the case began, from where an arm
                    # `;;&` ended (bash then tests every pattern after it), or from where the arm before ended, if
                    # `;&` ended it.
                    flow = frames[-1][6]
                    here = (state.copy(), dict(self.functions))
                    flow.ways.append(here)
                    flow.tested += [here] if flow.through == ";;&" else []
                    self._join(state, [(frames[-1][1], frames[-1][5]), *flow.tested,
                                       *([here] if flow.through == ";&" else [])])
                    flow.through, previous = None, ")"
                    lists[-1] = _List(state.copy(), self.functions)
                continue
            terminator = token if token in TERMINATORS else None  # a case's arm ends, and its list with it
            token = ";" if terminator else token
            if token in REDIRECTS:
                # One after a compound command's closing words is the compound's that the last of them closes:
                # bash sets it up before the body runs, from where that compound began (`{ cd x; } > >(cmd)`,
                # `{ cd x; { :; } } < missing`).
                closed = _closed(words, frames)
                compound = closed > 0
                began = (frames[-closed][1], frames[-closed][5]) if compound else None  # its state and functions
                if token in ("<", ">") and tokens[i:i + 1] == ["("]:  # a process substitution runs beside its command
                    end = _closing(tokens, i)
                    if end is None:
                        self._step("refuse", UNENDED, sub=sub)
                        break
                    if depth >= MAX_DEPTH:
                        self._deep(True)
                    else:  # in a subshell, with its functions
                        begun, table = began if began else (state, self.functions)
                        inner, kept = begun.copy(), self.functions
                        self.functions = dict(table)
                        self.traps.append([])
                        self._walk(tokens[i + 1:end], inner, depth + 1, True)
                        self._exit(inner, depth + 1)
                        self.functions = kept
                    if not targeted:  # one of its command's words, by the name bash gives it
                        words.append(SUBSTITUTED)
                    i, targeted = end + 1, False
                    continue
                # the descriptor of 2>file or 1>&2
                descriptor = words.pop()[len(FD):] if words and words[-1].startswith(FD) else ""
                if token in ("<", "&>") and tokens[i:i + 1] == [">"] and tokens[i + 1:i + 2] != ["("]:
                    token, i = token + ">", i + 1  # `<>` and `&>>`, which the tokens split (`&> >(cmd)` is `&>`)
                target = tokens[i] if i < len(tokens) else ""
                # whether the target is a process substitution (`> >(cmd)`), which the next token starts
                targeted = target in ("<", ">") and tokens[i + 1:i + 2] == ["("]
                if _may_fail(token, descriptor, None if targeted else target):
                    if compound:  # the compound may not have run: the shell may stand where it began
                        self._join(state, [(state.copy(), dict(self.functions)), began])
                    else:  # bash then runs no command it belongs to
                        failing = True
                if targeted:
                    continue
                if token in WRITES and target not in DEVICES and not target.startswith("/dev/fd/") \
                        and not (token == ">&" and (target.isdigit() or target == "-")):
                    written.append(f"{token} {target}")
                i += 1  # the redirection's target, or a here-string's text
                continue
            if token in self.shell.OPERATORS or token in ("(", ")"):
                if token == "(" and tokens[i:i + 1] == [")"] and words \
                        and set(words[:-1]) <= set(OPENERS + PARTS) - set(HEADERS):
                    # `name ()`: a function's definition, whose body runs where the function is called; the
                    # reserved words before it (`{ f() ...`, `then f() ...`) open or part the compound it is in
                    name, words = words[-1], words[:-1]
                    keywords(token)
                    end = _compound_end(tokens, i + 1)
                    if end is None:
                        self._step("refuse", UNENDED, sub=sub)
                        break
                    i = define(name, i + 1, end)
                    words, failing = [], False
                    continue
                # A redirection with no command of its own after a `)` or a closing word is the compound's.
                bare = not words and previous != ")"
                keywords(token)
                ran = None
                if words:
                    place()
                    # A pipeline's commands and a background job run in subshells: their cd stays there.
                    piped = previous in ("|", "|&") or token in ("|", "|&", "&")
                    start, table = len(self.steps), dict(self.functions)
                    before = (state.copy(), dict(self.functions)) if failing and not piped else None
                    moved |= self._command(words, state.copy() if piped else state, depth, sub)
                    if piped:  # and the functions it defines or removes
                        self.functions = table
                    elif before:  # a redirection that may fail runs no command: the shell may go on as it was
                        self._join(state, [(state.copy(), dict(self.functions)), before])
                    ran = self.steps[start:]
                elif written and bare:
                    place()
                if written:
                    # A file the command writes may be a ref, a config or a script; a push's own output is not.
                    if not ran or any(step.kind != "push" for step in ran):
                        self._step("write", " ".join([*words, *written]), sub=sub)
                    written = []
                words, failing = [], False
                if token == "&" and pipe:
                    pipe.background = True
                listed = lists[-1]
                if token in ("&&", "||"):  # the pipeline after it runs where the list succeeded, or failed
                    listed.ended(state, self.functions)
                    listed.operator = token
                    self._join(state, [listed.succeeded if token == "&&" else listed.failed])
                elif token in (";", "&", ")"):  # the list ends, in one of the states its pipelines left
                    if token == "&":
                        state.__dict__.update(listed.start.__dict__)  # it ran in the background
                        self.functions = dict(listed.functions)
                    elif listed.operator is not None:
                        listed.ended(state, self.functions)
                        self._join(state, [listed.succeeded, listed.failed])
                    lists[-1] = _List(state.copy(), self.functions)
                if terminator and frames and frames[-1][0] == "case":
                    # once the words before it are read: a closing word there (`};;`, `fi;&`, `esac;;`) ends its
                    # compound first
                    frames[-1][6].through = terminator
                if token == "(":
                    open_("(")
                elif token == ")" and frames and frames[-1][0] == "(":
                    close(state, tokens[i] if i < len(tokens) else ";")
                previous = token if token != "(" else previous
                continue
            if token == "function" and set(words) <= set(OPENERS + PARTS) - set(HEADERS) and i < len(tokens):
                keywords(token)  # `function name [()] body`, a definition, after any reserved words
                name, j = tokens[i], i + 1
                j += 2 if tokens[j:j + 2] == ["(", ")"] else 0
                end = _compound_end(tokens, j)
                if end is None:
                    self._step("refuse", UNENDED, sub=sub)
                    break
                i = define(name, j, end)
                continue
            words.append(token)
        while frames:  # a compound command left open ends with the line
            close(state, ";")
        self.path, self.at = saved
        return moved

    def _command(self, words: list[str], state: _State, depth: int, sub: bool) -> bool:
        """Read one command into steps; whether it moved the directory."""
        if time.monotonic() > self.deadline:  # functions that call each other, each more than once
            raise _Unscannable(f"reading this call took the hook past its {DEADLINE:.0f} seconds (functions that "
                               "call each other, many times over), so it cannot tell what the call pushes. Write "
                               "it more plainly")
        text = " ".join(words)
        env = dict(state.env)
        assigned = []  # the command's own assignments, which what it runs gets whatever the shell exports
        while words and (match := ASSIGNS.match(words[0])):
            # bash expands it with the HOME set so far; an addition or an element's assignment (`NAME+=value`,
            # `NAME[1]=value`) leaves a value the hook does not join
            name, value = match[1], words[0][match.end():]
            env[name] = "$" if match[2] or match[3] else self._tilde(value, env.get("HOME"))
            assigned.append(name)
            words = words[1:]
        if not words:
            # Assignments alone set shell variables, which reach git only if exported, and the hook cannot see
            # whether they are: a GIT_* variable set this way is one whose value the hook does not know. cd reads
            # HOME, CDPATH and OLDPWD exported or not.
            for name in assigned:
                state.set(name, env[name] if name in (*CD_VARIABLES, "OLDPWD") else "$")
            return False
        if words[0] in ("break", "continue") and self.flows:
            self._jump(words, state)
        elif words[0] == "return" and self.returns:
            self.returns[-1].append((state.copy(), dict(self.functions)))  # the function's call ends here
        elif words[0] == "exit" and self.traps:
            for script in self.traps[-1]:  # its shell's traps run as it exits, from here
                self.read(script, state.copy(), depth + 1, True)
        if words[0] in self.functions:  # a function the call defines runs its body here, in this shell
            if depth >= MAX_DEPTH:
                self._deep(sub)
                return False
            if self.functions[words[0]] is None:  # one the call may define otherwise, or not at all
                self._unknown(text, state, sub)
                return True
            before = {name: state.env.get(name) for name in assigned if name != "OLDPWD"}
            state.env.update((name, env[name]) for name in before)  # its assignments last while it runs,
            shown = state.hidden & set(before)  # exported to what it runs
            state.hidden -= shown
            if "OLDPWD" in assigned:
                state.set("OLDPWD", env["OLDPWD"])  # cd - goes there until the body moves the shell
            self.returns.append([])
            flows, self.flows = self.flows, []  # a break in its body leaves no loop of the caller's
            moved = self._walk(self.functions[words[0]], state, depth + 1, sub)
            self.flows = flows
            returned = self.returns.pop()
            if returned:  # it ends at its body's end, or at a return
                self._join(state, [(state.copy(), dict(self.functions)), *returned])
            if "OLDPWD" in assigned:
                state.old = None  # what bash puts back after the call, the hook does not follow
            for name, value in before.items():
                if value is None:
                    state.env.pop(name, None)  # the body may have unset it
                else:
                    state.env[name] = value
            state.hidden |= shown
            return moved
        name, start, directory = words[0].rsplit("/", 1)[-1].lower(), 0, state.dir
        if name in WRAPPERS:  # the command a wrapper runs: its first git, gh, curl, shell or eval word
            # sudo runs its command where its options or its policy say (-D, -i, runcwd), with the variables its
            # policy keeps, none of which the hook reads.
            wrapper, k, started = name, 1, directory
            if wrapper == "sudo":
                directory = None
                _policed(env)
            while k < len(words):
                word, base = words[k], words[k].rsplit("/", 1)[-1].lower()
                # bash expands it as it would an assignment, with the shell's HOME; env takes any word with `=`
                if ASSIGNMENT.match(word) or (wrapper == "env" and "=" in word and not word.startswith("-")):
                    key, _, value = word.partition("=")
                    env[key] = self._tilde(value, state.env.get("HOME"))
                    assigned.append(key)
                elif wrapper == "env" and word == "-":
                    _emptied(env)
                elif wrapper == "env" and word.startswith("-"):
                    k, directory = self._env_option(words, k, directory, started, env, state)
                elif wrapper == "exec" and word.startswith("-") and word != "--":
                    flags, named, argv0 = word[1:].partition("a")  # -a takes a name: the group's rest or the next word
                    k += bool(named) and not argv0
                    if "c" in flags:
                        _emptied(env)  # exec -c runs its command with an empty environment
                elif base in ("git", "gh", "curl", "eval", *SHELLS):
                    name, start = base, k
                    break
                elif wrapper == "time" == words[0] and word in self.functions and not (self.bash or assigned):
                    # time is a reserved word in zsh and ksh, which run the function, and a program in dash, which
                    # runs the program by that name
                    self._unknown(text, state, sub)
                    return True
                elif base in WRAPPERS:  # a wrapper the first one runs, whose options follow
                    wrapper, started = base, directory
                    if wrapper == "sudo":
                        directory = None
                        _policed(env)
                elif word in WRAPPER_VALUES.get(wrapper, ()):
                    k += 1  # the option's value
                elif base in INERT:  # a program that runs no other (`xargs grep -l git`), read as itself
                    name, start = base, k
                    break
                elif not word.startswith("-") and not NUMBER.fullmatch(word):
                    directory = None  # a program the wrapper runs, which may run what it holds anywhere
                k += 1
        if directory is not None and not os.path.isdir(directory):
            directory = None
        inner = state if directory == state.dir else state.copy()
        inner.dir = directory
        # What a program the command runs gets: a variable the shell holds unexported, it does not, and one of cd's
        # is then one the hook cannot read, since its own reads would take the session's.
        passed = dict(env)
        for key in state.hidden - set(assigned):
            if key in CD_VARIABLES:
                passed[key] = "$"
            else:
                _unset(passed, key)
        args = words[start + 1:]
        if name == "git":  # xargs adds the words it reads to the command it runs
            xargs = "xargs" in [word.rsplit("/", 1)[-1] for word in words[:start]]
            self._git(args, inner, passed, depth, sub, text, appended=xargs)
            return False
        if name in ("cd", "pushd", "popd") and words[0] == name:  # a builtin by its exact name; `CD` is another
            self._move(name, args, state, env)
            return True
        if name == "eval":  # its words run in this shell, with its assignments, and may set its traps
            kept, shown = {key: state.env.get(key) for key in assigned}, state.hidden & set(assigned)
            state.env.update((key, env[key]) for key in assigned)
            state.hidden -= shown  # what its words run gets them
            self.read(" ".join(args), state, depth + 1, sub, shell=False)
            state.hidden |= shown
            for key, value in kept.items():
                if value is None:
                    state.env.pop(key, None)
                else:
                    state.env[key] = value
        elif name == "trap":
            args = args[1:] if args[:1] == ["--"] else args
            if args and not args[0].startswith("-"):
                self.traps[-1].append(args[0])
                if {signal.upper() for signal in args[1:]} & {"DEBUG", "ERR", "RETURN"}:
                    # it runs between the commands after it: where it moves the shell, or what it sets, the hook
                    # cannot place
                    state.dir = None
                    state.obscure()
            self._step("read", text, sub=sub)
        elif name in SHELLS:
            script = _shell_string(args)
            if script is None:  # a script file or standard input: what it runs is not read
                self._step("write", text, sub=sub)
            else:  # a new shell, with the variables its command has, no directory stack and the exported functions
                # A PWD the call passes may give it its directory by another path, and an OLDPWD it takes only from
                # its command (the shell's may be unexported, or name no directory, which bash then drops).
                shell = _State(None if "PWD" in env else inner.dir, None, None,
                               {key: value for key, value in passed.items() if key != "OLDPWD"})
                if "OLDPWD" in env:
                    shell.set("OLDPWD", env["OLDPWD"])  # its cd - goes there until a cd moves it
                if set(STARTUP) & set(env) or any(key.startswith("BASH_FUNC_") for key in env):
                    self._step("write", text, sub=sub)  # it first runs a file or a function the hook does not read
                self._new_shell(script, shell, depth, sub, bash=name == "bash")
        elif name == "gh":
            write = _gh_api_write(args, text, directory)
            kind = "refuse" if write else "read" if args[:1] == ["api"] else "write"
            self._step(kind, write or text, sub=sub)
        elif name == "curl":  # curl can write any file (-o, -O, -D, -c and more), a ref among them
            write = _curl_write(args, text, directory)
            self._step("refuse" if write else "write", write or text, sub=sub)
        elif name in ("export", "unset") and words[0] == name:
            options = "".join(word[1:] for word in args if word.startswith("-"))
            # bash expands each word before the builtin runs, so a `~` takes the HOME set before the command
            unexport, home = name == "unset" or "n" in options, state.env.get("HOME")
            for word in args:
                key, eq, value = word.partition("=")
                if word.startswith("-"):
                    continue
                appended = bool(eq) and key.endswith("+")  # `NAME+=value` adds to what the shell holds
                key = key[:-1] if appended else key
                if name == "unset":
                    key = key.split("[", 1)[0]  # unset of a scalar's element, `X[0]`, unsets it whole
                if set(key) & set("$`"):
                    state.obscure()  # a name the hook cannot read may be any variable it follows
                elif "f" in options:  # export -f exports a function, unset -f removes one: no variable changes
                    if name == "export" and "n" not in options:
                        self.functions[("export", key)] = True
                    else:  # export -fn stops exporting it
                        self.functions.pop(("export", key), None)
                        if name == "unset":
                            self.functions.pop(key, None)
                elif name == "unset" and key in ("HOME", "OLDPWD", "PWD"):
                    state.set(key, "$")  # cd alone, or cd -, then fails, which the hook does not follow
                    state.hidden |= {key} & set(CD_VARIABLES)  # one assigned later is the shell's alone
                elif unexport:
                    if name == "unset" and "v" not in options and key in self.functions:
                        # bash unsets a variable by the name if one is set, else the function, and the hook does not
                        # see every variable a call sets (read's, a loop's, bash's own); dash keeps the function
                        self.functions[key] = None
                    if name == "unset":
                        _unset(state.env, key)
                        state.hidden.discard(key)
                    elif eq:  # `export -n NAME=value` sets it too
                        state.set(key, "$" if appended else self._tilde(value, home))
                    # export -n leaves the shell its own variable, which no program the command runs gets
                    state.hidden |= {key} if name == "export" else {key} & set(CD_VARIABLES)
                else:
                    state.hidden.discard(key)  # exported again
                    if eq:  # an addition joins a value the hook does not join
                        state.set(key, "$" if appended else self._tilde(value, home))
            self._step("read", text, sub=sub)
        elif name in NAMING:  # the variables read, printf -v and wait -p assign take values the hook does not read
            for key in _named(name, args):
                if set(key) & set("$`"):
                    state.obscure()
                elif FOLLOWED.fullmatch(key):
                    state.set(key, "$")
            self._step("read", text, sub=sub)
        else:
            # A push another command holds, wherever its git word stands, is read as that push, with the words that
            # command may add: from the shell's directory when the command runs nothing (`echo git push`), and from
            # one the hook cannot name when it may run it anywhere (find's -execdir, in each directory it finds).
            held = len(self.steps)
            holder = inner.copy()
            holder.dir = holder.dir if name in INERT else None
            for k, word in enumerate(args):
                if word.rsplit("/", 1)[-1].lower() == "git":
                    self._git(args[k + 1:], holder, passed, depth, sub, text, only_pushes=True, appended=True)
                    break
            if len(self.steps) == held:
                self._step("read" if name in INERT or (name == "exec" and not args) else "write", text, sub=sub)
        if words[0] in SPECIAL:  # bash in POSIX mode, and sh, keep its assignments: each may hold either value
            for key in assigned:
                if FOLLOWED.fullmatch(key):
                    state.set(key, "$")
        return False

    def _move(self, name: str, args: list[str], state: _State, env: dict) -> None:
        """Follow a cd, pushd or popd as bash does, with the HOME, CDPATH and OLDPWD the call gives it; the
        directory, or an entry of the stack, becomes None when the hook cannot name it. The stack is the one
        `dirs -v` lists: entry 0 the shell's directory, then state.dirs from its end."""
        self.moves += 1
        self._moved(name, args, state, env)
        if "PWD" in env:  # bash keeps $PWD as OLDPWD, which the call sets, and then sets PWD where it lands
            state.old = None
            state.env.pop("PWD", None)

    def _moved(self, name: str, args: list[str], state: _State, env: dict) -> None:
        if name != "cd" and not self.bash:  # dash has neither, and zsh's read their options otherwise
            state.dir = None
            return
        keep = name != "cd" and "-n" in args  # pushd -n and popd -n change the stack, not the directory
        option = ""  # cd's -L or -P, the last one written; pushd takes neither
        if name == "cd":
            k, letters = 0, ""  # its options end at `--` or at the first word that is not one, as getopt reads them
            while k < len(args) and args[k].startswith("-") and args[k] != "-":
                k += 1
                if args[k - 1] == "--":
                    break
                letters += args[k - 1][1:]
            words = args[k:]
            # an option the shell's cd refuses (dash's takes -L and -P alone): it fails, which the hook does not follow
            if set(letters) - set("LPe" if self.bash else "LP"):
                state.dir = None
                return
            option = letters.replace("e", "")[-1:]
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
        word = self._tilde(words[0], state.env.get("HOME")) if words else ""  # with the shell's own HOME
        if not words:  # cd alone: the HOME it reads, a prefix assignment's among them
            home = env.get("HOME")
            target = _landing(state.dir, os.path.expanduser("~") if home is None else home, option)
        elif word == "-":
            self.olds += 1
            target = _landing(state.dir, env["OLDPWD"] if "OLDPWD" in env else state.old, option)
        elif env.get("CDPATH") and not word.startswith(("/", "./", "../")) and word not in (".", ".."):
            target = None  # bash looks the name up along CDPATH before the shell's directory
        else:
            target = _landing(state.dir, word, option)
        if target is not None and not os.path.isdir(target):
            target = None  # the cd fails or enters a directory the call makes first
        if keep:  # pushd -n puts the directory under the shell's own, and popd later enters it from there
            state.dirs.append(target if word.startswith("/") else None)  # popd resolves a `-` or a relative one
            return
        if name == "pushd":
            state.dirs.append(state.dir)
        state.old, state.dir = state.dir, target

    def _git(self, words: list[str], state: _State, env: dict, depth: int, sub: bool, text: str,
             only_pushes: bool = False, overrides: dict | None = None, aliases: int = 0,
             appended: bool = False) -> None:
        """Read a git command line (the words after `git`) into steps."""
        directory = state.dir
        # git takes a relative GIT_DIR or --git-dir from the directory its -C options leave, wherever they stand.
        named = env.get("GIT_DIR") or None
        # A ref store, object store or namespace the call moves is one the hook does not follow, and settings the
        # call gives git through the environment may change what a push sends.
        unknown = directory is None or bool(RELOCATING & set(env)) or "$" in (env.get(name) for name in LOCATING) \
            or self.assigning
        opaque = any(key.startswith("GIT_CONFIG") or key in CONFIG_HOMES for key in env)
        overrides = dict(overrides or {})
        i = 0
        while i < len(words):
            word = words[i]
            if word in GIT_VALUE_OPTIONS and i + 1 < len(words):
                value = words[i + 1]
                if word == "-C":
                    directory = _join(directory, self._tilde(value, state.env.get("HOME")), real=True)
                    unknown |= directory is None or not os.path.isdir(directory)
                elif word == "-c":
                    key, eq, setting = value.partition("=")
                    overrides[key.lower()] = setting if eq else "true"  # `-c name` alone sets a boolean
                elif word == "--git-dir":
                    named = self._tilde(value, state.env.get("HOME"))
                unknown |= word == "--namespace"
                opaque |= word == "--config-env"
                i += 2
                continue
            if word.startswith("--git-dir="):
                named = word[len("--git-dir="):]
            elif not word.startswith("-"):
                break
            unknown |= word.startswith("--namespace=")
            opaque |= word.startswith("--config-env=")
            i += 1
        git_dir = _join(directory, named, real=True) if named else None
        unknown |= bool(named) and git_dir is None
        if i >= len(words):  # `git` alone, `git --version`; or one xargs gives its command and words, which may push
            if appended and not only_pushes:  # (a git another command holds alone, as `which git`, runs nothing)
                where = None if unknown or directory is None else _Where(directory, git_dir)
                invocation = self._id()
                self._step("push", text, _Push(where, [], overrides, text, True), sub, invocation)
                self._step("write", text, sub=sub, invocation=invocation)
            elif not only_pushes:
                self._step("read", text, sub=sub)
            return
        command, args = words[i], words[i + 1:]
        # A word up to the command that bash may expand to others, or any there in a call with backquotes, may be
        # an option the loop above did not see (`o=-C; git $o <dir> push`, `git {-C,<dir>} push`).
        unknown |= any(EXPANDS.search(word) or (self.globbed and GLOB.search(word)) for word in words[:i + 1]) or (
            self.backquoted and (i > 0 or not self._own(command, None)))
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
                    # git runs it with sh, which may be dash
                    self._new_shell(script, _State(top or (where.dir if where else None), env=inherited), depth, sub,
                                    bash=False)
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
    # With no rules on main, none is named and gitleaks reads its built-in ones, as CI's scan does: rules that only
    # extend them (`[extend] useDefault = true`) drop their global allowlist's stopwords, and refuse what CI passes.
    rules = _blob(where, tip, ".gitleaks.toml", deadline, env) if where else None
    if rules is not None:
        (tmp / "main.gitleaks.toml").write_bytes(rules)
        command += ["--config", str(tmp / "main.gitleaks.toml")]
    _its_own_repository(git_dir, env, deadline)  # gitleaks' own git log runs in the git directory
    # gitleaks reads a .gitleaksignore in the directory it scans, and a .gitleaks.toml there when no --config names
    # one, so a git directory that holds either, as any kind of file and whatever main holds, is refused.
    for name, read in ((".gitleaksignore", "beside main's pins"),
                       (".gitleaks.toml", "in place of its built-in rules when main has none")):
        planted = os.path.join(git_dir, name)
        if os.path.lexists(planted):
            raise _Unscannable(f"this repository's git directory holds a {name} ({planted}), a name gitleaks reads "
                               f"there {read}, so it could hide a finding. Remove it, then run the call again")
    try:
        proc = subprocess.run(command, cwd=tmp, env=env, capture_output=True, timeout=_left(deadline))
    except subprocess.TimeoutExpired as error:
        raise _Unscannable(f"gitleaks outlasted the scan's {DEADLINE:.0f} seconds") from error
    except OSError as error:
        raise _Unscannable(f"gitleaks did not start ({error})") from error
    if proc.returncode not in (0, LEAKS):
        raise _Unscannable(f"gitleaks failed (exit {proc.returncode}: {_logged(proc.stderr)})")
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


def _its_own_repository(git_dir: str, env: dict, deadline: float) -> None:
    """Refuse a git directory that git, run there (`git -C <git dir>`, as the scan's reads and gitleaks' own git log
    are), does not take for the repository, where a call from the worktree reads the git directory itself: a .git
    there that names another repository, a commondir file (git follows a linked worktree's one step, to this
    directory, and no further) or a HEAD git cannot read (git then walks up to whatever repository is above)."""
    proc = _git(_Where(git_dir, None), ["rev-parse", "--git-common-dir"], deadline, env=env)
    # git answers from the directory it runs in (`.` for itself), or by its absolute path where it enters a worktree
    # that holds it (a core.worktree)
    found = os.path.normpath(os.path.join(git_dir, _out(proc))) if proc.returncode == 0 and _out(proc) else ""
    if found != os.path.normpath(git_dir):
        taken = (f"takes {found} for the repository, so the scan would read another" if found
                 else f"finds no repository there ({_tail(proc.stderr)})")
        raise _Unscannable(f"git run in this repository's git directory ({git_dir}), as the scan's reads and gitleaks' "
                           f"own git are, {taken}. A .git or a commondir file in the git directory does this, and so "
                           "does a HEAD there git cannot read: remove the file or repair HEAD, then run the call again")


def _scan_pushes(pushes: list[_Push], deadline: float) -> str | None:
    """Scan the commits each push would add, one gitleaks run per repository."""
    import tempfile

    repos: dict[str, list] = {}
    for push in pushes:
        # What a push sends is read where it runs, with the configuration its git reads.
        where = push.where
        proc = _git(where, ["rev-parse", "--git-common-dir"], deadline)
        if proc.returncode != 0:  # with no repository the push fails too, but it may read one this read cannot
            raise _Unscannable(f"git cannot read a repository where this push runs ({where.dir}: "
                               f"{_tail(proc.stderr)}), so the hook cannot tell which commits it would send. Push "
                               "from a repository git reads as it is set up, without settings in the call (a "
                               "safe.directory, say, belongs in git's global configuration, which the hook reads)")
        # git answers from the directory it enters, which a link on the shell's path leads to: a relative answer is
        # joined to that directory's real path.
        git_dir = os.path.realpath(os.path.join(where.dir, _out(proc)))
        revs, broad = _sends(push, where, deadline)
        if revs:
            entry = repos.setdefault(git_dir, [[], False])
            entry[0] += revs
            entry[1] |= broad
    env = _scan_env()
    for git_dir, (revs, broad) in repos.items():
        # The commits it adds, main's pins and the scan are read in the git directory gitleaks reads, as it does.
        _its_own_repository(git_dir, env, deadline)  # before any read there, which could answer from another
        scan = _Where(git_dir, None)
        revs = [*dict.fromkeys(revs), "--not", f"--remotes={REMOTE}"]
        proc = _git(scan, ["rev-list", "--count", *revs], deadline, env=env)
        if proc.returncode != 0:
            raise _Unscannable(f"git could not list the commits this push adds ({_tail(proc.stderr)})")
        count = _out(proc)
        if count == "0":
            continue
        version, binary = _binary()
        _new_enough(scan, env, deadline)
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
    try:
        reader.read(command, _State(base))
    except (_Unscannable, RecursionError):  # refusal() refuses each
        raise
    except Exception as error:  # a call that names git or gh: an error the hook does not expect refuses it
        raise _Unscannable(f"reading this call hit an error the hook does not expect ({type(error).__name__}: "
                           f"{error})") from error
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
                "push, its call may run only cd, pushd, popd, the builtins the hook reads (echo, printf, test, "
                "read, set, export, unset, eval and the like, not declare, local, alias or source), reads and "
                "filters that write no file and run no other program (cat, head, tail, grep, cut, wc, ls, jq and the "
                "like), and "
                "git commands that change no commit, ref or setting (not git clean, which may remove a directory) "
                "and take no settings from the call. A "
                "redirection may write /dev/null or another device, and the push's own output may go to a file "
                "(`git push ... > push.log 2>&1`). Run tests, lints, scripts, fetches and commits in an earlier call"
            )
    if any(step.push.where is None for _, step in pushes):
        return (
            "this command pushes from a directory the hook cannot name (one a variable, a substitution, sudo or "
            "another program that runs the push picks, one the ways of a command that may or may not run leave "
            "apart (a branch, a loop's turn, a break, a return, an `&&` or `||`, a redirection that may fail, as "
            "`< missing` or `2>&3`), one a trap on DEBUG, ERR or RETURN runs between the commands after it, one "
            "that does not exist yet, one "
            "an option a word before git's command may hide (`git $o push`), one a function the call may define "
            "otherwise, or a loop's later turn may run, may push from or move to, one a shell other than bash may "
            "leave otherwise (its pushd, popd, cd options, `~`, `$'...'` or `$\"...\"`, an exported function it may "
            "not import, or `time` before a function), one a `~` gives in a call that may quote one or run POSIX "
            "mode, one past a link and `..` that cd takes "
            "either way unless -P says which, a GIT_DIR or another variable it follows that the call sets in a way "
            "it cannot read, or a ref store, object store or namespace the call moves), so it cannot tell which "
            "commits the push sends. Push from a literal path, with no redirection that may fail, and not through "
            "a function: "
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
    _new_enough(project, plain, deadline, repository=bool(base))  # without a base, a fresh scratch repository is read
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
