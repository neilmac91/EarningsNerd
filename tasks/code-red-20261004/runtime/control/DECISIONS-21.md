# Decision record 21 — chief succession: the predecessor session blocked by a Claude Code safety check from about 21:40Z and the successor appointed by the founder's handover brief at 22:38Z; PR #1167 (record 20) merged, fourteenth deploy-skip proof; #1169's deploy read back from its log (every process carries both SEC pins, the insider switch is off, the health check passed) and twelve later main runs classified, four of them deploys by other writers (#1166, #1123, #1135, #1140), each read back from its log; the founder's USD 5 balance floor recorded as a stop condition; a duplicate second successor session holds every write; the Monday check-in re-armed; disclosures (chief defects 9, 10, 11 and 12, classifier denials 11 and 12, a record-20 wording correction, the account's usage-limit interruption); closure 172 (chief, 2026-10-09)

Recorded 2026-10-09T23:02Z, amended 2026-10-09T23:12Z (the relayed confirmation), 2026-10-10T04:05Z (the usage-limit
interruption; the fresh reviewer context), 04:09Z (chief defect 10), 04:30Z (after the record-21 review: the later main runs
read back, including two deploys by other writers), 05:03Z (chief defect 11), 05:11Z (the records gate extended to every verification step; the title; the
interval of chief defect 11 corrected), 05:21Z (the wrapper's `backend` scope carries the full backend gate; chief
defect 12), 05:50Z (`auto` also reads the commits since main), 06:03Z (`auto` refuses a self-comparison with the local `main`) and 06:19Z (untracked files read regardless of
configuration), by the successor chief (`https://claude.ai/code/session_011jZyZqfNWZRqiFNWfTc3u8`).
Context: record 20 merged to main as `da8dc998` (PR #1167, 2026-10-09T22:14:52Z); this is the first PR from the successor's
branch `claude/stoic-wright-6jeujo`, started at `a572876c`. Records, two lessons, the lessons index, one records-tree tool
(`tools/records-gate.sh`) and its test under `backend/tests/unit/`: no application code, workflow, migration, cloud, IAM or
production change in this PR (nothing under `backend/` outside `tests/`, so the merge deploys nothing); no provider call; no reservation; nothing opened under `tasks/readiness-2026-09-21/acceptance/` or
`tasks/review-evidence/`. (The successor's branch started at `a572876c`, main's tip at 22:38Z; main's later merges, by other
writers, are classified below up to this record's last amendment.)

## The predecessor's block and the succession

The predecessor chief (`https://claude.ai/code/session_01GWYV7WXWstgVGQG43YcSM8`, records 01–20) lost the ability to act on
2026-10-09, as its own closing report (22:36:50Z) and its session's event log, read by the successor through the platform's
session API, record:

- **From about 21:40Z, every shell command was refused** by a Claude Code safety check separate from the auto-mode classifier.
  Its message said it was "blocking it for safety — a safety check separate from auto mode blocked this request because of earlier
  conversation content — it isn't about the action itself", and that it would keep refusing until the conversation ended. The first
  refusal was an edit adding the founder's USD 5 floor to the ledger-event script; after it even `date` was refused. So no commit,
  push, test, hash or ledger publish was possible from that session.
- **From about 22:05Z, every message to its review agents was refused**, so `record-20-reviewer-01` could not re-check PR #1167's
  final head `084c9d48` (GitHub's update-branch merge of main into `86334d59`, bringing in #1169; it changed no runtime-record
  file). The PR merged on the reviewer's verdict bound to `86334d59`, disclosed in the PR's description.
- **Two container restarts stopped the read-back design workflow** (`wf_11203ef3-3cf`, under closure 171's label
  `ops-readback-pr-01`). The second restart, at 22:31:34Z, stopped its final step (the revision of the draft patch); the attempt
  to resume it at 22:31:50Z was refused by the same check. The first restart's exact time is not recovered here (the session API
  pages one hundred raw events at a time, most of them token stream events); the predecessor reported both. Its draft patch and two
  adversarial reviews survive only in the predecessor's scratchpad and workflow journal, which the successor cannot read, so nothing
  from it enters the repository and the design is redone (Plan, below).
- **What kept working:** file reads, GitHub reads and writes (which is how PR #1167 was merged at 22:14:52Z and its deploy-skip
  proof read), and messages and check-ins to other sessions.
- **Handover:** at 22:36:50Z the predecessor wrote the handover brief for a fresh session; the founder created this session with it
  at 22:38:39Z (the founder's words in the brief: "Work autonomously and fast; ask me only for decisions that are mine. Use
  workflows (multi-agent orchestration) for design and review."). The brief restates the standing rules (exclusions, single writer,
  no production change by the chief, the two conditions before any paid trigger, the review rules, the holds, the public-repository
  rule) and the state at handover; the successor verified each state item it could reach (below) before writing anything.

### The successor's takeover (22:38Z to 22:53Z)

1. **Records read on main** as the brief lists them: the checkpoint (header, decisions 1–70, founder items, Next), records 20 and
   the control files, closure 171, the ledger access statement, the spend policy statement, the lessons index, and the
   runtime-records gate (`backend/tests/unit/test_code_red_runtime_records.py`).
2. **The Monday check-in re-armed.** The predecessor's one-shot trigger `trig_01AaU4ABbNNMQNoPZGPfQ6Dt` (2026-10-12T08:20Z into the
   dead session) was deleted at 22:42Z and `trig_01GS8mRCbyazWppZuSheNWkd` armed at 22:42:24Z for the same time into this session,
   with the same task (the 06:00–08:00Z `capacity-readout`, compared with record 10's Monday and record 20's baseline; analysis
   contexts under `monday-readout-20261012-01`).
3. **The private ledger read back:** `spend-and-reservation.json`, 129,259 bytes, SHA-256 `547946296e3be5ad84ac143f75eafd23772d8cf77259ef7fd96635571db0d51b`,
   equal to the hash after event 44 in `LEDGER-ACCESS.md`; 44 events, the last event 44; no active reservation; conditional
   unreserved 21.605243. No event written in this record.
4. **APPOINTMENTS updated:** the chief's identity is this session; a `succession` field names the predecessor, the reason and the
   second session (below); classifier denials 11 and 12 and chief defect 9 added.
5. **Closure 172** (574 → 580 at 22:53Z; 582 after the in-place amendments) registers this session and the second successor session, resolves `record-20-reviewer-01`, registers
   the predecessor's design workflow at workflow level and pre-registers `record-21-reviewer-01` and `record-22-reviewer-01`; it is
   committed and pushed before any launch (Registration, below).
6. **Two classifier denials in this session** (about 22:41Z, both "Irreversible Local Destruction", neither retried): denial 11, a
   checkout of main followed by a hard reset to `origin/main` in a clean checkout whose branch already stood at that commit; denial
   12, a compound read-only command (a status count, three directory listings and seven byte counts). The dedicated file tools were
   used instead; the work continued on the designated branch at the same commit.
7. **An exclusion-safe agent copy** of main (`a572876c`) was made in the session's scratchpad with `git archive` excluding the two
   directories, checked absent; every agent of the read-back PR reads that copy, never the checkout.

### A duplicate second successor session; the single-writer agreement

The founder also created a second successor session with the same brief at 22:44:47Z
(`https://claude.ai/code/session_0172iDJgYdJweV79iRjtmgc2`, branch `claude/dazzling-cerf-12u9eu`). It found this session through
the trigger list and proposed by cross-session message (about 22:50Z) that the earlier session, which already held the Monday
trigger, stay the single writer while it held every write until the founder decides; it reported reads only (the handover records
on main, the gate test, `ops.yml`, session metadata, the trigger list and one page of this session's event log), nothing opened under
the excluded directories, no push, PR, ledger write, closure, trigger or agent. This session accepted at 22:52Z and listed its own
writes to that point (the two trigger operations; nothing else). **Single writer: this session.** The second session then relayed
(22:59Z and 23:00Z) that the founder confirmed in that session at about 23:00Z, in these words: "the earlier session is the chief";
this session has no direct word from the founder yet and acts on the relayed confirmation (founder action 1, below, asks only for
an overrule if the founder wants one). The second session's complete activity, as it disclosed it: repository reads on main only
(the handover records, the lessons index, the records gate test, `ops.yml`, `ci.yml`, `ops/capacity/readout.py` and
`snapshot.sql`, the capacity and workflow tests, `docs/DEPLOYMENT.md` and `docs/OPERATIONS.md`; nothing under the two excluded
directories opened, listed or searched); two read-backs of the private ledger (the page and the document, the same hash as above;
no write); session reads through the platform's tools (this session three times, itself, the predecessor and the two backlog
sessions; the trigger list once; two pages of this session's event log and seven of the predecessor's); GitHub reads (the
`deepseek-balance` run list, the open-PR list; no write); one self check-in Routine for 23:44Z into its own session, created and
then deleted (`trig_01XhF6Jaxm4UwWCqV8tV7RkG`); three cross-session messages to this session; no agent, workflow, push, PR, commit
or closure. It stands down to read-only for good. It also passed one observation, taken up in the Plan: PR #1123 (then open; merged at 23:18:46Z) changes which paths fire
`copilot-eval`, so the chief re-checks whether a `backend/tests`-only PR still fires the paid run before event 45. The second session is registered in closure 172 as a read-only context (amended in place before merge with this list).

## PR #1167 review record closed (decision record 20)

`record-20-reviewer-01` (closure 171; launched 19:58Z) kept one context for five checks: `37cf582c` **no blocker** (3 should-fixes,
8 nits, applied in `5b20a77a`); `5b20a77a` **no blocker** (1 should-fix, 3 nits, applied in `43cf410b`); `43cf410b` **no blocker**
(1 optional nit, applied in the description); `06397c08` **no blocker** (1 should-fix, "cannot" overstated, and 2 nits; the
should-fix and 1 nit applied in `86334d59` and the description, 1 nit declined: the comment footer the session requires); `86334d59`
**no blocker, bound to `86334d59`** (3 nits: 2 applied in the description, 1 carried here and applied below). The final head
`084c9d48` (GitHub's update-branch merge of main; the PR's diff unchanged at 5 files, +888/−19) was **not re-bound** (the block
above). Codex: one P2 on `43cf410b` (the founder's instruction, not record 18's remit line, governs the squash default), answered
and resolved; no major issues on `06397c08`, `86334d59` or `084c9d48`. `review-gate` and the five other required checks passed on
`084c9d48`; earlier heads' `migrations-postgres` had failed before any step ran under Docker Hub's anonymous pull limit, which #1169
fixed on main. No paid run (tasks-only). Squash-merged `da8dc998` at 22:14:52Z with an explicit title and message. Main CI run
37998159560 green; `deploy-backend` job 114051857861 (22:23:02–22:23:09Z) reported the switches `DURABLE_TASKS_ENABLED=true
TASKS_WORKER_URL=set`, printed "No deployable backend changes - skipping deploy." and skipped every deploy step, 6 to 17
(**fourteenth deploy-skip proof**).

## Production after record 20: #1169's deploy read back from its log; twelve later main runs classified (four deploys by other writers read back)

**#1169 (`86ac7878`, CI images through `mirror.gcr.io`) deployed production** (main run 37997043510; `deploy-backend` job
114047761921, 22:09:50–22:12:21Z), shipping #1144 (the stage decomposition of the summary pipeline) and everything merged since
#1148. The successor downloaded the job's log into its scratchpad, read it through a redacting filter (every `run.app` host and signed
query replaced) and deleted the raw copy. Read from the echoed commands and their results:

- Switches `DURABLE_TASKS_ENABLED=true TASKS_WORKER_URL=set`; `apply_migrations: applied=0 skipped=41`.
- **Task worker** `earningsnerd-task-worker-00008-74z`: command `uvicorn task_worker_main:app` (port 8080, proxy headers), 1 CPU,
  2 GiB, CPU throttling with boost, minimum 0 and maximum 1 instance, concurrency 1, timeout 600 s; env includes
  `SEC_RATE_LIMIT_PER_SECOND=1`, `EDGAR_RATE_LIMIT_PER_SEC=1`, `DURABLE_TASKS_ENABLED=true`, `TASKS_WORKER_PROCESS=true`,
  `DB_POOL_SIZE=3`, `DB_MAX_OVERFLOW=0`; traffic 100% LATEST, tags cleared.
- **API service** `earningsnerd-backend-00455-w65`: 1 CPU, 1 GiB, CPU throttling with boost, minimum 1 and maximum 2 instances,
  concurrency 40, timeout 600 s; env includes `SEC_RATE_LIMIT_PER_SECOND=1`, `EDGAR_RATE_LIMIT_PER_SEC=1`,
  `ENABLE_INSIDER_ACTIVITY=false`, `DURABLE_TASKS_ENABLED=true`, `TASKS_WORKER_PROCESS=false`, `DB_POOL_SIZE=4`; traffic 100%
  LATEST, tags cleared.
- **Pregenerate**, the **six-job loop** (filing-scan, filing-digest, earnings-calendar-refresh, earnings-day-alerts, notable-filings,
  retention-purge) and **backfill-facts** each updated with `SEC_RATE_LIMIT_PER_SECOND=1,EDGAR_RATE_LIMIT_PER_SEC=1` (pregenerate
  with `DB_POOL_SIZE=3`, the others `DB_POOL_SIZE=1`, all `DB_MAX_OVERFLOW=0`; backfill-facts with its scheduled entrypoint); none
  reported missing.
- Health at 22:12:17Z: `status healthy`, database latency 7.98 ms, Redis disabled, SEC circuit closed; "Deployed 86ac787 and
  verified healthy."

Like record 19's reading, this rests on the deploy log's echoed commands and gcloud's result lines; the worker's live configuration
is still read back only by the read-back PR's `describe-service`.

**Later main runs**, each from its `deploy-backend` job's step list (steps 6 to 17 are the deploy steps):

| Merge | PR | Main CI run | `deploy-backend` job | Outcome |
|---|---|---|---|---|
| `8eed19c4` | #1153 (risk headings) | 37997224662 | 114048950234 | every deploy step skipped (22:13:44–22:13:49Z) |
| `07bfaa63` | #1156 (size-budget gate) | 37997231285 | 114048947096 | every deploy step skipped (22:13:36–22:13:40Z) |
| `da8dc998` | #1167 (record 20) | 37998159560 | 114051857861 | every deploy step skipped (fourteenth proof) |
| `97eea4ca` | #1143 (filing reader) | 37998425708 | 114052833022 | every deploy step skipped (22:26:12–22:26:16Z) |
| `f8ec0491` | #1142 (a11y) | 37999408483 | 114055797517 | every deploy step skipped (22:36:08–22:36:15Z) |
| `a572876c` | #1166 (design follow-ups A–E) | 38000074176 | 114057357644 | **deployed** (22:41:34–22:44:23Z; every step success; read back below) |
| `9e80b31d` | #1170 (triage replay tool) | 38001224982 | 114061786362 | every deploy step skipped (22:57:05–22:57:11Z) |
| `153ee0e6` | #1134 (Lane B gate) | 38001249490 | 114061568096 | every deploy step skipped (22:56:18–22:56:24Z) |
| `a3e11995` | #1171 (risk headings) | 38003499338 | 114070361468 | every deploy step skipped (23:28:34–23:28:41Z) |
| `8c304779` | #1123 (copilot-eval paths) | 38003784423 | 114071113401 | **deployed** (23:31:24–23:33:50Z, during the interruption; every step success; read back below) |
| `b0cf98cb` | #1135 (parallel-safe suite) | 38023102869 | 114128850894 | **deployed** (04:14:05–04:16:31Z; every step success; read back below) |
| `b814242b` | #1140 (saved-summaries router) | 38023630189 | 114130592902 | **deployed** (04:23:56–04:26:20Z; every step success; read back below) |

**#1166 (`a572876c`, design critique follow-ups A–E; merged 22:35:48Z by another writer) deployed production** while the successor
was taking over (`deploy-backend` job 114057357644, 22:41:34–22:44:23Z), read from its log the same way: switches
`DURABLE_TASKS_ENABLED=true TASKS_WORKER_URL=set`; `apply_migrations: applied=0 skipped=41`; the task worker
`earningsnerd-task-worker-00009-t8x` and the API service `earningsnerd-backend-00456-9xj` each deployed and routed 100% LATEST with
tags cleared; every echoed `--update-env-vars` (the worker, the service, pregenerate, the six-job loop, backfill-facts) carries
`SEC_RATE_LIMIT_PER_SECOND=1` and `EDGAR_RATE_LIMIT_PER_SEC=1`, the service's also `ENABLE_INSIDER_ACTIVITY=false`; no job reported
missing; health at 22:44:18Z `status healthy` (database latency 8.03 ms); "Deployed a572876 and verified healthy." #1166's deploy
left the API service on `00456-9xj` and the worker on `00009-t8x`; two later deploys by other writers followed.

**#1123 (`8c304779`, the `copilot-eval` trigger paths; merged 23:18:46Z by another writer) deployed production during the
interruption** (`deploy-backend` job 114071113401, 23:31:24–23:33:50Z), read from its log the same way: switches `true` / `set`;
`apply_migrations: applied=0 skipped=41`; worker `earningsnerd-task-worker-00010-nz8` and service `earningsnerd-backend-00457-jnc`
each at 100% LATEST with tags cleared; every echoed `--update-env-vars` carries both SEC pins, the service's also
`ENABLE_INSIDER_ACTIVITY=false`; no job reported missing; health at 23:33:46Z `status healthy` (database latency 6.75 ms); "Deployed
8c30477 and verified healthy."

**#1135 (`b0cf98cb`, the parallel-safe backend suite; merged 04:09:58Z by another writer) deployed production** (`deploy-backend`
job 114128850894, 04:14:05–04:16:31Z), read the same way: switches `true` / `set`; `apply_migrations: applied=0 skipped=41`; worker
`earningsnerd-task-worker-00011-m2f` and service `earningsnerd-backend-00458-gls` each at 100% LATEST with tags cleared; every
echoed `--update-env-vars` carries both SEC pins, the service's also `ENABLE_INSIDER_ACTIVITY=false`; no job reported missing;
health at 04:16:27Z `status healthy` (database latency 6.99 ms); "Deployed b0cf98c and verified healthy."

**#1140 (`b814242b`, the saved-summaries router refactor; merged 04:18:53Z by another writer) deployed production**
(`deploy-backend` job 114130592902, 04:23:56–04:26:20Z), read the same way: switches `true` / `set`; `apply_migrations: applied=0
skipped=41`; worker `earningsnerd-task-worker-00012-r2r` and service `earningsnerd-backend-00459-wf9` each at 100% LATEST with
tags cleared; every echoed `--update-env-vars` carries both SEC pins, the service's also `ENABLE_INSIDER_ACTIVITY=false`; no job
reported missing; health at 04:26:15Z `status healthy` (database latency 7.84 ms); "Deployed b814242 and verified healthy." So as
of 04:26Z, this record's last classification, production runs #1140's images: the API service `00459-wf9` and the worker
`00012-r2r`, every pin in place. Other writers keep merging the backlog; main runs after `b814242b` are classified in record 22.

## The founder's USD 5 floor (instruction 2026-10-09T21:38:15Z)

The founder's instruction, given to the predecessor: **"proceed. you can keep going until the balance reaches 5$"**. The chief reads
it as a **stop condition on the provider wallet**, added beside the standing reservation rule, not as an authorization: the shared
USD 25 authority (ledger event 2), the dearest-measured-run reservation rule (record 09) and `provider_wallet_is_authorization:
false` stand unchanged. Operating rule from this record: **before any paid trigger, both must hold** — (1) a reservation is written
to the private ledger first (`copilot-eval` USD 0.060000 per run; `eval-baseline` USD 0.730000 per push), and (2) a fresh reading from
the free `deepseek-balance` workflow, taken for that trigger, shows the DeepSeek balance above USD 5.00. A reading at or below USD
5.00 holds every paid trigger until the founder says otherwise. Latest reading: **USD 24.25 at 21:10:42Z** (run 37991815539, job
114027646900, read by the predecessor; the successor confirmed the figure from the job's public log). The floor is written into the
ledger by event 45 together with the fresh reading taken for the read-back PR's leaving draft; a reservation joins it only if a
paid trigger can still fire (Plan, below); the predecessor's attempt to add it to its ledger script was the first refused command.

## Disclosures

1. **Chief defect 9 (the predecessor's; disclosed by the successor):** while checking the final head `084c9d48` through GitHub's file
   listing, the predecessor's listing printed one path under `tasks/review-evidence/` (a file main's merge brought into the PR;
   path and line counts only). Nothing there was opened, quoted or copied, and the line informed nothing beyond the fact that no
   runtime-record file changed. Added to `APPOINTMENTS.json`'s `chief_defects`; the rule stands: listings of a merge commit are
   filtered to the records tree before they are printed.
2. **A record-20 wording correction (the carried nit):** decision 2 of `DECISIONS-20.md` says of the refused squash-default attempt
   that "the setting is as it was"; the accurate statement is **"the attempt changed nothing"**: nothing was sent, so the setting was
   never read or written by the chief, and whether the founder has since changed it is unknown here. Record 20 stays as merged;
   this record carries the correction.
3. **Classifier denials 11 and 12** (above; `APPOINTMENTS.json`).
4. **The predecessor's refusals were not classifier denials.** They came from a safety check separate from the auto-mode
   classifier, reacting to the conversation rather than to the actions; by record 20's convention such refusals are disclosed in
   the decision records (here) and not added to `classifier_denials`.
5. **The duplicate launch** (above): two successor sessions created six minutes apart with the same brief; both had written nothing
   to the repository or the ledger at the time of the agreement; the second holds every write and has stood down, the founder's
   confirmation reaching this session as relayed by the second.
6. **The account's usage limit interrupted the successor's first launches.** At about 23:25Z the Claude account's five-hour usage
   limit (reset 00:50Z) ended the first `record-21-reviewer-01` context (launched 23:05Z on `65dc598a`; it had built its archive,
   run the gate with 9 passed and begun the hash and closure checks; no verdict, nothing bound) and 13 of the 15 agents of the
   read-back design workflow `wf_b0cbcf69-f9d` (two readers completed; every design, judge, refuter and the synthesis failed
   before running); the session's worker process restarted twice. Work resumed at 04:04Z on 2026-10-10 on the founder's "Try
   again": the design workflow resumed from its journal (the two completed readers replay from cache; the rest run live) and a
   fresh reviewer context `record-21-reviewer-02` was pre-registered (closure 172 amended in place before merge) and launched.
   Nothing in the repository or the ledger was changed by this session during the interruption; other writers kept merging to
   main, and one of their merges (#1123) redeployed production at 23:31–23:33Z (read back below); PR #1172's CI completed green
   on `72f01ed` at 23:27Z.
7. **Chief defect 10 (the successor's):** at 04:05Z on 2026-10-10 a commit chain ran the runtime-records gate through a pipe
   (`pytest … | tail -1`) without `pipefail`, so the gate's failure did not stop the chain and head `7d65c89` was committed and
   pushed to this PR with the gate red. The failure: closure 172 resolved `record-21-reviewer-01` inside the closure that registered
   it, which the chain rule forbids (a label is resolved only in a later closure). Noticed from the printed "1 failed" in the same
   output; corrected in `351319f` one minute later (committed 04:07:02Z, pushed by 04:07:08Z; the label annotated as exercised,
   its launch-time identity registered, the formal resolution left to a later closure; 9 passed). No merge and no production effect; PR #1172's CI on `7d65c89` is expected
   red on `backend-tests` for the same reason. Rule: a verification command in a chain is never piped away; its exit status gates
   the commit. Added to `APPOINTMENTS.json`'s `chief_defects`; lesson `lessons/ops-a-piped-gate-does-not-gate.md`. **Machine gate**
   (rule 12; Codex's P1 on this PR, extended after chief defect 11 by Codex's P1 on `61ed80e` and after chief defect 12 by Codex's
   P1 on `8a3fd35`): `tools/records-gate.sh` is the supported way to verify a records commit. In its `records` scope it runs the
   runtime-records gate, `ruff check` and `ruff format --check` on the backend test files the records tree owns; in its `backend`
   scope, chosen automatically when the working tree or the commits since main change anything under `backend/`
   (failing closed when no base exists to compare with), it adds the repository's
   full backend gate (`ruff check .`, `bandit -r app -ll`, `python -m pytest`). Every step runs unpiped, each exit status is captured
   explicitly (`|| status=$?`, never `set -e`, which the tool shell suppresses), one line per step is printed, and the exit status is
   0 only when every step passed. `backend/tests/unit/test_records_gate_wrapper.py` pins that form and proves it by mutation in
   temporary repositories: a failing pytest step, a failing non-pytest step (an unformatted file) and a failing full-gate step (a
   planted Bandit finding) each fail the wrapper; clean trees pass it in both scopes; `auto` picks `backend` in a repository with a
   change under `backend/` in the working tree or in the commits since main, `records` otherwise, and fails closed without a base or
   when the only base is the local `main` that HEAD itself sits on (Codex's P1 on `8f64ee6`: the first `auto` read the working tree
   only, so a clean tree after a commit chose `records`; Codex's P2 on `f97a02f`: a self-comparison with the local `main` would have
   hidden a change committed on it; Codex's P2 on `4f55e93`: the working tree is read with `--untracked-files=all`, so a
   `status.showUntrackedFiles=no` configuration cannot hide a new file). The repository still cannot see the chief's shell, so the gate is the wrapper plus
   CI's own run of the records gate, which is what caught `7d65c89`.
8. **The successor's side effects to this record:** read-only GitHub requests (runs, jobs, one PR, the open PR list, the balance
   job's log); two pages of the predecessor's session event log through the platform's session API (its own transcript events,
   summarised through a redacting script; one path fragment of the predecessor's scratchpad seen in its tool calls, written nowhere);
   five signed job-log downloads (the #1169, #1166, #1123, #1135 and #1140 deploy logs) into the scratchpad, each read through
   the redacting filter and the raw copies deleted; the private ledger read back once; the two
   trigger operations; the agent copy and a virtual environment with the pinned backend toolchain in the scratchpad; four cross-session
   messages (three received, one sent). No SEC, production, `run.app` or Google Cloud request; no repository write before this PR.

9. **Chief defect 11 (the successor's):** at 05:00Z on 2026-10-10 a commit chain for this PR ran `ruff format --check` on the new
   wrapper test, the check failed (the file would be reformatted), and the chain committed and pushed head `577edeb` anyway: the
   chain's `set -euo pipefail` did not stop it. A probe in the same tool shell, `(set -e; false; echo survived)`, prints, so errexit is
   suppressed there (the shell's rule for commands run inside a conditional context); `set -e` at the top of a chain gates nothing in
   this session's shell. The records gate (through `tools/records-gate.sh`, a separate script in which `set -e` does work), the
   wrapper test and `ruff check` all passed on that head, and CI runs `ruff check` only, so nothing red reached CI; the file was
   formatted in `2dc7a3b` under a minute later (committed 05:00:50Z, pushed by 05:00:56Z). The same rule as chief defect 10, failed by a second mechanism: in a chain that commits
   or pushes, every verification step carries its own explicit exit (`cmd || exit 1`); `set -e` is not that check here. The lesson
   gains the paragraph; `APPOINTMENTS.json`'s `chief_defects` has the entry. **Machine gate** (rule 12; Codex's P1 on `61ed80e`):
   `tools/records-gate.sh` now runs every verification step of a records commit (the runtime-records gate, `ruff check` and
   `ruff format --check` on the two backend test files the records tree owns), each with its exit status captured explicitly, and
   exits 0 only when every step passed; its test proves by mutation that a failing non-pytest step (an unformatted file) fails the
   gate as a failing pytest step does (disclosure 7). Codex's P1 on `8a3fd35`: the wrapper's `backend` scope, chosen automatically
   when the working tree or the commits since main change `backend/`, adds the repository's full backend gate (`ruff check .`, `bandit -r app -ll`,
   `python -m pytest`) as three more steps, and the test proves a planted Bandit finding fails it (disclosure 10).

10. **Chief defect 12 (the successor's):** the pushes of this PR that changed `backend/tests/` (`0fc248f`, `577edeb`, `2dc7a3b`,
    `10df20f`) were preceded locally by `ruff check` and `ruff format --check` on the changed test file and by the two tests
    themselves, not by the full backend gate the repository requires before every push that changes `backend/` (`ruff check . &&
    bandit -r app -ll && python -m pytest`, AGENTS.md). CI's backend-tests job ran the full gate green on each of those heads, so
    nothing red reached CI or main; the gap is procedural. Found by Codex (P1 on `8a3fd35`). From this head the wrapper's `backend`
    scope runs the full gate automatically whenever the working tree or the commits since main change anything under `backend/` (its test proves a planted
    Bandit finding fails it), and this head was pushed only after that scope passed on it under a Python 3.11 environment matching CI's
    (`RECORDS_GATE_PYTHON`): a first run under this container's default Python 3.13 failed 11 tests in two files this PR does not
    touch (`test_copilot_prose_quotations.py`, whose unassigned-character cases use U+2FFC and U+31EF, assigned in the Unicode 15.1
    data Python 3.13 carries; and one `test_capacity_readout.py` case, a JSON error-detail difference), identically on main's
    `a572876c` with the same interpreter, so those failures are environmental and pre-existing, not this PR's. The full gate is run
    with CI's interpreter version from now on (the lesson says so). Rule: a records commit that changes
    anything under `backend/` runs the full backend gate before the push, through the wrapper. `APPOINTMENTS.json`'s
    `chief_defects` has the entry.

## Plan

1. **This record's PR** (`record-21-reviewer-02`, closure 172, after the first context ended at the usage limit; records-only rule:
   one reviewer context bound to the final head, with same-context delta checks; Codex; explicit squash title and message; then
   the deploy-skip proof).
2. **The read-back PR** (`ops-readback-pr-01`; redone by the successor on a second branch so it runs beside this record): a read-only
   design workflow (readers of `ops.yml`, `ops/capacity/readout.py` and its tests, `ci.yml`'s deploy steps and the
   `docs/DEPLOYMENT.md` checklist; independent designs; judges; refuters) fixes the design, then the implementation, then the lean
   three-lens review with refuters and one delta reviewer, all in draft. Scope as record 20's Plan, sharpened by the founder's brief:
   `describe-service` also reports the API service's minimum and maximum instances, CPU, memory and CPU allocation, and the task
   worker's revision, traffic, command, sizing, ingress, allow-listed env values (both SEC pins) and whether its invoker policy
   admits the public, failing closed on a public invoker, on split or tagged worker traffic, or on a pin other than 1, and reporting
   a denied read as UNVERIFIED; `describe-jobs` prints both SEC pins per job and fails when one is not 1; `capacity-readout` adds the
   worker's request counts and latencies, the Cloud Tasks queue's depth and attempt outcomes and the worker's error-level logs,
   aggregates only; tests and docs in the same PR; it deploys nothing (workflow, `ops/`, `backend/tests/` and docs only). Order:
   design and review in draft → **ledger event 45** (the founder's floor and a fresh balance reading above USD 5; a reservation of
   USD 0.060000 only if a paid trigger can fire) → ready → Codex → explicit squash merge (→ **event 46** only if a run fired).
   PR #1123 merged at 23:18:46Z as `8c304779` and narrowed `copilot-eval.yml`'s trigger paths to the eval's own import closure
   and data: a PR confined to `.github/workflows/ops.yml`, `ops/`, `backend/tests/` and docs no longer fires the paid run, and it
   never fired `eval-baseline`. So event 45 records the floor and the fresh reading with no reservation, unless the PR's files
   come to match a filter before it leaves draft, in which case a reservation is written first and any later push while ready
   is reserved the same way.
3. **The checks:** after it merges, `describe-service`, `describe-jobs` and a `capacity-readout` over a past window of at most two
   hours; the `docs/DEPLOYMENT.md` durable-tasks checklist completed from them; one read-only context (`durable-tasks-check-01`)
   checks the reading independently; record 22 (`record-22-reviewer-01`).
4. **Monday 2026-10-12, 08:20Z:** the armed check-in dispatches the 06:00–08:00Z `capacity-readout` and compares it with record 10's
   Monday and record 20's baseline (`monday-readout-20261012-01`).
5. **Then the checkpoint's Next queue:** the COO's G3 first-customer-part review and the G4 gate; B32's qualifying retained window;
   R1 waits on the founder's custody step-A answer.

## Registration (closure 172)

Closure 172 (574 → 582; recorded 22:53:10Z; amended in place before merge at 23:12Z and at 04:06–04:07Z on 2026-10-10, two
commits, its scope saying so) registers as actual: this session; the second successor session (reads only, every write held); `record-20-reviewer-01`
resolved to its launch-time identity (`launched-2026-10-09T1958Z`; five checks, the last bound to `86334d59`; the final head not
re-bound); the predecessor's read-back design workflow `wf_11203ef3-3cf` at workflow level (its agent identities are not recoverable
here; nothing from it enters the repository); and the first record-21 reviewer context (`launched-2026-10-09T2305Z`, ended by the
usage limit before a verdict; the provisional `record-21-reviewer-01` is annotated as exercised and is formally resolved in a later closure,
since the chain rule resolves a label only in a later closure). It pre-registers, before any launch by the
successor, `record-21-reviewer-02` (the fresh reviewer) and `record-22-reviewer-01`, and annotates `ops-readback-pr-01`, `durable-tasks-check-01` and
`monday-readout-20261012-01` as covering the contexts this session launches under them, each resolved to launch-time identities in a
later closure. The side effects of `record-20-reviewer-01` beyond its five reported checks are not independently disclosed: the
predecessor's transcript is not available to the successor, and the PR #1167 description records its verdicts. No context gains
source, reconciliation or judging eligibility; every earlier identity and adverse history is retained.

## Spend

No paid run since ledger event 44; no ledger event in this record. Recorded use against the authority 1.513044 (1,153 calls);
retained holds 1.881713; headroom 21.605243; cumulative 3,212 calls / USD 5.297293; 0 active reservations. The read-back PR's
leaving draft is covered by event 45, which records the founder's USD 5 floor and the fresh balance reading taken for it and
writes a reservation only if a paid trigger can still fire for the PR's files (none can under `copilot-eval.yml`'s paths since PR
#1123 and `eval-baseline`'s filter, so no reservation is expected and nothing is encumbered today).

## Founder actions this record needs

1. **The single writer** (new; confirmed as relayed): the founder's words in the second session at about 23:00Z, "the earlier
   session is the chief", reached this session through that session's message. Nothing further is needed unless the founder wants
   to overrule it here; if the founder names the second session (`session_0172iDJgYdJweV79iRjtmgc2`) instead, this session hands
   over.
2. **Squash default** (optional, recommended; carried from record 20): Settings → General → Pull Requests → "Allow squash merging"
   → "Default commit message": "Pull request title and description".
3. **Custody step A** (optional, recommended now; carried from record 20): send the prepared relay (`DECISIONS-20.md`'s appendix) once
   to the custody side; if you agree, also tell the chief, in your own words, "If the answer is outcome B, I adopt record 16's form (b)
   for R1" (now or with the answer).
