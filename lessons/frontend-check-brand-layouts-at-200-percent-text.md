# Check a brand layout at 390px under a 200% root font, not only at the default size

Date: 2026-10-11   Area: frontend, design system

**Context**: Two parts of the brand device were laid out for the default text size. The catch
card set "$391.0B" and "$416.2B" in two equal grid tracks; at 390px under a 32px root font each
track was 106px and each value about 198px, so the amounts overlapped by 59.6px, and the same
happened in the desktop column. The margin twin was placed by subtracting half of an assumed 16px
height, while its `line-height: 1rem` grows with the root, so at 200% it sat 8px below its marker.
The founder's review of PR #1226 measured both on the production build.

**Rule**:
- Two unbreakable figures that share a line sit in a wrapping row whose items take their own
  content as basis (`flex flex-wrap` with `flex-auto` items), so they stack when the whole values
  do not fit, in any column; not in equal tracks, and not behind a viewport breakpoint. As a last
  resort a value wider than its card breaks inside (`break-words`) rather than overflowing.
- An element positioned against another (a margin twin, a badge on a line) is anchored at the
  measured midpoint of what it follows and centred with `translateY(-50%)`; never subtract an
  assumed height.
- Prove it in Playwright on the real page at 390px with `document.documentElement.style.fontSize
  = '32px'`, in both themes, measuring painted text with a Range, and in the narrowest desktop
  column the layout uses.

**Evidence**: founder review 5484603342 on PR #1226 (P2 on `CatchCard.tsx`, P3 on
`MarkedCopy.tsx`); `frontend/tests/e2e/catch-card-reflow.spec.ts`; `frontend/tests/unit/markedCopy.spec.tsx`;
the 125% root-font case in `frontend/tests/e2e/metrics-stacked-cards.spec.ts` for the same method.
