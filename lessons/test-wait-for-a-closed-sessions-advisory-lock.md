# Prove that a closed session freed its advisory lock by waiting for it, never with a probe that does not wait

Date: 2026-11-04 · Area: testing / PostgreSQL

**Context.** On 2026-11-04, `migrations-postgres` failed on #1990's head `e5046b2cb`, in a case that pull request
did not touch: `test_summary_job_transactions.py::test_recovery_session_excludes_other_caller_without_open_transaction`.
Its `pg_try_advisory_lock` probe, run right after the recovery owner's `release()`, returned False. `release()` closes
the owning session and returns at once (0.1 ms measured). PostgreSQL frees a session's advisory lock only when that
session's backend exits, which comes after the close, so on a busy runner the probe ran first.
`test_recovery_repeated_cancellation_cannot_cancel_queued_disconnect` probed the same way after its release. A
harness that held each released backend's exit for 300 ms found a third case:
`test_recovery_lock_timeout_closes_pass_without_queue_work` starts a second recovery pass right after the first one's
release and asserts that it ran, and that pass's own try-lock raced the exit. Production is unaffected: a recovery
pass that loses this race returns 0, as it does whenever another pass holds the lock, and the next scheduled pass
runs.

**Rule.**
1. A test that proves a closed session freed its advisory lock waits for the lock. It takes the lock with the
   blocking `pg_advisory_xact_lock`, under a statement timeout that bounds the wait and is not an elapsed
   assertion, so a lock left held fails the case at the timeout.
2. A probe that does not wait (`pg_try_advisory_lock`, or its `_xact` or `_shared` forms) is sound only while a live
   session holds the lock and the case asserts that the probe fails. Use the transaction-level form, so a probe that
   ever succeeds keeps nothing on a pooled connection.
3. The same race holds for the code under test's own non-blocking acquisition. After a close, wait for the lock
   before asserting that another owner's try-lock (`_RecoveryOwner.acquire()`, a recovery pass) succeeds.
4. A test thread that watches for a waiter reads `pg_locks` with `pg_blocking_pids`, in autocommit. A transaction
   keeps its first read of `pg_stat_activity` until it ends, so a watcher reading it would miss a waiter that
   connected after that read.

**Evidence.**
- The failure: [job 126317457344](https://github.com/neilmac91/EarningsNerd/actions/runs/41751512361/job/126317457344)
  (`assert False`). Its one re-run passed. The cause and the evidence are in comment 6620007610 on #1990.
- On a local PostgreSQL 16, with the owning backend paused (SIGSTOP) across `release()`, the non-blocking probe
  returned False, and a waiting probe took the lock once the backend exited.
- `tests/integration/test_summary_job_transactions.py`: `_wait_until_free` and `_assert_held_elsewhere`, and
  `recovery_guard`'s `late` mode. That mode runs every recovery case again, and keeps each released session that held
  the lock open, with its pool slot already free, until another session waits for the lock or the case ends. Each of
  the three racy forms fails there every time, and `test_late_mode_frees_a_released_lock_only_for_a_waiter` pins that
  the mode holds the lock. Its first watcher read `pg_stat_activity` in one transaction, and so missed a waiter on a
  connection opened after its first read. That failed one parallel run in five, until it read `pg_locks` in
  autocommit (rule 4).
- Gate: `backend/tests/unit/test_advisory_lock_probe_sites.py` holds every line under `backend/tests/` that names a
  probe, in code, a string or a comment, to an exact list by file and top-level definition, and requires each probe
  call to sit inside an `assert not`. Rules 1 and 3 are gated by the `late` mode for the recovery owner's cases, and
  review-checked elsewhere.
