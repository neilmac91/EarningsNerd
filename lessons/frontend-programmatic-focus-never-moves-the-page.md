# Move focus into a pane with preventScroll, reveal its target inside the box that scrolls it, and move the page at most once, after the pane settles

Date: 2026-10-30   Area: frontend

**Context**: A press on Source opens the filing page's pane on Ask, and the rail focuses its composer a frame later,
or once the plan or usage loads. The composer's `focus()` used the browser's own scroll, which moves every scrolling
ancestor, the page included. The desktop pane's height follows its top a frame late, so after the page above it moves
its lower part can sit below the fold, and in #1813's e2e run 41053542799 the page sat at 495px after the press. With
the pane held three screens tall, a real Chromium moved the page from 0 to 2,142px (E248). Chief design on #1813: "A
press on Source should never move the page under the reader." jsdom scrolls nothing, so every unit test passed. A page
kept still everywhere then left focus in a composer the reader could not see (E252): at the foot of a long page under
200% text the pane's sticky cell has scrolled up with the workspace's end, and at the page's top in a short window the
pane opens below the fold, or shorter than its own tabs.

**Rule**:

(a) A focus the code moves into the filing page's pane (on open, a shortcut, a hand-off, a pre-fill) passes
`{ preventScroll: true }`. It then brings its target into view inside the box that scrolls it and nowhere else, by the
least distance, aiming at the box's part on screen: below the bars the page's scroll padding holds (the site header),
above the fold and the consent bar, or within the window in a fixed layer (the phone's sheet); at the box's own edges
when the target does not fit there. Use `revealInScrollBox` in `CopilotComposer.tsx`, or the same shape
(`highlightInDom`'s `revealWithin` for the reader, `AlertBell`'s `revealFocusIn` for its panel). Never `scrollIntoView`
for it: that scrolls every ancestor.

(b) The box and the target can still change size after the reveal, as a pane settles or a pre-fill grows the field:
while focus stays in the target, bring it back to the nearest edge of the box's part on screen on each resize (a
ResizeObserver on both), but only while it follows. A reveal starts the follow, and so do the reader's scroll and focus
moving in once the target is in view; the reader's scroll that takes it out of view stops it, and a resize never starts
it again. A reveal's own scroll reaches the box's listener a frame late, maybe after the target has grown: read a scroll
to where the reveal left the box as the reveal's, not the reader's.

(c) The page moves at most once, for the press that opened the pane on the target's tab or pre-filled it (Source, ⌘K or
"/", "Ask about this"), and only after the pane has settled: once the target and its box hold still for two frames
(twelve at most), if the target, its scroll margins included, is still not wholly in view below the site header, the
page moves by the least distance that brings it there. Chief design's ruling on #1845 (E252): "Move it once per press or
⌘K. Never move it from a resize or the follow." Never in a fixed layer, which no page scroll moves, and never for a
focus the press did not make: a starter's hand-off, a tab pressed or switched back (an open on another tab arms
nothing). A reader who wheels, touches, clicks or types before the target takes focus, or wheels, touches or presses
before the pane settles, has moved on, and the page stays. Gate the page-move sites to that one. A focus the user moves
(Tab, the arrow keys between tabs, Escape's return) keeps the browser's scroll, which brings the next control into view
where a keyboard user needs it, and so does a dialog's own focus (ui/Modal, the phone's sheet).

(d) Prove it in a real browser, on each path that hands focus over: with the target held below the fold until a frame
after it takes focus, as the pane's height catches up; and, with nothing held, at the page's foot and its top in short
windows under 200% text, and in the sheet. Opening the pane reflows the page, and where Chrome's scroll anchoring then
leaves it varies from run to run, so read where the target lands and how far the page moved (a wrapped
`window.scrollBy`), not one scroll position. In jsdom, record each focus's options, the scroll box's scrollTop writes
and the page's moves (`frontend/tests/unit/scrollBoxes.ts`), and fake the animation frames the settle counts.

**Evidence**: `frontend/features/filings/components/copilot/CopilotComposer.tsx` (`revealInScrollBox`,
`revealOnPage`, the handle and the resize effect) and `AskCopilotRail.tsx` (the press that arms the page's move).
`frontend/tests/e2e/source-press-keeps-the-page.spec.ts` failed on main: the press moved the page from 0 to 2,142px. It
also covers ⌘K, an "Ask about this" pre-fill, a starter pressed from the keyboard, a column that settles shorter, a
pre-fill into a short column, and under 200% text the page's foot (one move up, the shell landing at the header's foot),
the page's top at 1100x800, 600 and 500 (one move down, landing at the window's foot) and the sheet (no move); at 100%
text the foot holds. `frontend/tests/unit/copilotFocusKeepsThePage.spec.ts` gates (a)'s preventScroll half for the
pane's folder and its launcher hand-off, and (c)'s one page-move site. `frontend/tests/unit/CopilotComposer.spec.tsx`
and `AskCopilotRail.spec.tsx`. `frontend/DESIGN_SYSTEM.md` §4, Source pane.
