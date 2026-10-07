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
own success (`aria-disabled="true"`, `not.toBeDisabled()`). One exception: RetryButton's own unit case
(`useRetainedFailure.spec.tsx`) asserts its busy state, `not.toBeDisabled()` included, because every Retry
renders through that one control: it is the control's contract, not a per-site repeat. Focus loss itself
needs a real-browser keyboard pass.

(d) Gated (rule 12): `tests/unit/busyControlsStayFocusable.spec.ts` reads the AST of every `.tsx`
under app/, components/, features/, hooks/ and lib/ (so RetryButton itself, in hooks/, is scanned: a native
`disabled` on it fails) and fails on any `disabled={…}` whose expression names a busy
flag (`pending`, `loading`, `submitting`, `sending`, `streaming`, …), directly or through the
binding visible from the site (a `const` or a renamed destructured prop, resolved in its lexical
scope). #1045 converted the four auth submits, and the sweep that followed converted the 29
follow-ups. It now pins 9 sites in 5 files, each by its exact expression, all kept by design because
the control cannot hold focus when it flips: this bell's `checking`; the Analysis Run button (a
contract spec pins it); RevokeConfirmModal's Cancel; the invite fields (four sites); and the
delete-account confirm field and Cancel. In each of the last three, only a sibling's click starts
the request and there is no form. Pins only shrink, and both files and sites are capped: converting
a site means removing its pin, and adding a busy flag to a pinned expression fails. It also fails on
a post-success flag by name (`resent`, `saved`, `copied`, `succeeded`/`success`, `cooldown`), with
no pins: EmailVerificationModal's `disabled={resent}` was the last one. The same file gates every Retry of
a query to `<RetryButton>` (rule (g)), seen two ways. By its wiring, through the same binding resolver:
`loading` fed by a fetching flag (`isFetching` is false while a fetch waits paused, so the control goes
live mid-request) or by the query's `fetchStatus` (the right signal, hand-rolled), or a handler that
reaches `refetch…` (`refetchQueries` included) or a failure's `retry`, through a const or a function
declaration (`function reload() { … }` is followed like `const reload = () => …`), or that calls
`invalidateQueries` or `resetQueries` in its own expression. Those two count only inline: through bindings they reach every
mutation whose `onSuccess` invalidates (rule (f) requires it) and every submit that refreshes after it
lands, 20 handlers in 15 files when measured and none a Retry, so a Retry that invalidates through a named
handler is left to the label clause. By its label: any element but RetryButton whose `loadingText` starts
"Retrying" or whose label starts "Retry" or "Try again", a same-file string const (`{retryLabel}`)
included. RetryButton's own definition is the one exemption from both Retry clauses, by file and function
name (it is the sanctioned wiring and label); a function of that name anywhere else is just another
hand-rolled Retry. Each has a shrink-only, capped allowlist with reasons: ALLOW_RETRY pins 5 wiring sites
in 3 files (open rule (h) Retry buttons), ALLOW_RETRY_LABEL 11 labels in 11 files (4 error-boundary
resets, 3 stream or answer restarts, 4 open rule (h) sites). Every Retry the retry-hardening follow-up
converted fails both clauses at its 026d6df version (20 wiring and 10 label offenders in 6 files). A third
clause (EN-05) checks what RetryButton is given: each element of its `failures` is `useRetainedFailure(…)`,
inline, through a same-file const or either branch of a conditional, or, when it is a prop of the component
rendering RetryButton, at every `<Component prop={…}>` call site (a prop nobody passes fails). Anything else is
a failure built by hand, which skips the hold and can carry `busy: isFetching`: ALLOW_HAND_BUILT_FAILURE pins
it by its text (1 site, the filing page's stream restart), capped and shrink-only.

(e) A control unavailable after its own activation (`!dirty` after a save, an incomplete form, a
cooldown, "Link sent") is aria-disabled with an early return too. A primary DS Button in that state
takes `primaryUnavailableClass`, a secondary one `secondaryUnavailableClass`, and a field
`fieldUnavailableClass` (all in `components/ui`), for the disabled look without native `disabled`.
Never `loading`'s look: that stays the resting fill. `secondaryUnavailableClass` fades the label and
the hairline, not the element: the variant's native `opacity-50` would fade the focus ring the
focusable state still shows (EmailVerificationModal's Resend, measured in Chromium).

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

(g) A control that unmounts as a result of its own activation (a row removed on success, Save replaced
by a "Saved" label) hands focus to a stable target: a heading or status line with `tabIndex={-1}`, focused
with `{ preventScroll: true }`. Two forms are accepted: before the unmount, only when the control holds
focus (`document.activeElement === e.currentTarget`), or after it, only when focus fell to `<body>`. Never
move focus a mouse user did not lose.
- A Retry's hand-off fires only when the Retry unmounts while it holds focus, whatever the cause: its own
  success, a recovery nobody pressed (a reconnect, window focus, an invalidation), a new search term.
  Nothing is armed by a press. The press-armed form (a `retried` or `pressed` ref, fired when the error UI
  later cleared) is the bug class this replaced: a second press or a retry paused offline wedged it, a
  press that failed again left it armed for a later recovery, and a refetch nobody pressed still dropped a
  focused Retry to `<body>`. `useFocusHandoff` (`hooks/useFocusHandoff.ts`) is the mechanism: the
  control's callback ref sees it leave while it is still connected and focused, and a microtask after the
  commit moves focus only if the node really left (React may keep a node under a new ref callback) and
  focus is on `<body>`. Runtime: the unit tests run react 18.3.1 (package.json); the App Router aliases
  `react` and `react-dom` to Next's vendored React, 19.3.0-canary-cbb046ab-20260731 with next 16.3.6
  (`node_modules/next/dist/build/create-compiler-aliases.js`), and there is no `pages/` router, so
  production runs React 19. The hand-off was checked in Chromium under both, 7/7 scenarios each (a press,
  a recovery nobody pressed, focus elsewhere, a busy re-render, no target, a reused node, a deep subtree).
- The hold contract (`useRetainedFailure(query, queryKey)`, `hooks/useRetainedFailure.tsx`): a failure a
  component has rendered stays on screen through any refetch of that query, pressed or not, until data
  replaces it, with its Retry busy. React Query puts a failed query with no data back to `pending`
  (`error: null`) the moment it refetches; read raw, that swaps the error UI, and a focused Retry in it, for
  a skeleton. The hold is tied to the failing query: `queryKey` is the key its own `useQuery` was given (a
  query result does not carry it), and the hold is `hashKey(queryKey)` with the failure's `errorUpdatedAt`
  and `errorUpdateCount`, which a pending refetch keeps. So a key change (another user, a new search term)
  shows the new query's own first load, never the old error. The query state alone cannot tell two keys
  apart: two keys that each fail once in the same millisecond share both counters, and the counters-only
  hold returned `{failed: true, busy: true, error: 'a down'}` for the new key's first load.
  `errorUpdateCount > 0` alone is weaker still. The count tells a second failure in the same millisecond
  from the first; the time tells a failure after a reset of the same key (`resetQueries`, which zeroes both
  counters, so its refetch is a first load) from the one before it at the same count. Data ends the hold (a query that is neither `error` nor `pending`),
  so a later background refetch over loaded data never shows the old error. A first load is never held, nor
  a fresh mount over a failure it never rendered. It is derived from the query's state on each render, so no
  second press, paused fetch or batched settle can wedge it. Gated (rule 12): every caller under app/,
  components/, features/, hooks/ and lib/ passes, as `queryKey`, the same expression as its own same-file
  query hook's `queryKey:` (`useRetainedFailure.spec.tsx`, an AST scan), so a caller that passes another
  key, or none, fails. This is a visible change
  the founder chose (2026-10-04): an error card stays up, its Retry busy, through a reconnect or a refocus
  that used to show the skeleton.
- One `<RetryButton>` owns the Retry: busy (`loading`) while any of its failures has a fetch in flight
  (`fetchStatus !== 'idle'`, paused offline included), whoever started it; a press retries only the
  failures that failed, since a healthy sibling refetched too could settle first and end the error UI early;
  the hand-off above. It reads "Retrying…" only while its own press's retry runs. During a refetch nobody
  pressed it is busy (aria-busy, aria-disabled, the spinner, a refused press) under its own label: a label
  swap inside the card's `role=alert` would re-announce the failure at every reconnect.
- One RetryButton instance never serves two error UIs. React reuses an unkeyed element in the same slot, so
  when one Notice replaces another in a single render the focused node stays, relabelled, and never
  unmounts: key the wrappers (the pricing page's `key="identity"` and `key="details"` Notices).
- A Retry that hands focus to a text field skips the hand-off when the last press since it took focus was a
  pointer's, since focusing the field after a tap raises the touch keyboard. The press origin is taken at
  pointerdown, which a busy Retry does not swallow. Its click it does: the DS Button's `loading` guard
  refuses it before onClick runs, so a tap on a busy Retry recorded nothing, and the focus that tap started,
  read as a fresh focus, forgot the earlier press. A tap on a Retry busy from a refetch nobody pressed, then
  its unmount, focused the field and raised the keyboard. So `useFocusHandoff`'s `onPointerDown` marks the
  press as a pointer's and the focus it starts keeps that mark; only a focus no pointerdown started (Tab, a
  script) forgets it. A click records its own origin (`e.detail > 0`). A keyboard press, or no press since a
  keyboard focus, hands off, including after a tap the user then left and came back to by Tab.
  `:focus-visible` cannot stand in, because it reflects how the control got focus, not how it was
  activated: a tap on a keyboard-focused button still matches. Limit: a pointerdown that starts neither a
  focus nor a click (a touch scroll begun on the Retry, or a Safari mouse press on a busy one, since Safari
  does not focus buttons on click) leaves its mark for the next focus, so one keyboard focus right after it
  skips the hand-off. That errs toward no touch keyboard.
- A Retry that restarts a stream (SSE), not a query, has no failure to hold, but it is still RetryButton for
  its hand-off: the filing page's "Retry generation" passes the stream's own failure, `{ failed: true, error,
  busy: false, retry }`. Its press clears the error in the render that starts the stream, so the card leaves
  with the press and focus goes to the progress card's heading (`tabIndex={-1}`), in the branch that replaced it.
  That literal is pinned in the gate's ALLOW_HAND_BUILT_FAILURE (d): a hand-built failure for a query would skip
  the hold.
- The other direction (EN-05, 2026-10-07): a card that ends a run the user is waiting on takes focus when it
  appears, only when nobody holds focus. A failed generation usually lands with focus on `<body>` (the page
  generates at load), and the keyboard user then tabbed through the site header to reach the Retry (9 stops
  at 1440px). `useFocusOnArrival(target, shown)` (`hooks/useFocusHandoff.ts`) focuses the card's title
  (`GuidanceCard`'s `headingRef`) after the commit, when focus is on `<body>`; a focused element that commit
  removed (the progress heading) counts as nobody's. Focus in a field or on a link is never moved, nor taken
  from behind an open `aria-modal` dialog the card is not in (a control unmounting inside a dialog drops focus
  to `<body>` too), and a re-render while the card shows never takes it back. The title, not the Retry: a key
  pressed as the card lands (Space to scroll, Enter) must not restart the run. The title is described by the
  card's description (`aria-describedby`), so a screen reader that cuts the live announcement short for the
  focus move still reads why; whether it reads twice needs a real screen reader.
- A fetch is in flight while `fetchStatus !== 'idle'`. A retry paused offline or in a hidden tab is still
  in flight, so `isFetching` alone would release the failure, and the busy state, too early.
- When a retry fails again with the same message, the alert's text is unchanged, so nothing is announced.
  Keying the message node to `errorUpdateCount` re-inserts it. A card whose Retry sits inside its
  `role=alert` needs no key for a press: the "Retrying…" swap back to "Retry" is a text change inside the
  region, and Chromium exposes `role=alert` as atomic and assertive, so the whole alert is presented again
  (FilingFeed review, refuted 2/3 with the accessibility tree). A refetch nobody pressed that fails again
  says nothing new, by design.
- A page-level loading gate over a query its children also observe gates on the retained failure, not raw
  `isLoading`, or the children's mount refetches loop forever:
  `frontend-spinner-gate-on-shared-errored-query.md` (the settings page's `/me` loop), gated by
  `tests/unit/spinnerGateHoldsFailure.spec.ts`.

(h) The scan cannot see post-success flips outside its names, unmounts, or a busy flag under another
name. Those stay per-site specs plus a real-browser keyboard pass. Known open cases, same class, not
yet fixed: the filing page's summary Retry ("Summary temporarily unavailable") and Regenerate Analysis, and
focus after a generation that succeeds (the progress heading a keyboard Retry focused leaves with the run, and
focus falls to `<body>`, where it always ended after a finished generation); FeedbackRow's status
select when the list is filtered by status (its own update removes the row); the dashboard header's
Log out (no in-flight guard); PopularTickerChips' add when the insights refetch after it fails (the
chip goes live again, and with no row to prune it needs the added ticker remembered); YourCompanies'
remove when the insights refetch after it fails (the error card replaces the list and focus falls to
`<body>` with no hand-off); the company page's filings Retry, EarningsCalendarPage's "Try again",
FullTextSearch's Retry and FilingViewer's "Try again" (each pinned in the Retry gate's allowlists, so a
conversion must remove its pins). The scan cannot see how a press was made either: the text-field
hand-off's pointer origin (g) is pinned in `useRetainedFailure.spec.tsx` (a tap on a busy Retry, focused or
not, a tap on the busy Retry's spinner, a tap then Tab away and back, a tap then a keyboard press, a click
that starts no focus) and needs a touch-device pass. Fixed, all on
RetryButton: the dashboard's account, plan and Your companies Retry buttons, FilingFeed's Retry,
CompanySearch's "Try again" (a tap on it busy no longer raises the keyboard when it goes), the pricing
page's three and BillingPanel's two (`busyControls.dashboard.spec.tsx`, `busyControls.watchlist.spec.tsx`,
`CompanySearch.spec.tsx`, `busyControls.forms.spec.tsx`, `busyControls.settings.spec.tsx`,
`useRetainedFailure.spec.tsx`); the filing page's Retry generation and the arrival of its failure card
(`StreamingSummaryDisplay.spec.tsx`, `useRetainedFailure.spec.tsx`, e2e `summary-generation-focus.spec.ts`); and
EmailVerificationModal's Resend (`busyControls.admin-auth.spec.tsx`
plus the e2e `email-verification-resend.spec.ts`). The dashboard's saved-summary Delete and Manage
subscription are fixed too (`busyControls.dashboard.spec.tsx`).

**Evidence**: `frontend/features/calendar/components/AlertBell.tsx` (`disabled={checking}`,
`aria-disabled={pending || undefined}` plus an early return). `tests/unit/calendarBellKeepsFocus.spec.tsx`
fails on the old attribute. Real build, both themes, a bell on the page and one in the day dialog:
focus stays on the bell during and after the request, 8/8; `main` fails 8/8 with focus on `<body>`.
The gate fails on the bell's old `disabled={pending || checking}`, on a new busy-disabled site in an
unlisted file, and on a converted site whose pin was not removed.
The sweep that followed (busyControls.<group>.spec.tsx) pins every converted control's attributes,
its focus through busy and settle, and that a second activation sends nothing; each case fails with
the old native `disabled` restored.
The retry-hardening follow-up (2026-10-04, design C): 35 of its 38 new or inverted page-level cases fail
on the pre-conversion sources (the 3 that pass there are controls: focus elsewhere, a key change, one
batched paused failure). Removing the hold's query identity fails 5 cases; the `errorUpdateCount > 0`
formula alone fails 1; an always-on "Retrying…" fails 2 and a never-on one 1; unkeyed pricing Notices fail
1; the settings page's old spinner gate fails the `/me` bound (11 calls). Real build (React 19 canary), both
themes, 8/8: a keyboard press reads "Retrying…" and lands on the Dashboard title; a reconnect refetch nobody
pressed keeps "Retry" busy and focused, then lands on the title; focus the Retry did not hold is not moved;
the settings page over a `/me` 503 sends 2 calls in ~2 s.
Its review follow-up (same day) killed every surviving mutant, each by at least one case on the fixed code:
the hold's identity, then the pair of counters, without its failure count (both branches, the release branch,
the record branch), and without its failure time (also failing CompanySearch's return to an earlier failed
term); the hand-off
without its `isConnected` check or its `<body>` check; a keyboard re-focus that keeps a pointer mark (in the
hook, or RetryButton without `onFocus`); and the pointer origin gone (the code before it, RetryButton
without `onPointerDown`, a pointerdown that marks no focus or records no press, a click that keeps the mark,
a mark set on an already focused Retry). The gate fails on `disabled={busy}` rendered by RetryButton, on a
fetchStatus busy, an inline `invalidateQueries` press, a label from a same-file const, a hand-rolled Retry
in hooks/, and on each converted file at 026d6df.
Its second review round (same day): the counters-only identity collided across keys (above). With the key in
it, the case "two keys that failed once each in the same millisecond" fails on 44835fe's hook and on the hook
without the key; "a reset of the shown failure's own query" fails on a key-only identity; the query failing
again in the same millisecond with another Error fails without the count; a reset whose refetch fails again
fails without the time; "once data replaced the failure, a later refetch nobody pressed shows no failure"
fails on a release that ignores `status`. The error object no longer takes part in the identity (a failure of
the same query always moves its count or, after a reset, its time). Hand-off killers, each
failing its mutant: a tap on the busy Retry's spinner (a pointerdown checked against `e.target`, not
`e.currentTarget`), a tap on it busy and unfocused then Tab away and back (a focus that keeps the
pointer-focus mark), a tap then a keyboard press (a sticky pointer mark), a pointer press on a Retry whose
target is a heading (the skip without `textField`), and `preventScroll`. The gate fails on a refetch through a
function-declaration handler; the key gate fails on a caller passing a sibling query's key and on CompanySearch
passing the undebounced term.
