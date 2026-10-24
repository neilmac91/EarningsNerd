# Close a disclosure that leaves with focus inside the focusout for a keyboard or script focus, and on a press only where it lies over the page

Date: 2026-10-23, updated 2026-10-24 (E182)   Area: frontend / focus

**Context**: E167 (#1542) made the open phone menu close when focus leaves the site header. The browser scrolls a
newly focused control into view after its focus event, reading the document's `scroll-padding-top`, which reads
`--site-header-h`: the header's height, open menu included. A close through React's ordinary update was in time for
a native Tab, since React flushes a discrete event's update in a microtask that runs once the focusout listener
returns. It was too late for a focus moved by script: script on the stack runs no microtask between the focusout and
the scroll, and under 200% text at 390x844 the control landed at 91 to 211px, partly under the 151px bar. Closed
inside the focusout (`flushSync`, the new height published in the same commit), it landed at 438 to 558px.

The first version also closed on a press's focusout. A tap or a click moves focus on its mousedown, before the
release: to what it presses, or to the page's main region (`tabindex="-1"`, the skip link's target) when it presses
text. The header is in the page's flow, so the close shrank it by the menu's height, and at the top of a page nothing
anchors the scroll: the page moved under the pointer, the release landed on another element, and the click went to
the two elements' common ancestor. A tap on "See a live example" below the open menu followed nothing, where main
followed it. The review lens found it on a model of the header, chief design on a production build (comment
6375679863), and a production build in this container confirmed it by touch and by mouse. Chief design's refined
ruling: a press leaves the menu open, as before, since a reader who presses can see where.

E182 refined the press half. #1558 moved the open compact menu over the page from `lg` (`lg:absolute`), where the
header keeps the bar's height, so a close there moves nothing under the pointer, and the menu was left as the one
menu in the bar that a press outside did not close (the account menu and the bell's panel close on it). Chief design
ruled (#1565, comment 6380050139) that from `lg` a press outside the open menu closes it; below `lg`, in the flow, a
press still leaves it open.

**Rule**:
- A disclosure that closes when focus leaves, and whose height a scroll padding or an offset reads, closes inside
  the focusout for a keyboard or script focus (`flushSync`, the new height published in the same commit), never
  through a deferred update.
- A press's focusout never closes it: mark the press from its `mousedown` (capture, on the document) until the next
  task, and skip the focusout's close while it is marked. Use `mousedown`, not `pointerdown`: a tap moves focus with
  its compatibility mousedown, after its pointer events and in a later task.
- A press closes it only where the close moves nothing. Where the open disclosure lies over the page (its own
  computed position `absolute`, read at the press, not a breakpoint repeated in the code), a press outside its owner
  closes it from that same `mousedown`, as a dropdown closes, and the press lands where it was aimed. Where it sits in
  the page's flow, a press leaves it open.
- A focus taken by a modal layer (a trap that focuses from an effect) needs no padding: close with a plain update,
  since React refuses `flushSync` inside its own effects.
- Test a press at the top of a page (`scrollY` 0): scroll anchoring hides the shift anywhere else. Test the close
  over the page with a pointer press on a control below the open disclosure: the control takes the click and the page
  holds. Playwright's own click scrolls a sticky element into view first, so press at its box (`page.mouse.click`).

**Evidence**: `frontend/components/Header.tsx` (`pressingRef` and `closeMenuWhenFocusLeaves`);
`frontend/tests/unit/Header.spec.tsx` (the menu and the published height read inside the next control's focus event,
a press on a control and on text leaving the menu open, a press's mark ending with its task, a navigation closing it,
a modal layer closing it with no `flushSync` warning, and, with the menu's position absolute, a press on the page
closing it and a press inside the header keeping it); `frontend/tests/e2e/header-covers-nothing.spec.ts` (the Tab
out and the script focus at both text sizes, the tap at the top of the page following its link, and from `lg` a
press on the page closing the open menu and reaching its target at 1024x768 and 1100x800, E182, #1572). Measured on
production builds in this container's Chromium: main followed the tap, the first version of #1542 did not, and the
fix does.
