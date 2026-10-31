-- Freeze Reply-To with each delivery envelope. No default or backfill: existing batches,
-- attempted or not, keep the omitted header and the digest their provider key was bound to.
-- Fresh selections freeze the configured role. Guard the ALTER so a converged replay takes
-- no ACCESS EXCLUSIVE lock; migration_ledger owns application of this file.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'earningsnerd_delivery_batches'
          AND column_name = 'reply_to'
    ) THEN
        ALTER TABLE earningsnerd_delivery_batches ADD COLUMN reply_to TEXT;
    END IF;
END $$;
