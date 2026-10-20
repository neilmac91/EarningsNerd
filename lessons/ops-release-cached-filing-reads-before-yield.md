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
E118). The analysis router's other routes did the same: coverage looked its company up on the loop
and, after the companyfacts wait, checked a fresh connection out there for its period reads, so
eight coverage reads on four slots answered 500 to two, three and four of them in three runs; the
dataset route built its dataset (reads and CPU work) on the loop; and the xlsx and PDF exports held
their transaction through the render. Each is now a thread-pool unit (coverage two: the lookup, then
the reads after the wait), released before any wait or render that follows; their burst cases hold
every statement off the loop, the first-touch handoff to the queue included, and a single export
renders with no connection out (2026-10-19, E119). The companyfacts sync the coverage route runs
as a task on the loop read freshness, re-read a follower's stamp and persisted every fact there. Each
unit now runs on the sync's own threads (`lessons/ops-auth-lookups-must-let-request-cleanup-progress.md`
says why not the default executor); the leader claims the sync before its read, so a request arriving
meanwhile follows it; a leader cancelled during its persist keeps its claim until the persist ends;
and the burst's `coverage_sync` row runs `ingest_companyfacts_by_id` itself, only its SEC fetch faked,
with its sessions off the loop (2026-10-19, E129).
The pool-lifetime file's AST ratchet reads every async router function and fails a session call on the
loop in its own body above that function's ceiling (on main before the fix it named both summaries
routes). Neither half sees a session handed to a service that runs on the loop where the burst does
not list the route (the rest of the
auth router and the checkout route, E121), or a background task's own session worked on the loop
(E123), which stays a review check. Local PostgreSQL measurement is separate from production headroom and safe-cohort
evidence.

E118's reviews found that five of its units had relied on the loop's order. Without a lock:
- two joins lost a referral credit and took one place;
- two alert enables put an account over its cap;
- two adds, or an add and an enable, wrote two rows for one company;
- two removes both succeeded;
- a disable racing a remove failed on the deleted row.

Each now holds a lock from its check to its commit (2026-10-19). The gate is
`backend/tests/unit/test_check_then_write_units_serialize.py`. It meets two threads inside each unit
after their checks, so without the lock the race happens however loaded the host, and it fails any
checkout made inside the watch-row lock. It covers those five units only.

The refresh token's rotation was one more. It read its token, checked it live, minted a successor and
marked the token rotated, so two refreshes with one cookie both minted, and a refresh racing a logout or
logout-all left a live successor. That race also spans the API's two instances, which no process lock
reaches. Every rotation and revocation of a user's tokens (a refresh, logout, logout-all, the theft
sweep, a password change or reset) now takes the account's users row lock and re-reads under it, and a
logout that finds its token already rotated by a racing refresh revokes the successor. A guarded UPDATE
alone would not have served: logout-all's bulk UPDATE sees only rows committed when it starts, so a
successor committed after that survives it. The account's deletion takes the lock first too: its cascade
deletes the tokens before the account, so in the other order it deadlocked with a token writer
(2026-10-19, E127). `backend/tests/integration/test_refresh_rotation_transactions.py` runs each order
on PostgreSQL in CI's migrations-postgres job, holding the first writer's commit until the second is
blocked; on the old code every token case fails. A sign-in's new token takes no lock, so a login that
verified the old password before a reset committed still mints after it (E131). Any other
check-then-write unit stays a review check.
