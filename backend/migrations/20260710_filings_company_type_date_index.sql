-- PS1: composite index for the filings-list DB read path.
-- Backs get_cached_filings / DB-first serving in app/routers/filings.py:
--   SELECT ... FROM filings
--   WHERE company_id = ? AND filing_type IN (...) ORDER BY filing_date DESC LIMIT 20
-- and the trending join's company_id filter. filings.company_id was previously unindexed, so this
-- query degraded toward a sequential scan as the table grows.
--
-- Additive, idempotent (safe to re-run on every deploy — CI re-applies all migrations). The same
-- Index is declared on the Filing model so Base.metadata.create_all() builds it on fresh DBs under
-- the same name; IF NOT EXISTS keeps create_all + this migration from colliding.
-- Plain (non-CONCURRENT) CREATE INDEX to match the house style and stay transaction-safe: filings is
-- a small, low-write table, so the brief build lock is acceptable (CONCURRENTLY cannot run inside
-- the BEGIN/COMMIT block and would leave an INVALID index on interruption that IF NOT EXISTS skips).

BEGIN;

CREATE INDEX IF NOT EXISTS ix_filings_company_type_date
  ON filings (company_id, filing_type, filing_date);

COMMIT;
