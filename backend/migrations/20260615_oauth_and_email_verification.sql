-- OAuth accounts + email verification + password reset (additive)
-- Date: 2026-06-15
--
-- Builds on the existing INTEGER users.id schema (no id migration). Adds the columns
-- and table needed for Google/Apple sign-in, email verification, and password reset.
-- Schema is also created at startup by Base.metadata.create_all(); this file lets the
-- changes be applied to an existing database. Idempotent.
--
-- Run with: psql $DATABASE_URL -f migrations/20260615_oauth_and_email_verification.sql

BEGIN;

-- 1. Email verification + password reset columns on users (store SHA-256 hashes only)
ALTER TABLE users
  ADD COLUMN IF NOT EXISTS email_verified              BOOLEAN     NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS email_verification_token    TEXT,
  ADD COLUMN IF NOT EXISTS email_verification_expires  TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS password_reset_token        TEXT,
  ADD COLUMN IF NOT EXISTS password_reset_expires      TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS last_login_at               TIMESTAMPTZ;

-- 2. Social-only accounts (Google/Apple) have no password
ALTER TABLE users ALTER COLUMN hashed_password DROP NOT NULL;

-- 3. Fast single-use token lookups
CREATE INDEX IF NOT EXISTS idx_users_email_verification_token
  ON users (email_verification_token)
  WHERE email_verification_token IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_users_password_reset_token
  ON users (password_reset_token)
  WHERE password_reset_token IS NOT NULL;

-- 4. OAuth provider links (one user may link Google + Apple). INTEGER FK to users.id.
CREATE TABLE IF NOT EXISTS oauth_accounts (
    id                  SERIAL      PRIMARY KEY,
    user_id             INTEGER     NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    provider            VARCHAR(20) NOT NULL,        -- 'google' | 'apple'
    provider_account_id TEXT        NOT NULL,        -- provider's 'sub' claim
    provider_email      TEXT,                        -- may be an Apple private relay address
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (provider, provider_account_id)
);

CREATE INDEX IF NOT EXISTS idx_oauth_accounts_user_id ON oauth_accounts (user_id);

COMMIT;
