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
(PostgreSQL's default and production's): the waiter's check must see the holder's commit, so it
reads the database under the lock (a column query, or `populate_existing()`: an entity query hands
back an already-loaded object unchanged), not an attribute loaded before it (checkout's customer
check reads the id the auth lookup loaded, E166).

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
The contact form handed its session to `persist_contact_submission` on the loop, and the feedback
submit committed and refreshed its row in its own body, so each held a connection through its mails:
eight contact messages on four slots, each mail taking 0.3 s, answered 4x201 then 4x500, and eight
feedback reports answered 8x201 but left every transaction for the finalizer. Each is now one
thread-pool unit, the insert and the response it echoes, released before its first mail; their burst
case holds every statement off the loop, and a single submit sends each mail with no connection out
(2026-10-23, E144).
The usage and subscription-status routes read their counts, the reader's subscription row and the
plan the entitlements derive from it through services on the loop, on the connection the auth lookup
had checked out: eight readers on four slots answered 8x200 with all eight transactions left for the
finalizer. Each is now one thread-pool unit, and their burst case holds every statement and every
release off the loop and each reader to their own payload, with and without a subscription row
(2026-10-23, E144).
The pool-lifetime file's AST ratchet reads every async router function and fails a session call on the
loop in its own body above that function's ceiling (on main before the fix it named both summaries
routes). Neither half sees a session handed to a service that runs on the loop where the burst does
not list the route (the rest of the
auth router, E121, and checkout, E144), or a background task's own session worked on the loop
(E123 moved the company list's units into the thread pool, `test_filings_endpoint_db_first.py`'s
off-the-loop cases; the flag-off job runners are E150), which stays a review check. Local PostgreSQL measurement is separate from production headroom and safe-cohort
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

Those locks reach one process, and the API runs up to two instances, across which the five races stayed
open. Since E128 each unit also takes, before its check, a lock in the database that every instance
shares, and holds it to the commit that carries its write. The watch-row writes take the account's users
row lock (`watchlist_service.lock_watch_rows`, FOR NO KEY UPDATE, as the refresh token's writers do)
before the process lock. That lock serves every account: a unit that waited on one account's row inside
it, behind a Stripe delivery's read say, stalled every other account's writes on the instance, and with
the auth lookup's connection each waiter holds, three such waiters and the stalled unit filled the
instance's four-slot pool. The join takes the waitlist's place lock, a transaction-level advisory lock,
since no row is common to every join (`waitlist_service._lock_waitlist_places`), inside its process lock,
which a waiter takes before its first query and so waits on holding no connection. Its place is one past
the highest held, so no two signups on the list share one even after a deletion, and its credit one
UPDATE that adds to the stored score. The process locks stay: under SQLite they are the only serialization.
`backend/tests/unit/test_check_then_write_units_lock_across_instances.py` holds each lock from before its
unit's first read to the commit of its write, as statements compiled for PostgreSQL, the watch-row lock
outside the process lock and the reads beside them taking no lock, and the credit to one that a
concurrent commit cannot lose. No CI step races two instances on PostgreSQL. The pull request's local run
did, with a process lock per thread for each instance: two enables at the cap, two adds, two removes, a
disable against a remove, an add against an enable, and two joins with and without a link. It also timed
other accounts' adds while one account waited on a held row.

A company's filing writers were next (E123's review). Each read which of the company's filing rows
existed before the company row lock that serialized their inserts, so two writers of one company could
both find a filing missing, and the second insert failed the unique accession and rolled back its batch.
Once E123 moved the list's background refresh and the history backfill into the thread pool, two of
them could meet in one process, where the loop had run them one at a time. The live listing's unit, in
the thread pool since E94, already could, and worse: it flushed its inserts and URL rewrites before it
took the lock, the reverse of the other writers' order, so on PostgreSQL it could deadlock with one of
them, across processes too (an API request and the durable worker), and the loser lost its rows. Every
writer (the scan's `upsert_filings`, which the refresh, the backfill and the durable worker write
through; the live listing's `persist_live_filings`; `precompute_one`) now takes that row lock before it
reads or writes a filing row (`filing_amendment_service.lock_company_filings`), which reaches every
process and instance (2026-10-21). It serializes one company's writers only: a filing listed under two
companies, a co-registrant filing, is checked under two locks, so two writers of the two companies
could both find it missing, and the second insert failed (Codex on #1483). Since E153 a writer that
finds an accession missing also takes the filing-insert lock after its company's, a transaction-level
advisory lock that every inserting writer shares, and reads the missing accessions again before it
inserts (`filing_amendment_service.existing_filings_for_insert`), so a writer that waited there inserts
only what is still missing. One lock serves every accession: a first listing or a history backfill
inserts hundreds of rows, and a lock apiece would hold as many entries of PostgreSQL's shared lock
table. A writer with nothing to insert takes no lock, and one that takes it ends its transaction soon
after (its commit, or its caller's commit or close), with no network call between. SQLite omits both
locks, so `backend/tests/unit/test_filing_writers_lock_before_they_check.py` reads each writer's
statements, compiled for PostgreSQL: a lock that waits, then the check, with no end of a transaction
between them; `backend/tests/unit/test_filing_inserts_lock_across_companies.py` reads the insert lock
after the check, the second read and the commit, runs the race in one thread, and holds every builder of
a filing row under `app/` to the three writers. On PostgreSQL,
`backend/tests/integration/test_filing_insert_transactions.py` races two companies' writers of shared
filings, each held after its check: the scan's against the scan's, the live listing's against the scan's,
and a backfill-sized scan against a one-row one. Each race runs with either writer holding the insert
lock, kept there until PostgreSQL shows the other waiting for it, beside a control without the lock whose
second writer fails its batch. `precompute_one`'s writer is raced only by the one-thread case above
(E161).

The refresh token's rotation was one more. It read its token, checked it live, minted a successor and
marked the token rotated, so two refreshes with one cookie both minted, and a refresh racing a logout or
logout-all left a live successor. That race also spans the API's two instances, which no process lock
reaches. Every rotation and revocation of a user's tokens (a refresh, logout, logout-all, the theft
sweep, a password change or reset) now takes the account's users row lock and re-reads under it, and a
logout that finds its token already rotated away revokes its chain's live tip. A guarded UPDATE
alone would not have served: logout-all's bulk UPDATE sees only rows committed when it starts, so a
successor committed after that survives it. The account's deletion takes the lock first too: its cascade
deletes the tokens before the account, so in the other order it deadlocked with a token writer
(2026-10-19, E127). `backend/tests/integration/test_refresh_rotation_transactions.py` runs each order
on PostgreSQL in CI's migrations-postgres job, holding the first request's commit until the second is
blocked on a lock or has finished; on the old code every case that races two token writers fails. Its
requests use production's `SessionLocal` settings, autoflush off. In an autoflushing session a password
reset flushed its users UPDATE before its bulk revoke and waited there for a racing refresh, which hid a
mutant that moved the lock out of the revocation. Since E132 every PostgreSQL gate opens its sessions
that way (`lessons/test-a-postgres-gate-opens-production-sessions.md`), and its step fails when its
cases skip (`lessons/test-a-step-fails-when-its-gated-cases-skip.md`). A sign-in's new token takes no
lock. A password login now mints under it, and a password change writes under it,
each only while the hash it verified is still the account's: a login that verified the old password
before a reset committed used to mint after it, and such a change to overwrite the reset's password and
keep a session of its own (E121). Any other check-then-write unit stays a review check.
