-- Durable, anti-enumeration failed-login lockout (replaces the in-memory per-process limiter).
-- Keyed on a SECRET_KEY-peppered SHA-256 of the email, NOT the user row, so a non-existent
-- address locks exactly like a real one (no 429-vs-401 account-enumeration oracle) and the raw
-- email is never stored. Schema is also created at startup by Base.metadata.create_all(); this
-- file documents the table and lets it be applied manually to existing databases.

CREATE TABLE IF NOT EXISTS login_attempts (
    email_hash VARCHAR(64) PRIMARY KEY,
    failed_count INTEGER NOT NULL DEFAULT 0,
    locked_until TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
