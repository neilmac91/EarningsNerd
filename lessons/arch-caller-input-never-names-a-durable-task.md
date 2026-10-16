# Never let a public caller's input name a durable task or key its dedupe

Date: 2026-10-16   Area: arch

**Context**: `GET /api/filings/company/{ticker}` needs no login and has no rate limiter. In
durable mode its DB-first branch handed Cloud Tasks a refresh whose payload carried the caller's
`?filing_types=` list. `enqueue_task` names a task with `sha256(key:body)`, body included, and
the router's per-process guard keys on the payload too. So every distinct value queued a new task,
with no 409 from Cloud Tasks and no local suppression. That held for junk forms and for known
forms in another order or spelling: 40 GETs queued 40 tasks. Each task costs a worker child
process and an SEC fetch on the 0.2 dispatch/s queue that companyfacts syncs, history backfills
and operator jobs share.

**Rule**: A background or durable task started by a public request carries only server-owned
identity: ids the server resolved and fixed vocabularies, never the caller's string. When the
caller's choice must shape the work, first validate it where it enters (CLAUDE.md rule 9) into a
bounded canonical set, and count how many distinct payloads one company can produce per dedupe
bucket. The response can still filter per request. A fix is proven by sending N distinct caller
values through the real task-naming code, with only the transport faked, and counting the tasks.

**Evidence**: `enqueue_task` in `backend/app/services/durable_tasks.py` hashes whatever body it
is given, by design, so the fix belongs to the caller: `backend/app/routers/filings.py` enqueues
`company_list_forms()`, and `backend/app/services/filing_list_service.py::requested_filing_types`
reads each entry as its SEC form and drops unknown ones. Gate:
`backend/tests/unit/test_filings_routes.py::test_filing_types_values_cannot_mint_durable_refresh_tasks`
(before the fix: 40 junk values queued 40 tasks, and 5 known-form variants queued 4). The other
enqueue sites carry a resolved company id (`routers/analysis.py`) or sit behind operator auth
(`services/internal_task_runner.py`); new sites are review-checked.
