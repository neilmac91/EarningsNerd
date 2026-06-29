# Task: Activation-funnel instrumentation (roadmap item 1.8)

## Context
Roadmap item 1.8 — instrument the activation funnel for PostHog. A grounded
fan-out map (analytics infra + every funnel touchpoint + the launch-runbook §C
event contract) found the funnel is **already fully instrumented except one
event**: the click-to-source verification moment, which is item 1.8's centerpiece
(the verifiability "aha" the product is built on).

Existing events (no change): `$pageview`, `example_cta_clicked`,
`company_searched`, `quick_access_click`, `filing_viewed`, `summary_viewed`,
`copilot_entry_clicked`, `pricing_viewed`, `checkout_started`, and the
server-side `generation_*`.

## Decision
- Add ONE new event: `source_span_click`, emitted from the single shared
  `requestHighlight` handler in `FilingViewerContext` — this covers every in-app
  citation click (text `[n]` + XBRL `[F#]`) from one point.
- Reuse the existing `analytics` helper + `safeCapture` (dark-launch safe; no-ops
  until `NEXT_PUBLIC_POSTHOG_KEY` is set). No new analytics layer.
- New provider props (`filingId`/`ticker`/`filingType`) are **optional** so the
  three existing propless `FilingViewerProvider` test mounts (and the FREE-teaser
  path) keep working; the event is simply not emitted without filing context.
- Defer the no-viewer FREE-teaser `<a>` path (`action: 'open_original'`) — the
  `action` property is pre-defined so it can be added later with no schema change.

## Plan
- [x] `analytics.ts`: add typed `sourceSpanClicked` method → `safeCapture('source_span_click', {snake_case})`
- [x] `FilingViewerContext.tsx`: optional `filingId/ticker/filingType` props; emit
      (guarded on `filingId != null`) as the first statement of `requestHighlight`; update deps
- [x] `page-client.tsx`: pass `filingId/ticker/filingType` to `<FilingViewerProvider>` (line 551)
- [x] New Vitest: click a real `CitationChip` in a propped provider → asserts the
      snake_case payload (text + XBRL kinds) and that propless mounts don't emit
- [x] Verify locally: full vitest suite (48 files / 218 tests) + typecheck + lint (max-warnings 0) — all green
- [ ] Commit + push + open draft PR

## User actions (to make the funnel capture data — separate from shipping code)
- Set `NEXT_PUBLIC_POSTHOG_KEY` (+ optional `NEXT_PUBLIC_POSTHOG_HOST`) in Vercel.
- Confirm backend `POSTHOG_API_KEY` in Cloud Run (joins server `generation_*`).
- Build the PostHog funnel + a `source_span_click` activation-depth insight.

## Review
- Net change is one new funnel event, `source_span_click`, emitted from the single shared
  `requestHighlight` handler in `FilingViewerContext` — so every in-app citation click (text
  `[n]` + XBRL `[F#]`) is captured from ONE point, with no threading into `CitationChip`.
- Strictly additive: a new `analytics` method (no existing event touched) + new OPTIONAL provider
  props. The three existing propless `FilingViewerProvider` tests keep passing unchanged.
- The one risk this introduced — `FilingViewerContext` now transitively loads `analytics.ts` →
  `@sentry/nextjs` in tests that don't mock it — was verified safe by running those specs: the
  full frontend suite (48 files / 218 tests) is green, plus typecheck and lint (max-warnings 0).
- Dark-launch safe: rides the existing `safeCapture` (no-ops until `NEXT_PUBLIC_POSTHOG_KEY` is
  set in the provider); no separate key check added.
- Deliberately NOT done: the no-viewer FREE-teaser `<a>` path (`action: 'open_original'`) and the
  `SourceTrace` metric/risk provenance chips — separate components with no filing context. The
  `action` property is pre-defined so the teaser path can be added later with no schema change.
