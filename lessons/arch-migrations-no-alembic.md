# No Alembic: fresh schema via create_all, changes via idempotent SQL applied once through the migration_ledger table

Date: 2026-07-06 (ledger: 2026-09-04)   Area: arch

**Context**: Schema for a fresh DB comes from `Base.metadata.create_all()` at startup
(`backend/main.py` lifespan) plus `ensure_additive_columns`. Existing DBs change only via
hand-written SQL files in `backend/migrations/`. Until 2026-09 CI re-applied EVERY file on
EVERY deploy; that equated *idempotent* with *safe*, and the 2026-07-16 hang showed a
converged `ALTER TABLE … IF NOT EXISTS` still takes ACCESS EXCLUSIVE
(`ops-migrations-need-lock-timeout.md`). ADR-0007 replaced re-apply-all with a ledger:
`backend/scripts/apply_migrations.sh` records `(filename, sha256, applied_at)` in
`migration_ledger` and skips recorded files, so converged DDL never re-acquires a lock.

**Rule**: Any change to an existing table = a new SQL file in `backend/migrations/`
(date-prefixed name). It runs once per (filename, content) — but write it to be safe under
re-application anyway (`IF NOT EXISTS`, constraint-existence checks in `DO $$` blocks, UPDATEs
whose predicates no-op once converged): a ledger reset, an edited file (new hash → one
re-run), or a crash between apply and record all re-run it, and CI's `migrations-postgres`
job re-runs every file after `DELETE FROM migration_ledger`. Never edit an applied
migration — the one-shot re-apply is an escape hatch, not a workflow. Never apply migration
SQL outside the script (a hand `psql -f` bypasses the ledger); the gate that enforces this
covers `ci.yml` only — `ops.yml`'s manual psql steps are outside it and must call the script if
they ever apply migrations. New constraints also go in the
ORM (`__table_args__`) so create_all matches. Destructive steps (dedup deletes) must key on
provably-safe predicates and be order-independent w.r.t. sibling migrations.

**Evidence**: `backend/migrations/20260705_summary_filing_id_unique.sql` (dedup +
repoint + conditional constraint — the reference example); `backend/scripts/apply_migrations.sh`
(the only apply site; run by `deploy-backend` and by the `migrations-postgres` CI job's three
passes); `tests/unit/test_migration_lock_safety.py`; `docs/adr/0007-schema-migrations-ledger.md`;
ADR-0001.
