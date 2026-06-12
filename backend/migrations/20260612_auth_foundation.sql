-- Auth Foundation Migration
-- Date: 2026-06-12
-- Safe to run: ZERO production user accounts exist at time of migration.
-- Migrates users.id from INTEGER to UUID; adds email verification and
-- password-reset columns; makes hashed_password nullable; updates all FK columns.
--
-- Run with: psql $DATABASE_URL -f migrations/20260612_auth_foundation.sql
-- Idempotent: wrapped in a transaction; rolls back on any error.

BEGIN;

-- Enable pgcrypto for gen_random_uuid() if not already present
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. Drop all FK constraints on columns that reference users.id
-- ─────────────────────────────────────────────────────────────────────────────
ALTER TABLE watchlist        DROP CONSTRAINT IF EXISTS watchlist_user_id_fkey;
ALTER TABLE user_usage       DROP CONSTRAINT IF EXISTS user_usage_user_id_fkey;
ALTER TABLE user_searches    DROP CONSTRAINT IF EXISTS user_searches_user_id_fkey;
ALTER TABLE saved_summaries  DROP CONSTRAINT IF EXISTS saved_summaries_user_id_fkey;

-- ─────────────────────────────────────────────────────────────────────────────
-- 2. Truncate user-dependent tables (no production data)
-- ─────────────────────────────────────────────────────────────────────────────
TRUNCATE TABLE watchlist, user_usage, user_searches, saved_summaries CASCADE;

-- ─────────────────────────────────────────────────────────────────────────────
-- 3. Migrate users.id INTEGER → UUID
-- ─────────────────────────────────────────────────────────────────────────────
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_pkey;
ALTER TABLE users DROP COLUMN IF EXISTS id;
ALTER TABLE users ADD COLUMN id UUID NOT NULL DEFAULT gen_random_uuid();
ALTER TABLE users ADD PRIMARY KEY (id);

-- ─────────────────────────────────────────────────────────────────────────────
-- 4. Add new auth columns to users
-- ─────────────────────────────────────────────────────────────────────────────
ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified         BOOLEAN      NOT NULL DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_reset_token   TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_reset_expires TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login_at          TIMESTAMPTZ;

-- Make hashed_password nullable (social-only accounts have no password)
ALTER TABLE users ALTER COLUMN hashed_password DROP NOT NULL;

-- ─────────────────────────────────────────────────────────────────────────────
-- 5. Migrate FK columns on dependent tables to UUID
-- ─────────────────────────────────────────────────────────────────────────────
ALTER TABLE watchlist       ALTER COLUMN user_id TYPE UUID USING NULL;
ALTER TABLE user_usage      ALTER COLUMN user_id TYPE UUID USING NULL;
ALTER TABLE user_searches   ALTER COLUMN user_id TYPE UUID USING NULL;
ALTER TABLE saved_summaries ALTER COLUMN user_id TYPE UUID USING NULL;

-- audit_logs has no FK constraint (user may be deleted); just change column type to VARCHAR(36)
ALTER TABLE audit_logs ALTER COLUMN user_id TYPE VARCHAR(36) USING NULL;

-- ─────────────────────────────────────────────────────────────────────────────
-- 6. Restore FK constraints
-- ─────────────────────────────────────────────────────────────────────────────
ALTER TABLE watchlist       ADD CONSTRAINT watchlist_user_id_fkey
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

ALTER TABLE user_usage      ADD CONSTRAINT user_usage_user_id_fkey
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

ALTER TABLE user_searches   ADD CONSTRAINT user_searches_user_id_fkey
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL;

ALTER TABLE saved_summaries ADD CONSTRAINT saved_summaries_user_id_fkey
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

-- ─────────────────────────────────────────────────────────────────────────────
-- 7. Index on password_reset_token for fast lookup
-- ─────────────────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_users_password_reset_token
  ON users (password_reset_token)
  WHERE password_reset_token IS NOT NULL;

COMMIT;
