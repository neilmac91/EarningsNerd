# Scan your commits with the pinned gitleaks before pushing a secret-shaped literal; once pushed, it fails every pull request until it leaves the branch history or main pins it

Date: 2026-10-16   Area: ops

**Context**: The E20 branch committed Svix's published example secret (`whsec_…`) as a test
vector, without the `# gitleaks:allow` marker the repository's test fixtures carry. CI's
`secret-scan` job checks out every branch (`fetch-depth: 0`) and runs gitleaks with
`--log-opts="--branches --remotes"`, so after the push it failed on another session's pull request
(#1310's run 38881925266), and it would have blocked any `deploy-backend` that ran in that window.
A follow-up commit cannot clear it, because the scan reads every commit on every branch.

**Rule**: Before pushing a commit that adds a literal shaped like a credential (a provider's test
vector, a sample key, a fixture password, a made-up token at its real length), mark the line
`# gitleaks:allow` with its reason, or build the value so no rule matches, and run the job's pinned
gitleaks (version and SHA-256 in `.github/workflows/ci.yml`'s `secret-scan` job) over your new commits.
The **Gate** below does it before each push. By hand, scan the git directory with main's pins alone, so
a pin only your branch carries hides nothing. gitleaks reads a `.gitleaksignore` in the directory it
runs in unless `--gitleaks-ignore-path` names another file, and the scanned directory's own, so name
main's. Name your own HEAD by its commit, since gitleaks' git runs in the git directory, where `HEAD` is
the main worktree's. And keep the git directory free of what the scan would read there: a
`.gitleaksignore` or `.gitleaks.toml`; an `info/attributes` that marks a file binary; settings that
change what `git log -p` prints (colour, a text conversion, no prefixes and the like, which the **Gate**
holds at git's defaults); and a `.git`, a `commondir` file or a HEAD git cannot read, which send git to
another repository. Run it as the **Gate**'s scan does: with none of your own git configuration,
attributes or `GIT_*` and `GITLEAKS_*` variables, since a `color.ui`, a `core.attributesFile`, a global
attributes file or a `GITLEAKS_CONFIG` would hide a line too; past replace refs, which would show
another commit's lines; with `attr.tree` at the empty tree and `core.attributesFile` at none, so no
`.gitattributes` (in the git directory, in the worktree a `core.worktree` names, in a tree the
repository's own `attr.tree` names or at a bare repository's HEAD) and no attributes file the repository
names marks a file binary; with `safe.directory` open, since git refuses another user's checkout; and
with git's graft hint on, so a graft file fails the scan rather than hide a commit's lines. Name main by
its full ref, since a branch or tag named `origin/main` takes the short name's place. Whatever git
writes to its standard error (another user's checkout, an ambiguous ref, a graft's hint), gitleaks
reports a partial scan as clean (`no leaks found in partial scan`) and exits 1: that is a failed scan.
It needs git 2.43 or later, the first to read `attr.tree`:

```bash
pins=$(mktemp) && git --no-replace-objects show refs/remotes/origin/main:.gitleaksignore > "$pins" &&
env -i PATH="$PATH" HOME=/nonexistent GIT_CONFIG_NOSYSTEM=1 GIT_ATTR_NOSYSTEM=1 GIT_NO_REPLACE_OBJECTS=1 \
  GIT_CONFIG_COUNT=4 GIT_CONFIG_KEY_0=attr.tree GIT_CONFIG_VALUE_0=4b825dc642cb6eb9a060e54bf8d69288fbee4904 \
  GIT_CONFIG_KEY_1=safe.directory GIT_CONFIG_VALUE_1='*' \
  GIT_CONFIG_KEY_2=core.attributesFile GIT_CONFIG_VALUE_2=/dev/null \
  GIT_CONFIG_KEY_3=advice.graftFileDeprecated GIT_CONFIG_VALUE_3=true \
  gitleaks git "$(git rev-parse --git-common-dir)" --redact --gitleaks-ignore-path "$pins" \
  --log-opts="refs/remotes/origin/main..$(git rev-parse HEAD)"
```

Here `gitleaks` is the job's pinned binary, which `--install` (see **Gate**) puts under
`~/.cache/earningsnerd/gitleaks/`. Were main to carry a `.gitleaks.toml`, name it too, with `--config`.

If a flagged commit is already pushed, rewrite it out of the branch at once (amend and `--force-with-lease`
on a branch you created), then re-run the `secret-scan` jobs it failed on other pull requests. A pin
in the flagged branch's own `.gitleaksignore` reaches only that branch's runs. Where a rewrite is not
open to you (pushed history you may not rewrite, or a branch others build on), pin the fingerprints
on main at once in a routine pull request, as #1342 and #1382 did: CI checks out each pull request
merged into main, so main's file reaches every pull request's run that an event starts after the
pin. It does not reach a re-run: GitHub re-runs a pull request's run on the merge commit that run
first built (the original event's `GITHUB_SHA`), whose file predates the pin, so while the flagged
commit is on any branch, a pull request whose scan failed passes on its next push (a merge of main
will do), not on a re-run. A fingerprint is commit-scoped (`<commit>:<path>:<rule>:<line>`); write
the lines byte for byte as the branch's own `.gitleaksignore` writes them, so neither merge
conflicts, and prove a pin by scanning without it from a checkout whose `.gitleaksignore` is main's,
since gitleaks reads the scanned directory's own file as well as any `-i` path.

**Gate**: `.claude/hooks/secret_scan_guard.py`, which `.claude/settings.json` runs before every Bash
command and every call to an MCP server whose name contains "github" in any case, and which git runs
as its pre-push hook (`.claude/hooks/git/pre-push`) in a clone that turns that hook on
(`backend/tests/unit/test_secret_scan_guard.py`). It runs the `secret-scan` job's gitleaks over the
commits a call or a push would add to GitHub, and refuses the call, or stops the push, on a finding. The binary is the version and
archive SHA-256 in `ci.yml`, installed once per machine and pin with
`python3 .claude/hooks/secret_scan_guard.py --install`, which checks the linux x64 archive against
that SHA-256 and another platform's against the release's checksums file once that file lists the pin.
- **What it scans.** For a `git push`, the commits reachable from what it sends and from no ref under
  `refs/remotes/origin` (GitHub as last fetched); a push whose words it cannot read whole counts as
  sending HEAD and every branch and tag. For a GitHub MCP write (`push_files`,
  `create_or_update_file`), the commit the write would make on its branch's tip as last fetched, so
  only the lines it adds count, as in CI; a branch not fetched, or another repository, gets the files
  whole.
- **How.** It scans the git directory with main's `.gitleaksignore` and `.gitleaks.toml` alone
  (gitleaks' built-in rules when main has none, as in CI), so a pin only the branch carries does not
  count there, as it does not in other pull requests' runs. The scan reads none of the session's
  `GIT_*` or `GITLEAKS_*` variables, no system or global git configuration, no replace ref and no
  attributes but the repository's own `info/attributes`, and holds the settings that change what
  `git log -p` prints at git's defaults.
- **Refused outright.** A push that follows, or runs beside, a command in the same call that may make or
  move its commits, or remove the directory it runs in: a commit, a test run, a fetch, a `git clean`
  (which may remove a directory a later `cd` enters), a redirection that writes a file, a git read given
  settings or a file to write, a new shell given a startup file or a function, a function the call may
  define otherwise or not at all, or that `unset` may remove, and a builtin the hook does not read
  (`declare`, `local`, `alias`, `source` and the rest it takes for programs). Run them in a call before,
  and push in a call of its own. A filter that can write a file or run a program counts too, so
  `git push 2>&1 | tee push.log`, `git push 2> >(tee push.log)` and a `sort` before the push are
  refused, where `| tail`, `> push.log 2>&1` and `> /dev/null` pass. Also a push from a directory it
  cannot name (one a variable, a substitution, sudo or another program that runs the push picks, one the
  ways of a command that may or may not run leave apart, as a branch, a loop's turn, a break, a return
  or a redirection that can fail may, one that does not exist yet, one a function the call may define
  otherwise, or a loop's later turn may run, may push from or move to, one an option a word before git's
  command may hide (`git $o push`), one a shell other than bash may leave otherwise (its `pushd`,
  `popd`, `cd` options, `~`, `$'...'` and `$"..."`, an exported function it may not import, and `time`
  before a function), one past a link and `..` that `cd` takes either way unless `-P` says which, or one
  a variable the call sets in a way the hook cannot read decides), and one with a ref store, object
  store or namespace the call moves (`GIT_COMMON_DIR`, `GIT_OBJECT_DIRECTORY`,
  `GIT_ALTERNATE_OBJECT_DIRECTORIES`, `GIT_NAMESPACE`, `--namespace`); `git subtree push`,
  `git send-pack` and `git http-push`; a line nested more than five levels deep (shells, evals, traps,
  functions, `!` aliases, process substitutions); a case in a command substitution with a pattern no `(`
  opens; a parameter expansion the hook's shell reader splits where bash reads one word (one with an
  operator character in it outside quotes, as `${x%)}`, one in double quotes that nests a quote or a
  backquote, as `"${x:-"a"}"`, or a `<<` in a `${...}`, a `$[...]` or a subscript, as `a[1<<2]=x`, which
  the reader takes for a here-document); a function's body (one that is no group, subshell or compound a
  reserved word opens, as `f() [[ -n x ]]`, among them) or a process substitution whose end the hook
  cannot find; a call that takes the hook more than its 50 seconds to read, or holds a line of more than
  400,000 characters outside its here-documents; an MCP write that sends a path twice; and a write to a
  repository's contents or git data through GitHub's API. The nested line, the case, the parameter
  expansion, the body or process substitution with no end, the slow call and the long line are refused
  whether or not the call pushes.
- **Failing closed.** For a call that adds commits, a missing binary, an unreadable pin, a git older
  than 2.43 (the first to read `attr.tree`, which the scan holds at the empty tree) or one whose version
  it cannot read, a scan that would read a repository whose objects are not SHA-1, a `.gitleaksignore`
  or `.gitleaks.toml` in the git directory, or a scan that fails, errs or outlasts 50 seconds refuses
  the call. So does a line or an input nested past Python's own limits and, before the commits are
  counted, a push whose repository git cannot read where it runs (the call's own settings may let the
  push read one) or a git directory that git, run there as the scan's reads are, does not take for the
  repository (a `.git` or a `commondir` file in it, or a HEAD git cannot read, sends git elsewhere). A
  failed scan's refusal names the errors gitleaks logged. An error the hook does not expect in reading a
  Bash call that names git or gh refuses it too; any other crash lets the call through.
- **git's pre-push hook.** `git config core.hooksPath .claude/hooks/git` turns it on in a clone, once,
  and a cloud session's start does it for the session's clone (`.claude/settings.json`'s SessionStart
  command), unless a hooks path is set at any level or the clone has hooks of its own, which it leaves
  as they are and names to the session. git runs it before a push sends anything, whoever runs the
  push, and hands it the refs the push sends: it scans the commits each one reaches and no ref under
  `refs/remotes/origin` holds, with the scan above, and stops the push on a finding, wherever the scan
  fails closed (that refusal names `git push --no-verify`, which skips git's hooks; a finding's does
  not) and on any error. A delete, and a commit GitHub holds as last fetched, send it nothing to scan.
  git skips a hook it cannot execute, so the suite holds the hook's tracked mode. In a Claude Code
  session a push passes both: the PreToolUse hook before the call, git's as git sends it.
- **What it cannot see.** Before a call, the PreToolUse hook cannot see these; git's pre-push hook
  stops each push among them as git sends it, in a clone that turns it on:
  - a push a script, a program (`env -S`'s string among them) or a shell's standard input runs;
  - a git that a variable, a substitution, an escape, a brace expansion, a glob or a shell alias or
    function names;
  - a `GIT_DIR`, `HOME` or `CDPATH` the shell's profile sets;
  - a break in a function that an older bash compatibility level (`BASH_COMPAT`, `shopt -s compat43`)
    lets leave its caller's loop;
  - an assignment `set -k` makes of a command's argument, or a variable an arithmetic expression assigns
    outside `$((...))`;
  - a command substitution inside an unquoted here-document's text, or a `$((` that bash reads as one;
  - the commits a git command it does not know makes as it runs, or a program the repository's own
    configuration has a git read run (an fsmonitor, a textconv or clean filter);
  - a push in a trap (on EXIT or a signal) when the shell may stop before its end, under `set -e` or
    `set -u`, at a `${x?}`, at a signal, or at a syntax error: the hook reads the trap from where the
    shell would end normally, not from where it stopped;
  - a push in a session that loads no repository hooks;
  - a person's own push.

  Neither hook sees these:
  - a push with `--no-verify`, from a clone whose `core.hooksPath` is unset or names other hooks (or
    that the push's own `-c core.hooksPath=` moves), or from a checkout without
    `.claude/hooks/git/pre-push`: only the PreToolUse hook, before a Claude Code call, stands there;
  - the commits a push sends to submodules, which run their own repositories' hooks;
  - a commit a stale ref under `refs/remotes/origin` still holds, or an MCP write to a branch fetched
    before it changed;
  - the attributes the repository's own `info/attributes` sets;
  - a squash or rebase merge whose net change still holds a line pinned only by its branch commit (so
    mark such a line inline, as the Rule says);
  - content other programs send through GitHub's API, a URL a variable holds, or a GraphQL mutation
    read from standard input or a variable;
  - a GitHub MCP server named without "github", and an MCP write in a session that loads no repository
    hooks.

  CI's `secret-scan` still reads each of them that reaches this repository, after the push.

**Evidence**: E20's commit 4ac900bb, amended to 2398f2af with the marker and force-pushed at 09:53 UTC;
#1310's `secret-scan` re-run afterwards. Partly gated: CI's `secret-scan` finds the literal, but only
after the push, when the next scan of each pull request fails; since E126 the **Gate** above runs the
scan before a push in a session that loads the repository's hooks.

**Recurrence (2026-10-15 and 2026-10-17, pinned on main)**: #1340's branch carried a design-token
name that the generic-api-key rule matched; main's run and every pull request's failed until #1342
pinned its fingerprint on main. #1334's push at 02:44 UTC on 2026-10-17 brought `eec330cb` to the
remote, whose two mail-test fixtures printed a made-up 43-character token at its real length (base64
of a phrase, no credential): main's run at 01:11 had read 2,515 commits clean (job 117269404361), and
#1334's run on `b591767b` read 2,533 and failed on them (job 117288949283, `leaks found: 2`). Its pushed
history was not to be rewritten, so `283ac453` pinned the two in its own `.gitleaksignore` and marked
both lines, and #1382 merged the same six lines on main (`cc071d4a`, 06:16 UTC). No push to main and
no other pull request ran CI in that window, so nothing was blocked.

**Recurrence (2026-10-19, pinned on main)**: #1407's push at 09:15 UTC brought `41da420b` to the
remote. Its E125 evidence holds a copy of E110's mail renderer (`render_mails.py.txt`), which sets the
test suite's `SECRET_KEY` (`backend/tests/conftest.py`'s value) and a made-up 43-character token: an
evidence script, not a test, pushed without the scan this rule asks for. #1407's own run failed on the
two (job 117981141804, `leaks found: 2`), and so did three other pull requests' runs, each red on the
scan alone: #1372's at 09:24 (job 117984774947), #1409's at 09:36 (job 117989883239) and #1410's at
09:47 (job 117994135994). `3ed4198c` marked both lines and pinned them in #1407's own
`.gitleaksignore`, which reached #1407's runs alone; another session's #1408 merged the same six lines
on main (`4b2ae9d8`, 09:50 UTC), and the runs that started after it passed (main's on `4b2ae9d8`,
#1372's on its merge of main, `896fa772`). #1409's and #1410's runs had started before it, so their
next pushes clear them, not a re-run. Two pushes this lesson records have skipped the scan since the
rule was written (#1334's and #1407's), so E126 added the **Gate** above, which scans before the
push.
