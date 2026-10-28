-- The stored summary excerpts by the builder that wrote them (E28 (a)/(b), read-only, counts only). Its own Ops
-- step runs it (with ops/excerpts/provenance_count.py), not detection-sql: it reads filing_content_cache, which
-- that loop's stated read scope does not name, and a failure here must not cut off the loop's other snapshots.
-- No column records an excerpt's source: the `Excerpt provenance` log line is its only record
-- (summary_generation_service.get_or_cache_excerpt). The two builders write different openings, unchanged
-- since 2026-09-13 (d91dbdde) and through the October window, so a stored excerpt's first bytes name its
-- builder (ai/extraction.py):
--   regex_targeted   the regex path's sections: "\n\n" and 50 "=" glued to the first section's label
--                    (extract_critical_sections' `combined`, since bf56144f 2026-06-14; recovered windows may
--                    follow it).
--   regex_recovered  the regex path's windows alone: "RISK & NARRATIVE CONTEXT (recovered from filing):"
--                    or "FINANCIAL & MD&A CONTEXT (recovered from filing):" first (also since bf56144f).
--   native           a section the fetched document's parse supplied: one of _SECTION_LAYOUT's labels and
--                    ":" and a newline first (assemble_excerpt_from_sections), on a row created since the
--                    native assembler (2714c4df, 2026-06-15); never a separator first.
--   label_before_native  the same opening on a row created before 2026-06-15: the regex path wrote those
--                    labels first with no separator until cdea7751 (2026-01-25), and a native excerpt may since
--                    have been written onto the row. Unverified.
--   unclassified     anything else: the regex path's last resort (the cleaned document's first 120,000
--                    characters), or an older builder's. Unverified.
--   none             no excerpt stored (null or empty).
-- An opening names the builder, never why a native parse was not used (a 403 before 2026-10-16 04:10Z, a
-- parse timeout, a size cap since #1347, the flag): that cause is Unverified here, and only the provenance
-- log lines of the time can name the builder for a row whose bytes were since replaced.
-- When: a row's created_at is its insert and updated_at its last ORM update of any column (null until one),
-- so neither dates the excerpt itself: a forced precompute may have replaced an in-window excerpt, and
-- another column's update moves updated_at. Both are bucketed against the CI-derived marks (tasks/todo.md
-- E28; tasks/review-evidence/e28-native-sections-2026-10-15/README.md): the last native eval report
-- (2026-10-04 09:29Z), the first all-regex one (2026-10-07 19:06Z) and #1350's deploy (2026-10-16 04:10Z).
-- The onset between the first two is unmeasured, hence its own bucket.
-- Repair reach (founder-held, E28 (b)): with_summary counts filings with a stored summary; latest_of_form
-- counts filings no newer stored filing of their company and form follows (filing_date, then id). The forced
-- precompute (precompute_service.precompute_one, #1585) reaches only the latest filing of a ticker and form,
-- resolved from SEC by report date, so latest_of_form is an upper bound on what it can repair.
-- Read-only: one REPEATABLE READ READ ONLY transaction; 120 s per statement, 10 s for a lock. Tables:
-- filing_content_cache, filings, summaries (no user, auth or billing table). Cost: filing_content_cache once
-- (each excerpt's first 64 characters, which PostgreSQL may detoast whole to take), filings once and again
-- per row through ix_filings_company_type_date, summaries per row through uq_summaries_filing_id. Output:
-- counts by form, builder and bucket; no accession, ticker, id or text.
-- The openings, the CASE's arms, the marks and the output columns are pinned by
-- backend/tests/unit/test_excerpt_source_cohort_sql.py; nothing runs this file in CI (its rehearsal is on a local
-- PostgreSQL, recorded in its PR).
-- Retire: the session that closes E28 (b) deletes this file and its test in that records PR.
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout = '120s';
SET LOCAL lock_timeout = '10s';

\echo '0. Session: this transaction is read-only and bounded.'
SELECT current_setting('transaction_read_only') AS read_only,
       current_setting('transaction_isolation') AS isolation,
       current_setting('statement_timeout') AS statement_timeout,
       current_setting('lock_timeout') AS lock_timeout;

\echo '1. Stored excerpts by form, builder (opening), and the buckets their created_at and last write fall in;'
\echo '   then each builder by last write, then each builder (form, created or last_written read all).'
\echo '   Buckets: before (< 10-04 09:29Z), onset (to 10-07 19:06Z), window (to 10-16 04:10Z), after.'
\echo '   One row per filing and one filing per accession, so excerpts = accessions: a check, not a dedupe.'
\echo '   label_before_native and unclassified are Unverified: their builder is not named by their bytes, and no'
\echo '   builder names why it fell back (a 403, a parse timeout, the size cap, the flag): that cause is Unverified.'
WITH marks AS (
    SELECT timestamptz '2026-10-04 09:29:00+00' AS last_native_report,
           timestamptz '2026-10-07 19:06:00+00' AS first_regex_report,
           timestamptz '2026-10-16 04:10:00+00' AS fix_deployed
),
openings AS (
    SELECT c.filing_id,
           f.accession_number,
           upper(btrim(f.filing_type)) AS form,
           f.filing_type AS filing_type,
           f.company_id,
           f.filing_date,
           c.created_at,
           COALESCE(c.updated_at, c.created_at) AS last_write,
           CASE
               WHEN c.critical_excerpt IS NULL OR substr(c.critical_excerpt, 1, 1) = '' THEN 'none'
               WHEN substr(c.critical_excerpt, 1, 52) = E'\n\n' || repeat('=', 50) THEN 'regex_targeted'
               WHEN substr(c.critical_excerpt, 1, 64) LIKE 'RISK & NARRATIVE CONTEXT (recovered from filing):' || E'\n%'
                 OR substr(c.critical_excerpt, 1, 64) LIKE 'FINANCIAL & MD&A CONTEXT (recovered from filing):' || E'\n%'
                   THEN 'regex_recovered'
               WHEN substr(c.critical_excerpt, 1, 64) LIKE ANY (ARRAY[
                   'ITEM 8 - FINANCIAL STATEMENTS AND SUPPLEMENTARY DATA:' || E'\n%',
                   'ITEM 7 - MANAGEMENT''S DISCUSSION AND ANALYSIS:' || E'\n%',
                   'ITEM 1A - RISK FACTORS:' || E'\n%',
                   'ITEM 1 - FINANCIAL STATEMENTS:' || E'\n%',
                   'ITEM 2 - MANAGEMENT''S DISCUSSION AND ANALYSIS:' || E'\n%',
                   'ITEM 18 - FINANCIAL STATEMENTS:' || E'\n%',
                   'ITEM 5 - OPERATING AND FINANCIAL REVIEW AND PROSPECTS:' || E'\n%',
                   'ITEM 3.D - RISK FACTORS:' || E'\n%'
               ]) THEN CASE WHEN c.created_at >= timestamptz '2026-06-15 00:00:00+00' THEN 'native'
                            ELSE 'label_before_native' END
               ELSE 'unclassified'
           END AS builder
    FROM filing_content_cache c
    JOIN filings f ON f.id = c.filing_id
),
bucketed AS (
    SELECT o.*,
           CASE WHEN o.created_at < m.last_native_report THEN '1 before'
                WHEN o.created_at < m.first_regex_report THEN '2 onset'
                WHEN o.created_at < m.fix_deployed THEN '3 window'
                ELSE '4 after' END AS created,
           CASE WHEN o.last_write < m.last_native_report THEN '1 before'
                WHEN o.last_write < m.first_regex_report THEN '2 onset'
                WHEN o.last_write < m.fix_deployed THEN '3 window'
                ELSE '4 after' END AS last_written,
           EXISTS (SELECT 1 FROM summaries s WHERE s.filing_id = o.filing_id) AS with_summary,
           NOT EXISTS (
               SELECT 1 FROM filings newer
               WHERE newer.company_id = o.company_id
                 AND newer.filing_type = o.filing_type
                 AND (newer.filing_date, newer.id) > (o.filing_date, o.filing_id)
           ) AS latest_of_form
    FROM openings o CROSS JOIN marks m
)
SELECT COALESCE(form, 'all') AS form, builder, COALESCE(created, 'all') AS created,
       COALESCE(last_written, 'all') AS last_written,
       count(*) AS excerpts,
       count(DISTINCT accession_number) AS accessions,
       count(*) FILTER (WHERE with_summary) AS with_summary,
       count(*) FILTER (WHERE latest_of_form) AS latest_of_form,
       count(*) FILTER (WHERE with_summary AND latest_of_form) AS with_summary_and_latest
FROM bucketed
GROUP BY GROUPING SETS ((form, builder, created, last_written), (builder, last_written), (builder))
ORDER BY GROUPING(form, created, last_written), form, builder, created, last_written;

COMMIT;
