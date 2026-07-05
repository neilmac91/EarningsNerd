-- Multi-Period Analysis (M2): cached analysis runs (dataset + AI narrative + citations), one row
-- per (company, mode, period range). Additive only, idempotent. Fresh DBs get the table via
-- create_all; this file is for existing prod DBs.

BEGIN;

CREATE TABLE IF NOT EXISTS trend_analysis (
  id SERIAL PRIMARY KEY,
  company_id INTEGER NOT NULL REFERENCES companies (id),
  mode VARCHAR NOT NULL,                  -- 'annual' | 'quarterly'
  period_key VARCHAR NOT NULL,            -- canonical range, e.g. 'FY2016..FY2025'
  prompt_version VARCHAR NOT NULL,
  dataset_fingerprint VARCHAR NOT NULL,   -- sha256 of the canonical dataset JSON
  dataset_json JSON NOT NULL,
  narrative_md TEXT,
  citations_json JSON,
  model VARCHAR,
  grounded INTEGER NOT NULL DEFAULT 0,
  created_by_user_id INTEGER REFERENCES users (id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ,
  CONSTRAINT uq_trend_analysis_key UNIQUE (company_id, mode, period_key)
);

CREATE INDEX IF NOT EXISTS ix_trend_analysis_company_id ON trend_analysis (company_id);

COMMIT;
