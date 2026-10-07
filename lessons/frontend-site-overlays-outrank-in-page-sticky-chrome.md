# A fixed site-level overlay ranks above in-page sticky chrome, and the ladder gate scans sticky sites too

Date: 2026-10-06   Area: frontend

**Context**: EN-02 moved the cookie-consent bar from `z-50` (over the Ask launcher, the coachmark
and the mobile sheet's composer) to a new consent layer. The first cut put it at 20, "below the
z-30 scrims so a modal sheet dims it". In Chromium at 320x568 the bar then lost "Accept All" to the
summary's section nav: that nav is `sticky top-16 z-sticky` (30) and, before the page has scrolled,
sits at its static position in the flow — which on a short phone is exactly the bar's region — and
a sticky element with a higher z paints over a fixed one. Nothing in jsdom shows it; the ladder gate
only scanned `fixed` class lists, so it passed; the Playwright hit test (`elementFromPoint` at the
choice's centre) was what caught it.

**Rule**:

(a) A fixed, site-level overlay that must stay operable (consent bar, banner) ranks ABOVE every
in-page z the page's own content can use: in-page sticky chrome (`z-sticky`), DataTable's internal
sticky cells, search dropdowns. Below it only the page's static content; above it the workspace
layers and the transient layers (overlay, modal, toast). Equal z is DOM order and proves nothing.

(b) When a layer's rank is lowered, scan what can paint over it: every `fixed` AND every `sticky`
class list with a z token, and inline `position` styles. The rule-12 gate must read both — a sticky
site at or above the layer fails unless it is pinned as top-anchored chrome (site header, page header).

(c) Prove non-occlusion with a hit test at each control's centre in a real browser at the shortest
supported viewport (320x568) with the page unscrolled; a z-index comparison is not evidence.

**Evidence**: `frontend/tailwind.config.js` (`consent: '32'`, between `sticky` 30 and the `scrim` 35 /
z-40 workspace sheets); `frontend/tests/unit/bottomChromeLadder.spec.ts` ("no in-page sticky chrome ranks
at or above z-consent", pins `Header` z-50 and `SecondaryHeader` z-40; a scratch-copy probe `z-sticky` →
`z-40` on `SummaryBlocks.tsx` fails it — the repository's one mutation demonstration is the bar's
`z-consent` → `z-50`); `frontend/tests/e2e/consent-bar-yields.spec.ts` "narrow and short
viewports › 320x568" (the choices hit themselves beside the unscrolled nav); DESIGN_SYSTEM §4 Stacking.
