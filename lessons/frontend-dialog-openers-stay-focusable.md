# Keep a dialog's opener focusable through its pending and cooldown states — aria-disabled, not native disabled

Date: 2026-10-02   Area: frontend

**Context**: On `/admin/invites`, Resend opens `ResendShareModal` on success and then sits in a
30 s cooldown. The button used native `disabled` for both the in-flight request and the cooldown.
`ResendShareModal` (like `RevokeConfirmModal`, and the v3 `ui/Modal` that replaces both in #1043)
records `document.activeElement` as its opener on open and calls `opener.focus()` on close, so
focus fell to `<body>` on every close path (Done, Escape, scrim). It failed twice over in Chromium:
disabling a focused button moves focus to `<body>` at once and fires `blur`, so the dialog recorded
`<body>` as its opener before it even opened; and `focus()` on a disabled button is a no-op. A
Playwright keyboard pass on the v3 modal PR (#1043) caught it. jsdom shows only the second failure.

**Rule**: When a button opens a dialog from an async flow (the dialog opens on a mutation's
success, or focus returns to the button while it is still cooling down), render its in-flight and
post-success states with `aria-disabled` (plus `aria-busy` while pending) and guard its click
handler with an early return. Don't use native `disabled` for those states. The DS `Button`'s
`loading` prop already gives you the attributes and the guard, but not a dimmed look; a hand-rolled
button has to copy them. Converting only the post-success state is not enough, because the
in-flight disable still drops focus in Chromium. Every such opener must also get a close-path spec
like the one below: open the dialog, close it, and assert focus is back on the opener and that the
opener is not natively disabled. The rule is enforced per site by those specs and nothing else.
Opener identity is only known at runtime, so a source scan would cover less than this rule does.
The general gate belongs in `ui/Modal` once #1043 lands.

**Evidence**: `frontend/features/admin/components/InviteRow.tsx` (Resend button);
regression specs in `frontend/tests/unit/admin-invites-page.spec.tsx` ("resend dialog focus
return": all three close paths, the cooldown guard, and the in-flight state, which fails if
native `disabled` comes back while pending); Chromium 141 probe:
`button.disabled = true` while focused leaves `document.activeElement === body` synchronously.
