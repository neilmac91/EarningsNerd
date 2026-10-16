# Cache only a read that succeeded; a failure that degrades to empty serves one request

Date: 2026-10-16 · Area: arch / caching

**Context.** The homepage reporting-this-week strip degrades to an empty result when its database
read fails. Its in-memory cache stored that empty list as if it were the real week, for the 6h TTL.
On a cache miss the public route ran the read on the event loop, so a full pool blocked the loop
until the checkout timed out. The swallowed timeout was then cached, and the strip stayed blank on
that instance for hours after the database recovered.

**Rule.** A best-effort read that swallows its failure must still tell its caller that it failed,
for example by returning `None` rather than `[]`. The caller caches and timestamps only a success.
After a failure it serves the degraded result to that one request and leaves the cache as it was,
so the next request retries. A successful empty result may be cached. When a route reaches the
pool with no earlier off-loop checkout, run the read in the thread pool
(`ops-auth-lookups-must-let-request-cleanup-progress.md`).

**Evidence.** `backend/app/services/reporting_this_week_service.py` (`get_reporting_this_week`,
`_fetch`). `backend/tests/unit/test_reporting_this_week_service.py::test_failed_fetch_is_not_cached`
runs a failed read and then a healthy one, which must return the week.
`::test_waiting_fetch_lets_another_request_release_its_connection` sends two ASGI requests through
a one-slot QueuePool. `notable_filings_service.py` still has the old shape; its homepage section is
not mounted.
