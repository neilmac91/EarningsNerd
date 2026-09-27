# Live Analysis acceptance observations — 27 September 2026

Production backend during these observations was `537bf59b` (revision `00391-rgl`). Checks used the founder’s existing signed-in Chrome session, normal Analysis controls and downloads; no force refresh or payment action was used.

- AAPL FY2024–FY2025 completed with 17 source links and one numeric mismatch. A repeated cached result retained the narrative but lost the warning; PR #968 repairs that defect.
- Citation 1 moved to the matching annual Revenue source entry. External SEC filing-link navigation remains untested.
- AAPL 2026Q2–2026Q3 completed with 17 source links and two numeric mismatches. Its four-page PDF and six-sheet Excel export downloaded.
- The five-page annual and four-page quarterly PDFs were fully rendered and visually inspected. Text, metrics and sources were readable; unreconciled-value warnings were retained. No layout defect was established.
- Read-only Excel inspection found the expected numeric values/formats, explicit blanks for unavailable growth, source-warning comments, no error cells and no external workbook links. Native Excel rendering remains untested.
- Novo Nordisk (NVO) showed the explicit IFRS unsupported message. No generation was requested for this case.

The quarterly narrative describes a rounded current ratio of `1.00x` as “exactly” equal/no cushion. The workbook retains `1.003294804655586`; its stated assets/liabilities differ by $492 million. This is a retained product-quality example requiring a bounded narrative correction and evaluation, not a formal E7 verdict. The original output must not be redrawn away.

[Observation receipt](live-acceptance-extension.json), [annual workbook checks](annual-xlsx-validation.json), [quarterly artifact hashes and checks](quarterly-export-inspection.json). Raw financial exports and rasters remain in the workspace `outputs/takeover-2026-09-26/live-analysis/`; no authentication material was exported.

These observations do not establish independent financial-source truth, E7 acceptance, IFRS analysis support, free-tier/payment behavior or cohort outcomes. The later post-release cached warning check is recorded separately below.

## Post-release cached UI check

After #968’s backend cache-warning correction and #966’s frontend release, the root observer reopened both normal cached AAPL results in the existing signed-in Chrome session. At approximately 02:14 UTC, the FY2024–FY2025 result showed `Cached`, 17 source links and one numeric mismatch in the visible warning paragraph. At approximately 02:18 UTC, the 2026Q2–2026Q3 result showed `Cached`, 17 source links and two numeric mismatches in the visible warning paragraph. The [post-release receipt](post-release-cache-check.json) preserves the approximate observer times and release identities.

This post-release UI observation is separate from the earlier pre-release PDF, workbook, citation-navigation and source-warning artifact checks. The receipt writer independently verified the GitHub/Vercel release state but did not repeat the browser interaction. No new model call, force refresh, screenshot, financial-source audit or E7 verdict is claimed.
