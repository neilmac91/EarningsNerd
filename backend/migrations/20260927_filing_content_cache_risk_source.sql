-- Preserve the application-prepared bounded decoded source used for source-first Risks when
-- critical excerpt extraction is unavailable. This is deliberately separate from both
-- critical_excerpt (which controls future prompt selection) and markdown_content (the filing
-- reader's cached full text). Nullable and additive for safe rolling deployment.

ALTER TABLE filing_content_cache
    ADD COLUMN IF NOT EXISTS risk_source_text TEXT;
