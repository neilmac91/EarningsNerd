# Prefer a committed, auditable universe over a live feed for a listing surface; make the filter fail OPEN

**Area:** backend · **Date:** 2026-07-04

The calendar listed every Alpha Vantage ticker (hundreds/day). For a new startup that widens the
data-quality blast radius (the false-"reported" bug lived on the long tail) and dilutes focus.
Restricting to S&P 500 ∪ Nasdaq 100 (~515 names) is tighter, brandable, and higher-signal.

**Rule:** for a discovery/listing surface, prefer a committed, auditable universe over a live API
feed, and make the filter **fail OPEN** (serve unfiltered if the list is missing/short) so it can
only ever hide tail names, never empty the page. Gate it behind ONE flag controlling BOTH ingest and
serve so it's reversible within a refresh cycle. Before trusting the filter, verify the membership
tickers match the *event source's* exact format against live data — AV emits `BRK.B` (dot) while FMP
uses `BRK-B` (dash); a format mismatch silently HIDES a mega-cap, the inverse of the bug you're
preventing. (Here: normalize `-`→`.`, and cross-checked the 515-ticker list against the live AV
universe — which also surfaced 2 non-trading spin-off artifacts, FDXF/HONA, to prune.)
