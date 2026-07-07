-- Detection: ticker-corruption PROXY signals (data-quality plan P0-1).
-- The authoritative check diffs companies.ticker against the primary-per-CIK from SEC's
-- company_tickers.json (repair_ticker_by_cik.py --dry-run / the P1-9 weekly report); SQL alone
-- can only spot the preferred-share suffix signature and CIK duplicates.
-- Read-only; table: companies.

-- Preferred-share-suffix tickers persisted as a company's operational ticker (expect 0 after repair).
SELECT COUNT(*) AS preferred_suffix_ticker_count
FROM companies
WHERE ticker ~ '-P[A-Z]{1,2}$';

-- The rows themselves (bounded).
SELECT id, cik, ticker, name
FROM companies
WHERE ticker ~ '-P[A-Z]{1,2}$'
ORDER BY ticker
LIMIT 50;

-- CIK duplicates: expect none (companies.cik is UNIQUE); listed defensively.
SELECT cik, COUNT(*) AS row_count
FROM companies
GROUP BY cik
HAVING COUNT(*) > 1;
