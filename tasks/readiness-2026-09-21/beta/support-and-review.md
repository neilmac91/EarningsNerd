# Support operation and two-week cohort review v1

Fill the bracketed fields before the first invitation. The founder owns candidate selection, consent, promised response target and offered capability scope. This template records those decisions; it makes none of them.

## Cohort control sheet (private, not committed with user data)

| Field | Required entry |
|---|---|
| Cohort label / version | `[exact invite_codes.cohort]` / `[readout version]` |
| Candidate profile | `[filing-summary user/problem and unsupported expectations]` |
| Candidate slots | `[5–10 aliases; identity and contact kept in approved private location]` |
| Consent / commitment | `[per-alias status; who obtained it; date; any restrictions]` |
| Owner and backup | `[named support owner]`; `[backup]` |
| Frozen exclusions | `[founder/staff/agent/automation/test user IDs and test invite IDs; owner; freeze time]` |
| Window | `[week 1 UTC start/end]`; `[week 2 UTC start/end]` |
| Offered scope | `[accepted forms, limits, known unsupported surfaces]` |
| Query/source receipt | `[commit SHA, DB/PostHog access availability, query timestamp, output location]` |

Onboarding script: state the accepted filing scope and known limitations; ask the participant to choose a real filing and articulate one question they would use the summary to answer; observe whether they read a cached or fresh summary, inspect a cited source and judge whether it helped. Record the participant's words and the session alias, not an invented usefulness score. Ask permission separately for any interview recording or quotation. Do not promise turnaround or feature work until the owner fills the fields above.

Consent language for founder review before use: “We are inviting a small group to try the filing-summary beta within the scope we describe. We may ask you about your experience and review the feedback you choose to submit. Participation and analytics choices are separate; please use the site's consent controls for analytics. May we contact you about feedback you submit? `[approved contact and data-handling details]`.” Record the exact approved text/version and each participant's choice in the private control sheet. This draft is not a policy or authorization to send invitations.

## Support queue

The durable intake is `feedback` and the existing `/admin/feedback` view; admin notification email can fail after the row commits. Check the queue at `[owner-set cadence]` and link every item to an owner. Do not create a second ticket store. Record `feedback_id`, alias, received UTC, type, severity, owner, first response UTC, target UTC, status, resolution UTC, linked incident/issue and user-confirmed outcome in the private support sheet. Reconcile `new`, `triaged`, `resolved` counts from `db_support_alerts.sql` each week. A status transition is not itself evidence the user got an answer.

| Severity | Triage rule | Required decision field |
|---|---|---|
| S0 | Security/privacy issue, material fabricated quote/citation, broad user harm or data loss | `[incident owner, immediate containment/escalation path and response target approved by founder]` |
| S1 | Core accepted workflow blocked or repeated misleading analysis | `[owner, affected users, workaround/stop-use decision and response target]` |
| S2 | Partial output, export/UI fault or recoverable workflow issue | `[owner, impact and response target]` |
| S3 | Question, feature request or low-impact polish | `[owner and response target]` |

Escalate an S0/S1 to the named owner through the existing operating process; attach source evidence and avoid discussing account details in aggregate readouts. Response targets above are deliberately blank until authorized. Use [OPERATIONS](../../../docs/OPERATIONS.md) for health, alerts and incident procedures.

## Weekly review, twice before any expansion decision

Repeat this sheet for week 1 and week 2. Use counts and exact denominators; for a small cohort, print `n/N` before any percentage. Mark each source `observed`, `unavailable` or `unknown`, and note its last complete interval.

| Measure | Week 1 | Week 2 | Denominator / source |
|---|---|---|---|
| Invites issued / reachable / redeemed / registrations / verified eligible | `[ ]` | `[ ]` | `db_roster.sql`, distinct eligible IDs; registration is pre-verification |
| Client event coverage / unknown | `[ ]` | `[ ]` | observed client IDs / all verified eligible; missing is unknown |
| First summary viewed; fresh generation outcomes | `[ ]` | `[ ]` | cohort-associated views are diagnostic; signed-in activation unknown without event-time account identity; fresh attempts/successes separate; exact cached-view count unknown |
| First explicitly useful analysis; time to first useful output p50/p95 | `[unknown until session-linked evidence]` | `[ ]` | reviewed sessions with explicit usefulness / eligible; report coverage and timestamp basis |
| Later ISO-week new-filing return | `[usually immature]` | `[ ]` | cohort-associated two-week views are diagnostic; signed-in return unknown without event-time account identity; `posthog.hogql` B |
| Citation inspection and reported accuracy problems | `[ ]` | `[ ]` | `source_span_click` / observed summary viewers; support/quality evidence separately |
| Accepted alert batches / first clicks | `[ ]` | `[ ]` | `db_support_alerts.sql`; all-user trend in OPERATIONS |
| Feedback new / triaged / resolved; median first response | `[ ]` | `[ ]` | DB status counts; response timing from private owner sheet |
| Fresh inference cost and cost per successful Analysis | `[ ]` | `[ ]` | cost-observed fresh completions only; unknown if coverage incomplete |
| Summary unit cost / paid conversion / refunds | `[unknown or observed evidence]` | `[ ]` | no complete summary-cost source; natural payment report only; refunds require separate observation |
| Failed/degraded outputs; known missing telemetry | `[ ]` | `[ ]` | fresh generation failure/partial counts; account for best-effort capture |

Weekly interview prompts: “What question brought you to this filing?”, “What did you read or check against the source?”, “What part helped or misled you?”, “What did you do next?”, and “Would you return for another filing, and what would prevent it?” Record exact session alias and time so a reviewed usefulness judgment can be linked without publishing participant identity. Summarize strongest/weakest examples and unresolved failures. The founder sets expansion thresholds after these two observed reviews; a fabricated zero or conversion percentage is not a decision rule.
