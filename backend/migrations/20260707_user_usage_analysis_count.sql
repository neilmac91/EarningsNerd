-- Multi-Period Analysis (M2): monthly generation counter (fresh AI narratives only; cached
-- re-serves are never metered). Fair-use cap enforced via settings.ANALYSIS_MONTHLY_CAP.
-- Additive only, idempotent. Fresh DBs get the column via create_all; this file is for existing
-- prod DBs.

BEGIN;

ALTER TABLE user_usage ADD COLUMN IF NOT EXISTS analysis_count INTEGER NOT NULL DEFAULT 0;

COMMIT;
