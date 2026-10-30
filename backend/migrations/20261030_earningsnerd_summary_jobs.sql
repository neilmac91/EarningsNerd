-- Off-by-default durable summary ownership, outbox intent and usage receipt.
CREATE TABLE IF NOT EXISTS earningsnerd_summary_jobs (
    id VARCHAR(32) PRIMARY KEY,
    filing_id INTEGER NOT NULL UNIQUE REFERENCES filings(id) ON DELETE CASCADE,
    generation INTEGER NOT NULL DEFAULT 1,
    prompt_version VARCHAR(80) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'queued',
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    system_funded BOOLEAN NOT NULL DEFAULT FALSE,
    force BOOLEAN NOT NULL DEFAULT FALSE,
    lease_token VARCHAR(32),
    lease_until TIMESTAMPTZ,
    attempts INTEGER NOT NULL DEFAULT 0,
    next_attempt_at TIMESTAMPTZ NOT NULL,
    last_dispatched_at TIMESTAMPTZ,
    dispatch_token VARCHAR(32) NOT NULL,
    stage VARCHAR(30) NOT NULL DEFAULT 'queued',
    error_code VARCHAR(60),
    summary_id INTEGER,
    reservation_token VARCHAR(36),
    charge_state VARCHAR(20) NOT NULL DEFAULT 'unreserved',
    charge_month VARCHAR(7),
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_earningsnerd_summary_jobs_status ON earningsnerd_summary_jobs(status);
