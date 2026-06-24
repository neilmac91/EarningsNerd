-- Optional cohort label on invite_codes for grouping invites (e.g. a launch wave or partner batch).
-- Schema is also created at startup by Base.metadata.create_all(); this migration keeps an existing
-- production database in sync. Base.metadata.create_all() only creates MISSING TABLES, never ALTERs
-- existing ones, so apply this out-of-band before deploying the code that ships InviteCode.cohort.
-- Idempotent — safe to re-run.
-- Apply:  psql "$DATABASE_URL" -f backend/migrations/20260624_add_cohort_to_invite_codes.sql

BEGIN;

ALTER TABLE invite_codes ADD COLUMN IF NOT EXISTS cohort VARCHAR(64);

CREATE INDEX IF NOT EXISTS ix_invite_codes_cohort ON invite_codes (cohort);

COMMIT;
