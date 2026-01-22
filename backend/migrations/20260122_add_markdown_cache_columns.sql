-- Add markdown caching columns to filing_content_cache table
-- These columns store the AI-ready markdown content parsed from SEC filings

ALTER TABLE filing_content_cache
ADD COLUMN IF NOT EXISTS markdown_content TEXT,
ADD COLUMN IF NOT EXISTS markdown_generated_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS markdown_sections JSONB;

-- Add index for faster lookups when checking if markdown exists
CREATE INDEX IF NOT EXISTS idx_filing_content_cache_markdown_generated
ON filing_content_cache (markdown_generated_at)
WHERE markdown_generated_at IS NOT NULL;

COMMENT ON COLUMN filing_content_cache.markdown_content IS 'Clean, AI-ready markdown content parsed from the SEC filing';
COMMENT ON COLUMN filing_content_cache.markdown_generated_at IS 'Timestamp when markdown was generated';
COMMENT ON COLUMN filing_content_cache.markdown_sections IS 'JSON array of section types successfully extracted from the filing';
