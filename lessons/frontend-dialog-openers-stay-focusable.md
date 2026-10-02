# A control that opens a dialog stays focusable until the dialog closes — gate it with aria-disabled, not native disabled

Date: 2026-10-02   Area: frontend

**Context**: On `/admin/invites`, Resend opens `ResendShareModal` on success and then sits in a
30 s cooldown. The button used native `disabled` for both the in-flight request and the cooldown.
Every dialog in the app (the hand-rolled shells and the v3 `ui/Modal`) records
`document.activeElement` as its opener on open and calls `opener.focus()` on close, so focus fell
to `<body>` on every close path (Done, Escape, scrim). It failed twice over in Chromium: disabling
a focused button moves focus to `<body>` at once and fires `blur`, so the dialog recorded `<body>`
as its opener before it even opened; and `focus()` on a disabled button is a no-op. A Playwright
keyboard pass on the v3 modal PR (#1043) caught it. jsdom shows only the second failure.

**Rule**: Any control that opens a dialog, and any control the dialog's close returns focus to,
must stay focusable for its in-flight and post-success states. Render those states with
`aria-disabled` (plus `aria-busy` while pending), style them with `aria-disabled:` variants, and
guard the click handler with an early return. Never use native `disabled` there. This is the DS
`Button`'s `loading` contract; a hand-rolled button has to copy it. When you convert one, test the
pending state too: converting only the post-success state still loses focus in Chromium.

**Evidence**: `frontend/features/admin/components/InviteRow.tsx` (Resend button);
regression specs in `frontend/tests/unit/admin-invites-page.spec.tsx` ("resend dialog focus
return" — all three close paths, the cooldown guard, and the in-flight state); Chromium 141 probe:
`button.disabled = true` while focused leaves `document.activeElement === body` synchronously.
