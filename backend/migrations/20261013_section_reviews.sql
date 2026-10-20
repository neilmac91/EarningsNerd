-- A reader's review of a filing section's wording changes: labels per change, completion and the
-- frozen receipt (tasks/todo.md E27, PR B). Fresh databases receive the same schema through the
-- SectionReview model/create_all; this file brings existing databases level. Idempotent: CREATE
-- TABLE IF NOT EXISTS and catalog-guarded indexes, so a ledger reset or CI's third pass re-runs it
-- without taking a lock on a live table.
CREATE TABLE IF NOT EXISTS section_reviews (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filing_id INTEGER NOT NULL REFERENCES filings(id) ON DELETE CASCADE,
    section VARCHAR(32) NOT NULL,
    labels JSON NOT NULL,
    engine_version SMALLINT,
    completed_at TIMESTAMPTZ,
    receipt JSON,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ,
    CONSTRAINT uq_section_reviews_user_filing_section UNIQUE (user_id, filing_id, section)
);
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'ix_section_reviews_user_id') THEN
        CREATE INDEX ix_section_reviews_user_id ON section_reviews (user_id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'ix_section_reviews_filing_id') THEN
        CREATE INDEX ix_section_reviews_filing_id ON section_reviews (filing_id);
    END IF;
END $$;
