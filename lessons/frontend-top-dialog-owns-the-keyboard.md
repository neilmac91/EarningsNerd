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
