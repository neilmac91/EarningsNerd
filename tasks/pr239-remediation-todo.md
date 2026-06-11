# PR #239 Remediation — Eval gate fixes (review response)

Source: principal-engineer review of PR #239 + Gemini/Codex review threads.
Branch: `claude/magical-brahmagupta-ynfvko` (PR #239 updates in place).
Decisions (user): keep `gemini-3.1-pro-preview`; accession-specific ground truth
with invariants; fix regressions + dup-column drop here; defer full XBRL
accession-awareness rework to follow-up issue.

## Plan

- [x] 1. `client.py:_transform_filing` — build `document_url` from listing
      metadata only (`urljoin(sec_url, primary_document)`); never touch
      `filing_url` (lazy SGML download per filing). [Codex P2, Gemini urljoin]
- [x] 2. Extraction fixes — EMPIRICAL FINDING: edgartools 5.x has NO
      `Company.financials` property (AttributeError → silent fallback) and
      `to_dataframe()` puts concepts in a `concept` COLUMN, so the dataframe
      path never ran at all; prod always used the companyfacts fallback, whose
      first-concept-wins selection surfaced stale tags (AAPL `Revenues` ends
      FY2018 = the bogus 265.6B). Fixed: new `statement_parser.py` (concept
      column + dimension/abstract filtering + positional iteration for dup
      columns + FY-over-Q duration rank), `get_financials()` call, and
      companyfacts concept-recency + duration-aware dedupe.
- [x] 3. Amendment leakage — `amendments=False` for base forms, True for
      explicit "/A" fetches (False strips the suffix). TSLA now resolves to
      the real 10-K, not the 10-K/A.
- [x] 4. Rewrote `evals/build_golden_set.py` — accession-specific XBRL facts
      (undimensioned, period_end == period_of_report, duration windows
      320-390d/75-105d), hard invariants gate `verified`.
- [x] 5. Regenerated: 18/19 verified (BRK.B honestly unverified — EPS only
      tagged per share class, dimensioned). Cross-check: EPS × shares ≈ NI
      holds for every entry; AAPL rev now 416.161B (matches filing).
- [x] 6. 13 unit tests in tests/unit/test_statement_extraction.py.
- [x] 7. Backend unit+smoke suite: 194 passed.
- [ ] 8. Commit + push to PR branch.
- [x] 9. Filed issue #240 (accession-aware XBRL rework).
- [ ] 10. Reply on all 6 review threads (4 valid → fixed; 2 model-ID → reasoned
      rejection) and resolve them.

## Review

(to fill at completion)
