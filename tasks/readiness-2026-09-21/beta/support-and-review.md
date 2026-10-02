# Support operation and two-week cohort review v1

Updated October 2, 2026. The recorded founder decisions are an **intended cohort of
10–20 people** and **email support with a response target within two business days**.
The [released v1 runbook](summary-v1-readout.md) records the cohort size and response
target; the October 2 operator handoff specifies email support. These replace this
worksheet's earlier 5–10 placeholder and undecided target. They establish neither
an enrolled cohort nor observed support performance. Candidate selection, individual
consent, offered scope and launch disposition remain with the founder.

Complete the private control sheet before any authorized invitation. Use the
[current operator checklist](summary-v1-readout.md#current-operator-checklist-october-2)
for the export prerequisite and the two actual weekly readouts. This worksheet
does not authorize contact, data collection, a production change or beta launch.

## Cohort control sheet (private, not committed with user data)

| Field | Recorded decision or required entry |
|---|---|
| Intended cohort / actual participants | **10–20 intended people**; `[actual consented aliases and count; identity/contact in approved private location]` |
| Support commitment | **Email response target within two business days**; `[support address, owner-defined business-day calendar/timezone, queue cadence and coverage]` |
| Cohort label / version | `[exact invite_codes.cohort]` / `[readout version]` |
| Candidate profile | `[filing-summary user/problem and unsupported expectations]` |
| Participation / contact consent | `[per-alias choice; exact approved text/version; who obtained it; date; restrictions]` |
| Analytics choice | `[known choice and observation basis, or unknown; separate from participation/contact consent]` |
| Owner and backup | `[named support owner]`; `[named backup]`; `[readout/review owner]` |
| Frozen eligible roster | `[authorized db_roster.sql snapshot, roster_observed_at, eligible IDs/count and private receipt]`; intended size is not this denominator |
| Frozen exclusions | `[founder/staff/agent/automation/test user IDs and test invite IDs; owner; freeze time]` |
| Start date / windows | `[actual start date, not yet established]`; `[week 1 UTC start/end]`; `[week 2 UTC start/end]`; `[fixed roster and combined window for return observation]` |
| Offered scope | `[accepted forms, limits, known unsupported surfaces and owner acceptance]` |
| Query/source receipt | `[commit/query/consumer versions, exact parameters, source availability, observation timestamp, input/output hashes and private locations]` |
| Observed outcomes | `[actual weekly readout receipts and support response observations, or unknown]` |

Onboarding script for separately authorized use: state the accepted filing scope and
known limitations; ask the participant to choose a real filing and articulate one
question they would use the summary to answer; observe whether they read a cached
or fresh summary, inspect a cited source and judge whether it helped. Record the
participant's words and session alias, not an invented usefulness score. Ask
permission separately for any interview recording or quotation. State the recorded
email response target only with an assigned owner and coverage; it is not a
resolution deadline or a promise of feature work.

Consent language for founder review before use: “We are inviting a small group to
try the filing-summary beta within the scope we describe. We may ask you about your
experience and review the feedback you choose to submit. Participation and analytics
choices are separate; please use the site's consent controls for analytics. May we
contact you about feedback you submit? `[approved contact and data-handling details]`.”
Record the exact approved text/version and each participant's choice in the private
control sheet. This draft is not a policy or authorization to send invitations.

## Support queue

The durable in-app intake is `feedback` and the existing `/admin/feedback` view;
admin notification email can fail after the row commits. Check the queue at the
assigned cadence and link every item to an owner. Keep email correspondence and
first-response evidence linked in the private support sheet; do not imply every
email is a DB feedback row or create a second ticket store. Record `feedback_id`
when available, alias, received UTC, type, severity, owner, first response UTC,
target UTC under the recorded business-day calendar, status, resolution UTC, linked
incident/issue and user-confirmed outcome. Reconcile `new`, `triaged`, `resolved`
counts from [db_support_alerts.sql](db_support_alerts.sql) each week. A status
transition is not itself evidence the user got an answer.

The common email response target is **within two business days**. Severity controls
triage and escalation; no severity-specific response promises have been approved
in this handoff. Keep actual response performance separate from that commitment.

| Severity | Triage rule | Required operational entry |
|---|---|---|
| S0 | Security/privacy issue, material fabricated quote/citation, broad user harm or data loss | `[incident owner and immediate containment/escalation path]` |
| S1 | Core accepted workflow blocked or repeated misleading analysis | `[owner, affected users and workaround/stop-use decision]` |
| S2 | Partial output, export/UI fault or recoverable workflow issue | `[owner and impact]` |
| S3 | Question, feature request or low-impact polish | `[owner and disposition]` |

Escalate an S0/S1 to the named owner through the existing operating process; attach
source evidence and avoid account details in aggregate readouts. Use
[OPERATIONS](../../../docs/OPERATIONS.md) for health, alerts and incident procedures.

## Weekly review, twice before any expansion decision

Repeat the sheet for two actual weeks. Record UTC half-open windows `[start, end)`,
the frozen eligible denominator **N**, exclusions and source receipt for each.
Show `n/N` before percentages where a cohort rate is meaningful; label event,
request, batch and session counts with their own denominators. Mark each source
`observed`, `unavailable` or `unknown`, with its observation time and last complete
interval. Missing telemetry is unknown, not zero or non-participation. If N is
zero, report no eligible users and no rate; do not run placeholder account IDs.

The **v1 readout** below means the existing [posthog-v1-export.hogql](posthog-v1-export.hogql)
plus [readout_v1.py](readout_v1.py), under the [runbook's input and attribution contract](summary-v1-readout.md#what-the-consumer-counts).
It uses event-time snapshots, never current person linkage. Client-authenticated
view snapshots are not server-authenticated view receipts. Server requests have
authenticated account identity but only client-declared consent. Preserve the
exact query, parameters, originals, hashes, diagnostics and completeness flag.
The supported export and reviewed file-input contract remain prerequisites.

The historical [posthog.hogql](posthog.hogql) A/B queries remain unchanged. Their
person-linked coverage, citation, generation and Analysis observations are labeled
diagnostics below; they do not establish event-time authentication or consent and
must not replace prospective v1 view/request measures. No new query is defined here.

| Measure | Week 1 | Week 2 | Existing source, denominator, window and evidence limits |
|---|---|---|---|
| Invites issued / pending reachable / redeemed / registrations / verified eligible | `[unknown; receipt]` | `[unknown; receipt]` | [db_roster.sql](db_roster.sql): invite rows created before the week's end, with exclusions shown separately; distinct linked users for registrations and distinct `eligible_verified` users for N. This is a cumulative end-boundary roster, not invitations issued during the week. Redemption/registration use timestamps; verification and revocation use current flags. Save `roster_observed_at`; do not reconstruct an earlier state from a later run. |
| Historical client-event coverage / unknown | `[unknown]` | `[unknown]` | `posthog.hogql` A: `client_observed` eligible IDs / N for the weekly window; unresolved/ambiguous identities and `client_unobserved_unknown` remain in N. Named browser events linked through current persons are a coverage diagnostic, not a consent or signed-in receipt. |
| First observed v1 summary view | `[unknown]` | `[unknown]` | V1 `observed_view_accounts` / `eligible_denominator` N and `unobserved_view_accounts_unknown`; per-account `first_observed_view_timestamp_s` within the weekly window. This is first observed in-window, not first-ever activation or time from registration/verification. Retain `view_event_uuids`; cached/fresh split and usefulness remain unknown. |
| Summary request outcomes and duration | `[unknown]` | `[unknown]` | V1 `request_status_counts`, `paired_outcome_counts` and each request's `observed_terminal` / `paired_duration_ms`, within the weekly window. Use valid paired server requests as the paired-outcome/duration denominator; report missing-start, missing-finish and ambiguous requests separately. Retain all seven outcomes and delivery paths. Requests are not logical actions, provider calls, browser receipt or fresh-generation success. |
| Historical generation diagnostics | `[unknown]` | `[unknown]` | Historical A `fresh_generation_attempt_events`, `fresh_generation_success_events`, `fresh_generation_partial_events` and `fresh_generation_failure_events`, for the weekly window, as event counts and distinct affected eligible users / N where derivable. Success includes partials; these pipeline signals are not an exact fresh-generation, retry or transaction census and cannot be added to v1 request totals. |
| First explicitly useful analysis; time to first useful output p50/p95 | `[unknown]` | `[unknown]` | Reviewed session-linked participant answers in the private support sheet / N, with answered-session coverage and yes/partly/no/unknown counts. Use sessions in the weekly window and retain the timestamp basis. The consumer supplies no usefulness or elapsed-time metric; p50/p95 require separately recorded valid start/session times and sample count, otherwise unknown. Generic feedback is not a useful rating. |
| Observed later ISO-week new-filing return | `[unknown / immature]` | `[unknown; combined-window receipt]` | V1 per-account `observed_later_week_new_filing_return=true` count / the fixed N for a separately frozen combined two-week window. It requires a later ISO-week view of a filing different from an earlier view in the first observed ISO week; preserve that roster even for unobserved accounts. No qualifying observation remains unknown. This is observed return, not complete retention; historical B is a separate diagnostic, and Analysis attempts do not qualify. |
| Citation inspection and reported accuracy problems | `[unknown]` | `[unknown]` | Historical A `citation_click_events` and `summary_view_events` in the weekly window: event counts, not unique clickers or verified inspections. If reporting viewer context, count A's cohort-associated observed viewers and label the retrospective linkage; do not divide historical clicks by v1 viewers. Persisted feedback and reviewed session/source evidence record reported problems separately; a click does not verify correctness. |
| Accepted alert batches / first clicks | `[unknown]` | `[unknown]` | [db_support_alerts.sql](db_support_alerts.sql): `first_clicked_batches` / `accepted_batches` with a provider ID and first dispatch in the weekly window; first click must be before its end. Report `alerted_users` / N and `alert_clicked_users` separately. Accepted send is not inbox delivery; click is not a product return. The [OPERATIONS trend](../../../docs/OPERATIONS.md#alert-to-return-measurement-e11c) has an all-user denominator. |
| Feedback new / triaged / resolved; first response | `[unknown]` | `[unknown]` | `db_support_alerts.sql`: current statuses of feedback created in the weekly window, `feedback_submissions` and `feedback_reporters` / N; not the entire backlog or transitions during the week. Private sheet supplies first-response times for received items, including email-only items separately. Report timed-response sample count, missing/unanswered count and calendar basis alongside median/target performance; DB status alone proves no response. |
| Fresh Analysis inference cost observations | `[unknown]` | `[unknown]` | Historical A `fresh_analysis_cost_usd` and `fresh_analysis_cost_observations` in the weekly window; any quotient describes cost-observed fresh completions only, with that observation count as denominator. It is not cost per all successful Analysis: cached completions and missing usage are absent, `analysis_generated` is only an attempt, and malformed/missing cost values can be coerced to zero by the query. Keep coverage/provenance limits and Copilot cost separate. |
| Summary unit cost | `[unknown]` | `[unknown]` | No complete source in this kit. V1 request delivery paths/service invocation are not provider usage or charge receipts. A weekly cost-per-success figure requires a separately reconciled cost source and a declared success denominator; no provider cost is inferred here. |
| Observed paying-user share / refunds | `[unknown]` | `[unknown]` | [db_paid_cohort.sql](db_paid_cohort.sql): `observed_paying_users` / `eligible_verified_users` N for positive, live, qualifying subscription allocations with `paid_at` in the weekly window. This is in-window payer share, not proven first-ever conversion. [Existing billing report](../../../backend/scripts/billing_revenue_report.py) owns gross amount/currency/coverage evidence before refunds and other adjustments; trial, checkout and $0 beta invoices do not count. Refunds need a separate observation, not subtraction invented from this payer query. |
| Failed/degraded outputs and missing telemetry | `[unknown]` | `[unknown]` | V1 paired `partial`, `error`, `timed_out`, `rejected`, `cancelled`, `incomplete` remain distinct from `complete`; show request denominator, diagnostics, missing sides and ambiguous groups for the weekly window. Historical A generation partial/failure event counts are separate pipeline diagnostics, not additional unique failed requests. Retain reported quality failures independently of terminal state. Project-wide unattributable events and total capture loss remain unknown. |

Weekly interview prompts: “What question brought you to this filing?”, “What did
you read or check against the source?”, “What part helped or misled you?”, “What
did you do next?”, and “Would you return for another filing, and what would prevent
it?” Record session alias and time so reviewed usefulness can be linked without
publishing identity. Summarize strongest/weakest examples and unresolved failures.
The founder sets expansion thresholds after these two observed reviews; a fabricated
zero or conversion percentage is not a decision rule. Quality acceptance and other
unresolved launch prerequisites remain separate from this operating worksheet.

## Concrete usefulness evidence to retain per beta session

Use the existing feedback queue and private cohort sheet. Ask: “Did this summary help
you answer the question you brought to this filing: yes, partly, or no? What helped
or was missing?” Keep the participant's exact answer, not an inferred rating. Record
cohort/session alias, authenticated feedback author (when submitted through the app),
filing ID, summary ID, session UTC time, and feedback ID. If analytics was consented
and observed, also retain the exact `summary_viewed` event UUID and timestamp; without
it, label the linkage as facilitator-observed rather than an analytics join. Record
permission for any quoted feedback separately. Never synthesize a participant response.

A reviewer checks that the answer addresses the actual summary and session before
counting it. Retain yes/partly/no separately, plus unknown/no response, and the full
eligible denominator. The first useful time is the participant's recorded session
time, not registration, pageview, generic feedback, export, or generation success.
No cohort, invitation, consent, or useful result is established by this worksheet.
