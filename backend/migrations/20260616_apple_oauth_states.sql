-- Apple Sign In: state/nonce storage for form_post OAuth flow
-- Date: 2026-06-16
-- SameSite=Lax cookies are dropped on Apple's cross-site form_post callback,
-- so state+nonce are stored in this table (10-min TTL, consumed on first use).
-- Run with: psql $DATABASE_URL -f migrations/20260616_apple_oauth_states.sql

BEGIN;

CREATE TABLE IF NOT EXISTS oauth_states (
    id         SERIAL      PRIMARY KEY,
    state      VARCHAR(64) UNIQUE NOT NULL,
    nonce      VARCHAR(64) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL
);

-- Note: UNIQUE on state implicitly creates an index; no separate CREATE INDEX needed.

COMMIT;
