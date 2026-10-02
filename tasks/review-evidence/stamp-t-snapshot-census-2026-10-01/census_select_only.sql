-- SQL Studio variant of census.sql: the same query as one SELECT statement, with no transaction
-- statements, for consoles that do not accept BEGIN/ROLLBACK. A lone SELECT writes nothing.
-- Classes and meaning: see README.md. The query text is byte-identical to census.sql.
WITH f AS (
    SELECT fl.id, fl.filing_type,
           CASE WHEN fl.xbrl_data IS NULL THEN NULL ELSE fl.xbrl_data::jsonb END AS x,
           EXISTS (SELECT 1 FROM summaries s WHERE s.filing_id = fl.id) AS has_summary
    FROM filings fl
), c AS (
    SELECT id, filing_type, has_summary,
      CASE
        WHEN x IS NULL OR jsonb_typeof(x) = 'null' THEN '0_no_snapshot'
        WHEN jsonb_typeof(x) <> 'object' THEN '1_unusable_not_object'
        WHEN NOT EXISTS (
            SELECT 1 FROM unnest(ARRAY['revenue','net_income','earnings_per_share','total_assets',
                                       'total_liabilities','cash_and_equivalents',
                                       'net_interest_income','noninterest_income']) AS k(key)
            WHERE jsonb_typeof(x -> k.key) = 'array' AND jsonb_array_length(x -> k.key) > 0)
          THEN '1_unusable_empty_reextracted'
        WHEN jsonb_typeof(x -> 'net_income') IS DISTINCT FROM 'array'
             AND x -> 'net_income' IS NOT NULL AND jsonb_typeof(x -> 'net_income') <> 'null'
          THEN '2_net_income_malformed'
        WHEN x -> 'net_income' IS NULL OR jsonb_typeof(x -> 'net_income') = 'null'
             OR jsonb_array_length(x -> 'net_income') = 0
          THEN '3_no_net_income'
        WHEN EXISTS (SELECT 1 FROM jsonb_array_elements(x -> 'net_income') p
                     WHERE jsonb_typeof(p) <> 'object')
          THEN '2_net_income_malformed'
        WHEN NOT EXISTS (SELECT 1 FROM jsonb_array_elements(x -> 'net_income') p
                         WHERE NOT coalesce(jsonb_typeof(p -> 'raw_tag') = 'string'
                                             AND btrim(p ->> 'raw_tag') <> '', false))
          THEN '4_tagged_scope_renders'
        WHEN EXISTS (SELECT 1 FROM jsonb_array_elements(x -> 'net_income') p
                     WHERE coalesce(jsonb_typeof(p -> 'raw_tag') = 'string'
                                    AND btrim(p ->> 'raw_tag') <> '', false))
          THEN '5_mixed_partially_tagged'
        WHEN NOT EXISTS (SELECT 1 FROM jsonb_array_elements(x -> 'net_income') p
                         WHERE NOT (p ? 'currency'))
          THEN '6_untagged_legacy_instance'
        WHEN NOT EXISTS (SELECT 1 FROM jsonb_array_elements(x -> 'net_income') p WHERE p ? 'currency')
          THEN '7_untagged_fallback_or_older'
        ELSE '8_untagged_unknown_shape'
      END AS class
    FROM f
)
SELECT class,
       count(*)                                   AS filings,
       count(*) FILTER (WHERE has_summary)        AS with_summary,
       count(*) FILTER (WHERE filing_type IN ('10-K','10-K/A')) AS k10,
       count(*) FILTER (WHERE filing_type IN ('10-Q','10-Q/A')) AS q10,
       count(*) FILTER (WHERE filing_type IN ('20-F','20-F/A','40-F','40-F/A')) AS foreign_annual,
       count(*) FILTER (WHERE filing_type NOT IN ('10-K','10-K/A','10-Q','10-Q/A',
                                                   '20-F','20-F/A','40-F','40-F/A')) AS other_forms
FROM c
GROUP BY ROLLUP (class)
ORDER BY class NULLS LAST;
