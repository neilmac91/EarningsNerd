# A popover that opens on focus must survive the scroll that focusing caused

Date: 2026-10-05   Area: frontend

**Context**: SourceTrace's and CitationChip's evidence popovers open on hover or focus and close on
any `scroll` event, because a `position: fixed` popover detaches from its chip when the page moves.
Tabbing to a chip below the fold makes the browser scroll it into view, and that scroll closed the
popover the focus had just opened, in the same frame. The Impeccable critique's keyboard probe
counted zero popovers after focusing a chip, and Tab left the chip for the next chip: "Open in SEC
EDGAR" was unreachable by keyboard (EN-01). jsdom fires no scroll on focus, so unit tests passed; only
Chromium showed it (`locator.focus()` then Tab landed on the next chip).

**Rule**:

(a) A surface that opens on focus is owned by the keyboard while the trigger has focus or focus is
inside it. On `scroll` and `resize`, re-anchor it (recompute its position from the trigger's rect);
close it only when the pointer owns it (focus elsewhere).

(b) A keyboard hand-off into a portaled popover (Tab from the trigger to its action) is proven in a
real browser with the trigger scrolled from off-screen, not with the trigger already in view.

(c) The dismiss rule stays for hover: a hover popover that outlives a scroll sits over the wrong text.

**Evidence**: `frontend/features/filings/components/SourceTrace.tsx` and
`copilot/CitationChip.tsx` (the scroll/resize listener re-anchors when `document.activeElement` is the
trigger or inside the popover). `tests/unit/evidencePopoverKeys.spec.tsx` "a scroll re-anchors a
keyboard-owned popover and closes a hover one" (both chips; fails on the old `setOpen(false)` /
`setPos(null)`). `tests/e2e/filing-source-chip.spec.ts` "keyboard: Tab from the chip reaches
'Open in SEC EDGAR'" runs in Chromium against a chip the page has to scroll to.
