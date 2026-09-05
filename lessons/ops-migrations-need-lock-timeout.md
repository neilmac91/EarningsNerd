# Give every migration session a lock_timeout and every deploy job a timeout — idempotent is not lock-free

**Date:** 2026-09-04 · **Area:** ops / migrations / CI

## Context

The 2026-07-16 release (PR #634) passed every test, built and pushed its image, then hung in
`deploy-backend` → "Apply database migrations" for six hours until GitHub's default job timeout
cancelled it. The Cloud Run deploy, all job-image updates and the health check were skipped, and
production ran a 7-week-old backend without anyone noticing. The job log shows `psql` parked at
`backend/migrations/20260122_add_markdown_cache_columns.sql:7` — an
`ALTER TABLE filing_content_cache ADD COLUMN IF NOT EXISTS …` whose columns had existed since
January. PostgreSQL acquires ACCESS EXCLUSIVE on the table *before* it evaluates `IF NOT EXISTS`,
so a converged, "safe to re-run" statement still waits behind any open transaction that has merely
read the table — and, while it waits, every new reader of that hot table queues behind it. There
was no `lock_timeout`, no `statement_timeout`, and no `timeout-minutes` on the job.

## Rule

1. Every psql session that applies migrations sets `lock_timeout` (seconds, not minutes) and
   `statement_timeout`, retries a bounded number of times **only** on the contention SQLSTATEs
   (`55P03`, `57014`, `40P01` — read from psql stderr under `VERBOSITY=verbose`; a syntax or
   permission error is final), and on final failure prints `pg_stat_activity` (unfiltered — other
   roles' rows are NULL without `pg_read_all_stats`) plus a `pg_locks ⨝ pg_class` dump so the
   blocker and the relation are visible from the CI log. Every other workflow step that reaches
   Cloud SQL (`ops.yml`) sets the same `lock_timeout`; its `statement_timeout` is scoped per step
   (write path 120 s, read-only snapshots 600 s).
2. Every deploy job carries `timeout-minutes` well under GitHub's 360-minute default.
3. New migration files never issue a top-level `ALTER TABLE` on a pre-existing table. Wrap it in
   `DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM information_schema.columns …) THEN ALTER … END IF; END $$;`
   so any re-application (ledger reset, edited file, CI's triple pass) is a true no-op that takes no
   table lock (pattern: `backend/migrations/20260705_summary_filing_id_unique.sql`).
4. "Idempotent" in rule 3 of CLAUDE.md means *re-runnable*, not *lock-free*. Treat every DDL
   statement as a lock acquisition on a live table. Since ADR-0007 the `migration_ledger` table
   (`backend/scripts/apply_migrations.sh`) stops converged files from being re-executed on a deploy
   at all — the durable fix for this incident class.
5. Plain `CREATE [UNIQUE] INDEX IF NOT EXISTS` on a pre-existing table is the same trap in a
   smaller lock (SHARE, taken before the existence check). New files use the same `DO $$` catalog
   guard (`pg_indexes`) or `CREATE INDEX CONCURRENTLY` outside a transaction block.
   CONCURRENTLY has its own failure mode: a build cancelled by `statement_timeout` (57014, the
   retryable class) leaves the index behind marked INVALID, the retry's `IF NOT EXISTS` sees the
   relation and skips with a NOTICE, and the ledger records the file — so the script ends every run
   with `SELECT … FROM pg_index WHERE NOT indisvalid` and exits 1 on any hit (remedy in its output:
   `DROP INDEX CONCURRENTLY`, then delete the file's `migration_ledger` row).

Enforced by `backend/tests/unit/test_migration_lock_safety.py` (job knobs and proxy checksum pin in
`ci.yml`; PGOPTIONS, SQLSTATE-only retry, the blocker dump and the INVALID-index exit in `backend/scripts/apply_migrations.sh`,
the only place migration SQL runs; `ops.yml` dispatch-only + per-step `PGOPTIONS`; the real-Postgres
triple-apply job; and two frozen, shrink-only allow-lists: the 17 legacy unguarded-ALTER files and
the 7 legacy unguarded-index files).

## Evidence

- CI run 29524625738 / job 87710378965: step 7 "Apply database migrations" 18:40:23Z → 00:38:50Z
  (`cancelled`); steps 8–11 `skipped`. Log tail: `psql:backend/migrations/20260122_add_markdown_cache_columns.sql:7: server closed the connection unexpectedly`.
- `backend/scripts/apply_migrations.sh` (PGOPTIONS + `apply_with_retry` + `dump_blockers`; run by the
  `ci.yml` "Apply database migrations" step and by the `migrations-postgres` job),
  `deploy-backend.timeout-minutes`. `ops.yml`'s psql steps run ops SQL, never migration files, so they
  are outside that script and the ledger; each sets its own `PGOPTIONS` (lock_timeout=10s; statement
  budget per step).
- `docs/ENGINEERING_AUDIT_2026-09.md` §1 for the full timeline and the production-drift list.
