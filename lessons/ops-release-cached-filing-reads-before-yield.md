# Release cached filing-list sessions before yielding to dependency cleanup

Date: 2026-09-29   Area: ops

**Context**: Eight concurrent cached filing-list requests exhausted a four-slot PostgreSQL pool.
Four completed reads remained idle in transaction while subsequent synchronous checkouts blocked
the event loop; the asynchronous wrapper around the sync dependency could not run its finalizer.
The same failure reproduced in the full application and an actual local Uvicorn HTTP server.

**Rule**: The filing-list route materializes response DTOs and closes its session in the same
synchronous unit, including cached, live and fallback reads. Do not leave completed reads for
the sync dependency's thread-pool finalizer, or increase the pool to hide the blockage. Keep the
dependency finalizer as a final safety net, and retain scalar identities for any later work.

**Evidence**: `backend/app/routers/filings.py::get_company_filings`; the full-app eight-request,
four-slot regression is `backend/tests/unit/test_cached_filings_pool_lifetime.py`. Local PostgreSQL
measurement is separate from production headroom and safe-cohort evidence.
