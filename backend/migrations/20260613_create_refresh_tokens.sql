-- Refresh tokens: opaque, rotated, stored as a SHA-256 hash (raw token never persisted).
-- Schema is also created at startup by Base.metadata.create_all(); this file documents the
-- table and lets it be applied manually to existing databases.

CREATE TABLE IF NOT EXISTS refresh_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    token_hash VARCHAR(64) NOT NULL UNIQUE,
    expires_at TIMESTAMP NOT NULL,
    revoked_at TIMESTAMP,
    replaced_by_id INTEGER REFERENCES refresh_tokens (id) ON DELETE SET NULL,
    user_agent VARCHAR(500),
    ip_hash VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_id ON refresh_tokens (user_id);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_token_hash ON refresh_tokens (token_hash);
