-- Detection: financial companies' revenue as the database holds it, before and after E264's resync, preview and
-- cleanup (tasks/todo.md, E264). Since #1913 (deployed 2026-11-01) a financial filer's (SIC 6000-6799)
-- companyfacts revenue is its reported total, chosen by facts/fi_revenue.py::financial_revenue_tags, never the
-- ASC 606 fee line the generic tag tuple reads first. The rows stored before then keep the old reading until
-- the founder's forced resync and cleanup. A run before the resync is the before, and a run after each step
-- is that step's after; E264's "Check after" reads sets 2 and 4 to 7. The sets: 1 counts the feed's revenue
-- rows (filing_id NULL, source companyfacts) by tag, current or not (the non-current ones are own-report
-- history rows and demoted winners, the database half of the preview's sets D and E); 2 lists the companies
-- whose current revenue carries the fee tag, the list E264 reviews by SIC; 3 counts the calculated rows built
-- on a fee-tag revenue operand (set C); 4 lists the current net margins above 100%; 5 checks each named
-- bank's current fiscal-year revenue against its net interest income plus noninterest income; 6 counts the
-- duplicate current rows and 7 lists them; 8 lists the per-filing revenue rows the old cross-check replaced
-- (set F's database half). The preview itself reads SEC's payloads under the deployed rule, which no SQL can.
-- It names companies and counts rows, and changes nothing.
-- Retire: the records PR that closes E264 deletes this file and the unit test that holds its tags, SIC band
-- and margin scale to the code (backend/tests/unit/test_financial_revenue_detection_sql.py).
--
-- Read-only: one REPEATABLE READ READ ONLY transaction, so the sets share one snapshot. Tables: companies,
-- financial_fact. Each statement gets 120 s and waits at most 10 s for a lock (SET LOCAL below; the step's
-- PGOPTIONS allow 600 s). A failure stops this file, and under the step's set -e the files after it do not
-- run. Cost per statement: each reads companies once for the financial ones, then their financial_fact rows
-- through ix_financial_fact_company_id, filtered by concept (set 6 reads every current row of theirs, set 5
-- the named banks' fiscal-year rows only); sets 3, 4 and 8 parse the provenance of the rows they keep, and
-- sets 3 and 8 read only those whose provenance text names the fee tag or an authoritative check. A list
-- stops at 200 rows, and each row carries its set's full count (of_n), so a cut list shows.
-- financial company: one whose companies.sic, compared as text in byte order (COLLATE "C"), lies from '6000'
-- to '6799', as facts/concepts.py::_is_financial_sic compares it; an empty or NULL code is none.
-- tag: the row's raw_tag without its 'us-gaap:' namespace. fee: facts/fi_revenue.py's FEE_TAG; total: one
-- of its TOTAL_TAGS; other: any other tag, or none. A margin is stored as a percentage (x100, unit pure), so
-- 100 is 100%.
-- JSON: -> and ->> raise for a whole json value holding a NUL or a lone-surrogate escape, so sets 3, 4 and 8
-- read provenance after rewriting a NUL or any surrogate escape to the escape of U+FFFD (same length;
-- nothing else moves), as proxy_form_winners.sql does. Sets 1, 2, 5, 6 and 7 parse no JSON.
-- Patterns assume standard_conforming_strings = on (the default).
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout = '120s';
SET LOCAL lock_timeout = '10s';

\echo '0. Session: this transaction is read-only and bounded.'
SELECT current_setting('transaction_read_only') AS read_only,
       current_setting('transaction_isolation') AS isolation,
       current_setting('statement_timeout') AS statement_timeout,
       current_setting('lock_timeout') AS lock_timeout;

\echo '1. The feed''s revenue rows at financial companies (any unit), by current and tag, then each current''s'
\echo '   total (the row with no class). Non-current rows are own-report history rows and demoted winners.'
\echo '   fy_rows and quarter_rows split the rows by fiscal period; first_fy and last_fy span their fiscal years.'
WITH params AS (
    SELECT '6000'::text AS sic_low, '6799'::text AS sic_high,
           'us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax'::text AS fee_tag,
           ARRAY['us-gaap:RevenuesNetOfInterestExpense', 'us-gaap:Revenues', 'us-gaap:SalesRevenueNet']::text[] AS total_tags
), fin AS MATERIALIZED (
    SELECT c.id
    FROM companies c
    CROSS JOIN params p
    WHERE c.sic <> '' AND c.sic COLLATE "C" BETWEEN p.sic_low AND p.sic_high
), feed AS (
    SELECT ff.company_id, ff.is_latest, ff.fiscal_period, ff.fiscal_year,
           CASE WHEN ff.raw_tag = p.fee_tag THEN 'fee'
                WHEN ff.raw_tag = ANY (p.total_tags) THEN 'total'
                ELSE 'other' END AS class,
           COALESCE(regexp_replace(ff.raw_tag, '^us-gaap:', ''), '(none)') AS tag
    FROM fin
    JOIN financial_fact ff ON ff.company_id = fin.id
    CROSS JOIN params p
    WHERE ff.concept = 'revenue' AND ff.filing_id IS NULL AND ff.source = 'companyfacts'
)
SELECT is_latest AS current, class, tag, count(*) AS rows, count(DISTINCT company_id) AS companies,
       count(*) FILTER (WHERE fiscal_period = 'FY') AS fy_rows,
       count(*) FILTER (WHERE fiscal_period IN ('Q1', 'Q2', 'Q3', 'Q4')) AS quarter_rows,
       min(fiscal_year) AS first_fy, max(fiscal_year) AS last_fy
FROM feed
GROUP BY GROUPING SETS ((is_latest, class, tag), (is_latest))
ORDER BY is_latest DESC, class NULLS LAST, rows DESC, tag;

\echo '2. Financial companies whose current feed revenue carries the fee tag, the most such rows first. fee_fy:'
\echo '   those at a fiscal year. total and other: the same company''s current feed revenue rows of a total tag'
\echo '   and of any other. first_fee_fy and last_fee_fy span the fee rows'' fiscal years. A company whose'
\echo '   choice ends in the fee tag (BLK, TROW, EQIX, NDAQ, O, PNC, ICE outside FY2015) belongs here; review'
\echo '   the rest by SIC.'
WITH params AS (
    SELECT '6000'::text AS sic_low, '6799'::text AS sic_high,
           'us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax'::text AS fee_tag,
           ARRAY['us-gaap:RevenuesNetOfInterestExpense', 'us-gaap:Revenues', 'us-gaap:SalesRevenueNet']::text[] AS total_tags
), fin AS MATERIALIZED (
    SELECT c.id, c.ticker, c.sic
    FROM companies c
    CROSS JOIN params p
    WHERE c.sic <> '' AND c.sic COLLATE "C" BETWEEN p.sic_low AND p.sic_high
), per AS (
    SELECT fin.id, fin.ticker, fin.sic,
           count(*) FILTER (WHERE ff.raw_tag = p.fee_tag) AS fee,
           count(*) FILTER (WHERE ff.raw_tag = p.fee_tag AND ff.fiscal_period = 'FY') AS fee_fy,
           count(*) FILTER (WHERE ff.raw_tag = ANY (p.total_tags)) AS total,
           count(*) FILTER (WHERE ff.raw_tag IS NULL
                               OR (ff.raw_tag <> p.fee_tag AND NOT ff.raw_tag = ANY (p.total_tags))) AS other,
           min(ff.fiscal_year) FILTER (WHERE ff.raw_tag = p.fee_tag) AS first_fee_fy,
           max(ff.fiscal_year) FILTER (WHERE ff.raw_tag = p.fee_tag) AS last_fee_fy
    FROM fin
    JOIN financial_fact ff ON ff.company_id = fin.id
    CROSS JOIN params p
    WHERE ff.concept = 'revenue' AND ff.is_latest AND ff.filing_id IS NULL AND ff.source = 'companyfacts'
    GROUP BY fin.id, fin.ticker, fin.sic
)
SELECT ticker, sic, fee, fee_fy, total, other, first_fee_fy, last_fee_fy, count(*) OVER () AS of_n
FROM per
WHERE fee > 0
ORDER BY fee DESC, ticker, id
LIMIT 200;

\echo '3. Calculated rows (source derived) at financial companies with a fee-tag revenue operand, by concept and'
\echo '   current, then in total (the row with no concept): the revenue quarters a fee row entered and the'
\echo '   margins over it. companies: how many hold them.'
WITH params AS (
    SELECT '6000'::text AS sic_low, '6799'::text AS sic_high,
           'us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax'::text AS fee_tag,
           '\\u(0000|[dD][89a-fA-F][0-9a-fA-F]{2})'::text AS json_hazard
), fin AS MATERIALIZED (
    SELECT c.id
    FROM companies c
    CROSS JOIN params p
    WHERE c.sic <> '' AND c.sic COLLATE "C" BETWEEN p.sic_low AND p.sic_high
), calc AS MATERIALIZED (
    SELECT ff.company_id, ff.concept, ff.is_latest,
           CASE WHEN ff.provenance::text ~ p.json_hazard
                THEN regexp_replace(ff.provenance::text, p.json_hazard, '\\ufffd', 'g')::json
                ELSE ff.provenance END -> 'inputs' AS inputs
    FROM fin
    JOIN financial_fact ff ON ff.company_id = fin.id
    CROSS JOIN params p
    WHERE ff.source = 'derived' AND ff.concept IN ('revenue', 'net_margin', 'operating_margin', 'gross_margin')
      AND strpos(ff.provenance::text, p.fee_tag) > 0
), on_fee AS (
    SELECT k.*
    FROM calc k
    CROSS JOIN params p
    WHERE json_typeof(k.inputs) = 'array'
      AND EXISTS (SELECT 1 FROM json_array_elements(k.inputs) i
                  WHERE i ->> 'concept' = 'revenue' AND i ->> 'raw_tag' = p.fee_tag)
)
SELECT concept, is_latest AS current, count(*) AS rows, count(DISTINCT company_id) AS companies
FROM on_fee
GROUP BY GROUPING SETS ((concept, is_latest), ())
ORDER BY concept NULLS LAST, is_latest DESC;

\echo '4. Current net margins above 100% at financial companies, by company, the most first. on_fee: those whose'
\echo '   revenue operand carries the fee tag. max_margin: the largest, at max_fy and max_fp. all_rows: every'
\echo '   such margin in the cohort.'
WITH params AS (
    SELECT '6000'::text AS sic_low, '6799'::text AS sic_high,
           'us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax'::text AS fee_tag,
           '\\u(0000|[dD][89a-fA-F][0-9a-fA-F]{2})'::text AS json_hazard,
           100::numeric AS full_margin
), fin AS MATERIALIZED (
    SELECT c.id, c.ticker, c.sic
    FROM companies c
    CROSS JOIN params p
    WHERE c.sic <> '' AND c.sic COLLATE "C" BETWEEN p.sic_low AND p.sic_high
), high AS MATERIALIZED (
    SELECT ff.company_id, ff.fiscal_year, ff.fiscal_period, ff.value,
           CASE WHEN ff.provenance::text ~ p.json_hazard
                THEN regexp_replace(ff.provenance::text, p.json_hazard, '\\ufffd', 'g')::json
                ELSE ff.provenance END -> 'inputs' AS inputs
    FROM fin
    JOIN financial_fact ff ON ff.company_id = fin.id
    CROSS JOIN params p
    WHERE ff.concept = 'net_margin' AND ff.is_latest AND ff.value > p.full_margin
), tagged AS (
    SELECT h.company_id, h.fiscal_year, h.fiscal_period, h.value,
           (SELECT i.operand ->> 'raw_tag'
            FROM json_array_elements(CASE WHEN json_typeof(h.inputs) = 'array' THEN h.inputs END)
                 WITH ORDINALITY AS i(operand, n)
            WHERE i.operand ->> 'concept' = 'revenue'
            ORDER BY i.n
            LIMIT 1) AS revenue_tag
    FROM high h
), per AS (
    SELECT t.company_id, count(*) AS rows,
           count(*) FILTER (WHERE t.revenue_tag = p.fee_tag) AS on_fee,
           max(t.value) AS max_margin,
           (array_agg(t.fiscal_year ORDER BY t.value DESC, t.fiscal_year DESC))[1] AS max_fy,
           (array_agg(t.fiscal_period ORDER BY t.value DESC, t.fiscal_year DESC))[1] AS max_fp
    FROM tagged t
    CROSS JOIN params p
    GROUP BY t.company_id
)
SELECT fin.ticker, fin.sic, per.rows, per.on_fee, round(per.max_margin, 1) AS max_margin, per.max_fy, per.max_fp,
       sum(per.rows) OVER () AS all_rows, count(*) OVER () AS of_n
FROM per
JOIN fin ON fin.id = per.company_id
ORDER BY per.rows DESC, fin.ticker, fin.id
LIMIT 200;

\echo '5. JPM''s, BAC''s, C''s, WFC''s, GS''s, MS''s, IBKR''s, AXP''s and COF''s current fiscal-year revenue against net'
\echo '   interest income plus noninterest income at the same period end (current, USD), by bank, newest first.'
\echo '   components: their sum, blank when either is missing. gap: |revenue - components| / max(|revenue|,'
\echo '   |components|). over_1pct: E264''s check fails there.'
WITH params AS (
    SELECT ARRAY['JPM', 'BAC', 'C', 'WFC', 'GS', 'MS', 'IBKR', 'AXP', 'COF']::text[] AS banks,
           0.01::numeric AS tolerance
), cur AS MATERIALIZED (
    SELECT c.ticker, ff.company_id, ff.concept, ff.period_end, ff.fiscal_year, ff.value, ff.raw_tag, ff.source
    FROM companies c
    CROSS JOIN params p
    JOIN financial_fact ff ON ff.company_id = c.id
    WHERE c.ticker = ANY (p.banks) AND ff.is_latest AND ff.fiscal_period = 'FY' AND ff.unit = 'USD'
      AND ff.concept IN ('revenue', 'net_interest_income', 'noninterest_income')
), checked AS (
    SELECT r.ticker, r.company_id, r.fiscal_year, r.period_end, r.value AS revenue,
           regexp_replace(r.raw_tag, '^us-gaap:', '') AS revenue_tag, r.source AS revenue_source,
           n.value AS net_interest_income, x.value AS noninterest_income, n.value + x.value AS components
    FROM cur r
    LEFT JOIN cur n ON n.company_id = r.company_id AND n.period_end = r.period_end
                   AND n.concept = 'net_interest_income'
    LEFT JOIN cur x ON x.company_id = r.company_id AND x.period_end = r.period_end
                   AND x.concept = 'noninterest_income'
    WHERE r.concept = 'revenue'
)
SELECT k.ticker, k.fiscal_year, k.period_end, k.revenue, k.revenue_tag, k.revenue_source, k.net_interest_income,
       k.noninterest_income, k.components,
       round(abs(k.revenue - k.components) / NULLIF(greatest(abs(k.revenue), abs(k.components)), 0), 4) AS gap,
       abs(k.revenue - k.components) > p.tolerance * greatest(abs(k.revenue), abs(k.components)) AS over_1pct,
       count(*) OVER () AS of_n
FROM checked k
CROSS JOIN params p
ORDER BY k.ticker, k.period_end DESC, k.company_id
LIMIT 200;

\echo '6. Duplicate current rows at financial companies: identities (company, concept, period end, fiscal period,'
\echo '   unit) holding more than one current row, by concept, then in total (the row with no concept).'
WITH params AS (
    SELECT '6000'::text AS sic_low, '6799'::text AS sic_high
), fin AS MATERIALIZED (
    SELECT c.id
    FROM companies c
    CROSS JOIN params p
    WHERE c.sic <> '' AND c.sic COLLATE "C" BETWEEN p.sic_low AND p.sic_high
), dup AS (
    SELECT ff.company_id, ff.concept, count(*) AS n
    FROM fin
    JOIN financial_fact ff ON ff.company_id = fin.id
    WHERE ff.is_latest
    GROUP BY ff.company_id, ff.concept, ff.period_end, ff.fiscal_period, ff.unit
    HAVING count(*) > 1
)
SELECT concept, count(*) AS identities, sum(n) AS rows, count(DISTINCT company_id) AS companies
FROM dup
GROUP BY GROUPING SETS ((concept), ())
ORDER BY concept NULLS LAST;

\echo '7. Those identities, the most rows first: each row''s accession and source, so a later run shows which are new.'
WITH params AS (
    SELECT '6000'::text AS sic_low, '6799'::text AS sic_high
), fin AS MATERIALIZED (
    SELECT c.id, c.ticker
    FROM companies c
    CROSS JOIN params p
    WHERE c.sic <> '' AND c.sic COLLATE "C" BETWEEN p.sic_low AND p.sic_high
), dup AS (
    SELECT ff.company_id, ff.concept, ff.period_end, ff.fiscal_period, ff.unit, count(*) AS n,
           string_agg(ff.accession || ' ' || ff.source, ', ' ORDER BY ff.accession, ff.source) AS held
    FROM fin
    JOIN financial_fact ff ON ff.company_id = fin.id
    WHERE ff.is_latest
    GROUP BY ff.company_id, ff.concept, ff.period_end, ff.fiscal_period, ff.unit
    HAVING count(*) > 1
)
SELECT fin.ticker, d.concept, d.period_end, d.fiscal_period, d.unit, d.n, d.held, count(*) OVER () AS of_n
FROM dup d
JOIN fin ON fin.id = d.company_id
ORDER BY d.n DESC, fin.ticker, d.concept, d.period_end, d.fiscal_period
LIMIT 200;

\echo '8. Per-filing revenue rows at financial companies the old cross-check replaced (source companyfacts, a'
\echo '   filing owner, provenance outcome replaced), by company, the most first. current: those still current.'
\echo '   max_gap: the largest |stored - original| / max(|stored|, |original|), the original being the parsed'
\echo '   figure the authority displaced. The preview compares each with the new authority.'
WITH params AS (
    SELECT '6000'::text AS sic_low, '6799'::text AS sic_high,
           '\\u(0000|[dD][89a-fA-F][0-9a-fA-F]{2})'::text AS json_hazard
), fin AS MATERIALIZED (
    SELECT c.id, c.ticker, c.sic
    FROM companies c
    CROSS JOIN params p
    WHERE c.sic <> '' AND c.sic COLLATE "C" BETWEEN p.sic_low AND p.sic_high
), checked AS MATERIALIZED (
    SELECT ff.company_id, ff.fiscal_year, ff.is_latest, ff.value,
           CASE WHEN ff.provenance::text ~ p.json_hazard
                THEN regexp_replace(ff.provenance::text, p.json_hazard, '\\ufffd', 'g')::json
                ELSE ff.provenance END -> 'checks' -> 'authoritative' AS authoritative_check
    FROM fin
    JOIN financial_fact ff ON ff.company_id = fin.id
    CROSS JOIN params p
    WHERE ff.concept = 'revenue' AND ff.filing_id IS NOT NULL AND ff.source = 'companyfacts'
      AND strpos(ff.provenance::text, '"authoritative"') > 0
), replaced AS (
    SELECT k.company_id, k.fiscal_year, k.is_latest, k.value,
           CASE WHEN json_typeof(k.authoritative_check -> 'original_value') = 'number'
                THEN (k.authoritative_check ->> 'original_value')::numeric END AS original_value
    FROM checked k
    WHERE json_typeof(k.authoritative_check) = 'object' AND k.authoritative_check ->> 'outcome' = 'replaced'
), per AS (
    SELECT r.company_id, count(*) AS rows, count(*) FILTER (WHERE r.is_latest) AS current,
           min(r.fiscal_year) AS first_fy, max(r.fiscal_year) AS last_fy,
           max(abs(r.value - r.original_value) / NULLIF(greatest(abs(r.value), abs(r.original_value)), 0)) AS max_gap
    FROM replaced r
    GROUP BY r.company_id
)
SELECT fin.ticker, fin.sic, per.rows, per.current, per.first_fy, per.last_fy, round(per.max_gap, 4) AS max_gap,
       count(*) OVER () AS of_n
FROM per
JOIN fin ON fin.id = per.company_id
ORDER BY per.rows DESC, fin.ticker, fin.id
LIMIT 200;

COMMIT;
