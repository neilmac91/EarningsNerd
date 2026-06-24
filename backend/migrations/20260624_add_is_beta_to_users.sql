-- Closed-beta cohort flag on users, set server-side at invite redemption. Drives the 100%-off
-- promo at checkout (eligibility never depends on a client parameter).
-- IMPORTANT — apply this to prod MANUALLY *before* deploying the code that ships User.is_beta.
-- Base.metadata.create_all() (app startup) only creates MISSING TABLES; it does NOT ALTER existing
-- ones, so this column will not reach the existing prod `users` table on deploy. (An earlier attempt
-- to auto-apply migrations inside app startup was reverted: ADD COLUMN needs an ACCESS EXCLUSIVE lock
-- that contends with the still-serving old revision during a Cloud Run rolling deploy and fails the
-- new revision's healthcheck. Apply out-of-band instead — psql waits patiently for the lock.)
-- Idempotent — safe to re-run.
-- Apply:  gcloud sql connect earningsnerd-db --user=<dbuser>   then run the statements below
--   (or)  psql "$DATABASE_URL" -f backend/migrations/20260624_add_is_beta_to_users.sql

BEGIN;

ALTER TABLE users ADD COLUMN IF NOT EXISTS is_beta BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_users_is_beta ON users (is_beta) WHERE is_beta = TRUE;

COMMIT;
