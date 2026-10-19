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
once the stream ends. A route that awaits other I/O, such as an SEC fetch or a mail send, releases
its session before that await, so no pool slot waits on it. Moving a unit off the loop also ends
the one-at-a-time order the loop gave it within the process: a check-then-write unit (a cap or
duplicate check before an insert, a read-modify-write) holds a lock from its check to its commit, or
writes with an atomic database operation. Take the lock before the session's first query, so no
waiter holds a connection, or after it with no new checkout inside, so no holder waits for a pool
slot that a waiter holds. A lock taken after the first query relies on READ COMMITTED
(PostgreSQL's default and production's): the waiter's check must see the holder's commit.

**Evidence**: `backend/app/routers/filings.py` company, specific, recent, content and fundamentals
read handlers, and the `backend/app/routers/summaries.py` summary read, progress and what-changed
handlers (2026-10: the summary read and its polled progress had been missed and answered 4x500 in
the same burst; each is now one unit in the thread pool). The gate is
`backend/tests/unit/test_cached_filings_pool_lifetime.py`, in two halves. Its parameterized
full-app eight-request, four-slot burst also checks that the dependency's finalizer never finds a
transaction still open and that no listed route makes a checkout on the loop; it covers only the
routes it lists. The peers ranking and the waitlist status and stats reads
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
answered 500 until each route became one unit in the thread pool (2026-10-18, E121). The filings reads
handed their session to `filing_read_service` and `filing_list_service` on the loop, so every read
checked out on the loop and, once the pool was full, froze it for the pool timeout (1 s in #1357's
probe); each is now a unit in the thread pool, the company list's lookup, company
persist, cached and live reads and fallbacks included, and
`backend/tests/unit/test_filings_endpoint_db_first.py` holds the company list's SEC-phase and fallback
paths to no request-session transaction begun on the loop (2026-10-18, E94). The watchlist router's
routes handed their session to services on the loop too: the reads and every refusal left a
transaction for the finalizer, the add, remove and alert toggles ran their statements on the loop
on the connection the auth lookup had checked out, and the waitlist join checked out on the loop and
held a connection through each of its welcome and referral sends, so eight joins on four slots answered
4x200 then 4x500. Each is now a thread-pool unit (the join two: the insert, then the welcome flag
after the send); their burst cases also hold every
statement off the loop, and the join's own case holds both sends to no connection out (2026-10-19,
E118). Its reviews found that five of those units had relied on the loop's order. Without a lock:
- two joins lost a referral credit and took one place;
- two alert enables put an account over its cap;
- two adds, or an add and an enable, wrote two rows for one company;
- two removes both succeeded;
- a disable racing a remove failed on the deleted row.

Each now holds a lock from its check to its commit (2026-10-19, E118's reviews). The gate is
`backend/tests/unit/test_check_then_write_units_serialize.py`:
- it meets two threads inside each unit after their checks, so the race happens without the lock
  however loaded the host;
- it fails any checkout made inside the watch-row lock. The file's AST ratchet reads every async router function and fails a session call on the
loop in its own body above that function's ceiling (on main before the fix it named both summaries
routes). Neither half sees a session handed to a service that runs on the loop where the burst does
not list the route (the rest of the analysis router, E119; the rest of the
auth router and the checkout route, E121), a background task's own session worked on the loop
(E123), or a check-then-write unit other than the four above, such as the refresh token's
rotation (E127), which stays a review check. Local PostgreSQL measurement is separate from production headroom and safe-cohort
evidence.
