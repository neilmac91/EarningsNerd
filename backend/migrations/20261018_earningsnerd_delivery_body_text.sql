-- E110: a delivery batch freezes its mail's plain-text part beside its page, so every attempt of a
-- queued alert or digest sends the same text part, as it sends the same page, under the same key.
-- NULL on a batch frozen before this column: it replays as it was frozen, its page alone, and the
-- provider builds its text part from the page (notification_delivery_service.payload_digest leaves
-- a NULL text out, so such a batch keeps the digest its key is bound to). Fresh databases get the
-- column through the model and create_all, and app/database.py's additive self-heal repairs an older
-- local one; production gets it here. ADD COLUMN is guarded so a re-run never takes the ACCESS
-- EXCLUSIVE lock twice.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'earningsnerd_delivery_batches'
          AND column_name = 'body_text'
    ) THEN
        ALTER TABLE earningsnerd_delivery_batches ADD COLUMN body_text TEXT;
    END IF;
END $$;
