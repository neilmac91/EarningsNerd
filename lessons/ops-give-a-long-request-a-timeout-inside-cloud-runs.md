# Give a route that works for minutes in its request a timeout of its own inside Cloud Run's, and start no step it cannot finish before it

Date: 2026-10-26   Area: ops

**Context**: `POST /api/admin/summaries/refresh-stale` regenerates up to ten summaries one at a time
in its request, which keeps its CPU allocated: the deploy runs the API with `--cpu-throttling` while
durable tasks are on, and work after a response can be slowed or cut short. `main.py`'s
request-timeout middleware gave the path its 30 s default, while one generation can take the
pipeline's 120 s backstop. A real run that passed 30 s answered 504 and lost its per-filing outcomes, and since
Starlette's middleware lets the route finish after the response, the rest of the batch and its audit
row ran on under that throttling (E213, from #1645's review). An entry of 600 s or more would never
fire: Cloud Run ends the request at the service's `--timeout=600` first, with a response that carries
no CORS headers, so a page on the site's origin cannot read it.

**Rule**: A route that does minutes of work in its request takes an entry of its own in `main.py`'s
`REQUEST_TIMEOUT_SECONDS`, below the API service's Cloud Run `--timeout`. It starts no step after
that timeout less the step's allowance and a margin for the work around the batch, counting from the
route's start, and it reports what it does not start as deferred, never as done. A step's allowance
is its own deadline plus what runs outside it, its setup and cleanup; where nothing bounds the
cleanup (a pipeline run waits for its worker threads), the allowance is an estimate, and a step that
outlasts it still ends in the 504. The 504 does not stop the route: its work goes on after the
response, under the throttled CPU. Work that cannot fit belongs in a job.

**Evidence**: `backend/app/routers/admin.py` (`REFRESH_STALE_TIMEOUT_SECONDS`,
`_REFRESH_STALE_GENERATION_ALLOWANCE_SECONDS`, `_REFRESH_STALE_START_BY_SECONDS`),
`backend/app/services/admin_summary_service.py::regenerate_in_place`, `backend/app/services/request_work.py`
(`RequestWork.drain`, which has no cleanup timeout),
`backend/main.py::request_timeout_middleware`; gates `backend/tests/unit/test_request_timeouts_fit_cloud_run.py`
(every entry below the deploy's `--timeout`) and `backend/tests/unit/test_admin_refresh_stale.py` (a run
past the default timeout answers its outcomes; what the budget leaves unstarted is deferred).
