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
gitleaks (version and SHA-256 in `.github/workflows/ci.yml`'s `secret-scan` job) over your new
commits. The **Gate** below does it before each push. By hand, scan the git directory, which holds no
`.gitleaksignore` of its own, so a pin only your branch carries hides nothing:
`gitleaks git "$(git rev-parse --git-common-dir)" --log-opts=origin/main..HEAD --redact`. If a
flagged commit is already pushed, rewrite it out of the branch at once (amend and `--force-with-lease`
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
command and every call to an MCP server whose name contains "github" in any case
(`backend/tests/unit/test_secret_scan_guard.py`). It runs the `secret-scan` job's gitleaks over the
commits a call would add to GitHub, and refuses the call on a finding. The binary is the version and
archive SHA-256 in `ci.yml`, installed once per machine and pin with
`python3 .claude/hooks/secret_scan_guard.py --install`, which checks the linux x64 archive against
that SHA-256 and another platform's against the release's checksums file once that file lists the pin.
- **What it scans.** For a `git push`, the commits reachable from what it sends and from no ref under
  `refs/remotes/origin` (GitHub as last fetched); a push whose words it cannot read whole counts as
  sending HEAD and every branch and tag. For a GitHub MCP write (`push_files`,
  `create_or_update_file`), the commit the write would make on its branch's tip as last fetched, so
  only the lines it adds count, as in CI; a branch not fetched, or another repository, gets the files
  whole.
- **How.** It scans the git directory with main's `.gitleaksignore` and `.gitleaks.toml` alone, so a
  pin only the branch carries does not count there, as it does not in other pull requests' runs. The
  scan reads none of the session's `GIT_*` or `GITLEAKS_*` variables, no system or global git
  configuration and no replace ref, and holds the settings that change what `git log -p` prints at
  git's defaults.
- **Refused outright.** A push that follows, or runs beside, a command that may make or move its
  commits in the same call: a commit, a test run, a fetch, a redirection that writes a file, a git read
  given settings or a file to write. Run them in a call before, and push in a call of its own. A filter
  that can write a file or run a program counts too, so `git push 2>&1 | tee push.log` and a `sort`
  before the push are refused, where `| tail`, `> push.log 2>&1` and `> /dev/null` pass. Also a
  push from a directory it cannot name; `git subtree push`, `git send-pack` and `git http-push`; a line
  nested more than five levels deep (shells, evals, traps, functions, `!` aliases, process
  substitutions); an MCP write that sends a path twice; and a write to a repository's contents or git
  data through GitHub's API.
- **Failing closed.** For a call that adds commits, a missing binary, an unreadable pin, or a scan that
  fails, errs or outlasts 50 seconds refuses the call, and so does a line or an input nested past
  Python's own limits. Any other crash in reading the command lets the call through.
- **What it cannot see.**
  - a push a script, a program or a shell's standard input runs;
  - a git that a variable, a substitution, an escape or a shell alias or function names;
  - a `GIT_DIR`, `HOME` or `CDPATH` the shell's profile sets;
  - a command substitution inside an unquoted here-document's text, or a `$((` that bash reads as one;
  - the commits a git command it does not know makes as it runs, or a program the repository's own
    configuration has a git read run (an fsmonitor, a textconv or clean filter);
  - the commits a push sends to submodules;
  - a commit a stale ref under `refs/remotes/origin` still holds, or an MCP write to a branch fetched
    before it changed;
  - the attributes the repository's own `info/attributes` sets;
  - a squash or rebase merge whose net change still holds a line pinned only by its branch commit (so
    mark such a line inline, as the Rule says);
  - content other programs send through GitHub's API, a URL a variable holds, or a GraphQL mutation
    read from standard input or a variable;
  - a GitHub MCP server named without "github";
  - a session that loads no repository hooks;
  - a person's own push.

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
