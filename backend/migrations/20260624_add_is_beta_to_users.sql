-- Closed-beta cohort flag on users, set server-side at invite redemption. Drives the 100%-off
-- promo at checkout (eligibility never depends on a client parameter).
-- IMPORTANT: Base.metadata.create_all() (app startup) only creates MISSING TABLES — it does NOT
-- ALTER existing ones. So this column will NOT appear on the existing prod `users` table on deploy;
-- it MUST be applied to prod BEFORE (or with) the backend deploy that ships User.is_beta, or every
-- user query (which now SELECTs is_beta) will error. Idempotent — safe to re-run.
-- Apply:  psql "$DATABASE_URL" -f backend/migrations/20260624_add_is_beta_to_users.sql

BEGIN;

ALTER TABLE users ADD COLUMN IF NOT EXISTS is_beta BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_users_is_beta ON users (is_beta) WHERE is_beta = TRUE;

COMMIT;
