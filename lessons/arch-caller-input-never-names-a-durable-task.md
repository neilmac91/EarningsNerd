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
One task departs from this by the founder's decision (F60, option B, 2026-10-23): the account mail
of forgot-password and resend-verification carries the caller's address, in its body and in its
dedupe key, since both branches of each route must queue it before any lookup. Its bound is counted:
the request schema validates the address, and the per-address limit (3 an hour) and per-IP limit (20
an hour per route) bound each caller, but an IPv6 block rotates past the per-IP one at will, so the
process-wide `ACCOUNT_MAIL_LIMITER` caps both routes together at 60 an hour per API instance (120 at
the service's two) against the shared queue's 720 dispatches an hour, its dispatch ceiling; at 6 s a
delivery the queue drains 600 an hour, of which the cap is a fifth. A new exception needs the same:
a founder decision, validation where the value enters, per-caller limits and a process-wide cap taken
before every enqueue, the count written down, and an `EXEMPT` entry whose callers the gate pins.
Server-owned names still let a caller pick the company, so a route that needs no login also spends a
process-wide budget on each handoff. Size it, summed over every serving process and with every other
cap that bounds what public requests put on the same queue, under the queue's real drain: a queue that
dispatches one task at a time drains one per mean delivery time, which can be slower than its
dispatch-rate ceiling. A request that hands nothing off spends nothing, and one past the budget is
served without queuing.

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
token-gated internal job routes). It does follow the account mail's:
`test_account_mail_is_queued_only_behind_the_two_routes_limits` holds `queue_account_mail` to the
auth router's `_queue_account_mail`, that helper to the two routes, each after its two limits, and
the helper to the cap before its handoff. What bounds the filings route since 2026-10-23:
`_enqueue_visit_task` spends `VISIT_TASK_BUDGET` after its guard and before `enqueue_task`, so a
crawl of stored companies is served its rows and queues nothing past it. It allows 11 handoffs per 5
minutes per process, 22 across two instances (0.073/s). The queue dispatches one task at a time, at
most 0.2/s, so it drains 1/max(5 s, mean delivery time); a delivery execs a fresh Python child
(about 1.7 s of imports) and a history backfill paces 4 EFTS windows at 1 request/s, so a delivery
is taken to average 6 s. The account mail's cap feeds the same queue (0.033/s across two instances),
so the two public producers take at most 0.107/s, 64% of that drain, and leave 0.06/s (216 an hour)
to companyfacts syncs, operator jobs and tasks already queued; they stay within two thirds of the
drain while deliveries average up to 6.25 s and fill it at 9.375 s. If the account mail moves to a
queue of its own (F60's open item), its cap leaves this sum. The first size, 20, was set against the
0.2/s ceiling and took 80% of the drain; 15, sized without the account mail, took 80% once it was
counted. The synchronous SEC fetch, taken when nothing is stored in the requested forms and no
listing of the company within the 3-hour freshness TTL found them empty (a first view, once per TTL
for a company that has none of them, or, on every visit, a listing made only of rows another company
stores or rows it could not store), spends `LIVE_FETCH_LIMITER` (10 per minute per client IP in each
process, so up to 20 a minute across two instances) and answers 429 past it. A fetch is one SEC
request, the company's submissions JSON, on edgartools' bucket (1 request/s per process), so one
client takes at most a sixth of each process's pace while SEC answers. The payload gate requires a
pass-through to spend such a module-level budget first, a direct router `enqueue_task` to sit in a
route with `Depends(get_current_user)`, and every `EXEMPT` site to say whether a request with no
login reaches it, and its cap (`EXEMPT_PUBLIC_CAPS`). Tests:
`test_filings_routes.py::test_handoffs_past_the_budget_serve_stored_rows_and_queue_nothing_until_the_window_passes`,
`::test_visits_that_hand_nothing_off_spend_no_budget`,
`::test_live_fetches_past_the_per_ip_budget_answer_429_only_when_nothing_is_stored`,
`::test_a_client_spends_one_live_fetch_budget_whichever_company_or_forms_it_asks_for`,
`::test_a_live_fetch_is_one_sec_request`,
`::test_one_clients_live_fetches_take_at_most_a_sixth_of_the_sec_pace_they_wait_on`, which reads the
pace from `ci.yml`, and
`::test_the_public_handoff_caps_take_at_most_two_thirds_of_the_queue_drain_across_the_api_instances`,
which sums the cap of every producer the payload gate finds a request with no login reaching
(`public_queue_caps`) and reads the API's instance cap from `ci.yml` and the queue's provisioning from
`docs/DEPLOYMENT.md`. Its 6 s delivery time is an estimate, and the route's SEC reach is
review-checked. The same route's in-process refresh (`DURABLE_TASKS_ENABLED=false`, not the
production path) still takes the caller's canonical forms in the caller's order: it queues nothing
on the shared queue, is deduped per process while in flight, and stamps the per-filter freshness key
that the fast path reads.
