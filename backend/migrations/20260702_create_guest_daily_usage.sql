-- Durable per-IP daily cap on anonymous summary generation (denial-of-wallet backstop).
-- Replaces a Redis-only quota that failed open in production (Redis is off there). Keyed on a
-- SECRET_KEY-peppered SHA-256 of the TRUSTED client IP (never the raw IP, never the Cloud Run
-- front-end address). One row per distinct guest IP hash; the counter self-resets when usage_date
-- rolls to a new UTC day. Schema is also created at startup by Base.metadata.create_all(); this
-- file documents the table and lets it be applied manually to existing databases.

CREATE TABLE IF NOT EXISTS guest_daily_usage (
    ip_hash VARCHAR(64) PRIMARY KEY,
    usage_date DATE NOT NULL,
    count INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
