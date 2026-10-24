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
the warm case: there a key without the ET day serves Monday's week without reading, which a cold
cache cannot show (and before E171 made the cache one snapshot, a cold cache with no timestamp also
passed code that wrote the failed list but not its time). `::test_successful_empty_week_is_cached`
pins the other half, an empty week fetched once.
`::test_waiting_fetch_lets_another_request_release_its_connection` sends
two ASGI requests through a one-slot QueuePool. `::test_concurrent_misses_share_one_read` sends
eight cold-cache requests at a blocked read and expects one read;
`::test_failed_read_lets_the_next_waiter_retry` sends three, fails the first read, and expects one
more read and one cache hit. Since E171 the strip's route runs the read and its release as one
thread-pool unit, so its lock is a thread lock and each test request runs in a thread.
`notable_filings_service.py` follows the rule with a thread lock too, since its route reads in the
thread pool (#1437):
`test_notable_filings_service.py::test_a_failed_read_is_not_cached` (cold and warm),
`::test_a_successful_empty_read_is_cached`, `::test_a_miss_during_a_fill_waits_for_it_and_reads_nothing`
and `::test_a_failed_read_lets_the_next_waiter_read_again`. The company filings list's freshness stamp
(`filing_list_service.py`) is written only after SEC answered the listing, and the route answers a
fresh key from the stored rows even when the listing found nothing:
`test_filings_routes.py::test_a_listing_that_found_nothing_is_answered_from_its_stamp_until_the_ttl_passes`
and `::test_a_failed_live_listing_stamps_nothing_so_the_next_visit_fetches_again` (cold and stale).
It has no single-flight lock: concurrent misses of one key each fetch, as before.
