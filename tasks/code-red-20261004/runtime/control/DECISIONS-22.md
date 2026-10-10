# Decision record 22 — record 21 merged (fifteenth deploy-skip proof); the read-back PR designed, implemented, reviewed and merged (sixteenth proof); the first live read-backs (`describe-service` PASS with the worker invoker policy PRIVATE, `describe-jobs` PASS, a `capacity-readout` over 10:55–12:55Z) and every durable-tasks post-deploy check completed from them (the first probe unverified); ledger event 45; seven backend deploys by other writers read back; closure 173

Recorded 2026-10-10T13:45Z, by the successor chief (`https://claude.ai/code/session_011jZyZqfNWZRqiFNWfTc3u8`).
Context: record 21 merged to main as `b32003f8` (PR #1172, 2026-10-10T10:44:46Z) and the read-back PR as `2d738050` (PR #1181,
12:50:28Z); the records branch `claude/stoic-wright-6jeujo` was restarted from main `2d738050` after its merged history (GitHub had
deleted the remote branch at the merge; it was recreated from main) and fast-forwarded to `aa9cf45b` (#1183) before this record's
first commit. This PR: this record, closure 173, the checkpoint, the appointments
file, one lesson and its index line, the archive ledger's record-22 entry, `tasks/todo.md` (two closed lines; the standing refreshed)
and `docs/DEPLOYMENT.md` (the durable-tasks checklist's verification paragraph): no application code, workflow, migration, cloud, IAM
or production change (nothing under `backend/`, so the merge deploys nothing); no provider call; no reservation; nothing opened
under `tasks/readiness-2026-09-21/acceptance/` or `tasks/review-evidence/`. The four `ops.yml` dispatches of this record (one refused
by its own guard) are read-only operations run from `main` by the founder's account; they changed nothing.

## Record 21 merged (PR #1172): review record closed; fifteenth deploy-skip proof

`record-21-reviewer-02` (closure 172; one context for the review and its deltas, launched 04:08Z after the first context ended at the
usage limit) reviewed `e375a7f` (BLOCKER: production had been redeployed by other writers while the record said it ran #1166's images;
applied in `b57093e` with the later deploys read back) and then, in eleven same-context delta checks each from an exclusion-safe
archive of the head, bound no blocker in turn to `c3b21fe`, `95780d5`, `61ed80e`, `8a3fd35`, `8fb9802`, `aa5fb5d` and `2d9d4a6`, with interim findings on the heads
between (its check of `e4a9910` was cut by the second usage-limit interruption and resumed from its transcript). Codex reviewed fourteen of
the eighteen heads from `c3b21fe` (the PR was marked ready at 04:40:30Z) to `2d9d4a6`, each on the ready event or an `@codex review`
request; four heads superseded within minutes, before a review was requested (`577edeb`, `2dc7a3b`, `10df20f`, `d0ce70a`), were
covered only by their successors' reviews. Its findings: four P1 and eleven P2 (the four P1 and eight P2 on the records-gate wrapper or its durable descriptions, three P2 on
the records' wording), each fixed and resolved — the last two, on `8fb9802` and `aa5fb5d`, taught the wrapper that a damaged `.git` and a dangling `.git` symlink are
inspection errors, not non-repositories; no findings on `2d9d4a6`. The wrapper's own `backend` scope ran the full backend gate
under Python 3.11 before every push from `8f64ee6` on (6438 passed on the final head; 20 wrapper cases). Squash-merged `b32003f8` at
10:44:46Z with an explicit title and message, before the merge train's #1176 as that session asked; main CI run 38045972688 green
(10:44:49–10:50:07Z); `deploy-backend` job 114196342079: the detector step ran, steps 6 to 17 all skipped (**fifteenth deploy-skip
proof**); `eval-baseline` skipped by the path filter; no `copilot-eval` run. The reviewer's last optional nit (an import out of
alphabetical order, outside the repository's ruff selection) was not taken, and its note that the inspection message quotes git's own
last stderr line, which can carry a path, is recorded here: the wrapper prints no path of its own, and such a line is never quoted
into a record.

## The read-back PR (#1181, `ops-readback-pr-01`): designed, implemented, reviewed and merged; sixteenth deploy-skip proof

**Design.** The successor's read-back design workflow `wf_b0cbcf69-f9d` (first agent 2026-10-09T23:07Z; thirteen of its fifteen
agents ended by the account's usage limit at about 23:24Z and re-run from 04:04Z, in the same run; the synthesis finished at 06:29Z) ran five readers over an exclusion-safe copy of
main and the Google Cloud documentation, three independent designs, three judges, three refuters and one synthesis that executed its
own specification (SPEC.md, 1,388 lines, with prototype bodies for both heredocs and the readout, run against the tests' own fakes).
**Implementation.** One agent (launched 09:28Z) implemented the specification in an exclusion-safe sparse worktree as commit `c56cd6c`
(nine files, +1290/−187): the `describe-service` and `describe-jobs` heredocs in `.github/workflows/ops.yml`, `ops/capacity/readout.py`,
five tests under `backend/tests/unit/`, `docs/DEPLOYMENT.md` and `docs/OPERATIONS.md`. The chief ran the full backend gate in a full
checkout under Python 3.11 (6516 passed) and pushed; draft PR #1181 opened 10:21:35Z; CI green; `eval-baseline` skipped by the path
filter; no `copilot-eval` run (PR #1123's paths).
**Review.** The lean three-lens workflow `wf_e5ff680a-2c4` (10:15–12:02Z; privacy and public-log safety; failure semantics; tests,
gates and docs; two refuters per lens; one synthesis) found no blocker: 5 should-fixes, 18 nits, 1 refuted. The should-fixes: the env
allow-list was only lower-bounded by a test (now pinned by an exact frozen literal); the PR body said every gcloud call captured stderr
while the two shell-level describe reads did not (the describe-jobs read now discards stderr, the describe-service read is a recorded
follow-up behind its byte-exact lock, the body names the scope); a non-dict job execution aborted the whole receipt (it now counts in
`unplaced_count`); `docs/DEPLOYMENT.md` said every describe failure prints every block and a verdict (traffic, undescribable-resource
and shape defects exit at once without one; the docs now say so). The in-PR nits applied with them: immediate exits name every defect
collected before them; the per-call gcloud timeout is 100 s so five reads fit the ten-minute step; a duplicate or nameless env entry
is a collected defect; both step timeouts are gated; the failed-describe test covers the first read and the `unavailable` class; the
docs no longer say the API deploy sets only `--min-instances`. Declined with reasons on the PR: bounding `DB_POOL_SIZE`,
`DB_MAX_OVERFLOW` and `taskCount` in describe-jobs alone (asymmetric with describe-service; `ci.yml` pins them); withholding custom
role names (an IAM role is a closed-charset identifier); a grammar for the bool `TASKS_WORKER_PROCESS` (a non-boolean never reaches a
ready revision); widening the stderr classifier on an unverified reading of the SDK; four null- or non-object-shape hygiene items
(shapes gcloud's `--format=json` does not emit; a crash on them is still fail-closed). Two pre-existing items outside the diff are
follow-ups: the receipt's bounded `error_detail.message` is not address-redacted, and the logs-probe step echoes raw gcloud stderr on
its denied branch. The fixes landed as `9f7c771` (12:13Z; 6525 passed; 257 in the nine relevant test files). The delta reviewer
(launched 12:14Z) bound no blocker to `9f7c771` (three optional nits: the describe-service shell read's inherited stderr, a docs
clause, one body wording — the wording applied) after six anti-vacuity mutations each failed their gate.
**Ledger event 45, ready, Codex, merge.** Event 45 (floor only; below) was written, published and read back before the PR left draft
at 12:32:17Z. Codex's ready-for-review run found one P2 on `9f7c771`: `show()` printed every allow-listed value with `repr()`, so a
nonnumeric SEC pin value would have reached the public log's env block before `require_sec_pins()` withheld it in the verdict. Fixed
in `dab895b` (12:42Z): the two pin names print through the same bounded formatter as the verdict (`bounded_pin`, reused by
`pin_state`); the privacy gate asserts the whole output; with the bounding removed five cases fail; full gate 6525 passed. Codex found
no issues on `dab895b` (12:46:52Z); the delta reviewer bound no findings to it (12:48Z; a ten-scenario differential of both heredocs
showed byte-identical output for digit pins and exactly one env-block line changed for nonnumeric ones). Squash-merged `2d738050` at
12:50:28Z with an explicit title and message, main carrying no pending deploy (#1176's deploy had been verified by the merge train at
11:16Z); main CI run 38053444141 green (12:50:30–12:55:47Z); `deploy-backend` job: the detector step ran, steps 6 to 17 all skipped
(**sixteenth deploy-skip proof**). Where the specification could not be applied as written is listed on the PR; after the review the
heredoc bodies and `readout.py` are no longer byte-identical to the specification's prototypes (five deliberate deviations, named
there).

## Production after record 21: seven deploys by other writers read back; eighteen later main runs classified

Record 21 classified main's runs up to #1140 (`b814242b`, 04:26Z). The eighteen runs after it, each from its `deploy-backend` job's step
conclusions (read through the platform's REST API, read-only), and the seven that deployed read from their logs through a redacting
filter (every Cloud Run default-domain host, signed query, address and token replaced; only the step markers, pins, migration counts,
revision and health lines kept; raw copies deleted):

| Merge | PR | Main CI run | `deploy-backend` job | Outcome |
|---|---|---|---|---|
| `1b58eb3e` | #1141 (users router) | 38024120612 | 114132073794 | **deployed** 04:32:17–04:34:42Z; service `earningsnerd-backend-00460-58j`, worker `earningsnerd-task-worker-00013-vsl` |
| `aa33afee` | #1139 (watchlist router) | 38024608062 | 114133515497 | **deployed** 04:40:32–04:42:59Z; `00461-797` / `00014-xm9` |
| `e7d3eaca` | #1138 (admin router) | 38025078237 | 114134634566 | **deployed** 04:47:00–04:49:34Z; `00462-rpt` / `00015-6fp` |
| `b026ceaf` | #1137 (auth router) | 38025449750 | 114135925220 | **deployed** 04:54:36–04:57:03Z; `00463-9sn` / `00016-gx9` |
| `f04f4af5` | #1163 (companies router) | 38025861581 | 114137337136 | **deployed** 05:02:59–05:05:37Z; `00464-9wc` / `00017-5ww` |
| `b38c94dd` | #1174 (move proof) | 38025884417 | 114137534456 | every deploy step skipped |
| `abda78ce` | #1164 (filings router) | 38026379554 | 114138864276 | **deployed** 05:11:40–05:14:13Z; `00465-gjn` / `00018-ckg` |
| `72a0ca03` | #1118 (agent workflow cost) | 38041285006 | 114182709245 | every deploy step skipped |
| `e26fd5a1` | #1175 (read-only GET pins) | 38043655631 | 114190029829 | every deploy step skipped |
| `58137d37` | #1178 (a11y) | 38044875339 | 114193129288 | every deploy step skipped |
| `b4874674` | #1180 (raw selects) | 38045859964 | 114196020758 | every deploy step skipped |
| `b32003f8` | #1172 (record 21) | 38045972688 | 114196342079 | every deploy step skipped (fifteenth proof) |
| `0b50b564` | #1173 (chrome ring gate) | 38046044483 | 114196551507 | every deploy step skipped |
| `0a672ebe` | #1176 (account deletion cancels every live subscription) | 38047385361 | 114200257270 | **deployed** 11:13:12–11:15:45Z; `00466-8d8` / `00019-97g`; the merge train posted "deploy verified" at 11:16:42Z |
| `0de046fa` | #1177 (move proof, SHADOWS) | 38047859714 | 114201762198 | every deploy step skipped |
| `cba20c81` | #1182 (todo line) | 38048440388 | 114203423982 | every deploy step skipped |
| `2d738050` | #1181 (the read-back PR) | 38053444141 | 114217934396 | every deploy step skipped (sixteenth proof) |
| `aa9cf45b` | #1183 (ESLint wiring timeouts; a todo line) | 38053943458 | 114219454239 | every deploy step skipped |

In each of the seven deploys, read through the redacting filter from the echoed commands and gcloud's result lines:
`apply_migrations: applied=0 skipped=41`; the worker update carries `DURABLE_TASKS_ENABLED=true` and `TASKS_WORKER_PROCESS=true`;
the six-job loop and backfill-facts carry both pins (`DB_POOL_SIZE=1`, `DB_MAX_OVERFLOW=0`) and pregenerate its pool
(`DB_POOL_SIZE=3`); both services "deployed and serving 100 percent of traffic", then `update-traffic --to-latest --clear-tags`; the
health body `status healthy` (database healthy, Redis disabled by design); "Deployed <sha> and verified healthy." The worker's, the
service's and pregenerate's pins and the service's `ENABLE_INSIDER_ACTIVITY=false` sit past the filter's 400-character line cut, so
they are read from `ci.yml` at the seven deployed commits (those lines are unchanged across them), each step succeeding, and the live
`describe-service` and `describe-jobs` below read them back from the running revisions and the pregenerate job's configuration. So from 11:15:45Z production ran #1176's
images: the API service `earningsnerd-backend-00466-8d8` and the worker `earningsnerd-task-worker-00019-97g`, which the live
`describe-service` below confirms from the services themselves at 12:57Z. Main runs after `aa9cf45b` are classified in record 23.

## The first live read-backs

The dispatches ran from `main` under the founder's account with the merged heredocs; each log was downloaded through the
platform's REST API, read through the redacting filter and deleted; the output lines below are the heredocs' own prints (which print
only closed-grammar values, verdicts and names).

**`describe-service`** (ops run 38053869837, job 114218269440, 12:57:25–12:57:54Z, on main `2d738050`): `describe-service: PASS`.
The API service: traffic 100% on `earningsnerd-backend-00466-8d8`, the latest ready revision; `SENTRY_RELEASE` = `0a672ebe…`;
`DB_POOL_SIZE` `'4'`; `DURABLE_TASKS_ENABLED` `'true'`; `TASKS_WORKER_PROCESS` `'false'`; `SEC_RATE_LIMIT_PER_SECOND` `'1'`;
`EDGAR_RATE_LIMIT_PER_SEC` `'1'`; `ENABLE_INSIDER_ACTIVITY` `'false'`; service minScale absent (service-level minimum off), service
maxScale 2; revision minScale 1, maxScale 2, CPU 1, memory 1Gi, CPU allocation request-based (`cpu-throttling=true`) → MATCH, startup
CPU boost true, containerConcurrency 40, timeoutSeconds 600. The pregenerate job: both pins `'1'`, `DB_POOL_SIZE` `'3'`, the rollout
flags not set (Settings defaults). The task worker: traffic 100% on `earningsnerd-task-worker-00019-97g`, the same image digest as the
service; `DURABLE_TASKS_ENABLED` `'true'`; `TASKS_WORKER_PROCESS` `'true'`; `DB_POOL_SIZE` `'3'`; both pins `'1'`; service minScale
absent, service maxScale 1; revision minScale `unset_or_unresolved` (deduced: no annotation, so minimum zero; item 14), maxScale 1, CPU 1, memory 2Gi, CPU
allocation request-based → MATCH, startup CPU boost true, containerConcurrency 1, timeoutSeconds 600; `Worker ingress: all`;
`Worker command/args: matches the committed worker entrypoint (values withheld)`; `Worker invoker IAM check: enforced`;
**`Worker invoker policy: PRIVATE (1 roles/run.invoker member(s); 1 binding(s))`** — the Ops identity may read the policy, so the UNVERIFIED path stayed unexercised and no
founder IAM item arises. No `::error::`, no `::warning::`.

**`describe-jobs`** (ops run 38053962543, job 114218532382, 12:58:56–12:59:25Z, on main `aa9cf45b`): `describe-jobs: PASS`; "All
expected jobs use one release image with the production pool budget, both SEC pins at 1 and taskCount=1." Eight blocks, each on the
release image tagged `0a672eb`, `taskCount` 1, both pins `'1'`, `DB_POOL_SIZE` 3 (pregenerate) or 1 (the seven others);
`command/args`: backfill-facts "matches the committed entrypoint", the seven others "override present (values withheld)".

**`capacity-readout`** over 2026-10-10T10:55:00Z–12:55:00Z (two hours; the window holds #1176's deploy at 11:13–11:15Z and the merge
train's signed-out smoke of the changed router at 11:16Z). The first dispatch (ops run 38054010974, 12:59:43Z) was refused by the workflow's own guard, "a CI run for a push to main is
in flight (in_progress=1)": #1183's CI run (38053943458, created 12:58:37Z) was running; the guard is the designed protection against
reading while a deploy may be re-imaging jobs, and the two describe operations do not carry it. The second dispatch after that run
concluded (13:04:04Z): ops run 38054375439, job 114219713883, 13:05:16–13:05:52Z, on main `aa9cf45b`; receipt artifact 11669819053
(`capacity-readout-38054375439`, kept 14 days; `cloud.json` and `database.jsonl`), read as aggregates. `window.end_age_seconds` 631,
so no freshness flag. Every channel `complete` except the filing-scan executions (`partial`, `page_limit` after 500 retained
resources; both of its executions inside the window were found).

- **Durable tasks.** The `earningsnerd-background` queue's attempts: 17, every one `ok` (none `unavailable`, no other code; at most
  8 in one minute); queue depth 0 at every one of the 120 one-minute samples. The worker served 17 requests, every one `200`, all on
  `earningsnerd-task-worker-00019-97g` (mean latency about 7.1 s; none on the revision before the deploy); worker error-level logs:
  none.
- **The API.** 392 `2xx` (mean latency 69 ms on `00465-gjn` before the deploy, 90 ms on `00466-8d8` after); 15 `401` and 1 `405`,
  all on `00466-8d8`: the `405` and 3 `401` in the minute of the merge train's signed-out smoke of the changed router (11:16–11:17Z;
  the smoke made two `401` requests and one `405`), 10 `401` at 11:30–11:34Z and 2 at 12:42–12:43Z, of an origin the receipt does not
  record; no `5xx`.
- **Cloud SQL.** 3–4 backends on the application database (2 for `cloudsqladmin`) against `max_connections` 25 (3 reserved).
- **Jobs.** filing-scan at 11:00 and 12:00 and notable-filings at 12:30, one task each, all succeeded; the other six jobs did not
  run in the window. Error-level logs for the service and the jobs: 3, all from notable-filings at 12:30:18–12:30:32Z, inside its
  first task attempt (no pool-timeout signature; the receipt keeps no message text, by design). That attempt (12:30:16–12:30:32Z in
  the job ledger) counted two source errors, the counter the job keeps for failed SEC full-text-search requests, and failed, as the
  job is built to, so Cloud Run retried it; the retry succeeded (12:30:46–12:31:01Z; `retriedCount` 1, `succeededCount` 1). Not a
  durable-tasks signal; the Monday readout reads the error channels again.

## The durable-tasks post-deploy checklist (`docs/DEPLOYMENT.md`, "Durable background delivery rollout"): every post-deploy check completed, the first probe unverified

The rollout text's steps and checks in its order, each with the evidence that answers it; the paragraph added to `docs/DEPLOYMENT.md`
in this PR records which checks completed, the unverified probe and what no operation reads back. Every post-deploy check the text
names is completed: its verification list, the invoker-policy item and the three watch items. The first-enablement probe is not: no
read-back can show it, so it stays unverified, under the rule of `lessons/ops-denied-reads-report-unverified.md` that a checklist
item completes only on a positive read.

1. **The authenticated `probe` with an empty payload, enqueued first:** not readable, so **unverified**. No operation records a task's kind or payload,
   and Ops has no probe operation; the step belongs to the first enablement, before the repository variables were set, and they were
   already set at #1176's deploy (11:13:17Z) while the receipt's first sample is 10:56Z. The deliveries in item 9, through the enforced invoker check, answer
   the question the probe asks.
2. **Worker completion and task removal,** by the rollout text's own inference rule: 17 worker requests, every one `200`, all on the
   serving revision `00019-97g` (none on `00018-ckg`, the revision before the deploy); 17 attempts, every one `ok`; queue depth 0 at
   all 120 one-minute samples; requests and `ok` attempts agree minute by minute within one minute. The worker's INFO completion logs
   are not collected by the readout, as the text says.
3. **The repository variables:** #1176's deploy job printed `Variable-driven rollout switches: DURABLE_TASKS_ENABLED=true
   TASKS_WORKER_URL=set` at 11:13:17Z, and, as the independent check read from their logs, the jobs of the four later main pushes
   (#1177, #1182, #1181, #1183) printed the same line (the last at 13:04:00Z). The URL is not printed; the worker step's equality check of the variable against the worker's own URL passed under `set -euo pipefail`.
4. **CI requires the worker, updates it before the API, routes its traffic to the latest revision, and pins queue handoff with
   request-based CPU:** the deploy's step "Update configured private task worker" succeeded (11:14:03–11:14:22Z) before "Deploy Cloud
   Run service" (11:14:22–11:14:52Z), each printing its new revision serving 100 percent of traffic; `describe-service`: `Worker serving
   traffic` 100% on `00019-97g`, `DURABLE_TASKS_ENABLED` `'true'` on the service and the worker, `TASKS_WORKER_PROCESS` `'true'` on the
   worker and `'false'` on the service, `Revision CPU allocation … MATCH` on both. "No tags" is not a printed value: the heredoc stops
   before the worker block on any tag, split or non-latest traffic, and this run printed every block.
5. **The current-head CI run** (the merge's `deploy-backend` job): #1176's run 38047385361, job 114200257270, every step success
   (11:13:12–11:15:45Z); every later main push skipped its deploy steps, so `0a672eb` still serves.
6. **API detailed health** (the deploy's own health step): `healthy` (the database healthy, the SEC EDGAR circuit closed) and "Deployed
   0a672eb and verified healthy." at 11:15:37Z; the merge train read `/health/detailed` `healthy` again at 11:16Z.
7. **Service minimum one and memory 1 GiB:** `Revision minScale: 1`, `Revision memory: 1Gi`.
8. **Worker command and revision:** `Worker command/args: matches the committed worker entrypoint (values withheld)`; `Worker revision:
   earningsnerd-task-worker-00019-97g`, the revision the deploy created, on the digest the deploy pushed for `0a672eb`.
9. **Authenticated task success** (`queue_task_attempts` by response code, `worker_request_count` by response class): 17 `ok` and no
   `unavailable` or other code; 17 `2xx` and no other class. With IAM enforced and one invoker member, every `2xx` passed Cloud Run's
   invoker check; which identity that member is, is not printed.
10. **The worker's invoker-policy item:** complete — `Worker invoker policy: PRIVATE (1 roles/run.invoker member(s); 1 binding(s))`.
11. **Watch: task retries and errors:** attempts equal worker requests, so no retry in the window; `worker_error_logs` complete and
    empty.
12. **Watch: API latency:** 408 requests at a count-weighted mean of 84 ms (for `2xx`, 69 ms on `00465-gjn` before the deploy and 90 ms
    on `00466-8d8` after); from the merged histograms, p95 211–232 ms and p99 602–663 ms; the worst one-minute means 1,045 ms (2
    requests, 11:46Z) and 644 ms (7 requests during the deploy, 11:15Z); 392 `2xx`, 15 `401` and 1 `405` (the `405` and 3 `401` in the
    smoke's minute; 12 `401` later, origin not recorded), no `5xx`.
13. **Watch: SQL connections:** 3–4 backends on the application database (5–6 in all; 6 at 10:56–11:14Z, 12:31Z and 12:52Z) against `max_connections` 25 with 3
    reserved. The one-minute samples missed the worker's pool (3 during the 12:42–12:44Z burst), so its three-connection budget is
    unobserved, not disproved.
14. **The worker's shape** in the rollout text (minimum zero, maximum one, concurrency one, 1 CPU, 2 GiB, request-based CPU, ingress
    `all`, IAM enforced, neither public principal, both SEC pins `1`): each printed as written — `Worker invoker IAM check: enforced`,
    and the heredoc fails closed on either public principal — except the minimum, which is deduced: the service-level annotation is
    absent and the revision value `unset_or_unresolved`, and any revision value of one to four digits would have printed, so the
    minimum is Cloud Run's default of zero.
15. **The independent check** (`durable-tasks-check-01`, launched 13:22:59Z; read-only over the same logs through the redacting filter,
    the receipt and the committed files at `aa9cf45b`): every item the read-backs can show SATISFIED and nothing contradicting the
    docs; open as above: the probe (item 1), the worker's INFO completion logs (item 2) and the minimum, deduced (item 14). The limits it
    named are recorded here: the worker's `DB_MAX_OVERFLOW`, its `TASKS_*` values and its generation flags are not visible through the
    heredoc's filter; no operation reads the queue's settings, the API enablement, the enqueuer, service-account-user and service-agent
    grants, project-level IAM or who the single invoker member is; the window's 17 tasks are of unknown kind and it misses the time
    before 10:55Z, so earlier unavailable attempts or retries are not excluded; the health check is one point in time (no API `5xx`
    since). It found no change to production between the read-backs and its last look (about 13:37Z): every later main push skipped
    its deploy steps and no Ops run rolled back or wrote.

## Ledger event 45

Written 2026-10-10T12:29:06Z after the ledger was read back at the hash recorded after event 44 (`547946296e3be5ad84ac143f75eafd23772d8cf77259ef7fd96635571db0d51b`,
129,259 bytes): type `provider_balance_floor_recorded`; the founder's USD 5 floor (instruction 2026-10-09T21:38:15Z) recorded as a stop
condition beside the reservation rule; the fresh reading USD 21.83 available at 12:10:15Z (`deepseek-balance` run 38050979625, job
114209879737, the chief's own dispatch; USD 24.25 at 21:10:42Z the day before); no reservation, because PR #1181's files match no
paid-run trigger (`copilot-eval.yml`'s paths since PR #1123; `eval-baseline`'s filter); balances, holds and reservations unchanged;
conditional unreserved 21.605243; 0 active reservations. Published as the private ledger's version 46 with its page updated (the floor
and reading pill, the writer pill naming this session from event 45 on, the hash lines) and read back: SHA-256
`38696143971c8155cd20a823e36b69f328186f444bfcfea7f15d80748421c23d`, 133,271 bytes, matching the staged file. No event 46: no paid run
fired (none could).

## Disclosures

1. **No chief defect and no classifier denial this record.** Three process misses were harmless and are recorded as such: the first `capacity-readout`
   dispatch ran into the workflow's in-flight guard (above), one wasted read-only run with no effect; and the chief's local redacting
   filter at first dropped the `Worker invoker IAM check: enforced` line (its keep list did not name it), so the line was read from a
   second filtered download, the keep list was widened, and the independent check, told so, filtered its own copy again. No value was
   lost or misread. And four of #1172's eighteen ready heads were superseded within minutes, before an `@codex review` request was
   posted (above); each was covered by the next reviewed head (`61ed80e` for `577edeb` and `2dc7a3b`, `8a3fd35` for `10df20f`,
   `8fb9802` for `d0ce70a`), and the merged head had no findings.
   **A wording correction** (the same class as record 21's correction of record 20): `b32003f8`'s squash message says Codex raised
   "P1 four times and P2 nine times across the heads"; the count is four P1 and eleven P2 (above). The PR body's own figure,
   "P1 four times and P2 eight times on the gate itself", is right. Main's history is left as merged.
2. **The founder's note of about 12:47Z** ("continue. note that im fine with you spending more if you need to") is read by the chief
   as permission to spend more compute and agents on verification; it names no number and does not amend the DeepSeek ledger's shared
   USD 25 authority or the USD 5 floor, so the ledger's recorded authority is unchanged. If the founder means the provider authority,
   that is a ledger event the founder's words would set (founder action 1).
3. **Side effects of this record:** read-only GitHub requests (PR, run, job and check-run reads through the GitHub MCP server; eleven job
   logs downloaded through the platform's REST API with the preconfigured CLI — the seven deploys and the four ops runs, some more than
   once (the describe-service log a second time after the filter fix) — each redacted locally and the raw copy deleted; the capacity receipt artifact downloaded into the scratchpad); four read-only
   `ops.yml` dispatches (one refused by its own guard) and one `deepseek-balance` dispatch (free; the balance endpoint only); the
   private ledger read back twice and published once; PR #1172's body edited, Codex's last finding answered and its thread resolved, the
   PR squash-merged; PR #1181 opened as a draft, its body edited, marked ready, Codex's finding answered, squash-merged; one comment on
   each after its merge; two cross-session messages to the merge
   train (session `018w7VWiSMYqGddE2thede6V`: #1172's merge before #1176, and #1181's merge); the records branch recreated from main
   after the merge deleted it; agent and workflow launches as closure 173 registers; scratchpad only otherwise.
4. **The delta reviewer's disclosures:** its REPORT.md writes were refused by the harness (reports delivered as hand-back messages and
   saved by the chief); a first differential attempt imported the application's config module, which echoed ambient environment values
   into the agent's own tool output and nothing else (the committed harness clears the environment and imports nothing); one `gh api`
   poll loop for a run's completion.
5. **The `describe-service` output lines** include the release image's Artifact Registry path and digest and the revision names; the
   project id in that path is already public in the repository, and no host, URL, principal or command value was printed, as the
   heredoc's privacy gate pins.
6. **The session's worker restarted, and the founder changed this session's model.** Between about 13:06Z and 13:19Z the
   session's worker process restarted; the background waits had completed and the scratchpad and working tree were intact, so
   nothing was lost or repeated. At about 13:19Z the founder changed the model this session runs on (no model is named in these
   records, record 15's rule) and wrote "Continue"; the chief is the same session and its registration (closure 172) stands.
7. **The independent check's disclosures:** 33 read-only GitHub REST requests and no write (Ops and CI runs, jobs and artifacts; ten
   job-log downloads, each filtered and the raw copy deleted, the describe-service log twice; one artifact download, its zip digest
   matching the artifact's); local read-only git; no gcloud, dispatch, install or other network access. One rule deviation: one
   `git ls-tree --name-only` of `ops/capacity/` on `origin/main` without the exclusion pathspecs (the command does not accept them),
   which listed that directory's two files; the path lies outside both excluded directories, so nothing excluded could be listed, and
   a count-only search of its scratch directory for both excluded prefixes found none.

## Plan

1. **This record's PR** (`record-22-reviewer-01`, closure 172; records-only rule: one reviewer context bound to the final head, with
   same-context delta checks; Codex; explicit squash title and message; then the seventeenth deploy-skip proof).
2. **Monday 2026-10-12, 08:20Z:** the armed check-in (`trig_01GS8mRCbyazWppZuSheNWkd`) dispatches the 06:00–08:00Z `capacity-readout`
   and compares it with record 10's Monday, record 20's baseline and this record's 10:55–12:55Z window (`monday-readout-20261012-01`).
3. **Follow-ups from the read-back review** (`readback-followups-pr-01`, closure 173; a workflow file, so a code PR's review), as an
   engineering line in `tasks/todo.md`: the describe-service shell read's inherited
   stderr, the receipt's address-redaction of `error_detail.message`, the logs-probe step's raw stderr echo, and the extraction of
   both heredoc bodies to committed modules under `ops/` (the stopping point the PR named); and, from this PR's review, a test pinning the
   classifier's `error (gcloud not executable)` class.
4. **Then the checkpoint's Next queue:** the COO's G3 first-customer-part review and the G4 gate; B32's qualifying retained window; R1
   waits on the founder's custody step-A answer.

## Registration (closure 173)

Closure 173 (582 → 628; recorded 13:44:59Z) registers as actual: `record-21-reviewer-02`'s launch-time identity
(`launched-2026-10-10T0408Z`); the design workflow `wf_b0cbcf69-f9d` and its 28 agent contexts (fifteen, then thirteen re-launched
after the usage limit); the implementation context (`launched-2026-10-10T0928Z`); the review workflow `wf_e5ff680a-2c4` and its ten
agent contexts under the `workflow_lens_labels` convention; the delta reviewer (`launched-2026-10-10T1214Z`); and the
`durable-tasks-check-01` context (`launched-2026-10-10T1322Z`). It resolves closure 172's `record-21-reviewer-01` and `record-21-reviewer-02` and
closure 171's `ops-readback-pr-01` and `durable-tasks-check-01` to those identities, annotates `record-22-reviewer-01` as covering
this record's reviewer (resolved in a later closure, the chain rule), re-annotates `monday-readout-20261012-01` (unchanged), and
pre-registers `record-23-reviewer-01` and `readback-followups-pr-01` (every context of the follow-ups PR, plan item 3) before any launch.
No context gains source, reconciliation or judging eligibility; every earlier identity and adverse history is retained.

## Spend

No paid run; one ledger event (45, floor only; no reservation). Recorded use against the authority 1.513044 (1,153 calls); retained
holds 1.881713; headroom 21.605243; cumulative 3,212 calls / USD 5.297293; 0 active reservations; latest balance reading USD 21.83 at
12:10:15Z, above the floor.

## Founder actions this record needs

1. **The spending note** (new): if "spending more" was meant for the DeepSeek provider authority as well, say so in your own words and
   the chief writes the ledger event; otherwise nothing changes (disclosure 2).
2. **Squash default** (optional, recommended; carried from record 20): Settings → General → Pull Requests → "Allow squash merging"
   → "Default commit message": "Pull request title and description".
3. **Custody step A** (optional, recommended; carried from record 20): send the prepared relay (`DECISIONS-20.md`'s appendix) once to
   the custody side; if you agree, also tell the chief, in your own words, "If the answer is outcome B, I adopt record 16's form (b)
   for R1".
