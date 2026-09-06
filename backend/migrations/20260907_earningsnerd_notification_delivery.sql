-- Durable alert delivery (E11b-1): one batch per outbound email with its frozen payload and
-- provider idempotency key, plus the filings it owns. Project-specific names: never adopt a
-- conventional table. Fresh databases receive the same schema through the models/create_all;
-- this file exists so production (no startup DDL) gets it through the migration ledger.
CREATE TABLE IF NOT EXISTS earningsnerd_delivery_batches (
    id SERIAL PRIMARY KEY,
    kind VARCHAR(20) NOT NULL,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    channel VARCHAR(20) NOT NULL,
    to_email TEXT NOT NULL,
    from_email TEXT NOT NULL,
    expected_item_count INTEGER NOT NULL,
    subject TEXT NOT NULL,
    body_html TEXT NOT NULL,
    payload_sha256 VARCHAR(64) NOT NULL,
    idempotency_key VARCHAR(36) NOT NULL UNIQUE,
    status VARCHAR(20) NOT NULL,
    owner_token VARCHAR(36),
    lease_expires_at TIMESTAMPTZ,
    first_dispatch_at TIMESTAMPTZ,
    attempts INTEGER NOT NULL DEFAULT 0,
    next_attempt_at TIMESTAMPTZ,
    provider_email_id VARCHAR(64),
    last_error_kind VARCHAR(32),
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS earningsnerd_delivery_items (
    id SERIAL PRIMARY KEY,
    batch_id INTEGER NOT NULL REFERENCES earningsnerd_delivery_batches(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filing_id INTEGER NOT NULL REFERENCES filings(id) ON DELETE CASCADE,
    channel VARCHAR(20) NOT NULL,
    position INTEGER NOT NULL,
    CONSTRAINT uq_earningsnerd_delivery_items_owner UNIQUE (user_id, filing_id, channel)
);
-- Catalog guards so ledger-reset replays never take a lock on these now-live tables.
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'ix_earningsnerd_delivery_batches_user_id') THEN
        CREATE INDEX ix_earningsnerd_delivery_batches_user_id ON earningsnerd_delivery_batches (user_id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'ix_earningsnerd_delivery_batches_due') THEN
        CREATE INDEX ix_earningsnerd_delivery_batches_due ON earningsnerd_delivery_batches (status, next_attempt_at);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'ix_earningsnerd_delivery_batches_lease') THEN
        CREATE INDEX ix_earningsnerd_delivery_batches_lease ON earningsnerd_delivery_batches (status, lease_expires_at);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'ix_earningsnerd_delivery_items_batch') THEN
        CREATE INDEX ix_earningsnerd_delivery_items_batch ON earningsnerd_delivery_items (batch_id, position);
    END IF;
END $$;
