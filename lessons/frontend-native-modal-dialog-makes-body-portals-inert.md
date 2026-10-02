# Under a native showModal() dialog, portal into the dialog and preventDefault the keys you own

Date: 2026-10-02   Area: frontend

**Context**: The calendar's bell popover portalled to `<body>` at `z-50`. The same bell renders
inside `DayDetailDialog`, a native `<dialog>` opened with `showModal()`. Measured in Chromium,
a `<body>` portal opened while that dialog is up is inert (`focus()` is refused) and painted
beneath the top layer (`elementFromPoint` returns the dialog), whatever its z-index. So a
signed-out user who clicked a bell in the day view got a prompt nobody could see or reach.
Migrating the popover to `ui/Modal` would not have helped, because Modal also portals to
`<body>`. Separately, the popover's document-capture Escape handler called only
`stopPropagation()`, and the native dialog still fired `cancel` and `close` on the same key.
One Escape closed both layers.

**Rule**:

(a) Anything raised while a native modal `<dialog>` is open portals into that dialog
(`document.querySelector('dialog[open]') ?? document.body`), not into `<body>`. That includes an
async result whose trigger sat outside the dialog. Fixed positioning still works there:
the dialog animates opacity only, so it is not a containing block.
Such a layer also never outlives a change of that dialog. The calendar page clears the popover on
every day change: a dialog removed by React (its ✕ from the keyboard) fires no `cancel` or `close`,
which would orphan the popover in the detached dialog, still holding Escape.
`calendarDayDialogPopover.spec.tsx` pins both directions.

(b) A layer above a native dialog that handles Escape calls `preventDefault()` as well as
`stopPropagation()`. The dialog's close request is the key's default action.

(c) Never open `ui/Modal` from anything the calendar page renders; any layer it raises can sit over
`DayDetailDialog`. Gated: `dialogAllowlist.spec.ts` walks the page's imports.

(e) The day dialog never gains a transform, filter, contain, will-change or a non-opacity animation.
Any of those makes it the containing block for the fixed popovers portalled into it, which then clip
and mis-position. Gated in the same spec, which reads its `className` and its keyframes.

(d) A keyboard pass on any layer that can appear inside the day dialog runs one case with
the dialog open.

**Evidence**: Chromium 1194 measurements (body portal under `showModal()`: focus refused, the
dialog on top; portal into the dialog: focusable, on top; Escape with stopPropagation only:
`cancel` then `close`; with preventDefault: dialog stays open). `tests/unit/BellPopover.spec.tsx`
"raised from a bell inside an open <dialog>…", "an error that arrives after a day dialog
opened…" and "Escape closes, is consumed…". Each fails alone when its line is mutated (portal
to `<body>`; drop `preventDefault`). The real-build keyboard pass in the follow-up PR covers the
in-dialog cases in both themes.
