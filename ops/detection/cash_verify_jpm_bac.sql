-- Verification (data-quality plan P0-3): the cash_and_equivalents FY series for JPM and BAC
-- after the resync. Expected — JPM: FY2016-18 on the legacy tag (391.2/431.3/278.8, unchanged),
-- FY2019-25 on the restricted-cash tag (263.6/527.6/740.8/567.2/624.2/469.3/343.3); BAC:
-- FY2020-25 filled (380.5/348.2/230.2/333.1/290.1/231.8). raw_tag shows which tag won each year.
-- Read-only; tables: financial_fact, companies.
SELECT c.ticker,
       ff.fiscal_year,
       round(ff.value / 1e9, 1) AS cash_usd_b,
       ff.raw_tag
FROM financial_fact ff
JOIN companies c ON c.id = ff.company_id
WHERE ff.is_latest
  AND ff.fiscal_period = 'FY'
  AND ff.concept = 'cash_and_equivalents'
  AND ltrim(c.cik, '0') IN ('19617', '70858')
ORDER BY c.ticker, ff.fiscal_year;
