# Arm a dialog's focus trap once per open; never key its effect on a callback prop's identity

Date: 2026-10-01   Area: frontend

**Context**: The design-v3 `components/ui/Modal.tsx` (pack file) listed `onClose` in the
dependency array of the effect that captures the opener, moves focus in, traps Tab and restores
focus on cleanup. Most consumers pass an inline `onClose={() => …}`, so every parent render handed
Modal a new function and re-ran the effect while the dialog stayed open: the cleanup returned
focus to the opener, the re-run captured an element INSIDE the panel as the new "opener" and
refocused the first focusable. Unit tests, lint, the build and the visual pass were all green; a
Playwright keyboard pass on the real build caught it on `/admin/invites`, where the invite row's
30 s resend cooldown re-renders every second: focus jumped to the ✕ once a second and landed on
`<body>` after closing (5 failed checks on ResendShareModal; Revoke and Upgrade carried the same
latent dependency without a re-render source).

**Rule**: (a) An effect that captures `document.activeElement`, moves focus or installs a trap
must depend only on the open state and configuration (`open`, `dismissible`, `initialFocusRef`),
never on a callback prop: read callbacks through a ref synced in its own effect (the repo's
`react-hooks/refs` lint rule forbids writing a ref during render). (b) Do not ask consumers to
memoize instead — the primitive must be correct with inline arrows. (c) Verify dialogs with a
keyboard pass on a real build that includes a parent re-render while open (an interval tick or a
`rerender`), not only open/close; `tests/unit/Modal.spec.tsx` pins the regression. The copilot
sheet's `useSheetFocusTrap` still keys its effect on `onClose`; its two callers pass stable
callbacks today, and it was outside the v3 scope (queued as a follow-up).

**Evidence**: PR #1043, the ui/Modal commit (the fix is folded into it); keyboard pass
before (104 pass / 5 fail, all ResendShareModal, focus timeline jumping to ✕ on each cooldown
tick) and after (the 1.5 s focus-stability check passes on every dialog);
`tests/unit/Modal.spec.tsx` "does not re-arm when the parent re-renders with a new inline onClose".
