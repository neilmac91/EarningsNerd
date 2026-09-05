-- Retain originals; link them to the newest same-period amendment during ingestion.
-- Existing rows remain unknown until their company is refreshed/backfilled.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'filings'
          AND column_name = 'superseded_by_accession'
    ) THEN
        ALTER TABLE filings ADD COLUMN superseded_by_accession TEXT;
    END IF;
END $$;
