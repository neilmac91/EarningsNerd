-- Detection: the size of WP5a-B's rebuild wave (docs/mpa-improvements/coherence.md §1.6, "As shipped (WP5a-B)").
-- It names no company and changes nothing.
-- Retire: the records PR that reports this query's run deletes this file.
--
-- WP5a-B's annual dataset reads a year's own annual report from any non-current fiscal-year row in the figure's cell
-- (backend/app/services/trend_analysis/first_reports.py), not only the history rows a sync stores after #1682: a
-- demoted former winner or a row the per-filing writer stored holds the cell alike. So a company whose rows already
-- hold such a value changes at B's deploy, without a sync, and every saved annual analysis of it with the year in its
-- window changes fingerprint: its narrative regenerates once at next open (unmetered), and its saved PDF answers 409
-- until the analysis is re-run.
--
-- Population: a cell is (company, concept, fiscal year) for a reported concept (not the six calculated ones), its
-- current FY row (is_latest), and a non-current FY row in the same concept, period end, unit and span (a missing start
-- matches only on a balance) at another accession, whose accession is an annual report's (an FY row of an annual form
-- is stored there, or its filing row is an annual report's, as the reader admits either) and whose latest FY row stored
-- there ends on the cell's period end, not withheld (validation unavailable), finite, and more than 0.1% of its own
-- value off the current row (any difference where it is 0). That is an upper bound on the cells B gives evidence: the
-- reader also ranks the figure's own filing among the year's own reports and drops a filing whose filing row reports a
-- later year, and both only remove cells.
-- Growth n/m and the inputs' evidence follow these cells, so they add no company.
--
-- Read-only: one REPEATABLE READ READ ONLY transaction, so every set shares one snapshot. Each statement gets 120 s
-- and waits at most 10 s for a lock. Cost: the FY rows of financial_fact once (materialized), trend_analysis once.
-- JSON: a provenance value holding a NUL or a lone-surrogate escape is rewritten to the escape of U+FFFD before it is
-- parsed, as #1532 did.
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout = '120s';
SET LOCAL lock_timeout = '10s';

\echo '0. Session: this transaction is read-only and bounded.'
SELECT current_setting('transaction_read_only') AS read_only,
       current_setting('transaction_isolation') AS isolation,
       current_setting('statement_timeout') AS statement_timeout,
       current_setting('lock_timeout') AS lock_timeout;

\echo '1. Cells (company x concept x fiscal year) that carry evidence at B''s deploy, an upper bound, and their companies;'
\echo '   saved annual analyses whose window holds one: each regenerates its narrative once at next open (unmetered),'
\echo '   and its saved PDF answers 409 until it is re-run.'
WITH params AS (
    SELECT ARRAY['10-K', '10-K/A', '20-F', '20-F/A', '40-F', '40-F/A']::text[] AS annual_forms,
           ARRAY['net_margin', 'operating_margin', 'gross_margin', 'free_cash_flow', 'working_capital',
                 'current_ratio']::text[] AS calculated,
           ARRAY['total_assets', 'cash_and_equivalents', 'shareholders_equity', 'long_term_debt', 'current_assets',
                 'current_liabilities']::text[] AS balances,
           0.001::numeric AS tolerance,
           '\\u(0000|[dD][89a-fA-F][0-9a-fA-F]{2})'::text AS json_hazard
), fy AS MATERIALIZED (
    SELECT ff.company_id, ff.concept, ff.fiscal_year, ff.period_start, ff.period_end, ff.unit, ff.value, ff.form,
           ff.is_latest, replace(ff.accession, '-', '') AS acc,
           CASE WHEN ff.provenance IS NULL OR ff.provenance::text = 'null' THEN NULL
                WHEN ff.provenance::text ~ p.json_hazard
                THEN regexp_replace(ff.provenance::text, p.json_hazard, '\\ufffd', 'g')::jsonb
                ELSE ff.provenance::jsonb END AS pv
    FROM financial_fact ff CROSS JOIN params p
    WHERE ff.fiscal_period = 'FY'
), annual AS (
    SELECT DISTINCT fy.company_id, fy.acc FROM fy CROSS JOIN params p WHERE fy.form = ANY (p.annual_forms)
    UNION
    SELECT f.company_id, replace(f.accession_number, '-', '') FROM filings f CROSS JOIN params p
    WHERE f.filing_type = ANY (p.annual_forms)
), own_end AS (
    SELECT fy.company_id, fy.acc, max(fy.period_end) AS end_date
    FROM fy JOIN annual a ON a.company_id = fy.company_id AND a.acc = fy.acc CROSS JOIN params p
    WHERE fy.form = ANY (p.annual_forms) OR fy.form IS NULL
    GROUP BY fy.company_id, fy.acc
), cells AS MATERIALIZED (
    SELECT DISTINCT c.company_id, c.concept, c.fiscal_year
    FROM fy c
    JOIN fy r ON r.company_id = c.company_id AND r.concept = c.concept AND r.period_end = c.period_end
             AND r.unit = c.unit AND NOT r.is_latest AND r.acc <> c.acc
    JOIN own_end o ON o.company_id = r.company_id AND o.acc = r.acc AND o.end_date = r.period_end
    CROSS JOIN params p
    WHERE c.is_latest AND c.fiscal_year IS NOT NULL AND NOT (c.concept = ANY (p.calculated))
      AND (r.period_start = c.period_start OR (r.period_start IS NULL AND c.period_start IS NULL
                                               AND c.concept = ANY (p.balances)))
      AND coalesce(r.pv ->> 'validation', '') <> 'unavailable'
      AND r.value::text NOT IN ('NaN', 'Infinity', '-Infinity')
      AND c.value::text NOT IN ('NaN', 'Infinity', '-Infinity')
      AND CASE WHEN r.value = 0 THEN c.value <> 0 ELSE abs(c.value - r.value) > p.tolerance * abs(r.value) END
), saved AS (
    SELECT DISTINCT ta.id, ta.company_id
    FROM trend_analysis ta
    WHERE ta.mode = 'annual' AND ta.period_key ~ '^FY[0-9]{4}\.\.FY[0-9]{4}$'
      AND EXISTS (SELECT 1 FROM cells cell
                  WHERE cell.company_id = ta.company_id
                    AND cell.fiscal_year BETWEEN substring(ta.period_key FROM 3 FOR 4)::int
                                             AND substring(ta.period_key FROM 11 FOR 4)::int)
)
SELECT (SELECT count(*) FROM cells) AS cells,
       (SELECT count(DISTINCT company_id) FROM cells) AS companies,
       (SELECT count(*) FROM saved) AS saved_annual_analyses,
       (SELECT count(DISTINCT company_id) FROM saved) AS companies_with_saved_analyses;

COMMIT;
