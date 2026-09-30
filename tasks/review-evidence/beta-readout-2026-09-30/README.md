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

After the founder reconnected, the export tools became available. One exact-query
literal export was submitted in confirmed EarningsNerd project 117863. PostHog
returned HTTP 403: `HogQL batch exports are not enabled for this team.` The
[capability receipt](export-capability.json) retains the scope, configuration,
private request/response custody hashes and outcome. No run ID, completed record
count or files were returned, and no download or unchanged retry followed.

Request HogQL batch-export beta access from PostHog support for project 117863.
Once access is confirmed, verify a tiny literal export before considering customer
data. Retain the actual run status, record count and every downloaded part; design
and independently review an explicit input format for those artifacts before
using them for a cohort readout. Broader events/persons exports are not a substitute
for the precisely scoped query.

PostHog directs bulk, recurring and third-party-connector exports to its
[supported export paths](https://posthog.com/docs/api/queries). The
[file-download export documentation](https://posthog.com/docs/cdp/file-download-exports)
describes run/file delivery, which does not supply the v1 query response's
pagination fields. No completed export or new adapter is claimed here.

The [operator runbook](../../readiness-2026-09-21/beta/summary-v1-readout.md)
retains the existing consumer semantics and the remaining live verification steps.
