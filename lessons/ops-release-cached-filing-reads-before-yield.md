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
back an already-loaded object unchanged), not an attribute loaded before it
(`lessons/arch-store-a-stripe-customer-only-while-the-account-has-none.md`, E166).

**Evidence**: `backend/app/routers/filings.py` company, specific, recent, content and fundamentals
read handlers, and the `backend/app/routers/summaries.py` summary read, progress and what-changed
handlers (2026-10: the summary read and its polled progress had been missed and answered 4x500 in
the same burst; each is now one unit in the thread pool). The gate is
`backend/tests/unit/test_cached_filings_pool_lifetime.py`, in three parts. Its parameterized
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
Stripe checkout and the billing portal called Stripe synchronously on the loop, each call blocking it,
and held a pooled connection across those calls: the auth lookup's, and in checkout, once a new
customer's claim had committed, the one its read-back opened, which the user's reload and the trial's
subscription check then used. Eight checkouts on four slots, each Stripe call taking 0.3 s, answered
4x200 and 4x500 (pool timeouts), with a stored customer or without one, and so did eight portal
sessions. Each route now reads what it needs in one thread-pool unit, released before its first Stripe
call; checkout's claim of a new customer, and its trial's row check after the customer step as before,
are units of their own; and every Stripe call runs off the loop, on the Stripe threads since E170. Their burst case holds every statement, release and Stripe call off the loop and each new
customer to its own account, and a single request makes each Stripe call with no connection out
(2026-10-23, E144).
The company lookup, the search and the trending list, all public, ran their units on the loop between
their SEC and Yahoo awaits, each released before the next await: eight readers of each answered as they
should, but with every checkout and statement on the loop (13 of 13 statements for eight lookups of a
new company, 24 of 24 for eight searches of a stored one). Each unit now runs in the thread pool and
releases in a `finally`. Off the loop, eight lookups or eight searches of one new company race for its
row, as two instances always could: the unique CIK decides, and each loser serves the stored row through
the resolver's recovery or the search's. Two searches writing the same companies in different orders did
worse: on PostgreSQL they deadlocked, and the one PostgreSQL aborted answered 500 after the deadlock
timeout. One local probe held two searches of the same two new companies, in opposite orders, behind a
third transaction's uncommitted insert of the two rows, which then rolled back: 11 of 20 runs deadlocked.
Another held a search's batch, which updated a stored row before inserting a new company with a lower
CIK, against a second search's conflict recovery, which wrote the two in CIK order: 6 of 10. The probes
line the two units up behind a blocker, and the race once it lets go deadlocked in about half the runs;
they do not measure how often traffic meets one. The batch and its recovery now write each company
alone, in CIK order, a stored row's update in its place among the inserts: 0 of 20 in each probe. Their
burst case holds every statement and release off the loop and those racers to one row, and
`test_company_routes.py` holds each unit's write order, read at the statements; no CI step races the
searches on PostgreSQL (2026-10-24, E171).
The saved-summary routes (the save, the library list, the notes update and the delete) and the dashboard's
upcoming calendar handed their session to services on the loop, on the connection the auth lookup had
checked out. Eight readers of each on four slots answered as they should, but every statement after the
auth lookup ran on the loop (56 of 64 for eight saves, 48 of 56 for eight notes updates, 16 of 24 for
eight calendars), a save's or a notes update's read after its commit checked a connection out there (8 of
16), and every route but a delete that found its row left its transaction for the finalizer, the
saved-summary status read, a sync route, among them. Each async route is now one thread-pool unit, the status route releases its
own connection, and the library's writes hold a lock from their check to their commit (below). Their
burst case holds every checkout, statement and release off the loop and each reader to its own library
(2026-10-24, E171).
The homepage's reporting-this-week strip, public, ran its read in the thread pool from its service, behind
a single-flight lock on the loop, but left that read's transaction for the finalizer: eight readers on four
slots left the one reader's on a cold cache, and all eight with a cache that never holds. The service is
now synchronous, as the notable-filings strip's is, its single flight a thread lock and its cache replaced
in one assignment, and the route runs it and the release as one thread-pool unit: neither burst leaves one.
A cache hit now takes a thread hop as well, and a miss waits for the fill on a thread, holding no
connection. Its burst case holds every checkout off the loop and nothing left for the finalizer
(2026-10-24, E171).
The account routes (the profile edit, the alert preferences' read and update, and the bell's list and
mark) handed their session to services on the loop, on the connection the auth lookup had checked out.
Eight readers of each on four slots answered as they should, but every statement after the auth lookup
ran on the loop (16 of 24 for eight profile edits or bell reads, 40 of 48 for eight first preference
reads or eight updates, 32 of 40 for eight marks), each write's read after its commit checked a connection out
there (8 of 16), and every one of them, a refused update included, left its transaction for the
finalizer. Each is now one thread-pool unit that shapes its answer and releases its session, the
update's refusal and the plan behind its Pro toggles (the account's subscription row) inside it too, and
two of their writes are atomic in the database (below). Their burst case holds every checkout,
statement and release off the loop, each answer and each reader's rows (2026-10-24, E171). A body or
query that fails its schema (422) is answered after the auth dependency has run and before the route
does, so it still leaves the lookup's transaction for the finalizer, here as on every authenticated
route; malformed JSON is refused before any dependency runs.
The data export and the account deletion handed their session to services on the loop as well. Eight of
each on four slots answered as they should, but every statement after the auth lookup ran on the loop (80
of 88 for eight exports, 144 of 152 for eight deletions), each audit row's read after its commit checked
a connection out there (8 of 16), every export left its transaction for the finalizer, and each of the
eight deletions held the auth lookup's connection through its Stripe cancellation and its PostHog flush,
and flushed on the loop. The export is now one thread-pool unit that builds the payload, writes its audit
row, releases its session and renders the response. The deletion releases the auth lookup's connection
before its third-party calls, sends PostHog its deletion event in a worker thread (the flush waits up to
10 s, holding that thread's token), then writes its audit row and deletes the account in one unit that
rolls a failure back before its release. That unit deletes the account by its id once the lock's own
query finds the row (`user_account_service.delete_user`; `db.get` would hand back a row the session
loaded before another transaction deleted it): the second of two deletions of one account at once finds
none there and answers the route's own 500, naming the account in its log line, where the base's re-read
the expired account in its error log and raised, so the global handler answered (a local PostgreSQL 16
probe, 10 of 10 each; `test_refresh_rotation_transactions.py` races two deletions on PostgreSQL in CI). A
cancelled request task stops the deletion at the await it is in, so before the audit row unless that unit
has started: a unit or a Stripe call a thread has started runs to its end, and one still queued never
runs. Nothing in the deploy cancels a request today (uvicorn cancels only after a graceful-shutdown
timeout the deploy does not set, or on a forced quit), but Cloud Run's SIGKILL, which follows its
SIGTERM, stops a deletion wherever it is (F18). Their burst cases hold every checkout, statement and
release off the loop, and one deletion makes its Stripe and PostHog calls with no connection out
(2026-10-24, E171).
The Copilot ask stream read its filing, resolved the plan and took its admission's lease on the loop, on
the connection the auth lookup had checked out. Eight askers on four slots answered as they should, but
56 of 128 statements ran on the loop for eight Pro questions and 48 of 88 for eight Free ones, each
admission's commit gave its connection back there, and a missing filing (8 of 24 statements) or a
reached cap (16 of 32) left its transaction for the finalizer. On a local PostgreSQL 16, another
transaction holding the asker's `users` row for 1.0 s froze the loop for 1.0 s, Pro or Free: the
admission waits for that row's lock (up to `USAGE_COUNTER_LOCK_TIMEOUT_MS`, 3 s), and every request on
the instance waited with it. The filing read, its snapshot, the plan and the admission are now one
thread-pool unit that releases its session before the stream starts, the admission's refusals included;
with the row held the same way, the loop's longest gap between its 10 ms ticks was 14 ms (five runs of
each). The admission is a check-then-write that the loop no longer runs one at a time, and it needs
nothing new: `subscription_service._reserve_use` takes the account's `users` row lock before it
counts, and `test_usage_counter_transactions.py` races both Copilot leases on PostgreSQL in CI. A taste
the dependency already finds spent (`require_copilot_or_taste`'s 403) and a question over the route's own
rate limit (its 429) are refused before the unit runs, so, like a 422, each still leaves the lookup's
transaction for the finalizer. Its burst case holds every checkout, statement and release off the loop,
each answer and each asker's metering (2026-10-25, E171).
The admin router's maintenance routes (the feedback list and its status update, the summary delete, the
XBRL clear, the filing reset, the stale-XBRL audit and bulk reset, and the summaries' reset-all) handed
their session to services on the loop, on the connection the auth lookup had checked out. Eight requests
to each on four slots answered as they should, but every statement after the auth lookup ran on the loop
(8 of 16 for eight feedback lists, 56 of 64 for eight status updates, 72 of 80 for eight filing resets),
the stale-XBRL audit and bulk reset loading and decoding every filing's XBRL there, each read after a
write's commit checked a connection out there (16 of 24 for the status updates, 8 of 16 for the XBRL
clears, filing resets and bulk resets), and every case but a summary delete that found its filing, whose
commit gave its connection back on the loop, left its transaction for the finalizer, the 404s included.
On a local PostgreSQL 16, another transaction holding a filing's `summaries` row for 1.0 s froze the loop
for about that long (0.94 to 1.02 s, three runs of each) through that filing's summary delete or reset,
or a reset-all: each waited for the row's lock on the loop, and the app's engine sets no lock or
statement timeout. Each route is now one thread-pool unit that makes its service call (with the status
update's or the reset-all's audit row) and releases its session; a 404 leaves the unit after that
release, and the admin's id and email are read before it, since a commit expires them. A non-admin's 403
(`_require_admin`) and a 422 answer before the unit runs, so, like the ask stream's refusals before its
unit, each still leaves the lookup's transaction for the finalizer. With the row held the same way, the
loop's longest gap between its 10 ms ticks was 12 ms (59 ms on a process's first request, whichever route
took it). In the thread pool the maintenance writes overlapped on one instance, as they always could
across the service's two, and they are the Rule's check-then-write units. A reset-all, which deletes
progress rows before summaries, and a summary delete or filing reset, whose flush deletes the summary
first, deadlocked on that PostgreSQL (the review's probes: 9 of 9 rounds with the summary row held, 5 of
12 without; one request answered 500 and rolled back), and two resets each reported, and two reset-alls
each audited, rows one of them had deleted. So the summary delete, the XBRL clear, the filing reset and
the real bulk reset and reset-all take one transaction-level advisory lock before their first read of
those rows (`admin_filing_service.lock_maintenance`): they run one at a time across both instances, each
read sees the commit of the one before it, and a waiter holds only the connection the auth lookup checked
out. `test_admin_maintenance_transactions.py` races them on PostgreSQL in CI: no deadlock; two of one
write at once, for each of the five, report what they found once, the second reading after the first's
commit; each write waits for the lock; and, without it, the deadlock. Their burst case holds every
checkout, statement and release off the loop, each answer, each route's rows, and each audit row's admin
and the count its request answered (2026-10-25, E171).
The admin invite routes did the same (`admin.py`: the invite list, mint, revoke and re-send). Under eight
admins on four slots, through the real auth dependency, the list, revoke, mint and re-send ran 8 of 16,
48 of 56, 48 of 56 and 64 of 80 statements on the loop, the writes checked out 16 of 24 connections
there, and every case left its transaction for the finalizer, the 404s and 409s included; the mint and
re-send held a connection through their invite mail (each the same in three runs; the mail runs only with
marketing readiness open, and `is_marketing_available()` keeps it closed, so a mint asking for it answers
503 before any unit and a re-send of a bound invite answers 503 from its unit). The list and the revoke
(with its audit row) are now one unit each, and the mint and the re-send mint in one unit and write their
audit row in another after the mail, so no pool slot waits on the mail provider; that row now takes a
checkout of its own, so a pool still full at its timeout loses it, logged, where the base's held
connection kept it. The revoke and the re-issue are the Rule's check-then-write units: in the thread pool
a registration on the same instance can redeem the invite between their check and their write, as one on
the other instance always could. On a local PostgreSQL 16, with a registration's redemption of the invite
uncommitted for 1.0 s, the base's revoke and re-send froze the loop for 0.945 to 1.019 s at their write,
then revoked the redeemed invite, and the re-send minted a replacement for it. They now read the invite
under its row lock until their commit (`invite_service._unused_invite_locked`, with `populate_existing`,
so a caller that kept an invite it read before the lock sees the redemption too): each waits in the
thread pool, sees the redemption's commit and answers 409, and the loop's longest gap was 11 to 14 ms
(88 ms on a process's first request). A registration on the same instance, whose session work still runs
on the loop (E121), can now wait there for that lock, from the revoke's or re-send's read to its commit
(a median of about 4 ms in the review's stress run, and up to 205 ms when a garbage collection paused
inside it), which the base's loop never overlapped. `test_admin_invite_transactions.py` races both
against a redemption on PostgreSQL in CI, its control shows each acting on the redeemed invite without
the lock, and two admins' writes of one invite take turns at the lock: a shared one (FOR SHARE) would let
both read, then deadlock at their writes. A redemption that comes second is refused (E201): `redeem_invite`
checks `is_revoked` as well as `used_at`, and one that waits behind the lock re-checks the row when the
write commits; the same gate races it, its control redeeming the revoked invite without the check.
`create_free_account`, a refusal, no longer takes a session of its own; its auth lookup's transaction is
still left for the finalizer, as a 403's is (2026-10-25, E171).
The summaries router's two exports (`export_summary_pdf`, `export_summary_csv`) ran their plan check (the
reader's subscription read) and their summary and filing reads on the loop, on the connection the auth lookup
had checked out, and each build read its company there too; every export, refusal and 404 left its transaction
for the finalizer, and an export kept its connection through its build and render. Under eight readers on four
slots, through the real auth dependency, eight exports ran 32 of their 40 statements on the loop, eight Free
readers' refusals (403) 8 of 16, and eight 404s for a missing summary or a missing filing 16 of 24 and 24 of
32. With the real WeasyPrint, one PDF export of a full summary held its connection 649 to 1,035 ms (ten
exports), the length of its render, so four at once held each of an instance's four pooled connections that
long. The plan check, both reads and the release are now one thread-pool unit the two routes share
(`_summary_and_filing_for_export`); its rows come back detached with the filing's content cache and company
loaded, and its 403 and 404s leave it after the release. The same PDF export holds its connection 2.5 to 6.4
ms. The builds ran on the loop as well: projecting the filing's text takes about 1 ms for a one-sentence
excerpt, 12 to 17 ms for a real 10-K's text (588,000 characters) and 1.2 to 1.8 s for a cache holding only
that filing's raw HTML (4.3 million characters), so the CSV and the PDF's HTML now build in worker threads, as
the render does (`asyncio.to_thread`; `test_default_executor_allowlist.py` names both). An anonymous request's
401 answers before the unit; one whose token names an inactive or deleted account answers there too, after the
lookup, so it still leaves the lookup's transaction for the finalizer. Its burst case holds every checkout,
statement and release off the loop and each answer, each reader's plan given by its Subscription row against
its `is_pro` mirror (a plan check on the detached user falls back to the mirror and answers wrong), and its
render case holds no connection while either export builds or renders, and neither on the loop (2026-10-25,
E171).
The admin router's stale-summary refresh (`refresh_stale_summaries`) read its candidates on the loop, on the
connection the auth lookup had checked out, and a real run kept a connection out through every generation: the
candidates' read left its transaction open through the first, each stamp re-read after it, on the same session
after a commit, checked out another on the loop that stayed out through the next, and the audit row was written
there too. Under eight admins on four slots, through the real auth dependency, with the generation stubbed,
eight dry runs ran 16 of their 24 statements on the loop, eight real runs of five candidates each 72 of 80 with
48 of their 56 checkouts there, and every run left its transaction for the finalizer. Each generation of a real
run began with the request's connection out, so four real runs at once held all four of an instance's pooled
connections, and a fifth admin's request answered 500 at the pool's timeout (each the same in two runs; one
second in the probe, `DB_POOL_TIMEOUT`'s 10 s in production, where a generation takes up to about 120 s and a
run makes up to ten). The candidates' read and the release are now one thread-pool unit, the admin's id and
email read before it, and `admin_summary_service.regenerate_in_place` takes no session: it re-reads each stamp,
and writes the audit row, in a session of its own in the thread pool (`_in_own_session` through `run_owned_sync`,
which outside a `request_work` scope runs on anyio's tokens, as `run_in_threadpool` does), so no connection is out
while a generation runs. That session's close, like the release, logs a failure rather than raising it. On
PostgreSQL, with the connection dropped after a unit's last statement, an unguarded close answered 500 after the
paid generations wherever the drop came; the guarded one answers 200 with the audit row. The base answered 500 at
its next commit, 200 without its audit row after the last re-read, or, after the audit row's read-back, 200 with
its audit row, its request-scoped `get_db` then failing to close once the answer had gone (the review's probes).
The job-side drain
(`summary_refresh.drain_stale`) re-reads in a session of its own too, on its job's loop, where no request
waits. `lessons/ops-one-connection-per-request-unit.md` keeps a session of its own for background work, since one
opened while the request's session holds a connection needs a second; the refresh's open only after the release,
one at a time, so none waits for a connection while it holds one. The audit row is a call of its own with its
action written out (`_record_refresh`): the legal pages' audit walk (`frontend/tests/unit/legalTruth.spec.tsx`)
reads a writer where it is called or handed first to `run_in_threadpool`, not one handed on through another
call. A non-admin's 403 answers before the unit, so it still leaves the
lookup's transaction for the finalizer, as the other admin routes' do. Its burst cases hold every checkout,
statement and release off the loop, each answer, each generation and each audit row; its hold case, no
connection out as each generation starts or ends; a case of its own, a run whose own sessions fail to close,
still returning its outcomes and writing its audit row; and the route's tests, a generation that raises or ends
in an error event counted failed (2026-10-25, E171).
The summaries router's generate stream (`generate_summary_stream`), E171's last route, ran its admission on the
loop, on the connection the auth lookup had checked out: its filing and summary reads, the served body (the stored
summary's Risks projected over the filing's own text: about 0.5 ms for a one-sentence excerpt, 11 ms for a real
10-K's text and 1.0 to 1.15 s for a cache holding only the filing's raw HTML, 4.3 million characters), the
readiness and Pro checks, the force branch's progress clear and commit, and the close before it streamed. Under
eight readers on four slots, through the real auth dependency, with the orchestrator stubbed, eight replays ran 16
of their 24 statements on the loop, eight generations and eight regenerations of an unready row 16 of 32 each,
eight Pro forces 33 of 41, eight Free forces 24 of 32 and eight requests for a missing filing 8 of 16; each
replay, generation and Pro force gave its connection back on the loop, and each Free force's 403 and each 404 left
its transaction for the finalizer (each the same in two runs). One replay of the raw-HTML cache froze the loop for
1.3 to 1.5 s, and on a local PostgreSQL 16 another transaction holding the filing's progress row for 1.0 s froze
it for 0.91 to 0.95 s through a Pro force, whose progress clear waited for the row's lock at its commit (three
runs). The admission is now one thread-pool unit (`admit`) that takes those steps in the route's order and
releases the session in its `finally`, its 404 and 403 leaving it after the release; it returns the replay's
response or the generation's inputs, the reader's id read before it, and the stream calls the one orchestrator
with the same arguments. The same probes ran every statement, checkout and checkin off the loop; behind the held
row the loop's longest gap was 12 to 33 ms (six runs, the longest on a process's first request), and behind the
raw-HTML replay 0.17 to 0.27 s (seven runs), the projection's own work in its worker thread (11 to 17 ms in five
runs with the projection stubbed). The progress clear was a read, then a delete at the commit, which the loop had
run one at a time on an instance: in the thread pool two Pro forces of one filing both found the row, and the
second's delete matched none, which SQLAlchemy only warns of (in two sets of six bursts in the review, 4 and 5 met
it, and under `-W error` a force answered 500). It is the Rule's check-then-write, so it is now one DELETE by
filing with no read before it, which checks no row count, so a row another force has already deleted is no error,
and which holds between instances too; behind the held row both forces answered 200 in three runs. A clear that
landed inside another run's `record_progress`, between its read and its update, still failed that run: the
`StaleDataError` reached the pipeline's failure stage and ended it in the error event, refunding its unit only
between the provider's start and the summary's save, as one could on the base and from another instance. Since
E214 `record_progress` writes the row in one `INSERT … ON CONFLICT (filing_id) DO UPDATE` with no read before it:
after such a clear it inserts a fresh row, and after another run's insert, which its INSERT had collided with
(`IntegrityError`), it updates that row (`backend/tests/unit/test_progress_write_is_one_upsert.py`, and
`backend/tests/integration/test_summary_progress_transactions.py` on PostgreSQL). The
route's rate limit (its 429) answers before the unit, so, like a 422, it still leaves the lookup's transaction for
the finalizer. Its burst case holds every checkout, statement and release off the loop, the served body built off
the loop, each answer and each admitted request's orchestrator inputs, each reader's plan given by a Subscription
row its `is_pro` mirror contradicts, and the progress row touched only by the Pro forces' DELETEs, one each; a
case of its own holds the 429 before the unit (no filing or summary read, no served body, no clear); and
`test_summary_provider_lifecycle.py`'s route cases hold the request's release off the loop, before the response
starts (2026-10-25, E171). The progress poll's unit was a read-modify-write: it read the row, flipped a stalled one
to an error in memory and committed, so a clear landing between the read and the commit answered that poll 500
(`StaleDataError`), a clear after the commit did too as the answer read the row the commit had expired
(`ObjectDeletedError`), and a run's write landing before the commit was overwritten with the stall's error. Since
E215 the mark is one UPDATE by filing on a non-terminal stage whose last write is past the cutoff, which a clear or a
fresh write leaves matching nothing, and the poll reads the row after it (`backend/tests/unit/test_orphaned_progress.py`,
and `backend/tests/integration/test_summary_progress_transactions.py` on PostgreSQL) (2026-10-26).
A unit run with `run_in_threadpool`, as every E171 unit is, takes one of anyio's default thread tokens (40 a
process), and an auth lookup blocked on the pool holds one while it waits; the dependency's finalizer had a
one-token limiter of FastAPI's own (`contextmanager_in_threadpool`), and the feedback router's units run on
`request_work`'s executor of their own (`run_owned_sync`). So an instance with more requests in flight than
its tokens and pool slots together can have every token held by lookups waiting for connections whose holders
need a token to give them back, and nothing moves until the pool times out, which the optional lookup reads as
anonymous. In the exports' review, on 40 tokens and four slots, 43 PDF exports all answered and 44 as few as 4
(the rest 401); sixty answered 20 or 36 of 60, where the base answered all 60, and sixty change reports, one
unit since #1286, 32 to 42 in three runs (the rest 500); forty exports, and forty change reports, all
answered. Cloud Run's `--concurrency=40` keeps an instance at the token count, a margin of the pool's slots,
and the pool-lifetime file holds every concurrency the deploy sets there; raising it needs the units on a
limiter of their own (2026-10-25, E171).
The pool-lifetime file's AST ratchet reads every async router function and fails, above that function's
ceiling, a session call on the loop in its own body (on main before the fix it named both summaries
routes) or, since 2026-10-24, the session handed there to any call but a thread dispatcher's (with the
dashboard feed's unit composed on the loop, a route no burst lists, it fails while main's file
passed), a `with` it enters there, or a call there of a nested unit whose body, read by the same
rules, uses it. Its ceilings hold the routes that still use their session on the loop at
their counts (the rest of the auth router, E121, since E171's last route left on 2026-10-25; four of those
hand-offs, the header's strict ones, use no connection on the loop), so none can add one in a
form the ratchet counts and a new route starts at 0. Neither half
sees a form the ratchet's header puts out of its reach (a session inside a container, a lambda called
where it is written) where the burst does not list the route, or a background task's own session worked on the loop
(E123 moved the company list's units into the thread pool, `test_filings_endpoint_db_first.py`'s
off-the-loop cases; the flag-off job runners are E150), which stays a review check. Local PostgreSQL measurement is separate from production headroom and safe-cohort
evidence.

E118's reviews found that five of its units had relied on the loop's order. Without a lock:
- two joins lost a referral credit and took one place;
- two alert enables put an account over its cap;
- two adds, or an add and an enable, wrote two rows for one company;
- two removes both succeeded;
- a disable racing a remove failed on the deleted row.

Each now holds a lock from its check to its commit (2026-10-19). E171's saved-summary slice found three
more in the library's writes, each now under `saved_summary_service.saved_row_lock`: two saves of one
summary both passed the duplicate check and stored it twice, two deletes of one row both succeeded, and a
notes update racing a delete failed on the deleted row (`StaleDataError`, a 500) (2026-10-24). E171's
account slice found two more and writes each atomically in the database instead, which reaches every
instance and the alert scanner too: two first reads of one account's alert preferences both found no
row, and the second insert's clash on the unique `user_id` answered 500, so the insert runs under a
SAVEPOINT and a clash reads the stored row (`notification_service.get_or_create_preferences`); and of
two marks of the bell, the one stamped first could commit last and put its earlier stamp back, so the
mark's UPDATE writes its stamp only over an older one (`user_notification_feed_service.mark_seen`)
(2026-10-24). The gate is `backend/tests/unit/test_check_then_write_units_serialize.py`. It meets two
threads inside each unit after their checks (for the marks, the one stamped first checks before the other
starts and writes once it has committed), so without the lock or the atomic write the race happens
however loaded the host, and it fails any checkout made inside the watch-row or saved-row lock in the
races it runs. It covers those
ten units only. SQLite serializes every writer, so for the two account writes it meets only their
sequential order. No CI step races them on PostgreSQL, where the second insert waits on the first's
uncommitted row and the stamp's UPDATE re-checks its WHERE after a row-lock wait. The pull request's
local PostgreSQL 16 run did, ten runs each: two first reads that met after their check answered one stored
row (on the base one of them failed with IntegrityError); a first read that met an update's uncommitted
insert waited 0.505 to 0.510 s for it and answered its row; and a mark stamped first that waited on the
later mark's row lock left the later stamp (on the base, the earlier one).

Those locks reach one process, and the API runs up to two instances, across which the five races stayed
open. Since E128 each unit also takes, before its check, a lock in the database that every instance
shares, and holds it to the commit that carries its write. The watch-row writes take the account's users
row lock (`watchlist_service.lock_watch_rows`, FOR NO KEY UPDATE, as the refresh token's writers do)
before the process lock. That lock serves every account: a unit that waited on one account's row inside
it, behind a Stripe delivery's read say, stalled every other account's writes on the instance, and with
the auth lookup's connection each waiter holds, three such waiters and the stalled unit filled the
instance's four-slot pool. The library's writes take the same users row lock before their own process
lock (`saved_summary_service.lock_saved_rows`, E171). Inside that process lock a library write can still
wait in PostgreSQL behind an admin tool's delete, which takes no users row lock: a save at its INSERT's
foreign-key check on a summary being deleted, an update or a delete on a bookmark the reset-all is
deleting. Every account's library write on the instance then waits too: a local PostgreSQL probe held
another account's save of another summary 1.49 to 1.51 s behind a 1.5 s admin delete, and the waiting save
failed its foreign-key check (500). Taking the summary's key-share lock at the save's read, before both
locks, ended that wait (0.006 to 0.021 s) but deadlocked a save over a saved row with the reset-all, which
deletes the bookmarks before their summaries, as `scripts/reset_filing_summary.py --include-saved` does
(40P01, five runs of five in each order), so the save takes no lock on its summary until both of their
orders change with it. The join takes the waitlist's place lock, a
transaction-level advisory lock, since no row is common to every join
(`waitlist_service._lock_waitlist_places`), inside its process lock,
which a waiter takes before its first query and so waits on holding no connection. Its place is one past
the highest held, so no two signups on the list share one even after a deletion, and its credit one
UPDATE that adds to the stored score. The process locks stay: under SQLite they are the only serialization.
`backend/tests/unit/test_check_then_write_units_lock_across_instances.py` holds each lock from before its
unit's first read to the commit of its write, as statements compiled for PostgreSQL, the watch-row and
saved-row locks outside their process locks and the reads beside them taking no lock, each saved-row
write's commit inside `saved_row_lock` with no checkout inside it and nothing run there after the commit
(a read after the commit would check a connection out inside the lock), the save taking no lock on its
summary, and the credit to one that a concurrent commit cannot lose. No CI step races two instances on PostgreSQL. The pull request's local run
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
