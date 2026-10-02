-- Read-only, zero-spend check of the census class-7 filing(s) that have a summary (census result:
-- exactly 1). Not run by the author. One SELECT, no transaction statements, so it pastes into Cloud
-- SQL Studio as-is; a lone SELECT writes nothing. psql users can wrap it in
-- BEGIN TRANSACTION READ ONLY; ... ROLLBACK; exactly as ../stamp-t-snapshot-census-2026-10-01/census.sql does.
--
-- Question: does the persisted Filing.xbrl_data snapshot carry the pre-#785 (fc2bf2f7) shape of
-- `_fetch_from_latest_financials`? That fallback copied the company's LATEST 10-K statement values and
-- wrote every point as exactly {period, value, form: null, accn: <this filing's accession>}. If the
-- newest net-income period is not this filing's period_end_date, the snapshot holds another filing's
-- figures under this filing's accession (a filing-only violation, independent of item B). The
-- companyfacts fallback shape (the other class-7 source) sets `form` and carries each fact's own accn.
--
-- Class-7 predicates are census.sql's (net_income a non-empty array of objects, no point with a
-- non-blank raw_tag, no point with `currency`).
WITH f AS (
    SELECT fl.id, fl.company_id, fl.accession_number, fl.filing_type, fl.filing_date, fl.period_end_date,
           fl.created_at, fl.xbrl_data::jsonb AS x
    FROM filings fl
    WHERE fl.xbrl_data IS NOT NULL
      AND EXISTS (SELECT 1 FROM summaries s WHERE s.filing_id = fl.id)
), c7 AS (
    SELECT * FROM f
    WHERE jsonb_typeof(x) = 'object'
      AND jsonb_typeof(x -> 'net_income') = 'array' AND jsonb_array_length(x -> 'net_income') > 0
      AND NOT EXISTS (SELECT 1 FROM jsonb_array_elements(x -> 'net_income') p WHERE jsonb_typeof(p) <> 'object')
      AND NOT EXISTS (SELECT 1 FROM jsonb_array_elements(x -> 'net_income') p
                      WHERE coalesce(jsonb_typeof(p -> 'raw_tag') = 'string' AND btrim(p ->> 'raw_tag') <> '', false))
      AND NOT EXISTS (SELECT 1 FROM jsonb_array_elements(x -> 'net_income') p WHERE p ? 'currency')
), pts AS (
    -- Every point of every metric list in the snapshot, with its key set.
    SELECT c7.id, m.key AS metric, p,
           (SELECT string_agg(k, ',' ORDER BY k) FROM jsonb_object_keys(p) k) AS keyset,
           (coalesce(jsonb_typeof(p -> 'form'), 'null') = 'null') AS form_null,
           (replace(p ->> 'accn', '-', '') = replace(c7.accession_number, '-', '')) AS accn_is_own
    FROM c7, jsonb_each(c7.x) m, jsonb_array_elements(m.value) p
    WHERE jsonb_typeof(m.value) = 'array' AND jsonb_typeof(p) = 'object'
), agg AS (
    SELECT id,
           count(*) FILTER (WHERE metric = 'net_income') AS ni_points,
           max(p ->> 'period') FILTER (WHERE metric = 'net_income') AS newest_ni_period,
           count(*) AS all_points,
           count(*) FILTER (WHERE keyset = 'accn,form,period,value' AND form_null AND accn_is_own)
               AS latest_financials_shaped_points,
           count(*) FILTER (WHERE NOT form_null) AS points_with_form,
           count(*) FILTER (WHERE NOT coalesce(accn_is_own, false)) AS points_with_other_or_no_accn,
           string_agg(DISTINCT keyset, ' | ') AS keysets,
           jsonb_agg(jsonb_build_object('period', p ->> 'period', 'value', p -> 'value', 'form', p -> 'form',
                                        'accn', p ->> 'accn') ORDER BY p ->> 'period' DESC)
               FILTER (WHERE metric = 'net_income') AS ni_series
    FROM pts
    GROUP BY id
)
SELECT co.ticker, c7.id AS filing_id, c7.accession_number, c7.filing_type,
       to_char(c7.period_end_date AT TIME ZONE 'UTC', 'YYYY-MM-DD') AS filing_period_end,
       to_char(c7.filing_date AT TIME ZONE 'UTC', 'YYYY-MM-DD') AS filing_date,
       c7.created_at AS filing_row_created_at,
       s.id AS summary_id, s.created_at AS summary_created_at, s.updated_at AS summary_updated_at,
       s.schema_version, s.prompt_version,
       a.ni_points, a.newest_ni_period, a.all_points, a.latest_financials_shaped_points, a.points_with_form,
       a.points_with_other_or_no_accn, a.keysets,
       (SELECT to_char(max(o.period_end_date) AT TIME ZONE 'UTC', 'YYYY-MM-DD') FROM filings o
         WHERE o.company_id = c7.company_id AND o.filing_type IN ('10-K', '10-K/A', '20-F', '20-F/A', '40-F', '40-F/A')
       ) AS latest_stored_annual_period_end,
       CASE
         WHEN a.latest_financials_shaped_points = a.all_points
              AND a.newest_ni_period IS DISTINCT FROM to_char(c7.period_end_date AT TIME ZONE 'UTC', 'YYYY-MM-DD')
           THEN 'pre_785_shape_period_mismatch: another filing''s figures under this accession'
         WHEN a.latest_financials_shaped_points = a.all_points
           THEN 'pre_785_shape_period_matches: figures plausibly this filing''s own'
         WHEN a.points_with_form = a.all_points THEN 'companyfacts_fallback_shape'
         ELSE 'other_shape: inspect ni_series'
       END AS verdict,
       a.ni_series,
       s.raw_summary::jsonb -> 'sections' -> 'value_drivers' ->> 'returns_on_capital' AS stored_returns_line
FROM c7
JOIN agg a ON a.id = c7.id
JOIN companies co ON co.id = c7.company_id
JOIN summaries s ON s.filing_id = c7.id
ORDER BY c7.id;
