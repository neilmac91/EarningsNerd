# Independent scan finding review

Confirmed false positive at published commit `6ee3c7c847d83e76dac72cbc8429c6dacbfaac81`. The reported occurrence is the radius identifier borderRadius.2xl, with value 1.5rem, a definition at `frontend/tailwind.config.js:238`, utility candidates such as `rounded-2xl`, and 23 static uses across 16 files. The source defines the same 24px radius. This is a public styling identifier, not a credential or authentication token.

Reproduced independently with Gitleaks 8.24.3 on scratch copies of the exact published JSON:

- Original file: exit 1, one `generic-api-key` finding.
- Changed all 156 inventory property keys from `token` to `name`, retaining their values and other content: exit 0, zero findings.

Thus the schema clarification removes this match from the current file under the pinned scanner. It does not guarantee that arbitrary future inventory content will never match another rule.

The CI command scans Git history with `--branches --remotes`. A subsequent JSON rename cannot remove the finding from the already published commit. The separately reviewed fingerprint for the gate owner is:

`6ee3c7c847d83e76dac72cbc8429c6dacbfaac81:tasks/design-system-review-2026-10/data/tokens.json:generic-api-key:1`

No branch files or gate configuration were edited. Scratch probe files and redacted results are in `/workspace/scratch/scan-review-probe/`.

Author verification: the proposed exact pin was supplied only through a scratch ignore file. The unchanged full branch-history command then scanned 2,129 commits and found no leaks. The working records directory also passed the pinned scanner after the schema change. The patch remains unapplied; no credential rule or gate file changed.
