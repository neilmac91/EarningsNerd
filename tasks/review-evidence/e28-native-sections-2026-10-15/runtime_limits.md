# Runtime limits of the local section parse (E28, 2026-10-16)

PR #1347 moves the summary's section parse off edgartools' network path. It becomes CPU work on the
document the pipeline already fetched, on the request path. This record covers what that costs on
the one-vCPU deploy shapes and what bounds it. Everything below was measured offline (no network),
from the golden documents and the code at the head that adds this file.

## Deploy shapes

- **API service**: `--cpu=1 --memory=1Gi --concurrency=40` (`.github/workflows/ci.yml`, the "Deploy
  Cloud Run service" step). It runs up to `MAX_CONCURRENT_GENERATIONS = 6` generations per process
  (`backend/app/config.py`).
- **Task worker**: `--cpu=1 --memory=2Gi --concurrency=1`, one generation per delivery.
- **Pregenerate job**: one vCPU and 1 GiB, per `tasks/gcp-deploy-runbook.md`. Its drain ran out of
  memory on 2026-09-16 after 22 sequential regenerations (`docs/OPERATIONS.md`), while `obj()` still
  worked.

## A burst of four large documents

[`burst_through_seam.py.txt`](burst_through_seam.py.txt) sends four of the largest golden documents
through `xbrl_service.get_filing_sections` at once, on one pinned CPU (`taskset -c 0`):

- JPMorgan's 10-K, 12.9M characters;
- Prologis's 10-K, 11.5M characters;
- Alibaba's 20-F, 11.7M characters;
- TSMC's 20-F, 10.4M characters.

While the parses run, the script submits a no-op to the four-thread SEC pool every 0.5 s, with the
15 s timeout that the XBRL instance extraction uses, and samples the event loop's lag. The "shared"
mode routes the parse back to the SEC pool, as it ran before this change. Results are in
[`burst_results.jsonl`](burst_results.jsonl). Each run returned all three sections for all four
filings.

| | one parse worker (this PR) | the shared SEC pool (before) |
|---|---|---|
| parses finished at | 6.2, 9.7, 13.5, 17.6 s | 13.8, 15.1, 16.4, 18.5 s |
| longest wait for a SEC-pool no-op | 0.11 s | 13.27 s |
| longest event-loop lag | 281 ms | 729 ms |
| peak memory above the loaded documents | +297 MB | +513 MB |

The CPU is the bound either way, so the total time is the same. The single worker:

- finishes its first parse three times sooner;
- holds about 40% less memory at peak;
- keeps the SEC pool free.

On the shared pool, a timed SEC call waited 13.27 s against a 15 s timeout. A breaker-wrapped call
that times out counts as a circuit-breaker failure (`backend/app/services/edgar/circuit_breaker.py`).
Five in a row open the breaker for 30 s, and that breaker also guards the primary-document fetch
(`backend/app/services/edgar/compat.py`). One parse at a time is a module constant in
`backend/app/services/edgar/async_executor.py`, not a Setting: it describes the parser's cost on one
vCPU, and `USE_EDGARTOOLS_SECTIONS` is already the kill switch.

## On the request path

- **Time budget.** The parse starts once the document is fetched and resolves inside the 18 s
  enrichment join (`CONTEXT_ENRICHMENT_TIMEOUT_SECONDS`), alongside XBRL. The documented budget
  (15 + 18 + 75 s against the 120 s backstop) is unchanged. A parse not done by the join leaves the
  excerpt to the regex extractor, as before E28.
- **Cancellation.** A parse still queued when its waiter is cancelled, by the join's deadline or a
  disconnect, never runs. A running parse is joined at cleanup, before the generation slot and the
  in-flight leadership are released (`backend/tests/unit/test_durable_request_ownership.py`). That
  holds where `DURABLE_TASKS_ENABLED` is on: the API service since 2026-10-08, and the task worker.
  Elsewhere a running parse finishes on its own.
- **Stream silence.** The longest silent stretch is the 18 s join plus under a second. The client
  aborts after 120 s with no frame (`STREAM_TIMEOUT_MS`, reset on every frame, in
  `frontend/features/summaries/api/summaries-api.ts`). The request-timeout middleware skips stream
  paths (`backend/main.py`), and Cloud Run's 600 s request timeout covers the stream. No heartbeat is
  needed, and the frame sequence is a locked contract (CLAUDE.md rule 6).
- **Stored excerpts.** A filing with a stored excerpt, fresh or past its 24-hour window, is not
  parsed: `get_or_cache_excerpt` returns the stored excerpt as it is. This covers regenerations,
  including the drain on the pregenerate job.
- **Size cap.** Documents over 16,000,000 characters are not parsed. The largest golden document with
  sections is JPMorgan's 12.9M (6.2 s above). ASML's 24.9M-character 20-F yields no sections and is
  skipped.
- **Other callers.** The eval runner and the Copilot bootstrap call the same seam, so they share the
  single worker. CI's evaluation runs two filings at a time (`EVAL_CONCURRENCY=2`), so a parse there
  waits behind at most one other, well inside the seam's 30 s (40 s for a 20-F) bound.

## Not measured here

- Production memory and RSS.
- Memory that the allocator keeps after a large parse.
- Behaviour on documents larger than the golden set's.

Raising a job's memory is a founder capacity decision.
