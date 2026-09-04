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
   `statement_timeout`, retries a bounded number of times, and on final failure prints
   `pg_stat_activity` so the blocker is visible from the CI log.
2. Every deploy job carries `timeout-minutes` well under GitHub's 360-minute default.
3. New migration files never issue a top-level `ALTER TABLE` on a pre-existing table. Wrap it in
   `DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM information_schema.columns …) THEN ALTER … END IF; END $$;`
   so re-application on every deploy is a true no-op that takes no table lock
   (pattern: `backend/migrations/20260705_summary_filing_id_unique.sql`).
4. "Idempotent" in rule 3 of CLAUDE.md means *re-runnable*, not *lock-free*. Treat every re-applied
   DDL statement as a lock acquisition on a live table.

Enforced by `backend/tests/unit/test_migration_lock_safety.py` (workflow knobs + a frozen,
shrink-only allow-list of the 17 legacy unguarded files).

## Evidence

- CI run 29524625738 / job 87710378965: step 7 "Apply database migrations" 18:40:23Z → 00:38:50Z
  (`cancelled`); steps 8–11 `skipped`. Log tail: `psql:backend/migrations/20260122_add_markdown_cache_columns.sql:7: server closed the connection unexpectedly`.
- `.github/workflows/ci.yml` migration step (PGOPTIONS + `apply_with_retry`), `deploy-backend.timeout-minutes`.
- `docs/ENGINEERING_AUDIT_2026-09.md` §1 for the full timeline and the production-drift list.
