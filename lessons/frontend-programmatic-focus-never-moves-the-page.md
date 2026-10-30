# Move focus from code with preventScroll, and bring its target into view inside the box that scrolls it, never the page

Date: 2026-10-30   Area: frontend

**Context**: A press on Source opens the filing page's pane on Ask, and the rail focuses its composer a frame later,
or once the plan or usage loads. The composer's `focus()` used the browser's own scroll, which moves every scrolling
ancestor, the page included. Before the desktop pane measures its top, its lower part can sit below the fold, and in
#1813's e2e run 41053542799 the page sat at 495px after the press. With the pane held three screens tall, a real
Chromium moved the page from 0 to 2,142px (E248). Chief design on #1813: "A press on Source should never move the page
under the reader." jsdom scrolls nothing, so every unit test passed.

**Rule**:

(a) A focus the code moves (on open, a shortcut, a hand-off, a pre-fill) passes `{ preventScroll: true }`. It then
brings its target into view inside the box that scrolls it and nowhere else: the nearest scroll container, the least
distance, never the page. Use `revealInScrollBox` in `CopilotComposer.tsx`, or the same shape (`highlightInDom`'s
`revealWithin` for the reader, `AlertBell`'s `revealFocusIn` for its panel). Never `scrollIntoView` for it: that
scrolls every ancestor.

(b) A focus the user moves (Tab, the arrow keys between tabs) keeps the browser's scroll, which brings the next control
into view where a keyboard user needs it.

(c) Prove it in a real browser with the target held below the fold. In jsdom, record each focus's options and the
scroll box's scrollTop writes, and watch the page's own scroll (`frontend/tests/unit/scrollBoxes.ts`).

**Evidence**: `frontend/features/filings/components/copilot/CopilotComposer.tsx` (`revealInScrollBox` and the handle).
`frontend/tests/e2e/source-press-keeps-the-page.spec.ts` failed on main: the press moved the page from 0 to 2,142px.
`frontend/tests/unit/CopilotComposer.spec.tsx` and `AskCopilotRail.spec.tsx` ("focuses its composer without moving
the page (E248)"). `frontend/DESIGN_SYSTEM.md` §4, Source pane.
