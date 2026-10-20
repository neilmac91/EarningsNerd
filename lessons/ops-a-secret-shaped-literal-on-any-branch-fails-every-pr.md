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
commits: `gitleaks git . --log-opts="origin/main..HEAD" --redact=100 --exit-code 1`. If a flagged
commit is already pushed, rewrite it out of the branch at once (amend and `--force-with-lease` on a
branch you created), then re-run the `secret-scan` jobs it failed on other pull requests. A pin in the
flagged branch's own `.gitleaksignore` reaches only that branch's runs. Where a rewrite is not open to
you (pushed history you may not rewrite, or a branch others build on), pin the fingerprints on main at
once in a routine pull request, as #1342 and #1382 did: CI checks out each pull request merged into
main, so main's file reaches every pull request's run that an event starts after the pin. It does not
reach a re-run: GitHub re-runs a pull request's run on the merge commit that run first built (the
original event's `GITHUB_SHA`), whose file predates the pin, so while the flagged commit is on any
branch, a pull request whose scan failed passes on its next push (a merge of main will do), not on a
re-run. A fingerprint is commit-scoped (`<commit>:<path>:<rule>:<line>`); write the lines byte for byte
as the branch's own `.gitleaksignore` writes them, so neither merge conflicts, and prove a pin by
scanning without it from a checkout whose `.gitleaksignore` is main's, since gitleaks reads the scanned
directory's own file as well as any `-i` path.

**Gate (E126)**: `.claude/hooks/secret_scan_guard.py`, which `.claude/settings.json` runs before every
Bash command and every call to an MCP server whose name contains "github" in any case
(`backend/tests/unit/test_secret_scan_guard.py`). Before a `git push` it runs the job's pinned gitleaks,
with the job's flags, over the commits the push would add: those reachable from what it sends and from no
remote-tracking ref of the remote it pushes to, which it finds as git does (the remote the line names, by
its first word or `--repo`; else the current branch's `pushRemote`, `remote.pushDefault`, the current
branch's remote, then origin), whose refs count only when it pushes to the repository it fetches from:
a push to a URL, a path, a fork or a mirror reads every commit it sends. Its `git log` runs with options
that hold it to what CI's git prints
(`--no-color --no-textconv --no-ext-diff --root --pretty=medium --date=default --no-abbrev-commit
--no-show-signature --src-prefix=a/ --dst-prefix=b/`) and `GIT_NO_REPLACE_OBJECTS=1`, so the user's or the
repository's git config, none of which CI has, cannot hide an added line (colour, a textconv driver, a
replace ref, `log.showRoot`) or change its fingerprint (`format.pretty`, `log.date`, `log.abbrevCommit`,
`diff.noprefix`). It refuses the call on a
finding, naming each finding's file, line, rule and commit fingerprint, never the literal, and before any
scan when it cannot tell what the push sends (a source or a repository it cannot resolve as the line
stands, a `cd` that may not run where it stands, a long option `git push` does not take as written, which
git may complete (`--mirr` for `--mirror`), or a line that also runs another git command but a read, such as
a checkout or a fetch), saying what to name literally, or to push in a call of its own. It reads the push's
options in order, as git does, so a later `--no-dry-run` takes a dry run back, and a push that names
nothing to send reads git's config as git does (a remote's push refspecs, `push.default=matching`, a
mirror remote, with the pushing git's own `-c`). Every scan reads main's pins
and config (`origin/main`'s `.gitleaksignore` and `.gitleaks.toml`, as
last fetched; no pins when it cannot read them, and gitleaks' own default config, which the job runs,
while main has no `.gitleaks.toml`), never the pushing checkout's, its git directory's, a call's or one
that `GITLEAKS_CONFIG` or `GITLEAKS_CONFIG_TOML` names, since every other pull request's `secret-scan`
reads main's: a reviewed false positive takes `# gitleaks:allow` on its line, or a pin that has landed on
main and been fetched (a commit's, or a global `path:rule:line` one), and a pin on the branch gets nothing
past it. It refuses a line that makes commits and pushes them, since a hook runs before the line and
cannot read a commit the line has yet to make: commit in one call, push in the next. Before the GitHub MCP
`push_files` and `create_or_update_file` tools, and a `gh api` (or api.github.com) call naming a
repository's contents or git data, it scans the files the call sends, a base64 `content` value decoded,
and refuses the call when a file it sends cannot be read as the line stands (the line itself makes it,
it is over 1 MiB, it is no regular file, or a relative path names it in a line that changes
directory); it reads them under a staging directory, not at the repository paths pins name, so a
reviewed false positive there takes the marker, or a commit pushed with git, whose scan reads main's
pins. The binary is the one
`.claude/hooks/secret_scan_setup.py`, a SessionStart hook, extracts from the archive the job pins (version
and SHA-256 read from `.github/workflows/ci.yml`) into
`~/.cache/earningsnerd/gitleaks/<version>-<archive SHA-256>/`, with its own SHA-256 recorded beside it;
use it for a scan by hand. CI runs the linux x64 archive; the setup pins the same release's macOS arm64
and x64 and linux arm64 archives from its checksums file, and the gate fails when `ci.yml`'s version moves
without them. Without a verified binary, or on a platform with no pin, the guard refuses every call it
would scan and says what to do (the setup command; how to add a pin). Not gated: a push or write another
shell or program makes (`bash -c '...'`, a script, an alias), text a command builds as it runs, git
configuration a line sets through the environment (`GIT_CONFIG_COUNT=`, an export), a form only a
deliberate bypass writes (an escape that spells a word or a JSON key; the hook stops accidents, not a
session set on getting past it), a remote-tracking ref whose branch the remote has since deleted
(`git fetch --prune` drops it), a file whose text git leaves out of `git log -p`
as binary because of the repository's or the user's settings (a `-diff` attribute in `info/attributes`
or `core.attributesFile`, a diff driver set `binary = true`, `core.bigFileThreshold` below its size; CI
has none of them and scans that text; `--text` would scan it, but also the binary files CI skips, so the
hook would refuse pushes CI passes), the other way about a committed `.gitattributes` that marks files
`-diff` (CI's checkout honours it and the hook reads none, so it can refuse a push CI passes), a fork
layout, where CI reads the main of another
remote than origin (the pins come from `origin/main` alone), a session that loads no repository hooks
(Codex, Astra), a person's own push, and every clause above about a literal already pushed.

**Evidence**: E20's commit 4ac900bb, amended to 2398f2af with the marker and force-pushed at 09:53 UTC;
#1310's `secret-scan` re-run afterwards. Partly gated: the hook above refuses a session's push before it
leaves; CI's `secret-scan` finds what gets past the hook, but only after the push, when the next scan of
each pull request fails.

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
rule was written (#1334's and #1407's), so E126 made the scan a gate before the push (**Gate** above).
