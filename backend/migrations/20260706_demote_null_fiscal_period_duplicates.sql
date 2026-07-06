-- Multi-Period Analysis (M1) safety net: legacy 10-Q facts carry fiscal_period = NULL (the quarter
-- label was never derivable from a single filing — see facts_service._fiscal_period). The
-- companyfacts ingest writes properly-labelled Q1..Q4 rows for the same periods and demotes the
-- NULL twins as it goes (upsert_facts_bulk); this idempotent pass converges any rows written before
-- that code shipped so a period never has two is_latest rows (one NULL, one labelled). Safe to
-- re-run any time; no-ops until labelled rows exist. Run after the first companyfacts warm sync.

BEGIN;

UPDATE financial_fact f
SET is_latest = FALSE
WHERE f.fiscal_period IS NULL
  AND f.is_latest
  AND EXISTS (
    SELECT 1
    FROM financial_fact g
    WHERE g.company_id = f.company_id
      AND g.concept = f.concept
      AND g.period_end = f.period_end
      AND g.unit = f.unit
      AND g.fiscal_period IS NOT NULL
      AND g.is_latest
  );

COMMIT;
