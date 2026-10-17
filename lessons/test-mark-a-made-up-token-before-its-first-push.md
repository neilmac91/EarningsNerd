# Mark a made-up, credential-shaped fixture value `gitleaks:allow` before its first push; the secret scan reads every branch

Date: 2026-10-17   Area: test

**Context**: CI's `secret-scan` (`.github/workflows/ci.yml`) runs gitleaks over `--branches --remotes`
after a full checkout. It reads `.gitleaksignore` from the tree it checks out, so a finding on one branch
fails main's run and every other pull request's run. `deploy-backend` needs that job, so a main push skips
its deploy until the finding is pinned on main.

- 2026-10-15: #1340's branch carried a design-token name that the generic-api-key rule matched. Main's run
  and every pull request's failed until #1342 pinned its fingerprint on main.
- 2026-10-17: #1334's push at 02:44 UTC brought `eec330cb` to the remote. Two of its mail-test fixtures
  printed a made-up 43-character token at its real length (base64 of a phrase, no credential). Main's run
  at 01:11 had read 2,515 commits clean. #1334's run on `b591767b` at 02:44 read 2,533 and failed on them
  (job 117288949283). #1334 pinned them in its own `.gitleaksignore` (`283ac453`) and marked both lines
  `# gitleaks:allow`. Main's file stayed unpinned until #1382 merged the same six lines (`cc071d4a`,
  06:16 UTC). No push to main and no other pull request ran CI in that window, so nothing was blocked.

**Rule**: Before a branch's first push, give each made-up value shaped like a credential an inline
`# gitleaks:allow` on its own line, or build it so no rule matches. A fixture token at its real length is
the common case. Then scan the branch's new commits with CI's pinned gitleaks (8.24.3):
`gitleaks git . --log-opts="origin/main..HEAD" --redact=100`. If a finding reaches the remote anyway, pin
its fingerprints on main at once in a routine pull request, as #1342 and #1382 did. Each fingerprint is
commit-scoped (`<commit>:<path>:<rule>:<line>`). Write the lines byte for byte as the branch's own
`.gitleaksignore` writes them, so neither merge conflicts. To prove a pin, scan without it from a checkout
whose `.gitleaksignore` is main's: gitleaks reads the scanned directory's own file as well as any `-i` path.

**Evidence**: #1342; #1382 (`cc071d4a`); jobs 117269404361 (main at `2140131b`, clean) and 117288949283
(#1334 at `b591767b`, `leaks found: 2`); `.gitleaksignore`.
