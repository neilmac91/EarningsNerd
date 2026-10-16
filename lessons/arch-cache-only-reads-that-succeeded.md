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
(`ops-auth-lookups-must-let-request-cleanup-progress.md`). That await lets every concurrent miss
reach the read, which a sync read on the loop had serialised, so hold one lock across the miss and
the fill and recheck the cache after acquiring it. A waiter behind a failed read reads again.

**Evidence.** `backend/app/services/reporting_this_week_service.py` (`get_reporting_this_week`,
`_fetch`). `backend/tests/unit/test_reporting_this_week_service.py::test_failed_fetch_is_not_cached`
fails a read on a cold instance and again on a warm one, where ET midnight changes the key while
Monday's success is still inside the TTL; the healthy retry after each must return the week. Test
the warm case: a cold cache has no timestamp, so code that writes the failed entry but not its
timestamp still passes there. `::test_successful_empty_week_is_cached` pins the other half, an
empty week fetched once. `::test_waiting_fetch_lets_another_request_release_its_connection` sends
two ASGI requests through a one-slot QueuePool. `::test_concurrent_misses_share_one_read` sends
eight cold-cache requests at a blocked read and expects one read;
`::test_failed_read_lets_the_next_waiter_retry` sends three, fails the first read, and expects the
second request to read again and the third to hit the cache. `notable_filings_service.py` still has the old shape; its
homepage section is not mounted.
