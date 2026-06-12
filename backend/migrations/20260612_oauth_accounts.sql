-- OAuth Accounts Table
-- Date: 2026-06-12
-- Stores OAuth provider links per user. One user may have multiple providers
-- (Google, Apple) all pointing to the same users.id.
-- Run AFTER 20260612_auth_foundation.sql.
--
-- Run with: psql $DATABASE_URL -f migrations/20260612_oauth_accounts.sql

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS oauth_accounts (
  id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id             UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  provider            VARCHAR(20) NOT NULL,        -- 'google' | 'apple'
  provider_account_id TEXT        NOT NULL,        -- provider's 'sub' claim
  -- Email from provider; may be a private Apple relay address
  provider_email      TEXT,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (provider, provider_account_id)
);

CREATE INDEX IF NOT EXISTS idx_oauth_accounts_user_id
  ON oauth_accounts (user_id);

-- Partial index: find by provider+email quickly (used during account linking)
CREATE INDEX IF NOT EXISTS idx_oauth_accounts_provider_email
  ON oauth_accounts (provider, provider_email)
  WHERE provider_email IS NOT NULL;

COMMIT;
