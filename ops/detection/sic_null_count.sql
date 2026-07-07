-- Detection: Company.sic population state (data-quality plan §5 / P0-2 flag-independent FI signal).
-- The statement-financials rollout runbook (backend/docs/edgartools-best-practices.md) notes sic
-- was never populated by any ingestion path; this measures whether the backfill has since run.
-- Read-only; table: companies.
SELECT COUNT(*)              AS companies_total,
       COUNT(sic)            AS companies_with_sic,
       COUNT(*) - COUNT(sic) AS companies_sic_null
FROM companies;
