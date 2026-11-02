-- Detection: E198's reach, before and after its deploy (E198's pull request, #1956). With E198 every companyfacts sync
-- runs the currency step (facts/currency.py), a sync in USD alone too. At each key its payload presents (company,
-- concept, period end, fiscal period) in an amount or per-share unit, the convergence (_promote_batch_rows) makes the
-- payload's own stored row current and demotes every other current row there, unless a current row holds the key: one
-- of a filing filed strictly after the payload row's own (each dated by _filed: a Filing row, else the payload's filed,
-- else a provenance filed_at); such a row that is a feed row (no filing owner) of a filing the payload names holds only
-- where the upsert's own Filing-date rule keeps it too (R1u: it has a Filing row, dated, then by accession, after the
-- payload row's, or that row has none). Until E198 deploys, a sync in USD alone is the upsert alone, so a key it left
-- behind stays so: an amendment the per-filing writer stored behind its original's companyfacts row; a newer filing's
-- restatement under a lower-priority tag; a newer filing's row a lagging payload's insert demoted; a same-day filing's
-- row current over the payload's; a feed row an older rule read (an 8-K's recast) current over an older payload winner.
-- This file sizes those keys at the companies whose stored rows read no other currency (the syncs E198 changes; a
-- company storing another currency's row has run the step since #1583). It names companies and changes nothing.
--
-- An upper bound, not the count E198 moves. Each stored row that is not current is read as the payload's winner (which
-- SEC's payload alone says: the latest-filed item of the first registry tag with data) holding the payload's figure (a
-- stored identity holding another is left as found, R2), and each current feed row as one of a filing the payload
-- names. A key counts where such a row is one no current row there holds (eligible). Left out: a key whose current row
-- is a proxy statement's (E211's), a quarantined row (never made current), and a payload item no writer stored yet (the
-- sync's insert, which Guard.later decides). Quarter twins (the upsert's D1 rule) are not read, which only adds keys.
-- Ratios (pure) do not converge outside a key a newer filing the payload does not name holds: set 3 sizes the question
-- E198 leaves open, read as set 2 reads amounts.
--
-- Definitions. amount: a unit whose part before '/' is three capital letters (USD, USD/shares; is_amount_unit). USD
-- alone: the company stores no row in such a unit other than USD or USD/shares (current or not), a company-level
-- reading of _another_currency, which reads the batch's concepts: only the concepts its companyfacts rows hold count
-- (fed), and a company with no companyfacts row has never synced and is left out (set 1 counts it). filed, a row's
-- date: its Filing row's date (same company, accession with dashes ignored), else the first ten characters of its
-- provenance filed_at where they spell YYYY-MM-DD, else none. It is text, compared as _filed compares its strings, so
-- an impossible day sorts where the sync sorts it and no value is cast or raises. The sync also reads the payload's
-- filed dates, which this cannot see, so a row with no date here leaves its key undecided. owned: the date of the
-- Filing row whose accession is the row's own exactly, as the sync reads it (_filing_dates). Text compares under
-- COLLATE "C", as Python compares strings. quarantined: provenance validation 'unavailable' (currency._promotable).
-- proxy: the form, its whitespace collapsed, trimmed and upper-cased, matches ^[A-Z]+ ?14[AC][0-9A-Z]*(/A)?$
-- (is_proxy_form; gated by backend/tests/unit/test_usd_sync_convergence_detection_sql.py). candidate: a row with a
-- fiscal period that is not current, not quarantined and no proxy's. holds: a current row at its key filed after the
-- candidate, which has a filing owner, or an owned date that outranks the candidate's (owned, then accession) or a
-- candidate with none. shape, each key's most likely, in this order: later (a candidate filed after every current row),
-- same_day (filed the day of the latest current row), r1u (filed before it, or undated, where every current row is a
-- feed row the Filing-date rule does not keep), gap (no current row), undated (a date this cannot see decides it).
-- same_tag: a candidate carries a current row's own tag (an untagged row matches an untagged one). kind: amendment (a
-- candidate's form ends in /A) or original; source: feed (companyfacts, no filing owner), filing (a filing owner: the
-- per-filing writer's, or the cross-check's replacement), derived.
--
-- Readback. Ops detection-sql runs only main's SQL, and never while a main push's deploy is in flight, so this file
-- lands on main before E198: run it before E198's merge (the before, the exposure bound) and after the companies' next
-- syncs (the after). A key moves only where the payload's winner is not current already, which this cannot see, so the
-- after run reads by shape: later same_tag keys should fall to the doubtful remainder; a key r1u moved reads as later
-- after it (the row it demoted is filed after the one now current), and a same_day key reads alike before and after,
-- whichever same-day row is current; an undated key can stay listed. Retire: the records PR that reports the after run
-- deletes this file and its test (tasks/todo.md, E198).
--
-- Read-only: one REPEATABLE READ READ ONLY transaction, so every set shares one snapshot. Each statement gets 120 s and
-- waits at most 10 s for a lock (SET LOCAL below; the step's PGOPTIONS allow 600 s). Cost per statement: two scans of
-- financial_fact, for its companyfacts concepts (fed) and for the keys that hold a row that is not current (no index
-- holds is_latest alone), then their rows through uq_financial_fact_identity's (company, concept, period_end) prefix,
-- the provenance of those rows parsed once, the filings of those keys' companies once, by accession, hash-joined, and
-- each row's own Filing row through its unique accession index; each candidate then meets the few current rows at its
-- key. A list stops at 50 rows and carries its set's full count (of_n). JSON: -> and ->> raise for a whole json value
-- holding a NUL or a lone-surrogate escape, so provenance is read after rewriting a NUL or any surrogate escape to the
-- escape of U+FFFD (same length; nothing else moves), as #1532 did. Patterns assume standard_conforming_strings = on
-- (the default).
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout = '120s';
SET LOCAL lock_timeout = '10s';

\echo '0. Session: this transaction is read-only and bounded.'
SELECT current_setting('transaction_read_only') AS read_only,
       current_setting('transaction_isolation') AS isolation,
       current_setting('statement_timeout') AS statement_timeout,
       current_setting('lock_timeout') AS lock_timeout;

\echo '1. Companies holding financial_fact rows: those in USD alone (each sync of theirs changes at E198''s deploy),'
\echo '   those storing another currency''s amount or per-share row in a concept their companyfacts rows hold (their'
\echo '   syncs have run the step since #1583), and those with no companyfacts row (never synced), with their current'
\echo '   amount and per-share rows.'
WITH params AS (
    SELECT '^[A-Z]{3}$'::text AS amount_code
), fed AS MATERIALIZED (
    SELECT DISTINCT company_id, concept FROM financial_fact WHERE source = 'companyfacts'
), units AS MATERIALIZED (
    SELECT ff.company_id,
           bool_or(f.concept IS NOT NULL AND split_part(ff.unit, '/', 1) ~ p.amount_code
                   AND split_part(ff.unit, '/', 1) <> 'USD') AS other,
           count(*) FILTER (WHERE ff.is_latest AND split_part(ff.unit, '/', 1) ~ p.amount_code) AS current_amount_rows,
           bool_or(f.concept IS NOT NULL) AS synced
    FROM financial_fact ff
    LEFT JOIN fed f ON f.company_id = ff.company_id AND f.concept = ff.concept
    CROSS JOIN params p
    GROUP BY ff.company_id
), readings AS (
    SELECT CASE WHEN NOT u.synced THEN 'never_synced' WHEN u.other THEN 'another_currency' ELSE 'usd_alone' END
           AS reading, u.current_amount_rows
    FROM units u
)
SELECT r.reading, count(*) AS companies, sum(r.current_amount_rows) AS current_amount_rows
FROM readings r
GROUP BY ROLLUP (r.reading)
ORDER BY GROUPING(r.reading), r.reading;

\echo '2. Keys at companies in USD alone where a row that is not current is eligible (see the header), by shape,'
\echo '   fiscal period (FY or a quarter), the candidates'' kind and source, and whether one carries the current row''s'
\echo '   own tag (same_tag; a gap carries none), then by shape, then in total (the row with every key blank): keys,'
\echo '   companies, and the candidates'' newest date. An upper bound: see the header.'
WITH params AS (
    SELECT '^[A-Z]{3}$'::text AS amount_code,
           '^[A-Z]+ ?14[AC][0-9A-Z]*(/A)?$'::text AS proxy_form,
           '\\u(0000|[dD][89a-fA-F][0-9a-fA-F]{2})'::text AS json_hazard
), fed AS MATERIALIZED (
    SELECT DISTINCT company_id, concept FROM financial_fact WHERE source = 'companyfacts'
), usd_alone AS MATERIALIZED (
    SELECT ff.company_id
    FROM financial_fact ff
    JOIN fed f ON f.company_id = ff.company_id AND f.concept = ff.concept
    CROSS JOIN params p
    GROUP BY ff.company_id
    HAVING NOT bool_or(split_part(ff.unit, '/', 1) ~ p.amount_code AND split_part(ff.unit, '/', 1) <> 'USD')
), keyed AS MATERIALIZED (
    SELECT DISTINCT ff.company_id, ff.concept, ff.period_end, ff.fiscal_period, ff.unit
    FROM financial_fact ff
    JOIN usd_alone a ON a.company_id = ff.company_id
    WHERE NOT ff.is_latest AND ff.fiscal_period IS NOT NULL AND split_part(ff.unit, '/', 1) = 'USD'
), filing_dates AS MATERIALIZED (
    SELECT f.company_id, replace(f.accession_number, '-', '') AS acc, max(f.filing_date) AS filed
    FROM filings f
    WHERE f.company_id IN (SELECT company_id FROM keyed)
    GROUP BY f.company_id, replace(f.accession_number, '-', '')
), dated AS MATERIALIZED (
    SELECT ff.id, ff.company_id, ff.concept, ff.period_end, ff.fiscal_period, ff.unit, ff.is_latest, ff.raw_tag,
           ff.source, ff.filing_id, ff.form, ff.fiscal_year, ff.accession COLLATE "C" AS accession,
           upper(btrim(regexp_replace(coalesce(ff.form, ''), '\s+', ' ', 'g'))) ~ p.proxy_form AS proxy,
           coalesce(pv.pv ->> 'validation', '') = 'unavailable' AS quarantined,
           to_char(fe.filing_date, 'YYYY-MM-DD') COLLATE "C" AS owned,
           coalesce(to_char(fd.filed, 'YYYY-MM-DD'),
                    CASE WHEN pv.pv ->> 'filed_at' ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}'
                         THEN left(pv.pv ->> 'filed_at', 10) END) COLLATE "C" AS filed
    FROM financial_fact ff
    JOIN keyed k ON k.company_id = ff.company_id AND k.concept = ff.concept AND k.period_end = ff.period_end
                AND k.fiscal_period = ff.fiscal_period AND k.unit = ff.unit
    LEFT JOIN filing_dates fd ON fd.company_id = ff.company_id AND fd.acc = replace(ff.accession, '-', '')
    LEFT JOIN filings fe ON fe.accession_number = ff.accession
    CROSS JOIN params p
    CROSS JOIN LATERAL (
        SELECT CASE WHEN ff.provenance IS NULL OR ff.provenance::text = 'null' THEN NULL
                    WHEN ff.provenance::text ~ p.json_hazard
                    THEN regexp_replace(ff.provenance::text, p.json_hazard, '\\ufffd', 'g')::jsonb
                    ELSE ff.provenance::jsonb END AS pv
    ) pv
), candidates AS (
    SELECT d.id, d.company_id, d.concept, d.period_end, d.fiscal_period, d.unit, d.fiscal_year, d.raw_tag, d.form,
           d.source, d.filing_id, d.filed,
           bool_or(o.id IS NOT NULL) AS has_current, coalesce(bool_or(o.proxy), false) AS proxy_current,
           bool_or(h.holds) AS held, bool_or(o.id IS NOT NULL AND h.holds IS NULL) AS open,
           max(o.filed) AS current_filed,
           string_agg(DISTINCT coalesce(o.raw_tag, '-'), ',') FILTER (WHERE o.id IS NOT NULL) AS current_tags
    FROM dated d
    LEFT JOIN dated o ON o.company_id = d.company_id AND o.concept = d.concept AND o.period_end = d.period_end
                     AND o.fiscal_period = d.fiscal_period AND o.unit = d.unit AND o.is_latest
    CROSS JOIN LATERAL (
        SELECT o.filed > d.filed AND (o.filing_id IS NOT NULL OR (o.owned IS NOT NULL
               AND (d.owned IS NULL OR (o.owned, o.accession) > (d.owned, d.accession)))) AS holds
    ) h
    WHERE NOT d.is_latest AND NOT d.quarantined AND NOT d.proxy
    GROUP BY d.id, d.company_id, d.concept, d.period_end, d.fiscal_period, d.unit, d.fiscal_year, d.raw_tag, d.form,
             d.source, d.filing_id, d.filed
), eligible AS (
    SELECT c.*,
           CASE WHEN NOT c.has_current THEN 'gap' WHEN c.open THEN 'undated' WHEN c.filed > c.current_filed THEN 'later'
                WHEN c.filed = c.current_filed THEN 'same_day' ELSE 'r1u' END AS shape
    FROM candidates c
    WHERE NOT c.proxy_current AND NOT coalesce(c.held, false)
), keys AS (
    SELECT e.company_id, CASE WHEN e.fiscal_period = 'FY' THEN 'FY' ELSE 'Q' END AS fp,
           min(CASE e.shape WHEN 'later' THEN 1 WHEN 'same_day' THEN 2 WHEN 'r1u' THEN 3 WHEN 'gap' THEN 4
                            ELSE 5 END) AS rank,
           CASE WHEN bool_or(upper(coalesce(e.form, '')) LIKE '%/A') THEN 'amendment' ELSE 'original' END AS kind,
           CASE WHEN bool_or(e.source = 'derived') THEN 'derived'
                WHEN bool_or(e.filing_id IS NOT NULL) THEN 'filing' ELSE 'feed' END AS source,
           CASE WHEN NOT bool_or(e.has_current) THEN 'gap'
                WHEN bool_or(coalesce(e.raw_tag, '-') = ANY (string_to_array(e.current_tags, ','))) THEN 'same_tag'
                ELSE 'other_tag' END AS tag,
           max(e.filed) AS candidate_filed
    FROM eligible e
    GROUP BY e.company_id, e.concept, e.period_end, e.fiscal_period, e.unit
)
SELECT CASE WHEN GROUPING(k.rank) = 1 THEN NULL ELSE (ARRAY['later', 'same_day', 'r1u', 'gap', 'undated'])[k.rank]
       END AS shape, k.fp, k.kind, k.source, k.tag,
       count(*) AS keys, count(DISTINCT k.company_id) AS companies, max(k.candidate_filed) AS newest_candidate_filed
FROM keys k
GROUP BY GROUPING SETS ((k.rank, k.fp, k.kind, k.source, k.tag), (k.rank), ())
ORDER BY GROUPING(k.rank), k.rank, GROUPING(k.fp), k.fp, k.kind, k.source, k.tag;

\echo '3. Ratio keys (pure) at companies in USD alone where a row that is not current is eligible, as set 2 reads'
\echo '   amounts: E198 converges no ratio outside a key a newer filing the payload does not name holds (the question'
\echo '   E198 leaves open), by fiscal period and shape.'
WITH params AS (
    SELECT '^[A-Z]{3}$'::text AS amount_code,
           '^[A-Z]+ ?14[AC][0-9A-Z]*(/A)?$'::text AS proxy_form,
           '\\u(0000|[dD][89a-fA-F][0-9a-fA-F]{2})'::text AS json_hazard
), fed AS MATERIALIZED (
    SELECT DISTINCT company_id, concept FROM financial_fact WHERE source = 'companyfacts'
), usd_alone AS MATERIALIZED (
    SELECT ff.company_id
    FROM financial_fact ff
    JOIN fed f ON f.company_id = ff.company_id AND f.concept = ff.concept
    CROSS JOIN params p
    GROUP BY ff.company_id
    HAVING NOT bool_or(split_part(ff.unit, '/', 1) ~ p.amount_code AND split_part(ff.unit, '/', 1) <> 'USD')
), keyed AS MATERIALIZED (
    SELECT DISTINCT ff.company_id, ff.concept, ff.period_end, ff.fiscal_period, ff.unit
    FROM financial_fact ff
    JOIN usd_alone a ON a.company_id = ff.company_id
    WHERE NOT ff.is_latest AND ff.fiscal_period IS NOT NULL AND ff.unit = 'pure'
), filing_dates AS MATERIALIZED (
    SELECT f.company_id, replace(f.accession_number, '-', '') AS acc, max(f.filing_date) AS filed
    FROM filings f
    WHERE f.company_id IN (SELECT company_id FROM keyed)
    GROUP BY f.company_id, replace(f.accession_number, '-', '')
), dated AS MATERIALIZED (
    SELECT ff.id, ff.company_id, ff.concept, ff.period_end, ff.fiscal_period, ff.unit, ff.is_latest, ff.raw_tag,
           ff.source, ff.filing_id, ff.form, ff.fiscal_year, ff.accession COLLATE "C" AS accession,
           upper(btrim(regexp_replace(coalesce(ff.form, ''), '\s+', ' ', 'g'))) ~ p.proxy_form AS proxy,
           coalesce(pv.pv ->> 'validation', '') = 'unavailable' AS quarantined,
           to_char(fe.filing_date, 'YYYY-MM-DD') COLLATE "C" AS owned,
           coalesce(to_char(fd.filed, 'YYYY-MM-DD'),
                    CASE WHEN pv.pv ->> 'filed_at' ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}'
                         THEN left(pv.pv ->> 'filed_at', 10) END) COLLATE "C" AS filed
    FROM financial_fact ff
    JOIN keyed k ON k.company_id = ff.company_id AND k.concept = ff.concept AND k.period_end = ff.period_end
                AND k.fiscal_period = ff.fiscal_period AND k.unit = ff.unit
    LEFT JOIN filing_dates fd ON fd.company_id = ff.company_id AND fd.acc = replace(ff.accession, '-', '')
    LEFT JOIN filings fe ON fe.accession_number = ff.accession
    CROSS JOIN params p
    CROSS JOIN LATERAL (
        SELECT CASE WHEN ff.provenance IS NULL OR ff.provenance::text = 'null' THEN NULL
                    WHEN ff.provenance::text ~ p.json_hazard
                    THEN regexp_replace(ff.provenance::text, p.json_hazard, '\\ufffd', 'g')::jsonb
                    ELSE ff.provenance::jsonb END AS pv
    ) pv
), candidates AS (
    SELECT d.id, d.company_id, d.concept, d.period_end, d.fiscal_period, d.unit, d.fiscal_year, d.raw_tag, d.form,
           d.source, d.filing_id, d.filed,
           bool_or(o.id IS NOT NULL) AS has_current, coalesce(bool_or(o.proxy), false) AS proxy_current,
           bool_or(h.holds) AS held, bool_or(o.id IS NOT NULL AND h.holds IS NULL) AS open,
           max(o.filed) AS current_filed,
           string_agg(DISTINCT coalesce(o.raw_tag, '-'), ',') FILTER (WHERE o.id IS NOT NULL) AS current_tags
    FROM dated d
    LEFT JOIN dated o ON o.company_id = d.company_id AND o.concept = d.concept AND o.period_end = d.period_end
                     AND o.fiscal_period = d.fiscal_period AND o.unit = d.unit AND o.is_latest
    CROSS JOIN LATERAL (
        SELECT o.filed > d.filed AND (o.filing_id IS NOT NULL OR (o.owned IS NOT NULL
               AND (d.owned IS NULL OR (o.owned, o.accession) > (d.owned, d.accession)))) AS holds
    ) h
    WHERE NOT d.is_latest AND NOT d.quarantined AND NOT d.proxy
    GROUP BY d.id, d.company_id, d.concept, d.period_end, d.fiscal_period, d.unit, d.fiscal_year, d.raw_tag, d.form,
             d.source, d.filing_id, d.filed
), eligible AS (
    SELECT c.*,
           CASE WHEN NOT c.has_current THEN 'gap' WHEN c.open THEN 'undated' WHEN c.filed > c.current_filed THEN 'later'
                WHEN c.filed = c.current_filed THEN 'same_day' ELSE 'r1u' END AS shape
    FROM candidates c
    WHERE NOT c.proxy_current AND NOT coalesce(c.held, false)
), keys AS (
    SELECT e.company_id, CASE WHEN e.fiscal_period = 'FY' THEN 'FY' ELSE 'Q' END AS fp,
           min(CASE e.shape WHEN 'later' THEN 1 WHEN 'same_day' THEN 2 WHEN 'r1u' THEN 3 WHEN 'gap' THEN 4
                            ELSE 5 END) AS rank
    FROM eligible e
    GROUP BY e.company_id, e.concept, e.period_end, e.fiscal_period, e.unit
)
SELECT k.fp, CASE WHEN GROUPING(k.rank) = 1 THEN NULL ELSE (ARRAY['later', 'same_day', 'r1u', 'gap', 'undated'])[k.rank]
             END AS shape,
       count(*) AS keys, count(DISTINCT k.company_id) AS companies
FROM keys k
GROUP BY GROUPING SETS ((k.fp, k.rank), ())
ORDER BY GROUPING(k.fp), k.fp, k.rank;

\echo '4. Quarantined rows (provenance validation unavailable), which no sync makes current: rows and companies, in'
\echo '   total and at companies in USD alone. Where one is the payload''s own row, E198''s sync leaves its key as found'
\echo '   and demotes its own insert there (a gap where a lagging payload inserted, never its older figure).'
WITH params AS (
    SELECT '^[A-Z]{3}$'::text AS amount_code,
           '\\u(0000|[dD][89a-fA-F][0-9a-fA-F]{2})'::text AS json_hazard
), fed AS MATERIALIZED (
    SELECT DISTINCT company_id, concept FROM financial_fact WHERE source = 'companyfacts'
), usd_alone AS MATERIALIZED (
    SELECT ff.company_id
    FROM financial_fact ff
    JOIN fed f ON f.company_id = ff.company_id AND f.concept = ff.concept
    CROSS JOIN params p
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

\echo '5. Saved analyses whose window holds the fiscal year of a set-2 eligible row, any shape (annual:'
\echo '   FYyyyy..FYyyyy; quarterly by the years of yyyyQn..yyyyQn): where its key moves at the company''s next sync,'
\echo '   the dataset''s fingerprint changes, so its narrative regenerates once at next open (unmetered) and its saved'
\echo '   PDF answers 409 until it is re-run. An upper bound, as set 2 is.'
WITH params AS (
    SELECT '^[A-Z]{3}$'::text AS amount_code,
           '^[A-Z]+ ?14[AC][0-9A-Z]*(/A)?$'::text AS proxy_form,
           '\\u(0000|[dD][89a-fA-F][0-9a-fA-F]{2})'::text AS json_hazard
), fed AS MATERIALIZED (
    SELECT DISTINCT company_id, concept FROM financial_fact WHERE source = 'companyfacts'
), usd_alone AS MATERIALIZED (
    SELECT ff.company_id
    FROM financial_fact ff
    JOIN fed f ON f.company_id = ff.company_id AND f.concept = ff.concept
    CROSS JOIN params p
    GROUP BY ff.company_id
    HAVING NOT bool_or(split_part(ff.unit, '/', 1) ~ p.amount_code AND split_part(ff.unit, '/', 1) <> 'USD')
), keyed AS MATERIALIZED (
    SELECT DISTINCT ff.company_id, ff.concept, ff.period_end, ff.fiscal_period, ff.unit
    FROM financial_fact ff
    JOIN usd_alone a ON a.company_id = ff.company_id
    WHERE NOT ff.is_latest AND ff.fiscal_period IS NOT NULL AND split_part(ff.unit, '/', 1) = 'USD'
), filing_dates AS MATERIALIZED (
    SELECT f.company_id, replace(f.accession_number, '-', '') AS acc, max(f.filing_date) AS filed
    FROM filings f
    WHERE f.company_id IN (SELECT company_id FROM keyed)
    GROUP BY f.company_id, replace(f.accession_number, '-', '')
), dated AS MATERIALIZED (
    SELECT ff.id, ff.company_id, ff.concept, ff.period_end, ff.fiscal_period, ff.unit, ff.is_latest, ff.raw_tag,
           ff.source, ff.filing_id, ff.form, ff.fiscal_year, ff.accession COLLATE "C" AS accession,
           upper(btrim(regexp_replace(coalesce(ff.form, ''), '\s+', ' ', 'g'))) ~ p.proxy_form AS proxy,
           coalesce(pv.pv ->> 'validation', '') = 'unavailable' AS quarantined,
           to_char(fe.filing_date, 'YYYY-MM-DD') COLLATE "C" AS owned,
           coalesce(to_char(fd.filed, 'YYYY-MM-DD'),
                    CASE WHEN pv.pv ->> 'filed_at' ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}'
                         THEN left(pv.pv ->> 'filed_at', 10) END) COLLATE "C" AS filed
    FROM financial_fact ff
    JOIN keyed k ON k.company_id = ff.company_id AND k.concept = ff.concept AND k.period_end = ff.period_end
                AND k.fiscal_period = ff.fiscal_period AND k.unit = ff.unit
    LEFT JOIN filing_dates fd ON fd.company_id = ff.company_id AND fd.acc = replace(ff.accession, '-', '')
    LEFT JOIN filings fe ON fe.accession_number = ff.accession
    CROSS JOIN params p
    CROSS JOIN LATERAL (
        SELECT CASE WHEN ff.provenance IS NULL OR ff.provenance::text = 'null' THEN NULL
                    WHEN ff.provenance::text ~ p.json_hazard
                    THEN regexp_replace(ff.provenance::text, p.json_hazard, '\\ufffd', 'g')::jsonb
                    ELSE ff.provenance::jsonb END AS pv
    ) pv
), candidates AS (
    SELECT d.id, d.company_id, d.concept, d.period_end, d.fiscal_period, d.unit, d.fiscal_year, d.raw_tag, d.form,
           d.source, d.filing_id, d.filed,
           bool_or(o.id IS NOT NULL) AS has_current, coalesce(bool_or(o.proxy), false) AS proxy_current,
           bool_or(h.holds) AS held, bool_or(o.id IS NOT NULL AND h.holds IS NULL) AS open,
           max(o.filed) AS current_filed,
           string_agg(DISTINCT coalesce(o.raw_tag, '-'), ',') FILTER (WHERE o.id IS NOT NULL) AS current_tags
    FROM dated d
    LEFT JOIN dated o ON o.company_id = d.company_id AND o.concept = d.concept AND o.period_end = d.period_end
                     AND o.fiscal_period = d.fiscal_period AND o.unit = d.unit AND o.is_latest
    CROSS JOIN LATERAL (
        SELECT o.filed > d.filed AND (o.filing_id IS NOT NULL OR (o.owned IS NOT NULL
               AND (d.owned IS NULL OR (o.owned, o.accession) > (d.owned, d.accession)))) AS holds
    ) h
    WHERE NOT d.is_latest AND NOT d.quarantined AND NOT d.proxy
    GROUP BY d.id, d.company_id, d.concept, d.period_end, d.fiscal_period, d.unit, d.fiscal_year, d.raw_tag, d.form,
             d.source, d.filing_id, d.filed
), eligible AS (
    SELECT c.*,
           CASE WHEN NOT c.has_current THEN 'gap' WHEN c.open THEN 'undated' WHEN c.filed > c.current_filed THEN 'later'
                WHEN c.filed = c.current_filed THEN 'same_day' ELSE 'r1u' END AS shape
    FROM candidates c
    WHERE NOT c.proxy_current AND NOT coalesce(c.held, false)
), years AS (
    SELECT DISTINCT e.company_id, e.fiscal_year FROM eligible e WHERE e.fiscal_year IS NOT NULL
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

\echo '6. Companies in USD alone with the most decided keys in set 2 (any shape but undated), then the most keys, at'
\echo '   most 50, for a dry run''s cohort (an undated key can stay listed after a sync): ticker, keys, keys by shape,'
\echo '   those where a candidate carries the current row''s own tag, and its last companyfacts sync; of_n counts them'
\echo '   all.'
WITH params AS (
    SELECT '^[A-Z]{3}$'::text AS amount_code,
           '^[A-Z]+ ?14[AC][0-9A-Z]*(/A)?$'::text AS proxy_form,
           '\\u(0000|[dD][89a-fA-F][0-9a-fA-F]{2})'::text AS json_hazard
), fed AS MATERIALIZED (
    SELECT DISTINCT company_id, concept FROM financial_fact WHERE source = 'companyfacts'
), usd_alone AS MATERIALIZED (
    SELECT ff.company_id
    FROM financial_fact ff
    JOIN fed f ON f.company_id = ff.company_id AND f.concept = ff.concept
    CROSS JOIN params p
    GROUP BY ff.company_id
    HAVING NOT bool_or(split_part(ff.unit, '/', 1) ~ p.amount_code AND split_part(ff.unit, '/', 1) <> 'USD')
), keyed AS MATERIALIZED (
    SELECT DISTINCT ff.company_id, ff.concept, ff.period_end, ff.fiscal_period, ff.unit
    FROM financial_fact ff
    JOIN usd_alone a ON a.company_id = ff.company_id
    WHERE NOT ff.is_latest AND ff.fiscal_period IS NOT NULL AND split_part(ff.unit, '/', 1) = 'USD'
), filing_dates AS MATERIALIZED (
    SELECT f.company_id, replace(f.accession_number, '-', '') AS acc, max(f.filing_date) AS filed
    FROM filings f
    WHERE f.company_id IN (SELECT company_id FROM keyed)
    GROUP BY f.company_id, replace(f.accession_number, '-', '')
), dated AS MATERIALIZED (
    SELECT ff.id, ff.company_id, ff.concept, ff.period_end, ff.fiscal_period, ff.unit, ff.is_latest, ff.raw_tag,
           ff.source, ff.filing_id, ff.form, ff.fiscal_year, ff.accession COLLATE "C" AS accession,
           upper(btrim(regexp_replace(coalesce(ff.form, ''), '\s+', ' ', 'g'))) ~ p.proxy_form AS proxy,
           coalesce(pv.pv ->> 'validation', '') = 'unavailable' AS quarantined,
           to_char(fe.filing_date, 'YYYY-MM-DD') COLLATE "C" AS owned,
           coalesce(to_char(fd.filed, 'YYYY-MM-DD'),
                    CASE WHEN pv.pv ->> 'filed_at' ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}'
                         THEN left(pv.pv ->> 'filed_at', 10) END) COLLATE "C" AS filed
    FROM financial_fact ff
    JOIN keyed k ON k.company_id = ff.company_id AND k.concept = ff.concept AND k.period_end = ff.period_end
                AND k.fiscal_period = ff.fiscal_period AND k.unit = ff.unit
    LEFT JOIN filing_dates fd ON fd.company_id = ff.company_id AND fd.acc = replace(ff.accession, '-', '')
    LEFT JOIN filings fe ON fe.accession_number = ff.accession
    CROSS JOIN params p
    CROSS JOIN LATERAL (
        SELECT CASE WHEN ff.provenance IS NULL OR ff.provenance::text = 'null' THEN NULL
                    WHEN ff.provenance::text ~ p.json_hazard
                    THEN regexp_replace(ff.provenance::text, p.json_hazard, '\\ufffd', 'g')::jsonb
                    ELSE ff.provenance::jsonb END AS pv
    ) pv
), candidates AS (
    SELECT d.id, d.company_id, d.concept, d.period_end, d.fiscal_period, d.unit, d.fiscal_year, d.raw_tag, d.form,
           d.source, d.filing_id, d.filed,
           bool_or(o.id IS NOT NULL) AS has_current, coalesce(bool_or(o.proxy), false) AS proxy_current,
           bool_or(h.holds) AS held, bool_or(o.id IS NOT NULL AND h.holds IS NULL) AS open,
           max(o.filed) AS current_filed,
           string_agg(DISTINCT coalesce(o.raw_tag, '-'), ',') FILTER (WHERE o.id IS NOT NULL) AS current_tags
    FROM dated d
    LEFT JOIN dated o ON o.company_id = d.company_id AND o.concept = d.concept AND o.period_end = d.period_end
                     AND o.fiscal_period = d.fiscal_period AND o.unit = d.unit AND o.is_latest
    CROSS JOIN LATERAL (
        SELECT o.filed > d.filed AND (o.filing_id IS NOT NULL OR (o.owned IS NOT NULL
               AND (d.owned IS NULL OR (o.owned, o.accession) > (d.owned, d.accession)))) AS holds
    ) h
    WHERE NOT d.is_latest AND NOT d.quarantined AND NOT d.proxy
    GROUP BY d.id, d.company_id, d.concept, d.period_end, d.fiscal_period, d.unit, d.fiscal_year, d.raw_tag, d.form,
             d.source, d.filing_id, d.filed
), eligible AS (
    SELECT c.*,
           CASE WHEN NOT c.has_current THEN 'gap' WHEN c.open THEN 'undated' WHEN c.filed > c.current_filed THEN 'later'
                WHEN c.filed = c.current_filed THEN 'same_day' ELSE 'r1u' END AS shape
    FROM candidates c
    WHERE NOT c.proxy_current AND NOT coalesce(c.held, false)
), keys AS (
    SELECT e.company_id,
           min(CASE e.shape WHEN 'later' THEN 1 WHEN 'same_day' THEN 2 WHEN 'r1u' THEN 3 WHEN 'gap' THEN 4
                            ELSE 5 END) AS rank,
           bool_or(coalesce(e.raw_tag, '-') = ANY (string_to_array(e.current_tags, ','))) AS same_tag
    FROM eligible e
    GROUP BY e.company_id, e.concept, e.period_end, e.fiscal_period, e.unit
), by_company AS (
    SELECT k.company_id, count(*) AS keys, count(*) FILTER (WHERE k.rank = 1) AS later,
           count(*) FILTER (WHERE k.rank = 2) AS same_day, count(*) FILTER (WHERE k.rank = 3) AS r1u,
           count(*) FILTER (WHERE k.rank = 4) AS gaps, count(*) FILTER (WHERE k.rank = 5) AS undated,
           count(*) FILTER (WHERE k.same_tag) AS same_tag
    FROM keys k
    GROUP BY k.company_id
)
SELECT c.ticker, bc.company_id, bc.keys, bc.later, bc.same_day, bc.r1u, bc.gaps, bc.undated, bc.same_tag,
       c.facts_synced_at, count(*) OVER () AS of_n
FROM by_company bc JOIN companies c ON c.id = bc.company_id
ORDER BY bc.keys - bc.undated DESC, bc.keys DESC, c.ticker
LIMIT 50;

COMMIT;
