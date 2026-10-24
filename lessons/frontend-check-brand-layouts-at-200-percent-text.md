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
  mid-word, at 320 and 390px under 200% text, not only for sideways scroll. A surface's own inset (a
  card, a frame, a dialog's sections) takes the capped step instead, `p-cap-N` = min(N × 0.25rem, N vw),
  which stops growing below a 25rem viewport (E120; gate: the ESLint rule
  `earningsnerd/surface-padding-cap`, and reflow-200's cookie dialog cards read a character at a time).
- A title between a leading glyph and a trailing control (a dialog header's icon, title and close
  button) keeps a rem basis beside them (`min-w-0 flex-[1_1_9rem]`, as a Notice's text column does).
  Where it cannot, it goes to a line of its own at the row's full width, under the glyph and the
  control or under the control alone, and the control keeps the top right, so no word of it breaks
  that the row's width holds. flex-wrap alone carries the control down after a wrapped title, so the
  row is a query container that moves the title at the row's own width (`[container-type:inline-size]`,
  then `[@container(width<14.25rem)]:order-last` and `basis-full`, E158; 11rem with no glyph, whose
  `justify-end` keeps the control alone on its line at the right, E165). A row that only shrinks
  leaves the title a sliver at 200% text, and its words paint past it.
- A bar whose blocks wrap (`flex-wrap justify-between`) puts a line's only block at its start, so a block
  that must keep its edge when it lands alone (the site header's desktop controls, whose menus open
  from their right edge) takes an auto margin toward the other side (`ml-auto`), and the block across
  from it the mirror margin (`mr-auto`), which share a one-line bar's free space as justify-between did
  (E160). A popover anchored at its trigger's edge (`right-0`) goes wherever the wrap takes the trigger,
  so open it under 200% text where the bar wraps (a desktop at 1024 to 1440px), not only at 390px.
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

**Recurrence (2026-10-21, the landing hero and /search, E81)**: the figure clause had not reached the hero
example's strip, three figures in equal thirds: at 390px under 200% text each value ran across its 81px cell into the
next. They now take their own widths in a wrapping row inside the one hairline strip, each figure's own left and top
rules its dividers, which the strip clips at a row's start and on the first row. The subhead broke "10-Ks" at 390px
and "10-Qs" at 1440px; its codes are `FormCodeText` runs now. A label and its value held in one nowrap run are as wide
as the run: "filed Oct 31, 2025" took the page to 329px at 320px. The date is now an inline-block after its label that
moves down whole and breaks after its day only where it cannot fit whole, and each middot sits in one item with the
fact before it, so where "AAPL · 10-K ·" does not fit on one line (320px) no middot stands alone; the EDGAR receipt's
middot, which began its second line at 1440px, is held to the word before it by a no-break space. A native date field
is wider than its text, since Chrome keeps blank room for a six-digit year: in the forms plugin's 1rem each /search
field was 312px under 200% text, in a 256px row at 320px. It shrinks to its row (`min-w-0`) in the Input primitive's
14px, giving up the blank room and no digit. The site scrolls smoothly (`scroll-behavior: smooth`), so a capture
scrolls with `behavior: 'instant'` or it shows the page where it was. `tests/e2e/reflow-200.spec.ts` holds the hero's
figures, codes and middots at 320, 390 and 1440px, and the strip's rules as painted at both text sizes, since they rest
on three coupled values (the list's negative margins, a figure's padding and its 1px rules) that a class check cannot
hold together. Until E131 it held every route at 320px, /security but for its headings' words that E131 owned: those runs were allowed by name, the page no wider than the widest of them, and the page had to still show
one, never each run, since one passed the edge by 5px there and a few pixels are one machine's measure
(`lessons/test-layout-numbers-are-one-environments-run.md`). /privacy was pinned too, from the agents' sandbox, which
paints the body text in an installed static Inter; in the site's own Inter, as CI's runner paints it, the page fits at
320px, and CI failed the pin, as the expiry is meant to (#1462).

**Recurrence (2026-10-21 and 22, the legal pages, E131)**: a legal page's column at 320px under 200% text was 256px,
its 1rem gutters doubled, and its 48px headings hold words wider than that, one wider than the screen:
"Indemnification" is 330px, so /terms reached 362px, and /security 348px on "Authentication" and "Infrastructure".
Under D-055 each legal page's `<main>` at first took only the last resort the first rule names,
`[overflow-wrap:anywhere]`, which every heading, paragraph and address inherits. It broke every word wider than the column, not only those that
passed the screen: at 320px the page title "Security" ("Securit" over "y") and words that sat a pixel or so into the
gutter ("Responsible", /privacy's "Introduction"), and at 390px "Indemnification", 4px wider than its 326px column,
left its "n" on a line of its own. Read a character at a time, as the gutter rule asks, the words showed those breaks;
the page-width check saw none of them. Chief design's review of #1475 asked for the gutter rule first: the gutter
gives way before a word breaks, and the wrap stays the last resort. Each page's `<main>` now sits in a query container
and takes one class string, `frontend/lib/legalPageLayout.ts`, whose gutter is 16px below 13em of its text size
(/analysis's measure), so the column is 358px at 390px and 288px at 320px. At 390px no word but an address breaks; at
320px the titles hold and six words still break: /security's "Authentication" and "Infrastructure" and /terms'
"EarningsNerd", "Subscriptions,", "MERCHANTABILITY," and "Indemnification", three of those by 1 to 5px, so another
machine's list can differ by them. At the default size, and from 430px under 200% text, each text run's line boxes are
what they were, in both themes. `E131_AT_320`'s pins left with the first fix, and `tests/e2e/reflow-200.spec.ts` holds
/security, /terms and /privacy at every width its route loop visits, every word of each whole at 390px under 200% text
(an address and a break after a hyphen left out) and each page's h1 whole at 320px.

**Recurrence (2026-10-22, C5 consistency)**: the approved full-fill italic treatment first reached only
the default homepage headline. The founder requested full consistency; the other experiment arms,
authentication pane, waitlist, mail header and current share/print templates still carried the old
promotional mark. `BrandEmphasis` now owns the web phrase recipe and local italic loader;
`brandCopyRules.spec.ts` checks its callers while keeping source annotations separate. The existing
reflow gates cover the longer phrases and waitlist form codes. Current editable templates and
generated assets change together; historical audit screenshots remain evidence of their date.

**Recurrence (2026-10-23, the dialog header again, E158; chief design on #1495)**: the title wrapped under
its icon but kept the group's width beside the close button's column, 64px narrower than the header, so
at 320 and 360px under 200% text the consent dialog's "preferences" (197px) broke inside a 152px and a
187px title. A stacked title now takes the header's full width (216, 251 and 277px at 320, 360 and
390px), and `frontend/tests/e2e/reflow-200.spec.ts` holds both dialogs: the stacked title at the header's
full width, under the close button too, every painted line inside the title's box and clear of the close
button, and no word broken. A header with no icon kept its title beside the close button until E165
gave it the same line (the feedback dialog's "feedback", 153px, broke in a 152px title at 320px), and
the case holds the feedback dialog too.

**Recurrence (2026-10-23, the site header's menus, E160; chief design on #1491)**: signed in at 1024, 1280
and 1440px under 200% text the bar wrapped and its controls landed alone on a line, at its start, so the
notification menu (20rem, anchored at the bell's right edge) spanned -408 to 232px and the account menu
-108 to 372px, every item losing its first letters. The logo's `mr-auto` and the controls' `ml-auto` keep
the controls at the right of their line (at 1024px the menus span 180 to 820px and 480 to 960px), and
`frontend/tests/e2e/reflow-200.spec.ts` opens each menu at the three widths under 200% text, with the
one-line bar at 1440px held to justify-between's place (the nav as far from the logo as from the
controls).
