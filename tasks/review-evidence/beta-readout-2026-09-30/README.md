# September 30 beta readout evidence

A live PostHog literal projection returned three invented rows with the expected
21-column shape. The unchanged released v1 consumer read those rows and reported
one view and one paired complete request with a 1,000 ms duration, no diagnostics
and no conflicting event UUIDs. **Export completeness remains false**: the actual
response omitted pagination metadata. This is a synthetic compatibility receipt,
not customer observation, consent, a cohort result or beta admission.

## Retained evidence

- [Exact provider-returned query](literal-projection.hogql): literal rows only;
  no events or persons table access.
- [Provider response](provider-response.json): actual result object selected from
  the retained tool envelope and serialized as JSON. No metadata was filled in.
- [Synthetic parameters](parameters.json) and [consumer output](readout.json).
- [Receipt](receipt.json): byte lengths, SHA-256 hashes, consumer release/hash and
  extraction transformations. The original tool envelope remains private because
  it also contains connection metadata; its hash provides the custody reference.

The consumer was invoked once for this observation, with no provider/model call
from the consumer. Its three input hashes match the retained artifacts. Saved
insight metadata and a UI row count were not promoted to pagination evidence.
No runtime, consumer, contract test, flag or pricing behavior changed here.

## Next executable step

The connector currently lacks `batch_export:read` and `batch_export:write`.
After reconnecting with these scopes, inspect the available file-download export
tools and confirm whether this team can use the HogQL model. Its documented closed
beta availability is not established by scope access alone. Test only a tiny
literal export before considering customer data. Retain the actual run status,
record count and every downloaded part; design and independently review an
explicit input format for those artifacts before using them for a cohort readout.

PostHog directs bulk, recurring and third-party-connector exports to its
[supported export paths](https://posthog.com/docs/api/queries). The
[file-download export documentation](https://posthog.com/docs/cdp/file-download-exports)
describes run/file delivery, which does not supply the v1 query response's
pagination fields. No completed export or new adapter is claimed here.

The [operator runbook](../../readiness-2026-09-21/beta/summary-v1-readout.md)
retains the existing consumer semantics and the remaining live verification steps.
