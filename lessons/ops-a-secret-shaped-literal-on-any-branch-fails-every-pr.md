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
branch you created), then re-run the `secret-scan` jobs it failed. A pin in the flagged branch's own
`.gitleaksignore` reaches only that branch's runs. Where a rewrite is not open to you (pushed history
you may not rewrite, or a branch others build on), pin the fingerprints on main at once in a routine
pull request, as #1342 and #1382 did: CI checks out each pull request merged into main, so main's file
reaches every run. A fingerprint is commit-scoped (`<commit>:<path>:<rule>:<line>`); write the lines
byte for byte as the branch's own `.gitleaksignore` writes them, so neither merge conflicts, and prove
a pin by scanning without it from a checkout whose `.gitleaksignore` is main's, since gitleaks reads
the scanned directory's own file as well as any `-i` path.

**Evidence**: E20's commit 4ac900bb, amended to 2398f2af with the marker and force-pushed at
09:53 UTC; #1310's `secret-scan` re-run afterwards. Partly gated: CI's `secret-scan` finds the
literal, but only after the push, when every pull request already fails.

**Recurrence (2026-10-15 and 2026-10-17, pinned on main)**: #1340's branch carried a design-token
name that the generic-api-key rule matched; main's run and every pull request's failed until #1342
pinned its fingerprint on main. #1334's push at 02:44 UTC on 2026-10-17 brought `eec330cb` to the
remote, whose two mail-test fixtures printed a made-up 43-character token at its real length (base64
of a phrase, no credential): main's run at 01:11 had read 2,515 commits clean (job 117269404361), and
#1334's run on `b591767b` read 2,533 and failed on them (job 117288949283, `leaks found: 2`). Its pushed
history was not to be rewritten, so `283ac453` pinned the two in its own `.gitleaksignore` and marked
both lines, and #1382 merged the same six lines on main (`cc071d4a`, 06:16 UTC). No push to main and
no other pull request ran CI in that window, so nothing was blocked.
