-- Run ONLY against the isolated clone's earningsnerd database through an already
-- authorized reader. Record the clone instance/connection target before execution.
-- No application data is changed; the transaction is rolled back.
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL lock_timeout = '2s';
SET LOCAL statement_timeout = '30s';
SET LOCAL idle_in_transaction_session_timeout = '45s';
SET LOCAL TIME ZONE 'UTC';

SELECT transaction_timestamp() AS observed_at_utc,
       current_database() AS database_name,
       current_setting('server_version') AS postgres_version,
       current_setting('max_connections') AS max_connections,
       pg_is_in_recovery() AS is_replica;

SELECT to_regclass('public.companies') AS companies,
       to_regclass('public.filings') AS filings,
       to_regclass('public.summaries') AS summaries,
       to_regclass('public.earningsnerd_job_runs') AS job_runs;

SELECT 'companies' AS relation, count(*) AS rows FROM public.companies
UNION ALL SELECT 'filings', count(*) FROM public.filings
UNION ALL SELECT 'summaries', count(*) FROM public.summaries;

SELECT count(*) AS filings_without_company
FROM public.filings f LEFT JOIN public.companies c ON c.id = f.company_id
WHERE c.id IS NULL;

SELECT count(*) AS summaries_without_filing
FROM public.summaries s LEFT JOIN public.filings f ON f.id = s.filing_id
WHERE f.id IS NULL;

SELECT count(*) AS filings_missing_required_identity
FROM public.filings
WHERE accession_number IS NULL OR sec_url IS NULL OR document_url IS NULL;

SELECT c.ticker, f.accession_number, f.filing_type, f.filing_date,
       s.id AS summary_id, s.created_at AS summary_created_at
FROM public.filings f
JOIN public.companies c ON c.id = f.company_id
LEFT JOIN public.summaries s ON s.filing_id = f.id
ORDER BY f.filing_date DESC, f.id DESC LIMIT 10;
ROLLBACK;
