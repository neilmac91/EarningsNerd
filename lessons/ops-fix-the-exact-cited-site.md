# Fix and test the plan's exact cited site, not an adjacent manifestation

Date: 2026-07-06   Area: ops

**Context**: Executing F2, the plan cited latent bug L1 as "poll-forever on `partial`" at the progress poll. Investigation found the SSE stream parser already handled a terminal `partial` frame correctly; pinned that with a test and declared L1 closed — while the actually-cited line (the poll's `refetchInterval`) moved into the new hook still missing `partial` from its terminal set, so a `partial`-ending run still polled at 1s forever. The plan author caught it in a base-vs-head audit.

**Rule**: When a plan/report cites a specific site (file:line, symbol, function) for a bug, fix and test THAT site — open the exact line and confirm the defect is gone there. A fix to a related/adjacent manifestation does not discharge the citation; if your investigation redirects to a different site, say so explicitly and confirm the original is either also fixed or provably not the bug. "I fixed a partial-handling bug" ≠ "I fixed the cited partial-handling bug."

**Evidence**: `page-client.tsx:323` (the poll's `refetchInterval`); backend writes three terminal stages via `record_progress(..., "partial")`, the poll stopped on two; F2 / latent bug L1.
