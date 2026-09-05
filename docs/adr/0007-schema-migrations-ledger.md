# ADR 0007 — Track applied SQL migrations in a `migration_ledger` table

- **Status:** Accepted
- **Deciders:** EarningsNerd maintainers
- **Supersedes:** the "re-applied on EVERY deploy" rule (CLAUDE.md rule 3,
  `lessons/arch-migrations-no-alembic.md`, `docs/DEPLOYMENT.md`) — a rule, not a prior ADR.
  The no-Alembic decision itself stands.

## Context

There is no Alembic (deliberate — a solo project with a small schema). A fresh database gets its
schema from `Base.metadata.create_all()` at startup; every change to an existing table is a
hand-written, idempotent SQL file in `backend/migrations/` (32 files as of this ADR). Until now the
`deploy-backend` job ran **every** file on **every** deploy, and the rule was simply "every file
must stay safe to re-run forever".

That rule equated *idempotent* with *safe*, and the 2026-07-16 release showed they are not the same
(`lessons/ops-migrations-need-lock-timeout.md`): a converged
`ALTER TABLE … ADD COLUMN IF NOT EXISTS` still takes ACCESS EXCLUSIVE before it evaluates
`IF NOT EXISTS`, queued behind one open transaction, and held the deploy for six hours. PR #653
made that failure fast and diagnosable (`lock_timeout`, retries, blocker dump) but every deploy
still re-acquired locks it did not need: 17 legacy files with top-level ALTERs, ~43
`CREATE INDEX IF NOT EXISTS` statements (SHARE lock before the existence check), and a correlated
`UPDATE financial_fact` that re-scans the table against a 120 s statement budget.

Two designs were weighed (audit appendix `docs/audit-2026-09/01-deploy-pipeline.md` §5b, decision
D1 in the September 2026 briefs):

- **(a) Guard-only** — keep re-applying everything and require the `DO $$ … IF NOT EXISTS (SELECT …)`
  wrapper for new files. Simple, but the 17 legacy files and ~43 index statements keep taking locks
  on every deploy unless they are rewritten.
- **(b) Ledger** — record what has been applied and skip it.

## Decision

**(b).** A ledger table

```sql
CREATE TABLE IF NOT EXISTS migration_ledger (
    filename   TEXT PRIMARY KEY,
    sha256     TEXT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

(named `schema_migrations` when this ADR was accepted — see the 2026-09-05 amendment below)
owned and created by the deploy step itself — `backend/scripts/apply_migrations.sh` — never by
`create_all` and never in the serving container (`lessons/ops-no-ddl-in-startup-path.md`).

For each `backend/migrations/*.sql` in byte-order filename order the script computes the file's
sha256, **skips** it when `(filename, sha256)` is recorded, otherwise applies it under the existing
`lock_timeout=10s` / `statement_timeout=120s` + bounded-retry session and then records it with
`INSERT … ON CONFLICT (filename) DO UPDATE SET sha256 = EXCLUDED.sha256, applied_at = now()`.

- **Seeding.** The first run against the production database applies all existing files once (they
  are idempotent) and records them. Nothing is pre-inserted by hand.
- **Edited files.** A file whose content changes gets a new hash and re-applies exactly once. That is
  the *escape hatch* (e.g. a hand-fix that must reach prod through CI), not a workflow: "never edit
  an applied migration" still stands. The other escape hatch is
  `DELETE FROM migration_ledger WHERE filename = '…'` to force one re-run.
- **One script, two callers.** `deploy-backend` (through `cloud-sql-proxy`) and the new
  `migrations-postgres` CI job run the identical file — no duplicated bash. The CI job seeds a
  `postgres:15` service with `create_all`, then runs the script three times: pass 1 must apply every
  file, pass 2 must apply zero (ledger skip), pass 3 after `DELETE FROM migration_ledger` must
  apply every file again (files stay re-runnable). `deploy-backend` depends on it, so a migration
  that fails on real Postgres blocks the release instead of being discovered in the deploy step.
- **Rule 3 wording** becomes: each file is applied once per (filename, content) by the ledger, but
  must still be idempotent — the ledger-reset, edited-file and crashed-between-apply-and-record
  paths all re-run it. The DO-block guard for new ALTERs on existing tables
  (`tests/unit/test_migration_lock_safety.py`) remains: a *first* application on prod takes the
  lock regardless, and the guard keeps re-runs lock-free.

## Consequences

**Positive**
- Converged DDL is never re-executed, so a deploy's migration step acquires locks only for the
  files it actually introduces. The 2026-07-16 failure mode (a converged statement waiting on a
  reader) cannot recur for recorded files.
- The migration step is O(new files); the 120 s `UPDATE financial_fact` runs once.
- Every migration is now exercised against real PostgreSQL 15 on every PR (CI was SQLite-only for
  the schema path before; see `lessons/ops-no-ddl-in-startup-path.md` on why that is "untested").
- No new runtime dependency: the ledger is plain SQL + `psql` + `sha256sum`.

**Negative / costs**
- Apply and record are two statements, not one transaction (some files manage their own
  `BEGIN`/`COMMIT`, and a future `CREATE INDEX CONCURRENTLY` cannot run inside one). A crash between
  them re-applies the file next deploy — acceptable only because files stay idempotent, which is
  why CI pass 3 exists.
- The ledger is deploy-owned state that `create_all` knows nothing about. A developer's local
  Postgres gets the table the first time they run the script; SQLite dev databases never have it
  (the script is Postgres-only, as the migrations always were).
- Any out-of-band way of applying migrations (a hand `psql -f`, an `ops.yml` step) bypasses the
  ledger and must go through the script instead. The "only the script applies SQL" gate in
  `test_migration_lock_safety.py` inspects `ci.yml` only; `.github/workflows/ops.yml` (manual
  operations, its own psql sessions running ops SQL) is deliberately outside it — each of its Cloud
  SQL steps sets its own `PGOPTIONS` (`lock_timeout=10s`, statement budget per step), and any future
  migration-applying step there must call this script rather than `psql -f` a migration file.
- Still no down-migrations and no dependency graph between files — unchanged from before.

## Amendment 2026-09-05 — the table is `migration_ledger`, not `schema_migrations`

The first ledger deploy (CI run 33941732087, main `c6eaddf`) failed in the migration step with
`column "sha256" does not exist`: production already had a `schema_migrations` table — created
outside this repository (no commit ever referenced the name before this ADR), with a different
shape — and `CREATE TABLE IF NOT EXISTS` adopted it silently. The `migrations-postgres` CI job
could not catch this because its database is fresh.

- The ledger is renamed to `migration_ledger` (script, CI, tests, docs). The legacy prod
  `schema_migrations` table is left untouched for the founder to inspect and drop.
- The CI job now plants a decoy `schema_migrations (version TEXT PRIMARY KEY, …)` before pass 1, so
  every pass proves the script never reads or writes the legacy name (rule 12: the incident is a
  gate, not a comment). `test_migration_lock_safety.py` pins both the decoy step and the absence of
  `schema_migrations` from the script's executable lines.
- Lesson: `CREATE TABLE IF NOT EXISTS` for state the deploy owns is only safe under a name nothing
  else could plausibly have created; a conventional name is a collision waiting to happen.

## When to revisit

Adopt a real migration tool (Alembic) via a superseding ADR if any of: files need explicit
dependency ordering beyond filename sort, down-migrations become a requirement, or more than one
person is writing schema changes concurrently.
