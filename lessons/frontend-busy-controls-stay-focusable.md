# A control busy with its own request stays focusable: aria-disabled plus an early return, never native disabled

Date: 2026-10-02   Area: frontend

**Context**: The calendar's earnings-alert bell rendered `disabled={pending || checking}`. A
keyboard user who pressed Enter on a bell started the toggle, and the focused button then became
natively `disabled`. Chromium blurs a focused element that turns disabled. Focus landed on `<body>`
and stayed there after the request settled. So every keyboard toggle sent the user back to the top of
the document, including inside the day dialog. jsdom does not blur disabled elements, so unit tests
never saw it. The real-build keyboard pass in the design-v3 dialog follow-up measured it:
`before: BUTTON · while pending: BODY · after settle: BODY`.

**Rule**:

(a) While a control's own request is in flight, mark it `aria-disabled` and return early in its
handler. That keeps it focusable and announced as unavailable. Keep the busy styling. The DS
`<Button loading>` already does this by design (see
`frontend-guard-submit-on-loading-buttons.md`).

(b) Native `disabled` is fine only where the control cannot hold focus yet, for example before
identity first resolves.

(c) A unit test pins the attribute: `aria-disabled="true"` and `not.toBeDisabled()`. Focus loss
itself needs a real-browser keyboard pass.

(d) Gated (rule 12): `tests/unit/busyControlsStayFocusable.spec.ts` reads the AST of every `.tsx`
under app/, components/ and features/ and fails on any `disabled={…}` whose expression names a busy
flag (`pending`, `loading`, `submitting`, `sending`, `streaming`, …), directly or through the
binding visible from the site (a `const` or a renamed destructured prop, resolved in its lexical
scope). It found 38 such sites in 26 files; each is pinned by its exact expression with a reason:
two kept by design (this bell's `checking`; the Analysis Run button, which a contract spec pins),
seven the design-v3 stack converts, and the rest follow-ups. Pins only shrink, and both files and
sites are capped: converting a site means removing its pin, and adding a busy flag to a pinned
expression fails.

(e) The scan cannot see post-success flips (`!dirty` after a save, `saved`, `resent`, a cooldown)
that disable the control the user just activated, nor a busy flag under another name. Those stay
per-site specs plus a real-browser keyboard pass.

**Evidence**: `frontend/features/calendar/components/AlertBell.tsx` (`disabled={checking}`,
`aria-disabled={pending || undefined}` plus an early return). `tests/unit/calendarBellKeepsFocus.spec.tsx`
fails on the old attribute. Real build, both themes, a bell on the page and one in the day dialog:
focus stays on the bell during and after the request, 8/8; `main` fails 8/8 with focus on `<body>`.
The gate fails on the bell's old `disabled={pending || checking}`, on a new busy-disabled site in an
unlisted file, and on a converted site whose pin was not removed.
