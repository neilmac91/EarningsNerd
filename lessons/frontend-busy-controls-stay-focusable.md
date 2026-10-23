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
handler is left to the label clause. By its label: any element but RetryButton whose `loadingText` (or
`reserveLoadingText`, the busy text whose room a button keeps at rest) starts "Retrying" or "Trying again" or
whose label (its text, or a `children` attribute) starts "Retry" or "Try again", a same-file string const
(`{retryLabel}`) included. RetryButton's own
definition is the one exemption from both Retry clauses, by file and function name (it is the sanctioned wiring
and label); a function of that name anywhere else is just another hand-rolled Retry. Each has a shrink-only, capped allowlist with reasons: ALLOW_RETRY pins 1 wiring site
in 1 file (the `loading` of "Show full history", the filings query's fetching flag on a button that is not a
Retry; the calendar's and full-text search's Retry handlers became RetryButton in #1301), ALLOW_RETRY_LABEL
6 labels in 6 files (4 error-boundary resets and 2 stream restarts, the stored summary's and an Ask answer's,
each pinned as "Try again" since E44).
Every Retry the retry-hardening follow-up
converted fails both clauses at its 026d6df version (20 wiring and 10 label offenders in 6 files). A third
clause (EN-05) checks what RetryButton is given: each element of its `failures` is `useRetainedFailure(…)` (the
hook its module exports, under any name an import gives it; a same-named local or a shadowing parameter is not it),
inline, through a same-file `const` or either branch of a conditional, or, when it is a prop of the component
rendering RetryButton, at every JSX use of that component (by its declared name in its own file, by any
imported name elsewhere; a prop nobody passes fails), or destructured from what a hook in another module returns
(ComparePeriodsCard's `const { failure } = useWhatChanged(id)`, renamed or not: the hook is a named import, its
module is read from disk, and every own `return` of that export is an object literal whose property is retained
there by the same rules, so one hook may hand on another's and a cycle fails; a default value, a nested, rest or
array pattern, a `let`, a member read, a default import, an export list, a bare `return`, a returned literal that
spreads another object, a module the scan cannot read or one that exists as both `.ts` and `.tsx` counts as built
by hand). RetryButton is matched under any name an import of its module gives it too (an alias, a default
import, `H.RetryButton` under `import * as H`). What
the scan cannot prove counts as built by hand: a `let`, a spread element, an empty list (a visible Retry whose
press retries nothing), any JSX spread on RetryButton (a
forwarding wrapper) or into such a component. A failure built by hand skips the hold and can carry
`busy: isFetching`: ALLOW_HAND_BUILT_FAILURE pins it by its text (1 site, the filing page's stream restart),
capped; converting another stream restart moves its pin there from ALLOW_RETRY_LABEL. The one retry verb
(docs/brand/decisions-log.md D-032; E44) is two more clauses in the same file. On controls: a RetryButton call
site that passes a label of its own fails (a child, a `children`, `aria-label` or `aria-labelledby` attribute,
or a JSX spread it cannot read), and so does a use of RetryButton the scan cannot follow (its name anywhere but
a JSX tag, an import or a type, such as an alias or a createElement argument; an `export *` or `import()` of
its module). That clause is one of three holds on the label. TypeScript refuses each label prop (children,
aria-label, aria-labelledby) at a call site because RetryButtonProps declares it `never`, which the gate checks:
leaving a name out of the props would not do, since JSX never checks an undeclared hyphenated attribute such as
aria-label. RetryButton drops all three at run time, for one a spread or a cast brings in
(useRetainedFailure.spec.tsx renders each and finds the name "Try again"). Any other retry control fails,
RetryButton's own definition included with no exemption, when its label (its text, or a `children` attribute) is
not exactly "Try again", its busy text (shown or reserved) is not exactly "Trying again…" (U+2026) or its text
starts "Retry"; a part of a retry control the scan cannot read (a parameter, a `let`, a call, a template with a
substitution, an aria-labelledby, whose name is another element's text) fails as unread, a template's text before
its first substitution still marking its control a retry (an icon-only Button's ``aria-label={`Try again for
${name}`}``), and RetryButton's definition must reserve the busy text it shows. On copy: every string, template
text and JSX text in the .ts and .tsx modules under the same roots is read, and "retry", "retrying", "retries" or
"retried" fails, outside console calls, imports, object keys, string types, code attributes and the header name
Retry-After; ALLOW_RETRY_WORD pins, with reasons and caps equal to the list, the two backend tokens the app
matches and never shows (PLACEHOLDER_PATTERNS' "retry" and SUMMARY_FALLBACK_MESSAGE). Its limit, planted as a gap:
a word split across JSX text and an expression (`Please re{''}try`) is read a part at a time, so neither clause
sees it.

(e) A control unavailable after its own activation (`!dirty` after a save, an incomplete form, a
cooldown, "Link sent") is aria-disabled with an early return too. A primary DS Button in that state
takes `primaryUnavailableClass`, a secondary one `secondaryUnavailableClass`, and a field
`fieldUnavailableClass` (all in `components/ui`), for the disabled look without native `disabled`.
Never `loading`'s look: that stays the resting fill. `secondaryUnavailableClass` fades the label and
the hairline, not the element: the variant's native `opacity-50` would fade the focus ring the
focusable state still shows (EmailVerificationModal's Resend, measured in Chromium). The same holds for
every hand-rolled look, busy or unavailable: no element `opacity` on an aria-disabled control. Fade
what it draws in (its label's ink, its hairline, a switch track's fill) on the tokens it already uses,
in both themes, or a child (`group-aria-disabled:opacity-50`); only a natively disabled state, which
cannot hold focus, keeps `disabled:opacity-*`. The eleven sites that faded the element (ten on
`aria-disabled:opacity-*`, AlertBell on a class its busy flag picked) were converted on 2026-10-10: the
brand ring on panel went from 1.37:1 back to 1.97:1 in light and from 1.68:1 to 2.87:1 in dark, and
the browser's own outline on the five controls with no ring recipe faded the same way. Gated (rule 12):
`tests/unit/ariaDisabledKeepsItsRing.spec.ts` reads the AST of every .ts and .tsx under app/,
components/, features/, hooks/ and lib/ and fails on an `opacity-*` class behind the element's own
`aria-disabled:` variant, wherever the class list is written, and on any other `opacity-*` class on a
control, except behind `disabled:`. A control is an element that carries `aria-disabled`, or a use of
a shared control: a component that renders one with the caller's className, given a prop that makes it
aria-disabled (`<Button loading>`; every use of RetryButton and AlertBell). It reads what the
className's names hold (a const, a function's body) across imports and a barrel's re-exports, so a
shared class list is held to the rule at each control that takes it. No allowlist.

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
(`window.location` to Stripe for Manage billing, BillingPanel's and the dashboard's) stays pending until the page
goes. Its `onSuccess` returns `untilPageReturns()` (`lib/untilPageReturns.ts`). That settles on
`pageshow`, so a back-forward restore brings the button back live. It also settles on the Navigation
API's `navigateerror`, which Chromium fires when the user aborts the pending navigation with Esc or
Stop. A fixed timeout cannot tell an aborted navigation from a slow one, so it is only the fallback
where that API is missing (Codex P2 on #1075). A success that unmounts the control itself (Sign out everywhere's `queryClient.clear()` skeleton)
needs neither. Audit every `onSuccess` of a control this sweep keeps focusable. Hosted Codex found
four of these in later review rounds, after the sweep had shipped them fire-and-forget.

(g) A control that unmounts as a result of its own activation (a row removed on success, Save replaced
by a "Saved" label) hands focus to a stable target: a heading or status line with `tabIndex={-1}`, focused
with `{ preventScroll: true }`. A layout whose pages own its heading hands it to the landmark it renders
first: the admin layout's account card gives way to the section's `<nav tabIndex={-1}>`, since each admin
page writes its own h1 below it (`app/admin/layout.tsx`). A Retry whose success renders content in its
place hands focus to that content's container: TurnstileWidget's Try again gives way to the security
check, a group named "Security check" with `tabIndex={-1}` (E152). Two forms are accepted: before the
unmount, only
when the control holds focus (`document.activeElement === e.currentTarget`), or after it, only when focus
fell to `<body>`. Never move focus a mouse user did not lose.
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
  so a later background refetch over loaded data never shows the old error. Placeholder data is the one
  exception (#1301): a query with `placeholderData` (the search's `keepPreviousData`) reports a refetch of
  its held failure as `status: 'success'` with `isPlaceholderData`, carrying the previous key's data while it
  has none of its own. So while a failure is held, a placeholder-backed result counts as `pending`: the error
  UI and its focused Retry stay up, busy, and only the query's own data ends the hold. Read raw, the
  placeholder ended the hold and unmounted the focused Retry for the previous search's hits
  (`useRetainedFailure.spec.tsx` and `full-text-search.spec.tsx` pin it). A caller without `placeholderData`
  never sees `isPlaceholderData`, so nothing changes for it. A first load is never held, nor
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
  the hand-off above. Its label is "Try again", the one retry verb (D-032), and RetryButton's own, so a call
  site passes none. It reads "Trying again…" only while its own press's retry runs, and keeps that label's room
  (with the spinner's) at rest, Button's `reserveLoadingText`, so the swap never resizes it or moves what sits
  beside it (e2e `filing-source-chip.spec.ts` holds the box; chief design kept the reserve on 2026-10-17, D-032).
  That room must never cost reflow, and a reserved Retry is wider than its label, so its family is every place a
  retry control sits, each checked at 320, 360 and 390px under 200% text, at rest and busy. The Retry takes its own
  row under its message, as a Notice's action does, never a place beside its message or another control in a row
  that cannot wrap; a card's two actions wrap (GuidanceCard's action row, global-error's); a message carrying the
  backend's words breaks a long token; and the reserve's rows wrap, the label based at its longest word, so a
  cramped Retry sets its spinner above its label instead of growing past "again…" beside the spinner. Found that
  way on #1380: the homepage search alert (the reserve's narrow minimum, the spinner, the gap and "again…", 178px,
  left its message too little of the row: at rest the Retry ran 87px past the alert, the page 445px at 390px), the
  full-text search alert (Codex: the page 472px, 848px with a long token), the dashboard's account card (Try again
  beside Go to login, the Retry's left edge off the screen at 320px), the route, dashboard and root error fallbacks
  (two actions past the card or the screen at 320px), and the company page's comparison card (a Notice in a card:
  the page 326px at 320px). Gates: `tests/e2e/reflow-200.spec.ts` ("a failure's controls stay inside their card",
  the full-text search alert on /search included), `full-text-search.spec.tsx` (that alert's layout),
  `twoActionsWrap.spec.tsx` and `button-wrap.spec.tsx`.
  A Notice's row wraps, its text column going under the glyph where it cannot keep 9rem beside it, so a Notice
  inside a card keeps its Retry and its title inside its own border (reflow-200 holds three such cards). At 320px
  under 200% text a `p-6` card (billing, ticker filings, the admin lists) left a Notice a 92px content box, narrower
  than the Retry's narrowest state (138px), so the Retry ran past the Notice's border there, inside the card; since
  E120 a surface's inset stops growing at narrow widths (`p-cap-6`, 19.2px a side there), the Notice keeps 150px and
  reflow-200 holds the billing and ticker filings cards to it at 320px too. During a refetch nobody
  pressed it is busy (aria-busy, aria-disabled, the spinner, a refused press) under its own label: a label
  swap inside the card's `role=alert` would re-announce the failure at every reconnect. Two failed reads in one
  Notice share one RetryButton (the dashboard's plan strip, the pricing page's details Notice): its press
  retries the ones that failed, and two buttons with one label could not say which read each retries.
- One RetryButton instance never serves two error UIs. React reuses an unkeyed element in the same slot, so
  when one Notice replaces another in a single render the focused node stays, still pressed or busy, and never
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
  its hand-off: the filing page's generation restart passes the stream's own failure, `{ failed: true, error,
  busy: false, retry }`. Its press clears the error in the render that starts the stream, so the card leaves
  with the press when the run starts and focus goes to the progress card's heading (`tabIndex={-1}`), in the
  branch that replaced it. The card offers the Retry only for a failure a retry can help
  (`isNonRetryableStreamError`, which also stops the stream's automatic retry), so a signed-out press, which
  starts no run and leaves a sign-in sentence, keeps the card and drops its Retry: focus then goes to the
  card's own heading, the target's fallback.
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
  `role=alert` needs no key for a press: the "Trying again…" swap back to "Try again" is a text change inside the
  region, and Chromium exposes `role=alert` as atomic and assertive, so the whole alert is presented again
  (FilingFeed review, refuted 2/3 with the accessibility tree). A refetch nobody pressed that fails again
  says nothing new, by design.
- A page-level loading gate over a query its children also observe gates on the retained failure, not raw
  `isLoading`, or the children's mount refetches loop forever:
  `frontend-spinner-gate-on-shared-errored-query.md` (the settings page's `/me` loop), gated by
  `tests/unit/spinnerGateHoldsFailure.spec.ts`.

(h) The scan cannot see post-success flips outside its names, unmounts, or a busy flag under another
name. Those stay per-site specs plus a real-browser keyboard pass. Known open cases, same class, not
yet fixed: the filing page's summary Retry (the stored-failure card, "This summary did not finish") and Regenerate Analysis; FeedbackRow's status
select when the list is filtered by status (its own update removes the row); PopularTickerChips' add when the
insights refetch after it fails (the chip goes live again, and with no row to prune it needs the added ticker
remembered); YourCompanies' remove when the insights refetch after it fails (the error card replaces the list
and focus falls to `<body>` with no hand-off). The scan cannot see how a press was made either: the text-field
hand-off's pointer origin (g) is pinned in `useRetainedFailure.spec.tsx` (a tap on a busy Retry, focused or
not, a tap on the busy Retry's spinner, a tap then Tab away and back, a tap then a keyboard press, a click
that starts no focus) and needs a touch-device pass. Fixed, all on
RetryButton: the dashboard's account, plan and Your companies Retry buttons, FilingFeed's Retry, the
company page's filings Retry (`FilingIndex.spec.tsx` for the control, `busyControls.watchlist.spec.tsx` for the
hold through its retry and the hand-off to the "SEC filings" heading; its pins removed from the Retry gate in #1147),
the company page's company Retry (`company-page-lead.spec.tsx`: the card and its busy, focused Retry held through
the retry instead of the page spinner, then the hand-off to the "SEC filings" heading, the not-found title on a 404,
or the coverage card's title for an unsupported issuer; a 404 card held through a background refetch, #1292),
CompanySearch's Retry (a tap on it busy no longer raises the keyboard when it goes), the pricing
page's two (the account check's, and since E44 one over both detail reads) and BillingPanel's two
(`busyControls.dashboard.spec.tsx`, `busyControls.watchlist.spec.tsx`, `CompanySearch.spec.tsx`,
`busyControls.forms.spec.tsx`, `busyControls.settings.spec.tsx`, `useRetainedFailure.spec.tsx`); FilingViewer's
Retry (#1271, `FilingViewerEmbedded.spec.tsx` and e2e `filing-source-chip.spec.ts`), the calendar's and
FullTextSearch's (#1301, `full-text-search.spec.tsx`); the filing page's generation restart and the arrival of its failure card
(`StreamingSummaryDisplay.spec.tsx`, `useRetainedFailure.spec.tsx`, e2e `summary-generation-focus.spec.ts`); the completed-generation arrival in the persistent filing shell (first summary heading, only after a run, preserving held focus and modal ownership; the same e2e); and
EmailVerificationModal's Resend (`busyControls.admin-auth.spec.tsx`
plus the e2e `email-verification-resend.spec.ts`). The dashboard's saved-summary Delete and Manage
billing are fixed too (`busyControls.dashboard.spec.tsx`), as is its header's Log out, unavailable while its
logout runs and available again after one that did not take (#1496, `failedLogoutChecksSession.spec.tsx`),
and Watchlist insights' Retry keeps its error card, busy and focused, through its refetch
(`summaryStatusCopy.spec.tsx`). The admin invites and
feedback list Retry buttons hold their Notice through the retry and hand focus to the "Invites" or
"Feedback" list heading (`busyControls.admin-auth.spec.tsx`).

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
the settings page over a `/me` 503 sends 2 calls in ~2 s. (Those runs read the labels of their day; since E44
the words are "Try again" and "Trying again…", and the same page specs assert them.)
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
