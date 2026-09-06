-- Admission reservations for per-user quotas (E07b). Project-specific name: never adopt a
-- conventional table. Fresh databases receive the same schema through the UsageReservation
-- model/create_all; this file exists so production (no startup DDL) gets it through the ledger.
CREATE TABLE IF NOT EXISTS earningsnerd_usage_reservations (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    month VARCHAR(7) NOT NULL,
    kind VARCHAR(20) NOT NULL,
    token VARCHAR(36) NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);
-- Catalog guard so ledger-reset replays never take a lock on this now-live table.
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'ix_earningsnerd_usage_reservations_scope') THEN
        CREATE INDEX ix_earningsnerd_usage_reservations_scope
            ON earningsnerd_usage_reservations (user_id, month, kind, expires_at);
    END IF;
END $$;
