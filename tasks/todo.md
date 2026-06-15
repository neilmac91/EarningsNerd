# Targeted Section Extraction Fix — edgartools native parser (branch: claude/nice-curie-ugassy)

## Problem (root cause, confirmed by 2 agents + live verification)
`extract_critical_sections` regexes assume a line-oriented plain-text 10-K layout
(`ITEM 8. FINANCIAL STATEMENTS ... [^\n]*\n`, bound on `\nITEM 9.`). Input is raw `.htm`
normalized by `BeautifulSoup.get_text(separator='\n')`, which shreds modern inline-XBRL
headers across many one-token lines → 0 targeted chars → `_dense_window` fallback to a fixed
~260,154-char keyword slab. Quality degrades silently (tests only use idealized single-line headers).

## Fix (approved): edgartools native sections primary, regex+dense-window fallback, behind a flag
Live-verified: `filing.obj()['Item 1A'|'Item 7'|'Item 8']` yields clean sections
(AAPL 10-K: 68k / 18k / 61k chars = ~147k precise vs ~260k window — higher quality, lower cost).

## Tasks
- [x] config.py: `USE_EDGARTOOLS_SECTIONS: bool = True`
- [x] xbrl_service.py: `_extract_sections_sync` + `EdgarXBRLService.get_filing_sections` (executor + timeout, graceful None)
- [x] compat.py: `XBRLServiceCompat.get_filing_sections` passthrough
- [x] openai_service.py: `assemble_excerpt_from_sections(sections, filing_type, filing_text)` (same labels/caps + thin-financials backfill)
- [x] summary_generation_service.py: `get_or_cache_excerpt(..., sections=None)` prefers sections; batch core fetches sections in parallel
- [x] summary_pipeline.py (SSE): fetch sections in parallel, pass into excerpt builder
- [x] evals/runner.py: mirror new path in `_get_grounding`; print excerpt char count + source per filing
- [x] tests/unit/test_section_extraction_guard.py: regression guard for assembler (labels/caps/order/empty)

## Verify (approved: full bake-off + live run)
- [x] backend test suite (314 passed) + 6 new regression tests green; ruff clean
- [x] live extraction NVDA/TSLA/MSFT 10-Ks — precise sections where regex captured 0
- [x] NVDA edge case (Item 8 incorporated by reference -> 207-char stub) handled by financials backfill (80k -> 210k)
- [x] eval bake-off before/after (deepseek candidate, 8 filings)
- [x] commit + push to claude/nice-curie-ugassy

## Review
Root cause: regex extractor assumed line-oriented plain-text headers; modern inline-XBRL HTML
(after get_text(separator='\n')) shreds headers across lines -> 0 targeted chars -> ~260,154-char
dense-window fallback. Fixed by preferring edgartools' native parser, with the regex+dense-window
path kept as an automatic fallback behind USE_EDGARTOOLS_SECTIONS (default on, instant rollback).

Bake-off (8 filings, deepseek-chat comparison model), BEFORE (flag off) -> AFTER (flag on):
- excerpt source: 0/8 precise -> 7/8 edgartools (JPM bank 10-K safely falls back to regex)
- excerpt size: uniform ~260k slab -> precise 96k-170k (fewer tokens)
- mean_aggregate 0.5125 -> 0.5312; mean_coverage 0.325 -> 0.40 (+23% rel)
- numeric accuracy 0.9583 (held); numeric precision 1.0 (held)
- gate failures 0; errors 0; cost $0.0579 -> $0.0558 (cheaper)
- financial_depth 0.0 in BOTH runs — a limitation of the weak deepseek-chat comparison model's
  output (prod uses deepseek-v4-pro), constant across runs, so neutral to the extraction change.

No regression on any axis; coverage + aggregate up, cost down. Safe to ship.
