# Count a completion event on the transition the server names, never on the client's guess

Date: 2026-10-13   Area: frontend

**Context**: the wording review's completion event (`wording_review_completed`, the E3 measure of
the "what changed" build) first fired when the client's optimistic label count reached the total.
Two labels pressed within milliseconds each saw the count cross the line, so the event fired
twice; answers landing out of order left the cache incomplete while the server was complete. The
lens's proposed fix, a `scope` on the mutation so labels go out one at a time, was shown
insufficient by both refuters: a queued mutation's `onMutate` still runs at once, so a scoped
probe still double-counted. React Query serializes the requests, not the optimistic writes.

**Rule**: a "this just completed" event is counted on a transition flag the server returns with
the write's answer (`completed_now`: true only on the write that completed the queue), never on a
count the client derives from its own optimistic state. Serialize writes with `scope` where order
matters, apply optimistic state for the row that was pressed, and let the server's answer replace
it; the receipt, the completion time and the event all come from the answer. When the server
cannot name the transition, decide against the cache at answer time (the state just before the
answer is written), not at press time.

**Evidence**: `backend/app/services/section_review_service.py::set_label` (`completed_now`),
`frontend/features/summaries/hooks/useWordingReview.ts` (`onSuccess`), pinned by
`frontend/tests/unit/wording-changes.spec.tsx` ("the completion event follows the server’s
transition, not the client’s guess": a client-count mutant fails three tests). Review-checked for
the next completion event; this instance is gated by that spec.
