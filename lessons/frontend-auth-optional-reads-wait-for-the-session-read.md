# A per-viewer read served by an auth-optional endpoint waits for the session read and has one owner

Date: 2026-10-13   Area: frontend

**Context**: `GET /api/summaries/filing/{id}/what-changed` reads the user optionally
(`get_current_user_optional`): an anonymous or Free reader gets the teaser, a Pro reader the full
wording-change list, and an expired access token reads as anonymous. The client refreshes a token
only on a 401 (`lib/api/client.ts`), so a Pro reader back after an hour was served the teaser with
a 200, nothing in that response refreshed anything, and the page kept the teaser under the one
`['what-changed', id]` key everyone shared. The review round then found two more shapes of the
same fault: a cached, still-fresh `/me` makes no request, so the report read went out with the
stale token anyway; and a signed-in reader's failed read dropped the anonymous seed the page had
rendered (`placeholderData` applies only while a query is pending).

**Rule**: a read whose answer depends on who is asking carries the signed-in reader's id in its key
(anonymous readers share one entry, which the page's server read seeds), is issued only once `/me`
has settled and is not being re-read (that request is the one that refreshes a token), and treats a
Pro reader served the teaser as a stale token: re-read `/me`, then the report, once per entry, and
let a second teaser stand. While the seed stands in for a signed-in reader, hold it `provisional`:
no event is counted against it, no upgrade prompt is shown for it, and a failed own read keeps it
in place. Put all of that in ONE hook and read through it everywhere; a second `useQuery` on the
same endpoint carries none of it.

**Evidence**: `frontend/features/summaries/hooks/useWhatChanged.ts` and
`frontend/tests/unit/useWhatChanged.spec.tsx` (the cold, re-read and fresh-cached `/me` cases, the
failed read, the seed). Partly gated: `frontend/tests/unit/whatChangedReadOwner.spec.ts` keeps
`getWhatChanged` and `queryKeys.whatChanged.byViewer` inside the hook; the next auth-optional
endpoint is review-checked against this rule.
