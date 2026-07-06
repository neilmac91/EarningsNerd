-- Multi-Period Analysis (M1): stamp when a company's SEC companyfacts history was last ingested
-- into financial_fact (24h TTL + newer-filing override drive re-syncs). Additive only, idempotent.
-- Fresh DBs get the column via create_all; this file is for existing prod DBs.

BEGIN;

ALTER TABLE companies ADD COLUMN IF NOT EXISTS facts_synced_at TIMESTAMPTZ;

COMMIT;
