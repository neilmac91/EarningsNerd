# Scan your commits with the pinned gitleaks before pushing a secret-shaped literal; once pushed, it fails every pull request until it leaves the branch history

Date: 2026-10-16   Area: ops

**Context**: The E20 branch committed Svix's published example secret (`whsec_…`) as a test
vector, without the `# gitleaks:allow` marker the repository's test fixtures carry. CI's
`secret-scan` job checks out every branch (`fetch-depth: 0`) and runs gitleaks with
`--log-opts="--branches --remotes"`, so after the push it failed on another session's pull request
(#1310's run 38881925266), and it would have blocked any `deploy-backend` that ran in that window.
A follow-up commit cannot clear it, because the scan reads every commit on every branch.

**Rule**: Before pushing a commit that adds a literal shaped like a credential (a provider's test
vector, a sample key, a fixture password), mark the line `# gitleaks:allow` with its reason and run
the job's pinned gitleaks (version and SHA-256 in `.github/workflows/ci.yml`'s `secret-scan` job) over
your new commits: `gitleaks git . --log-opts="origin/main..HEAD" --redact=100 --exit-code 1`. If a
flagged commit is already pushed, rewrite it out of the branch at once (amend and
`--force-with-lease` on a branch you created), then re-run the `secret-scan` jobs it failed.
`.gitleaksignore` only reaches branches that carry the entry, which other pull requests do not.

**Evidence**: E20's commit 4ac900bb, amended to 2398f2af with the marker and force-pushed at
09:53 UTC; #1310's `secret-scan` re-run afterwards. Partly gated: CI's `secret-scan` finds the
literal, but only after the push, when every pull request already fails.
