-- Detection: tier=partial quality verdicts bucketed by reason string and SIC prefix
-- (data-quality plan P0-2). A bank-heavy (SIC 60-67) spike after any prompt change is the
-- recurrence signal for the bank-blind-grounding incident class. sic is NULL in prod today,
-- so buckets read 'null' until a SIC backfill runs — reason counts are the live signal.
-- Read-only; tables: summaries, filings, companies. A raw_summary holding a NUL or a lone-surrogate
-- escape is rewritten to the escape of U+FFFD before the jsonb cast, which would reject it (as the
-- other detection files do for provenance).
WITH params AS (
    SELECT '\\u(0000|[dD][89a-fA-F][0-9a-fA-F]{2})'::text AS json_hazard
), parsed AS (
    SELECT s.filing_id,
           CASE WHEN s.raw_summary::text ~ p.json_hazard
                THEN regexp_replace(s.raw_summary::text, p.json_hazard, '\\ufffd', 'g')::jsonb
                ELSE s.raw_summary::jsonb END AS doc
    FROM summaries s
    CROSS JOIN params p
)
SELECT COALESCE(LEFT(c.sic, 2), 'null') AS sic_prefix,
       r.reason,
       COUNT(*) AS n
FROM parsed s
JOIN filings f ON f.id = s.filing_id
JOIN companies c ON c.id = f.company_id
CROSS JOIN LATERAL jsonb_array_elements_text(
    COALESCE(s.doc->'quality'->'reasons', '[]'::jsonb)
) AS r(reason)
WHERE s.doc->'quality'->>'tier' = 'partial'
GROUP BY 1, 2
ORDER BY n DESC, sic_prefix;
