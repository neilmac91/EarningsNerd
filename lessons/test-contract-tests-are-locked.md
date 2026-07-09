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
