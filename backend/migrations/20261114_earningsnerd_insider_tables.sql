-- Insider activity (SEC Form 4) stored per accession, and the per-issuer scan that fills it (ADR 0009): the models
-- in app/models/insider.py. Public SEC data; no row references a user or the filings table. Project-specific
-- names: never adopt a conventional table. Fresh databases receive the same schema through the models/create_all;
-- this file exists so production (no startup DDL) gets it through the migration ledger.
CREATE TABLE IF NOT EXISTS earningsnerd_insider_filings (
    id SERIAL PRIMARY KEY,
    accession VARCHAR(25) NOT NULL,
    issuer_cik VARCHAR(10) NOT NULL,
    filed_date DATE,
    primary_document VARCHAR(255),
    status VARCHAR(20) NOT NULL,
    error_type VARCHAR(60),
    parser_version INTEGER,
    attempted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_earningsnerd_insider_filings_issuer_accession UNIQUE (issuer_cik, accession)
);
CREATE TABLE IF NOT EXISTS earningsnerd_insider_transactions (
    id SERIAL PRIMARY KEY,
    accession VARCHAR(25) NOT NULL,
    ordinal INTEGER NOT NULL,
    issuer_cik VARCHAR(10) NOT NULL,
    insider_name VARCHAR(255),
    insider_title VARCHAR(255),
    is_director BOOLEAN,
    is_officer BOOLEAN,
    is_ten_pct_owner BOOLEAN,
    ticker VARCHAR(16),
    transaction_date DATE,
    transaction_code VARCHAR(4),
    transaction_label VARCHAR(60),
    shares DOUBLE PRECISION,
    price DOUBLE PRECISION,
    value DOUBLE PRECISION,
    acquired_disposed VARCHAR(1),
    is_10b5_1 BOOLEAN,
    filed_date DATE,
    created_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_earningsnerd_insider_transactions_accession_ordinal UNIQUE (accession, ordinal)
);
CREATE TABLE IF NOT EXISTS earningsnerd_insider_scans (
    id SERIAL PRIMARY KEY,
    issuer_cik VARCHAR(10) NOT NULL,
    status VARCHAR(20) NOT NULL,
    lease_token VARCHAR(32),
    lease_until TIMESTAMPTZ,
    last_listed_at TIMESTAMPTZ,
    paused_until TIMESTAMPTZ,
    pauses INTEGER NOT NULL DEFAULT 0,
    error_code VARCHAR(60),
    steps INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_earningsnerd_insider_scans_issuer_cik UNIQUE (issuer_cik)
);
-- Catalog guards so ledger-reset replays never take a lock on these now-live tables. Each looks in the schema the
-- statement would write to: pg_indexes lists every schema, and an index of that name elsewhere is not this one.
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname = current_schema()
                   AND indexname = 'ix_earningsnerd_insider_filings_issuer_status') THEN
        CREATE INDEX ix_earningsnerd_insider_filings_issuer_status ON earningsnerd_insider_filings (issuer_cik, status);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname = current_schema()
                   AND indexname = 'ix_earningsnerd_insider_transactions_issuer_date') THEN
        CREATE INDEX ix_earningsnerd_insider_transactions_issuer_date ON earningsnerd_insider_transactions (issuer_cik, transaction_date);
    END IF;
END $$;
