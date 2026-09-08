# Master-plan checkpoint — 2026-09-08

Draft pending #779's production verification. The audit and remediation are complete, and the
assigned dependency closeout is in its final evaluation. The overall beta-to-scale plan still
has substantive activation, quality, fleet-coordination and operational acceptance work. Green
engineering gates do not establish launch readiness, paying conversion or scale economics.

## Work completed before this takeover

Earlier agents shipped the reliability foundation: migration ledger and guarded SQL, serial
deploy checks, runtime/security modernization, production/evaluation parity, a measured AI
baseline, grounded filing facts and Copilot, reporting-period/amendment handling, public index
retrieval and observability. The September 6 queue added mobile/example consistency, SEC token
accounting, shorter database transactions, SSE bounds, checkout/event ordering, actual-payment
measurement, atomic usage increments, hot-read indexes, local generation ownership, login
hardening, sharing and sitemap eligibility.

The specific intervening Claude/Fable session audited here (#742–#770) delivered account-cache
isolation and billing-state honesty; quota reservations for summary, Copilot and Analysis;
durable alert delivery and earnings-day claims; click/return measurement; bounded startup and
sitemap behavior; process-level chat admission; unread-count and limiter consolidation;
retention and reconciliation tooling; and recorded transient evaluation retries.

The founder separately executed/reviewed W3-9, created the retention job/scheduler, and
created/seeded Notable. Those console operations are founder accomplishments, not agent work.
The latest W3-9 record supersedes its earlier failed flag-only assumption; FMP access is no
longer a prerequisite for the deployed public-source membership refresh.

## Work completed by this Astra team

The team audited the requested 132-file span with independent correctness, rules/tests and
GitHub/ledger reviews. All fifteen backend deploy logs were reconciled. Fresh main gates passed
2729 backend tests with performance/four PostgreSQL lanes and 569 frontend tests with lint,
TypeScript and build. [Audit #773](https://github.com/neilmac91/EarningsNerd/pull/773) is merged.

[Fix #772](https://github.com/neilmac91/EarningsNerd/pull/772) closes a crash gap that could
permanently lose an older pending alert during batch replacement. Release and replacement now
commit atomically; fresh-session failure/collision recovery is tested. The fix is deployed and
healthy. The audit also identified #759's previously unrecorded locked-file edit; the founder
explicitly approved retaining its three additions. Original assertions were unchanged and
future edits remain locked. No locked test was edited by this team.

Dependency work is isolated into [PostHog JS #774](https://github.com/neilmac91/EarningsNerd/pull/774),
[greenlet/Python PostHog #775](https://github.com/neilmac91/EarningsNerd/pull/775),
[OpenAI SDK #777](https://github.com/neilmac91/EarningsNerd/pull/777), and
[EDGAR/lxml #779](https://github.com/neilmac91/EarningsNerd/pull/779). The first three are
released; #779's actual regression/deployment checkpoint is pending. Backend candidates pass
2731 local tests; the SDK's actual summary gate scored 52/52 with zero errors/retries/vetoes,
and its normal paid Copilot gate accepted 18/18. DeepSeek and the baseline remain unchanged.

The [E09 proposal](e09-fleet-coordination-proposal-2026-09-08.md) is prepared and independently
reviewed, with read-only founder inventory commands. Three major frontend upgrade candidates
also passed full local gates with unchanged tests; they remain unmerged pending approval.

## What remains

| Workstream | Remaining acceptance or engineering | Prerequisite/owner |
| --- | --- | --- |
| Notable | Retain/kill review, then the owned flag PR and production/homepage verification | Founder review through **2026-09-15**, then recorded retain decision |
| Analysis | Frontend activation, full gates, both-theme preview and Pro-account acceptance | Founder records effective Vercel flag and companyfacts warm-up; live account smoke remains founder-held |
| AI quality and coverage | Wrong-snap report, evidence-snap arming/re-pin; golden breadth then 6-K classifier/re-pin | First actual strong-judge artifact with **24/24 scored**, then founder arm decision. W3-8a's existing more-than-one-week delay exception had not elapsed on September 8 |
| Fleet scaling (E09) | Cross-instance generation ownership and shared SEC admission are **not implemented** | Effective fleet/egress/provider/database budgets and bounded founder design decision; proposal is complete, build is held |
| Billing/product | E06 event-selection reconciliation if production differs; calendar licence/activation and price/trial/promo/registration decisions | Founder Stripe selected-events/API-version observation and product/legal decisions |
| Data and operations | Seed/SIC/warm-up/pregeneration/drain and anomaly coverage; automatic changed-membership PR publication; backups/alerts/restore acceptance | Existing founder console/data prerequisites in wave-3 §2 and wave-2 §6; do not rerun completed W3-9 or restore the removed FMP prerequisite |
| Dependency/hygiene | Vitest 5, jest-dom 7 and jsdom/types 30 majors; D8 stale-branch deletion; alert #270 | Founder approval. Prepared majors need current-main integration and full gates before publication. Fresh Dependabot versions beyond original #752 are a subsequent queue |

Notable provisioning and W3-9 repair are already complete; their later acceptance steps must
not be confused with repeating those operations. Retention's first scheduled live run is
separate from its founder-observed dry run. No actual customer/revenue/cohort outcome or fleet
headroom measurement is established by the code releases alone.

## Findings and challenges to retain

One runtime must-fix and one historical contract-authorization defect were resolved as described
above. A **should-fix remains open**: chat admission releases its slot before the prior provider
transport finishes closing, permitting bounded cleanup overlap. It is tracked explicitly in
[todo](todo.md#astra-audit-and-remaining-plan--2026-09-08), as instructed, rather than included
in unrelated dependency work. Historical production impact of the crash scenario was not
measured; no replay or live email/job test was performed.

Migration/evaluation-count summaries were inaccurate; dated corrections preserve the old
records. Some historical local mutation tails and independent curls cannot be reconstructed
from GitHub, and the audit states that limit. Local native-library/sandbox restrictions required
environment restoration and full reruns; they are resolved, not outstanding product failures.
The actual strong-judge report is still unavailable (latest inspected artifact `10029049893`,
0/24 scored). Routine judge-off regressions do not replace it.

The next engineering work follows the named prerequisites, not an open-ended new feature queue.
Use the [live ordered checklist](todo.md#remaining-master-plan--astra-checkpoint-2026-09-08)
and [continuation handover](handover-astra-continuation-2026-09-08.md) for exact release points
and remaining decisions. No completion percentage is assigned to workstreams of unequal scope.
