# Give each test process its own database, and never let a test depend on another test's order or leftovers

Date: 2026-09-08 (rule revised 2026-10-09, 2026-10-11) · Area: ops / verification

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
The random-order runs before the switch (pytest-randomly, serial and `-n 4`, several seeds) found
eight cross-test dependencies, each fixed at the root:
- Files that wrote through `SessionLocal` without creating tables relied on an earlier test (or an
  earlier `TestClient` lifespan) having run `create_all`; conftest now creates the schema per process.
- SQLite re-issued a deleted test's id, and the next test's new filing inherited an orphaned
  `filing_content_cache` row (SQLite here enforces no foreign keys); conftest now gives SQLite tables
  AUTOINCREMENT ids, as PostgreSQL sequences behave.
- A test re-patched a `stream_boundaries` seam with the function-scoped `monkeypatch`, whose teardown
  re-installed the harness mock on a shared singleton for the rest of the process.
- The pipeline finalizes the harness's module-level `CANONICAL_PAYLOAD` in place, so later
  generations started from an earlier test's output; conftest now restores it after each test.
- A 40 ms real provider budget raced the first heartbeat under parallel load; the test now arms the
  budget after the stream opens, as its sibling case already did.
- `test_admin_feedback.py` inserted reporter users 501/502 only when the id was free, so a user
  another test had auto-created with that id became the reporter; reporters now get assigned ids.
- A process's first OpenAI SDK request costs ~60 ms (later ones ~2 ms), so whichever test made it
  paid that inside its own real-time budget (an 80 ms copilot caller deadline failed 7 of 8 cold
  runs under load); conftest now makes one offline plain and one streamed request per process
  before any test.
- A shared-deadline test's 40 ms budget left 15 ms of slack and failed under load even when warm;
  it now expires the shared deadline while the recovery request is in flight.

**Ninth dependency (2026-10-11).** A test helper built `Company.ticker` from 4 uuid hex chars
(65,536 values) while the worker's database kept every company its earlier tests had created, and
`backfill_facts` scopes a pass by `Company.ticker IN (...)`: a leftover company with the same ticker
and an unprocessed XBRL filing was processed too (`filings_processed` 2 instead of 1 in
`test_tickers_filter_scopes_the_pass`, once on #1234 at `0bc0a354`, green on the next identical
push, never reproducible alone). Every ticker and cohort key that a query filters on now carries the
full 8-hex slice the helper already held (`test_facts_service.py`, `test_peers_service.py`); keys
that are only stored and never looked up, and patterns created once per worker run, were left alone.

**First week on the parallel gate (2026-10-15).** CI completed about 886 parallel pytest steps between
2026-10-10 and 2026-10-15, with 9 flaky failures (about 1%). A query on failed runs finds only four of
the nine: four more show up only as attempt 1 of a run a re-run turned green, and one sits in a run
that was cancelled after backend-tests failed. Each was a race
(against the wall clock, or a signal against a syscall) or a shared-state leak. #1213, #1239, #1244, #1276 and #1236 fixed six. Three were still
open on main:
- The admission test asserted elapsed < 1.2 s and ran 1.22 s.
- The charge-write test's 0.6 s pipeline deadline expired during a 0.53 s mocked fetch, so no write
  began.
- A process-group test's grandchild caught SIGTERM in a Python handler and, about once in a thousand
  runs under load, missed it for its whole 60 s sleep (`test-child-scripts-wait-for-signals.md`).
A sweep found four more asserts that held only on an idle loop. Each now asserts on the deadline the
code enters, or on what the code did, not on how long it took, and `tests/unit/test_wall_clock_bounds.py`
fails on a new one.

**Rule.** A worktree may run more than one pytest process; each owns its database. Within a process,
tests still share that database and every module-level global, in whatever order xdist produces (and
pytest-randomly, when installed locally for a hunt). So a test must not depend on another test's
order or leftovers: scope its assertions to its own rows, undo every override it makes before the
context it overrides exits (`monkeypatch.context()` inside `stream_boundaries`), and reset
process-wide state in a conftest autouse fixture. A key that the test or the code it calls filters
on (a ticker, a cohort code, a filing type) is built from the full uuid slice the helper holds
(8+ hex), never a 3-5 char sub-slice: rows accumulate per worker, so a lookup on a 65,536-value key
eventually matches another test's row, and the failure looks like a flake because it needs a
particular test-to-worker split. A real-time budget in a test must not race a
wall-clock margin: arm or expire the deadline once the operation under test is under way, by
rescheduling the real `asyncio.timeout` it entered, as the provider-lifecycle and shared-deadline
tests do. Check the outcome on the deadline itself, never on elapsed time against a bound. Record
the timeout the code enters (a `SimpleNamespace` proxy over the module's `asyncio`) and compare its
`when()` with the deadline the call fixed, or assert which timeout `expired()`. Every remaining
wait in the test is a generous hang guard. A "passes alone, fails in the suite" result is reproduced first by running the suspect
leaker and the victim in that order in one process (`python -m pytest -n 0 -p no:randomly <leaker>
<victim>`), never accepted as a flake. Do not edit a checkout while a run reads it
(`test-leave-the-tree-alone-during-a-background-suite.md`).

**Enforcement.** `backend/tests/unit/test_suite_isolation.py` fails if:
- the suite database is not a private per-process temp file, including when a developer's
  `DATABASE_URL` is set;
- EdgarTools writes outside that directory;
- a fresh process lacks the schema before its first test, or its SDK is cold;
- SQLite re-issues a deleted id;
- a mock is left on the generation singletons, or the guard does not put the real one back;
- a conftest reset stops holding: the canonical payload, the summary limiter, the delivery and lease
  rows, the `ai_metrics` trigger, or a service method left pinned on its singleton.
  `monkeypatch.setattr` on an instance saves the old attribute with `getattr`, a bound method, and
  its undo sets that back on the instance, where it shadows any later class-level patch. Tests reach
  those singletons through `app.services.edgar.compat` without importing `summary_pipeline`, so the
  guard finds them where they live;
- `_offline_stream_enrichment` stubs any file but its listed three, or the temp directory of any
  process (the xdist controller and each worker included) outlives its run.

It runs the probe pairs in a fixed order in a fresh serial process, because `-n auto` and random
order can split or reverse a definition-order pair. A `test_probe_*` or `test_isolation_*` function
outside that order fails it. `backend/tests/unit/test_wall_clock_bounds.py` fails on an assert that
requires elapsed time to stay under a bound, except for the listed guards whose bound is many times
what they measure. CI's backend step runs the same parallel `python -m pytest`, so every PR exercises
a different test-to-worker split.

**Evidence.** W3-9 gate on `457933fd` (1 failed / 2703 passed) versus the verbose re-run on
`70fca647` (2705 passed) with the worktree left alone; `tasks/archive/todo-ledger-through-2026-10-07.md` W3-9 section. The
2026-10-09 parallel switch, its random-order runs and wall-clock figures are in the PR body of
https://github.com/neilmac91/EarningsNerd/pull/1135. The 4-hex ticker collision: CI on
https://github.com/neilmac91/EarningsNerd/pull/1234 at `0bc0a354` (`assert (2 == 1)`), reproduced
deterministically by patching `uuid.uuid4` to share a 4-hex prefix, and gone with the full slice.
