# WS-10 — configuration and script placement hygiene

Implementation candidate: PR #696; merge held for WS-7 documentation/default integration and independent review.



- [x] Document every backend Settings field with actual defaults, validation and deployment overrides; preserve WS-7 statement-financials guidance.
- [x] Add a configuration completeness gate and prove it fails when a real field row is removed.
- [x] Move the Vercel helper and manual Resend smoke into backend/scripts; repair file-relative paths, update references, and verify without deployment or email.
- [x] Run full backend gates plus shell/AST/provenance checks; record exact evidence and request independent review before merge.

Verification before the final prose-only evidence update (candidate cb40ca33, main157e6a39):

```text
ruff check .: All checks passed! (exit 0)
bandit -r app -ll: No issues identified. (exit 0)
python -m pytest: 1876 passed, 2 deselected, 72 warnings in 143.67s (exit 0)
```

Exact runtime/dev pins checked using Python3.13.12; cryptography50.0.0 imported
from an isolated dependency target over the unchanged shared baseline environment.
Native Pango enabled for real PDF tests; workspace EDGAR/cache/SQLite paths kept the
run isolated. The two deselections are the existing performance lane.

The new Settings inventory test passed (1 passed, 1 warning in 0.18s). Removing
`JWT_LEEWAY_SECONDS` from the actual documentation failed with
`Settings inventory mismatch: missing=['JWT_LEEWAY_SECONDS'], obsolete=[]`
and `1 failed, 1 warning in 0.21s`. Changing the documented `SEC_MAX_RETRIES` default
from 5 to 6 also failed (`1 failed, 1 warning in 0.23s`). Both mutations were restored
before the full gate.

Script checks: Bash syntax passes; normalized Resend sender AST matches the original
except the declared function rename, return annotation, and non-interpolating f-string
lint repairs. The bootstrap now uses the file-relative backend path instead of cwd.
A mocked import from an unrelated directory resolves backend/.env and the backend
import path without sending. The sender was exercised only with an AsyncMock.
The Vercel helper was run from two working directories with npm/vercel stubs; both
resolved the same frontend directory and passed the existing build/deploy arguments.
Its public API variable was corrected to NEXT_PUBLIC_API_BASE_URL, used by the actual
frontend client. No real deployment, package installation, or email was triggered by
these script proofs.

Follow-up before merge: incorporate WS-7, retain its statement-aware extraction
section, change the inventory default to true, and refresh full gate evidence.
