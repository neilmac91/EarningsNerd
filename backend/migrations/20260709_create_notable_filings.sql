-- Notable filings — homepage market-wide EDGAR discovery surface
-- (tasks/homepage-sections-review-findings.md; replaces the retired own-DB "Trending Filings").
-- Applied by CI on deploy; Base.metadata.create_all() also creates this at startup.
-- Idempotent: safe to re-run.

CREATE TABLE IF NOT EXISTS notable_filings (
    id               SERIAL PRIMARY KEY,        -- matches the model's Integer PK (create_all runs first in prod)
    accession_number VARCHAR(25) NOT NULL,      -- with dashes, as EFTS reports it
    ticker           VARCHAR(16) NOT NULL,      -- normalised upper-case; no-ticker hits dropped at scan
    cik              VARCHAR(10),
    company_name     TEXT,
    form             VARCHAR(12) NOT NULL,      -- 8-K | 10-K | 10-Q | S-1 | SC 13D
    items            JSON,                      -- 8-K item codes, e.g. ["2.02","9.01"]; NULL otherwise
    reason           VARCHAR(32) NOT NULL,      -- slug: earnings_results | annual_report | ...
    filed_date       DATE NOT NULL,
    score            NUMERIC NOT NULL DEFAULT 0, -- base + demand; recency decay applied at serve time
    sec_url          TEXT NOT NULL,
    first_seen_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_notable_filings_accession UNIQUE (accession_number)
);

-- Index names match the ones SQLAlchemy generates (create_all path), so running both this
-- migration and create_all does not create duplicate indexes.
CREATE INDEX IF NOT EXISTS ix_notable_filings_rank   ON notable_filings (filed_date, score);
CREATE INDEX IF NOT EXISTS ix_notable_filings_ticker ON notable_filings (ticker);
