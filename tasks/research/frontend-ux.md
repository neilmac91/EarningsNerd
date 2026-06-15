# Frontend Report Render + Post-Generation UX (evidence)

Read-only review of `/frontend`. Citations are file:line. Feeds Phase 5 Track 2 (post-generation UX).

## 1. Filing summary page & API shape
- Primary page: `frontend/app/filing/[id]/page-client.tsx` (render logic ~242–611, actions ~1010–1226).
- API response type: `frontend/features/summaries/api/summaries-api.ts:22-49`. Consumes:
  `business_overview` (markdown), `raw_summary.sections[]`, `financial_highlights`, `risk_factors[]`,
  `management_discussion_insights`, `guidance_outlook`, `liquidity_capital_structure`,
  `three_year_trend`, `segment_performance`, plus `status`/`message`.

## 2. Primary visible body
- Default render = the **`business_overview` markdown** (single body), with placeholder stripping
  applied (`page-client.tsx:1010` → `stripInternalNotices`).
- Structured **tabbed** view (`SummarySections.tsx:105-352`, tabs: Exec/Financials/Risks/MD&A/
  Guidance/Liquidity/Trends) is gated behind `ENABLE_SECTION_TABS` (**default false**), so most users
  see the prose body, not the structured sections.
- Empty tabs auto-hidden (`SummarySections.tsx:176`); Executive Summary always shown
  (`:166`) with a "not included" disclosure for missing sections (`:206-220`).

## 3. Source verifiability / citations  ← KEY GAP
- Evidence **is** rendered, but only for risks: `SummaryRisks.tsx:23-26` shows `supporting_evidence`
  in a labeled "Evidence" box. Compare page also shows it (`app/compare/result/page.tsx:498-506`).
- **No click-through links** to the SEC filing or specific Item/section anywhere. Evidence is plain text.
- Evidence keys recognised: excerpt/text/quote/source/reference/tag/xbrl_tag/citation
  (`lib/formatters.ts:3`). `source_section_ref` from the backend is **not surfaced as a link**.
- Financial highlights & MD&A insights carry **no** evidence callouts (citations only on risks).

## 4. Post-generation interactivity
- Save / bookmark: ✓ (`page-client.tsx:340-348, 1123-1142`).
- Export PDF / CSV: ✓ **Pro-gated** (`:1044-1114`, gate `:1147`).
- Peer / filing-over-filing **compare**: ✓ separate tool (`app/compare/page.tsx`,
  `app/compare/result/page.tsx:283-512` — multi-metric trend charts, delta highlights, risk tables).
- Dashboard **watchlist**: ✓ (`app/dashboard/watchlist/page.tsx:74-277`) — tracked cos, freshness.
- **Follow-up Q&A / chat on the filing: ✗ NOT implemented anywhere.**

## 5. Partial / fallback handling
- Quality badge (gated by `ENABLE_QUALITY_BADGE`): "Full" vs "Partial — {reason}"
  (`page-client.tsx:1181-1194`); regenerate button on writer fallback (`:1197`).
- `lib/stripInternalNotices.ts` removes leaked internal notices ("auto-generated from structured
  data", "writer output failed validation", etc.) — i.e. the frontend **papers over** the backend
  boilerplate/fallback markers rather than the backend not emitting them.
- `lib/QualityGate.ts` + `status`/`message` drive partial/writerError/writerFallback states.

## 6. Financial charts
- `FinancialCharts` gated by `ENABLE_FINANCIAL_CHARTS` (`lib/featureFlags.ts:24`, **default false**),
  wrapped in `ChartErrorBoundary` (`page-client.tsx:1222-1226`). `FinancialMetricsTable` always shown
  (`:1215-1220`).

## 7. Presentation strategy
- **Uniform sections/tabs, not highest-signal-up-top.** All sections equally weighted; no "top 3
  insights above the fold." No inline "vs prior period" callouts on the main page (compare is separate).

## Post-generation UX gaps (prosumer expectations that are missing)
1. **No click-to-source** — evidence is bare text; cannot jump to the Item 1A / MD&A passage.
2. **No follow-up Q&A** on the filing (Fiscal.ai/Quartr/Bloomberg all have it).
3. **No insight prioritization** — boilerplate-uniform sections instead of surfacing the few highest-signal findings.
4. **Citations only on risks** — financials/MD&A lack evidence callouts.
5. **Charts + structured tabs default OFF** — the richer views are flag-gated, so the default experience is the (often boilerplate) prose body.
6. Internal fallback notices are **hidden by the frontend** rather than fixed at the source — masks quality problems instead of solving them.
