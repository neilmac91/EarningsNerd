# Design Spec — Extract the summary pipeline into `run_summary_pipeline()`

> **Status:** Implemented. Shipped in #268 (Phase 1 — pipeline extraction into
> `app/services/summary_pipeline.py`). Retained as the design record for backlog item **M7**;
> this captures the rationale and proposed approach that preceded implementation.

## 1. Problem

The user-facing SSE path and the batch/cron path generate summaries through two **separately
maintained copies of the same pipeline**:

- **Streaming:** the `stream_summary()` async generator inside the endpoint at
  `app/routers/summaries.py:226–802` (~580 lines living in the router).
- **Batch/cron:** `generate_summary_background()` at
  `app/services/summary_generation_service.py` (`generate_summary_background`).

They duplicate ~10 stages — filing validation, XBRL fetch, excerpt extraction, excerpt/XBRL
join, AI summarization, financial-fact normalization, persistence, usage increment — and have
**already drifted**:

| Behaviour | Streaming path | Background path |
|-----------|:--------------:|:---------------:|
| Quality gate (`assess_quality`) | ✅ | ❌ missing |
| Fallback summary on AI timeout (`generate_xbrl_summary`) | ✅ | ❌ silently errors |
| Persists partial results | ✅ | ❌ discards |
| Heartbeats / progress events | ✅ | progress only |

Drift is the real cost: a fix or quality improvement made in one path is silently absent from the
other. The motivation for M7 is **a single source of truth for the pipeline**, with the SSE
transport concern kept thin in the router.

## 2. Goals / non-goals

**Goals**
- One pipeline implementation consumed by both the SSE endpoint and the background path.
- Router keeps only HTTP concerns (rate limit, guest quota, cached-summary short-circuit, SSE
  wire formatting). Business logic moves to the service.
- Zero behaviour change to the SSE contract in Phase 1 (same event types, same wire shape).
- Converge the two paths' quality-gate / fallback / partial-persistence behaviour (Phase 2).

**Non-goals**
- No change to the AI prompt, model, or summary content.
- No change to the SSE event JSON shape the frontend consumes.
- No new endpoints.

## 3. Proposed design

### 3.1 A transport-agnostic pipeline generator

Introduce a new module `app/services/summary_pipeline.py` exposing:

```python
async def run_summary_pipeline(
    *,
    filing_id: int,
    user_id: int | None,          # IDs only — never pass detached ORM objects
    force: bool,
    client_ip: str | None,        # for guest/telemetry; no FastAPI Request leaks in
    telemetry_ctx: TelemetryCtx,  # distinct_id, entry_point, etc. captured by the caller
    heartbeat_interval: float = settings.STREAM_HEARTBEAT_INTERVAL,
) -> AsyncIterator[PipelineEvent]:
    ...
```

The generator owns its **own DB session** for its whole lifetime (as the streaming generator does
today at `summaries.py:258`, closed in `finally`), and queries the filing fresh by id to avoid
cross-session detachment. It yields structured **domain events**, not SSE strings:

```python
@dataclass(frozen=True)
class Progress:    stage: str; message: str; percent: int; elapsed_seconds: int | None = None
@dataclass(frozen=True)
class Chunk:       content: str
@dataclass(frozen=True)
class Partial:     message: str; summary_id: int
@dataclass(frozen=True)
class Complete:    summary_id: int
@dataclass(frozen=True)
class Failed:      message: str; summary_id: int | None = None

PipelineEvent = Progress | Chunk | Partial | Complete | Failed
```

Heartbeats are just periodic `Progress` events emitted from the same fetch/summarize loops that
exist today (`summaries.py:426–441`, `564–591`) — they stay inside the pipeline because they are
driven by pipeline timing, not by the transport.

### 3.2 The SSE endpoint becomes an adapter

```python
@router.post("/filing/{filing_id}/generate-stream")
async def generate_stream(filing_id: int, request: Request, current_user=Depends(get_current_user_optional)):
    enforce_rate_limit(request, SUMMARY_LIMITER, ...)          # HTTP concern — stays
    # guest quota + cached-summary short-circuit — stay in the router
    telemetry_ctx = build_ctx(request, current_user)            # capture once, outside the generator
    async def event_stream():
        async for ev in run_summary_pipeline(
            filing_id=filing_id, user_id=getattr(current_user, "id", None),
            force=force, client_ip=request.client.host, telemetry_ctx=telemetry_ctx,
        ):
            yield to_sse(ev)                                    # the ONLY transport mapping
    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

`to_sse(ev)` is a tiny pure function mapping each dataclass to the existing
`data: {json}\n\n` shape — preserving the current `progress|chunk|partial|complete|error`
event names exactly.

### 3.3 The background path drains the same generator

```python
async def generate_summary_background(filing_id: int, user_id: int | None = None, force: bool = False):
    terminal: PipelineEvent | None = None
    async for ev in run_summary_pipeline(filing_id=filing_id, user_id=user_id, force=force,
                                          client_ip=None, telemetry_ctx=batch_ctx()):
        if isinstance(ev, (Complete, Partial, Failed)):
            terminal = ev
    return terminal   # cron/batch ignores Progress/Chunk; gets quality gate + fallback for free
```

This is what closes the drift: the background path inherits the quality gate, the fallback, and
partial-result persistence simply by reusing the generator.

## 4. Extraction hazards (from the current-code survey)

These must be preserved exactly during the move:

1. **Nested timeouts** — hard pipeline timeout (`asyncio.timeout`, `summaries.py:265`), the
   18s excerpt/XBRL join (`:511–514`), and the 3s heartbeat polls. Their interaction is load-bearing.
2. **Task cancellation** — the AI task is cancelled and the fallback invoked on the in-stage
   timeout (`:574–584`). Cancellation/`CancelledError` semantics must survive.
3. **Session lifecycle** — the generator creates its own session and nested functions spawn
   fresh `SessionLocal()`s for thread-pool safety (`:353, :384`). The extracted function must take
   **ids, not ORM objects**, and never hand detached objects across sessions.
4. **Closures over request scope** — telemetry context and client IP are captured *outside* the
   generator today (`:238–242`). The extracted signature passes these explicitly; nothing reads
   `Request` inside the pipeline.
5. **Order-dependent state** — `filing_text → excerpt → xbrl_metrics` feed later stages; the
   concurrency (XBRL task started early at `:365`) must be retained, not serialized.
6. **`PIPELINE_TIMEOUT_SECONDS` duplication** — currently declared twice with different values
   (`:232` vs the top-of-file constant). Collapse to one config-driven value during extraction.

## 5. Phased rollout (each phase independently shippable + tested)

- **Phase 1 — pure extraction, zero behaviour change.** Create `summary_pipeline.py`, move the
  generator body in, define event dataclasses + `to_sse()`. The SSE endpoint becomes the adapter.
  Background path untouched. **Gate:** `tests/integration/test_summaries_flow.py`,
  `test_stream_latency.py`, `test_summary_stream_heartbeat.py`, `test_concurrent_streams.py` all
  pass unchanged; manual SSE smoke shows identical event sequence.
- **Phase 2 — converge the background path.** Reroute `generate_summary_background` to drain the
  generator. **Behaviour change (intended):** batch summaries now get the quality gate, fallback,
  and partial persistence. **Gate:** new test asserting a forced-timeout batch produces a fallback
  summary instead of a silent error.
- **Phase 3 — delete the dead duplicate** in `summary_generation_service.py` and shared helpers
  that are now only called by the pipeline. **Gate:** full suite + grep for dangling references.

## 6. Open decisions (need your call)

1. **Module home** — new `summary_pipeline.py` (recommended, clean seam) vs. growing
   `summary_generation_service.py`.
2. **Phase 2 scope now or later** — converging the background path is the high-value half but it
   *changes batch behaviour*. Ship Phase 1 alone first, or go straight through Phase 2?
3. **Event type** — frozen dataclasses (recommended, type-safe) vs. plain dicts (less churn).

## 7. Risks

- Highest risk is Phase 1 subtly altering timeout/heartbeat timing → frontend progress regressions.
  Mitigated by the latency/heartbeat integration tests and a byte-level diff of the event sequence
  for a fixed filing before/after.
- Phase 2 changes what cron persists; if any dashboard counts "summaries generated" it may shift
  when partials start being stored. Low impact, called out for awareness.
