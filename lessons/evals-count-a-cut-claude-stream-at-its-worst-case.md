# Count a Claude stream cut before its message_delta at its worst case, never as a finished reply

Date: 2026-10-25   Area: evals

**Context**: The trend-depth harness spends a real Anthropic key under a ceiling it checks against a
ledger of the calls it made. Three reviews of its API path found the ledger could read less than the key
had spent. Retries (a 529, a stream reset mid-reply) all went out under the one reservation taken for the
call, and a failed attempt was never logged, though a stream that has started can be billed. Then an
offline run against the real SDK (anthropic 2.3.0, through an httpx2 mock transport) found a quieter case.
When the server closes a stream cleanly before `message_delta`, `get_final_message()` raises nothing: it
returns the partial message, with `stop_reason` None and the `output_tokens` that `message_start`
reported (1). The harness would have recorded that as a finished reply that cost almost nothing, and
parsed half a reply as the whole one. The SDK updates the output count only on `message_delta`, at the
end of the message, so no attempt cut short can say what it generated.

**Rule**: Wherever code streams from the Anthropic SDK and accounts for spend:
1. Treat a final message whose `stop_reason` is None as a cut attempt, not a reply.
2. Log an attempt that failed after `message_start` but before `message_delta` (an exception mid-stream,
   an early end, an interruption) at its worst case before anything else happens. The worst case is the
   prompt as `message_start` reported it, plus the full `max_tokens`. An attempt whose `message_delta`
   arrived is whole even if its connection then failed: keep the reply and log its own cost. An attempt
   that failed with an error before `message_start` was not billed.
3. Admit every attempt, retries included, against the ceiling on its own. Reserve its worst case in the
   ledger before it is sent, and release that only once its own cost is on disk, so an attempt stopped
   in between (a kill, a second Ctrl-C) leaves its worst case counted.

The ledger can then overstate spend but never understate it. The Console stays the exact record, and a
spend limit there is the stop that also covers other sessions and checkouts.

**Evidence**: `backend/evals/trend_depth/providers.py` (`_call_anthropic`, `_cut_cost`,
`_call_anthropic_metered`). The tests are in `backend/tests/unit/test_trend_depth_providers.py`:
`test_a_stream_that_ends_before_the_message_does_is_a_cut_attempt`,
`test_a_finished_reply_whose_connection_then_failed_is_kept`,
`test_a_cut_attempt_is_logged_at_its_worst_case_before_the_retry` and
`test_each_retry_is_admitted_against_the_ceiling_again`. The SDK's accumulator sets `usage.output_tokens`
only on `message_delta` (`anthropic/lib/streaming/_messages.py`, `accumulate_event`).
