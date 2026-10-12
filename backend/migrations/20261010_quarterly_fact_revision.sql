-- Append-only before/after audit of bounded, explicitly applied quarterly repairs.
-- No historical financial facts are modified by this schema migration.
SET lock_timeout = '5s';
SET statement_timeout = '30s';
CREATE TABLE IF NOT EXISTS financial_fact_revision (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(64) NOT NULL,
    company_id INTEGER NOT NULL REFERENCES companies(id),
    fact_id INTEGER NOT NULL REFERENCES financial_fact(id),
    action VARCHAR(16) NOT NULL,
    calculation_version VARCHAR(64) NOT NULL,
    payload_sha256 VARCHAR(64) NOT NULL,
    before_state JSON,
    after_state JSON NOT NULL,
    reverts_revision_id INTEGER REFERENCES financial_fact_revision(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_financial_fact_revision_run_company
    ON financial_fact_revision (run_id, company_id);
CREATE INDEX IF NOT EXISTS ix_financial_fact_revision_fact ON financial_fact_revision (fact_id);
RESET statement_timeout;
RESET lock_timeout;
