-- Requested beta-invitation email (EN-BETA PB-01): the address-level suppression list and the per-link delivery
-- ledger (app/models/invite_mail.py). Project-specific names: never adopt a conventional table. Fresh databases
-- receive the same schema through the MailRecipient and InviteDelivery models/create_all; this file brings existing
-- databases level. New tables only, and nothing is backfilled. Addresses are stored only as recipient_hash
-- (app/services/mail_suppression_service.py).
CREATE TABLE IF NOT EXISTS earningsnerd_mail_recipients (
    id SERIAL PRIMARY KEY,
    recipient_hash VARCHAR(64) NOT NULL UNIQUE,
    suppressed_at TIMESTAMPTZ,
    suppression_reason VARCHAR(20),
    suppression_event VARCHAR(80),
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT ck_earningsnerd_mail_recipients_reason CHECK (
        suppression_reason IS NULL
        OR suppression_reason IN ('unsubscribed', 'hard_bounce', 'complaint', 'provider_suppressed')
    ),
    CONSTRAINT ck_earningsnerd_mail_recipients_suppressed CHECK ((suppressed_at IS NULL) = (suppression_reason IS NULL))
);

CREATE TABLE IF NOT EXISTS earningsnerd_invite_deliveries (
    id SERIAL PRIMARY KEY,
    invite_id INTEGER NOT NULL UNIQUE REFERENCES invite_codes(id) ON DELETE CASCADE,
    recipient_hash VARCHAR(64) NOT NULL,
    delivery_ref VARCHAR(32) NOT NULL UNIQUE,
    unsubscribe_token_hash VARCHAR(64) NOT NULL UNIQUE,
    status VARCHAR(20) NOT NULL,
    permission_via VARCHAR(16) NOT NULL,
    permission_requested_on DATE NOT NULL,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    provider_email_id VARCHAR(64),
    error_kind VARCHAR(40),
    bounce_type VARCHAR(20),
    last_event_id VARCHAR(80),
    last_event_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT ck_earningsnerd_invite_deliveries_status CHECK (
        status IN ('sending', 'failed', 'unknown', 'accepted', 'delayed', 'delivered', 'bounced', 'suppressed',
                   'complained')
    ),
    CONSTRAINT ck_earningsnerd_invite_deliveries_permission CHECK (
        permission_via IN ('email', 'message', 'call', 'in_person', 'other')
    )
);
-- Catalog guards so ledger-reset replays never take a lock on these now-live tables.
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'ix_earningsnerd_invite_deliveries_recipient') THEN
        CREATE INDEX ix_earningsnerd_invite_deliveries_recipient ON earningsnerd_invite_deliveries (recipient_hash);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'ix_earningsnerd_invite_deliveries_provider_email_id') THEN
        CREATE INDEX ix_earningsnerd_invite_deliveries_provider_email_id
            ON earningsnerd_invite_deliveries (provider_email_id);
    END IF;
END $$;
