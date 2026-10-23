-- Detection: non-USD filers' stored summaries that print a native figure under "$" (F61 call 1:
-- the read-only count #1375 asked for before choosing a read-time chip check, per-filing
-- regeneration or a version bump). Before #1375 (1f72f89f) the AI-timeout fallback
-- (fallback_summary.py) and the prior-period backfill (schemas/summary.py _format_xbrl_value) wrote
-- "$" for every filer, as the primary filler (ai/markdown_render.py) did until the v2 cutover
-- (d7a80010e, 2026-07-09). A CNY figure under "$" reads ~7x too large, and the SEC-verified chip
-- matches its number only. Retire this file once F61's fix lands.
--
-- Fix boundary 2026-10-18 10:51:13 UTC: the end of the deploy-backend job that shipped 1f72f89f
-- (CI run 39119761394; the service took traffic at 10:50:25, the worker and job images by
-- 10:50:56). The merge was 10:34:00; rows written in between count as before the fix
-- (written_merge_to_deploy). An old-revision generation still in flight can land just after the
-- boundary: the after-fix dollar_in_cells column is the control. Stored at = COALESCE(updated_at,
-- created_at): finalize.py sets created_at on insert, updated_at on an in-place regeneration. One
-- summary per filing (uq_summaries_filing_id).
-- Stamp: stale mirrors summary_versioning.is_stale, which is refresh-stale's default filter
-- (summary_refresh.py stale_filter): a missing stamp, or one other than schema 2 and prompt
-- summary-2026-09-u, main's stamps when this was written (update params if they move first).
-- Reporting currency: filings.xbrl_data->>'reporting_currency' (what the writers read); when
-- absent, the most frequent three-letter unit of financial_fact rows with the filing's accession,
-- USD included (a tie goes to the non-USD unit, as facts/currency.py ranks); else "none recorded"
-- (a context row, like USD). A filing whose xbrl_data records no currency still printed "$" after
-- the fix (money_prefix_for(None), utils/numbers.py), so after-fix hits among currency_from_facts
-- rows come from that default.
-- Fallback: generate_xbrl_summary's fixed text, the headline "<name> <form> Filing - Partial
-- Analysis" in the_print (v2, an em dash) or executive_snapshot (v1, a hyphen), or the markdown's
-- "Click 'Regenerate Analysis'" line. raw_summary.status = 'partial' is no marker: the model path
-- stores it at low coverage too (summary_finalize.py determine_status). Full: every other summary.
-- A fallback stored before 2026-01-26 (184701c4d) may carry neither marker and counts as full; the
-- all-non-USD totals hold.
-- "$" figure: "$" then a digit, or "-" and a digit ($941.2B, $868,687,000,000, $-0.50), not after
-- an ASCII letter (US$, HK$ and NT$ are labels the old writers never wrote). JSON is matched as
-- stored, so a JSON escape before the "$" (a newline, a non-ASCII character) counts as no letter.
-- Reader fields: business_overview, management_discussion, key_changes, financial_highlights,
-- risk_factors and raw_summary's sections (not its audits). Cells: the P&L table rows of
-- financial_highlights and of sections.results_that_matter (v2) or .financial_highlights (v1);
-- current = current_period, prior = prior_period (where the backfill wrote), camelCase twins
-- included. in_current_cells is an upper bound on what the chip shows: the chip checks the
-- current_period of a mapped metric worth at least 1e6 (provenance_service.py
-- build_metric_source), so an EPS cell never carries it.
-- -> and ->> raise for a whole json value that holds a NUL or a lone-surrogate escape, so a value
-- holding a NUL or any surrogate escape is read after those escapes are rewritten to the escape of
-- U+FFFD (same length, nothing else moves). Patterns assume standard_conforming_strings = on (the
-- default). The classification CTEs are repeated verbatim in each statement.
-- Read-only (one READ ONLY transaction, so all three share one snapshot); tables: summaries,
-- filings, companies, financial_fact. Per statement: one seq scan of summaries joined to filings
-- (each summarized filing's xbrl_data read once); financial_fact only through
-- ix_financial_fact_accession, for filings with no recorded currency (never a full scan); summary
-- bodies of non-USD rows only, by primary key.
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;

\echo '1. Summaries by the filing''s reporting currency and when stored (fix live 2026-10-18 10:51:13 UTC).'
\echo '   The USD and none-recorded rows are context: their summary bodies are not read.'
WITH params AS (
    SELECT timestamptz '2026-10-18 10:34:00+00' AS merged_at,
           timestamptz '2026-10-18 10:51:13+00' AS fix_live_at,
           2 AS current_schema,
           'summary-2026-09-u'::text AS current_prompt,
           '(^|[^A-Za-z]|\\[nrtbf]|\\u[0-9A-Fa-f]{4})[$]-?[0-9]'::text AS dollar_re,
           '(?:^|[^A-Za-z]|\\[nrtbf]|\\u[0-9A-Fa-f]{4})([$]-?[0-9][0-9.,]*[A-Za-z]?)'::text
               AS figure_re,
           '\\u(0000|[dD][89a-fA-F][0-9a-fA-F]{2})'::text AS json_hazard
), summary_currency AS MATERIALIZED (
    SELECT s.id AS summary_id, f.id AS filing_id, f.accession_number,
           COALESCE(s.updated_at, s.created_at, '-infinity') AS stored_at,
           s.prompt_version,
           (s.schema_version IS NULL OR s.prompt_version IS NULL
            OR s.schema_version <> p.current_schema OR s.prompt_version <> p.current_prompt) AS stale,
           NULLIF(upper(btrim(
               (CASE WHEN f.xbrl_data::text ~ p.json_hazard
                     THEN regexp_replace(f.xbrl_data::text, p.json_hazard, '\\ufffd', 'g')::json
                     ELSE f.xbrl_data END) ->> 'reporting_currency')), '') AS xbrl_currency
    FROM summaries s
    JOIN filings f ON f.id = s.filing_id
    CROSS JOIN params p
), classified AS MATERIALIZED (
    SELECT sc.summary_id, sc.filing_id, sc.stored_at, sc.prompt_version, sc.stale,
           COALESCE(sc.xbrl_currency, fact.unit) AS reporting_currency,
           sc.xbrl_currency IS NULL AND fact.unit IS NOT NULL AS currency_from_facts
    FROM summary_currency sc
    LEFT JOIN LATERAL (
        SELECT ff.unit
        FROM financial_fact ff
        WHERE sc.xbrl_currency IS NULL
          AND ff.accession = sc.accession_number
          AND ff.unit ~ '^[A-Z]{3}$'
        GROUP BY ff.unit
        ORDER BY count(*) DESC, ff.unit = 'USD', ff.unit
        LIMIT 1
    ) fact ON true
), non_usd AS MATERIALIZED (
    SELECT c.*, kind.kind,
           COALESCE(cells.current_cells ~ p.dollar_re, false) AS d_current,
           COALESCE(cells.prior_cells ~ p.dollar_re, false) AS d_prior,
           COALESCE(body.reader_text ~ p.dollar_re, false) AS d_any,
           left(COALESCE(substring(cells.current_cells FROM p.figure_re),
                         substring(cells.prior_cells FROM p.figure_re),
                         substring(body.reader_text FROM p.figure_re)), 32) AS first_dollar_figure
    FROM classified c
    CROSS JOIN params p
    CROSS JOIN LATERAL (
        -- Keyed on c, so a summary body is read only for a row that passed the non-USD filter.
        SELECT s.business_overview, s.management_discussion, s.key_changes, s.risk_factors,
               (CASE WHEN s.raw_summary::text ~ p.json_hazard
                     THEN regexp_replace(s.raw_summary::text, p.json_hazard, '\\ufffd', 'g')::json
                     ELSE s.raw_summary END) -> 'sections' AS sections,
               CASE WHEN s.financial_highlights::text ~ p.json_hazard
                    THEN regexp_replace(s.financial_highlights::text, p.json_hazard, '\\ufffd', 'g')::json
                    ELSE s.financial_highlights END AS highlights
        FROM summaries s
        WHERE s.id = c.summary_id
        OFFSET 0
    ) doc
    CROSS JOIN LATERAL (
        SELECT CASE WHEN (doc.sections -> 'the_print' -> 'headline')::text
                             LIKE '"% Filing % Partial Analysis"'
                      OR (doc.sections -> 'executive_snapshot' -> 'headline')::text
                             LIKE '"% Filing % Partial Analysis"'
                      OR strpos(doc.business_overview,
                                'Click ''Regenerate Analysis'' for the full AI-powered insights') > 0
                    THEN 'fallback' ELSE 'full' END AS kind
    ) kind
    CROSS JOIN LATERAL (
        SELECT string_agg(concat_ws(' | ', (e.item -> 'current_period')::text,
                                           (e.item -> 'currentPeriod')::text), ' | ') AS current_cells,
               string_agg(concat_ws(' | ', (e.item -> 'prior_period')::text,
                                           (e.item -> 'priorPeriod')::text), ' | ') AS prior_cells
        FROM (VALUES (doc.highlights -> 'table'),
                     (doc.sections -> 'results_that_matter' -> 'table'),
                     (doc.sections -> 'financial_highlights' -> 'table')) AS t(tbl)
        CROSS JOIN LATERAL json_array_elements(CASE json_typeof(t.tbl) WHEN 'array' THEN t.tbl END)
            AS e(item)
        WHERE json_typeof(e.item) = 'object'
    ) cells
    CROSS JOIN LATERAL (
        SELECT concat_ws(' | ', doc.business_overview, doc.management_discussion, doc.key_changes,
                         doc.highlights::text, doc.risk_factors::text, doc.sections::text) AS reader_text
        OFFSET 0
    ) body
    WHERE c.reporting_currency <> 'USD'
), grouped AS (
    SELECT 1 AS grp, n.reporting_currency AS currency, n.stored_at < p.fix_live_at AS before_fix,
           count(*) AS summaries,
           count(*) FILTER (WHERE n.kind = 'fallback') AS fallback,
           count(*) FILTER (WHERE n.kind = 'full') AS full_summary,
           count(*) FILTER (WHERE n.d_any) AS with_dollar_figure,
           count(*) FILTER (WHERE n.d_current OR n.d_prior) AS dollar_in_cells,
           count(*) FILTER (WHERE n.currency_from_facts) AS currency_from_facts,
           count(*) FILTER (WHERE n.stored_at >= p.merged_at AND n.stored_at < p.fix_live_at)
               AS written_merge_to_deploy
    FROM non_usd n CROSS JOIN params p
    GROUP BY n.reporting_currency, n.stored_at < p.fix_live_at
    UNION ALL
    SELECT 2, COALESCE(c.reporting_currency, 'none recorded'), c.stored_at < p.fix_live_at,
           count(*), NULL::bigint, NULL::bigint, NULL::bigint, NULL::bigint, NULL::bigint,
           count(*) FILTER (WHERE c.stored_at >= p.merged_at AND c.stored_at < p.fix_live_at)
    FROM classified c CROSS JOIN params p
    WHERE c.reporting_currency IS NULL OR c.reporting_currency = 'USD'
    GROUP BY 2, 3
)
SELECT CASE WHEN grp = 2 THEN currency || ' (context)' ELSE currency END AS reporting_currency,
       CASE WHEN before_fix THEN 'before fix' ELSE 'after fix' END AS stored,
       summaries, fallback, full_summary, with_dollar_figure, dollar_in_cells, currency_from_facts,
       written_merge_to_deploy
FROM grouped
ORDER BY grp, currency, before_fix DESC;
\echo '   The fix''s control is dollar_in_cells, not with_dollar_figure: current writers still copy'
\echo '   filing text (risk factors, MD&A, quoted evidence) that can carry a filer''s own "$".'

\echo '2. Non-USD summaries stored before the fix, by kind: how many carry a "$" figure, and where.'
\echo '   A stale row (a missing or old stamp, refresh-stale''s default filter) is one refresh-stale'
\echo '   already regenerates without a bump; a current-stamped row is reached only by a version bump'
\echo '   or a per-filing regeneration.'
WITH params AS (
    SELECT timestamptz '2026-10-18 10:34:00+00' AS merged_at,
           timestamptz '2026-10-18 10:51:13+00' AS fix_live_at,
           2 AS current_schema,
           'summary-2026-09-u'::text AS current_prompt,
           '(^|[^A-Za-z]|\\[nrtbf]|\\u[0-9A-Fa-f]{4})[$]-?[0-9]'::text AS dollar_re,
           '(?:^|[^A-Za-z]|\\[nrtbf]|\\u[0-9A-Fa-f]{4})([$]-?[0-9][0-9.,]*[A-Za-z]?)'::text
               AS figure_re,
           '\\u(0000|[dD][89a-fA-F][0-9a-fA-F]{2})'::text AS json_hazard
), summary_currency AS MATERIALIZED (
    SELECT s.id AS summary_id, f.id AS filing_id, f.accession_number,
           COALESCE(s.updated_at, s.created_at, '-infinity') AS stored_at,
           s.prompt_version,
           (s.schema_version IS NULL OR s.prompt_version IS NULL
            OR s.schema_version <> p.current_schema OR s.prompt_version <> p.current_prompt) AS stale,
           NULLIF(upper(btrim(
               (CASE WHEN f.xbrl_data::text ~ p.json_hazard
                     THEN regexp_replace(f.xbrl_data::text, p.json_hazard, '\\ufffd', 'g')::json
                     ELSE f.xbrl_data END) ->> 'reporting_currency')), '') AS xbrl_currency
    FROM summaries s
    JOIN filings f ON f.id = s.filing_id
    CROSS JOIN params p
), classified AS MATERIALIZED (
    SELECT sc.summary_id, sc.filing_id, sc.stored_at, sc.prompt_version, sc.stale,
           COALESCE(sc.xbrl_currency, fact.unit) AS reporting_currency,
           sc.xbrl_currency IS NULL AND fact.unit IS NOT NULL AS currency_from_facts
    FROM summary_currency sc
    LEFT JOIN LATERAL (
        SELECT ff.unit
        FROM financial_fact ff
        WHERE sc.xbrl_currency IS NULL
          AND ff.accession = sc.accession_number
          AND ff.unit ~ '^[A-Z]{3}$'
        GROUP BY ff.unit
        ORDER BY count(*) DESC, ff.unit = 'USD', ff.unit
        LIMIT 1
    ) fact ON true
), non_usd AS MATERIALIZED (
    SELECT c.*, kind.kind,
           COALESCE(cells.current_cells ~ p.dollar_re, false) AS d_current,
           COALESCE(cells.prior_cells ~ p.dollar_re, false) AS d_prior,
           COALESCE(body.reader_text ~ p.dollar_re, false) AS d_any,
           left(COALESCE(substring(cells.current_cells FROM p.figure_re),
                         substring(cells.prior_cells FROM p.figure_re),
                         substring(body.reader_text FROM p.figure_re)), 32) AS first_dollar_figure
    FROM classified c
    CROSS JOIN params p
    CROSS JOIN LATERAL (
        -- Keyed on c, so a summary body is read only for a row that passed the non-USD filter.
        SELECT s.business_overview, s.management_discussion, s.key_changes, s.risk_factors,
               (CASE WHEN s.raw_summary::text ~ p.json_hazard
                     THEN regexp_replace(s.raw_summary::text, p.json_hazard, '\\ufffd', 'g')::json
                     ELSE s.raw_summary END) -> 'sections' AS sections,
               CASE WHEN s.financial_highlights::text ~ p.json_hazard
                    THEN regexp_replace(s.financial_highlights::text, p.json_hazard, '\\ufffd', 'g')::json
                    ELSE s.financial_highlights END AS highlights
        FROM summaries s
        WHERE s.id = c.summary_id
        OFFSET 0
    ) doc
    CROSS JOIN LATERAL (
        SELECT CASE WHEN (doc.sections -> 'the_print' -> 'headline')::text
                             LIKE '"% Filing % Partial Analysis"'
                      OR (doc.sections -> 'executive_snapshot' -> 'headline')::text
                             LIKE '"% Filing % Partial Analysis"'
                      OR strpos(doc.business_overview,
                                'Click ''Regenerate Analysis'' for the full AI-powered insights') > 0
                    THEN 'fallback' ELSE 'full' END AS kind
    ) kind
    CROSS JOIN LATERAL (
        SELECT string_agg(concat_ws(' | ', (e.item -> 'current_period')::text,
                                           (e.item -> 'currentPeriod')::text), ' | ') AS current_cells,
               string_agg(concat_ws(' | ', (e.item -> 'prior_period')::text,
                                           (e.item -> 'priorPeriod')::text), ' | ') AS prior_cells
        FROM (VALUES (doc.highlights -> 'table'),
                     (doc.sections -> 'results_that_matter' -> 'table'),
                     (doc.sections -> 'financial_highlights' -> 'table')) AS t(tbl)
        CROSS JOIN LATERAL json_array_elements(CASE json_typeof(t.tbl) WHEN 'array' THEN t.tbl END)
            AS e(item)
        WHERE json_typeof(e.item) = 'object'
    ) cells
    CROSS JOIN LATERAL (
        SELECT concat_ws(' | ', doc.business_overview, doc.management_discussion, doc.key_changes,
                         doc.highlights::text, doc.risk_factors::text, doc.sections::text) AS reader_text
        OFFSET 0
    ) body
    WHERE c.reporting_currency <> 'USD'
), before_fix AS (
    SELECT n.* FROM non_usd n CROSS JOIN params p WHERE n.stored_at < p.fix_live_at
)
SELECT k.kind,
       count(n.summary_id) AS summaries,
       count(*) FILTER (WHERE n.d_any) AS with_dollar_figure,
       count(*) FILTER (WHERE n.d_current) AS in_current_cells,
       count(*) FILTER (WHERE n.d_prior) AS in_prior_cells,
       count(*) FILTER (WHERE n.d_any AND NOT (n.d_current OR n.d_prior)) AS outside_cells_only,
       count(*) FILTER (WHERE (n.d_current OR n.d_prior) AND n.stale) AS cell_hits_already_stale,
       count(*) FILTER (WHERE (n.d_current OR n.d_prior) AND NOT n.stale) AS cell_hits_current_stamp
FROM (VALUES (1, 'fallback'), (2, 'full'), (3, 'all non-USD')) AS k(ord, kind)
LEFT JOIN before_fix n ON k.kind IN (n.kind, 'all non-USD')
GROUP BY k.ord, k.kind
ORDER BY k.ord;

\echo '3. Affected filings (non-USD, stored before the fix, a "$" figure), at most 50: cell hits'
\echo '   first, then newest first.'
WITH params AS (
    SELECT timestamptz '2026-10-18 10:34:00+00' AS merged_at,
           timestamptz '2026-10-18 10:51:13+00' AS fix_live_at,
           2 AS current_schema,
           'summary-2026-09-u'::text AS current_prompt,
           '(^|[^A-Za-z]|\\[nrtbf]|\\u[0-9A-Fa-f]{4})[$]-?[0-9]'::text AS dollar_re,
           '(?:^|[^A-Za-z]|\\[nrtbf]|\\u[0-9A-Fa-f]{4})([$]-?[0-9][0-9.,]*[A-Za-z]?)'::text
               AS figure_re,
           '\\u(0000|[dD][89a-fA-F][0-9a-fA-F]{2})'::text AS json_hazard
), summary_currency AS MATERIALIZED (
    SELECT s.id AS summary_id, f.id AS filing_id, f.accession_number,
           COALESCE(s.updated_at, s.created_at, '-infinity') AS stored_at,
           s.prompt_version,
           (s.schema_version IS NULL OR s.prompt_version IS NULL
            OR s.schema_version <> p.current_schema OR s.prompt_version <> p.current_prompt) AS stale,
           NULLIF(upper(btrim(
               (CASE WHEN f.xbrl_data::text ~ p.json_hazard
                     THEN regexp_replace(f.xbrl_data::text, p.json_hazard, '\\ufffd', 'g')::json
                     ELSE f.xbrl_data END) ->> 'reporting_currency')), '') AS xbrl_currency
    FROM summaries s
    JOIN filings f ON f.id = s.filing_id
    CROSS JOIN params p
), classified AS MATERIALIZED (
    SELECT sc.summary_id, sc.filing_id, sc.stored_at, sc.prompt_version, sc.stale,
           COALESCE(sc.xbrl_currency, fact.unit) AS reporting_currency,
           sc.xbrl_currency IS NULL AND fact.unit IS NOT NULL AS currency_from_facts
    FROM summary_currency sc
    LEFT JOIN LATERAL (
        SELECT ff.unit
        FROM financial_fact ff
        WHERE sc.xbrl_currency IS NULL
          AND ff.accession = sc.accession_number
          AND ff.unit ~ '^[A-Z]{3}$'
        GROUP BY ff.unit
        ORDER BY count(*) DESC, ff.unit = 'USD', ff.unit
        LIMIT 1
    ) fact ON true
), non_usd AS MATERIALIZED (
    SELECT c.*, kind.kind,
           COALESCE(cells.current_cells ~ p.dollar_re, false) AS d_current,
           COALESCE(cells.prior_cells ~ p.dollar_re, false) AS d_prior,
           COALESCE(body.reader_text ~ p.dollar_re, false) AS d_any,
           left(COALESCE(substring(cells.current_cells FROM p.figure_re),
                         substring(cells.prior_cells FROM p.figure_re),
                         substring(body.reader_text FROM p.figure_re)), 32) AS first_dollar_figure
    FROM classified c
    CROSS JOIN params p
    CROSS JOIN LATERAL (
        -- Keyed on c, so a summary body is read only for a row that passed the non-USD filter.
        SELECT s.business_overview, s.management_discussion, s.key_changes, s.risk_factors,
               (CASE WHEN s.raw_summary::text ~ p.json_hazard
                     THEN regexp_replace(s.raw_summary::text, p.json_hazard, '\\ufffd', 'g')::json
                     ELSE s.raw_summary END) -> 'sections' AS sections,
               CASE WHEN s.financial_highlights::text ~ p.json_hazard
                    THEN regexp_replace(s.financial_highlights::text, p.json_hazard, '\\ufffd', 'g')::json
                    ELSE s.financial_highlights END AS highlights
        FROM summaries s
        WHERE s.id = c.summary_id
        OFFSET 0
    ) doc
    CROSS JOIN LATERAL (
        SELECT CASE WHEN (doc.sections -> 'the_print' -> 'headline')::text
                             LIKE '"% Filing % Partial Analysis"'
                      OR (doc.sections -> 'executive_snapshot' -> 'headline')::text
                             LIKE '"% Filing % Partial Analysis"'
                      OR strpos(doc.business_overview,
                                'Click ''Regenerate Analysis'' for the full AI-powered insights') > 0
                    THEN 'fallback' ELSE 'full' END AS kind
    ) kind
    CROSS JOIN LATERAL (
        SELECT string_agg(concat_ws(' | ', (e.item -> 'current_period')::text,
                                           (e.item -> 'currentPeriod')::text), ' | ') AS current_cells,
               string_agg(concat_ws(' | ', (e.item -> 'prior_period')::text,
                                           (e.item -> 'priorPeriod')::text), ' | ') AS prior_cells
        FROM (VALUES (doc.highlights -> 'table'),
                     (doc.sections -> 'results_that_matter' -> 'table'),
                     (doc.sections -> 'financial_highlights' -> 'table')) AS t(tbl)
        CROSS JOIN LATERAL json_array_elements(CASE json_typeof(t.tbl) WHEN 'array' THEN t.tbl END)
            AS e(item)
        WHERE json_typeof(e.item) = 'object'
    ) cells
    CROSS JOIN LATERAL (
        SELECT concat_ws(' | ', doc.business_overview, doc.management_discussion, doc.key_changes,
                         doc.highlights::text, doc.risk_factors::text, doc.sections::text) AS reader_text
        OFFSET 0
    ) body
    WHERE c.reporting_currency <> 'USD'
), affected AS (
    SELECT n.*
    FROM non_usd n CROSS JOIN params p
    WHERE n.stored_at < p.fix_live_at AND n.d_any
    ORDER BY (n.d_current OR n.d_prior) DESC, n.stored_at DESC, n.summary_id DESC
    LIMIT 50
)
SELECT co.ticker,
       f.filing_type AS form,
       (f.filing_date AT TIME ZONE 'UTC')::date AS filing_date,
       f.accession_number AS accession,
       a.reporting_currency,
       a.kind,
       (a.stored_at AT TIME ZONE 'UTC')::timestamp(0) AS stored_at_utc,
       a.prompt_version,
       CASE WHEN a.stale THEN 'stale' ELSE 'current' END AS stamp,
       CASE WHEN a.d_current THEN 'current cell' WHEN a.d_prior THEN 'prior cell' ELSE 'text only' END
           AS dollar_in,
       a.first_dollar_figure,
       CASE WHEN a.currency_from_facts THEN 'financial_fact' ELSE 'xbrl_data' END AS currency_from
FROM affected a
JOIN filings f ON f.id = a.filing_id
JOIN companies co ON co.id = f.company_id
ORDER BY (a.d_current OR a.d_prior) DESC, a.stored_at DESC, a.summary_id DESC;

COMMIT;
