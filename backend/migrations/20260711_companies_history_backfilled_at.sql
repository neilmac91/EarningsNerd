-- P1-6: deep filing-history backfill stamp. Marks when a company's 10-K/10-Q history (since 2001)
-- was backfilled from EFTS, so the on-visit enqueue backfills each company exactly once.
-- create_all() also adds this column on a fresh DB; _ADDITIVE_COLUMNS (app/database.py) self-heals
-- it at startup. Idempotent: safe to re-run forever.
BEGIN;
ALTER TABLE companies
  ADD COLUMN IF NOT EXISTS history_backfilled_at TIMESTAMPTZ;
COMMIT;
