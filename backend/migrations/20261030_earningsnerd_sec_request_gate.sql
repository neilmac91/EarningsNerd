-- Optional SEC fleet request admission. No startup DDL and no reset on replay.
CREATE TABLE IF NOT EXISTS earningsnerd_sec_request_gate (
    id SMALLINT PRIMARY KEY CHECK (id = 1),
    next_admission_at TIMESTAMPTZ NOT NULL
);
INSERT INTO earningsnerd_sec_request_gate (id, next_admission_at)
VALUES (1, TIMESTAMPTZ '1970-01-01 00:00:00+00')
ON CONFLICT (id) DO NOTHING;
