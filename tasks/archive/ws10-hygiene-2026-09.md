# WS-10 — configuration and script placement hygiene

Implementation candidate: PR #696; WS-7 integrated, independent review and CI required before merge.



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

WS-7 integration: main99e91ba7 is incorporated at candidate5893a79d. The inventory
now records `USE_STATEMENT_FINANCIALS=true`; the statement-aware extraction section
and SIC backfill instructions are retained verbatim from main. Refreshed full gate:

```text
ruff check .: All checks passed! (exit 0)
bandit -r app -ll: No issues identified. (exit 0)
python -m pytest: 1910 passed, 2 deselected, 72 warnings in 143.01s (exit 0)
```

The repeated proof on this candidate passed (`1 passed, 1 warning in 0.10s`). Both
removed-field and incorrect-default mutations again failed (`1 failed, 1 warning
in 0.09s` each), and the script AST/bootstrap/stubbed-shell checks passed. Mutations
were restored byte-for-byte; no application source or tests changed after the gate.
Independent review and observed CI remain the merge prerequisites.
