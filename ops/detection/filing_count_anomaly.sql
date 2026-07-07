-- Detection: filing-count anomaly (data-quality plan P1-6 detection).
-- Companies whose financial_fact FY span shows >= 5 years of history but with <= 2 stored 10-K
-- Filing rows — the recent-window ingestion cap signature (mega-filers show ~1 stored 10-K).
-- Read-only; tables: companies, financial_fact, filings.
SELECT c.id, c.ticker,
       MIN(ff.fiscal_year) AS first_fact_fy,
       MAX(ff.fiscal_year) AS last_fact_fy,
       COUNT(DISTINCT f.id) FILTER (WHERE f.filing_type = '10-K') AS stored_10k_rows
FROM companies c
JOIN financial_fact ff ON ff.company_id = c.id AND ff.is_latest AND ff.fiscal_period = 'FY'
LEFT JOIN filings f ON f.company_id = c.id
GROUP BY c.id, c.ticker
HAVING MAX(ff.fiscal_year) - MIN(ff.fiscal_year) >= 5
   AND COUNT(DISTINCT f.id) FILTER (WHERE f.filing_type = '10-K') <= 2
ORDER BY (MAX(ff.fiscal_year) - MIN(ff.fiscal_year)) DESC, c.ticker;
