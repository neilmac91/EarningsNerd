-- Lifetime Copilot "free taste" counter on users (roadmap 2.2): a Free user gets a small lifetime
-- allowance of grounded "Ask this Filing" questions before the upsell. Lives on `users` (lifetime,
-- one row per user) rather than `user_usage` (which is monthly). Pro is unlimited via entitlements
-- and never touches this counter.
--
-- IMPORTANT — apply this to prod MANUALLY *before* deploying the code that ships
-- User.copilot_free_taste_used. Base.metadata.create_all() (app startup) only creates MISSING
-- TABLES; it does NOT ALTER the existing `users` table, so this column won't reach prod on deploy.
-- Apply out-of-band (psql waits for the ACCESS EXCLUSIVE lock instead of failing a rolling deploy's
-- healthcheck):
--   gcloud sql connect earningsnerd-db --user=<dbuser>   then run the statements below
--   (or)  psql "$DATABASE_URL" -f backend/migrations/20260629_user_copilot_free_taste.sql
-- Additive only, idempotent (safe to re-run).

BEGIN;

ALTER TABLE users
  ADD COLUMN IF NOT EXISTS copilot_free_taste_used INTEGER NOT NULL DEFAULT 0;

COMMIT;
