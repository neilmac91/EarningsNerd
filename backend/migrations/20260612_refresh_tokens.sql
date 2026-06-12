-- Refresh Token Columns
-- Date: 2026-06-12
-- Adds refresh_token and refresh_token_expires to users.
-- Run AFTER 20260612_auth_foundation.sql.
--
-- Run with: psql $DATABASE_URL -f migrations/20260612_refresh_tokens.sql

BEGIN;

ALTER TABLE users
  ADD COLUMN IF NOT EXISTS refresh_token         TEXT,
  ADD COLUMN IF NOT EXISTS refresh_token_expires TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_users_refresh_token
  ON users (refresh_token)
  WHERE refresh_token IS NOT NULL;

COMMIT;
