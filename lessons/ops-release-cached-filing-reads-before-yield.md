# Release completed filing reads before yielding to dependency cleanup

Date: 2026-09-29   Area: ops

**Context**: Eight concurrent cached filing-list requests exhausted a four-slot PostgreSQL pool.
Four completed reads remained idle in transaction while subsequent synchronous checkouts blocked
the event loop; the asynchronous wrapper around the sync dependency could not run its finalizer.
The same failure reproduced in the full application and an actual local Uvicorn HTTP server.
Separate actual-HTTP checks reproduced it for specific filings, recent filings, content and
filing fundamentals, including existing filings with empty content or facts.

**Rule**: Filing read routes materialize response DTOs or primitive payloads and close their
sessions in the same synchronous unit, including cached, live, fallback, empty and missing reads. Do not leave completed reads for
the sync dependency's thread-pool finalizer, or increase the pool to hide the blockage. Keep the
dependency finalizer as a final safety net, and retain scalar identities for any later work. In an
async route the unit is a sync function handed to `run_in_threadpool`, and the route's own body makes
no call on its session: a service called with the session on the loop checks out on the loop just as
the route's own call does, and freezes it for the pool timeout once the pool is full. A route that
returns a `StreamingResponse` releases its session before it returns, since the finalizer runs only
once the stream ends.

**Evidence**: `backend/app/routers/filings.py` company, specific, recent, content and fundamentals
read handlers, and the `backend/app/routers/summaries.py` summary read, progress and what-changed
handlers (2026-10: the summary read and its polled progress had been missed and answered 4x500 in
the same burst; each is now one unit in the thread pool). The gate is
`backend/tests/unit/test_cached_filings_pool_lifetime.py`, in two halves. Its parameterized
full-app eight-request, four-slot burst also checks that the dependency's finalizer never finds a
transaction still open and that the summaries, peers and waitlist routes make no checkout on the
loop; it covers only the routes it lists. The peers ranking and the waitlist status and stats reads
handed their session to a service on the loop and answered 500 in that burst until each became one
unit in the thread pool (2026-10-17); the analysis stream, at its cap, streamed with its cached-range
read's transaction still open, which its own case in the file holds to zero connections out while
the body streams. The generate stream's Pro force branch committed its clears and then read the user
and the filing; the commit had expired both, so each read refreshed its row with a checkout on the
loop (`lessons/arch-one-summary-orchestrator.md` keeps the stream's reads off expired fields). It
reads them before the commit now, and its own case in the file holds the force path to one
checkout, in the thread pool (2026-10-17, E104). The logout, logout-all and refresh routes handed
their session to services on the loop: a revoke that found no live token kept its read open, the
audit write read its row back after its commit, and the refresh read the user its rotation had
expired, so each left a connection for the finalizer, and two of the five rows of their burst case
answered 500 until each route became one unit in the thread pool (2026-10-18, E121). The file's AST ratchet reads every async router function and fails a session call on the
loop in its own body above that function's ceiling (on main before the fix it named both summaries
routes). Neither half sees a session handed to a service that runs on the loop where the burst does
not assert the route's checkouts (the filings reads, E94) or does not list the route (the rest of the
watchlist and analysis routers, E118 and E119; the rest of the auth router and the checkout route,
E121), which stays a review check. Local PostgreSQL measurement is separate from production headroom and safe-cohort
evidence.
