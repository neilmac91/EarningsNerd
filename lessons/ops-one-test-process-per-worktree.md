# One test process per worktree: never run pytest beside a running gate

Date: 2026-09-08 · Area: ops / verification

**Context.** The full local gate on a worktree reported one failure in a pre-existing facts
test (`facts_inserted` 4 instead of 2) that never reproduced alone, doubled, or in a verbose
re-run. The cause was the operator: while the gate was running, a "reproduce it alone" pytest
run was started in the same worktree, which deletes and rewrites the shared SQLite file
(`backend/earningsnerd.db`) the gate's process was still using. The gate counted the parallel
run's unstamped filings.

**Rule.** A worktree has one test process at a time. While its gate runs, do not start
pytest, mutation proofs, or a lens that runs tests in that worktree; use another worktree or
wait. A gate failure that a clean re-run cannot reproduce is first checked against this rule
before any test is called flaky or "fixed" by scoping.

**Evidence.** W3-9 gate on `457933fd` (1 failed / 2703 passed) versus the verbose re-run on
`70fca647` (2705 passed) with the worktree left alone; `tasks/todo.md` W3-9 section.

**Correction (2026-09-08, later the same day).** The parallel run was the trigger, not the whole
cause. The SQLite file outlives the test process, and `test_tickers_filter_scopes_the_pass`
(added in #763) deliberately leaves an unstamped marked filing behind; the unscoped idempotency
test then counts it on ANY later run in the same worktree — deterministic on the second run of
`test_facts_service.py`, fresh file or not. CI never saw it because CI runs one process on a
fresh file. Fixed by scoping the idempotency test to its own company (`tickers=[ticker]`), the
same seam the other backfill tests use. The rule above stands; the added rule: a test that
leaves state behind on purpose must not share an unscoped assertion with another test, and a
"passes alone, fails on re-run" result is checked by running the file twice on a fresh file
before any parallel-run explanation is accepted.
