-- Closed-beta invite gate: per-person, single-use registration invites.
-- Schema is also created at startup by Base.metadata.create_all(); this migration keeps an existing
-- production database in sync. Idempotent — safe to re-run.
-- Apply:  psql "$DATABASE_URL" -f backend/migrations/20260624_create_invite_codes.sql

BEGIN;

CREATE TABLE IF NOT EXISTS invite_codes (
    id          SERIAL       PRIMARY KEY,
    code_hash   VARCHAR(64)  NOT NULL UNIQUE,             -- SHA-256 of the raw token (never stored raw)
    email       VARCHAR(255),                             -- optional binding; only this address may redeem
    expires_at  TIMESTAMPTZ  NOT NULL,
    used_at     TIMESTAMPTZ,                              -- NULL = unused (single-use)
    is_revoked  BOOLEAN      NOT NULL DEFAULT FALSE,
    created_by  INTEGER      REFERENCES users (id) ON DELETE SET NULL,
    user_id     INTEGER      REFERENCES users (id) ON DELETE SET NULL,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_invite_codes_code_hash ON invite_codes (code_hash);
CREATE INDEX IF NOT EXISTS idx_invite_codes_email     ON invite_codes (email);
CREATE INDEX IF NOT EXISTS idx_invite_codes_used_at   ON invite_codes (used_at);
CREATE INDEX IF NOT EXISTS idx_invite_codes_user_id   ON invite_codes (user_id);

COMMIT;
