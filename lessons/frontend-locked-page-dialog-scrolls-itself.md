# A dialog that locks the page must bound itself to the viewport and scroll inside

Date: 2026-10-02   Area: frontend

**Context**: The design-v3 pack's `components/ui/Modal.tsx` locks `body` scrolling and centres a
fixed panel that has no height bound and no scroll container. A panel taller than the viewport
overflowed both edges, and with the page locked nothing could scroll it back into view. At 320×256
(a 1280-wide window at 400% zoom), ResendShareModal's ✕ was 1% visible and its Done button 31%;
RevokeConfirmModal's ✕ was 42% visible. The series ledger had recorded the gap as "pack geometry
kept, not measured at phone heights" and deferred it. A manual review on #1043 asked for the fix
in the primitive. Every keyboard pass had run at 1440×900, where every dialog fits.

**Rule**:
- (a) Whatever takes the page's scroll away gives the dialog a scroll of its own. The panel is
  bounded to the viewport (`max-h-full` inside the scrim's padding) and scrolls inside
  (`overflow-y-auto`). Callers never size its height.
- (b) The scrolling panel gets scroll padding equal to its inset (`scroll-py-6`), so a control
  scrolled in by focus lands with its ring clear of the edge. Chrome applies `scroll-padding`
  when focus scrolls a control into view.
- (c) Every dialog keyboard or visual pass includes one short viewport (320×256, the WCAG reflow
  size). Reachability defects never show at desktop heights.
- (d) A reachability gap you suspect gets measured before it goes into a ledger as deferred.

**Evidence**: PR #1043.
- **Regression spec:** `frontend/tests/e2e/modal-viewport.spec.ts` opens FeedbackWidget at 320×256
  on `/terms`, which needs no backend. On the pre-fix build the spec fails: the focused submit is
  87.5% in view. With the fix it passes.
- **Keyboard pass:** every Modal consumer was run at 320×256, 568×320, 640×220 and 1440×900. Every
  panel stays inside the viewport, the ✕ and the last action are fully in view when focused, and no
  focus ring is clipped. On the pre-fix build at 320×256, 18 reachability checks fail.
- **Residual:** browsers don't scroll a mostly-visible control when focus lands on it. The control a
  dialog focuses on open can therefore start partly below the fold: FeedbackWidget's textarea is 78%
  visible at 640×220. Its title stays in view.
