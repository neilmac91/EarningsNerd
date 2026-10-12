-- Per-filing section text (Item 1A) for the "what changed" wording diff (tasks/todo.md E17).
-- Fresh databases receive the same schema through the FilingSectionText model/create_all; this
-- file brings existing databases level. Idempotent: CREATE TABLE IF NOT EXISTS and catalog-guarded
-- indexes, so a ledger reset or CI's third pass re-runs it without taking a lock on a live table.
CREATE TABLE IF NOT EXISTS filing_section_text (
    id SERIAL PRIMARY KEY,
    filing_id INTEGER NOT NULL REFERENCES filings(id) ON DELETE CASCADE,
    section VARCHAR(32) NOT NULL,
    extractor_version SMALLINT NOT NULL,
    status VARCHAR(16) NOT NULL,
    text TEXT,
    char_count INTEGER NOT NULL DEFAULT 0,
    paragraph_count INTEGER NOT NULL DEFAULT 0,
    sha256 VARCHAR(64),
    reference_only BOOLEAN NOT NULL DEFAULT FALSE,
    detection_method VARCHAR(32),
    confidence DOUBLE PRECISION,
    error_type VARCHAR(120),
    diff_prior_filing_id INTEGER REFERENCES filings(id) ON DELETE SET NULL,
    diff_engine_version SMALLINT,
    diff_summary JSON,
    diff_computed_at TIMESTAMPTZ,
    extracted_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ,
    CONSTRAINT uq_filing_section_text_filing_section UNIQUE (filing_id, section)
);
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'ix_filing_section_text_filing_id') THEN
        CREATE INDEX ix_filing_section_text_filing_id ON filing_section_text (filing_id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'ix_filing_section_text_status_extracted') THEN
        CREATE INDEX ix_filing_section_text_status_extracted ON filing_section_text (status, extracted_at);
    END IF;
END $$;
