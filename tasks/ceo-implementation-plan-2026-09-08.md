# CEO implementation plan — quality before expansion

Date: 2026-09-08. Planning base: `c1bc866bfd61ba04b3f5f69ab629f5c8de8571b7`.
This continues the [master-plan checkpoint](master-plan-status-2026-09-08.md), informed by
fresh account inspection. The objective is a demonstrably useful, trustworthy filing-analysis
product for a controlled beta, with measured operating costs before expansion.

## Direction and authority

The founder delegated direct account access and necessary implementation edits on September 8,
with feedback requested only when necessary. Routine account observations and reversible,
evidence-supported configuration work are now agent-owned; the earlier blanket “no console /
live account access” limitation is superseded for this work. Use existing authenticated sessions
and established integrations. Keep credentials out of chat, logs and repository files. Authentication
or security approvals that require the account holder are concrete handoffs, not a reason to stop
independent engineering. Record the actual before/after state and verify each account change.

**Universe-wide pregeneration is held until the founder explicitly accepts the analysis-quality
evidence and releases that spend.** This supersedes the earlier D4 spend authorization for the
515-name generation run. W3-7 completion, a baseline re-pin or a green evaluation cannot release
this hold. Broad stale-summary regeneration is also deferred in this plan until quality is accepted;
a narrowly scoped repair is a separate decision. Existing example refreshes and bounded evaluation
are distinct workloads; do not describe a universe run as a warm-up to bypass the hold.

DeepSeek remains the production provider. Existing code review, locked-contract, committed-state
gate and serial release procedures continue. No new legal commitment, destructive cleanup,
security-access expansion, pricing/trial/registration change or open-ended spending is implied by
this plan. Major dependency maintenance is lower priority than quality and beta acceptance;
its previously requested specific decision remains recorded until resolved. No repeated question.

## Prioritized delivery sequence

Calendar estimates below are planning ranges in engineering days, excluding credential access,
paid-run queues and founder review. They are not delivery promises or authorization to skip evidence.
Each row produces a reviewable artifact or PR, with the owner accountable for verified outcomes.

| Priority | Deliverable and owner | Work and exit evidence | Dependency / estimate |
| --- | --- | --- | --- |
| P0 | Quality acceptance specification — engineering; founder accepts final evidence | Freeze rubric, severity definitions, cohort manifest, source references, spending ceiling and stop conditions before tuning. Explicitly distinguish existing regression gates from proposed acceptance targets below. | Start now; 0.5–1 day for specification, cohort verification separately |
| P0, parallel | Account and spend inventory — engineering | Verify effective Vercel settings/deployment, job commands/schedules, judge credential availability, PostHog project, Stripe event selection, backups/alerts and fleet budgets. Record observations, unknowns and proposed changes with rollback. | Existing sessions where available; 1–2 days, no production job run needed for inspection |
| P1 | Usable quality readout / W3-7 — engineering | Verify judge access, smoke one filing, then obtain an actual 24/24 strong-judge artifact. Diagnose wrong-snap and figure-trace findings against source context, propose arm/hold with examples. | Credential and bounded evaluation budget; 1–2 days after access, excluding defect fixes |
| P1 | Quality fixes and controlled arming — engineering | Fix confirmed material errors in isolated PRs. If evidence supports the arm decision, change all four parity locations and produce the authorized three-run pin. Retain rejected outputs and before/after evidence. | W3-7 assessment and concrete arm decision; 1–3 days per substantive fix, variable |
| P1 | Breadth, then 6-K / W3-8a → W3-8b — engineering | Add verified REIT, utility, insurer and two small-cap development goldens; independently implement and prove 6-K scorer contract before classifier/goldens. Each PR has its own measurement and pin. | Existing sequence; one re-pin PR open. W3-8a's >1-week readout-delay exception remains available; 3–6 days total initially |
| P1, parallel | Controlled-beta reliability — engineering | Resolve audit S1 provider-cleanup admission overlap; reconcile Stripe endpoint coverage; prove monitored failures and backup/restore procedure in an isolated target. Document current fleet safety limits. | No broad generation or higher capacity; 2–4 days plus an explicitly scoped restore exercise |
| P2 | Analysis and Notable acceptance — engineering | Analysis: verify actual deployed behavior and bounded companyfacts readiness, both themes and an approved test account. Notable: review observed source quality through Sep 15, record retain/kill, then flag PR if retained. | Analysis Vercel setting already true; data/behavior acceptance incomplete. Notable review week retained; 1–2 days each after evidence |
| P2 | Independent quality acceptance — engineering assembles; founder decides | Execute the unseen holdout below within its budget; review evidence, adjudicate defects and run a later out-of-time sample. Present a concise acceptance dossier including weakest outputs. | Stable candidate after quality fixes; 2–4 days engineering plus human review time |
| P2 | Controlled invite-only beta — engineering operates; founder handles recruitment/commitments | Start with a proposed 5–10 consenting target users. Measure first useful analysis, repeat use, alert return, failures, feedback and cost per successful analysis. Review two weekly cohorts before expansion. | Quality acceptance for offered filing classes, safe fleet envelope, support and applicable legal readiness; 2 calendar weeks of observation proposed |
| P3 | E09 fleet coordination and expansion — engineering | Use effective fleet, egress and DB/provider budgets to select the bounded design. Prove cross-instance ownership, fencing, fail-closed SEC admission and recovery under concurrent service/job processes. | [E09 proposal](e09-fleet-coordination-proposal-2026-09-08.md); prioritize earlier if inspection shows the existing beta envelope is unsafe. 4–8 days after design decision |
| P3 | Wider coverage and pregeneration — engineering after founder release | After quality approval, obtain explicit run scope and spending cap; execute a small canary, inspect quality/cost, then bounded batches with checkpoints. Universe-wide execution remains held today. | Quality acceptance **and** safe fleet budget **and** explicit spend release; estimate only after measured canary |
| P4 | Optional product and housekeeping | Calendar licensing/activation, Insiders, prices/trial/promo, major dependency upgrades, fresh #780, D8 and #270. Triage security advisories promptly; otherwise avoid displacing core quality work. | Existing specific decisions; no date-driven activation or unnecessary spend |

## What “world-class” acceptance must demonstrate

Passing today's gates means a candidate has not violated their measured regression contract. It
does not establish complete, useful or superior investment research. The current judge-off
baseline has advisory citation/quote dimensions and the last recorded strong-judge report is
unavailable. Even 24/24 scored proves measurement completeness, not that the judgments are positive.

The following are **proposed acceptance targets**, not claims of current results or newly implemented
CI gates. Freeze the targets and scoring definitions before running the holdout. Automated gate
implementation belongs in the corresponding quality PR with its mutation proof; this planning PR
adds no prose-mirroring test and does not represent the targets as already enforced software.

- **Factual safety:** zero material invented figures, wrong periods/currencies/units, misleading
  source citations, fabricated quotations or unsupported assertions in the acceptance sample.
  A material error could change a reasonable reader's view of results, liquidity, risk or guidance.
  Every such error blocks the affected capability; no aggregate score may conceal it.
- **Completeness and usefulness:** independently establish the filing's material issues first.
  Proposed bar: at least 95% of outputs score at least 4/5 on both material completeness and
  analytical usefulness, with no filing exhibiting repeated substantive failure. Score 4 means
  accurate coverage of the material issues, useful filing-supported explanation and only minor omissions.
- **Traceability:** adjudicate each challenged claim against the exact selected filing, including
  context, tables and XBRL period. Verify quotation exactness and navigable citation destinations.
  A plausible number elsewhere in a filing does not prove the claim's context is correct.
- **Independent review:** two reviewers blinded to candidate identity review the outputs and
  source evidence; disagreements are adjudicated. AI judges supplement human review. Agent
  agreement alone is not independent human or domain-expert acceptance. Founder time or any
  paid external reviewer is scoped before committing to it.
- **Comparative usefulness:** blind-compare a representative subset with the current product and
  an independently prepared source-grounded reference brief. Record which is more useful and why;
  do not claim market superiority without a fair, defined comparison and evidence.

Proposed final holdout: **30 previously unused filings, three generations each**, with a frozen
accession/source manifest outside development goldens. Stratify by sector, company size, annual
versus quarterly reporting, losses, non-calendar periods, foreign currency, sparse disclosures
and amendments. Include 20-F and, only after W3-8b, supported 6-K classes. Unsupported classes
remain excluded or honestly restricted rather than silently accepted. This is 90 outputs for
review, not 90 companies to seed in production. Human review capacity is a real prerequisite.

Start smaller: offline extraction/citation tests and source packets, one representative paid smoke,
the existing 24-attempt readout, then the holdout after serious defects are fixed. The generation
provider stays DeepSeek; the strong judge is an evaluator. Pin all effective settings, source SHA,
model IDs, retries and token limits. A candidate tuned on a failed holdout must face fresh unseen
cases as well as regression cases. Add a later out-of-time sample before releasing universe spend.

Before any new paid evaluation program, document maximum calls, retry ceiling, token budgets,
verified current prices and an enforceable monetary ceiling. A historical report showing `$0.0`
is not an estimate. A serious correctness failure stops promotion; missing rows, judge errors or
truncated grounding invalidate acceptance. Do not use repeated draws to select flattering outputs.

The founder receives the rubric, complete defect register, adjudicated scores, actual spend,
strongest and weakest examples, and a clear recommendation. Final quality acceptance and release
of the universe-wide hold are separate recorded decisions; absence of a reply is neither.

## Controlled beta and operating discipline

Use the existing invite-only posture. First validate summary → citation → useful decision-support
workflow on the selected cohort. Analysis is accepted only when its data, rendering and entitlement
behavior work together; configuration alone is insufficient. Defer calendar/Insiders additions
unless user evidence shows they are essential to the core proposition.

Reconcile PostHog definitions and exclusions before reading conversion: exclude internal agents,
founder tests, bots and duplicate events; use privacy-conscious aggregate reporting. Distinguish
successful generation, a user judging it useful, and a payment actually allocated by Stripe. Report
cohort counts and denominators, not unsupported conversion claims from tiny samples. Track p50/p95
time to first useful output, failures/degraded output, citation use, weekly return, alert return,
refund/support burden and cost per successful analysis. Set expansion thresholds after the first
measured cohort; a speculative revenue percentage is not a launch criterion.

Before increasing traffic, establish a safe aggregate SEC/provider/database envelope across service
instances and overlapping jobs. Low user count does not make a per-process limiter global. If the
current fleet cannot be shown safe, E09 moves ahead of beta expansion. Keep capacity unchanged until
that assessment. Backups/PITR/deletion protection and alert destinations must be observed, and a
restore must be rehearsed into an isolated target without touching the production data set.

For every implementation PR retain the existing full gates, independent review, mutation proof
per new invariant, exact-head merge and serial backend deployment verification. For account edits,
record target, before/after, reason, expected effect, rollback and observed outcome. If CI owns a
value, change its source through a PR so the next deploy does not undo a console edit.

## Account evidence and next actions

Fresh observations on September 8 supersede assumptions in earlier handovers; earlier entries
remain intact as historical records.

| Surface | Observed evidence | Consequence / remaining work |
| --- | --- | --- |
| Cloud Run | [Read-only Ops run 34264501243](https://github.com/neilmac91/EarningsNerd/actions/runs/34264501243) succeeded at source `c1bc866b`: service `00311-pm8` at 100%, DeepSeek v4 pro, invite-only, Notable/evidence-snap/figure-trace/forward-quote flags false; pregenerate image `b918bf3` with matching AI flags | No flag or capacity edit needed merely to discover state. Fleet/egress/database capacity inspection still required |
| Cloud Scheduler / pregenerate | Signed-in console shows seven schedules, all enabled; `earningsnerd-pregenerate-weekly` Monday 06:00 UTC. Its job command is `python scripts/pregenerate_examples.py`, no extra arguments, one task, three retries; last execution `earningsnerd-pregenerate-8gfmv` succeeded Sep 7 | Code defaults are eight example tickers / 15 annual-quarterly form selections, not the 515-name universe. Left unchanged. Scheduler delivery success is not proof of summary quality; no universe-wide execution found in this inspected scheduler list |
| Vercel | Signed-in project production deployment Ready on `c1bc866b`; `NEXT_PUBLIC_ENABLE_ANALYSIS=true`, Production and Preview, added Jul 6. PostHog ingestion host is EU | Remove the request for the founder to supply this flag. Verify deployment behavior and cohort warm-up before declaring Analysis accepted; do not add an unnecessary second source of the setting |
| GitHub evaluation access | Repository secret names show DeepSeek only; Production names show DeepSeek/FMP, no Anthropic. Weekly `measure` job has no Production environment and requires `ANTHROPIC_API_KEY` | Credential availability remains unresolved for the strong judge; never print or retrieve credential values into the ledger. The existing weekly workflow also emails through a live Cloud Run job, so use a separately reviewed measurement-only path for ad hoc quality work |
| GitHub membership publication | Current workflow permission reports `can_approve_pull_request_reviews=true` | Earlier policy uncertainty is removed; still require an actual changed-membership draft PR outcome. No permission broadening is needed or performed |
| PostHog / Stripe / Cloud SQL | PostHog EU sign-in succeeded through the existing Google account; organization EarningsNerd, Default project `117863`. Stripe and database recovery settings have not yet been inspected in this planning pass | Confirm actual account/project access; do not invent warm-up, billing, backup or analytics results |

No production settings, job executions, customer messages, new credentials or paid model runs
were changed/started during this planning pass. The existing read-only Ops inspection was dispatched;
it describes configuration and does not execute a Cloud Run job. Vercel/job edit inspection was left
without saving. The previous #781 post-merge main CI is now confirmed successful.

## First execution checkpoint

- [x] Publish this prioritized plan and record the new spend hold and account authority.
- [x] Inspect existing Google Cloud/Vercel access, example-job scope and effective service flags.
- [x] Replace the stale Analysis-value and Actions-policy observation requests with fresh evidence.
- [ ] Resolve strong-judge access without exposing credentials; propose a measured, bounded cost ceiling.
- [ ] Prepare the quality rubric, development/holdout manifests and source evidence packets offline.
- [ ] Prepare the smallest measurement-only workflow change needed to avoid unsolicited live report email.
- [ ] Inspect remaining PostHog/Stripe/Cloud SQL evidence and propose only necessary corrections.
- [ ] Continue W3-7 → W3-8 and the parallel reliability queue under the evidence conditions above.
- [ ] Present the first quality dossier and controlled-beta readiness decision; keep universe spend held.

Report at substantive milestones: what was released, what evidence changed the recommendation,
actual cost, unresolved quality defects and the next named decision. Do not create open-ended
background work or notification schedules without a request.

## September 9 execution correction

The previously fresh Dependabot #780 group is closed; its compatible minor SDK updates shipped and were verified through #791. Original major dependency decisions remain held. The EdgarTools study is complete and quality fixes #784–#791 have shipped as recorded in the September 9 handover. The first-checkpoint measurement-only workflow mode is prepared locally; no report/email job or paid weekly measurement was dispatched as a test. DeepSeek balance restoration now blocks further actual evaluation, independently of Fable's subscription limit and the founder's universe-wide pregeneration hold.

## September 9 final-review delivery correction

The final Fable reports are received and independently reconciled in the [final reconciliation](fable-quality-reconciliation-2026-09-09.md). This supersedes the missing-final-report prerequisite only: seven cases retain partial coverage, Amazon has a source-range ambiguity, and unseen human-reviewed acceptance remains open. Original reviewer counts are preserved separately; no global consensus defect rate is asserted.

Funding is restored for the ordered queue. Scope safeguard #794 merged as `47865758` with main CI `34315351755` and production revision `earningsnerd-backend-00319-kz4` verified. Only #792's failed summary job is now running as attempt 2, job `102352498206`; inspect its actual evidence before release, then release eval-error/identity c and assess integrated prompt d. FCF-basis e is a separate bounded candidate; #788 already addresses ROE/ROA labels. Missing source is a product coverage defect, and d does not resolve all traceability/narrative/acquisition failures. Existing master-plan, account, legal/product, vendor, universe-spend and historical-replay boundaries remain.
