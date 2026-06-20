-- P3 population: track which filings have been normalized into financial_fact, so the scheduled
-- backfill can run incrementally over just the newly-arrived filings. Additive, idempotent.
--
-- A new COLUMN on an existing table does NOT auto-add via Base.metadata.create_all(), so this
-- file is required for existing prod DBs (new envs get it from the model at startup).

BEGIN;

ALTER TABLE filings
  ADD COLUMN IF NOT EXISTS processed_facts_at TIMESTAMPTZ;

COMMIT;
