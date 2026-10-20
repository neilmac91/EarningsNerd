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
- A gutter or an inset beside prose set in rem doubles with the text and halves the measure. Let it
  give way below a measure through a container query in em on the copy's own width
  (`[container-type:inline-size]` with `[@container(width<13em)]:`), since `sm:` reads the viewport
  in px and never follows the text size, and read the prose a character at a time for a word broken
  mid-word, at 320 and 390px under 200% text, not only for sideways scroll.
- A title between a leading glyph and a trailing control (a dialog header's icon, title and close
  button) wraps under the glyph, never under the control: the glyph and the title are one wrapping
  group whose title takes a rem basis (`min-w-0 flex-[1_1_9rem]`, as a Notice's text column does)
  and breaks a word only when the word is wider than the group (`break-words`), and the control
  keeps its own column at the row's end. A row of the three that only shrinks leaves the title a
  sliver at 200% text, and its words paint past it.
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

**Recurrence (2026-10-18, the marked copy, #1396)**: chief design's review (6255015740) found the Risks
section's margin and its rows' rem insets leaving a marked excerpt 101px of 32px serif at 320px under 200%
text, about a third of its words broken mid-word ("primari / ly"), and 171px at 390px with five; the PR's
e2e case passed, since it read only sideways scroll. `MarkedCopy` now gives way below 13em of its own width
(`frontend/components/ui/markedCopyLayout.ts`), the marked block breaks a word longer than its measure inside
itself, and `frontend/tests/e2e/risk-evidence-rows.spec.ts` reads every marked block's words at 320, 390 and 1440px
in both themes, default and 200% text. That round also gave the block `hyphens: auto`, checked only on the
container's Chromium, which carries no hyphenation dictionary, so it changed nothing there; CI's Chromium carries
one and hyphenated ordinary words at every width ("re-sults" at 1440px), which the e2e failed on 1844574e. A
typographic rule that depends on browser data (hyphenation, fonts, locale) is checked on the browser CI runs, and
the marked block, a quote of the filing, now adds no hyphen (`hyphens: manual`). The same browser set a filing's
date joined by a no-break space ("September 27,") at 199px, where the container's set it at 194.5px, in a 197px
line, so CI broke it before its comma: a fit by a few pixels is not a fit. Below the measure the block's side
padding narrows too (`markedBlockInsetClass`), leaving 221px. CI's browser (Chrome for Testing, the version in
the e2e job's log) runs locally from its own folder through `launchOptions.executablePath`, without
`playwright install`.

**Recurrence (2026-10-20, the dialog header)**: the shared dialog header (`frontend/components/ui/Modal.tsx`,
`ModalHeader`) set its icon, title and close button in one row that only shrank, so at 390px under 200% text the
title kept 60px and its words painted past it, under the close button: "Cookie preferences" ran 26px past the
consent dialog's panel (Chrome for Testing 156). The cookie-settings work found it; #1380 had ruled the same
squeeze out of the Notice (E120). The header now wraps as the rule above says, and
`frontend/tests/e2e/reflow-200.spec.ts` holds two dialogs' headers at 390, 360 and 320px, the consent dialog and
the email verification prompt: the title beside the icon at the default size and under it at 200% text, every
painted line inside the panel and left of the close button, a word broken only when it is wider than the title.
