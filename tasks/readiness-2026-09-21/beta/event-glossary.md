# Event-to-emission glossary v1

All PostHog captures are best effort. The browser SDK uses the existing analytics preference. The summary-stream route now receives an explicit client consent declaration and uses only the authenticated account for server identity; other backend event families have separate contracts. See [summary request evidence v1](summary-request-evidence.md) for the new request pairs and their limits. Historical events may use client-supplied distinct IDs and lack consent or request identity.

Client coverage uses the 37 named browser emissions currently in `frontend/lib/analytics.ts`, `frontend/app/posthog-provider.tsx`, `frontend/app/pricing/page.tsx`, and `frontend/features/marketing/components/QuickAccessBar.tsx`. The A/B predicates in `posthog.hogql` are checked against those source files by `fixture_check.py --inventory-only`; the glossary table below explains the signals needed for this readout, rather than listing every browser action. Backend generation and inference-cost events are excluded from client coverage. The backend defines `EVENT_SUMMARY_VIEWED` but has no call site that emits it; the active `summary_viewed` capture is in the filing page.

| Signal | Actual emission point | What it establishes / limit |
|---|---|---|
| Invite issued/redeemed | `invite_codes` durable row; `backend/app/routers/auth.py` emits `invite_redeemed` after `redeem_invite` | Persisted `used_at` + `user_id` is authoritative. Exclude revoked/expired from currently reachable invitations, but retain issued counts. |
| `signup_completed` | `backend/app/routers/auth.py` immediately after `User` insert and invite attempt | Registration **before email verification**. `users.email_verified` is the current verified state; no verification timestamp exists for a precise time-to-verification calculation. The stale comment in `frontend/lib/analytics.ts` does not change this. |
| `generation_started`, `generation_succeeded`, `generation_failed`, `generation_timed_out` | `backend/app/services/summary_pipeline.py::stream_filing_summary`, only user-facing stream | Legacy pipeline diagnostics, with incomplete terminal coverage. `generation_succeeded` includes persisted partial results, excludes status `error`. Background generation suppresses funnel telemetry. New route calls include a server request ID and require client-declared consent; use the separate request pair for lifecycle measurement. |
| `summary_request_started`, `summary_request_finished` | Authenticated summary route and its owned stream iterator | Versioned server request/account identity, client-declared consent, outcome and delivery path. Client action/retry labels are untrusted hints; missing terminals stay unknown. [Full contract](summary-request-evidence.md). |
| `summary_generated` | `frontend/app/filing/[id]/page-client.tsx` when summary content exists | Client render, including cache; name does not mean a new model generation. |
| `summary_viewed` | Same filing page, when actual `summary` and content exist | Observable summary consumption, cached or fresh. It can fire for anonymous viewers; later person linkage to an eligible roster ID does not prove signed-in activation at event time. The template labels these cohort-associated views and leaves signed-in activation unknown. |
| `source_span_click` | `frontend/lib/analytics.ts` from citation interaction | Citation use; a click is not independent verification of summary correctness. |
| `analysis_generated` | `frontend/features/analysis/components/AnalysisPageClient.tsx::run`, **before** `getAnalysisDataset` | Analysis attempt only. Dataset may fail and narrative may never start. No completed dataset or cached narrative event is emitted today. |
| `analysis_inference_cost` | `backend/app/routers/analysis.py` for a fresh SSE `complete` event with usage | Best-effort cost observation for fresh completed narrative. Cached serves and fresh completions missing usage emit nothing; it cannot measure all successes. The `trend_analysis` row is a shared cache, not proof every user consumed it. |
| `export_generated` | `frontend/lib/analytics.ts` after Analysis/summary blob succeeds | Delivered download action, subject to browser telemetry; not evidence the analysis was useful. |
| `feedback_submitted` | `backend/app/routers/feedback.py` after `feedback` DB commit | Best-effort event; persisted row and `status` are authoritative for support. Type `general` is not an explicit useful rating. |
| `alert_email_clicked` | Resend click webhook, after first-click stamp in `earningsnerd_delivery_batches` | Click on accepted alert, not a summary read or return to product. Use accepted batch with `provider_email_id` as the denominator; `first_click_at` as numerator. An accepted send does not prove inbox delivery. |
| `filing_link_copied` | `frontend/lib/analytics.ts`, after successful clipboard write | Copy only; neither delivered share nor referral. |
| `homepage_section_viewed`, `notable_filing_clicked` | Homepage intersection observer/card click | Impression and click while visible; a dark Notable section has no engagement denominator. |
| `invoice_payment_recorded` | `backend/app/services/billing_revenue_service.py` on observed Stripe allocation | Analytics side-signal only. Use `earningsnerd_billing_payments` and its existing report for live positive, qualifying, attributed payment evidence; not ARR. |

No event currently means an explicit “useful” rating. No event proves an Analysis dataset request succeeded. No `users` field persists analytics consent. These are explicit **unknowns** in both weekly reviews, not zeroes. The original preparation added no production instrumentation; the later versioned implementations are documented separately below.

## Summary view evidence v1 (September 28 implementation)

New `summary_viewed` calls include `evidence_version=1`, `summary_id`,
`auth_state_at_event` (`authenticated`, `anonymous`, or `unknown`),
`account_id_at_event` (the route's current `/me` account ID or null), and
`analytics_consent_at_event=true`. The helper sends this event only when the existing
browser preference explicitly grants analytics consent. Pending/failed auth resolution
is unknown. The once-per-mount view is not replayed after login or consent changes.
These are client-observed snapshots, not server-authenticated view receipts; the existing
account-query reset owns account transitions. A later PostHog person merge must not
replace these properties or backfill legacy events. Historical claims above continue
to apply to unversioned data.

For a prospective weekly readout, select version 1 events with affirmative consent,
`auth_state_at_event=authenticated`, a nonempty `account_id_at_event` in the frozen
eligible account roster, and a valid filing/summary ID. Attribute using that event
property only; never resolve the event through current person traits. Keep anonymous,
unknown, malformed, legacy, excluded-account and outside-window rows as separate
diagnostic exclusions. Keep every eligible user in the denominator; a user without
a qualifying observed view remains unknown, not inactive. Report a client-observed
signed-in-view count with its telemetry coverage and client-auth limitations.

This closes the retrospective-identity ambiguity for new client events only after
deployment. It does not establish cached-versus-fresh consumption, complete request
lifecycles, actual usefulness, server-side analytics consent, or live PostHog receipt.
The existing support process can capture explicit session-linked usefulness before
a rating UI exists; ordinary `general` feedback is still not a useful rating.
