-- Detection: cash-series coverage gap (data-quality plan P0-3, SQL verbatim from the spec).
-- Companies whose latest FY total_assets year outruns their latest FY cash year by >= 2 years —
-- the ASU 2016-18 tag-migration signature (JPM stops at FY2018, BAC at FY2019, pre-fix).
-- Read-only; tables: financial_fact, companies. Expected EMPTY after the P0-3 registry fix + resync.
SELECT c.id, c.ticker,
       MAX(ff.fiscal_year) FILTER (WHERE ff.concept = 'cash_and_equivalents') AS last_cash_fy,
       MAX(ff.fiscal_year) FILTER (WHERE ff.concept = 'total_assets')         AS last_assets_fy
FROM financial_fact ff JOIN companies c ON c.id = ff.company_id
WHERE ff.is_latest AND ff.fiscal_period = 'FY'
  AND ff.concept IN ('cash_and_equivalents','total_assets')
GROUP BY c.id, c.ticker
HAVING MAX(ff.fiscal_year) FILTER (WHERE ff.concept = 'total_assets')
     - COALESCE(MAX(ff.fiscal_year) FILTER (WHERE ff.concept = 'cash_and_equivalents'), 0) >= 2
ORDER BY c.ticker;
