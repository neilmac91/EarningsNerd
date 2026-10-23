# Keep pool waits off the event loop and out of its default executor

Date: 2026-10-03, extended 2026-10-16 to Copilot lookups and 2026-10-19 to the companyfacts sync and
every default-executor site · Area: ops / authentication / Copilot / facts

**Context.** Authentication used a synchronous SQLAlchemy lookup inside an async dependency.
When another request held the last connection, pool checkout blocked the event loop that needed
to finish that request and schedule its session cleanup. A real FastAPI/QueuePool regression
reproduced a required-auth 500 and an optional-auth downgrade to anonymous. The Copilot's numeric
tool calls and its server claim-repair lookup had the same shape inside the ask-stream SSE
generator: with every slot held, the whole instance stalled for the pool timeout, the tool
returned `tool_failed`, and the figure shipped without its citation. Moving those lookups to the
loop's default executor was not enough. Login kept its connection checked out while it awaited
bcrypt through `asyncio.to_thread` (a password change or reset still does; login has released its
session before bcrypt since 2026-10-20, E121), so lookups holding every default-executor thread and a holder
needing one waited on each other until the pool timed out, with the same uncited figure.

**Rule.** The authentication dependencies await their blocking lookup through
`run_in_threadpool`. The Copilot's tool calls and claim-repair lookup await theirs through
`run_in_lookup_thread` (`backend/app/services/ai/copilot_chat.py`), whose threads only Copilot
lookups use, and never through `asyncio.to_thread`: the default executor is shared with work that
may be holding a slot. The companyfacts sync (`backend/app/services/facts/ingest.py`) runs its
freshness read, a follower's re-read and its persist on threads of its own
(`backend/app/services/facts/sync_threads.py`) for the same reason. Only work that never waits for a
pool slot goes to the default executor (`asyncio.to_thread`, `run_in_executor(None, ...)`), and each
such site is listed with why. The
threaded work opens its own session, or uses one no other coroutine touches until the await
returns. Preserve async dependency signatures, JWT and account checks,
request-context monitoring, and the request-owned session lifecycle. Do not close or detach the
user early, or increase pool sizes to hide event-loop starvation. The fix allows cleanup to
progress; it does not establish safe fleet concurrency or guarantee that every busy pool can
satisfy its timeout. The off-the-loop rule and its gates cover only these sites; the default-executor
listing covers each `asyncio.to_thread` and positional `run_in_executor(None, …)` call under `app/` and
in the backend's top-level modules, and its docstring names the forms it cannot see. Other async code still
makes blocking lookups on the loop (async route bodies such as `register`, `reset_password` and
`change_password`, and the `/internal` trigger helpers' flag-off jobs, E150; the
`filing_list_service.refresh_company_filings` background task moved its unit into the thread pool in
E123); those are known and review-checked.

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
loop and a holder shaped like a password change that needs the (one-thread) default executor. Running
the lookups through `asyncio.to_thread` instead fails the change-shaped cases. The companyfacts sync's first
off-loop draft (E129, 2026-10-19) ran its units through `asyncio.to_thread`, the shape this lesson had
already ruled out, and passed its own tests: `backend/tests/unit/test_companyfacts_sync_off_the_loop.py`
now holds the sync to its own threads and runs it against a one-slot pool whose holder needs the
one-thread default executor, a case the draft fails at the pool timeout. Prose had not stopped it, so
`backend/tests/unit/test_default_executor_allowlist.py` lists each such call under `app/` and in the
backend's top-level modules, each with why its work never waits for a slot: bcrypt, the PDF
and workbook renders, the Copilot's quotation check, and the startup connection check, which runs
before the app serves a request. Its first scan also found a `SELECT 1` waiting there for a slot, in
`metrics_service.get_health_summary`, which nothing had called since it was written; it is deleted.
