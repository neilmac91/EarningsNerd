# Decision record 17 — D3 stage 1 merged and deployed (the eight Cloud Run jobs and the task worker pinned to 1 + 1; PR #1131), and its deploy found to be the first CI rollout of durable background tasks (intended, the founder confirms); D3 stage 2 re-scoped by its design investigation and decided by the founder (option A: guard, then pin; backfill-facts to move off Monday 07:00, the founder's scheduler change, pending); the backend suite's live requests (fix pre-registered); PR #1129 review record; ninth deploy-skip proof; ledger events 35–36; superseded burst figures corrected; chief defect 6; closure 168 (chief, 2026-10-08)

Recorded 2026-10-08T20:30:19Z, amended 2026-10-09T06:14:33Z after the record-17 review and the founder's answers and 2026-10-09T06:32:09Z after its delta review, by the chief (`https://claude.ai/code/session_01GWYV7WXWstgVGQG43YcSM8`). Context: record 16 merged
to main as `2129a8035c0a36325ec5c820225dfacb4ac428c5` (PR #1129, 2026-10-08T18:53:40Z); D3 stage 1 merged as
`da636f6c57241273fb99444cb8f1e92a03c24522` (PR #1131, 20:08:15Z); this branch was restarted from `da636f6c`. Records only: no
code, workflow, migration, cloud, IAM or production change in this PR; no provider call; no reservation; no source material
opened.

## D3 stage 1 — merged and deployed (PR #1131)

**What it changed.** The deploy job's env maps for the private task worker, the pregenerate job, the six-job loop and
backfill-facts now end in `SEC_RATE_LIMIT_PER_SECOND=1,EDGAR_RATE_LIMIT_PER_SEC=1`; the API service is left at the code
defaults (10 and 9) for stage 2. A rule-12 gate (`backend/tests/unit/test_sec_process_budgets.py`) checks that every Cloud Run
update in the deploy job targets an inventoried process exactly once with both pins, the staged service excepted, and that the
fleet arithmetic in `docs/OPERATIONS.md` holds. `docs/OPERATIONS.md`, `docs/CONFIGURATION.md`, `docs/DEPLOYMENT.md`,
`tasks/gcp-deploy-runbook.md` and `backend/docs/plan_sec_pipeline.md` (whose change makes the merge deploy) state the pins, the
arithmetic, the limits and the rollback. Eight files, +305 / −24, four commits.

**Review.**
- Lean three-lens review of `0432bf4d` (workflow `wf_4ccc6fc9-a48`: correctness, tests and gates, docs and ops; three
  refuters; 18:57–19:25Z): no blocker; three should-fixes. One was confirmed by its refuter: the per-second ceilings under the
  pin were stated as 3 / 15 / 18 and are 2 / 10 / 12 (a one-token bucket admits at most one request in any second). A second
  (the gate could be escaped) was rated a nit by its refuter and fixed anyway. A third (operators had no documented or tooled
  way to confirm the pins are live) was refuted to a nit and answered in the docs' observability wording. Nits on rollback wording, the SIC lookup that
  draws from both limiters, the worker's 480 s task limit and the observability wording were applied. One deferred: the
  `notable_filings_service.py` docstring's "10 req/s bucket" (under `backend/app/`, so it goes with stage 2). Fixes in
  `31a6132a`.
- One delta reviewer (launched 19:29Z), three checks: `31a6132a` no blocker, one should-fix (the runbook's job-create commands
  set no pins) and five nits: the should-fix and four nits applied in `f307a12d`, the fifth (the stage-2 exemption written in
  two places) left for stage 2; `f307a12d` no blocker, two nits (one fixed in `cf64574d`, one recorded as a
  known limit of the gate); `cf64574d` **no blocker, bound to `cf64574d9ec6313a81882602c9b7ae170e0c4b2f`**.
- Known limits of the gate, for stage 2's hardening: a global flag before `run`, `gcloud run worker-pools`, a deploy step
  that calls a script, a local composite action. `ci.yml` uses none of them.
- Codex: summary comment 6068000391, Completed 2026-10-08T20:04:56Z on `cf64574` (trigger: draft marked ready), no findings;
  no override.
- Paid run: marking the PR ready at 20:00:42Z fired one `copilot-eval` run (37836232244, job 113513838886, 20:00:49–20:03:06Z,
  accepted 18 of 18) under ledger event 35's reservation (USD 0.060000, written 19:30:48Z); 36 calls, USD 0.006790; settled by
  event 36 (written 20:07:32Z), 0.053210 released, no excess. Event 35's statement names the head at writing (`31a6132a`); the
  PR left draft at `cf64574d` after the delta fixes; the reservation covered the one run that leaving draft fires, and exactly
  one fired. No push while ready. `eval-baseline` did not run (no `backend/app/`, `backend/evals/` or `backend/prompts/`
  change).
- `review-gate`: two runs started at 20:00:47Z (37836232169 and 37836232918); the first was cancelled at once by the
  workflow's concurrency group. Codex's summary comment (6068000391, created 20:00:55Z) carries the literal text "@codex
  review" in its boilerplate, so it fired an `issue_comment` run (37836273930, triggered by the Codex connector) whose
  re-run job re-ran 37836232169 at 20:01:11Z; that re-run took the concurrency group and cancelled 37836232918's job at
  20:02:19Z. The chief's merge at 20:05:17Z was refused ("Required status check \"review-gate\" is cancelled"),
  13 s after 37836232169's re-run had itself succeeded (20:05:04Z). The chief re-ran 37836232918 once (attempt 2, success
  20:05:38–20:05:54Z) and squash-merged with the expected head `cf64574d` at 20:08:15Z. The gate's trigger
  (`review-gate.yml:61`, any comment containing "@codex review") matching Codex's own boilerplate is a latent cancel
  cascade; it is noted for the workflow's owner (todo).

**Deploy (main CI run 37837186714 on `da636f6c`; green 20:08:18–20:19:30Z).** `deploy-backend` job 113520716670 (20:16:50–
20:19:11Z) built and pushed image `da636f6`, applied no migration (`applied=0 skipped=41`), and:
- updated `earningsnerd-pregenerate`, `earningsnerd-filing-scan`, `earningsnerd-filing-digest`,
  `earningsnerd-earnings-calendar-refresh`, `earningsnerd-earnings-day-alerts`, `earningsnerd-notable-filings`,
  `earningsnerd-retention-purge` and `earningsnerd-backfill-facts`, each with an env map ending in
  `SEC_RATE_LIMIT_PER_SECOND=1,EDGAR_RATE_LIMIT_PER_SEC=1` (all eight found; none skipped);
- deployed the API service as revision `earningsnerd-backend-00450-4ql` (100% of traffic) with no SEC key in its env map, so it
  stays at the code defaults;
- **deployed the private task worker** as revision `earningsnerd-task-worker-00003-d5z` (100% of traffic), with both pins;
- passed the deep health check (`/health/detailed`: healthy; database reachable; SEC circuit closed).

The chief expected the worker step to report its rollout disabled; it did not (next section).

## The stage-1 deploy was the first CI rollout of durable background tasks

The deploy job reads two repository variables, `GCP_DURABLE_TASKS_ENABLED` and `GCP_TASKS_WORKER_URL`. Its logs show:
- **00:09:45Z** (PR #1127's deploy, job 113080756294): `DURABLE_TASKS_ENABLED: false`, no worker URL; the worker step printed
  "Durable task worker rollout is disabled." and the API service was deployed with durable tasks off. Record 16's "off on the
  last deploy" refers to this deploy and was true.
- **00:42:46Z, 03:42Z, 04:27Z and 19:01Z** (the deploy-skip jobs of PRs #1112, #1110, #1128 and #1129):
  `DURABLE_TASKS_ENABLED: true` with the worker's URL. No commit changed this, so someone with repository-admin access switched
  the variables on between 00:09:45Z and 00:42:46Z. That is the last step of `docs/DEPLOYMENT.md`'s rollout procedure (provision the queue, the task identity and its
  IAM; bootstrap the private worker; probe; then set the two variables), which leaves the rollout to the next deploy.
- No CI deploy ran between 00:11Z and 20:16Z (the eight merges in between — PRs #1112, #1110, #1128, #1108, #1113, #1120,
  #1130 and #1129 — each skipped every deploy step). But the API service's revision numbers show one change outside CI in
  that window: CI's 00:10Z deploy created revision 00448 and the stage-1 deploy 00450, so revision 00449 was created between
  00:10:40Z and 20:17:57Z by something other than a GitHub workflow (no Ops run either). Its content is unknown, so when
  the API itself switched to durable tasks is not established. At the latest it switched with **the stage-1 merge's deploy
  at 20:17–20:18Z, the first CI deploy after the variables changed**. That deploy updated the worker to the new image with
  the pins, then redeployed the API service with `DURABLE_TASKS_ENABLED=true` and request-based CPU (`--cpu-throttling`).
  From then at the latest the API hands background work — filings-list refreshes, first-visit
  history backfills, companyfacts syncs, the `/internal/` job triggers — to the Cloud Tasks queue and the private worker
  instead of running it in-process.

The worker pin therefore took effect at once, not later, and the founder's durable-tasks question in record 16 (item 4) is
no longer about the future (stage 2 below).

What the chief verified: the run's success, the worker and service revisions serving 100% of traffic, and the deep health
check. What the chief cannot verify with the existing read-only operations (`ops.yml` reads neither the queue nor the
worker's task results): the checks `docs/DEPLOYMENT.md` lists after this deploy — authenticated task success, task retries and
errors, API latency and SQL connections. They belong to the rollout's owner (founder item 2). Rollback, per the same document:
set `GCP_DURABLE_TASKS_ENABLED=false` and restore the API's `DURABLE_TASKS_ENABLED=false` with `--no-cpu-throttling`; keep the
worker available to finish queued work; do not pause or delete the queue with unfinished tasks.

**Chief defect 6.** PR #1131's description said the worker's rollout "is off today, so the step still exits early", and the
chief planned to verify that the step skipped. The skip-job logs the chief cited as the seventh, eighth and ninth deploy-skip proofs
(03:42Z, 04:27Z, 19:01Z) already showed `DURABLE_TASKS_ENABLED: true`. The deploy did what the variables said, so nothing was rolled out against their
owner's setting, but the reviewers and the founder were told the merge would not touch the worker. The founder has since confirmed
the rollout was intended (below). Rule: before merging a deploying PR, read the repository-variable values in the most recent
`deploy-backend` log (a skip job prints them), note when they were read (they can change after that log), and state in the PR
what the deploy will roll out beyond its own diff. Machine enforcement (rule 12) goes in the stage-2 PR, which edits the
deploy job anyway: the job prints its variable-driven switches in one line before deploying, and a test pins that line.
That gate makes the values readable in every `deploy-backend` run, deploying or not; it cannot make the chief read them
before merging or state them in the PR, which stays a review-checked rule.

## D3 stage 2 — what its design investigation found; the founder's decision

Under closure 167's label `d3-stage-2-pr-01`, one read-only design workflow (`wf_41c365bd-3e9`, nine agents, 18:06–19:48Z:
four readers, three designs — minimal-diff, product-first, robustness-first — a judge and a refuter; probes offline, with
sockets disabled or fake transports) asked how the API service could run at 1 + 1 under the founder's staged choice. Findings
the chief accepts:

1. **The insider cold load costs more than record 16 said.** edgartools' Form 4 parse looks up every reporting owner's
   submissions (`Entity(cik).data`; no in-process cache, though the HTTP file cache keeps a response for 30 s), so a cold load
   is about two requests per Form 4: one submissions request plus up to 60 Form 4s took 97.9–127.2 s in a zero-latency
   harness at the pin's measured 1.051 s spacing (63 s is the floor without owner lookups), against a 30 s client and a 60 s
   server timeout. A
   timed-out fetch keeps running and spending the instance's tokens, and the timeout counts toward the shared SEC circuit
   breaker.
2. **Making it fit is a large change, and the leading plan has a hole.** The judged design needs an offline Form 4 parse, a
   bounded resumable scan and explicit partial results (additive response fields and frontend polling); the judge recommended a
   shared per-accession store before the panel is turned on. The refuter found a blocker: on this path edgartools hides SEC's
   403 and 5xx responses (`filing.xml()` returns None; SEC's rejection page raises an error with no status), so the plan's
   "stop on pushback" does not work as designed. Its remedies: treat None from an uncached fetch as a failure, classify
   edgartools' identity and status errors, or fetch through a status-checked path of its own.
3. **Pinning the service costs more than the insider endpoint:**
   - a pre-existing bug: the company-search fuzzy fallback (`EdgarClient.search_company`, through `get_company` and
     `_transform_company`) downloads submissions on the event-loop thread and always fails on a field-name mismatch, so it returns nothing; at 1 req/s each unmatched search can stall the
     whole instance for 10 s or more; it is reachable without signing in;
   - summaries: a cold generation costs two or three edgartools requests and fits; six at once on one instance (the per-process
     limit) take about 12–19 s to drain (estimated), so XBRL enrichment (15 s budget) is expected to fall back to companyfacts or regex
     under that load;
     a mega-filer's filing older than its recent submissions window needs about 43 history requests (about 45 s), past every
     enrichment budget;
   - the filings list's first view, coverage and full-text search cost one request each: fine at low concurrency, queued
     under load.
4. **Stage 1 itself is not expected to hurt pregenerated summaries.** pregenerate generates one filing at a time, two or three
   edgartools requests each. Not yet observed: the first check is the next pregenerate run that generates a new filing.

With the worker now enabled, the configured Monday 07:00 UTC overlap after stage 2 is 12 req/s in any one second (two service
instances, three jobs and the worker at 2 each), plus up to 2 more while one task child hands over to the next: above SEC's 10.
1 + 1 is the per-process floor, so only a schedule change or holding the worker in that window brings it to 10.

So the founder's staging condition ("once the insider panel is made budget-aware") is neither small nor sufficient: the panel
is documented as off in production, its rework is large, and the service pin costs summary enrichment under concurrency whatever happens to
the panel. The chief put the choice back to the founder, with a recommendation (the founder chose A; see "The founder's answers"):

- **Option A (recommended): guard, then pin.** One code PR: (i) a server-side switch for the insider endpoint, off unless
  set while its panel stays off (the endpoint answers 404 when off), so a dark feature stops being a public fan-out of up
  to about 120 SEC requests per cold call; (ii) delete the always-failing fuzzy-search fallback (no search result changes; up to
  10 event-loop SEC downloads per unmatched search removed); (iii) pin the API service to 1 + 1 and drop the gate's staged
  exemption. Accepted cost: under heavy concurrency first-time summaries fall back to companyfacts or text grounding for
  financials and SEC-backed pages queue; a mega-filer's older filing loses XBRL enrichment on its first generation; turning
  the insider panel on later needs option B's rework first. Why: at beta scale, concurrent cold generations are rare, while the
  two service instances at the defaults are the dominant unbounded term, and an SEC lockout from a burst would stop every SEC
  path for all users and jobs.
- **Option B: rework first, then pin** (record 16's staging as written): the budget-aware insider scan with its own
  status-checked fetch, response additions and frontend polling, then the pin. Several PRs with frontend and API changes; the
  service stays at the defaults meanwhile.
- **Option C: stop at stage 1 for the service.** Land (i) and (ii) as hardening; leave the service at the defaults; revisit
  when usage grows or SEC pushback is seen.

With A or B, the Monday overlap needs one of: move a Monday 07:00 job out of that minute, hold the worker in that window, or
accept 12 configured (the founder chose to move backfill-facts). Stage 2's PR runs under closure 167's label with its scope
set by the founder's answer; its `eval-baseline` reservation is written before its first push touching `backend/app/` and its
`copilot-eval` reservation before it leaves draft.

## The backend suite's live requests — fix pre-registered

Record 16 found that 11 tests make 72 outbound attempts per full run (60 to `efts.sec.gov`, 10 to `data.sec.gov`, one to
`www.sec.gov`, one to Yahoo Finance). The `backend-tests` job of main CI run 37837186714 (pytest 20:09:20–20:16:03Z) is one more
such run; so is every CI run until the fix lands. The fix — the 11 tests made hermetic (through conftest fixtures where a test
is locked by rule 6) and an outbound-network block in the test configuration as the rule-12 gate — is pre-registered as
`test-hermeticity-pr-01` (closure 168): a read-only investigation, the lean three-lens review with refuters and one delta
reviewer. It changes only `backend/tests/`, so its merge deploys nothing; `copilot-eval` runs on `backend/**`, so a
reservation is written before it leaves draft.

## PR #1129 review record closed (decision record 16)

- Head `b8f737b0` reviewed by the single pre-registered reviewer (closure 166, `record-16-reviewer-01`, launched 17:58Z): **NO
  BLOCKER**, 6 should-fix and 7 nits, applied in `ace8e31b`. Delta on `ace8e31b`: NO BLOCKER, one should-fix, five nits and one
  `data.sec.gov` proxy connection to attribute, applied in `3c4eb1a1` (the connection came from the test suite). Delta on
  `3c4eb1a1`: NO BLOCKER, two nits, applied in `331827d6`. Delta on `331827d6`: **NO BLOCKER bound to
  `331827d63808dbfa63214f91592cffef53e8c48a`**. Closure 167 was amended twice in place before merge.
- Codex: summary comment 6066719810, Completed 2026-10-08T18:47:08Z on `331827d` (trigger: draft marked ready), no findings; no
  override; `review-gate` passed.
- Merged `2129a803` at 18:53:40Z. Main CI run 37827793356 green (18:53:43–19:01:42Z); its `deploy-backend` job 113488456601
  logged `No deployable backend changes - skipping deploy.` and skipped every deploy step — the ninth live proof of the PR
  #1101 correction.
- PR #1130 (another session's lane: custody of the prompt-candidate archives) merged as `1928d057` meanwhile. Its files are
  under `tasks/review-evidence/`, which the chief does not open; observed only.

## Corrections to earlier records (burst figures)

Record 02 (D3, and its Appendix A's B36 row: "the first-second ceiling is 2× sustained"), record 06 (CTO revision 4's B36
line), record 08's fleet assumption (29 in the first second; under the pin 3, and ten processes 30), the CTO dispatch
`CTO-ENVELOPE-HANDBACK-02.json` (B36: first-second 29), the production-config observation of 2026-10-04, checkpoint decision
11 and the checkpoint's PR #1088 review record state a first-second ceiling of 29 per process at the defaults and 3 per
process (15 at Monday 07:00; 30 for ten processes) under the pin. Stage 1's review established that the app's bucket starts full with capacity equal to its
rate and refills continuously, so in any one second it admits at most 2R − 1 requests: 19 at the default 10, 1 at the pin.
Corrected: **28 per process at the defaults** (19 + edgartools' 9); **under the pin, 2 per process**; on the schedule before
the founder's backfill-facts move, 10 in the Monday 07:00 UTC overlap with the service pinned and the worker held, 12 with
the worker (up to 14 during a task-child handover); after the move, 8, 10 and 12; and 20 for ten processes (not 30). The
sustained figures (19 per process at the defaults, 2 under the pin) are unchanged. The earlier records are not edited; this
entry supersedes those figures and checkpoint decision 11 points here. The CTO handback's bound B36 carries the old figure
until its owner's next revision.

## Registration (closure 168)

`control/source-context-exclusion-168.json` (506 → 532, after one in-place amendment before merge):
- resolves `record-16-reviewer-01` to `launched-2026-10-08T1758Z`;
- resolves `d3-sec-budget-pr-01` to its 13 launch-time identities: the six investigation agents of `wf_6eb86498-eec`, the six
  review agents of `wf_4ccc6fc9-a48` and the delta reviewer launched at 19:29Z;
- registers the nine identities of `wf_41c365bd-3e9` under `d3-stage-2-pr-01`, which stays provisional for the stage-2 PR's
  remaining contexts;
- pre-registers `record-17-reviewer-01` and `test-hermeticity-pr-01`, and (amended in place before merge, after the review)
  `record-17-delta-reviewer-01`: the reviewer's context ended with a container restart after it returned its verdict, so the
  delta check runs in a fresh, separately registered context.

Disclosed side effects, from the agents' transcripts:
- `record-16-reviewer-01`: 19 commands issuing 39 read-only `gh api` GETs to GitHub; one read of the session proxy's status page; the records gate
  run and `git apply --check` inside scratchpad copies; scratchpad writes.
- Stage-1 review and delta reviewer: writes only to scratchpad copies (four scratch `git init`s, one with a commit; none in the
  repository); targeted tests only, under the network guard; no full suite.
- Stage-2 design: 3 commands issuing 7 read-only `gh api` GETs (`read:history-and-constraints`: commit history and PR
  #330's title and body); offline probes and scripts in
  the scratchpad. `refute:plan` ran five targeted test files in the chief's scratchpad worktree without the network guard (89
  passed; none of them is among the 11 that make requests), which modified that worktree's gitignored `backend/earningsnerd.db`.
  No stage-2 design agent ran the full suite, so none reached SEC through it, and none made any other SEC request.

No context gains source A/B, reconciliation or blind financial judging eligibility; all earlier identities and adverse
histories are retained.

## Spend

Since record 16: **ledger events 35–36, 36 DeepSeek calls, USD 0.006790.** Event 35 (written 19:30:48Z; version 36,
`3667842a…`, 108,881 bytes) reserved USD 0.060000 for the one `copilot-eval` run that leaving draft fires; event 36 (written
20:07:32Z; version 37, `f138dc97…`, 110,613 bytes) settled it at 0.006790 (1,062,931 prompt tokens, 1,056,887 of them cache
hits; 4,520 completion), released 0.053210, no excess. Recorded use 0.748572 → 0.755362 (872 → 908 calls); conditional
unreserved headroom 22.369715 → 22.362925; holds unchanged at 1.881713; cumulative recorded usage (all stages) 4.539611 /
2,967 calls. Active reservations 0; paid dispatch HELD. Both events are appended to `control/LEDGER-ACCESS.md`.

External mutations by the chief since record 16: PR #1129 squash-merged `2129a803`; this branch restarted (a force push was
denied by the auto-mode classifier as a destructive git action — classifier denial 8 — and not retried; the remote branch had
been deleted on merge, so a plain push recreated it); PR #1131 opened as a draft, four commits pushed, marked ready,
description edited, one cancelled `review-gate` run re-run, squash-merged `da636f6c` — whose deploy updated the eight jobs, the
task worker and the API service in production (founder-instructed D3 deploy; the durable-tasks rollout above came with it);
ledger events 35 and 36 written (private ledger republished twice); this branch restarted at `da636f6c`; this record.

## The founder's answers (asked 2026-10-08 at about 20:34Z; received 2026-10-09)

The chief put three questions to the founder after this record was first pushed. The answers, as given:

1. **D3 stage 2: "A: guard, then pin (Recommended)".** Stage 2 is one code PR: the insider endpoint behind a server-side
   switch that is off unless set (it answers 404 while off), the always-failing fuzzy-search fallback deleted, and the API
   service pinned to 1 + 1 with the gate's staged exemption removed. It runs under closure 167's label `d3-stage-2-pr-01`;
   `eval-baseline` is reserved before its first push touching `backend/app/`, draft or not, and `copilot-eval` before it leaves
   draft.
2. **The Monday 07:00 UTC overlap: "Move backfill-facts (Recommended)".** The option read: "You change the
   backfill-facts-weekly Cloud Scheduler job from 07:00 to 07:30 Monday (one gcloud command; it makes ~0 SEC requests
   anyway). The overlap is then 10 = the cap." The founder moves the `backfill-facts-weekly` Cloud
   Scheduler job from `0 7 * * 1` to `30 7 * * 1` (one `gcloud scheduler jobs update http` command; the chief has no cloud
   access). Then, with the service pinned and the worker enabled, the 07:00 overlap is configured at 10 req/s (two service
   instances, pregenerate if still running, the hourly scan and the worker at 2 each), with up to 2 more in a second in which
   one task child hands over to the next. The stage-2 PR updates `docs/DEPLOYMENT.md`'s schedule line, `docs/OPERATIONS.md`
   and the gate's arithmetic to match.
3. **Durable tasks: "Yes, intended; I'll check".** The rollout was intended. The founder runs the post-deploy checks in
   `docs/DEPLOYMENT.md`; no rollback.

## Founder actions this record needs

1. **Move `backfill-facts-weekly` (the founder's choice; cloud access is the founder's):** `gcloud scheduler jobs update http
   backfill-facts-weekly --location=us-west1 --schedule="30 7 * * 1"`, before the stage-2 PR merges (once the service is
   pinned, the 07:00 overlap is 12 configured until it moves). Tell the chief when it is done.
2. **Durable tasks (rollout owner, in hand):** the post-deploy checks in `docs/DEPLOYMENT.md` (authenticated task success, task
   retries and errors, API latency, SQL connections).
3. **Custody step A (optional, no deadline; unchanged):** relay record 16's five-field metadata request once; on outcome B, add
   "I adopt record 16's form (b) for R1".

Nothing in this record releases input, dispatches the planner, runs an export or operator leg, admits capacity, invites anyone,
changes a flag, adds load, implements E09 beyond D3 as instructed, redefines record 05's gate or changes the accepted reporting
contract.
