# Controlled beta measurement and operations kit v1

Prepared 21 September 2026. September 28 implementation adds [versioned event-time summary-view evidence](event-glossary.md#summary-view-evidence-v1-september-28-implementation); the queries below retain their historical diagnostic semantics until explicitly replaced and verified against live data. This is a query and review contract, not an observed cohort result or an invitation to run production operations. Use the existing [beta telemetry map](../../archive/beta-monitoring.md), [alert-return query](../../../docs/OPERATIONS.md#alert-to-return-measurement-e11c), and [billing observation report](../../../backend/scripts/billing_revenue_report.py); do not create parallel dashboards or payment ledgers.

Current request measurement uses [summary request evidence v1](summary-request-evidence.md): server-owned request/account identity, consent-gated terminal observations and explicit cached/shared/generation paths. The existing HogQL queries and the identity/request descriptions below are the original unversioned diagnostic baseline; do not apply them as the semantics of either new v1 contract. Live receipt and the consenting cohort remain unverified.

The [prospective summary v1 readout](summary-v1-readout.md) now provides a bounded raw-event export and an offline consumer for the versioned contracts. Historical `posthog.hogql` remains byte-identical. Offline fixtures do not establish live HogQL receipt, a consenting cohort or a weekly result.

## Current operator handoff (October 2)

The [support and cohort worksheet](support-and-review.md) records the intended
10–20-person cohort and email response target within two business days, with actual
consent, eligible IDs, owners, dates and results still to be recorded. Its weekly
metric map separates prospective v1 view/request observations from historical
diagnostics, durable DB counts and reviewed session evidence.

Follow the [current operator checklist](summary-v1-readout.md#current-operator-checklist-october-2)
for access, literal-only verification, a reviewed file-input contract, consented
cohort preparation and two real weekly readouts. The retained file-export attempt
returned HTTP 403 with no run, completed count or files. The three-row literal
projection lacked pagination metadata, so export completeness remains false.
These documents preserve that blocker and do not authorize a launch or collection.

## Freeze before each readout

Record the UTC half-open window `[window_start, window_end)`, exact invite `cohort`, the immutable list of founder/staff/agent/automation/test **user IDs**, any test invite IDs, data-source availability, and query version/SHA. A pending invite without a user ID cannot be classified as internal from this filter; exclude its invite ID explicitly if known. Record any unresolved identity as unknown and resolve it before claiming a rate. Use a separate copy of this parameter sheet for each weekly readout; never silently revise a past denominator.

The database stores the current `email_verified` and `is_revoked` flags, not their transition timestamps. Therefore historical verification and invite reachability cannot be reconstructed exactly by rerunning a past window. `registered_by_window_end` and `redeemed_by_window_end` use timestamps, while `eligible_verified` uses current verification state. `pending_reachable_at_window_end_current_state` treats an invite redeemed at or after the window end as still pending at that boundary, but uses current revocation state. Save each weekly roster output with `roster_observed_at`; do not re-label a later snapshot as the earlier week's state.

`db_roster.sql` uses only `SELECT` and returns one row per invite with eligibility flags. Run with a read-only database role and `psql -X -v ON_ERROR_STOP=1 -v cohort='...' -v window_start='2026-09-21T00:00:00Z' -v window_end='2026-09-28T00:00:00Z' -v excluded_user_ids='{...}' -v excluded_invite_ids='{...}' -f db_roster.sql`. Do not run it against customer data until the cohort/exclusion owner authorizes that observation. Count distinct eligible `user_id` values (the query selects one canonical redeemed invite per user). For prospective summary measurements, carry the frozen eligible IDs and exclusions into the [v1 query and private parameters](summary-v1-readout.md); use the same declared UTC window. For a separately labeled historical diagnostic, copy only the eligible numeric IDs into the `eligible_ids` array in `posthog.hogql`, with matching bounds and exclusions. Keep the export in the authorized analysis workspace; it is not a repository fixture.

`db_support_alerts.sql` reports persisted feedback and accepted alert batches for the same eligible cohort. The existing `docs/OPERATIONS.md` query remains the all-user trend; this query adds the frozen cohort filter. `db_paid_cohort.sql` adds only a distinct-payer count for the exact eligible denominator, using the same qualifying predicate as the existing [billing report](../../../backend/scripts/billing_revenue_report.py); use that report for amount/currency/coverage limits. Checkout, trial, `subscription_activated`, and a $0 beta invoice do not prove paid conversion.

## Historical unversioned diagnostic contract

The paragraphs below retain the original `posthog.hogql` semantics. References to
missing event-time identity or request IDs describe that unversioned baseline,
not the later [view v1](event-glossary.md#summary-view-evidence-v1-september-28-implementation)
or [request v1](summary-request-evidence.md) contracts. Use the current worksheet
and v1 runbook for prospective summary observations; do not relabel historical
queries or their saved receipts as v1 results.

`posthog.hogql` has independent named queries. Replace its eligible ID list and UTC bounds once per readout, after applying excluded IDs in `db_roster.sql`; do not use person traits to infer a cohort. Its A/B client-coverage predicates include every named event emitted by current frontend capture sites; the offline `fixture_check.py --inventory-only` check compares both lists to those sites. A/B anchor each eligible numeric account ID through PostHog's `person_distinct_ids` and join events by resolved `events.person_id`, which can include an anonymous UUID later linked by `identify`. A person linked to more than one numeric account ID is excluded from attribution and reported as `ambiguous_numeric_identity`; an absent mapping is `unresolved_identity`. Both remain in the eligible denominator. A different unmerged anonymous profile cannot be recovered, and the numeric-ID guard cannot prove who controlled a shared browser before identification; current identity mappings can also change a historical rerun, so save the readout. [PostHog's person documentation](https://posthog.com/docs/data/persons) describes retrospective anonymous-event linkage, and its [HogQL person-processing documentation](https://github.com/PostHog/posthog/blob/master/docs/published/handbook/engineering/person-processing.md) describes canonical person IDs and merge overrides.

PostHog client events are observable only when the browser captures them. Backend emissions are best effort and have no consent marker, so even a server event is **not** proof of analytics consent. `client_observed` means at least one named client event was associated with the eligible person's resolved identity; `client_unobserved` remains **unknown** (could be refusal, blocked/missing telemetry, no visit or identity mismatch). The product does not persist consent by user ID. A known non-consenter can be noted in the private cohort sheet, but still remains in the eligible denominator. Never compute a whole-cohort activation or return rate by silently excluding `client_unobserved` users. Cohort-associated observations are diagnostic counts, **not** lower bounds on signed-in activation or return: a later `identify` can associate pre-registration or signed-out events with the person. No zero is inferred for an unobserved person. If PostHog access/data is unavailable, write `unknown`, not `0`.

The primary first-use definition is a signed-in eligible user's first `summary_viewed` of actual summary content, whether that summary was already cached or freshly generated. The present event has no trustworthy event-time authenticated account ID. A later person merge can associate a signed-out view with the eligible account, so this template reports `signed_in_activation` as **unknown** and exposes cohort-associated views only for diagnosis. `generation_succeeded` is a separate fresh generation outcome; it can occur before a user sees content and misses cached consumption. These are separate measures, not a partition: the view event has no cache flag or request ID, so an exact cached-view count is unknown. `summary_generated` is a client render event and is not a fresh-generation count. First useful analysis requires an explicit useful rating or a reviewed, session-linked interview/feedback record; the current app emits no such rating. Until that evidence exists, usefulness and time to first **useful** output are unknown. Time from registration to first **viewed** output is also unverified without event-time account attribution; the database has no verification timestamp for a precise post-verification delay.

Weekly return means the same signed-in eligible user has `summary_viewed` in at least two distinct ISO weeks, with the later view of a *different* `filing_id`, or a separately evidenced completed core analysis. The current PostHog Analysis event is an attempt and no event proves dataset success or cached narrative completion, so the template's two-week calculation uses the summary path only. Its result is a cohort-associated diagnostic, **not** verified signed-in weekly return or a lower bound; `signed_in_weekly_returners` remains unknown without event-time account attribution. Pageviews, searches, Copilot questions and alert clicks alone do not qualify. `generation_started/succeeded/failed/timed_out` supply request telemetry, but no request ID permits exact retry deduplication; report event counts and distinct affected users, not a purported transaction success rate. Fresh Analysis `analysis_inference_cost` is emitted on completed, uncached narrative with usage and is a best-effort cost observation; a cached serve does not emit it. Thus its count is not a denominator for all Analysis attempts and its absence is not a zero-cost proof. Summary generation has no equivalent complete provider-cost event in this contract, so cost per successful filing summary is unknown unless a separately reconciled cost source is provided. Keep Copilot inference costs separate.

The acceptance worksheets add only the missing [Analysis](analysis-acceptance.md) and [Notable](notable-acceptance.md) proofs. The [support template](support-and-review.md) gives an owner and two-week review structure. The hold point is actual invitations, customer contact, production setting changes, live warm-up, and product acceptance decisions; this kit does none of those.

## Fixture verification

The paragraph below is the preparation-time description. Later verification is
recorded in [the original fixture receipt](fixture-receipt.md) and the
[September 30 literal-only receipt](../../review-evidence/beta-readout-2026-09-30/README.md).
The latter verified projection compatibility, while export completeness and a
real cohort readout remain unestablished; it does not replace the historical SQL
or its evidence.

`fixture_check.py` creates temporary tables in the isolated `tranche_beta` PostgreSQL database, inserts synthetic invite/user/feedback/alert/payment rows, executes the exact roster/support/payer SQL, and asserts denominator and exclusion outcomes. It refuses other database names, never reads application tables and rolls back at the end. `posthog.hogql` uses functions listed in the [PostHog SQL reference](https://posthog.com/docs/sql/clickhouse-functions) and [aggregation reference](https://posthog.com/docs/sql/aggregations), and its client-observation denominator is checked with a separate fixture truth table; live HogQL execution requires PostHog access and has not occurred. See `fixture-receipt.md` for the exact command/result.
