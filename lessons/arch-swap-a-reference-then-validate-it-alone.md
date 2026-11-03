# Replace a foreign key in one statement and validate it in another: a DO block holds every lock it takes until it ends

Date: 2026-11-02 (PB-02, #1955)   Area: arch / migrations

**Context**: PB-02's `20261102_trend_analysis_creator_set_null.sql` first replaced `trend_analysis.created_by_user_id`'s
reference to `users` in one `DO` block: drop the old reference, add the `SET NULL` one `NOT VALID`, then `VALIDATE`. Its
comment said the lock on `users` lasted only for the catalog change. The chief's review and PB-05's trial found it did
not: a `DO` block is one statement, so it holds every lock it takes until it ends, and dropping a foreign key takes
ACCESS EXCLUSIVE on the table it references as well as on its own (the reference's triggers are on both). For a
reference to `users`, every signed-in request queues behind the drop while it waits for that lock, and the validation's
scan ran under it too. Measured on PostgreSQL 16.15 from a second session: the swap stops every read and write of both
tables; the validation, in a statement of its own, holds SHARE UPDATE EXCLUSIVE on the table and ROW SHARE on the one it
references, which stop none.

**Rule**:
- Replace a reference in one statement (drop the old one, add the new one `NOT VALID`: catalog only) and validate it in
  a statement of its own; a catalog guard bounds what a block runs, never how long its locks last.
- Give a file that locks a hot table a `lock_timeout` of a few seconds (`SET lock_timeout = '2s'`, then `RESET`). It
  bounds each wait to acquire a lock, so a blocked try holds the queries queued behind it for at most that long; it does
  not bound how long a statement runs or holds a lock once it has it.
- Read each statement's locks from PostgreSQL, not from memory: run it in an open transaction, read `pg_locks`, and
  probe the tables from a second session with a short `lock_timeout`.

**Gate** (partly): `backend/tests/integration/test_subscription_event_transactions.py::test_postgres_each_pb02_migration_statement_holds_only_the_locks_its_comments_name`
holds PB-02's two files on CI's PostgreSQL (each statement's locks, the second session's probes, the 2 s wait, and that
`apply_migrations.sh` runs psql outside a transaction block). Another file that swaps a reference is review-checked.

**Evidence**: the chief's review of `fef3056` on #1955 (item 2) and PB-05's trial on #1954; `812523b` split the file;
mutation proof M12 (the validation back in the swap's statement fails the case); `lessons/ops-migrations-need-lock-timeout.md`
for the session's own timeouts.
