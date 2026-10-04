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

**Rule**: A page-level loading gate (`isLoading` or `isPending` swapping the page for a spinner or skeleton)
over a query that its children also observe must not read a refetch of a failure it has already shown as
a first load. Gate it on the retained failure: `if (isLoading && !failure.failed)` with
`const failure = useRetainedFailure(query)` (`hooks/useRetainedFailure.tsx`). The hook holds a failure the
page has shown through any refetch of that query until data replaces it, so the children stay mounted and
their own error UI (BillingPanel's Notice and Retry) answers the second failure. A first load still shows
the spinner. Do not fix it in the children with `retryOnMount: false`: every observer would have to opt
out, and the next child added brings the loop back. The gate is the one place that turns a refetch into an
unmount.

**Evidence**: `frontend/app/dashboard/settings/page.tsx` (`userLoading && !userFailure.failed`). The bound
is pinned in `frontend/tests/unit/busyControls.settings.spec.tsx` ("SettingsPage over a failed account
check"): a non-401 `/me` failure renders the page with the billing Notice after at most 2 `/me` calls in
200 ms, with the real ProfileForm and BillingPanel mounted. With the old `if (userLoading)` gate it sends
11. The spec renders through short `act()` windows: one long `act()` defers every render to its end, so
the loop could not spin and the bound would pass on the broken page. The dashboard's page skeleton gates
on the same retained failures (`frontend/app/dashboard/page.tsx`).
