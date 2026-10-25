-- Detection: current financial_fact rows a proxy or information statement supplies. Since 2023 a
-- proxy's pay-versus-performance table tags NetIncomeLoss (sometimes other lines) for five fiscal
-- years, filed after the 10-Ks it quotes, and until facts/currency.py's is_proxy_form the companyfacts
-- sync took each period's latest-filed item of any form, so the proxy's figure replaced the 10-K's
-- (the 2026-10 restatement census: 120 cells at 24 of 59 large filers, 12 of them off the 10-K's, FDX's
-- at a millionth of it). The next sync replaces such a row only where it never stored the 10-K's
-- identity; elsewhere it stays current, and a margin computed from it keeps its value. These sets are
-- the cohort of the journaled repair that a separate PR builds. It names companies and changes nothing.
-- Retire: the session that applies that repair deletes this file in the records PR that closes it,
-- after a detection-sql run reads no rows in sets 2 and 3, and by 2026-12-31 at the latest.
--
-- Read-only: one REPEATABLE READ READ ONLY transaction, so the three sets share one snapshot. Tables:
-- companies, financial_fact. Each statement gets 120 s and waits at most 10 s for a lock (SET LOCAL
-- below; the step's PGOPTIONS allow 600 s). A failure stops this file, and under the step's set -e the
-- files after it do not run. Cost per statement: sets 1 and 2 read financial_fact once for its current
-- proxy rows (no index holds the form), then each one's report rows through
-- uq_financial_fact_identity; set 3 reads financial_fact once for the proxy accessions, then the
-- affected companies' rows through ix_financial_fact_company_id and the text of their provenance. A
-- list stops at 200 rows, and each row carries its set's full count (of_n), so a cut list shows.
-- proxy form: the form, its whitespace collapsed, trimmed and upper-cased, matches
-- ^[A-Z]+ ?14[AC][0-9A-Z]*(/A)?$ (DEF 14A, DEFA14A, DEFM14A, PRE 14C, PX14A6G, ...), is_proxy_form's
-- rule. report row: a row that is not current, at the same company, concept, period end and fiscal
-- period, whose form is set and is no proxy form (10-K, 10-Q, 8-K, 20-F, ... and amendments; any source
-- or unit). gap: the relative distance from the proxy row's value to its nearest report row's,
-- |a - b| / max(|a|, |b|), 0 when one agrees. Stated limit: a 10-K/A that adds Part III late carries
-- the same table under a report form, and neither the fix nor this file can tell it apart.
-- Patterns assume standard_conforming_strings = on (the default).
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout = '120s';
SET LOCAL lock_timeout = '10s';

\echo '0. Session: this transaction is read-only and bounded.'
SELECT current_setting('transaction_read_only') AS read_only,
       current_setting('transaction_isolation') AS isolation,
       current_setting('statement_timeout') AS statement_timeout,
       current_setting('lock_timeout') AS lock_timeout;

\echo '1. Current rows a proxy or information statement supplies, by concept, fiscal period, fiscal year and'
\echo '   source (companyfacts: a reported winner; derived: a quarter named by that winner), then in total'
\echo '   (the row with every key blank). companies: how many hold them. with_report_row: rows with a report'
\echo '   row behind them; without_report_row: rows with none, which a repair cannot fill from a stored row.'
\echo '   differs: rows no report row matches in value. over_1pct: rows whose nearest report row is more'
\echo '   than 1% away.'
WITH params AS (
    SELECT '^[A-Z]+ ?14[AC][0-9A-Z]*(/A)?$'::text AS proxy_form
), proxy AS MATERIALIZED (
    SELECT ff.id, ff.company_id, ff.concept, ff.period_end, ff.fiscal_period, ff.fiscal_year, ff.source,
           ff.value
    FROM financial_fact ff
    CROSS JOIN params p
    WHERE ff.is_latest AND upper(btrim(regexp_replace(ff.form, '\s+', ' ', 'g'))) ~ p.proxy_form
), matched AS (
    SELECT x.*, r.report_rows, r.gap
    FROM proxy x
    CROSS JOIN params p
    CROSS JOIN LATERAL (
        SELECT count(*) AS report_rows,
               min(CASE WHEN t.value = x.value THEN 0
                        ELSE abs(t.value - x.value) / greatest(abs(t.value), abs(x.value)) END) AS gap
        FROM financial_fact t
        WHERE t.company_id = x.company_id AND t.concept = x.concept AND t.period_end = x.period_end
          AND t.fiscal_period = x.fiscal_period AND NOT t.is_latest
          AND btrim(COALESCE(t.form, '')) <> ''
          AND upper(btrim(regexp_replace(t.form, '\s+', ' ', 'g'))) !~ p.proxy_form
    ) r
)
SELECT m.concept, m.fiscal_period, m.fiscal_year, m.source, count(*) AS rows,
       count(DISTINCT m.company_id) AS companies,
       count(*) FILTER (WHERE m.report_rows > 0) AS with_report_row,
       count(*) FILTER (WHERE m.report_rows = 0) AS without_report_row,
       count(*) FILTER (WHERE m.gap > 0) AS differs,
       count(*) FILTER (WHERE m.gap > 0.01) AS over_1pct
FROM matched m
GROUP BY GROUPING SETS ((m.concept, m.fiscal_period, m.fiscal_year, m.source), ())
ORDER BY GROUPING(m.concept), m.concept, m.fiscal_period, m.fiscal_year, m.source;

\echo '2. The companies and concepts holding them: rows, their fiscal years, the proxy forms and accessions,'
\echo '   with_report_row, without_report_row and differs as in set 1, max_gap (the largest of their rows'''
\echo '   gaps to their nearest report row; 1.0 is a value at another scale) and the company''s last sync.'
WITH params AS (
    SELECT '^[A-Z]+ ?14[AC][0-9A-Z]*(/A)?$'::text AS proxy_form
), proxy AS MATERIALIZED (
    SELECT ff.id, ff.company_id, ff.concept, ff.period_end, ff.fiscal_period, ff.fiscal_year, ff.form,
           ff.accession, ff.value
    FROM financial_fact ff
    CROSS JOIN params p
    WHERE ff.is_latest AND upper(btrim(regexp_replace(ff.form, '\s+', ' ', 'g'))) ~ p.proxy_form
), matched AS (
    SELECT x.*, r.report_rows, r.gap
    FROM proxy x
    CROSS JOIN params p
    CROSS JOIN LATERAL (
        SELECT count(*) AS report_rows,
               min(CASE WHEN t.value = x.value THEN 0
                        ELSE abs(t.value - x.value) / greatest(abs(t.value), abs(x.value)) END) AS gap
        FROM financial_fact t
        WHERE t.company_id = x.company_id AND t.concept = x.concept AND t.period_end = x.period_end
          AND t.fiscal_period = x.fiscal_period AND NOT t.is_latest
          AND btrim(COALESCE(t.form, '')) <> ''
          AND upper(btrim(regexp_replace(t.form, '\s+', ' ', 'g'))) !~ p.proxy_form
    ) r
), by_company AS (
    SELECT m.company_id, m.concept, m.fiscal_period, count(*) AS rows,
           string_agg(DISTINCT m.fiscal_year::text, ',' ORDER BY m.fiscal_year::text) AS fiscal_years,
           string_agg(DISTINCT m.form, ',' ORDER BY m.form) AS forms,
           string_agg(DISTINCT m.accession, ',' ORDER BY m.accession) AS accessions,
           count(*) FILTER (WHERE m.report_rows > 0) AS with_report_row,
           count(*) FILTER (WHERE m.report_rows = 0) AS without_report_row,
           count(*) FILTER (WHERE m.gap > 0) AS differs,
           round(max(m.gap), 4) AS max_gap
    FROM matched m
    GROUP BY m.company_id, m.concept, m.fiscal_period
)
SELECT c.ticker, b.company_id, b.concept, b.fiscal_period, b.rows, b.fiscal_years, b.forms, b.accessions,
       b.with_report_row, b.without_report_row, b.differs, b.max_gap, c.facts_synced_at,
       count(*) OVER () AS of_n
FROM by_company b
JOIN companies c ON c.id = b.company_id
ORDER BY c.ticker, b.company_id, b.concept, b.fiscal_period
LIMIT 200;

\echo '3. Current rows of another form computed from a proxy row: a calculation whose recorded operands name'
\echo '   the accession of a proxy or information statement row of its company, current or not. A margin'
\echo '   from the proxy''s net income keeps revenue''s accession and form, so sets 1 and 2 cannot see it,'
\echo '   and no sync recomputes it (its identity is already stored).'
WITH params AS (
    SELECT '^[A-Z]+ ?14[AC][0-9A-Z]*(/A)?$'::text AS proxy_form
), proxy_accessions AS MATERIALIZED (
    SELECT DISTINCT ff.company_id, ff.accession
    FROM financial_fact ff
    CROSS JOIN params p
    WHERE upper(btrim(regexp_replace(ff.form, '\s+', ' ', 'g'))) ~ p.proxy_form
), dependents AS (
    SELECT ff.company_id, ff.concept, ff.fiscal_period, ff.fiscal_year
    FROM financial_fact ff
    CROSS JOIN params p
    WHERE ff.company_id IN (SELECT a.company_id FROM proxy_accessions a)
      AND ff.is_latest AND ff.provenance IS NOT NULL
      AND (ff.form IS NULL OR upper(btrim(regexp_replace(ff.form, '\s+', ' ', 'g'))) !~ p.proxy_form)
      AND EXISTS (SELECT 1 FROM proxy_accessions a
                  WHERE a.company_id = ff.company_id
                    AND strpos(ff.provenance::text, '"' || a.accession || '"') > 0)
)
SELECT c.ticker, d.company_id, d.concept, d.fiscal_period, count(*) AS rows,
       string_agg(DISTINCT d.fiscal_year::text, ',' ORDER BY d.fiscal_year::text) AS fiscal_years,
       count(*) OVER () AS of_n
FROM dependents d
JOIN companies c ON c.id = d.company_id
GROUP BY c.ticker, d.company_id, d.concept, d.fiscal_period
ORDER BY c.ticker, d.company_id, d.concept, d.fiscal_period
LIMIT 200;

COMMIT;
