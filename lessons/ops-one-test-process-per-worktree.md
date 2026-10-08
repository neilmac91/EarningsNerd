# Each test process owns its database; a test must never depend on another test's leftovers

Date: 2026-09-08 (rule revised 2026-10-09) · Area: ops / verification

**Context.** The full local gate on a worktree reported one failure in a pre-existing facts
test (`facts_inserted` 4 instead of 2) that never reproduced alone, doubled, or in a verbose
re-run. The cause was the operator: while the gate was running, a "reproduce it alone" pytest
run was started in the same worktree, which deletes and rewrites the shared SQLite file
(`backend/earningsnerd.db`) the gate's process was still using. The gate counted the parallel
run's unstamped filings.

**Correction (2026-09-08, later the same day).** The parallel run was the trigger, not the whole
cause. The SQLite file outlives the test process, and `test_tickers_filter_scopes_the_pass`
(added in #763) deliberately leaves an unstamped marked filing behind; the unscoped idempotency
test then counts it on ANY later run in the same worktree — deterministic on the second run of
`test_facts_service.py`, fresh file or not. CI never saw it because CI runs one process on a
fresh file. Fixed by scoping the idempotency test to its own company (`tickers=[ticker]`), the
same seam the other backfill tests use.

**Revision (2026-10-09).** The gate now runs in parallel (`-n auto` in `backend/pytest.ini`), and
`backend/tests/conftest.py` gives every pytest process (the session, or each pytest-xdist worker) a
private SQLite file in a fresh temp directory, created before any app import and removed at exit.
No test opens `backend/earningsnerd.db`, and two pytest runs in one worktree no longer share a file.
The same conftest gives SQLite tables AUTOINCREMENT ids, because SQLite otherwise re-issues a deleted
test's id and the next test's new row inherits the orphaned child rows (SQLite here enforces no
foreign keys). The random-order hunt that preceded the switch also found a test that re-patched a
`stream_boundaries` seam with the function-scoped `monkeypatch`, which re-installed the harness mock
on a shared singleton for the rest of the process.

**Rule.** A worktree may run more than one pytest process; each owns its database. Within a
process, tests still share that database and every module-level global, in whatever order xdist
and pytest-randomly produce. So a test must not depend on another test's order or leftovers: scope
its assertions to its own rows, undo every override it makes before the context it overrides
exits (`monkeypatch.context()` inside `stream_boundaries`), and reset process-wide state in a
conftest autouse fixture. A "passes alone, fails in the suite" result is reproduced first by
running the suspect leaker and the victim in that order in one process
(`python -m pytest -n 0 -p no:randomly <leaker> <victim>`), never accepted as a flake. Do not
edit a checkout while a run reads it (`test-leave-the-tree-alone-during-a-background-suite.md`).

**Enforcement.** `backend/tests/unit/test_suite_database_isolation.py` fails if the suite database
is not a private per-process temp file or if SQLite re-issues a deleted id. CI's backend step runs
the same parallel `python -m pytest`, so every PR exercises a different test-to-worker split.

**Evidence.** W3-9 gate on `457933fd` (1 failed / 2703 passed) versus the verbose re-run on
`70fca647` (2705 passed) with the worktree left alone; `tasks/todo.md` W3-9 section. The
2026-10-09 parallel switch, its random-order runs and wall-clock figures are in the Lane C PR body.
