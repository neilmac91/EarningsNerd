-- Beta-tester feedback (bug / feature / general) from the in-dashboard widget.
-- This is a NEW table, so Base.metadata.create_all() (app startup) creates it automatically on
-- deploy — no manual step needed. This file is kept for schema parity / manual provisioning.
-- Idempotent — safe to re-run.
-- Apply (optional):  psql "$DATABASE_URL" -f backend/migrations/20260624_create_feedback.sql

BEGIN;

CREATE TABLE IF NOT EXISTS feedback (
    id          SERIAL       PRIMARY KEY,
    user_id     INTEGER      REFERENCES users (id) ON DELETE SET NULL,
    type        VARCHAR(20)  NOT NULL DEFAULT 'general',
    message     TEXT         NOT NULL,
    page_url    VARCHAR(500),
    status      VARCHAR(20)  NOT NULL DEFAULT 'new',
    ip_address  VARCHAR(64),
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_feedback_user_id ON feedback (user_id);
CREATE INDEX IF NOT EXISTS idx_feedback_type ON feedback (type);
CREATE INDEX IF NOT EXISTS idx_feedback_status ON feedback (status);

COMMIT;
