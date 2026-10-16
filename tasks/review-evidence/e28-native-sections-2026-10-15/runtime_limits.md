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

- **Time budget.** The parse starts once the document is fetched, and the enrichment stage awaits it
  before building the excerpt, as it did before E28. `get_filing_sections` bounds it at 30 s (40 s
  for a 20-F), counting time queued behind another parse, and returns None when that runs out; the
  excerpt is then the regex excerpt, stored for good like any other. The excerpt build and XBRL then
  share the usual fresh 18 s join (`CONTEXT_ENRICHMENT_TIMEOUT_SECONDS`), exactly as before E28. On
  one CPU the four largest documents take 2.4 to 2.9 s for a regex excerpt and up to 2.4 s to
  assemble parsed sections when nothing else runs
  ([`excerpt_build_times.jsonl`](excerpt_build_times.jsonl), from
  [`excerpt_build_times.py.txt`](excerpt_build_times.py.txt)).
- **What changed against the `obj()` path.** The `obj()` path started with the fetch, so its 30 s
  (40 s) ran from the fetch's start; the local parse needs the fetched document, so its bound runs
  from the fetch's end. One large filing alone parses in 3 to 6.4 s. The fetch's 15 s is per attempt
  (up to three, with backoff), so with every step at its bound together the 120 s backstop can
  pre-empt the AI fallback, as it could before E28 (the `PIPELINE_TIMEOUT_SECONDS` comment).
- **Cancellation.** A parse still queued when its waiter is cancelled, by its own bound or by a
  disconnect, never runs. A running parse is joined at cleanup, before the generation slot and the
  in-flight leadership are released (`backend/tests/unit/test_durable_request_ownership.py`). That
  holds where `DURABLE_TASKS_ENABLED` is on: the API service since 2026-10-08, and the task worker.
  Elsewhere a running parse finishes on its own.
- **Stream silence.** The longest silent stretch is the parse wait after the 20% frame (at most 30 s,
  40 s for a 20-F) or the 18 s join, plus under a second. The client aborts after 120 s with no frame
  (`STREAM_TIMEOUT_MS`, reset on every frame, in `frontend/features/summaries/api/summaries-api.ts`).
  The request-timeout middleware skips stream paths (`backend/main.py`), and Cloud Run's 600 s
  request timeout covers the stream. No heartbeat is needed, and the frame sequence is a locked
  contract (CLAUDE.md rule 6).
- **Stored excerpts.** A filing with a stored excerpt, fresh or past its 24-hour window, is not
  parsed: `get_or_cache_excerpt` returns the stored excerpt as it is. This covers regenerations,
  including the drain on the pregenerate job.
- **Size cap.** Documents over 16,000,000 characters are not parsed. The largest golden document with
  sections is JPMorgan's 12.9M (6.2 s above). ASML's 24.9M-character 20-F yields no sections and is
  skipped.
- **Other callers.** The eval runner and the Copilot bootstrap call the same seam, so they share the
  single worker. CI's evaluation runs two filings at a time (`EVAL_CONCURRENCY=2`), so a parse there
  waits behind at most one other, well inside the seam's 30 s (40 s for a 20-F) bound.

## End to end under a burst

[`burst_end_to_end.py.txt`](burst_end_to_end.py.txt) runs whole summary generations through
`stream_filing_summary`, several at once on one pinned CPU, with the real section parse, excerpt
build and enrichment join. The document fetch and the provider are stubbed. XBRL is either stubbed
(0 s) or replaced by 3 s of pure-Python CPU per generation on the SEC pool, a stand-in for the
instance parse a first-time large filing runs. The documents are the four largest golden ones
(JPMorgan, Prologis, Alibaba, TSMC). Results are in [`burst_end_to_end.jsonl`](burst_end_to_end.jsonl):

| design | XBRL CPU | 2 at once | 4 at once |
|---|---|---|---|
| this PR: awaited before a fresh 18 s join, bounded at 30/40 s (two runs each) | 0 s | 2 native | 4 native (slowest 28.6 to 30.3 s) |
| the same | 3 s | 2 native | 2 or 3 native, the rest regex (slowest 43 to 45 s) |
| the parse inside the 18 s join for 12 s of it (superseded, `a6cd05d`) | 0 s | — | 1 native, 3 excerpts dropped |
| an 18 s wait, one 18 s deadline, a 10 s build floor (superseded, `6e1b19b`) | 0 s | 2 native | 3 native, 1 regex |
| the same | 3 s | 2 excerpts dropped | 4 excerpts dropped |
| a 10 s wait before a fresh 18 s join (superseded) | 0 s | 1 native, 1 regex | 1 native, 3 regex |
| a 15 s wait before a fresh 18 s join (superseded) | 3 s | 1 native, 1 regex | 4 regex |
| an 18 s wait before a fresh 18 s join (superseded) | 3 s | 1 native, 1 regex | 4 excerpts dropped |

This PR's design dropped no excerpt in any of its 16 runs (one to four documents, both XBRL loads), and
XBRL finished in every generation. A dropped excerpt is the review's blocker: the summary gets no
excerpt at all. A regex excerpt is stored for good, so a short wait turns a moment of load into a
lasting regex excerpt. Bounding the wait inside the request budget (the superseded designs) cost
native excerpts and, once XBRL's own CPU work was in the mix, dropped excerpts; awaiting the parse
as before E28 costs latency under a burst instead. In an earlier series, one single-document run
stalled for 31 s with nothing else on the machine using the CPU, and its excerpt was dropped
(superseded design, `burst_end_to_end.jsonl`); it did not reproduce in five more runs.

## Not measured here

- Production memory and RSS.
- Memory that the allocator keeps after a large parse.
- Behaviour on documents larger than the golden set's.

Raising a job's memory is a founder capacity decision.
