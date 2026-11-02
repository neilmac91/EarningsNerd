-- Detection: E198's reach. Since E198 every companyfacts sync runs the currency step (facts/currency.py), a sync in
-- USD alone too: at each key its payload presents (company, concept, period end, fiscal period, unit) in an amount or
-- per-share unit it makes the payload's own row current unless a row of a filing filed strictly after that row's own
-- filing is current there, and its upsert keeps such a row current over its insert (Guard.later). Before E198 a sync in
-- USD alone was the upsert alone, so a later-filed row stored behind an earlier one stayed behind for good: (1) an
-- amendment the per-filing writer stored behind its original's companyfacts row, (2) a newer filing's restatement
-- under a lower-priority tag behind an older filing's row with no Filing row, (3) a newer filing's row a lagging
-- payload's insert demoted. This file sizes those keys at the companies whose stored rows read no other currency (the
-- syncs E198 changes; a company storing another currency's row has run the step since #1583). It names companies and
-- changes nothing.
--
-- An upper bound, not the count E198 moves. A key here moves at the company's next sync only where the later row is
-- the payload's own row there, its winner: the latest-filed item of the first registry tag with data, which SEC's
-- payload alone says. same_tag splits the likely from the doubtful: a later row under the current row's own tag is the
-- winner wherever that tag still wins the period; one under another tag (a tag migration, (2), or a lineage an older
-- rule read, E264's fee line) stays behind wherever the current row's tag outranks it. A key whose current row is a
-- proxy statement's is left as found (E211's), and a quarantined row is never made current, so neither counts.
-- Ratios (pure) do not converge, outside a key a newer filing the payload does not name holds: set 3 sizes the
-- question E198 leaves open. A key E198 leaves to a later-filed current row over the payload's new insert (Guard.later)
-- shows here only after it happens; before the deploy those rows read as current, not behind.
--
-- Definitions. amount: a unit whose part before '/' is three capital letters (USD, USD/shares; is_amount_unit). USD
-- alone: the company stores no row in such a unit other than USD or USD/shares (current or not), a company-level
-- reading of _another_currency, which reads the batch's concepts. A row's date: its Filing row's filing_date (same
-- company and accession, dashes ignored), else its provenance filed_at (a companyfacts row's own filing date; a
-- calculation's latest operand's), else none; the sync also reads the payload's filed dates, which this cannot see.
-- quarantined: provenance validation 'unavailable' (currency._promotable). proxy: the form, its whitespace collapsed,
-- trimmed and upper-cased, matches ^[A-Z]+ ?14[AC][0-9A-Z]*(/A)?$ (is_proxy_form; gated by
-- backend/tests/unit/test_usd_sync_convergence_detection_sql.py). behind: a key with a fiscal period where a row that is
-- not current, not quarantined and no proxy's, is dated strictly after every dated current row there (or the key holds
-- no current row: a gap). kind: amendment (the later row's form ends in /A) or original; source: feed (companyfacts,
-- no filing owner), filing (a filing owner: the per-filing writer's, or the cross-check's replacement), derived.
--
-- Run it before E198's deploy (the before) and after the companies' next syncs (the after: set 2's same_tag rows
-- should fall to the doubtful remainder). Retire: the records PR that reports the after run deletes this file and its
-- test (tasks/todo.md, E198).
--
-- Read-only: one REPEATABLE READ READ ONLY transaction, so every set shares one snapshot. Each statement gets 120 s
-- and waits at most 10 s for a lock (SET LOCAL below; the step's PGOPTIONS allow 600 s). Cost per statement: one scan
-- of financial_fact for the keys that hold a row that is not current (no index holds is_latest alone), then their rows
-- through uq_financial_fact_identity's (company, concept, period_end) prefix, the provenance of those rows parsed once,
-- and filings by company. A list stops at 50 rows and carries its set's full count (of_n).
-- JSON: -> and ->> raise for a whole json value holding a NUL or a lone-surrogate escape, so provenance is read after
-- rewriting a NUL or any surrogate escape to the escape of U+FFFD (same length; nothing else moves), as #1532 did.
-- Patterns assume standard_conforming_strings = on (the default).
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout = '120s';
SET LOCAL lock_timeout = '10s';

\echo '0. Session: this transaction is read-only and bounded.'
SELECT current_setting('transaction_read_only') AS read_only,
       current_setting('transaction_isolation') AS isolation,
       current_setting('statement_timeout') AS statement_timeout,
       current_setting('lock_timeout') AS lock_timeout;

\echo '1. Companies holding financial_fact rows: those in USD alone (each sync of theirs changes at E198''s deploy)'
\echo '   and those storing another currency''s amount or per-share row (their syncs have run the step since #1583),'
\echo '   with their current amount and per-share rows.'
WITH params AS (
    SELECT '^[A-Z]{3}$'::text AS amount_code
), units AS MATERIALIZED (
    SELECT ff.company_id,
           bool_or(split_part(ff.unit, '/', 1) ~ p.amount_code AND split_part(ff.unit, '/', 1) <> 'USD') AS other,
           count(*) FILTER (WHERE ff.is_latest AND split_part(ff.unit, '/', 1) ~ p.amount_code) AS current_amount_rows
    FROM financial_fact ff CROSS JOIN params p
    GROUP BY ff.company_id
), readings AS (
    SELECT CASE WHEN u.other THEN 'another_currency' ELSE 'usd_alone' END AS reading, u.current_amount_rows
    FROM units u
)
SELECT r.reading, count(*) AS companies, sum(r.current_amount_rows) AS current_amount_rows
FROM readings r
GROUP BY ROLLUP (r.reading)
ORDER BY GROUPING(r.reading), r.reading;

\echo '2. Keys behind at companies in USD alone, by fiscal period (FY or a quarter), the later row''s kind and source,'
\echo '   whether it carries the current row''s own tag (same_tag; a gap carries none), then in total (the row with'
\echo '   every key blank): keys, companies, and the later rows'' newest date. An upper bound: see the header.'
WITH params AS (
    SELECT '^[A-Z]{3}$'::text AS amount_code,
           '^[A-Z]+ ?14[AC][0-9A-Z]*(/A)?$'::text AS proxy_form,
           '\\u(0000|[dD][89a-fA-F][0-9a-fA-F]{2})'::text AS json_hazard
), usd_alone AS MATERIALIZED (
    SELECT ff.company_id
    FROM financial_fact ff CROSS JOIN params p
    GROUP BY ff.company_id
    HAVING NOT bool_or(split_part(ff.unit, '/', 1) ~ p.amount_code AND split_part(ff.unit, '/', 1) <> 'USD')
), keyed AS MATERIALIZED (
    SELECT DISTINCT ff.company_id, ff.concept, ff.period_end, ff.fiscal_period, ff.unit
    FROM financial_fact ff
    JOIN usd_alone a ON a.company_id = ff.company_id
    CROSS JOIN params p
    WHERE NOT ff.is_latest AND ff.fiscal_period IS NOT NULL AND split_part(ff.unit, '/', 1) = 'USD'
), dated AS MATERIALIZED (
    SELECT ff.company_id, ff.concept, ff.period_end, ff.fiscal_period, ff.unit, ff.is_latest, ff.raw_tag, ff.source,
           ff.filing_id, ff.form, ff.fiscal_year,
           upper(btrim(regexp_replace(coalesce(ff.form, ''), '\s+', ' ', 'g'))) ~ p.proxy_form AS proxy,
           coalesce(pv.pv ->> 'validation', '') = 'unavailable' AS quarantined,
           coalesce(
               (SELECT max(f.filing_date)::date FROM filings f
                WHERE f.company_id = ff.company_id
                  AND replace(f.accession_number, '-', '') = replace(ff.accession, '-', '')),
               CASE WHEN pv.pv ->> 'filed_at' ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}'
                    THEN substring(pv.pv ->> 'filed_at' FROM 1 FOR 10)::date END) AS filed
    FROM financial_fact ff
    JOIN keyed k ON k.company_id = ff.company_id AND k.concept = ff.concept AND k.period_end = ff.period_end
                AND k.fiscal_period = ff.fiscal_period AND k.unit = ff.unit
    CROSS JOIN params p
    CROSS JOIN LATERAL (
        SELECT CASE WHEN ff.provenance IS NULL OR ff.provenance::text = 'null' THEN NULL
                    WHEN ff.provenance::text ~ p.json_hazard
                    THEN regexp_replace(ff.provenance::text, p.json_hazard, '\\ufffd', 'g')::jsonb
                    ELSE ff.provenance::jsonb END AS pv
    ) pv
), keys AS (
    SELECT d.company_id, d.concept, d.period_end, d.fiscal_period, d.unit,
           max(d.filed) FILTER (WHERE d.is_latest) AS current_filed,
           bool_or(d.is_latest) AS has_current,
           bool_or(d.is_latest AND d.proxy) AS proxy_current,
           string_agg(DISTINCT coalesce(d.raw_tag, ''), ',') FILTER (WHERE d.is_latest) AS current_tags
    FROM dated d
    GROUP BY d.company_id, d.concept, d.period_end, d.fiscal_period, d.unit
), behind AS (
    SELECT k.company_id, k.concept, k.period_end, k.fiscal_period, k.unit,
           CASE WHEN k.fiscal_period = 'FY' THEN 'FY' ELSE 'Q' END AS fp,
           CASE WHEN bool_or(upper(coalesce(d.form, '')) LIKE '%/A') THEN 'amendment' ELSE 'original' END AS kind,
           CASE WHEN bool_or(d.source = 'derived') THEN 'derived'
                WHEN bool_or(d.filing_id IS NOT NULL) THEN 'filing' ELSE 'feed' END AS source,
           CASE WHEN NOT k.has_current THEN 'gap'
                WHEN bool_or(coalesce(d.raw_tag, '') = ANY (string_to_array(k.current_tags, ','))) THEN 'same_tag'
                ELSE 'other_tag' END AS tag,
           max(d.filed) AS later_filed
    FROM keys k
    JOIN dated d ON d.company_id = k.company_id AND d.concept = k.concept AND d.period_end = k.period_end
                AND d.fiscal_period = k.fiscal_period AND d.unit = k.unit
    WHERE NOT k.proxy_current AND NOT d.is_latest AND NOT d.quarantined AND NOT d.proxy
      AND (NOT k.has_current OR (d.filed IS NOT NULL AND k.current_filed IS NOT NULL AND d.filed > k.current_filed))
    GROUP BY k.company_id, k.concept, k.period_end, k.fiscal_period, k.unit, k.has_current
)
SELECT b.fp, b.kind, b.source, b.tag, count(*) AS keys, count(DISTINCT b.company_id) AS companies,
       max(b.later_filed) AS newest_later_filed
FROM behind b
GROUP BY GROUPING SETS ((b.fp, b.kind, b.source, b.tag), ())
ORDER BY GROUPING(b.fp), b.fp, b.kind, b.source, b.tag;

\echo '3. Ratio keys (pure) behind at companies in USD alone, as set 2 reads them: E198 converges no ratio outside a'
\echo '   key a newer filing the payload does not name holds (the question E198 leaves open), by fiscal period.'
WITH params AS (
    SELECT '^[A-Z]{3}$'::text AS amount_code,
           '^[A-Z]+ ?14[AC][0-9A-Z]*(/A)?$'::text AS proxy_form,
           '\\u(0000|[dD][89a-fA-F][0-9a-fA-F]{2})'::text AS json_hazard
), usd_alone AS MATERIALIZED (
    SELECT ff.company_id
    FROM financial_fact ff CROSS JOIN params p
    GROUP BY ff.company_id
    HAVING NOT bool_or(split_part(ff.unit, '/', 1) ~ p.amount_code AND split_part(ff.unit, '/', 1) <> 'USD')
), keyed AS MATERIALIZED (
    SELECT DISTINCT ff.company_id, ff.concept, ff.period_end, ff.fiscal_period, ff.unit
    FROM financial_fact ff
    JOIN usd_alone a ON a.company_id = ff.company_id
    WHERE NOT ff.is_latest AND ff.fiscal_period IS NOT NULL AND ff.unit = 'pure'
), dated AS MATERIALIZED (
    SELECT ff.company_id, ff.concept, ff.period_end, ff.fiscal_period, ff.unit, ff.is_latest,
           upper(btrim(regexp_replace(coalesce(ff.form, ''), '\s+', ' ', 'g'))) ~ p.proxy_form AS proxy,
           coalesce(pv.pv ->> 'validation', '') = 'unavailable' AS quarantined,
           coalesce(
               (SELECT max(f.filing_date)::date FROM filings f
                WHERE f.company_id = ff.company_id
                  AND replace(f.accession_number, '-', '') = replace(ff.accession, '-', '')),
               CASE WHEN pv.pv ->> 'filed_at' ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}'
                    THEN substring(pv.pv ->> 'filed_at' FROM 1 FOR 10)::date END) AS filed
    FROM financial_fact ff
    JOIN keyed k ON k.company_id = ff.company_id AND k.concept = ff.concept AND k.period_end = ff.period_end
                AND k.fiscal_period = ff.fiscal_period AND k.unit = ff.unit
    CROSS JOIN params p
    CROSS JOIN LATERAL (
        SELECT CASE WHEN ff.provenance IS NULL OR ff.provenance::text = 'null' THEN NULL
                    WHEN ff.provenance::text ~ p.json_hazard
                    THEN regexp_replace(ff.provenance::text, p.json_hazard, '\\ufffd', 'g')::jsonb
                    ELSE ff.provenance::jsonb END AS pv
    ) pv
), keys AS (
    SELECT d.company_id, d.concept, d.period_end, d.fiscal_period,
           max(d.filed) FILTER (WHERE d.is_latest) AS current_filed, bool_or(d.is_latest) AS has_current,
           bool_or(d.is_latest AND d.proxy) AS proxy_current
    FROM dated d
    GROUP BY d.company_id, d.concept, d.period_end, d.fiscal_period
), behind AS (
    SELECT DISTINCT k.company_id, k.concept, k.period_end, k.fiscal_period,
           CASE WHEN k.fiscal_period = 'FY' THEN 'FY' ELSE 'Q' END AS fp, k.has_current
    FROM keys k
    JOIN dated d ON d.company_id = k.company_id AND d.concept = k.concept AND d.period_end = k.period_end
                AND d.fiscal_period = k.fiscal_period
    WHERE NOT k.proxy_current AND NOT d.is_latest AND NOT d.quarantined AND NOT d.proxy
      AND (NOT k.has_current OR (d.filed IS NOT NULL AND k.current_filed IS NOT NULL AND d.filed > k.current_filed))
)
, states AS (
    SELECT b.company_id, b.fp, CASE WHEN b.has_current THEN 'behind' ELSE 'gap' END AS state FROM behind b
)
SELECT s.fp, s.state, count(*) AS keys, count(DISTINCT s.company_id) AS companies
FROM states s
GROUP BY GROUPING SETS ((s.fp, s.state), ())
ORDER BY GROUPING(s.fp), s.fp, s.state;

\echo '4. Quarantined rows (provenance validation unavailable), which no sync makes current: rows and companies, in'
\echo '   total and at companies in USD alone. Where one is the payload''s own row, E198''s sync leaves its key as found'
\echo '   and demotes its own insert there (a gap where a lagging payload inserted, never its older figure).'
WITH params AS (
    SELECT '^[A-Z]{3}$'::text AS amount_code,
           '\\u(0000|[dD][89a-fA-F][0-9a-fA-F]{2})'::text AS json_hazard
), usd_alone AS MATERIALIZED (
    SELECT ff.company_id
    FROM financial_fact ff CROSS JOIN params p
    GROUP BY ff.company_id
    HAVING NOT bool_or(split_part(ff.unit, '/', 1) ~ p.amount_code AND split_part(ff.unit, '/', 1) <> 'USD')
), quarantined AS MATERIALIZED (
    SELECT ff.company_id
    FROM financial_fact ff CROSS JOIN params p
    WHERE ff.provenance IS NOT NULL AND ff.provenance::text LIKE '%unavailable%'
      AND (CASE WHEN ff.provenance::text ~ p.json_hazard
                THEN regexp_replace(ff.provenance::text, p.json_hazard, '\\ufffd', 'g')::jsonb
                ELSE ff.provenance::jsonb END) ->> 'validation' = 'unavailable'
)
SELECT count(*) AS rows, count(DISTINCT q.company_id) AS companies,
       count(*) FILTER (WHERE a.company_id IS NOT NULL) AS rows_usd_alone,
       count(DISTINCT q.company_id) FILTER (WHERE a.company_id IS NOT NULL) AS companies_usd_alone
FROM quarantined q LEFT JOIN usd_alone a ON a.company_id = q.company_id;

\echo '5. Saved analyses whose window holds a set-2 key''s fiscal year (annual: FYyyyy..FYyyyy; quarterly by the years'
\echo '   of yyyyQn..yyyyQn): where the key moves at the company''s next sync, the dataset''s fingerprint changes, so its'
\echo '   narrative regenerates once at next open (unmetered) and its saved PDF answers 409 until it is re-run.'
WITH params AS (
    SELECT '^[A-Z]{3}$'::text AS amount_code,
           '^[A-Z]+ ?14[AC][0-9A-Z]*(/A)?$'::text AS proxy_form,
           '\\u(0000|[dD][89a-fA-F][0-9a-fA-F]{2})'::text AS json_hazard
), usd_alone AS MATERIALIZED (
    SELECT ff.company_id
    FROM financial_fact ff CROSS JOIN params p
    GROUP BY ff.company_id
    HAVING NOT bool_or(split_part(ff.unit, '/', 1) ~ p.amount_code AND split_part(ff.unit, '/', 1) <> 'USD')
), keyed AS MATERIALIZED (
    SELECT DISTINCT ff.company_id, ff.concept, ff.period_end, ff.fiscal_period, ff.unit
    FROM financial_fact ff
    JOIN usd_alone a ON a.company_id = ff.company_id
    WHERE NOT ff.is_latest AND ff.fiscal_period IS NOT NULL AND split_part(ff.unit, '/', 1) = 'USD'
), dated AS MATERIALIZED (
    SELECT ff.company_id, ff.concept, ff.period_end, ff.fiscal_period, ff.unit, ff.is_latest, ff.fiscal_year,
           upper(btrim(regexp_replace(coalesce(ff.form, ''), '\s+', ' ', 'g'))) ~ p.proxy_form AS proxy,
           coalesce(pv.pv ->> 'validation', '') = 'unavailable' AS quarantined,
           coalesce(
               (SELECT max(f.filing_date)::date FROM filings f
                WHERE f.company_id = ff.company_id
                  AND replace(f.accession_number, '-', '') = replace(ff.accession, '-', '')),
               CASE WHEN pv.pv ->> 'filed_at' ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}'
                    THEN substring(pv.pv ->> 'filed_at' FROM 1 FOR 10)::date END) AS filed
    FROM financial_fact ff
    JOIN keyed k ON k.company_id = ff.company_id AND k.concept = ff.concept AND k.period_end = ff.period_end
                AND k.fiscal_period = ff.fiscal_period AND k.unit = ff.unit
    CROSS JOIN params p
    CROSS JOIN LATERAL (
        SELECT CASE WHEN ff.provenance IS NULL OR ff.provenance::text = 'null' THEN NULL
                    WHEN ff.provenance::text ~ p.json_hazard
                    THEN regexp_replace(ff.provenance::text, p.json_hazard, '\\ufffd', 'g')::jsonb
                    ELSE ff.provenance::jsonb END AS pv
    ) pv
), keys AS (
    SELECT d.company_id, d.concept, d.period_end, d.fiscal_period, d.unit,
           max(d.filed) FILTER (WHERE d.is_latest) AS current_filed, bool_or(d.is_latest) AS has_current,
           bool_or(d.is_latest AND d.proxy) AS proxy_current
    FROM dated d
    GROUP BY d.company_id, d.concept, d.period_end, d.fiscal_period, d.unit
), years AS (
    SELECT DISTINCT d.company_id, d.fiscal_year
    FROM keys k
    JOIN dated d ON d.company_id = k.company_id AND d.concept = k.concept AND d.period_end = k.period_end
                AND d.fiscal_period = k.fiscal_period AND d.unit = k.unit
    WHERE NOT k.proxy_current AND NOT d.is_latest AND NOT d.quarantined AND NOT d.proxy AND d.fiscal_year IS NOT NULL
      AND (NOT k.has_current OR (d.filed IS NOT NULL AND k.current_filed IS NOT NULL AND d.filed > k.current_filed))
), windows AS (
    SELECT ta.id, ta.company_id, ta.mode,
           CASE WHEN ta.mode = 'annual' AND ta.period_key ~ '^FY[0-9]{4}\.\.FY[0-9]{4}$'
                THEN substring(ta.period_key FROM 3 FOR 4)::int
                WHEN ta.mode = 'quarterly' AND ta.period_key ~ '^[0-9]{4}Q[1-4]\.\.[0-9]{4}Q[1-4]$'
                THEN substring(ta.period_key FROM 1 FOR 4)::int END AS first_year,
           CASE WHEN ta.mode = 'annual' AND ta.period_key ~ '^FY[0-9]{4}\.\.FY[0-9]{4}$'
                THEN substring(ta.period_key FROM 11 FOR 4)::int
                WHEN ta.mode = 'quarterly' AND ta.period_key ~ '^[0-9]{4}Q[1-4]\.\.[0-9]{4}Q[1-4]$'
                THEN substring(ta.period_key FROM 9 FOR 4)::int END AS last_year
    FROM trend_analysis ta
    JOIN usd_alone a ON a.company_id = ta.company_id
), saved AS (
    SELECT DISTINCT w.id, w.company_id, w.mode
    FROM windows w
    JOIN years y ON y.company_id = w.company_id AND y.fiscal_year BETWEEN w.first_year AND w.last_year
)
SELECT s.mode, count(*) AS saved_analyses, count(DISTINCT s.company_id) AS companies
FROM saved s
GROUP BY ROLLUP (s.mode)
ORDER BY GROUPING(s.mode), s.mode;

\echo '6. Companies in USD alone with the most keys behind (set 2), at most 50, for a dry run''s cohort: ticker, keys,'
\echo '   those under the current row''s own tag, gaps, and its last companyfacts sync; of_n counts them all.'
WITH params AS (
    SELECT '^[A-Z]{3}$'::text AS amount_code,
           '^[A-Z]+ ?14[AC][0-9A-Z]*(/A)?$'::text AS proxy_form,
           '\\u(0000|[dD][89a-fA-F][0-9a-fA-F]{2})'::text AS json_hazard
), usd_alone AS MATERIALIZED (
    SELECT ff.company_id
    FROM financial_fact ff CROSS JOIN params p
    GROUP BY ff.company_id
    HAVING NOT bool_or(split_part(ff.unit, '/', 1) ~ p.amount_code AND split_part(ff.unit, '/', 1) <> 'USD')
), keyed AS MATERIALIZED (
    SELECT DISTINCT ff.company_id, ff.concept, ff.period_end, ff.fiscal_period, ff.unit
    FROM financial_fact ff
    JOIN usd_alone a ON a.company_id = ff.company_id
    WHERE NOT ff.is_latest AND ff.fiscal_period IS NOT NULL AND split_part(ff.unit, '/', 1) = 'USD'
), dated AS MATERIALIZED (
    SELECT ff.company_id, ff.concept, ff.period_end, ff.fiscal_period, ff.unit, ff.is_latest, ff.raw_tag,
           upper(btrim(regexp_replace(coalesce(ff.form, ''), '\s+', ' ', 'g'))) ~ p.proxy_form AS proxy,
           coalesce(pv.pv ->> 'validation', '') = 'unavailable' AS quarantined,
           coalesce(
               (SELECT max(f.filing_date)::date FROM filings f
                WHERE f.company_id = ff.company_id
                  AND replace(f.accession_number, '-', '') = replace(ff.accession, '-', '')),
               CASE WHEN pv.pv ->> 'filed_at' ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}'
                    THEN substring(pv.pv ->> 'filed_at' FROM 1 FOR 10)::date END) AS filed
    FROM financial_fact ff
    JOIN keyed k ON k.company_id = ff.company_id AND k.concept = ff.concept AND k.period_end = ff.period_end
                AND k.fiscal_period = ff.fiscal_period AND k.unit = ff.unit
    CROSS JOIN params p
    CROSS JOIN LATERAL (
        SELECT CASE WHEN ff.provenance IS NULL OR ff.provenance::text = 'null' THEN NULL
                    WHEN ff.provenance::text ~ p.json_hazard
                    THEN regexp_replace(ff.provenance::text, p.json_hazard, '\\ufffd', 'g')::jsonb
                    ELSE ff.provenance::jsonb END AS pv
    ) pv
), keys AS (
    SELECT d.company_id, d.concept, d.period_end, d.fiscal_period, d.unit,
           max(d.filed) FILTER (WHERE d.is_latest) AS current_filed, bool_or(d.is_latest) AS has_current,
           bool_or(d.is_latest AND d.proxy) AS proxy_current,
           string_agg(DISTINCT coalesce(d.raw_tag, ''), ',') FILTER (WHERE d.is_latest) AS current_tags
    FROM dated d
    GROUP BY d.company_id, d.concept, d.period_end, d.fiscal_period, d.unit
), behind AS (
    SELECT k.company_id, k.has_current,
           bool_or(coalesce(d.raw_tag, '') = ANY (string_to_array(k.current_tags, ','))) AS same_tag
    FROM keys k
    JOIN dated d ON d.company_id = k.company_id AND d.concept = k.concept AND d.period_end = k.period_end
                AND d.fiscal_period = k.fiscal_period AND d.unit = k.unit
    WHERE NOT k.proxy_current AND NOT d.is_latest AND NOT d.quarantined AND NOT d.proxy
      AND (NOT k.has_current OR (d.filed IS NOT NULL AND k.current_filed IS NOT NULL AND d.filed > k.current_filed))
    GROUP BY k.company_id, k.concept, k.period_end, k.fiscal_period, k.unit, k.has_current
), by_company AS (
    SELECT b.company_id, count(*) AS keys, count(*) FILTER (WHERE b.same_tag) AS same_tag,
           count(*) FILTER (WHERE NOT b.has_current) AS gaps
    FROM behind b
    GROUP BY b.company_id
)
SELECT c.ticker, bc.company_id, bc.keys, bc.same_tag, bc.gaps, c.facts_synced_at,
       count(*) OVER () AS of_n
FROM by_company bc JOIN companies c ON c.id = bc.company_id
ORDER BY bc.keys DESC, c.ticker
LIMIT 50;

COMMIT;
