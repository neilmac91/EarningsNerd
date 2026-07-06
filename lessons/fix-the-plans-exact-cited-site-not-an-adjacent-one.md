# When a plan cites a specific site for a bug, fix and test THAT site — an adjacent fix doesn't discharge the citation

**Area:** process · **Date:** 2026-07-06

Executing F2, the plan cited latent bug L1 as "poll-forever on `partial`" at `page-client.tsx:323` —
the *progress poll*. I investigated, found the SSE *stream parser* already handled a terminal `partial`
frame correctly, pinned that with a test, and declared L1 closed — while the actually-cited line (the
poll's `refetchInterval`) moved into the new hook still missing `partial` from its terminal set. The
backend writes three terminal stages (`record_progress(..., "partial")`), the poll stopped on two, so a
`partial`-ending run still polled at 1s forever. The plan author caught it in a base-vs-head audit. I'd
fixed a *real, adjacent* facet and pattern-matched it to the citation instead of verifying the cited
site itself.

**Rule:** when a plan/report cites a specific site (file:line, symbol, function) for a bug, fix and test
THAT site — open the exact line and confirm the defect is gone there. A fix to a related/adjacent
manifestation does not discharge the citation; if your investigation redirects to a different site,
say so explicitly and confirm the original is either also fixed or provably not the bug. "I fixed a
partial-handling bug" ≠ "I fixed the cited partial-handling bug."
