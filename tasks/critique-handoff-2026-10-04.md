<!-- Repository copy of the implementation handoff from the 2026-10-04 Impeccable critique of
frontend/app/filing/[id]/page.tsx. The critique archive itself is .impeccable/critique/2026-10-04T16-43-55Z__frontend-app-filing-id-page-tsx.md;
the run notes are tasks/critique-run-notes-2026-10-04.md. "This package" below means the critique ZIP delivered in the
critique session (report/, evidence/, assessments/, environment/); evidence file names refer to that package, not to
repository paths. -->

# Implementation handoff — EarningsNerd filing-page critique (2026-10-04)

Status: FILLED after the founder's scope answers (recorded below). This document authorizes the accepted work only;
nothing was implemented during the critique run. Second agent: read REPORT.md and RUN_NOTES.md in this package first.

## Review baseline

- Critique report and evidence locations: `report/REPORT.md` (the chat deliverable), plugin archive copy
  `report/2026-10-04T16-43-55Z__frontend-app-filing-id-page-tsx.md` (also written to the checkout at
  `.impeccable/critique/`, untracked), structured assessments `assessments/assessment-A.json`, `assessments/assessment-B.json`,
  verification verdicts `assessments/verification.json`, screenshots and records under `evidence/` (names are quoted in the
  report), reproducible environment under `environment/` (mock backend, capture harness, job matrix, fixture).
- Critiqued commit and runtime build: `100fb7d6bdaf62590af19964d39c2ed732062210` (origin/main on 2026-10-04); production
  `next build` + `next start` with production-matching flags (see RUN_NOTES.md). Production could not be matched byte for byte.
- Plugin/engine versions: Impeccable 4.5.0 (marketplace, user scope), detector engine 0.1.11; Playwright 1.63.0, Chromium 141.
- User's selected priorities and scope (actual answers, 2026-10-04):
  - Priority: "The verify step (Recommended)" — EN-01 first (then EN-04 when filing text exists).
  - Chip intent while `has_content` is false: "Open the pane to its empty state (Recommended)" — the workspace opens on the
    Filing tab, shows "not available in-app yet" with a link to the primary document; the highlight takes over when text ships.
  - Scope: "Top 3 (EN-01, EN-02, EN-03) (Recommended)" — one PR each; EN-04, EN-05 and the deterministic cleanups deferred.
  - Established decisions the implementation may change: "Add a consent layer to the stacking ladder", "Give risk cards a
    filing-derived headline", "Point 'open original' at the document".
- Baseline drift (checked 2026-10-04 18:30 UTC): `main` has moved to `fdbbcb2` (three commits after the critiqued
  `100fb7d6`: #1085 retry/focus fix, #1086 and #1088 task ledgers). None of the files cited in Accepted work changed
  (`SourceTrace.tsx`, `FilingViewerContext.tsx`, `FilingWorkspace.tsx`, `FilingViewer.tsx`, `CitationChip.tsx`,
  `MetricSourceLink.tsx`, `page-client.tsx`, `CookieConsent.tsx`, `CopilotCoachmark.tsx`, `AskCopilotRail.tsx`,
  `FinancialMetricsTable.tsx`, `DataTable.tsx`, `tailwind.config.js`, `globals.css`), so the line references hold. Two things
  did change and bind the implementation: (1) `frontend/DESIGN_SYSTEM.md` §4 now says every Retry of a failed query is
  `<RetryButton failures={[useRetainedFailure(query, queryKey)]} focusTarget={headingRef}>` (lives in
  `hooks/useRetainedFailure.tsx`), with focus handed to `focusTarget` when the button unmounts while focused
  (`hooks/useFocusHandoff.ts`); `tests/unit/busyControlsStayFocusable.spec.ts` now gates this by wiring and by label.
  Any Retry or busy control the three PRs touch must use it, and the deferred EN-05 "focus to Retry after a failed
  generation" item should be solved with that convention, not a bespoke `focus()`. (2) Branch each PR from current
  `main`, not from the critique branch; re-run the full frontend gate there before pushing.
- Explicitly accepted changes to established design decisions:
  1. A documented consent layer in the z-index ladder (below the z-40 sheets), with a gate and DESIGN.md / DESIGN_SYSTEM §4
     updated in the same PR (EN-02).
  2. "Open original" / "Open the original on SEC.gov" target `filing.document_url` (primary .htm), `sec_url` as fallback (EN-01).
  3. Risk cards may carry a filing-derived headline instead of "Filing excerpt N" — ACCEPTED in principle but OUTSIDE the
     top-3 scope; see Deferred findings. Do not implement in these three PRs.

## Accepted work

| Finding ID | Accepted outcome | Files/components | Acceptance evidence | Dependencies |
|---|---|---|---|---|
| EN-01 (P1) Trace-to-Source chip no-op; no touch fallback; EDGAR link unreachable by keyboard; folder-index link | Any activation of a provenance chip (metrics, risks, quotes, footnotes) produces a visible result: the workspace opens on the Filing tab (`onOpenChange(true)` driven by `viewer.request` nonce or a provider `onRequestOpen`), highlights the passage when text exists, else shows the empty state whose CTA and the pane header "Open original" link to `document_url` (fallback `sec_url`). On coarse pointers the documented bottom sheet appears (SourceTrace keeps the sheet path even when `canHighlight`; the in-app jump lives inside the sheet). Keyboard users can reach "Open in SEC EDGAR" from a chip (popover in tab order or a secondary action). Chip accessible names never read "Source: Source". | `frontend/features/filings/components/SourceTrace.tsx`, `copilot/FilingViewerContext.tsx`, `copilot/FilingWorkspace.tsx`, `app/filing/[id]/page-client.tsx` (secUrl props), `copilot/FilingViewer.tsx` (empty-state CTA), `copilot/CitationChip.tsx` (same popover contract), `MetricSourceLink.tsx` (label), `features/marketing/components/TraceToSourceDemo.tsx` only if the shared panel body changes | At 1440x900 with the rail closed (scenario `pro`, no content): click "Verified in filing" under Total net sales → `[role=dialog][aria-label="Ask this Filing"]` has `aria-hidden="false"`, Filing tab selected, SEC.gov CTA visible; its href and the header "Open original" href end in `aapl-20250927.htm`. With fixture text (`pro,content`): the cited sentence is highlighted. At 390x844 touch: tapping the chip shows a visible sheet or pane containing the document link. Keyboard: from a chip, Tab reaches "Open in SEC EDGAR" and Enter opens it. `sourceSpanClicked` fires once per activation. Reproduce with `environment/capture.mjs` jobs `V-chip-closed-pane`, `V-chip-closed-pane-touch`, `V-chip-keyboard-edgar` (see `environment/jobs-verify.json`) or the baseline jobs `filing-light-desktop-pro-trace-nocontent`, `filing-light-mobile-pro-sourcetrace-sheet`. | Decide nothing further: chip intent is settled (open to empty state). Coordinate with EN-02 so an opened pane is not covered by the consent bar. Unit spec: `requestHighlight` opens the pane; focus-return spec per `lessons/frontend-dialog-opener-outlives-the-dialog.md`. |
| EN-02 (P1) Cookie consent bar (z-50) above the z-40 launcher, coachmark target and mobile sheet composer | Research chrome wins: the bar takes a documented consent layer below the sheets (or yields its height as a CSS inset that `LAUNCHER_OFFSET`, `COACHMARK_OFFSET` and the sheet bottom add while mounted); the coachmark is suppressed while the bar is visible; the z-50 "Cookie preferences saved" toast no longer shares the launcher corner. The ladder in DESIGN.md (Layout) and `frontend/DESIGN_SYSTEM.md` §4 Stacking documents the new layer; a gate (spec) asserts no fixed bottom chrome outranks the workspace layers at the launcher corner (rule 12). | `frontend/components/CookieConsent.tsx` (`:296`, `:149`), `frontend/features/filings/components/copilot/FilingWorkspace.tsx` (`:21-29`, `:56`, `:194`), `copilot/AskCopilotRail.tsx` (standalone launcher `:498`), `copilot/CopilotCoachmark.tsx`, `frontend/tailwind.config.js` (zIndex), `DESIGN.md`, `frontend/DESIGN_SYSTEM.md`, `.impeccable/design.json` if the documented ladder text it duplicates changes (parity spec) | Fresh storage, 1440x900, `/filing/3`: `document.elementFromPoint` at the launcher centre is the launcher (or a descendant) and a pointer click opens the rail (baseline job `filing-light-desktop-anon-viewport-top`, B probe `B-cookie-vs-launcher-1440`). 390x844 with the bar visible and the sheet open: the composer textarea rect is fully inside the viewport and not intersected by the bar (`B-cookie-vs-sheet-390`). Coachmark hidden while the bar shows, or shown above a visible launcher. Both themes verified on the Vercel preview (lesson: preview both themes). | None. Rule 11/12: documentation + gate in the same PR; `npm run test` includes `designSnapshotParity.spec.ts` if DESIGN.md changes. |
| EN-03 (P1) Phone-width metrics table hides the takeaway/provenance column and leaves ~400px-tall near-empty rows | Below `md` each metric renders as one stacked card (metric name + provenance chip; current vs prior with the change chip on one line; takeaway prose beneath with its "Verified in filing" chip); the DataTable remains from `md` up with its caption exposed to assistive tech in both layouts. | `frontend/features/summaries/components/FinancialMetricsTable.tsx` (`:73-159`), `frontend/components/ui/DataTable.tsx` only if a shared stacked mode is preferred, `frontend/features/summaries/components/SummaryBlocks.tsx` (GenericTable: same shape risk, optional) | 390x844 light and dark, `/filing/3`: the Total net sales value, change, takeaway text and its chip are visible in one viewport with no horizontal scrolling inside the card; no phone card is taller than its content plus padding (no blank space >64px between visible cells); ≥768px unchanged (baseline jobs `filing-light-mobile-anon`, `filing-dark-mobile-anon`, `filing-light-tablet-anon`; crop `A-crop-mobile-metrics.png` is the before state). | None. Vitest render test for both layouts (lesson: vitest for copy/rendered changes). |

## Boundaries

- Preserved behavior and design decisions: single sage accent; cards lift, never tint; serif only in `.filing-reader`; mono
  answers; justified summary paragraphs ≥640px; `ui/Modal` + documented bespoke sheets as the only dialogs (SourceTrace's sheet
  and the workspace shell are already allowlisted in `tests/unit/dialogAllowlist.spec.ts`; the list is shrink-only, so no new
  dialog kinds); busy controls stay focusable (`aria-disabled`); scoped "Source match found" wording; demo entry suppresses the
  quality badge and nudge; the search route stays hidden in production; the in-app highlight remains the primary action once
  filing text exists (the empty-state path is the interim behaviour, not a reversal).
- Deferred findings and reasons (founder scope = top 3):
  - EN-04 reader overflow (P2 today, P1 once in-app text ships): fixture-dependent; fix (`min-w-0` chain, table scroll wrapper,
    container-scoped highlight scroll) is ready to apply when filing content is populated or as a follow-up PR.
  - EN-05 keyboard focus loss on desktop rail close, focus to Retry after a failed generation, three controls on the browser
    default outline: small, independent follow-up PR; apply `lessons/frontend-dialog-opener-outlives-the-dialog.md`.
  - Risk-card headline (EN-08): accepted decision, deferred; needs a backend field (Item 1A sub-heading) or an agreed client
    rule (first clause of the excerpt), plus a neutral glyph and 14px evidence text.
  - Deterministic cleanups: light-mode ⌘K hint (1.11:1) in `FilingWorkspace.tsx:199` (align with `AskCopilotRail.tsx:503`);
    tertiary ink on bare cream at 12 sites (footer, disclaimers, "Evidence" and "ON THIS PAGE" eyebrows, company count/dates,
    "/" kbd hint); "Source: Source" names (covered by EN-01 if the label is fixed there); `/analysis?ticker=` handling and the
    missing `<main>` on `/analysis`; company rows' CTA for already-summarized filings and the 10-Q row tint; `aria-expanded`
    on year accordions; branded `app/not-found.tsx`; CopilotMessage pulse dot `motion-reduce`; the five documentation-drift items.
- Missing access/evidence that blocks a specific item: production has no in-app filing text (`has_content=false` for all 59
  sampled filings), so the EN-01 highlight branch and EN-04 can only be verified with the synthetic fixture
  (`environment/fixtures/filing-3-content.md`) or once content is populated; no real screen reader was available (keyboard
  acceptance is DOM-measured); the text-selection "Ask about this" pill was not captured.
- Proposed PR grouping and affected runtime surfaces:
  1. PR-A `feat(filing): provenance chips always reach the source` — EN-01 (filing page; shared SourceTrace also renders on
     the landing Trace-to-Source demo: verify it still renders).
  2. PR-B `fix(chrome): consent bar yields to the research chrome` — EN-02 (every route with the bar; filing page launcher,
     sheet, coachmark; docs + gate).
  3. PR-C `fix(summary): stacked metric cards below md` — EN-03 (filing page summary; PDF/CSV exports untouched).
  Serialize A then B (both touch `FilingWorkspace.tsx`); C is independent. Frontend-only; no backend deploy.

## Validation

- Targeted behavioral tests required by each change: EN-01 — unit spec that `requestHighlight` opens the workspace and selects
  the Filing tab; SourceTrace spec for the coarse-pointer sheet path with a mounted provider and for keyboard reachability of
  the EDGAR link; link-target spec (`document_url` first); analytics `sourceSpanClicked` once per activation. EN-02 — gate spec
  for the ladder (no fixed bottom chrome above the workspace layers at the launcher corner) and a coachmark-suppressed-while-
  consent-visible case; parity spec if DESIGN.md changes. EN-03 — render test for both layouts (phone list and md table) with
  the caption present in each.
- Desktop/mobile, light/dark and relevant interaction evidence: re-run the named baseline/verification jobs from
  `environment/jobs-baseline.json` and `environment/jobs-verify.json` against a rebuilt app (start the mock with
  `python3 environment/mock_api.py`, build/serve with `environment/env.sh` + `start_next.sh`, capture with
  `CHROMIUM_PATH=/opt/pw-browsers/chromium node environment/capture.mjs --jobs …`); keep before/after screenshots at 1440x900 and
  390x844 in both themes; eyeball the Vercel preview in both themes before done.
- Existing repository gates required for the actual files changed: from `frontend/`: `npm run lint && npx tsc -p tsconfig.ci.json
  && npm run test -- --run && npm run build`; `tests/unit/dialogAllowlist.spec.ts`, `busyControlsStayFocusable.spec.ts`,
  `designSystemDoneGate.spec.ts`, `designTokenParity.spec.ts`, `designSnapshotParity.spec.ts` (if DESIGN.md changes), ESLint design
  rules (`z-[N]` ban: new z steps go through `tailwind.config.js`), the legacy-colour grep in DESIGN_SYSTEM §12; Playwright e2e
  must still tolerate a dead API.
- Documentation/sidecar updates required by the implementation: DESIGN.md Layout paragraph + DESIGN_SYSTEM §4 Stacking (consent
  layer); SourceTrace.tsx doc comment and DESIGN.md "Dialogs and evidence" (behaviour now matches); `.impeccable/design.json`
  only where the sidecar duplicates the changed narrative (parity spec decides); CLAUDE.md rule 12 gate listed in the PR body.

## Completion record

- Implementation commit and draft PR: (to be filled by the implementation agent; open as drafts, one per finding)
- Validation commands/results and limitations: (to be filled)
- Independent reviewer findings and resolutions: (to be filled)
- Follow-up critique target and remaining issues: re-run `/impeccable critique frontend/app/filing/[id]/page.tsx` after the
  three PRs; remaining: EN-04, EN-05, risk headline, deterministic cleanups, documentation drift (see Deferred findings).
