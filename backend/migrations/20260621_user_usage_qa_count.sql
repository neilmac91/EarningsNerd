-- "Ask this Filing" Copilot (A2 / P1): per-user monthly Q&A question counter.
-- Metered separately from summary_count so the Copilot fair-use cap and the summary quota are
-- independent.
--
-- Additive only, idempotent (safe to re-run). The column does NOT auto-add via
-- Base.metadata.create_all() since `user_usage` already exists, so this file is required for prod.

BEGIN;

ALTER TABLE user_usage
  ADD COLUMN IF NOT EXISTS qa_count INTEGER NOT NULL DEFAULT 0;

COMMIT;
