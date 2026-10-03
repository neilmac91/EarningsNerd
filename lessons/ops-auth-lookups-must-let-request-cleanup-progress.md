# Keep authentication pool waits off the event loop

Date: 2026-10-03 · Area: ops / authentication

**Context.** Authentication used a synchronous SQLAlchemy lookup inside an async dependency.
When another request held the last connection, pool checkout blocked the event loop that needed
to finish that request and schedule its session cleanup. A real FastAPI/QueuePool regression
reproduced a required-auth 500 and an optional-auth downgrade to anonymous.

**Rule.** Await the existing thread-pool interface for the blocking authentication lookup.
Preserve async dependency signatures, JWT and account checks, request-context monitoring, and
the request-owned session lifecycle. Do not close or detach the user early, or increase pool
sizes to hide event-loop starvation. The fix allows cleanup to progress; it does not establish
safe fleet concurrency or guarantee that every busy pool can satisfy its timeout.

**Evidence.** `backend/app/routers/auth.py::_lookup_auth_user`, `get_current_user` and
`get_current_user_optional`; `backend/tests/unit/test_auth_pool_progress.py` exercises both
dependencies with two actual ASGI requests and a one-slot QueuePool. Returning the lookups to
the event loop makes the gate fail; restoring the thread-pool calls preserves both identities
and returns the checked-out connection.
