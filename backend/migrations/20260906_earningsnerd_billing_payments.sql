-- Gross observed allocation evidence; account erasure follows existing subscription semantics.
CREATE TABLE IF NOT EXISTS earningsnerd_billing_payments (
    stripe_payment_id VARCHAR(255) NOT NULL,
    livemode BOOLEAN NOT NULL,
    stripe_invoice_id VARCHAR(255) NOT NULL,
    source_event_id VARCHAR(255) NOT NULL,
    source_api_version VARCHAR(80),
    amount_minor BIGINT NOT NULL,
    currency VARCHAR(3) NOT NULL,
    payment_type VARCHAR(80) NOT NULL,
    paid_at TIMESTAMPTZ NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    subscription_invoice BOOLEAN NOT NULL,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    attribution VARCHAR(40) NOT NULL,
    stripe_customer_id VARCHAR(255),
    stripe_subscription_id VARCHAR(255),
    is_beta_observed BOOLEAN,
    invite_cohort_observed VARCHAR(64),
    billing_cycle VARCHAR(20),
    PRIMARY KEY (stripe_payment_id, livemode)
);
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'ix_billing_payments_user_paid') THEN
        CREATE INDEX ix_billing_payments_user_paid ON earningsnerd_billing_payments (user_id, paid_at);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'ix_billing_payments_mode_paid') THEN
        CREATE INDEX ix_billing_payments_mode_paid ON earningsnerd_billing_payments (livemode, paid_at);
    END IF;
END $$;
