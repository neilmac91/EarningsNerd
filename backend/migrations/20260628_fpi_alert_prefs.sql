-- FPI Phase 5: foreign-issuer alert opt-ins. Additive only, idempotent (safe to re-run).
--
-- New COLUMNS on an existing table do NOT auto-add via Base.metadata.create_all(), so this file is
-- required for prod. The DEFAULT clauses backfill existing rows in place (no separate UPDATE), and
-- match the model defaults: notify_20f ON (FPI annual, low-volume, like 10-K), notify_6k OFF (FPI
-- interim/furnished is frequent + heterogeneous → spam control; also forced digest-only in code).

BEGIN;

ALTER TABLE notification_preferences
  ADD COLUMN IF NOT EXISTS notify_20f BOOLEAN NOT NULL DEFAULT TRUE,
  ADD COLUMN IF NOT EXISTS notify_6k  BOOLEAN NOT NULL DEFAULT FALSE;

COMMIT;
