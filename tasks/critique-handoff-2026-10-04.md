<!-- Living implementation handoff from the 2026-10-04 Impeccable critique of frontend/app/filing/[id]/page.tsx (PR #1089).
Repository paths: the critique archive is .impeccable/critique/2026-10-04T16-43-55Z__frontend-app-filing-id-page-tsx.md, the
run notes are tasks/critique-run-notes-2026-10-04.md and the reproducible environment is tasks/critique-env-2026-10-04/.
Screenshot and record names quoted below (evidence/*.png, evidence/*.json, assessments/*.json, report/REPORT.md) are ARCHIVE
MEMBERS of the critique evidence package (earningsnerd-critique-2026-10-04-core.zip, delivered to the founder), not
repository files. Updated 2026-10-04 after Astra's follow-up review of head 8e09b1b (repository paths, acceptance
clarifications, tooling corrections); the archive itself is unchanged. -->

# Implementation handoff — EarningsNerd filing-page critique (2026-10-04)

Status: FILLED after the founder's scope answers (recorded below). This document authorizes the accepted work only;
nothing was implemented during the critique run. Second agent: read the critique archive (`.impeccable/critique/2026-10-04T16-43-55Z__frontend-app-filing-id-page-tsx.md`) and
`tasks/critique-run-notes-2026-10-04.md` in the repository first; the package's REPORT.md and RUN_NOTES.md are copies of them.

## Review baseline

- Critique report and evidence locations. In the repository (PR #1089): the critique archive
  `.impeccable/critique/2026-10-04T16-43-55Z__frontend-app-filing-id-page-tsx.md` (the report as persisted by the plugin), the run
  notes `tasks/critique-run-notes-2026-10-04.md`, and the reproducible environment `tasks/critique-env-2026-10-04/` (mock backend,
  capture harness, job matrices, labelled fixture with provenance, recorded detector scans; README inside). Archive members of the
  critique evidence package only (not repository files): `report/REPORT.md` (the chat deliverable; same content as the archive),
  structured assessments `assessments/assessment-A.json`, `assessments/assessment-B.json`, verification verdicts
  `assessments/verification.json`, and the screenshots and records under `evidence/` whose names are quoted in the report and below.
- Critiqued commit and runtime build: `100fb7d6bdaf62590af19964d39c2ed732062210` (origin/main on 2026-10-04); production
  `next build` + `next start` with production-matching flags (see RUN_NOTES.md). Production could not be matched byte for byte.
- Plugin/engine versions: Impeccable 4.5.0 (marketplace, user scope), detector engine 0.1.11; Playwright 1.63.0, Chromium 141.
- Deterministic scan record (added 2026-10-04 19:39 UTC, after the critique): `tasks/critique-env-2026-10-04/scans/detect-8e09b1b.json`
  with `detect-8e09b1b.meta.json`: 31 validated targets from `detect_targets.txt`, exit 2 (findings), 4 distinct warnings:
  `side-tab` at `SummaryBlock.tsx:42`, `SummaryBlocks.tsx:184`, `app/company/[ticker]/page-client.tsx:612` and `bounce-easing` at
  `globals.css:64`. These are the same four in-scope findings the archive's "Deterministic scan (B)" section classifies (one defect,
  one semantic, one false positive, one approved exception); the archive's original run, its two out-of-scope entries and its exit 1
  remain the historical record. The scanned `frontend/` tree (`ebb81d30…`) is identical at the critiqued `100fb7d6` and at `8e09b1b`.
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
| EN-01 (P1) Trace-to-Source chip no-op; no touch fallback; EDGAR link unreachable by keyboard; folder-index link | Any activation of a provenance chip (metrics, risks, quotes, footnotes) produces a visible result: the workspace opens on the Filing tab (`onOpenChange(true)` driven by `viewer.request` nonce or a provider `onRequestOpen`), highlights the passage when text exists, else shows the empty state whose CTA and the pane header "Open original" link to `document_url` (fallback `sec_url`). On coarse pointers the documented bottom sheet appears (SourceTrace keeps the sheet path even when `canHighlight`; the in-app jump lives inside the sheet). Keyboard users can reach "Open in SEC EDGAR" from a chip (popover in tab order or a secondary action). Chip accessible names never read "Source: Source". Source access is plan-independent: the chip → pane → document path behaves identically for anonymous, free and Pro users and introduces no plan gate; Ask entitlements (who may ask, the free taste, `app/services/entitlements.py` truth) are untouched, and opening the pane on the Filing tab must not grant, imply or prompt for Copilot access. | `frontend/features/filings/components/SourceTrace.tsx`, `copilot/FilingViewerContext.tsx`, `copilot/FilingWorkspace.tsx`, `app/filing/[id]/page-client.tsx` (secUrl props), `copilot/FilingViewer.tsx` (empty-state CTA), `copilot/CitationChip.tsx` (same popover contract), `MetricSourceLink.tsx` (label), `features/marketing/components/TraceToSourceDemo.tsx` only if the shared panel body changes | At 1440x900 with the rail closed (scenario `pro`, no content): click "Verified in filing" under Total net sales → `[role=dialog][aria-label="Ask this Filing"]` has `aria-hidden="false"`, Filing tab selected, SEC.gov CTA visible; its href and the header "Open original" href end in `aapl-20250927.htm`. With fixture text (`pro,content`): the cited sentence is highlighted. At 390x844 touch: tapping the chip shows a visible sheet or pane containing the document link. Keyboard: from a chip, Tab reaches "Open in SEC EDGAR" and Enter opens it. `sourceSpanClicked` fires once per activation. Repeat the closed-pane click under scenarios `anon`, `free` and `pro`: same visible result, and the Ask tab's entitlement messaging is unchanged from baseline. Reproduce with `tasks/critique-env-2026-10-04/capture.mjs` jobs `V-chip-closed-pane`, `V-chip-closed-pane-touch`, `V-chip-keyboard-edgar` (in `tasks/critique-env-2026-10-04/jobs-verify.json`) or the baseline jobs `filing-light-desktop-pro-trace-nocontent`, `filing-light-mobile-pro-sourcetrace-sheet` (`jobs-baseline.json`); the before-state captures of the same names are archive members. | Decide nothing further: chip intent is settled (open to empty state). Coordinate with EN-02 so an opened pane is not covered by the consent bar. Unit spec: `requestHighlight` opens the pane; focus-return spec per `lessons/frontend-dialog-opener-outlives-the-dialog.md`. |
| EN-02 (P1) Cookie consent bar (z-50) above the z-40 launcher, coachmark target and mobile sheet composer | Research chrome wins: the bar takes a documented consent layer below the sheets (or yields its height as a CSS inset that `LAUNCHER_OFFSET`, `COACHMARK_OFFSET` and the sheet bottom add while mounted); the coachmark is suppressed while the bar is visible; the z-50 "Cookie preferences saved" toast no longer shares the launcher corner. The ladder in DESIGN.md (Layout) and `frontend/DESIGN_SYSTEM.md` §4 Stacking documents the new layer; a gate (spec) asserts no fixed bottom chrome outranks the workspace layers at the launcher corner (rule 12). Consent choices stay usable: Accept, Decline and the preferences control remain visible, reachable and operable on every viewport and in both themes while the bar is mounted; the bar yields to the research chrome but is not hidden, clipped or auto-dismissed, and the user's choice is recorded exactly as today. | `frontend/components/CookieConsent.tsx` (`:296`, `:149`), `frontend/features/filings/components/copilot/FilingWorkspace.tsx` (`:21-29`, `:56`, `:194`), `copilot/AskCopilotRail.tsx` (standalone launcher `:498`), `copilot/CopilotCoachmark.tsx`, `frontend/tailwind.config.js` (zIndex), `DESIGN.md`, `frontend/DESIGN_SYSTEM.md`, `.impeccable/design.json` if the documented ladder text it duplicates changes (parity spec) | Fresh storage, 1440x900, `/filing/3`: `document.elementFromPoint` at the launcher centre is the launcher (or a descendant) and a pointer click opens the rail (baseline job `filing-light-desktop-anon-viewport-top`; archive record `B-cookie-vs-launcher-1440`). 390x844 with the bar visible and the sheet open: the composer textarea rect is fully inside the viewport and not intersected by the bar (archive record `B-cookie-vs-sheet-390`). With the bar visible at 1440x900 and 390x844: each consent button is fully inside the viewport, activates by pointer and by keyboard, and a choice dismisses the bar as before. Coachmark hidden while the bar shows, or shown above a visible launcher. Both themes verified on the Vercel preview (lesson: preview both themes). | None. Rule 11/12: documentation + gate in the same PR; `npm run test` includes `designSnapshotParity.spec.ts` if DESIGN.md changes. |
| EN-03 (P1) Phone-width metrics table hides the takeaway/provenance column and leaves ~400px-tall near-empty rows | Below `md` each metric renders as one stacked card (metric name + provenance chip; current vs prior with the change chip on one line; takeaway prose beneath with its "Verified in filing" chip); the DataTable remains from `md` up with its caption exposed to assistive tech in both layouts. Nothing is dropped: every metric name, current and prior value, change, takeaway, provenance chip and the caption the md table shows appears in the stacked layout for the same metrics; content stays accessible (no `aria-hidden` data, no fixed or forced card heights, no `line-clamp`/`truncate`/ellipsis on takeaway or metric text; long text wraps). | `frontend/features/summaries/components/FinancialMetricsTable.tsx` (`:73-159`), `frontend/components/ui/DataTable.tsx` only if a shared stacked mode is preferred, `frontend/features/summaries/components/SummaryBlocks.tsx` (GenericTable: same shape risk, optional) | 390x844 light and dark, `/filing/3`: the Total net sales value, change, takeaway text and its chip are visible in one viewport with no horizontal scrolling inside the card; no phone card is taller than its content plus padding (no blank space >64px between visible cells); ≥768px unchanged (baseline jobs `filing-light-mobile-anon`, `filing-dark-mobile-anon`, `filing-light-tablet-anon`; archive member `A-crop-mobile-metrics.png` is the before-state crop). The counts of metric names, values, change chips and takeaway texts rendered at 390px equal the counts at 1440px for the same summary, and no element in a card computes `text-overflow: ellipsis`, `-webkit-line-clamp` or a fixed `height`/`max-height` that clips. | None. Vitest render test for both layouts (lesson: vitest for copy/rendered changes). |

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
- Missing access/evidence that blocks a specific item: on 2026-10-04 `GET /api/filings/{id}/content` returned `has_content=false`
  for each of the 59 filing ids sampled (ids 1–40, 50, 100, 500, 1000, 5000 and others listed in the run notes). That is a dated
  observation about those ids, not a statement about every filing in production; re-check before relying on it. Until in-app text
  is present, the EN-01 highlight branch and EN-04 can only be verified with the synthetic, labelled fixture
  (`tasks/critique-env-2026-10-04/fixtures/filing-3-content.md`, provenance in `fixtures/PROVENANCE.json`) or once content is populated; no real screen reader was available (keyboard
  acceptance is DOM-measured); the text-selection "Ask about this" pill was not captured.
- Proposed PR grouping and affected runtime surfaces:
  1. PR-A `feat(filing): provenance chips always reach the source` — EN-01 (filing page; shared SourceTrace also renders on
     the landing Trace-to-Source demo: verify it still renders).
  2. PR-B `fix(chrome): consent bar yields to the research chrome` — EN-02 (every route with the bar; filing page launcher,
     sheet, coachmark; docs + gate).
  3. PR-C `fix(summary): stacked metric cards below md` — EN-03 (filing page summary; PDF/CSV exports untouched).
  Serialize A then B (both touch `FilingWorkspace.tsx`); C is independent. All three branch from current `main` (not from the
  critique branch). Frontend-only; no backend deploy.

## Validation

- Targeted behavioral tests required by each change: EN-01 — unit spec that `requestHighlight` opens the workspace and selects
  the Filing tab; SourceTrace spec for the coarse-pointer sheet path with a mounted provider and for keyboard reachability of
  the EDGAR link; link-target spec (`document_url` first); analytics `sourceSpanClicked` once per activation. EN-02 — gate spec
  for the ladder (no fixed bottom chrome above the workspace layers at the launcher corner) and a coachmark-suppressed-while-
  consent-visible case; parity spec if DESIGN.md changes. EN-03 — render test for both layouts (phone list and md table) with
  the caption present in each.
- Desktop/mobile, light/dark and relevant interaction evidence: re-run the named baseline/verification jobs from
  `tasks/critique-env-2026-10-04/jobs-baseline.json` and `jobs-verify.json` against a rebuilt app. From that directory:
  `./start_mock.sh`, then `source env.sh && (cd ../../frontend && npm ci && npm run build)`, then `./start_next.sh`, then
  `node capture.mjs --jobs jobs-verify.json` (an explicit `CHROMIUM_PATH` is honoured; otherwise `browser.mjs` uses Playwright's
  browser or the preinstalled `/opt/pw-browsers` Chromium), `./run_detect.sh` for a recorded detector scan, and `./stop_env.sh`
  (PID-file and command-line validated, process-group shutdown; no pattern kills). Keep before/after screenshots at 1440x900
  and 390x844 in both themes; eyeball the Vercel preview in both themes before done. README: `tasks/critique-env-2026-10-04/README.md`.
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
