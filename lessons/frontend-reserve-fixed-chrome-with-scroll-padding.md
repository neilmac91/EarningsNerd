# A focus scroll stops at the viewport edge, not at a fixed overlay: reserve the overlay with scroll-padding

Date: 2026-10-06   Area: frontend

**Context**: EN-02 made the desktop Ask pane's sticky column end where the cookie-consent bar begins
(`100vh - 4rem - var(--consent-inset)`). Opening the pane focuses its composer; before the change
the composer sat 152px below the viewport, the browser's focus scroll pulled it to the viewport
edge and left it 9px under the bar. After the change the composer sat INSIDE the viewport but
behind the bar, so the focus scroll did nothing at all: the user typed into a textarea they could
not see. Shrinking the chrome had moved the composer from "off-screen, auto-scrolled" to
"on-screen, covered" — a worse state the same focus() call could not repair, because the browser's
"scroll into view if needed" knows the viewport, not what paints over it.

**Rule**:

(a) When a fixed overlay reserves part of the viewport, give the scrollport the same reservation:
`scroll-padding-bottom: var(--overlay-inset, 0px)` on `html` (top for a sticky header). Every
`focus()`, `scrollIntoView()` and anchor jump then treats the overlay's strip as not visible and
scrolls the target clear of it. Chromium honours scroll padding for focus scrolling (measured: the
composer lands 88px above the bar at 1440x900 and 1280x600).

(b) An inset variable that chrome consumes needs a gate line for the scrollport too: the ladder
gate fails when `globals.css` loses `scroll-padding-bottom: var(--consent-inset, 0px)`.

(c) Measure the state a user reaches, not only the state a probe constructs: "open the pane from
the top of the page, then read the composer's rect and `elementFromPoint`" caught this; a probe that
scrolled first would not have.

**Evidence**: `frontend/app/globals.css` (`html { scroll-padding-bottom: var(--consent-inset, 0px) }`);
`frontend/tests/unit/bottomChromeLadder.spec.ts` (the scroll-padding clause; a scratch-copy probe setting
it to `0px` fails it — the repository's one mutation demonstration is the bar's `z-consent` → `z-50`); `frontend/tests/e2e/consent-bar-yields.spec.ts` `expectComposerClear` (desktop: waits for the
focus scroll, then the pane's bottom ≤ the bar's top and the composer hits itself);
harness jobs `A2after-launcher-click-pane-1440-pro`, `-1280x600-pro` in
`tasks/critique-env-2026-10-04/jobs-en02.json` (scrollY 480 / 330 after the click, composer clear).
