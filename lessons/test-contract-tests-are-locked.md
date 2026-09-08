# Contract anchors are locked: never edit them in the same PR as the code they guard

Date: 2026-07-06   Area: test

**Context**: The refactor's safety came from characterization anchors (T1–T10:
SSE stream contract, background-generation before-photo, guest quota (retired in #619 —
generation now requires an account; its successor anchor is test_generation_requires_account.py), Stripe downgrade,
expired-trial gating, filing-scan exactly-once, refresh replay, companyfacts fixture,
frontend SSE parser parity — plus `test_auth_flow.py` and the Stripe webhook tests).
Their value depends on them NOT moving while the guarded code moves. The one sanctioned
exception pattern: when a pre-approved behavior change retires code, the pins that
pinned the OLD behavior are deleted in the SAME commit as that code (e.g. the flag-off
legacy pins died with the legacy path in PR #565) — with the change recorded as an
explicit contract change in the PR body and delta log.

**Rule**: A refactor PR may touch a locked anchor ONLY to remove references to symbols
deleted in that same PR, or to execute a pre-approved, documented contract flip. Any
other anchor edit = stop and surface to the founder. Write anchors to survive the lock:
assert status codes and stable substrings (not full marketing copy), avoid patching
private internals that behavior-preserving refactors are free to rename.

**Evidence**: `tasks/architecture-refactor-plan.md` verification rules; PR #547 (anchor
quality review — lock-friction findings); PR #565 (the sanctioned pin-retirement pattern).


**Inventory clarification (2026-09-06):** frontend T10 is explicitly
`frontend/tests/unit/summaryStream.contract.spec.ts` (`tasks/architecture-refactor-plan.md:677,775`).
The separate `summaryStreamAuthRefresh.spec.ts` is not a named anchor; its descriptive filename
alone does not extend the lock. During account-cache work an agent initially over-applied the
lock to that ordinary test. Root and independent inventory review corrected the classification
before changing only its rejected-refresh fixture to carry HTTP 401, preserving every assertion.
Actual named anchors remained byte-identical. Use the cited inventory when resolving scope.

**Inventory correction (2026-09-08, Astra audit):** actual T4 is
`backend/tests/unit/test_subscription_webhook_sync.py`, as the completion record in
`tasks/architecture-refactor-plan.md` lines 78–83 and original commit `2b41718d` establish.
The earlier planned name `test_stripe_downgrade.py` never became its home. #759 appended
three tests while incorrectly classifying the actual file as unlocked; all prior assertions
are unchanged, but the file differs. Founder disposition on retaining those additions is
pending in `tasks/audit-astra-2026-09-08.md`. T6 remained deferred; T3's current successor is
`backend/tests/unit/test_generation_requires_account.py`. These clarify existing rule-6
coverage rather than create a new lock or authorize editing an existing one.
