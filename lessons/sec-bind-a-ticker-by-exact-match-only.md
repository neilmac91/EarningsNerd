# Bind a requested ticker to a company by exact match only; a search's first hit is not an identity

Date: 2026-10-16   Area: sec

**Context**: `GET /api/companies/{ticker}`, `GET /api/filings/company/{ticker}` and
`precompute_service.precompute_one` resolved a ticker missing from the DB with
`sec_edgar_service.search_company(ticker)` and took result `[0]`. That search serves the typeahead:
exact ticker hits first, then any entry whose name or ticker merely contains the query. So every
ticker SEC's ticker file no longer lists (retired, renamed or mistyped) bound to an unrelated issuer
with a 200: RTN to Enterprise Products PARTNERS, SQ to SQM, FB to FB Financial (FBK), X to Exxon
(XOM). The company page served that issuer under the requested URL, the filings list fetched and
stored its filings, and precompute paid to summarize it and reported `generated`. The curated
unsupported-ADR guard in `company_coverage.py` covered only its eight tickers.

**Rule**: Bind a requested ticker (a URL, a bookmark, a job input) to a company only through
`sec_edgar_service.resolve_ticker`: exact, case-insensitive, with `.` and `-` as the same share-class
separator (BRK.B is BRK-B). Treat None as not found (404 on a route, `company_not_found` in a job).
Never take a search result by position; `search_company` is for listing candidates a person
picks from. The stored-ticker DB lookup stays exact and runs first, so a company stored while its
ticker was listed keeps serving under that ticker. Any other way of turning a ticker into a company
(a name search, a substring scan of the ticker file) needs the same exact check.

**Evidence**: `backend/app/services/edgar/compat.py` (`resolve_ticker`, `_ticker_key`);
`backend/tests/unit/test_ticker_exact_resolution.py` (the three callers 404 or report
`company_not_found` for RTN, SQ, FB and X; AAPL, aapl, BRK-B and BRK.B resolve; the typeahead keeps
partial matches). Partly gated by `backend/tests/unit/test_search_company_callers_allowlist.py`:
every `search_company` access must be on its allow-list (the typeahead and `resolve_ticker`), and
no search result may be indexed by position. A ticker bound through another fuzzy source is
review-checked.
