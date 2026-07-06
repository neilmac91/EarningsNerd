# Bound discovery surfaces to a committed universe with a fail-open filter

Date: 2026-07-04   Area: arch

**Context**: The calendar listed every Alpha Vantage ticker (hundreds/day). For a new startup that widens the data-quality blast radius (the false-"reported" bug lived on the long tail) and dilutes focus. Restricting to S&P 500 ∪ Nasdaq 100 (~515 names) is tighter, brandable, and higher-signal. The format check mattered in practice: AV emits dots where FMP uses dashes.

**Rule**: For a discovery/listing surface, prefer a committed, auditable universe over a live API feed, and make the filter fail OPEN (serve unfiltered if the list is missing/short) so it can only ever hide tail names, never empty the page. Gate it behind ONE flag controlling BOTH ingest and serve so it's reversible within a refresh cycle. Before trusting the filter, verify the membership tickers match the event source's exact format against live data — a format mismatch silently HIDES a mega-cap, the inverse of the bug you're preventing.

**Evidence**: S&P 500 ∪ Nasdaq 100 (~515 names); AV emits `BRK.B` (dot) while FMP uses `BRK-B` (dash); normalize `-`→`.`; cross-check against the live AV universe surfaced 2 non-trading spin-off artifacts (FDXF/HONA) to prune.
