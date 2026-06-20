-- P3: normalized financial facts table — the queryable shape behind peer comparison (F3) and
-- fundamentals time-series (F5). Additive only, idempotent (safe to re-run). The table also
-- auto-creates at startup via Base.metadata.create_all(); this file is for existing prod DBs.

BEGIN;

CREATE TABLE IF NOT EXISTS financial_fact (
  id SERIAL PRIMARY KEY,
  company_id INTEGER NOT NULL REFERENCES companies (id),
  filing_id INTEGER REFERENCES filings (id),  -- nullable: backfill rows may precede a Filing row
  concept VARCHAR NOT NULL,                    -- standardized concept, e.g. 'revenue', 'net_income'
  raw_tag VARCHAR,                             -- as-reported us-gaap tag (audit trail)
  unit VARCHAR NOT NULL,                       -- USD | USD/shares | shares | pure
  period_start DATE,                           -- null for instant facts
  period_end DATE NOT NULL,
  fiscal_year INTEGER,
  fiscal_period VARCHAR,                       -- FY | Q1..Q4
  value NUMERIC NOT NULL,
  form VARCHAR,                                -- 10-K | 10-Q
  accession VARCHAR NOT NULL,
  source VARCHAR NOT NULL DEFAULT 'edgar_xbrl',-- edgar_xbrl | companyfacts | frames | fsds
  reconciled BOOLEAN NOT NULL DEFAULT FALSE,
  is_latest BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  -- Restatement-safe identity: accession in the key lets the original + restated rows coexist.
  CONSTRAINT uq_financial_fact_identity
    UNIQUE (company_id, concept, period_end, fiscal_period, unit, accession)
);

CREATE INDEX IF NOT EXISTS ix_financial_fact_company_id ON financial_fact (company_id);
CREATE INDEX IF NOT EXISTS ix_financial_fact_period_end ON financial_fact (period_end);
CREATE INDEX IF NOT EXISTS ix_financial_fact_accession ON financial_fact (accession);
-- Current-values-only partial indexes for the hot read paths.
CREATE INDEX IF NOT EXISTS ix_financial_fact_peer
  ON financial_fact (concept, period_end) WHERE is_latest;
CREATE INDEX IF NOT EXISTS ix_financial_fact_series
  ON financial_fact (company_id, concept, period_end) WHERE is_latest;

COMMIT;
