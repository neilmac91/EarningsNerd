# Close a disclosure that leaves with focus inside the focusout for a keyboard or script focus, and after a press's click, never on the press

Date: 2026-10-23   Area: frontend / focus

**Context**: E167 (#1542) made the open phone menu close when focus leaves the site header. The browser scrolls a
newly focused control into view after its focus event, reading the document's `scroll-padding-top`, which reads
`--site-header-h`: the header's height, open menu included. A close through React's ordinary update was in time for
a native Tab, since React flushes a discrete event's update in a microtask that runs once the focusout listener
returns. It was too late for a focus moved by script: script on the stack runs no microtask between the focusout and
the scroll, and under 200% text at 390x844 the control landed at 91 to 211px, partly under the 151px bar. Closed
inside the focusout (`flushSync`, the new height published in the same commit), it landed at 438 to 558px.

The first version also closed on a press's focusout. A tap or a click focuses what it presses on its mousedown,
before the release. The header is in the page's flow, so the close shrank it by the menu's height, and at the top of
a page nothing anchors the scroll: the page moved under the pointer, the release landed on another element, and the
click went to the two elements' common ancestor. A tap on "See a live example" below the open menu followed nothing,
where main followed it. The review lens found it on a model of the header; a production build confirmed it, by touch
and by mouse.

**Rule**:
- A disclosure that closes when focus leaves, and whose height a scroll padding or an offset reads, closes inside
  the focusout for a keyboard or script focus (`flushSync`, the new height published in the same commit), never
  through a deferred update.
- During a pointer press (from its pointerdown to its click or pointercancel; a keydown ends it), it defers the close
  to a task after the click, so the press activates the control it began on.
- A focus taken by a modal layer (a trap that focuses from an effect) needs no padding: close with a plain update,
  since React refuses `flushSync` inside its own effects.
- Test a press at the top of a page (`scrollY` 0): scroll anchoring hides the shift anywhere else.

**Evidence**: `frontend/components/Header.tsx` (the press ref and `closeMenuWhenFocusLeaves`);
`frontend/tests/unit/Header.spec.tsx` (the menu and the published height read inside the next control's focus event,
the press deferral, a key press ending a press, a modal layer closing it with no `flushSync` warning);
`frontend/tests/e2e/header-covers-nothing.spec.ts` (the Tab out and the script focus at both text sizes, and the tap
at the top of the page). Measured on production builds in this container's Chromium: main followed the tap, the
first version of #1542 did not, and the fix does.
