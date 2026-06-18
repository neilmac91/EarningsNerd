-- Phase 2: watchlist new-filing alerts. Additive only, idempotent (safe to re-run).
--
-- New tables also auto-create at startup via Base.metadata.create_all(); the new COLUMNS on
-- existing tables (watchlist, companies) do NOT auto-add, so this file is required for prod.

BEGIN;

-- Per-(user, company) alert high-water mark.
ALTER TABLE watchlist
  ADD COLUMN IF NOT EXISTS last_alerted_accession VARCHAR,
  ADD COLUMN IF NOT EXISTS last_alerted_at TIMESTAMPTZ;

-- When the scanner last checked a company (honours the scan cadence).
ALTER TABLE companies
  ADD COLUMN IF NOT EXISTS last_filings_check_at TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS notification_preferences (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL UNIQUE REFERENCES users (id) ON DELETE CASCADE,
  notify_10k BOOLEAN NOT NULL DEFAULT TRUE,
  notify_10q BOOLEAN NOT NULL DEFAULT TRUE,
  notify_8k  BOOLEAN NOT NULL DEFAULT FALSE,
  channel  VARCHAR(20) NOT NULL DEFAULT 'email',
  digest   VARCHAR(20) NOT NULL DEFAULT 'daily',
  realtime BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_notification_preferences_user_id ON notification_preferences (user_id);

CREATE TABLE IF NOT EXISTS notification_log (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  filing_id INTEGER NOT NULL REFERENCES filings (id) ON DELETE CASCADE,
  channel VARCHAR(20) NOT NULL DEFAULT 'email',
  status  VARCHAR(20) NOT NULL DEFAULT 'sent',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_notification_log_user_filing_channel UNIQUE (user_id, filing_id, channel)
);
CREATE INDEX IF NOT EXISTS idx_notification_log_user_id ON notification_log (user_id);
CREATE INDEX IF NOT EXISTS idx_notification_log_filing_id ON notification_log (filing_id);

-- Backfill default preferences for existing users (lazy get-or-create handles the rest at runtime).
-- Explicit column list required: table may have been created by SQLAlchemy create_all() without
-- DB-level DEFAULT clauses, so relying on implicit defaults causes NOT NULL violations.
INSERT INTO notification_preferences (user_id, notify_10k, notify_10q, notify_8k, channel, digest, realtime)
SELECT u.id, TRUE, TRUE, FALSE, 'email', 'daily', FALSE FROM users u
ON CONFLICT (user_id) DO NOTHING;

COMMIT;
