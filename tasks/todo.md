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
- [ ] config.py: `USE_EDGARTOOLS_SECTIONS: bool = True`
- [ ] xbrl_service.py: `_extract_sections_sync` + `EdgarXBRLService.get_filing_sections` (executor + timeout, graceful None)
- [ ] compat.py: `XBRLServiceCompat.get_filing_sections` passthrough
- [ ] openai_service.py: `assemble_excerpt_from_sections(sections, filing_type)` (same labels/caps as regex path)
- [ ] summary_generation_service.py: `get_or_cache_excerpt(..., sections=None)` prefers sections; batch core fetches sections in parallel
- [ ] summary_pipeline.py (SSE): fetch sections in parallel, pass into excerpt builder
- [ ] evals/runner.py: mirror new path in `_get_grounding`; surface excerpt char count in report
- [ ] tests/unit/test_section_extraction_guard.py: regression guard for assembler + sections-preferred path

## Verify (approved: full bake-off + live run)
- [ ] backend test suite + new regression tests green
- [ ] live single-filing extraction across NVDA/TSLA/MSFT/etc — confirm `thin targeted (0 chars)` gone
- [ ] eval bake-off before/after: coverage/financial_depth equal-or-better, excerpt token count down
- [ ] commit + push to claude/nice-curie-ugassy

## Review
(to be filled in after implementation)
