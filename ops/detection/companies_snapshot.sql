-- Detection: before/after snapshot of the plan's named multi-ticker issuers (data-quality plan P0-1).
-- JPM 19617, BAC 70858, Alphabet 1652044, Berkshire 1067983, WFC 72971, C 831001, GS 886982,
-- MS 895421. CIKs matched with leading zeros stripped (write paths store zero-padded 10-digit).
-- Read-only; table: companies.
SELECT id, cik, ticker, name, exchange, sic
FROM companies
WHERE ltrim(cik, '0') IN ('19617','70858','1652044','1067983','72971','831001','886982','895421')
ORDER BY ltrim(cik, '0')::bigint;
