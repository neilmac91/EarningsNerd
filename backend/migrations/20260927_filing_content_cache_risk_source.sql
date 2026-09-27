-- Preserve the application-prepared bounded decoded source used for source-first Risks when
-- critical excerpt extraction is unavailable. This is deliberately separate from both
-- critical_excerpt (which controls future prompt selection) and markdown_content (the filing
-- reader's cached full text). Nullable and additive for safe rolling deployment.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'filing_content_cache'
          AND column_name = 'risk_source_text'
    ) THEN
        ALTER TABLE filing_content_cache ADD COLUMN risk_source_text TEXT;
    END IF;
END $$;
