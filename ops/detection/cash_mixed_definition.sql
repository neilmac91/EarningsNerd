-- Detection: cash series that MIX the two cash definitions mid-window (data-quality plan P0-3,
-- P2 go/no-go input). Append-last is provably correct for the confirmed banks (their two tags
-- coincide in the overlap years), but a filer with material restricted cash that reports both
-- tags early then migrates to reporting ONLY the restricted total would step up at the boundary.
-- Flags any company whose cash_and_equivalents raw_tag changes between adjacent FY rows WITH a
-- >5% value discontinuity at the switch. A near-zero count confirms append-last is sufficient in
-- practice; a large count would justify building the parked per-series single-definition rule.
-- Read-only; tables: financial_fact, companies.
WITH fy AS (
    SELECT ff.company_id, c.ticker, ff.fiscal_year, ff.value, ff.raw_tag,
           LAG(ff.value)   OVER (PARTITION BY ff.company_id ORDER BY ff.fiscal_year) AS prev_value,
           LAG(ff.raw_tag) OVER (PARTITION BY ff.company_id ORDER BY ff.fiscal_year) AS prev_tag
    FROM financial_fact ff
    JOIN companies c ON c.id = ff.company_id
    WHERE ff.is_latest AND ff.fiscal_period = 'FY' AND ff.concept = 'cash_and_equivalents'
)
SELECT ticker, fiscal_year AS switch_year, prev_tag, raw_tag,
       round(prev_value / 1e9, 1) AS prev_b, round(value / 1e9, 1) AS curr_b
FROM fy
WHERE prev_tag IS NOT NULL
  AND raw_tag <> prev_tag
  AND prev_value > 0
  AND abs(value - prev_value) / prev_value > 0.05
ORDER BY ticker, switch_year;
