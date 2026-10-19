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
- A label beside a heading (a tone badge, a count) wraps alone: the heading and whatever must stay
  beside it (its index) are one group that never wraps, and the row wraps only the label. A wrapping
  row of three items places each at its whole width before shrinking any, so a long heading drops
  beneath its index instead of wrapping its own words.
- Two buttons side by side in a card sit in a row of their own that wraps, each label free to wrap
  inside its button (`buttonVariants({ wrap: true })`, `max-w-full`), when the card's own action row
  does not wrap; a header's figure beside a heading (a percent) moves beneath it on a line of its
  own; a form code ("10-K") is one `whitespace-nowrap` run, so it never breaks at its hyphen.
- Prove it in Playwright on the real page at 390px with `document.documentElement.style.fontSize
  = '32px'` (or Chromium's own text size, `Page.setFontSizes`), in both themes, measuring painted
  text with a Range, at 320px with the default size, and in the narrowest desktop column the layout
  uses: assert the property the layout promises (the label wholly beneath its heading, the heading
  beside its index, nothing past its row or the viewport), not only that two boxes do not meet.

**Evidence**: founder review 5484603342 on PR #1226 (P2 on `CatchCard.tsx`, P3 on
`MarkedCopy.tsx`); `frontend/tests/e2e/catch-card-reflow.spec.ts`; `frontend/tests/unit/markedCopy.spec.tsx`;
the 125% root-font case in `frontend/tests/e2e/metrics-stacked-cards.spec.ts` for the same method.

**Recurrence (2026-10-14 and 15, the filing page, #1293)**: the founder's design review found the
new "Management tone: cautious" badge squeezing its section heading at 320px and widening the page
at 390px with 200% text. The first fix wrapped the whole row, and the principal review found that a
long heading then dropped beneath its "01" index on every section (Chromium probes at 320, 360 and
390px and at 200% text); the e2e case that stood for the fix asserted only that the badge's box did
not meet the heading's, which the squeezed and the dropped layouts both satisfied. The capture review
then found the signup gate's two buttons past both card edges, the progress card's percent printed
over its heading and "10-|K" broken at 200% text. `SummaryBlocks.tsx` groups the index and the
heading; `tests/e2e/text-floors.spec.ts` asserts the badge wholly beneath its heading, every heading
beside its index and, at 320px, no sideways scroll; `SummaryBlocks.spec.tsx`,
`GenerateSignupGate.spec.tsx` and `StreamingSummaryDisplay.spec.tsx` pin the wrapping classes.

**Recurrence (2026-10-17, the mail header, #1334)**: the mail's lockup, the tile beside a one-word wordmark, and its
tagline's mark, kept on one line, held a phone's page about 420 px wide under a WebView text zoom at 200%, and the
overflow stayed a recorded residual until Codex's review flagged it (r4302052395). A text zoom scales px sizes, which
the site's rem-based checks never move. The wordmark now wraps between its two words at a zero-width space and the
mark is an inline-block that wraps inside itself only where its words do not fit (D-048), and
`frontend/tests/e2e/mail-header-reflow.spec.ts` holds the template's header, and through the parity test the mail's, to
no painted text outside the screen at 320 and 390 px with every computed size doubled: the wordmark on the lines
"Earnings" and "Nerd", and on one line at its set size; the mark on one line where it fits, and broken between its
words alone where it does not; the tile beside the wordmark. Its first form placed the tile against the wordmark's
cell, whose box is its row's height, so a tile moved off the wordmark's line passed (round 24's review); it now
places the tile against the painted lines, measured with a Range.
