-- The one-time handoff of an OAuth sign-in from its provider callback to the page it lands on (E29 (5)): the
-- SessionHandoff model (app/models/session_handoff.py). Only SHA-256 hashes of the code and of the browser-binding
-- cookie are stored; a row is single use and lives 120 seconds. Project-specific name: never adopt a conventional
-- table. Fresh databases receive the same schema through the model/create_all; this file exists so production (no
-- startup DDL) gets it through the migration ledger.
CREATE TABLE IF NOT EXISTS earningsnerd_session_handoffs (
    id SERIAL PRIMARY KEY,
    code_hash VARCHAR(64) NOT NULL,
    binder_hash VARCHAR(64) NOT NULL,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_earningsnerd_session_handoffs_code_hash UNIQUE (code_hash)
);
-- Catalog guards so ledger-reset replays never take a lock on this now-live table.
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'ix_earningsnerd_session_handoffs_user_id') THEN
        CREATE INDEX ix_earningsnerd_session_handoffs_user_id ON earningsnerd_session_handoffs (user_id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'ix_earningsnerd_session_handoffs_expires_at') THEN
        CREATE INDEX ix_earningsnerd_session_handoffs_expires_at ON earningsnerd_session_handoffs (expires_at);
    END IF;
END $$;
