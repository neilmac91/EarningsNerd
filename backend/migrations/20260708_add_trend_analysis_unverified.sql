-- Adds the unresolved-citation counter to cached Multi-Period Analysis rows.
-- `unverified` = F# references the model emitted that did not resolve against the dataset
-- (surfaced in the "verified citations" badge tooltip). NULL on pre-existing rows; every
-- regeneration (all rows regenerate lazily after the trends-v2 prompt bump) backfills it.
--
-- Apply manually BEFORE deploying the code that writes the column (the repo convention:
-- schema is created at startup only for NEW tables; ALTERs are one-off and out-of-band —
-- never in the serving container's startup path):
--   psql "$DATABASE_URL" -f migrations/20260708_add_trend_analysis_unverified.sql

ALTER TABLE trend_analysis ADD COLUMN IF NOT EXISTS unverified INTEGER;
