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

(c) The gate (d) owns "a busy flag never turns a control natively disabled"; per-site specs do not
re-assert it (AGENTS.md §4). They pin what the scan cannot see: no second request on a second
activation, the focus hand-off when a control unmounts, and an unavailable state after the control's
own success (`aria-disabled="true"`, `not.toBeDisabled()`). Focus loss itself needs a real-browser
keyboard pass.

(d) Gated (rule 12): `tests/unit/busyControlsStayFocusable.spec.ts` reads the AST of every `.tsx`
under app/, components/ and features/ and fails on any `disabled={…}` whose expression names a busy
flag (`pending`, `loading`, `submitting`, `sending`, `streaming`, …), directly or through the
binding visible from the site (a `const` or a renamed destructured prop, resolved in its lexical
scope). #1045 converted the four auth submits, and the sweep that followed converted the 29
follow-ups. It now pins 9 sites in 5 files, each by its exact expression, all kept by design because
the control cannot hold focus when it flips: this bell's `checking`; the Analysis Run button (a
contract spec pins it); RevokeConfirmModal's Cancel; the invite fields (four sites); and the
delete-account confirm field and Cancel. In each of the last three, only a sibling's click starts
the request and there is no form. Pins only shrink, and both files and sites are capped: converting
a site means removing its pin, and adding a busy flag to a pinned expression fails.

(e) A control unavailable after its own activation (`!dirty` after a save, an incomplete form, a
cooldown) is aria-disabled with an early return too. A primary DS Button in that state takes
`primaryUnavailableClass`, and a field takes `fieldUnavailableClass` (both in `components/ui`), for
the disabled look without native `disabled`. Never `loading`'s look: that stays the resting fill.

(f) Keeping focus makes a second activation reachable, so the guard must cover the whole
operation. A mutation whose success refetches the data the control depends on returns that
invalidation from `onSuccess` (`return queryClient.invalidateQueries(…)`), so it stays pending until
the refetched data lands. Otherwise the button re-enables in between and a second press sends a
duplicate request (ProfileForm's Save, ConnectedAccounts' Unlink). A hand-rolled async handler does
the same: it awaits the invalidation before clearing its busy flag (admin invites' Send, which would
otherwise mint and email the whole batch again). A removal goes further: its `onSuccess` prunes the item from the cache (`setQueryData`), so the
row and its focused control go with the request itself. A refetch that fails still resolves its
invalidation, so waiting on the refetch alone would leave the deleted row's control live for a second
DELETE (the dashboard's saved-summary Delete; Codex P2 on #1075). YourCompanies' remove needs no
prune: a failed insights refetch puts the section in its error card, which replaces the list
(pinned through the real page in `busyControls.dashboard.spec.tsx`). When `onSuccess` fans out several invalidations,
return the one whose refetch removes or flips the focused control, and fire the rest. Examples: the
filing page's saved status, which swaps Save for Saved; the dashboard's watchlist insights, which
drop a removed row and end the onboarding panel under the popular-ticker chips (a chip whose
insights refetch fails still goes live again: open in (h)). The admin feedback
list is another, because it moves FeedbackRow's controlled select. A success that leaves the page
(`window.location` to Stripe for Manage billing and Manage subscription) stays pending until the page
goes. Its `onSuccess` returns `untilPageReturns()` (`lib/untilPageReturns.ts`). That settles on
`pageshow`, so a back-forward restore brings the button back live. It also settles on the Navigation
API's `navigateerror`, which Chromium fires when the user aborts the pending navigation with Esc or
Stop. A fixed timeout cannot tell an aborted navigation from a slow one, so it is only the fallback
where that API is missing (Codex P2 on #1075). A success that unmounts the control itself (Sign out everywhere's `queryClient.clear()` skeleton)
needs neither. Audit every `onSuccess` of a control this sweep keeps focusable. Hosted Codex found
four of these in later review rounds, after the sweep had shipped them fire-and-forget.

(g) A control that unmounts as a result of its own activation (a row removed on success, a section
swapped for a skeleton, Save replaced by a "Saved" label) hands focus to a stable target: a heading
or status line with `tabIndex={-1}`, focused with `{ preventScroll: true }`. Two forms are accepted:
before the unmount, only when the control holds focus (`document.activeElement === e.currentTarget`),
or after it, only when focus fell to `<body>`. Never move focus a mouse user did not lose. A
hand-off armed by a press (a `retried` or `pressed` ref) is disarmed when that press's own request
fails again. Otherwise a later recovery nobody pressed, such as a reconnect refetch, moves focus
(`useRetainedFailure`'s `retrying` tells a retry that failed from one still running).

(h) The scan cannot see post-success flips, unmounts, or a busy flag under another name. Those stay
per-site specs plus a real-browser keyboard pass. Known open cases, same class, not yet fixed:
EmailVerificationModal's Resend (`disabled={resent}` after success, while focused); the filing
page's Retry generation / Retry / Regenerate Analysis; FeedbackRow's status select when the list is
filtered by status (its own update removes the row); the dashboard header's Log out (no in-flight
guard); PopularTickerChips' add when the insights refetch after it fails (the chip goes live again,
and with no row to prune it needs the added ticker remembered); YourCompanies' remove when the
insights refetch after it fails (the error card replaces the list and focus falls to `<body>` with
no hand-off); the company page's filings Retry, EarningsCalendarPage's "Try again", FullTextSearch's
Retry and FilingViewer's "Try again". YourCompanies' Retry, CompanySearch's "Try Again" and
FilingFeed's Retry are fixed (`busyControls.dashboard.spec.tsx`, `CompanySearch.spec.tsx`,
`busyControls.watchlist.spec.tsx`).
- A Retry that hands focus to a text field arms only on a keyboard press (`e.detail === 0`), since
  focusing the field after a tap raises the touch keyboard. `:focus-visible` cannot stand in, because
  it reflects how the control got focus, not how it was activated: a tap on a keyboard-focused button
  still matches.
- The hand-off is armed with the term pressed. A term that changes, including Escape clearing it,
  drops the failure without a result, so the hand-off disarms rather than firing.
- `useRetainedFailure` takes a reset key for a query whose key changes under it, such as a new
  search term.
- A fetch is in flight while `fetchStatus !== 'idle'`. A retry paused offline or in a hidden tab is
  still the press's fetch, so `isFetching` alone would release the failure, and the busy state, too
  early.
- When a retry fails again with the same message, the alert's text is unchanged, so nothing is
  announced. Keying the message node to `errorUpdateCount` re-inserts it, and the busy button's
  `loadingText` names the busy state. The dashboard's two Retry buttons, saved-summary Delete and Manage subscription are
fixed (`tests/unit/busyControls.dashboard.spec.tsx`). A Retry whose query has no data must keep its
failure while the press runs (`hooks/useRetainedFailure.ts`): the refetch puts the query back to
pending, and a page gated on `isLoading` swaps the focused Retry for a skeleton.

**Evidence**: `frontend/features/calendar/components/AlertBell.tsx` (`disabled={checking}`,
`aria-disabled={pending || undefined}` plus an early return). `tests/unit/calendarBellKeepsFocus.spec.tsx`
fails on the old attribute. Real build, both themes, a bell on the page and one in the day dialog:
focus stays on the bell during and after the request, 8/8; `main` fails 8/8 with focus on `<body>`.
The gate fails on the bell's old `disabled={pending || checking}`, on a new busy-disabled site in an
unlisted file, and on a converted site whose pin was not removed.
The sweep that followed (busyControls.<group>.spec.tsx) pins every converted control's attributes,
its focus through busy and settle, and that a second activation sends nothing; each case fails with
the old native `disabled` restored.
