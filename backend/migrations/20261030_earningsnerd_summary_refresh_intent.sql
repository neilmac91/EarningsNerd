-- Keep an explicit ready-result refresh distinct from repair of an unready row.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'earningsnerd_summary_jobs'
          AND column_name = 'refresh_xbrl'
    ) THEN
        ALTER TABLE earningsnerd_summary_jobs ADD COLUMN refresh_xbrl BOOLEAN NOT NULL DEFAULT FALSE;
    END IF;
END $$;
