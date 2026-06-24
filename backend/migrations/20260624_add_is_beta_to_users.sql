-- Closed-beta cohort flag on users, set server-side at invite redemption. Drives the 100%-off
-- promo at checkout (eligibility never depends on a client parameter).
-- NOTE: Base.metadata.create_all() (app startup) only creates MISSING TABLES — it does NOT ALTER
-- existing ones, so this column would not reach an existing prod `users` table on its own. The
-- startup runner (app/db_migrations.apply_pending_migrations) applies this file on deploy (Postgres);
-- it is idempotent and safe to re-run. Manual fallback:
--   psql "$DATABASE_URL" -f backend/migrations/20260624_add_is_beta_to_users.sql

BEGIN;

ALTER TABLE users ADD COLUMN IF NOT EXISTS is_beta BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_users_is_beta ON users (is_beta) WHERE is_beta = TRUE;

COMMIT;
