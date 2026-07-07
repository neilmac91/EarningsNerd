-- Detection: tier=partial quality verdicts bucketed by reason string and SIC prefix
-- (data-quality plan P0-2). A bank-heavy (SIC 60-67) spike after any prompt change is the
-- recurrence signal for the bank-blind-grounding incident class. sic is NULL in prod today,
-- so buckets read 'null' until a SIC backfill runs — reason counts are the live signal.
-- Read-only; tables: summaries, filings, companies.
SELECT COALESCE(LEFT(c.sic, 2), 'null') AS sic_prefix,
       r.reason,
       COUNT(*) AS n
FROM summaries s
JOIN filings f ON f.id = s.filing_id
JOIN companies c ON c.id = f.company_id
CROSS JOIN LATERAL jsonb_array_elements_text(
    COALESCE((s.raw_summary::jsonb)->'quality'->'reasons', '[]'::jsonb)
) AS r(reason)
WHERE (s.raw_summary::jsonb)->'quality'->>'tier' = 'partial'
GROUP BY 1, 2
ORDER BY n DESC, sic_prefix;
