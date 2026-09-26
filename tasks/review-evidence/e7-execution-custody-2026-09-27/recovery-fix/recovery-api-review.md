# Independent review: pending source-review recovery API

Reviewed delta `72606af246f89464f1acab1bdc8f4b6c877b5fd5..282d73c69d12307265c44e8ab5ce597cc95f906a`
plus the owner's focused path-boundary correction, identified by the final file hashes below. This
was a read-only code review; I did not edit the checkout or run tests.

## Resolved finding

### [P2] Validate complete recovery artifact paths inside the journal root

Original snapshot `282d73c6`, `backend/evals/acceptance_source_review_execution.py:650-692`.

`_pending_settlement_intent` passed only the attempt directory through `_safe`, then appended
`settlement-intent.json`, `artifact.bin`, and `receipt.json` and followed them with
`exists`/`is_file`/`read_bytes`. A child symlink could therefore resolve outside the journal root.
That broke the operator-owned artifact boundary and differed from prompt/input recovery and sealed
intent validation, which pass the complete child path through `_safe`. An external canonical intent
and matching artifact/receipt could be accepted as recovery state; a dangling intent symlink was
silently treated as no intent because `Path.exists()` follows it and returned false.

The owner fixed this by passing each complete intent, artifact, and receipt path through `_safe`
before inspection. External and dangling-external intent symlinks now fail with the root-escape
error. The same complete-path construction protects all three recovery artifacts. The focused
existing crash-recovery test covers the external and dangling path cases; the owner reported that
selection passing. I inspected the fix but did not run it.

Two independent refutation attempts failed:

1. A `_safe` parent directory does not contain its children: POSIX permits a child symlink in that
   directory to resolve outside the validated root.
2. Canonical JSON and SHA-256 checks validate bytes, not ownership. An external target can carry
   matching canonical bytes and hashes, while the sealed-history implementation demonstrates the
   intended stronger pattern by validating the complete intent path through `_safe`.

## Other review results

- **Correctness:** The API opens SQLite in read-only mode, preserves the pending row, returns the
  original reservation/prompt fields, and marks every recovered result delivery-uncertain with
  redispatch forbidden. It returns `None` only for no pending work or a valid sealed journal, and
  rejects multiple pending rows or a sealed journal that still contains one.
- **Crash recovery:** A durable settlement intent binds terminal status and artifact/receipt hashes.
  Recovery verifies canonical intent bytes and any already-written payload bytes. A different later
  settlement cannot overwrite that intent. The updated documentation correctly permits retirement
  only when no durable intent exists.
- **Retry/history:** Recovery creates no row. The existing pending row still blocks reservation and
  sealing; retirement followed by a fresh-context retry retains the next attempt number. The tests
  exercise ordinary lost-return recovery, prompt tampering, no row creation, settlement-intent crash
  recovery, retry, and sealed no-pending behavior.
- **Security/performance/maintainability:** No transport, provider call, admission claim, unbounded
  loop, query fan-out, or mutable global state was added. The helper is bounded to one pending row
  and a small fixed set of retained files. With the path-boundary issue resolved, the delta is
  cohesive and the public documentation matches the behavior.

Verdict: **clear** for commit and the owner's planned fault proof/full gate. No actionable finding
remains in the reviewed recovery delta. No unrelated capacity finding is included here.

## Reviewed hashes

- `backend/evals/acceptance_source_review_execution.py` SHA-256
  `03bba391b873a59ebf2cba1b232c728d6cb37c087271556fd1543ec2877283d8`
- `backend/tests/unit/test_acceptance_source_review_execution.py` SHA-256
  `306a292f92e3dfe4ab917103e17019d65a1eef9a68dff51331960d54c4f477bc`
- `tasks/readiness-2026-09-21/acceptance/source-review-execution.md` SHA-256
  `302583071ebd871da44dd1ebdca659b69bb21b3f9bb66702292cb49c557397ea`
