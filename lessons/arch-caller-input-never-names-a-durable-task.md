# Never let a public caller's input name a durable task or key its dedupe

Date: 2026-10-16   Area: arch

**Context**: `GET /api/filings/company/{ticker}` needs no login, and the site's own server renders
call it from Vercel's shared IPs with no credential. In durable mode its DB-first branch handed
Cloud Tasks a refresh whose payload carried the caller's `?filing_types=` list. `enqueue_task`
names a task with `sha256(key:body)`, body included, and the router's per-process guard keys on
the payload too. So every distinct value queued a new task, with no 409 from Cloud Tasks and no
local suppression. That held for junk forms and for known forms in another order or spelling: 40
GETs queued 40 tasks. Each task costs a worker child process and an SEC fetch on the 0.2 dispatch/s
queue that companyfacts syncs, history backfills and operator jobs share.

**Rule**: A durable (queued) task started by a public request carries only server-owned
identity: ids the server resolved and fixed vocabularies, never the caller's string. When the
caller's choice must shape the work, first validate it where it enters (CLAUDE.md rule 9) into a
bounded canonical set, and count how many distinct payloads one company can produce per dedupe
bucket. The response can still filter per request. A fix is proven by sending N distinct caller
values through the real task-naming code, with only the transport faked, and counting the tasks.
Server-owned names still let a caller pick the company, so a route that needs no login also spends a
process-wide budget on each handoff. Size it, summed over every serving process, under the queue's
real drain: a queue that dispatches one task at a time drains one per mean delivery time, which can
be slower than its dispatch-rate ceiling. A request that hands nothing off spends nothing, and one
past the budget is served without queuing.

**Evidence**: `enqueue_task` in `backend/app/services/durable_tasks.py` hashes whatever body it is
given, by design, so the fix belongs to the caller: `backend/app/routers/filings.py` enqueues
`company_list_forms()` on every visit, and also `other_filing_forms()` (every other form the
parameter accepts) when the visit serves stored rows of one of those, so one company has at most two
refresh payloads per bucket. `backend/app/services/filing_list_service.py::requested_filing_types`
reads each entry as its SEC form and drops unknown ones. A fixed vocabulary can be wider than the
work it should cause: the worker fetches the list-forms payload whole and keeps any other payload to
the forms the company already has rows of (`forms_to_refresh`), because one fetch keeps the newest
50 rows across its forms and the watchlist, dashboard and digest read every stored form. It
recognises the list payload in either state of `ENABLE_FPI_FILINGS`, since a queued task can outlive
a flag change, so a payload keeps the meaning it was queued with. Gate:
`backend/tests/unit/test_filings_routes.py::test_filing_types_values_cannot_mint_durable_refresh_tasks`
(before the fix: 40 junk values queued 40 tasks, and 5 known-form variants queued 4).
`backend/tests/unit/test_durable_task_payloads_server_owned.py` walks every `enqueue_task` and
`_enqueue_visit_task` call under `backend/app/`. In `app/routers/` the payload must be a dict
literal and the dedupe key a literal or f-string, built only from `company_id` (never a route
parameter, bound only from a row's `.id`) and the fixed vocabularies `company_list_forms()` and
`other_filing_forms()`, with no format spec in a key's parts; before the fix it failed on the
filings payload's `types_list`. Every such call passes a key (a keyless task is named at random, one
per request), and its window is a literal or a module-level constant.
`test_filings_routes.py::test_a_refresh_fetches_list_forms_and_only_other_forms_already_stored` pins
the worker's narrowing. Any other site, such as the operator-only
`services/internal_task_runner.py`, is listed with its reason, and a listed site that is gone fails.
Validating a caller's choice into a bounded set, and counting the payloads one company can produce
per bucket, are review-checked. So are the gate's two limits: it takes `.id` from any object, a
request model's too, and does not follow callers of `enqueue_internal_job` (today only the
token-gated internal job routes). What bounds the route since 2026-10-23: `_enqueue_visit_task`
spends `VISIT_TASK_BUDGET` after its guard and before `enqueue_task`, so a crawl of stored companies
is served its rows and queues nothing past it. It allows 15 handoffs per 5 minutes per process, 30
across two instances (0.1/s). The queue dispatches one task at a time, at most 0.2/s, so it drains
1/max(5 s, mean delivery time); a delivery execs a fresh Python child (about 1.7 s of imports) and a
history backfill paces 4 EFTS windows at 1 request/s, so a delivery is taken to average 6 s, and
the cap is then 60% of the drain. The first size, 20, was set against the 0.2/s ceiling and took
80% of that drain. The synchronous SEC fetch, taken whenever nothing is stored in the requested
forms (a first view, or every view of a company that has none of them), spends
`LIVE_FETCH_LIMITER` (10 per minute per client IP) and answers 429 past it. The payload gate
requires a pass-through to spend such a module-level budget first, and a direct router
`enqueue_task` to sit in a route with `Depends(get_current_user)`. Tests:
`test_filings_routes.py::test_handoffs_past_the_budget_serve_stored_rows_and_queue_nothing_until_the_window_passes`,
`::test_visits_that_hand_nothing_off_spend_no_budget`,
`::test_live_fetches_past_the_per_ip_budget_answer_429_only_when_nothing_is_stored` and
`::test_the_handoff_budget_takes_at_most_two_thirds_of_the_queue_drain_across_the_api_instances`,
which reads the API's instance cap from `ci.yml` and the queue's provisioning from
`docs/DEPLOYMENT.md`. Its 6 s delivery time is an estimate, and the route's SEC reach is
review-checked. The same route's in-process refresh (`DURABLE_TASKS_ENABLED=false`, not the
production path) still takes the caller's canonical forms in the caller's order: it queues nothing
on the shared queue, is deduped per process while in flight, and stamps the per-filter freshness key
that the fast path reads.
