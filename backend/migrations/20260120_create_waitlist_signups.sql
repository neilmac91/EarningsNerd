CREATE TABLE IF NOT EXISTS waitlist_signups (
    id SERIAL PRIMARY KEY,
    email VARCHAR NOT NULL UNIQUE,
    name VARCHAR,
    referral_code VARCHAR(8) NOT NULL UNIQUE,
    referred_by VARCHAR(8),
    source VARCHAR,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    email_verified BOOLEAN NOT NULL DEFAULT FALSE,
    welcome_email_sent BOOLEAN NOT NULL DEFAULT FALSE,
    position INTEGER NOT NULL,
    priority_score INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_waitlist_signups_email ON waitlist_signups (email);
CREATE INDEX IF NOT EXISTS idx_waitlist_signups_referral_code ON waitlist_signups (referral_code);
CREATE INDEX IF NOT EXISTS idx_waitlist_signups_referred_by ON waitlist_signups (referred_by);
