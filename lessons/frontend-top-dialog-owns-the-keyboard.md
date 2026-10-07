# The top dialog owns the keyboard: listen in window capture and stop the keys it handles

Date: 2026-10-02   Area: frontend

**Context**: `components/ui/Modal.tsx` (design-v3 pack) and the mobile copilot sheet's
`useSheetFocusTrap` both listened for `keydown` on `document` in the capture phase. Listeners on
the same node run in registration order, so when UpgradeModal opened from the sheet below `lg`,
the sheet's trap (armed first) saw every key before the dialog: Tab pulled focus back into the
sheet behind the scrim, and one Escape closed both layers. `stopPropagation()` inside the
dialog's listener could not help, because it does not stop other listeners on the same node.
Four review lenses reproduced it in jsdom; the per-dialog keyboard pass had opened each dialog
on its own, so it never stacked one over the sheet.

**Rule**: (a) A dialog primitive registers its key handling on `window` with `capture: true`,
which runs before every `document`-level listener, and calls `stopPropagation()` on the Tab and
Escape events it handles (Escape too when not dismissible: the layer beneath must not close
instead). (b) Dialogs that can stack keep a module-level stack and only the top one answers. (c)
Tab with focus outside the panel wraps back in. (d) Keyboard passes include one dialog opened over
an already-trapped layer. (e) The same stack owns the body scroll lock and focus return: lock when
the first dialog opens, restore when the last closes, and return focus only when the closing dialog
was the top layer. A per-dialog `prevOverflow` and an unconditional `opener.focus()` let a lower
dialog that closes first unlock the page and pull focus out from under the dialog still open.

**Evidence**: PR #1043, `tests/unit/Modal.spec.tsx` "owns Tab and Escape over a trap that armed
first (the copilot sheet beneath it)". Mutation proof: with the listener moved back to
`document`, the case fails (the sheet's close ran once). Rule (e), found by a Codex task on #1043
and fixed there: "keeps the scroll lock and focus with the upper dialog when a lower one closes
first" fails on the per-dialog cleanup (`overflow` `''`) and, with only the focus guard removed, on
focus. Each mutation: 1 failed | 6 passed; fixed, 7 passed.


**Additional evidence (2026-10-03)**: SourceTrace's window-capture Escape fix stopped the
copilot listeners below it, but it still closed alongside a later ui/Modal listener on the same
window. On the real filing page with a coarse pointer, keyboard users could open the source sheet,
Tab to the global Feedback opener, and open Feedback over it; one Escape closed both. A shared
capture phase does not establish ownership between sibling listeners. SourceTrace now ignores
keys targeted inside the shared Modal's explicit `data-ui-modal` panel marker. An `aria-modal`
check is too broad: a lower copilot sheet can retain focus beneath the source sheet, so its
semantics do not identify it as the upper layer.
`SourceTraceEscapeLayer.spec.tsx` covers a real Modal opened after the source sheet: one Escape
closes the upper dialog and the next closes the source sheet. The browser probe uses actual page
controls with fixture API responses; the source sheet's separate focus-containment limitation
predates this Escape change.

The same sibling-listener failure also occurred in BellPopover: start a calendar alert toggle,
open the global Feedback dialog while the request is pending, then let the request fail. The
error popover correctly preserves textarea focus in Feedback, but its unconditional window-capture
Escape listener closed both layers. The calendar import gate cannot prevent a global layout dialog
from opening. BellPopover now yields keys targeted inside the shared Modal marker too; its existing
test home covers the delayed popover mount, first Escape closing Feedback alone, and second Escape
closing the remaining popover. A current-source real-page dev probe with fixture API replies
reproduced the sequence; production-build confirmation belongs to the final parent integration gate.

**Additional evidence (2026-10-07)**: the same ordering defeated a popover that handled Escape in
React. EN-01 gave CitationChip's citation card `ownsEscape` through its own `onKeyDown`, which React
dispatches from the root, after every `document`-capture listener and only for keys targeted inside
the card. In Chromium on `main` (`f26debcb`), Escape with focus on a `[1]` chip in an Ask answer
closed the whole research pane (focus fell to `<body>` at 1440×900), and at 390×844 Escape from the
card's "Open original" link closed the sheet too, because the sheet's document-level trap saw the
key first. A popover over a trapped layer is a top layer like any dialog: `useEvidencePopoverKeys`
now takes Escape in window capture while the card is open (yielding to the `data-ui-modal` marker,
as above), so one press closes the card and the next closes the pane. Gate: the shared contract in
`tests/unit/evidencePopoverKeys.spec.tsx` runs both chips with a document-capture stand-in for the
trap and a window listener for the rail, and asserts neither sees the first Escape; with the
handler back in React, CitationChip fails 2 of 18. `tests/e2e/citation-chip-keyboard.spec.ts` covers
both widths in a real browser.
