-- FPI history backfill: from this release, with ENABLE_FPI_FILINGS on, the EFTS history walk
-- (app/services/filing_history_service.py) also lists a foreign private issuer's 20-F and 40-F annual
-- reports. Every company stamped history_backfilled_at before it was walked for 10-K/10-Q only, and the
-- on-visit backfill never walks a stamped company again, so a foreign issuer opened before this
-- release would never get its annual reports older than SEC's recent window.
--
-- Clear the stamp of each stamped company the old walk can have found none of its reports for: it
-- holds no 10-K or 10-Q row, original or amendment, and it holds a 20-F, 40-F or 6-K row (a foreign
-- issuer the live list has listed) or no filing row at all (unknown). Its next visit walks it again on
-- the service or the task worker, both of which run with the flag on: four EFTS requests through the
-- shared limiter, as a first visit costs. A company holding a 10-K/10-Q row, or only other forms (an
-- 8-K, a Form 4), keeps its stamp; a former foreign issuer now filing 10-K/10-Q gets its older 40-F or
-- 20-F only from the Ops backfill-filing-history operation, given its ticker.
--
-- Data only: one UPDATE of the matching companies rows, under the row locks it takes. The ledger
-- applies it once per sha256. Re-running is safe: it clears the same kind of stamp again, which costs
-- one more walk at the company's next visit; an unstamped company is untouched. The deploy applies it
-- before the new task worker and service revisions serve, so a matching company first walked by an old
-- revision in those minutes is stamped again without its 20-F/40-F; the Ops operation re-walks it.
SET lock_timeout = '5s';
SET statement_timeout = '30s';
UPDATE companies
SET history_backfilled_at = NULL
WHERE history_backfilled_at IS NOT NULL
  AND NOT EXISTS (
    SELECT 1
    FROM filings
    WHERE filings.company_id = companies.id
      AND filings.filing_type IN ('10-K', '10-K/A', '10-Q', '10-Q/A')
  )
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
