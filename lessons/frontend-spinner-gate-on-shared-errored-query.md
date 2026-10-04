# Gate a page's spinner on the retained failure when its children observe the same query

Date: 2026-10-04   Area: frontend

**Context**: A non-401 failure of `/me` (a 5xx, a network error) put the settings page into an unbounded
request loop. `SettingsPage` showed its full-page spinner while the current-user query `isLoading`. When
`/me` failed, the page rendered its sections, and `BillingPanel` and `ProfileForm` mounted. Both observe
the same query, and an observer that mounts over a failed query with no data refetches it
(`retryOnMount`, on by default). The refetch put the query back to `pending` and `fetching`, so
`isLoading` turned true and the spinner replaced the page, which unmounted those children. The refetch
failed, the page rendered, the children mounted and refetched again. In jsdom that was 11 `/me` calls in
200 ms; a browser loops as fast as the API answers. The 401 path never showed it: a 401 resolves to
`null`, which is data.

**Rule**: A page-level loading gate (`isLoading`, `isPending` or `status === 'pending'` swapping the page
for a spinner or skeleton) over a query that its children also observe must not read a refetch of a failure
it has already shown as a first load. Gate it on the retained failure: `if (isLoading && !failure.failed)`
with `const failure = useRetainedFailure(query, queryKey)` (`hooks/useRetainedFailure.tsx`; `queryKey` is the
key the query's own `useQuery` was given). The hook holds a failure the page has shown through any refetch of
that query until data replaces it, so the children stay mounted and their own error UI (BillingPanel's Notice
and Retry) answers the second failure. A first load still shows the spinner. The hold must be a conjunct of
the gate: `!failure.failed` itself beside the loading read under `&&` (parenthesized or nested in another
`&&` is fine), never under `||`, a ternary, a call or a negation, where the gate can still fire with the
failure shown. Never gate a page on `isFetching` (or `isRefetching`, `fetchStatus`) of a shared query, held or
not: a background refetch with data in hand turns it on too, so the gate unmounts the children, and their next
mount can refetch again. Do not fix it in the children with `retryOnMount: false`: every observer would have
to opt out, and the next child added brings the loop back. The gate is the one place that turns a refetch
into an unmount.

Gated (rule 12): `tests/unit/spinnerGateHoldsFailure.spec.ts` reads the AST of every `.tsx` under app/. A
query counts as shared when its key family (the `queryKey` with its call arguments dropped,
`queryKeys.usage.byUser`) is observed by a query hook in at least two modules under app/, components/,
features/, hooks/ and lib/; the scan cannot follow JSX into what a page renders, so that over-approximates
"a child observes it". A gate is `if (cond) return <render>` (either branch) or `cond ? <render> : …`, where a
render is JSX, `null`, a ternary with one in either branch, or a call with JSX among its arguments
(`return wrap(<Spinner />)`), and whose condition reads the loading state of a shared query: `isLoading`,
`isPending`, `isInitialLoading`, or `status` compared with `'pending'` (either side, any equality). Read as a
member, destructured (renamed or not), through same-file consts, or through a same-file hook's returned object
(the watchlist page's `useAuthGate`). It fails unless an enclosing `&&` has `!failure.failed` as a conjunct,
with `failure = useRetainedFailure(<that same query>, …)`. A condition that reads `isFetching`, `isRefetching`
or `fetchStatus` of a shared query fails held or not. Kept sites are pinned as `condition [families]` (the
condition's text and the shared families it reads, so a pinned condition that starts reading another shared
family fails), shrink-only and capped, each with its reason (5 in 4 files: the admin layout, the watchlist
page and the delete-account page render no observer over a failed `/me`; the filing page's two summary-pane
branches swap only components that observe no shared query). It cannot see a key built outside a `queryKey:`
property, a loading state passed through props, a hold read through an alias (`const ok = !failure.failed`),
a gate inside a component under features/ or components/, or a `!isLoading && <Panel />` that unmounts a
panel instead of replacing the page; review still reads those.

**Evidence**: `frontend/app/dashboard/settings/page.tsx` (`userLoading && !userFailure.failed`). The bound
is pinned in `frontend/tests/unit/busyControls.settings.spec.tsx` ("SettingsPage over a failed account
check"): a non-401 `/me` failure renders the page with the billing Notice after at most 2 `/me` calls in
200 ms, with the real ProfileForm and BillingPanel mounted. With the old `if (userLoading)` gate it sends
11. The spec renders through short `act()` windows: one long `act()` defers every render to its end, so
the loop could not spin and the bound would pass on the broken page. The dashboard's page skeleton gates
on the same retained failures (`frontend/app/dashboard/page.tsx`). The gate fails on the settings page's
old `if (userLoading)` (a case reads the real file and restores the old line), on the dashboard skeleton
gate without its user hold, and on its usage hold read from the subscription's failure. Its second review
round (same day) made the hold conjunct-only: the old scan accepted a `!failure.failed` anywhere in the other
`&&` operand, so `userLoading && (!userFailure.failed || !user)`, `userLoading && !(!userFailure.failed)`, a
hold in one ternary branch and a hold under `||` all passed; each is now an expected offender in the fixture,
and the settings page with either of the first two fails. Pinning `condition [families]` caught a watchlist
`useAuthGate` that folds the usage query's loading into the pinned `isReady`, which the condition-only pin
let through. New pages gated on `isFetching` (held or not), `status === 'pending'`, a call around the JSX and
a ternary in the return each fail, with no new offender on the tree.
