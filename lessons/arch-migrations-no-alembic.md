# No Alembic: fresh schema via create_all, changes via idempotent SQL re-applied on EVERY deploy

Date: 2026-07-06   Area: arch

**Context**: Schema for a fresh DB comes from `Base.metadata.create_all()` at startup
(`backend/main.py` lifespan) plus `ensure_additive_columns`. Existing DBs change only via
hand-written SQL files in `backend/migrations/`, and CI re-applies EVERY file on EVERY
deploy — so a migration is never "done"; it runs forever.

**Rule**: Any change to an existing table = a new SQL file in `backend/migrations/`
(date-prefixed name), written to be safe under infinite re-application (`IF NOT EXISTS`,
constraint-existence checks in `DO $$` blocks, UPDATEs whose predicates no-op once
converged). Never edit an applied migration. New constraints also go in the ORM
(`__table_args__`) so create_all matches. Destructive steps (dedup deletes) must key on
provably-safe predicates and be order-independent w.r.t. sibling migrations.

**Evidence**: `backend/migrations/20260705_summary_filing_id_unique.sql` (dedup +
repoint + conditional constraint — the reference example); CI deploy step applies all
`backend/migrations/*.sql`; ADR-0001.
