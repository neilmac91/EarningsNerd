-- Only explicit new-account confirmations produce evidence. No backfill for existing accounts.
CREATE TABLE IF NOT EXISTS account_agreements (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    adult_eligible BOOLEAN NOT NULL,
    terms_accepted BOOLEAN NOT NULL,
    terms_version VARCHAR(32) NOT NULL,
    eligibility_version VARCHAR(32) NOT NULL,
    accepted_at TIMESTAMPTZ NOT NULL,
    source VARCHAR(16) NOT NULL,
    CONSTRAINT ck_account_agreements_affirmative CHECK (adult_eligible = true AND terms_accepted = true),
    CONSTRAINT ck_account_agreements_source CHECK (source IN ('password', 'google', 'apple'))
);

-- OAuth signup confirmation stays bound to the expiring, single-use state. NULL means no assent.
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public'
                   AND table_name = 'oauth_states' AND column_name = 'agreement_terms_version') THEN
        ALTER TABLE oauth_states ADD COLUMN agreement_terms_version VARCHAR(32);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public'
                   AND table_name = 'oauth_states' AND column_name = 'agreement_eligibility_version') THEN
        ALTER TABLE oauth_states ADD COLUMN agreement_eligibility_version VARCHAR(32);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public'
                   AND table_name = 'oauth_states' AND column_name = 'agreement_accepted_at') THEN
        ALTER TABLE oauth_states ADD COLUMN agreement_accepted_at TIMESTAMPTZ;
    END IF;
END $$;
