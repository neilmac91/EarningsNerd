-- FPI history backfill: from this release, with ENABLE_FPI_FILINGS on, the EFTS history walk
-- (app/services/filing_history_service.py) also lists a foreign private issuer's 20-F and 40-F annual
-- reports. Every company stamped history_backfilled_at before it was walked for 10-K/10-Q only, and the
-- on-visit backfill never walks a stamped company again, so a foreign issuer opened before this
-- release would never get its annual reports older than SEC's recent window.
--
-- Clear the stamp of each stamped company that holds a 20-F, 40-F or 6-K row, original or amendment (a
-- foreign issuer the live list has listed, or one now filing 10-K/10-Q whose older 40-F or 20-F the old
-- walk skipped), or holds no filing row at all (unknown). Its next visit walks it again on the service
-- or the task worker, both of which run with the flag on: four EFTS requests through the shared
-- limiter, as a first visit costs. A company holding only 10-K/10-Q rows or other forms (an 8-K, a
-- Form 4) keeps its stamp; a former foreign issuer with no foreign row stored gets its older 40-F or
-- 20-F only from the Ops backfill-filing-history operation, given its ticker.
--
-- Data only: one UPDATE of the matching companies rows, under the row locks it takes. The ledger
-- applies it once per sha256. Re-running is safe: it clears the same kind of stamp again, which costs
-- one more walk at the company's next visit; an unstamped company is untouched. The deploy applies it
-- before the new task worker and service revisions serve, so a matching company first walked by an old
-- revision meanwhile (minutes, or until a deploy that failed after this step succeeds) is stamped
-- again without its 20-F/40-F, and its History backfill log line has no forms key. Once the new
-- revisions serve, re-run this file: delete its migration_ledger row and re-run the deploy
-- (scripts/apply_migrations.sh).
SET lock_timeout = '5s';
SET statement_timeout = '30s';
UPDATE companies
SET history_backfilled_at = NULL
WHERE history_backfilled_at IS NOT NULL
  AND (
    EXISTS (
      SELECT 1
      FROM filings
      WHERE filings.company_id = companies.id
        AND filings.filing_type IN ('20-F', '20-F/A', '40-F', '40-F/A', '6-K', '6-K/A')
    )
    OR NOT EXISTS (SELECT 1 FROM filings WHERE filings.company_id = companies.id)
  );
RESET statement_timeout;
RESET lock_timeout;
