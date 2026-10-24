-- Detection: the cohorts for the production data repairs the founder approved on 2026-10-24: F49's
-- relabel apply, #1549's quarterly repair, F61 call 2 (non-USD force-sync, then the repair) and
-- #1548's re-walks. It names companies and filings and changes nothing.
-- Retire: the engineering session that runs those repairs deletes this file in the records PR that
-- closes F49 and F61 call 2 in tasks/todo.md, after the last detection-sql run the repairs need, and
-- by 2026-11-30 at the latest: set 6's bounds describe one deploy, and every set goes stale as the
-- repairs land.
--
-- Read-only: one REPEATABLE READ READ ONLY transaction, so the six sets share one snapshot. Tables:
-- companies, filings, financial_fact, summaries. Each statement gets 120 s and waits at most 10 s for
-- a lock (SET LOCAL below; the step's PGOPTIONS allow 600 s). A failure stops this file, and under
-- the step's set -e the files after it do not run. Cost per statement: set 1 reads financial_fact
-- once; set 2 its current FY rows once (one scan, materialized), and each listed company's rows
-- through ix_financial_fact_company_id; set 3 financial_fact at most three times (to find the non-USD
-- companies, then their rows and USD twins); set 4 financial_fact and filings once each; set 5
-- summaries joined to filings once, and financial_fact only through ix_financial_fact_accession and
-- ix_financial_fact_company_id; set 6 companies and filings once, and financial_fact once for its
-- 20-F/40-F rows. A list stops at 200 rows, and each row carries its set's full count (of_n), so a
-- cut list shows.
-- JSON: -> and ->> raise for a whole json value holding a NUL or a lone-surrogate escape, so set 2
-- reads provenance and set 5 reads xbrl_data after rewriting a NUL or any surrogate escape to the
-- escape of U+FFFD (same length; nothing else moves), as #1532 did. Set 3 matches provenance as text
-- and parses nothing. A filed_at that does not spell a date (YYYY-MM-DD) reads as unknown; a day past
-- its month's end rolls into the next month instead of raising. Patterns assume
-- standard_conforming_strings = on (the default).
--
-- Bounds: quarterly_fact_repair.py MAX_COMPANY_FACTS = 10000. The quarterly repair and its audited
-- rollback (the only undo of a relabel apply) both refuse a company with more rows than that.
-- "cf FY row": source 'companyfacts', no filing owner, a raw tag, fiscal_period 'FY', current: the
-- rows _calendar_relabels can relabel. year_offset = year(period_end) - fiscal_year: 0 names a year
-- by the calendar year it ends in, 1 by the year before (Target, Home Depot, J&J).
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout = '120s';
SET LOCAL lock_timeout = '10s';

\echo '0. Session: this transaction is read-only and bounded.'
SELECT current_setting('transaction_read_only') AS read_only,
       current_setting('transaction_isolation') AS isolation,
       current_setting('statement_timeout') AS statement_timeout,
       current_setting('lock_timeout') AS lock_timeout;

\echo '1. Companies within 20% of the 10,000-row bound of the quarterly repair and its rollback, and JNJ'
\echo '   (F49: a rollback of its relabel is refused above it). headroom < 0: both refuse it now; the'
\echo '   repair''s inserts shrink headroom, and a rollback runs on the larger count.'
WITH counts AS (
    SELECT ff.company_id, count(*) AS facts,
           count(*) FILTER (WHERE ff.filing_id IS NULL) AS no_filing_owner,
           count(*) FILTER (WHERE ff.filing_id IS NOT NULL AND ff.fiscal_period = 'FY') AS filing_owned_fy,
           count(*) FILTER (WHERE ff.is_latest) AS current_rows
    FROM financial_fact ff
    GROUP BY ff.company_id
)
SELECT c.ticker, c.id AS company_id, COALESCE(t.facts, 0) AS facts, 10000 - COALESCE(t.facts, 0) AS headroom,
       COALESCE(t.no_filing_owner, 0) AS no_filing_owner, COALESCE(t.filing_owned_fy, 0) AS filing_owned_fy,
       COALESCE(t.current_rows, 0) AS current_rows, count(*) OVER () AS of_n
FROM companies c
LEFT JOIN counts t ON t.company_id = c.id
WHERE COALESCE(t.facts, 0) >= 8000 OR c.ticker = 'JNJ'
ORDER BY facts DESC, c.ticker, c.id
LIMIT 200;

\echo '2. Quarterly-repair candidates (#1549): a company with current cf FY durations and any of: a cf FY'
\echo '   balance older than its oldest cf FY duration end and not under expected_year (opening_off > 0); a'
\echo '   cf FY duration ending in January or February, or in March on a 20-F row (march_20f); or a newest'
\echo '   cf FY year end filed over 180 days after it (newest_filed_days > 180). opening_off: such balances.'
\echo '   expected_year approximates the year the writer now names: whole years back from the oldest cf FY'
\echo '   duration end (year_ending_on), else the calendar year the balance ends in. Where whole years do'
\echo '   not reach, the writer first takes the year the balance''s own timely annual report gave it'
\echo '   (reported_fiscal_year), which the row does not store, so opening_off may count a balance whose'
\echo '   stored year the writer would give it too; the repair preview decides. oldest_off_end, stored_year'
\echo '   -> expected_year is the oldest of them, off_ends how many ends they sit at. n0: current cf FY'
\echo '   durations ending January to March under the calendar year they end in, the most a repair of a late'
\echo '   chain relabels; a preview that relabels some but not all of them repairs it in part. owned_n0:'
\echo '   current filing-owned FY durations of that kind, which the repair never moves; a preview that'
\echo '   relabels any n0 row while owned_n0 > 0 leaves the chain mixed (#1549''s Target-shaped partial'
\echo '   case). Both keep the company out of the apply. newest_filed_days: days from the newest cf duration'
\echo '   end to its filing, blank when a filing-owned row holds a later year end (the cf row is then a'
\echo '   comparative) or the filing date is unknown. facts > 10000: the repair refuses the company. Rows'
\echo '   with opening_off or n0 above 0, or newest_filed_days above 180, come first; then the rest, listed'
\echo '   only for a January or February year end or a March one on a 20-F row; each group by ticker.'
WITH params AS (
    SELECT '\\u(0000|[dD][89a-fA-F][0-9a-fA-F]{2})'::text AS json_hazard
), fy AS MATERIALIZED (
    SELECT ff.company_id, ff.concept, ff.period_start, ff.period_end, ff.form, ff.fiscal_year,
           ff.filing_id IS NOT NULL AS filing_owned,
           ff.source = 'companyfacts' AND ff.filing_id IS NULL AND ff.raw_tag IS NOT NULL AS is_cf,
           extract(year FROM ff.period_end)::int - ff.fiscal_year AS year_offset,
           CASE WHEN ff.source = 'companyfacts' AND ff.filing_id IS NULL AND ff.raw_tag IS NOT NULL
                THEN (CASE WHEN ff.provenance::text ~ p.json_hazard
                           THEN regexp_replace(ff.provenance::text, p.json_hazard, '\\ufffd', 'g')::json
                           ELSE ff.provenance END) ->> 'filed_at' END AS filed_text
    FROM financial_fact ff
    CROSS JOIN params p
    WHERE ff.fiscal_period = 'FY' AND ff.is_latest AND ff.fiscal_year IS NOT NULL
), durations AS (
    SELECT fy.*,
           CASE WHEN fy.filed_text ~ '^(19|20)[0-9]{2}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])'
                THEN make_date(left(fy.filed_text, 4)::int, substr(fy.filed_text, 6, 2)::int, 1)
                     + (substr(fy.filed_text, 9, 2)::int - 1) END AS filed_on
    FROM fy
    WHERE fy.is_cf AND fy.period_start IS NOT NULL
), chain AS (
    SELECT d.company_id,
           count(*) AS durations,
           string_agg(DISTINCT to_char(d.period_end, 'MM'), ',') AS year_end_months,
           count(*) FILTER (WHERE d.year_offset = 0 AND extract(month FROM d.period_end) IN (1, 2, 3)) AS n0,
           bool_or(extract(month FROM d.period_end) IN (1, 2)) AS jan_feb_end,
           bool_or(extract(month FROM d.period_end) = 3 AND d.form LIKE '20-F%') AS march_20f,
           min(d.period_end) AS oldest_end,
           (array_agg(d.fiscal_year ORDER BY d.period_end, d.fiscal_year))[1] AS oldest_fy,
           max(d.period_end) AS newest_end,
           (array_agg(d.filed_on ORDER BY d.period_end DESC, d.filed_on NULLS LAST))[1] AS newest_filed_on
    FROM durations d
    GROUP BY d.company_id
), owned AS (
    SELECT fy.company_id, max(fy.period_end) AS newest_owned_end,
           count(*) FILTER (WHERE fy.year_offset = 0 AND extract(month FROM fy.period_end) IN (1, 2, 3))
               AS owned_n0
    FROM fy
    WHERE fy.filing_owned AND fy.period_start IS NOT NULL
    GROUP BY fy.company_id
), opening AS (
    SELECT i.company_id, count(*) AS opening_off, count(DISTINCT i.period_end) AS off_ends,
           (array_agg(i.period_end ORDER BY i.period_end, i.concept))[1] AS oldest_off_end,
           (array_agg(i.fiscal_year ORDER BY i.period_end, i.concept))[1] AS stored_year,
           (array_agg(i.expected_year ORDER BY i.period_end, i.concept))[1] AS expected_year
    FROM (
        SELECT b.*,
               CASE WHEN abs(b.days - b.years * 365.25) <= 18 THEN b.oldest_fy - b.years
                    ELSE extract(year FROM b.period_end)::int END AS expected_year
        FROM (
            SELECT fy.company_id, fy.concept, fy.period_end, fy.fiscal_year, chain.oldest_fy,
                   chain.oldest_end - fy.period_end AS days,
                   round((chain.oldest_end - fy.period_end) / 365.25)::int AS years
            FROM fy
            JOIN chain ON chain.company_id = fy.company_id AND fy.period_end < chain.oldest_end
            WHERE fy.is_cf AND fy.period_start IS NULL
        ) b
    ) i
    WHERE i.fiscal_year <> i.expected_year
    GROUP BY i.company_id
), candidates AS (
    SELECT c.ticker, c.id AS company_id, chain.year_end_months, chain.durations, chain.n0,
           COALESCE(w.owned_n0, 0) AS owned_n0, COALESCE(o.opening_off, 0) AS opening_off,
           o.oldest_off_end, o.stored_year, o.expected_year, COALESCE(o.off_ends, 0) AS off_ends,
           chain.newest_end,
           CASE WHEN w.newest_owned_end IS NULL OR w.newest_owned_end <= chain.newest_end
                THEN chain.newest_filed_on - chain.newest_end END AS newest_filed_days,
           chain.jan_feb_end, chain.march_20f, c.facts_synced_at
    FROM chain
    JOIN companies c ON c.id = chain.company_id
    LEFT JOIN opening o ON o.company_id = chain.company_id
    LEFT JOIN owned w ON w.company_id = chain.company_id
)
SELECT k.ticker, k.company_id, k.year_end_months, k.durations, k.n0, k.owned_n0, k.opening_off,
       k.oldest_off_end, k.stored_year, k.expected_year, k.off_ends, k.newest_end, k.newest_filed_days,
       k.march_20f,
       (SELECT count(*) FROM financial_fact x WHERE x.company_id = k.company_id) AS facts,
       k.facts_synced_at, k.of_n
FROM (SELECT candidates.*, count(*) OVER () AS of_n
      FROM candidates
      WHERE candidates.opening_off > 0 OR candidates.jan_feb_end OR candidates.march_20f
         OR candidates.newest_filed_days > 180
      ORDER BY (candidates.opening_off > 0 OR candidates.n0 > 0
                OR COALESCE(candidates.newest_filed_days, 0) > 180) DESC,
               candidates.ticker, candidates.company_id
      LIMIT 200) k
ORDER BY (k.opening_off > 0 OR k.n0 > 0 OR COALESCE(k.newest_filed_days, 0) > 180) DESC,
         k.ticker, k.company_id;

\echo '3. Non-USD reporters (F61 call 2): a row in a currency other than USD. cf_native = 0: no sync has'
\echo '   read the native lists (force-sync it); after a forced sync it stays 0 only where the series reads'
\echo '   USD (a filer that switched to USD) or the filer reports under IFRS. usd_twins_current: current'
\echo '   USD rows at the concept, period end and fiscal period of a current native row that a companyfacts'
\echo '   sync stored (source companyfacts, no filing owner, a raw tag). A force-sync that reads the native'
\echo '   lists again demotes them (currency.py demote_convenience_rows), so after a correct one it reads 0;'
\echo '   while cf_native = 0 it reads 0 too. A USD row beside only a per-filing native row is not counted:'
\echo '   the sync demotes one at a concept its payload carries, but not at a concept only the per-filing'
\echo '   writer stores, so counting it would keep the count above 0 after a correct sync.'
\echo '   usd_operand_ratios: current FY ratios with no filing owner whose recorded inputs include USD, or'
\echo '   none recorded (the repair recomputes them after the sync), counted only while a current native row'
\echo '   that a companyfacts sync stored remains, else blank (a series read in USD, or one no sync has read'
\echo '   natively yet). After a correct sync and the repair it reads 0 or blank, except in two shapes. A'
\echo '   ratio at a period the native batch computes none for stays current and counted, as neither the sync'
\echo '   nor the repair replaces it: a filer that switched from USD keeps its USD-derived ratios before the'
\echo '   switch (right for those years), and so does any year whose native items the collector drops. And a'
\echo '   filer that switched to USD reads a count, not blank, while a native row stays current at a concept'
\echo '   its USD filings never tag (the sync demotes only its own concepts). ifrs_rows > 0 with'
\echo '   cf_native = 0: an IFRS filer, which the sync stores nothing for and the repair refuses.'
WITH native AS MATERIALIZED (
    SELECT DISTINCT ff.company_id
    FROM financial_fact ff
    WHERE ff.unit ~ '^[A-Z]{3}(/shares)?$' AND ff.unit NOT IN ('USD', 'USD/shares')
), stats AS (
    SELECT ff.company_id,
           string_agg(DISTINCT ff.unit, ',' ORDER BY ff.unit)
               FILTER (WHERE ff.unit ~ '^[A-Z]{3}(/shares)?$' AND ff.unit NOT IN ('USD', 'USD/shares'))
               AS native_units,
           count(*) FILTER (WHERE ff.source = 'companyfacts' AND ff.unit ~ '^[A-Z]{3}(/shares)?$'
                              AND ff.unit NOT IN ('USD', 'USD/shares')) AS cf_native,
           CASE WHEN bool_or(ff.is_latest AND ff.source = 'companyfacts' AND ff.filing_id IS NULL
                             AND ff.raw_tag IS NOT NULL AND ff.unit ~ '^[A-Z]{3}(/shares)?$'
                             AND ff.unit NOT IN ('USD', 'USD/shares'))
                THEN count(*) FILTER (WHERE ff.is_latest AND ff.unit = 'pure' AND ff.filing_id IS NULL
                                        AND ff.fiscal_period = 'FY' AND ff.source IN ('derived', 'companyfacts')
                                        AND ff.raw_tag IS NULL
                                        AND (ff.provenance IS NULL OR ff.provenance::text = 'null'
                                             OR ff.provenance::text ~ '"unit"\s*:\s*"USD"')) END AS usd_operand_ratios,
           count(*) FILTER (WHERE ff.raw_tag LIKE 'ifrs-full:%') AS ifrs_rows,
           count(*) AS facts
    FROM financial_fact ff
    WHERE ff.company_id IN (SELECT native.company_id FROM native)
    GROUP BY ff.company_id
), twins AS (
    SELECT u.company_id, count(*) AS usd_twins_current
    FROM financial_fact u
    WHERE u.company_id IN (SELECT native.company_id FROM native)
      AND u.is_latest AND u.unit IN ('USD', 'USD/shares')
      AND EXISTS (SELECT 1 FROM financial_fact n
                  WHERE n.company_id = u.company_id AND n.concept = u.concept
                    AND n.period_end = u.period_end AND n.fiscal_period = u.fiscal_period
                    AND n.is_latest AND n.source = 'companyfacts' AND n.filing_id IS NULL
                    AND n.raw_tag IS NOT NULL AND n.unit <> u.unit
                    AND n.unit ~ CASE WHEN u.unit = 'USD' THEN '^[A-Z]{3}$' ELSE '^[A-Z]{3}/shares$' END)
    GROUP BY u.company_id
)
SELECT c.ticker, c.id AS company_id, c.facts_synced_at, s.native_units, s.cf_native,
       COALESCE(t.usd_twins_current, 0) AS usd_twins_current, s.usd_operand_ratios, s.ifrs_rows, s.facts,
       count(*) OVER () AS of_n
FROM stats s
JOIN companies c ON c.id = s.company_id
LEFT JOIN twins t ON t.company_id = s.company_id
ORDER BY c.ticker, c.id
LIMIT 200;

\echo '4. Sync candidates whose native currency may never have been read: a 20-F or 40-F (in companyfacts'
\echo '   or the filing list) and no non-USD row, or a companyfacts sync stamp and no companyfacts row (a'
\echo '   10-K in CAD, or an IFRS filer).'
WITH facts AS (
    SELECT ff.company_id,
           bool_or(ff.unit ~ '^[A-Z]{3}(/shares)?$' AND ff.unit NOT IN ('USD', 'USD/shares')) AS has_native,
           count(*) FILTER (WHERE ff.source = 'companyfacts') AS cf_rows,
           NULLIF(concat_ws(',', CASE WHEN bool_or(ff.form LIKE '20-F%') THEN '20-F' END,
                                 CASE WHEN bool_or(ff.form LIKE '40-F%') THEN '40-F' END), '') AS fact_forms
    FROM financial_fact ff
    GROUP BY ff.company_id
), listed AS (
    SELECT f.company_id, string_agg(DISTINCT f.filing_type, ',' ORDER BY f.filing_type) AS filing_forms
    FROM filings f
    WHERE f.filing_type ~ '^(20|40)-F'
    GROUP BY f.company_id
)
SELECT c.ticker, c.id AS company_id, c.facts_synced_at, x.fact_forms, l.filing_forms,
       COALESCE(x.cf_rows, 0) AS cf_rows, count(*) OVER () AS of_n
FROM companies c
LEFT JOIN facts x ON x.company_id = c.id
LEFT JOIN listed l ON l.company_id = c.id
WHERE NOT COALESCE(x.has_native, false)
  AND (x.fact_forms IS NOT NULL OR l.filing_forms IS NOT NULL
       OR (c.facts_synced_at IS NOT NULL AND COALESCE(x.cf_rows, 0) = 0))
ORDER BY c.ticker, c.id
LIMIT 200;

\echo '5. Summaries whose filing records no reporting currency (#1532''s "none recorded" rows, by its rule):'
\echo '   xbrl_data names none and no financial_fact row at the accession has a three-letter unit.'
WITH params AS (
    SELECT '\\u(0000|[dD][89a-fA-F][0-9a-fA-F]{2})'::text AS json_hazard
), summary_currency AS MATERIALIZED (
    SELECT s.id AS summary_id, f.company_id, f.accession_number, f.filing_type, f.filing_date,
           f.xbrl_data IS NULL AS no_xbrl_data,
           NULLIF(upper(btrim(
               (CASE WHEN f.xbrl_data::text ~ p.json_hazard
                     THEN regexp_replace(f.xbrl_data::text, p.json_hazard, '\\ufffd', 'g')::json
                     ELSE f.xbrl_data END) ->> 'reporting_currency')), '') AS xbrl_currency
    FROM summaries s
    JOIN filings f ON f.id = s.filing_id
    CROSS JOIN params p
), none_recorded AS (
    SELECT sc.*, count(*) OVER () AS of_n
    FROM summary_currency sc
    WHERE sc.xbrl_currency IS NULL
      AND NOT EXISTS (SELECT 1 FROM financial_fact ff
                      WHERE ff.accession = sc.accession_number AND ff.unit ~ '^[A-Z]{3}$')
    ORDER BY sc.filing_date, sc.summary_id
    LIMIT 200
)
SELECT c.ticker, n.summary_id, n.filing_type, (n.filing_date AT TIME ZONE 'UTC')::date AS filing_date,
       n.accession_number, n.no_xbrl_data,
       (SELECT count(*) FROM financial_fact ff WHERE ff.accession = n.accession_number) AS facts_at_accession,
       (SELECT count(*) FROM financial_fact ff
        WHERE ff.company_id = n.company_id AND ff.source = 'companyfacts') AS company_cf_rows,
       c.facts_synced_at, n.of_n
FROM none_recorded n
JOIN companies c ON c.id = n.company_id
ORDER BY c.ticker, n.filing_date, n.summary_id;

\echo '6. #1548 re-walk cases: a company whose history stamp an old revision may have written (a walk of'
\echo '   10-K/10-Q only) and which is, was or may be a foreign issuer. why: it holds a 20-F, 40-F or 6-K'
\echo '   row (the migration cleared such stamps, so one is stamped again or gained the row later), it holds'
\echo '   no filing row (cleared too, as unknown), or its companyfacts name a 20-F or 40-F with no such row'
\echo '   (a former foreign issuer, which the migration skipped). stamped: before the migration (UPDATE 159'
\echo '   at 02:32:20.74 UTC on 2026-10-24); while an old revision served (until the worker took traffic at'
\echo '   02:32:37 and the service at 02:33:06); or by an old request still in flight, within the 600 s'
\echo '   request timeout of both (to 02:43:07). A stamp before the migration is listed only with a why'
\echo '   above. One from 02:32:20 to 02:43:07 is listed whatever the company holds, why reading "stamped in'
\echo '   the rollout window" where none applies: a company the migration cleared for holding no filing row'
\echo '   may since hold the 10-K/10-Q rows an old walk stored, and then nothing stored tells it from a'
\echo '   domestic company. The forms key of the walk''s log line tells an old walk from a new one. A later'
\echo '   stamp came from a walk that listed 20-F and 40-F, so it is not listed.'
WITH params AS (
    SELECT timestamptz '2026-10-24 02:32:20+00' AS migration_at,
           timestamptz '2026-10-24 02:33:07+00' AS old_serving_until,
           timestamptz '2026-10-24 02:43:07+00' AS old_in_flight_until
), held AS (
    SELECT f.company_id,
           string_agg(DISTINCT f.filing_type, ',' ORDER BY f.filing_type)
               FILTER (WHERE f.filing_type IN ('20-F', '20-F/A', '40-F', '40-F/A', '6-K', '6-K/A'))
               AS foreign_filings
    FROM filings f
    GROUP BY f.company_id
), named AS (
    SELECT ff.company_id, string_agg(DISTINCT ff.form, ',' ORDER BY ff.form) AS cf_foreign_forms
    FROM financial_fact ff
    WHERE ff.form ~ '^(20|40)-F'
    GROUP BY ff.company_id
), cases AS (
    SELECT c.ticker, c.id AS company_id, c.history_backfilled_at,
           CASE WHEN c.history_backfilled_at < p.migration_at THEN 'before the migration'
                WHEN c.history_backfilled_at < p.old_serving_until THEN 'while an old revision served'
                ELSE 'old request in flight' END AS stamped,
           CASE WHEN h.foreign_filings IS NOT NULL THEN 'holds a foreign filing'
                WHEN h.company_id IS NULL THEN 'holds no filing'
                WHEN x.cf_foreign_forms IS NOT NULL THEN 'former foreign issuer'
                ELSE 'stamped in the rollout window' END AS why,
           h.foreign_filings, x.cf_foreign_forms
    FROM companies c
    CROSS JOIN params p
    LEFT JOIN held h ON h.company_id = c.id
    LEFT JOIN named x ON x.company_id = c.id
    WHERE c.history_backfilled_at IS NOT NULL AND c.history_backfilled_at < p.old_in_flight_until
      AND (c.history_backfilled_at >= p.migration_at
           OR h.foreign_filings IS NOT NULL OR h.company_id IS NULL OR x.cf_foreign_forms IS NOT NULL)
)
SELECT k.ticker, k.company_id, k.history_backfilled_at, k.stamped, k.why, k.foreign_filings,
       k.cf_foreign_forms, count(*) OVER () AS of_n
FROM cases k
ORDER BY k.history_backfilled_at, k.ticker, k.company_id
LIMIT 200;

COMMIT;
