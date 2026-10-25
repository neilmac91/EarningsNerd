-- Detection: current financial_fact rows a proxy or information statement supplied. Since 2023 a
-- proxy's pay-versus-performance table tags NetIncomeLoss (sometimes other lines) for five fiscal
-- years, filed after the 10-Ks it quotes. Until facts/currency.py's is_proxy_form the companyfacts sync
-- took each period's latest-filed item of any form, so the proxy's figure replaced the 10-K's (the
-- 2026-10 restatement census: 120 cells at 24 of 59 large filers, 12 of them off the 10-K's, FDX's at a
-- millionth of it), and the backfill's cross-check (facts/reconcile.py's extract_authoritative_values,
-- run by backfill-facts) took it as the authority and wrote it over a filing's parsed figure. The next
-- sync replaces a sync's proxy row only where no stored row holds the 10-K's identity: neither a
-- sync's nor a filing's, which the per-filing writer stores behind a current proxy row when the 10-K
-- is listed after it. Elsewhere the proxy row stays current, a margin computed from it keeps its value,
-- and no sync rewrites a filing's row. The sets: 1 counts the current rows whose form is a proxy form,
-- 2 lists their companies and concepts, 3 lists the calculations computed from them, and 4 lists the
-- filings' rows, current or not, the cross-check replaced with a proxy's figure. Together they are the
-- cohort of the journaled repair a separate PR builds. It names companies and changes nothing.
-- Retire: the session that applies that repair deletes this file, and the unit test that holds its
-- proxy-form pattern to is_proxy_form's (backend/tests/unit/test_proxy_form_detection_sql.py), in the
-- records PR that closes it, after a detection-sql run reads no rows in sets 2, 3 and 4, and by
-- 2026-12-31 at the latest.
--
-- Read-only: one REPEATABLE READ READ ONLY transaction, so the four sets share one snapshot. Tables:
-- companies, financial_fact. Each statement gets 120 s and waits at most 10 s for a lock (SET LOCAL
-- below; the step's PGOPTIONS allow 600 s). A failure stops this file, and under the step's set -e the
-- files after it do not run. Cost per statement: sets 1 and 2 read financial_fact once for its current
-- proxy rows (no index holds the form), then each one's report rows through
-- uq_financial_fact_identity; set 3 reads financial_fact once for the proxy accessions, then the
-- affected companies' rows through ix_financial_fact_company_id and the text of their provenance; set 4
-- reads financial_fact once for the filing-owned companyfacts rows (no index holds the source),
-- parses the provenance of those that name an authoritative check, and reads each one's period-end rows
-- through uq_financial_fact_identity. A list stops at 200 rows, and each row carries its set's full
-- count (of_n), so a cut list shows.
-- proxy form: the form, its whitespace collapsed, trimmed and upper-cased, matches
-- ^[A-Z]+ ?14[AC][0-9A-Z]*(/A)?$ (DEF 14A, DEFA14A, DEFM14A, PRE 14C, PX14A6G, ...), is_proxy_form's
-- rule. report row: a row that is not current, at the same company, concept, period end and fiscal
-- period, whose form is set and is no proxy form (10-K, 10-Q, 8-K, 20-F, ... and amendments; any unit),
-- and that the cross-check did not replace (a row with a filing owner and source companyfacts carries
-- the authority's figure, a proxy's among them, not its report's). gap: the relative distance from the
-- proxy row's value to its nearest report row's,
-- |a - b| / max(|a|, |b|), 0 when one agrees. Stated limits: a 10-K/A that adds Part III late carries
-- the same table under a report form, and neither the fix nor this file can tell it apart; set 4's
-- limits are stated with it.
-- JSON: -> and ->> raise for a whole json value holding a NUL or a lone-surrogate escape, so set 4 reads
-- provenance after rewriting a NUL or any surrogate escape to the escape of U+FFFD (same length;
-- nothing else moves), as #1532 did. Sets 1 to 3 parse no JSON.
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
          AND NOT (t.filing_id IS NOT NULL AND t.source = 'companyfacts')
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
          AND NOT (t.filing_id IS NOT NULL AND t.source = 'companyfacts')
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

\echo '4. Filing rows the backfill''s cross-check replaced with a proxy''s figure, current or not: a filing''s'
\echo '   own page reads its rows whatever is_latest says (get_filing_fundamentals). Candidates: rows with a'
\echo '   filing owner and source companyfacts, which only cross_check_facts writes on a filing''s row; since'
\echo '   #1191 (2026-10-10) it also records provenance.checks.authoritative, with outcome replaced and the'
\echo '   parsed original_value. why = proxy row: a stored proxy-form row of the company, concept and period'
\echo '   end, current or not, holds the same value (relative 1e-6; its accession is proxy_witness), and the'
\echo '   value is not 1,000 or 1,000,000 times the original, which is the authority multiplying up a figure'
\echo '   in millions read as units, the parse bug the check exists for. why = scale: no such row, and the'
\echo '   value is 1/1,000 or 1/1,000,000 of the original (within 1%, same sign), the FDX shape.'
\echo '   original_backed: a stored report row holds the original, so the replacement overwrote a figure a'
\echo '   report gives. Left out: a row whose value a stored report row holds. report row here: a row of a'
\echo '   report form, other than this one, that the cross-check did not replace. Limits: alone, a witness'
\echo '   cannot tell a proxy figure that differs from the 10-K''s from one that agrees with it, so a row'
\echo '   whose original was a mis-parse by a non-scale amount, or that a later restatement the proxy quotes'
\echo '   corrected, is listed unless a stored report row holds its value (original_backed false is the cue'
\echo '   to read the filing); requiring original_backed would drop every witness at a key where only the'
\echo '   proxy''s row was stored, as a sync stores only winners. A witness exists only where a companyfacts'
\echo '   sync stored the proxy''s item, so a non-scale proxy figure at a company no sync read after its'
\echo '   proxy is not found. A row replaced before #1191 records no original: only a witness finds it, and'
\echo '   the scale-up guard cannot apply. Scale also lists a parse that was itself 1,000 or 1,000,000 times'
\echo '   too large.'
WITH params AS (
    SELECT '^[A-Z]+ ?14[AC][0-9A-Z]*(/A)?$'::text AS proxy_form,
           '\\u(0000|[dD][89a-fA-F][0-9a-fA-F]{2})'::text AS json_hazard,
           0.000001::numeric AS tolerance
), replaced AS MATERIALIZED (
    SELECT ff.id, ff.company_id, ff.concept, ff.period_end, ff.fiscal_period, ff.fiscal_year, ff.form,
           ff.accession, ff.value, ff.is_latest,
           CASE WHEN strpos(ff.provenance::text, '"authoritative"') > 0
                THEN (CASE WHEN ff.provenance::text ~ p.json_hazard
                           THEN regexp_replace(ff.provenance::text, p.json_hazard, '\\ufffd', 'g')::json
                           ELSE ff.provenance END) -> 'checks' -> 'authoritative' END AS authoritative_check
    FROM financial_fact ff
    CROSS JOIN params p
    WHERE ff.filing_id IS NOT NULL AND ff.source = 'companyfacts'
), checked AS (
    SELECT r.*, r.authoritative_check ->> 'outcome' AS outcome,
           CASE WHEN json_typeof(r.authoritative_check -> 'original_value') = 'number'
                THEN (r.authoritative_check ->> 'original_value')::numeric END AS original_value
    FROM replaced r
), reports AS (
    SELECT k.id, b.value
    FROM checked k
    CROSS JOIN params p
    JOIN financial_fact b
      ON b.company_id = k.company_id AND b.concept = k.concept AND b.period_end = k.period_end
    WHERE b.id <> k.id AND NOT (b.filing_id IS NOT NULL AND b.source = 'companyfacts')
      AND btrim(COALESCE(b.form, '')) <> ''
      AND upper(btrim(regexp_replace(b.form, '\s+', ' ', 'g'))) !~ p.proxy_form
), signals AS (
    SELECT k.*,
           (SELECT w.accession
            FROM financial_fact w
            CROSS JOIN params p
            WHERE w.company_id = k.company_id AND w.concept = k.concept AND w.period_end = k.period_end
              AND upper(btrim(regexp_replace(w.form, '\s+', ' ', 'g'))) ~ p.proxy_form
              AND abs(w.value - k.value) <= p.tolerance * greatest(abs(w.value), abs(k.value))
            ORDER BY w.id
            LIMIT 1) AS proxy_witness,
           EXISTS (SELECT 1 FROM reports b CROSS JOIN params p
                   WHERE b.id = k.id
                     AND abs(b.value - k.value) <= p.tolerance * greatest(abs(b.value), abs(k.value)))
               AS report_backed,
           EXISTS (SELECT 1 FROM reports b CROSS JOIN params p
                   WHERE b.id = k.id AND k.original_value IS NOT NULL
                     AND abs(b.value - k.original_value) <= p.tolerance * greatest(abs(b.value), abs(k.original_value)))
               AS original_backed,
           CASE WHEN k.original_value <> 0 AND k.value <> 0 AND sign(k.value) = sign(k.original_value)
                THEN k.value / k.original_value END AS ratio
    FROM checked k
), listed AS (
    SELECT s.*,
           CASE WHEN s.proxy_witness IS NOT NULL
                     AND NOT COALESCE(abs(s.ratio / 1000 - 1) <= 0.01 OR abs(s.ratio / 1000000 - 1) <= 0.01, false)
                THEN 'proxy row'
                WHEN s.proxy_witness IS NULL
                     AND (abs(s.ratio * 1000 - 1) <= 0.01 OR abs(s.ratio * 1000000 - 1) <= 0.01)
                THEN 'scale'
           END AS why
    FROM signals s
    WHERE NOT s.report_backed
)
SELECT c.ticker, l.company_id, l.concept, l.fiscal_period, l.fiscal_year, l.period_end, l.accession, l.form,
       l.is_latest, l.value, l.original_value, l.outcome, l.why, l.proxy_witness, l.original_backed,
       count(*) OVER () AS of_n
FROM listed l
JOIN companies c ON c.id = l.company_id
WHERE l.why IS NOT NULL
ORDER BY c.ticker, l.company_id, l.concept, l.period_end, l.accession
LIMIT 200;

COMMIT;
