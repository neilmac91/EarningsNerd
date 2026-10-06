# Guard a loader with a synchronous in-flight ref when two effects can start it in one commit

Date: 2026-10-05   Area: frontend

**Context**: FilingViewer loads the filing text from two effects: the citation-request effect (a chip
asked for a highlight) and the first-activation effect (the Filing tab became active). Both decide by
reading `statusRef.current === 'idle'`, a render-time mirror of state. A chip activation on a closed
pane fires both in the same commit, and `setStatus('loading')` from the first has not rendered when
the second reads the mirror, so the viewer fetched the content twice in parallel and the answer that
settled last won. A unit spec that queued one mocked answer for the first call saw the second call's
default answer instead, which is how it surfaced (EN-01).

**Rule**: When more than one effect can start the same async work in one commit, the work itself
carries a synchronous guard: a ref set before the first `await` and cleared in `finally`. State
mirrors read during effects describe the last render, not the current pass, so they cannot
serialize starts. Pin it with a spec that counts the calls after the double trigger.

**Evidence**: `frontend/features/filings/components/copilot/FilingViewer.tsx` (`inFlight` ref in
`load`). `tests/unit/FilingViewerEmbedded.spec.tsx` "repeated activation of the same citation
highlights again each time" asserts one fetch for the chip-driven first activation; without the guard
it is two.
