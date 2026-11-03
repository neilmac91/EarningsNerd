# Shield a stream's meter and the work it waits on, and let no await come between that work and the metered event

Date: 2026-11-03   Area: arch

**Context**: The Multi-Period Analysis stream meters a fresh generation in the router when the narrative's
completion arrives (`backend/app/routers/analysis.py`, `stream_analysis`). E301 (#1990) moved the narrative's cache
write into a thread-pool unit after the `token` frame, which carries the whole narrative. uvicorn speaks ASGI 2.3, so
Starlette's `StreamingResponse` cancels the stream's task when the client disconnects. A cancel can land in two places:
- **During the write.** anyio's shielded `to_thread.run_sync` holds a cancel that arrives while the unit runs. It then
  delivers it at the task's next checkpoint, which was the entry of the meter's own `run_in_threadpool` (round 1 of
  the review).
- **Before the write starts.** The unit's entry checkpoint and its wait for one of the 40 worker tokens of anyio's
  default limiter both come before that shield. With the limiter full, a cancel landed in the wait. No row was
  written, nothing was counted, and the lease was given back (round 2, `(rows, counted, leases) = (0, 0, 0)` on the
  real app).

Either way, a client that read the narrative and closed went uncounted. A scripted Pro client could repeat that past
the monthly cap, since the count never rose.

Writing the row before the `token` did not help. Behind the app's `BaseHTTPMiddleware` layers each frame's send passes
a checkpoint, so the cancel landed at the `token`'s send instead. The row was written, nothing was counted, and the
next request re-served the row from the cache for free.

**Rule**: A streaming route that meters (or settles any count) on a stream event does three things:
1. It shields that await with `anyio.CancelScope(shield=True)`, as it shields the lease release in its `finally`.
2. Once the client has been sent what is counted, it shields the work the count waits on (a cache write) too. A
   thread unit's entry and its wait for a worker thread each take a cancel before the unit's own shield.
3. The metered event follows that work with no await between. Any await there, a frame's send included, is where a
   disconnect's cancel lands.

A client that leaves before it is sent what is counted is not counted, and nothing is kept for it. Once it has been
sent, the run completes and is counted, whether the client stayed or not.

**Evidence**:
- **Code.** `backend/app/routers/analysis.py` shields the meter in `stream_analysis`'s `event_stream`.
  `backend/app/services/trend_analysis/narrative.py` (`_publish`) sends the token, then writes the cache row inside a
  shield, then yields the completion.
- **Gate.** `backend/tests/unit/test_analysis_meter_survives_a_disconnect.py` drives the real app, its middleware
  included, with the router, the narrative, the admission and the meter, and only the model faked. The client leaves at
  one of three steps:
  - while the model runs: no row is written, nothing is counted, and the lease is given back;
  - after it read the narrative, while the write waits for a worker thread with every token of anyio's default
    limiter held: the row is written once a thread frees, it is counted once, and the lease is converted;
  - after it read the narrative, while the row is written: the same.
- **The orders measured for #1990.** Only one counted every run the client had read: the write after the token, the
  write and the meter both shielded. With the meter unshielded, or the write moved before the token (shielded or not),
  a row was written and left uncounted. With only the meter shielded, a full thread limiter left nothing written or
  counted.
- **Another design.** The Copilot's ask stream reaches the same end another way. It starts its metering write when the
  provider is called, as a future no cancel stops, and adopts it in a shielded `finally`
  (`backend/app/routers/summaries.py`). That design also covers an await before the event.
