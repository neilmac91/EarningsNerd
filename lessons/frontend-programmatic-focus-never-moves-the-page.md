# Move focus into a pane with preventScroll, and bring its target into view inside the box that scrolls it, never the page

Date: 2026-10-30   Area: frontend

**Context**: A press on Source opens the filing page's pane on Ask, and the rail focuses its composer a frame later,
or once the plan or usage loads. The composer's `focus()` used the browser's own scroll, which moves every scrolling
ancestor, the page included. The desktop pane's height follows its top a frame late, so after the page above it moves
its lower part can sit below the fold, and in #1813's e2e run 41053542799 the page sat at 495px after the press. With
the pane held three screens tall, a real Chromium moved the page from 0 to 2,142px (E248). Chief design on #1813: "A
press on Source should never move the page under the reader." jsdom scrolls nothing, so every unit test passed.

**Rule**:

(a) A focus the code moves into the filing page's pane (on open, a shortcut, a hand-off, a pre-fill) passes
`{ preventScroll: true }`. It then brings its target into view inside the box that scrolls it and nowhere else: the
nearest scroll container, the least distance, never the page. Use `revealInScrollBox` in `CopilotComposer.tsx`, or the
same shape (`highlightInDom`'s `revealWithin` for the reader, `AlertBell`'s `revealFocusIn` for its panel). Never
`scrollIntoView` for it: that scrolls every ancestor.

(b) The box can still change size after the reveal, as a pane settles: keep a target that stood in view at the box's
nearest edge while focus stays in it (a ResizeObserver on the box), and leave one the reader scrolled away where they
put it.

(c) A focus the user moves (Tab, the arrow keys between tabs, Escape's return) keeps the browser's scroll, which brings
the next control into view where a keyboard user needs it, and so does a dialog's own focus (ui/Modal, the phone's
sheet). Whether a press should move the page when the pane itself is off-screen, at the foot of a long page, is chief
design's call on E248's pull request.

(d) Prove it in a real browser with the target held below the fold, on each path that hands focus over. In jsdom,
record each focus's options and the scroll box's scrollTop writes, and watch the page's own scroll
(`frontend/tests/unit/scrollBoxes.ts`).

**Evidence**: `frontend/features/filings/components/copilot/CopilotComposer.tsx` (`revealInScrollBox`, the handle and
the resize effect). `frontend/tests/e2e/source-press-keeps-the-page.spec.ts` failed on main: the press moved the page
from 0 to 2,142px; it also covers ⌘K, an "Ask about this" pre-fill, a starter pressed from the keyboard, and a column
that settles shorter. `frontend/tests/unit/copilotFocusKeepsThePage.spec.ts` gates (a) for the pane's folder.
`frontend/tests/unit/CopilotComposer.spec.tsx` and `AskCopilotRail.spec.tsx` ("focuses its composer without moving the
page (E248)"). `frontend/DESIGN_SYSTEM.md` §4, Source pane.
