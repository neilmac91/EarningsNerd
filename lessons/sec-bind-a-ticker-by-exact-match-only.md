# Bind a requested ticker to a company by exact match only; a search's first hit is not an identity

Date: 2026-10-16   Area: sec

**Context**: `GET /api/companies/{ticker}`, `GET /api/filings/company/{ticker}` and
`precompute_service.precompute_one` resolved a ticker missing from the DB with
`sec_edgar_service.search_company(ticker)` and took result `[0]`. That search serves the typeahead:
exact ticker hits first, then any entry whose name or ticker merely contains the query. So a ticker
SEC's ticker file no longer lists (retired, renamed or mistyped) bound to an unrelated issuer with a
200 whenever it is a substring of another entry's name or ticker, which nearly every short ticker
is. Which issuer it reached follows the order of SEC's file, which changes, so these pairs only
illustrate: in the test fixture's order RTN bound to Enterprise Products PARTNERS, SQ to SQM, FB to
FB Financial (FBK) and X to Exxon (XOM), while main against SEC's file when #1356 was reviewed gave
RTN to RTNTF, SQ to BMY, FB to FBIN and X to XOM. The company page served that issuer under the requested URL, the filings list fetched and stored its
filings, and precompute paid to summarize it and reported `generated`. The curated unsupported-ADR
guard in `company_coverage.py` covered only its eight tickers.

**Rule**: Bind a requested ticker (a URL, a bookmark, a job input) to a company only through
`sec_edgar_service.resolve_ticker`: exact and case-insensitive, nothing more, so the fix only
narrows what resolves. Do not map another spelling onto SEC's in this lookup alone: SEC's file
spells a share class BRK-B, and serving BRK.B here would give a page whose ticker-keyed calls
(peers, insider, watchlist) still 404 on BRK.B, a half-working duplicate of the canonical one;
spelling equivalence is a canonicalization question for every ticker-keyed route at once. Treat None
as not found (404 on a route, `company_not_found` in a job). Never take a search result by position;
`search_company` is for listing candidates a person picks from. The stored-ticker DB lookup stays
exact and runs first, so a company stored while its ticker was listed keeps serving under that
ticker. Any other way of turning a ticker into a company (a name search, a substring scan of the
ticker file) needs the same exact check.

**Evidence**: `backend/app/services/edgar/compat.py` (`resolve_ticker`);
`backend/tests/unit/test_ticker_exact_resolution.py` (the three callers 404 or report
`company_not_found` for RTN, SQ, FB and X; AAPL, aapl, BRK-B and brk-b resolve; BRK.B stays not
found, as before the fix; the typeahead keeps partial matches). Partly gated by
`backend/tests/unit/test_search_company_callers_allowlist.py`: every access to `search_company` (the
typeahead and `resolve_ticker`) and to the ranking it wraps, `_local_search` (`search_company`
only), must be on its allow-list, and a heuristic check fails on a search result used by position
(an index, destructuring, `next(iter(...))`). A ticker bound through another fuzzy source, or by a
spelling the heuristic misses, is review-checked.
