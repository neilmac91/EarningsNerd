-- One Summary per Filing: add a UNIQUE constraint on summaries.filing_id (closes the concurrent
-- pregenerate + SSE double-insert race, latent bug #3 — the S1 unification routes both writers
-- through one orchestrator, and the losing writer now returns the existing row instead of erroring).
--
-- Idempotent + safe to re-apply every deploy (CI re-runs all migrations): it first collapses any
-- pre-existing duplicates (keeping the highest-id row per filing_id and repointing saved_summaries,
-- the only FK to summaries.id, to that survivor), then adds the named constraint only if absent.
-- In practice duplicates should be rare-to-none (the app checks for an existing summary before
-- generating), so the dedup steps are defensive. Fresh DBs get the same constraint from
-- Base.metadata.create_all() via Summary.__table_args__ (UniqueConstraint 'uq_summaries_filing_id').

BEGIN;

-- 1. Repoint saved_summaries off any duplicate summary rows onto the surviving row per filing.
--    Survivor = MAX(id) per filing_id (created_at can be NULL on legacy rows, so tiebreak on id).
WITH ranked AS (
    SELECT id, filing_id,
           ROW_NUMBER() OVER (PARTITION BY filing_id ORDER BY id DESC) AS rn
    FROM summaries
),
survivors AS (
    SELECT filing_id, id AS keep_id FROM ranked WHERE rn = 1
),
dupes AS (
    SELECT r.id AS dup_id, s.keep_id
    FROM ranked r
    JOIN survivors s ON s.filing_id = r.filing_id
    WHERE r.rn > 1
)
UPDATE saved_summaries ss
SET summary_id = d.keep_id
FROM dupes d
WHERE ss.summary_id = d.dup_id;

-- 2. Delete the now-orphaned duplicate summary rows (keep MAX(id) per filing_id).
DELETE FROM summaries s
USING (
    SELECT id, ROW_NUMBER() OVER (PARTITION BY filing_id ORDER BY id DESC) AS rn
    FROM summaries
) r
WHERE s.id = r.id AND r.rn > 1;

-- 3. Add the unique constraint if it isn't already present.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_summaries_filing_id' AND conrelid = 'summaries'::regclass
    ) THEN
        ALTER TABLE summaries ADD CONSTRAINT uq_summaries_filing_id UNIQUE (filing_id);
    END IF;
END $$;

COMMIT;
