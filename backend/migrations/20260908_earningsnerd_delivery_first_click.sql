-- E11c alert-to-return measurement: record the first click on each delivered alert email
-- (from Resend's email.clicked webhook) and index the provider email id the webhook carries.
-- Fresh databases get both through the models/create_all; production gets them here.
-- ADD COLUMN is guarded so a re-run never takes the ACCESS EXCLUSIVE lock twice; the index is
-- built CONCURRENTLY outside any transaction block (scripts/apply_migrations.sh runs each
-- statement on its own and fails on an INVALID index rather than accepting IF NOT EXISTS).
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'earningsnerd_delivery_batches'
          AND column_name = 'first_click_at'
    ) THEN
        ALTER TABLE earningsnerd_delivery_batches ADD COLUMN first_click_at TIMESTAMPTZ;
    END IF;
END $$;
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_earningsnerd_delivery_batches_provider_email_id
    ON earningsnerd_delivery_batches (provider_email_id);
