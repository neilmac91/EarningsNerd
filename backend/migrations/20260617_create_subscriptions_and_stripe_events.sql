-- Phase 1: billing → production + entitlements.
--
-- `subscriptions` is the durable, queryable billing record entitlements read from; `stripe_events`
-- is the webhook idempotency ledger. Both tables are ALSO created at startup by
-- Base.metadata.create_all(); this file lets them be applied manually to an existing database and
-- documents the backfill from the legacy `users.is_pro` / stripe id columns.
--
-- Safe to re-run (IF NOT EXISTS + ON CONFLICT DO NOTHING).

CREATE TABLE IF NOT EXISTS subscriptions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users (id) ON DELETE CASCADE,
    plan VARCHAR(20) NOT NULL DEFAULT 'free',
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    stripe_customer_id VARCHAR,
    stripe_subscription_id VARCHAR,
    stripe_price_id VARCHAR,
    current_period_end TIMESTAMPTZ,
    trial_end TIMESTAMPTZ,
    cancel_at_period_end BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON subscriptions (user_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_stripe_customer_id ON subscriptions (stripe_customer_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_stripe_subscription_id ON subscriptions (stripe_subscription_id);

CREATE TABLE IF NOT EXISTS stripe_events (
    event_id VARCHAR PRIMARY KEY,
    type VARCHAR NOT NULL,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Backfill: one subscriptions row per existing user, derived from the legacy mirror columns.
-- Pro users → active/pro; everyone else → active/free. (No trial/period data is known historically.)
-- cancel_at_period_end is set explicitly: when the table pre-exists from
-- Base.metadata.create_all() the column is NOT NULL with no server default, so the
-- backfill must supply a value rather than rely on the DEFAULT FALSE above.
INSERT INTO subscriptions (user_id, plan, status, stripe_customer_id, stripe_subscription_id, cancel_at_period_end, created_at)
SELECT
    u.id,
    CASE WHEN u.is_pro THEN 'pro' ELSE 'free' END,
    'active',
    u.stripe_customer_id,
    u.stripe_subscription_id,
    FALSE,
    NOW()
FROM users u
ON CONFLICT (user_id) DO NOTHING;
