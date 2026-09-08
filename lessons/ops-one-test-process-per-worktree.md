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
