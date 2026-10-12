-- Separate calculation lineage from validation without certifying legacy derived rows.
SET lock_timeout = '5s';
SET statement_timeout = '60s';
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'financial_fact' AND column_name = 'provenance'
    ) THEN
        ALTER TABLE financial_fact ADD COLUMN provenance JSON;
    END IF;
END $$;
RESET statement_timeout;
RESET lock_timeout;
