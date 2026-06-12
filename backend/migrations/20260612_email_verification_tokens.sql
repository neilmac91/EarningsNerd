-- Email Verification Token Columns
-- Date: 2026-06-12
-- Adds email_verification_token and email_verification_expires to users.
-- Run AFTER 20260612_auth_foundation.sql.
--
-- Run with: psql $DATABASE_URL -f migrations/20260612_email_verification_tokens.sql

BEGIN;

ALTER TABLE users
  ADD COLUMN IF NOT EXISTS email_verification_token   TEXT,
  ADD COLUMN IF NOT EXISTS email_verification_expires TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_users_email_verification_token
  ON users (email_verification_token)
  WHERE email_verification_token IS NOT NULL;

COMMIT;
