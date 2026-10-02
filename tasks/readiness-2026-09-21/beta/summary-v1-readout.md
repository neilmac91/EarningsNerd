# Prospective summary evidence readout v1

The existing `posthog.hogql` remains the historical, unversioned diagnostic. Use
[posthog-v1-export.hogql](posthog-v1-export.hogql) and [readout_v1.py](readout_v1.py)
for the separately versioned view/request contracts. This is preparation, not a live
receipt, cohort result, invitation or evidence of analytics consent.

Freeze the eligible account IDs from `db_roster.sql`, explicit founder/staff/test
exclusions, UTC half-open window and exact executed query before observation. Keep
all participant data and exports private. The founder's intended cohort is 10–20
people and support target is within two business days; those decisions do not supply
individual consent, eligible IDs, actual usefulness or a start date. No participant
names are required for preparing these tools.

The steps below describe the existing v1 query-response input contract. The live
export route is still a prerequisite; see [Supported export route remains a
prerequisite](#supported-export-route-remains-a-prerequisite) before collecting data.

1. Prepare the exact query by replacing its synthetic account IDs and UTC window.
   Scope it to the three named events and selected fields for that roster. Do not
   scan all customers or join current person identities to fill missing event-time
   identities. The v1 consumer accepts a retained raw JSON query response
   (`columns`, `results`, `hasMore` and warnings); a screenshot, coerced CSV or
   manually inferred event set cannot substitute. A batch export needs a separately
   reviewed input contract before it can supply this consumer.
2. Save a private parameter file, for example:

   ```json
   {"window_start":"2026-09-28T00:00:00Z","window_end":"2026-10-12T00:00:00Z",
    "eligible_account_ids":["1001","1002"],"excluded_account_ids":[]}
   ```

   IDs are distinct canonical positive decimal strings. Exclusions are removed from
   the frozen input roster; the output retains every remaining account, even if it
   has no event. Windows use whole-second UTC boundaries.
3. Run locally, with no database or network dependency:

   ```bash
   python3 tasks/readiness-2026-09-21/beta/readout_v1.py \
     --events /PRIVATE/events.json --parameters /PRIVATE/parameters.json \
     --query /PRIVATE/executed-query.hogql --output /PRIVATE/readout.json
   ```

   Output is exclusive-create, mode0600, with hashes of all three inputs. Preserve
   the originals beside it. Input files are bounded to16MiB and the query/consumer
   to10,000rows. `hasMore` must be explicitly false, the result below the cap and
   warnings absent, and any response offset exactly integer zero before
   `export_complete_observed` can be true. That observation
   is not proof that event capture was complete or that the operator used the right
   query/roster. Missing pagination metadata, warnings or a cap hit remain incomplete;
   do not concatenate overlapping exports or present partial results as a full window.

## What the consumer counts

A view requires integer `evidence_version=1`, boolean affirmative consent,
`auth_state_at_event=authenticated`, a roster account string, and positive integer
filing/summary IDs. Identity comes only from `account_id_at_event`; even a later
person merge cannot promote an anonymous/unknown/legacy event. These are client
snapshots, not server-authenticated view receipts. Valid views retain event UUIDs.
A later ISO-week view of a different filing establishes only an **observed** return;
absence remains unknown. Neither registration time, a generation result nor a view
proves a useful output.

Requests group only by canonical server `request_id`. Each valid row also needs
server-authenticated identity and `consent_evidence=client_declaration`. Account,
filing and client-correlation hints must agree across the pair. Different request
IDs never merge, even if they share a client label, account or filing. Both earlier
errors and later successes remain. No logical-action success rate is manufactured.

Identical repeated event UUID rows are deduplicated. Different event UUIDs with
identical selected properties, event name and second-resolution timestamp count as
duplicate request deliveries. Changed starts/finishes, identity/hint disagreement,
invalid terminal fields or conflicting UUIDs make a request ambiguous. A malformed
or out-of-roster row with a recognizable request ID cannot rescue its otherwise
valid pair. `poisoned_request_reasons` links each affected server request ID to its
actual causes; `poisoned_request_ids` remains the compatible ID list. Missing
start/finish is separate from ambiguity. A finish without a
start retains its observed outcome but contributes no paired duration or paired
outcome count. `complete`, `partial`, `error`, `timed_out`, `rejected`, `cancelled`
and `incomplete` remain distinct. `complete` and `partial` require a positive integer
`summary_id`; a missing or null ID makes the request ambiguous. Other outcomes may
have an absent ID, but any supplied ID must still be a positive integer.
Delivery path and summary-service invocation are
observations, not fresh content, provider calls or billing receipts. Duration is the
server-emitted `duration_ms` for valid pairs, not a browser/network latency estimate.

Event time is exported as UTC epoch seconds; subsecond distinctions are unavailable.
The raw selected fields are JSON-encoded using `JSONExtractRaw`, preserving numeric,
boolean and string identity. Identical second-resolution rows cannot prove whether
an upstream duplicate originally differed only below that precision. Keep that
limitation with the receipt. Full original events are not reconstructed here.

## Unknowns and validation

The extraction predicate cannot attribute missing/unusable account snapshots to a
cohort, so those project-wide events are outside this export and their count remains
unknown. Diagnostic exclusions describe only supplied rows. A start/finish outside
the window can appear as a missing side; capture/transport loss is not distinguishable
from no event. Bad auth before route invocation and non-consenting requests are outside
the server-event denominator. This readout makes no whole-cohort success rate,
exact cached-view count, provider-cost, payment or usefulness claim.

`fixture_check.py --v1-only` exercises the actual consumer and CLI using synthetic
producer-shaped JSON rows, including anonymous/legacy/type confusion, duplicate and
conflicting UUIDs/terminals, shared client labels, missing sides, window boundaries,
all seven outcomes, missing/null IDs on complete/partial, valid null-ID errors and
rejections, empty exports and incomplete export metadata. It requires only
Python's standard library. It does not execute HogQL or read customer data. Historical
SQL and fixture modes remain available unchanged.

Before a live readout, separately verify the query's syntax and JSON result shape
against PostHog using literal fixtures, then obtain the permitted cohort observation
and retain actual receipt/limitations. The [PostHog query response schema](https://github.com/PostHog/posthog/blob/master/frontend/src/queries/schema/schema-general.ts)
records columns/results and optional pagination/warning fields; absence of those
fields is not silently interpreted as complete.

The [September 30 literal-only live check](../../review-evidence/beta-readout-2026-09-30/README.md)
verified the 21-column projection and unchanged consumer against three actual
provider-returned synthetic rows. The connector omitted query-response pagination
metadata, so `export_complete_observed` correctly remained false. Saved-insight
metadata and the UI's row-count label do not fill that gap. This does not verify
the production predicate/roster, event capture, customer consent or a beta cohort.
The earlier connector/browser failures remain historical failures, not evidence
that the current connector is unavailable.

## Supported export route remains a prerequisite

PostHog's current [API guidance](https://posthog.com/docs/api/queries) directs bulk,
recurring and third-party connector exports to batch/file-download exports. The
query endpoint supports the small literal diagnostic above; do not build a beta
export pipeline around repeated query calls or inferred pagination flags.

For the supported [one-off file export](https://posthog.com/docs/cdp/file-download-exports),
the founder reconnected with the needed `batch_export:read` and `batch_export:write`
scopes on September 30. The export tools became available, but the single
[literal-only export attempt](../../review-evidence/beta-readout-2026-09-30/export-capability.json)
returned HTTP 403: `HogQL batch exports are not enabled for this team.` No run ID,
completed record count or files were returned. This is a team-feature restriction,
not a reason to request broader connector scopes. The next operator action is to
request HogQL batch-export beta access from PostHog support for project 117863,
then verify one tiny literal-only export when access is confirmed. No unchanged
retry or broader events/persons export was attempted.

Retain the exact requested query, run identity/status, reported row count and every
returned part before proposing an adapter. JSONLines rows and a completed file-export
run are a different evidence contract from this consumer's query-response JSON.
Do not manufacture `hasMore=false` or concatenate file parts into a v1 response and
call it a completed export. Review and validate an explicit input format before any
customer readout; keep the current consumer and its unknowns unchanged meanwhile.

## Current operator checklist (October 2)

This is a handoff of remaining prerequisites, not authorization to execute them.
The [support worksheet](support-and-review.md) maps the weekly measures and records
the intended 10–20 people and email response target within two business days.
Quality acceptance, individual consent, eligible IDs, named owners, a start date
and launch disposition remain separate requirements.

- [ ] **Resolve export access.** Retain the [September 30 capability receipt](../../review-evidence/beta-readout-2026-09-30/export-capability.json):
  HTTP 403, `HogQL batch exports are not enabled for this team.` There is no run ID,
  completed record count or returned file. Project 117863 was confirmed and the
  tools were available after reconnection; broader scopes or an unchanged retry
  do not resolve the recorded team-feature restriction. The founder reported that
  submitting support tickets requires a paid plan. That limits the known support
  route; it does not establish that payment is necessary or sufficient for feature
  access. The access request below is draft-only; no ticket or purchase is claimed.
- [ ] **Verify only literals after confirmed access and separate authorization.**
  First verify one tiny literal-only export, with no events/persons table access,
  before customer data. Retain the exact query, actual run identity/status,
  reported completed count, every returned part and custody hashes. Preserve the
  prior 403 and the [three-row query projection receipt](../../review-evidence/beta-readout-2026-09-30/receipt.json).
  That projection verified 21-column compatibility but omitted pagination metadata;
  `export_complete_observed` remains false. Neither a UI row count nor the literal
  fixture proves the production roster/predicate, capture or consent.
- [ ] **Review the actual file-input contract.** Once real literal-export artifacts
  exist, explicitly document their format, fields/types, part inventory, completion
  evidence, bounds, duplicate/conflict handling and provenance; independently
  review that contract before any customer readout. A completed file run and
  JSONLines parts are not this consumer's query-response JSON. Keep the released
  consumer unchanged here; do not design an adapter for a hypothetical file,
  concatenate parts into a fabricated response or manufacture `hasMore=false`.
- [ ] **Prepare the consented cohort privately.** The founder records participation
  and contact permission separately from analytics choice, offered scope and any
  quotation/recording permission. Assign support owner, backup and readout reviewer;
  record the business-day calendar/timezone for the two-business-day email target.
  Under separately authorized observation, freeze actual eligible IDs/exclusions,
  roster observation time, start date, weekly UTC windows and a fixed roster for
  the combined return window. Intended size supplies none of these facts. Keep
  participant data out of the repository and retain unobserved accounts in N.
- [ ] **Complete two actual weekly readouts before expansion disposition.** Retain
  each week's source availability, exact query/parameters and consumer version,
  original inputs, hashes, completeness/diagnostic outputs, denominator and unknowns.
  Use the fixed-roster combined two-week window for observed ISO-week new-filing
  returns; do not concatenate weekly exports to bypass the input contract. Include
  actual support responses and reviewed participant usefulness evidence, with
  absent evidence still unknown. A prepared worksheet, synthetic receipt or
  completed export is not a weekly cohort result or beta launch approval.

### Draft-only PostHog access request — not sent

> EarningsNerd project 117863 needs confirmation of eligibility and the supported
> route for HogQL batch-export beta access. After reconnection made the export
> tools available, our September 30 attempt using only three invented literal rows
> returned HTTP 403: “HogQL batch exports are not enabled for this team.” No run ID,
> completed record count or files were returned. Can you confirm the feature-access
> process and an available contact route? Our founder reports that the support
> ticket route requires a paid plan; we have not established whether payment is
> necessary or sufficient for this feature. We are not requesting broader
> events/persons exports. After confirmed access, our first separately authorized
> verification would use literal data only, before review of the actual file-input
> contract and any customer observation.

This text is retained for founder disposition only. No message, support ticket,
subscription purchase, export retry or customer query was performed for this handoff.
