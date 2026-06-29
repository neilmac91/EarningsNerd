# Task: In-app source highlight for figures + risks (roadmap item 1.4)

## Context
1.4's vision was "click any figure → exact source line highlights." A grounded recon (+ direct
code read of `provenance_service.build_metric_source`) found the approved "verified-snippet for
metrics" approach isn't safe: metrics carry **no verified verbatim excerpt** (verification runs
against the display string, not the filing text), and a bare number is non-unique across a 10-K —
so an exact figure-line highlight would risk flashing the WRONG line, which breaks the
verify-it-yourself promise. Risk factors, by contrast, already carry a filing-verified verbatim
excerpt (`supporting_evidence`) + the proven `requestHighlight` → `FilingViewer` pipeline.

Decision (user-approved, option "Both"): ship the robust pieces.

## Decision
- One shared mechanism in `SourceTrace`: when a `FilingViewerProvider` is mounted and there's a
  highlight target, the chip becomes an in-app "jump to source" (`requestHighlight`) instead of an
  external EDGAR link; the EDGAR link stays as the popover fallback. Outside a provider (compare
  page, FREE teaser, existing unit tests) `useFilingViewer()` is null → exact current behavior.
- Target = `excerpt || sectionRef`:
  - **Risk factors** pass `excerpt={supporting_evidence}` (verified verbatim) → anchors the exact
    line precisely.
  - **Figures/metrics** have no excerpt → fall back to the section heading (`source_section_ref`),
    a best-effort section jump that degrades honestly ("Couldn't pinpoint the exact passage —
    showing the full filing") rather than ever flashing a wrong line.
- Frontend-only: reuses provenance the API already serves; no backend change, no eval concern.

## Plan
- [x] `SourceTrace`: optional `excerpt` + `useFilingViewer()`; `canHighlight` → button →
      `requestHighlight({excerpt|heading, section_ref, verified, fragment_url})`; EDGAR fallback kept
- [x] `MetricSourceLink`: thread `sectionRef` through to `SourceTrace`
- [x] `SummaryRisks`: pass `excerpt={risk.supporting_evidence}`
- [x] `FinancialMetricsTable` + `SummaryFinancials`: pass `sectionRef={…source_section_ref}`
- [x] New Vitest: in-app highlight of the excerpt (risk) + section heading (metric); external-link
      fallback with no provider
- [x] Verify frontend locally: vitest (50 files / 224 tests) + typecheck + lint (max-warnings 0) — green
- [ ] Commit + push + open draft PR

## Notes
- Exact figure-line highlight was deliberately NOT built (fragile/wrong-line risk). The figure path
  is a best-effort section jump; precise figure→line would need a verified metric-excerpt the
  backend doesn't produce today.
- On touch, a highlightable chip jumps in-app on tap (the EDGAR sheet isn't surfaced there) — the
  in-app viewer is the better action when the workspace is open.

## Review
- Robust by construction: only highlights what's anchorable (verified risk excerpt), and degrades
  to the honest "showing the full filing" banner otherwise — never a confidently-wrong line.
- Backward-compatible: outside a `FilingViewerProvider`, `SourceTrace` is byte-for-byte its old
  self (the existing risk/metric trace-to-source specs pass unchanged).
