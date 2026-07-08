-- Summary version stamps: record the schema (sections taxonomy) and prompt version each cached
-- Summary was generated under, so a serializer / prompt / schema change can IDENTIFY and refresh
-- stale rows instead of stranding pre-change `business_overview`. This is the gap behind the
-- shipped-but-unseen ".;" fix (P0-2): summaries are rendered at generation time and stored, and
-- carried no version stamp, so a merged serializer fix never reached already-generated rows.
-- Mirrors the trend_analysis prompt_version pattern (trend_analysis_service.PROMPT_VERSION).
--
-- NULL = legacy / pre-stamp = always treated as stale (regenerable via the admin refresh-stale
-- endpoint and the background drain). Additive + nullable, so safe on a populated table.
--
-- Idempotent + safe to re-apply every deploy (CI re-runs all migrations). Fresh DBs get these
-- columns from Summary's ORM columns via create_all; existing DBs also self-heal at startup via
-- database.ensure_additive_columns (_ADDITIVE_COLUMNS), so the columns exist before this file runs.

BEGIN;

ALTER TABLE summaries ADD COLUMN IF NOT EXISTS schema_version SMALLINT;
ALTER TABLE summaries ADD COLUMN IF NOT EXISTS prompt_version TEXT;

COMMIT;
