# Read everything a request unit needs through its own session; never open a second one inside it

Date: 2026-10-18   Area: ops

**Context**: The dashboard feed and the watchlist insights read each filing's generation progress
through `summary_generation_service.get_generation_progress_snapshot`, which opened a `SessionLocal`
of its own. Each request held its session's connection while the helper waited for a second one,
so four concurrent requests filled the four-slot pool and each waited for a fifth slot. A probe on
main answered all eight requests of an eight-request burst with 500 at the pool timeout, on both
routes, and a single request on a one-slot pool could not finish. Production's API pool has four
slots and a 10 s timeout. Four dashboard loads at once, each watching a company whose newest filing
has no summary yet, would all fail and hold the whole pool for those 10 s.

**Rule**: A request unit reads everything it needs through the request's own session. A helper that
opens its own session (`SessionLocal()`) is for background work. Called while the request session
holds a connection, it needs a second one per request, and a full pool then deadlocks until its
timeout. Batch the read into the caller's session instead (one `IN` query), as the feed and the
insights now read `SummaryGenerationProgress`.

**Evidence**: `backend/app/services/dashboard_feed_service.py` (`compose_feed`) and
`backend/app/services/watchlist_service.py` (`load_insight_rows`), 2026-10-18. The gate is
`backend/tests/unit/test_progress_reads_share_the_request_session.py`:
- each route answers one request on a one-slot pool and eight on four slots;
- an AST check fails a `def`, `async def` or `class` of `get_generation_progress_snapshot`, and each use of
  the name (a name, an attribute, an import), under `app/` and in the backend's top-level modules, scored on
  planted source; a definition or reference through a string or a namespace (`setattr`, `getattr`,
  `importlib`) is out of its reach. E124 deleted the helper (2026-10-22).

Any other own-session helper called inside a request unit is a review check.
