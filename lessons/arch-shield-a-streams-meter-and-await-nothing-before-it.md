# Shield a stream's meter, and let no await come between the work it counts and the event it meters on

Date: 2026-11-03   Area: arch

**Context**: The Multi-Period Analysis stream meters a fresh generation in the router when the narrative's
completion arrives (`backend/app/routers/analysis.py`, `stream_analysis`). E301 (#1990) moved the narrative's cache
write into a thread-pool unit, so the loop was free while the row was written. uvicorn speaks ASGI 2.3, so Starlette's
`StreamingResponse` cancels the stream's task when the client disconnects. anyio's shielded `to_thread.run_sync` holds
that cancel until the unit returns and then delivers it at the task's next checkpoint, which was the entry of the
meter's own `run_in_threadpool`. A client that read the narrative (the `token` frame) and closed while the row was
written went uncounted and got its lease back. A scripted Pro client could repeat that past the monthly cap, since
the count never rose. Writing the row before the `token` did not help. Behind the app's `BaseHTTPMiddleware` layers
each frame's send passes a checkpoint, so the cancel landed at the `token`'s send instead. The row was written,
nothing was counted, and the next request re-served the row from the cache for free.

**Rule**: A streaming route that meters (or settles any count) on a stream event shields that await with
`anyio.CancelScope(shield=True)`, as it shields the lease release in its `finally`. The work the meter counts (a
cache write, a provider call) is followed by that event with no await between. Any await there, a frame's send
included, is where a disconnect's cancel lands. A client that leaves before the work finishes is then not counted
and nothing is kept for it. Once the work is done it is counted, whether the client stayed or not.

**Evidence**:
- **Code.** `backend/app/routers/analysis.py` shields the meter in `stream_analysis`'s `event_stream`.
  `backend/app/services/trend_analysis/narrative.py` (`_publish`) sends the token, writes the cache row, then yields
  the completion.
- **Gate.** `backend/tests/unit/test_analysis_meter_survives_a_disconnect.py` drives the real app, its middleware
  included, with the router, the narrative, the admission and the meter, and only the model faked. In one case the
  client leaves while the model runs: no row is written, nothing is counted, and the lease is given back. In the
  other it leaves while the row is written, after it read the narrative: the row is written and counted once, and the
  lease is converted.
- **The four orders measured for #1990.** Only one counted the row: the write after the token, with the meter
  shielded. With the meter unshielded, or the write moved before the token (shielded or not), the row was written
  and left uncounted.
- **Precedent.** The Copilot's ask stream settles its charge in a shielded `finally` the same way
  (`backend/app/routers/summaries.py`).
