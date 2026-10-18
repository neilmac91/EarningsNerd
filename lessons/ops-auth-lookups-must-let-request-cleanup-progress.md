# Keep authentication and Copilot pool waits off the event loop

Date: 2026-10-03, extended 2026-10-16 to Copilot lookups · Area: ops / authentication / Copilot

**Context.** Authentication used a synchronous SQLAlchemy lookup inside an async dependency.
When another request held the last connection, pool checkout blocked the event loop that needed
to finish that request and schedule its session cleanup. A real FastAPI/QueuePool regression
reproduced a required-auth 500 and an optional-auth downgrade to anonymous. The Copilot's numeric
tool calls and its server claim-repair lookup had the same shape inside the ask-stream SSE
generator: with every slot held, the whole instance stalled for the pool timeout, the tool
returned `tool_failed`, and the figure shipped without its citation. Moving those lookups to the
loop's default executor was not enough. Login keeps its connection checked out while it awaits
bcrypt through `asyncio.to_thread`, so lookups holding every default-executor thread and a holder
needing one waited on each other until the pool timed out, with the same uncited figure.

**Rule.** The authentication dependencies await their blocking lookup through
`run_in_threadpool`. The Copilot's tool calls and claim-repair lookup await theirs through
`run_in_lookup_thread` (`backend/app/services/ai/copilot_chat.py`), whose threads only Copilot
lookups use, and never through `asyncio.to_thread`: the default executor is shared with work that
may be holding a slot. The threaded work opens its own session, or uses one no other coroutine
touches until the await returns. Preserve async dependency signatures, JWT and account checks,
request-context monitoring, and the request-owned session lifecycle. Do not close or detach the
user early, or increase pool sizes to hide event-loop starvation. The fix allows cleanup to
progress; it does not establish safe fleet concurrency or guarantee that every busy pool can
satisfy its timeout. The rule and its gates cover only these sites. Other async code still makes
blocking lookups on the loop (async route bodies such as `login`, the
`filing_list_service.refresh_company_filings` background task, the `/internal` trigger helpers);
those are known and review-checked.

**Evidence.** `backend/app/services/auth_account_service.py::find_user_by_email` (the lookup,
moved out of the router as `_lookup_auth_user` in 2026-10), awaited through `run_in_threadpool`
by `backend/app/routers/auth.py::get_current_user` and `get_current_user_optional`;
`backend/tests/unit/test_auth_pool_progress.py` exercises both
dependencies with two actual ASGI requests and a one-slot QueuePool. Returning the lookups to
the event loop makes the gate fail; restoring the thread-pool calls preserves both identities
and returns the checked-out connection. For the Copilot, `stream_chat_with_tools` in
`backend/app/services/ai/copilot_chat.py` awaits `copilot_tools.run_tool` (its own
`SessionLocal()` per call) through `run_in_lookup_thread`, and `_admit_answer` in
`backend/app/services/copilot_service.py` awaits `_resolve_answer`, whose claim repair calls
`run_tool`, the same way. `backend/tests/unit/test_copilot_pool_progress.py` drives the real
answer path through both lookups against a one-slot QueuePool, with a holder that needs only the
loop and a login-shaped holder that needs the (one-thread) default executor. Running the lookups
through `asyncio.to_thread` instead fails the login-shaped cases.
