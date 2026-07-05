# Ask-this-Filing widget: overlap fix + discoverability (Direction B)

Branch: `claude/filing-chat-widget-discovery-nbsob1`

## Root cause (verified)
Both floating widgets are `position: fixed` to the same `bottom-5 right-5` anchor.
Feedback (`z-50`) paints over the Ask launcher (`z-40`) → collision. Same green pill,
no responsive offset, no safe-area handling.

## Decisions (from user)
1. Direction B — Ask = hero bottom-right; Feedback = secondary bottom-LEFT.
2. Feedback bottom-left is OK.
3. Both phases (overlap fix + discoverability layer).
4. Recommended discovery approach: end-of-summary CTA + starter chips, tappable
   follow-ups, one-time reduced-motion-safe coachmark + ping.
5. Free users → existing CopilotTeaser / UpgradeModal (preserve gating).

## Phase 1 — overlap fix + hierarchy
- [x] `FeedbackWidget.tsx`: moved launcher to bottom-LEFT, demoted to small tonal (not
      brand-filled), added focus-visible ring + aria-haspopup, >=44px target, safe-area insets;
      repositioned panel to bottom-left; lowered z to z-30 so the mobile Copilot sheet covers it.
- [x] `FilingWorkspace.tsx` launcher (the LIVE one): kept brand extended FAB, added
      safe-area insets + aria-haspopup/expanded; added reduced-motion-safe attention ping +
      one-time coachmark (persisted in localStorage; opening the rail by any means marks it seen).
- [x] `AskCopilotRail.tsx` standalone launcher: same safe-area insets + a11y attrs (in sync).
- [x] `app/layout.tsx`: added `viewport` export with `viewportFit: 'cover'`.

## Phase 2 — discoverability
- [x] `analytics.ts`: added `copilotEntryClicked({surface,...})`.
- [x] Extracted `copilot/starterQuestions.ts` (shared by the rail empty-state + the callout).
- [x] New `copilot/AskFilingCallout.tsx`: end-of-summary CTA card with starter chips + Ask button.
- [x] New `copilot/CopilotCoachmark.tsx`: one-time anchored coachmark (presentational).
- [x] `page-client.tsx`: general `handleAskCopilot(text, surface)`; threaded `onAsk` into
      `SummaryDisplay`; rendered callout after the summary; made Suggested Follow-Ups tappable.

## Verification (all green)
- [x] `npm run typecheck`
- [x] `npm run lint` (0 warnings)
- [x] `npm run test` — 206 passed (45 files), no regressions
- [x] `npm run build` — all 26 routes compile

## Review
Root cause was two `fixed bottom-5 right-5` launchers (Feedback z-50 over Ask z-40).
Fix splits the corners (Ask hero bottom-right, Feedback secondary bottom-left), so the overlap
is structurally impossible at every breakpoint with zero cross-component coupling. Hierarchy is
now size + weight + position: Ask is the only brand-filled extended FAB; Feedback is a smaller
tonal control. Added safe-area insets + viewport-fit=cover, a focus ring on Feedback, and ARIA
disclosure attrs. Discoverability: end-of-summary callout with starter chips, tappable
follow-ups, and a one-time reduced-motion-safe coachmark + ping. Free users open the same rail
and land on the existing teaser/UpgradeModal (gating preserved).

## Deliberately deferred (noted in PR)
- Per-section "Ask about this section" tab affordances: the live view is the simplified single
  "Key Takeaways" card (ENABLE_SECTION_TABS defaults off), so the end-of-summary callout under
  the output covers the "near the analysis output" intent with less surface area and risk.

## Deliberately deferred (noted in PR)
- Per-section "Ask about this section" tab affordances: the live view is the simplified
  single "Key Takeaways" card (ENABLE_SECTION_TABS defaults off), so the end-of-summary
  callout under the output covers the "near the analysis output" intent with less risk.
