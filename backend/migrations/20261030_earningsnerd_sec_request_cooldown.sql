-- Shared SEC response feedback. Replay must never reset an existing embargo.
-- This name sorts before the initial gate migration; ensure its table exists.
CREATE TABLE IF NOT EXISTS earningsnerd_sec_request_gate (
    id SMALLINT PRIMARY KEY CHECK (id = 1),
    next_admission_at TIMESTAMPTZ NOT NULL
);
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'earningsnerd_sec_request_gate'
          AND column_name = 'cooldown_until'
    ) THEN
        ALTER TABLE earningsnerd_sec_request_gate
        ADD COLUMN cooldown_until TIMESTAMPTZ NOT NULL
        DEFAULT TIMESTAMPTZ '1970-01-01 00:00:00+00';
    END IF;
END $$;
