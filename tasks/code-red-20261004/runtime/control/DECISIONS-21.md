# Decision record 21 — chief succession: the predecessor session blocked by a Claude Code safety check from about 21:40Z and the successor appointed by the founder's handover brief at 22:38Z; PR #1167 (record 20) merged, fourteenth deploy-skip proof; #1169's deploy read back from its log (every process carries both SEC pins, the insider switch is off, the health check passed) and six later main runs classified; the founder's USD 5 balance floor recorded as a stop condition; a duplicate second successor session holds every write; the Monday check-in re-armed; disclosures (chief defect 9, classifier denials 11 and 12, a record-20 wording correction); closure 172 (chief, 2026-10-09)

Recorded 2026-10-09T23:02Z, amended 2026-10-09T23:12Z (the relayed confirmation) and 2026-10-10T04:05Z (the usage-limit
interruption; the fresh reviewer context), by the successor chief (`https://claude.ai/code/session_011jZyZqfNWZRqiFNWfTc3u8`).
Context: record 20 merged to main as `da8dc998` (PR #1167, 2026-10-09T22:14:52Z); main has since moved to `a572876c` through
other writers' PRs (#1143, #1142, #1166); this is the first PR from the successor's branch `claude/stoic-wright-6jeujo`, started
at `a572876c`. Records, one lesson and the lessons index only: no code, workflow, migration, cloud, IAM or production change in
this PR; no provider call; no reservation; nothing opened under `tasks/readiness-2026-09-21/acceptance/` or
`tasks/review-evidence/`.

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
5. **Closure 172** (574 → 580) registers this session and the second successor session, resolves `record-20-reviewer-01`, registers
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
or closure. It stands down to read-only for good. It also passed one observation, taken up in the Plan: open PR #1123 would change
which paths fire `copilot-eval`, so before event 45 the chief re-checks whether a `backend/tests`-only PR still fires the paid
run. The second session is registered in closure 172 as a read-only context (amended in place before merge with this list).

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

## Production after record 20: #1169's deploy read back from its log; six later main runs

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

This is the first read-back of the worker's pins from a deploy log by the chief role since record 19 (which relied on the echoed
commands alone); the worker's live configuration is still read back only by the read-back PR's `describe-service`.

**Later main runs**, each from its `deploy-backend` job's step list (steps 6 to 17 are the deploy steps):

| Merge | PR | Main CI run | `deploy-backend` job | Outcome |
|---|---|---|---|---|
| `8eed19c4` | #1153 (risk headings) | 37997224662 | 114048950234 | every deploy step skipped (22:13:40–22:13:49Z) |
| `07bfaa63` | #1156 (size-budget gate) | 37997231285 | 114048947096 | every deploy step skipped (22:13:36–22:13:40Z) |
| `da8dc998` | #1167 (record 20) | 37998159560 | 114051857861 | every deploy step skipped (fourteenth proof) |
| `97eea4ca` | #1143 (filing reader) | 37998425708 | 114052833022 | every deploy step skipped (22:26:12–22:26:16Z) |
| `f8ec0491` | #1142 (a11y) | 37999408483 | 114055797517 | every deploy step skipped (22:36:08–22:36:15Z) |
| `a572876c` | #1166 (design follow-ups A–E) | 38000074176 | 114057357644 | **deployed** (22:41:34–22:44:23Z; every step success; read back below) |

**#1166 (`a572876c`, design critique follow-ups A–E; merged 22:35:48Z by another writer) deployed production** while the successor
was taking over (`deploy-backend` job 114057357644, 22:41:34–22:44:23Z), read from its log the same way: switches
`DURABLE_TASKS_ENABLED=true TASKS_WORKER_URL=set`; `apply_migrations: applied=0 skipped=41`; the task worker
`earningsnerd-task-worker-00009-t8x` and the API service `earningsnerd-backend-00456-9xj` each deployed and routed 100% LATEST with
tags cleared; every echoed `--update-env-vars` (the worker, the service, pregenerate, the six-job loop, backfill-facts) carries
`SEC_RATE_LIMIT_PER_SECOND=1` and `EDGAR_RATE_LIMIT_PER_SEC=1`, the service's also `ENABLE_INSIDER_ACTIVITY=false`; no job reported
missing; health at 22:44:18Z `status healthy` (database latency 8.03 ms); "Deployed a572876 and verified healthy." So production as
this record is written runs #1166's images: the API service `00456-9xj` and the worker `00009-t8x`, every pin in place.

## The founder's USD 5 floor (instruction 2026-10-09T21:38:15Z)

The founder's instruction, given to the predecessor: **"proceed. you can keep going until the balance reaches 5$"**. The chief reads
it as a **stop condition on the provider wallet**, added beside the standing reservation rule, not as an authorization: the shared
USD 25 authority (ledger event 2), the dearest-measured-run reservation rule (record 09) and `provider_wallet_is_authorization:
false` stand unchanged. Operating rule from this record: **before any paid trigger, both must hold** — (1) a reservation is written
to the private ledger first (`copilot-eval` USD 0.060000 per run; `eval-baseline` USD 0.730000 per push), and (2) a fresh reading from
the free `deepseek-balance` workflow, taken for that trigger, shows the DeepSeek balance above USD 5.00. A reading at or below USD
5.00 holds every paid trigger until the founder says otherwise. Latest reading: **USD 24.25 at 21:10:42Z** (run 37991815539, job
114027646900, read by the predecessor; the successor confirmed the figure from the job's public log). The floor is written into the
ledger by event 45, the reservation for the read-back PR's `copilot-eval` run, together with the fresh reading taken before it
(Plan, below); the predecessor's attempt to add it to its ledger script was the first refused command.

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
   Nothing in the repository, the ledger or production changed during the interruption; PR #1172's CI completed green on
   `72f01ed` at 23:27Z.
7. **The successor's side effects to this record:** read-only GitHub requests (runs, jobs, one PR, the open PR list, the balance
   job's log); two pages of the predecessor's session event log through the platform's session API (its own transcript events,
   summarised through a redacting script; one path fragment of the predecessor's scratchpad seen in its tool calls, written nowhere);
   two signed job-log downloads (the #1169 and #1166 deploy logs) into the scratchpad, each read through the redacting filter
   and the raw copies deleted; the private ledger read back once; the two
   trigger operations; the agent copy and a virtual environment with the pinned backend toolchain in the scratchpad; four cross-session
   messages (three received, one sent). No SEC, production, `run.app` or Google Cloud request; no repository write before this PR.

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
   design and review in draft → **ledger event 45** (the founder's floor, a fresh balance reading above USD 5, a reservation of USD
   0.060000) → ready (one `copilot-eval` run) → Codex → explicit squash merge → **event 46** settles the run. Any later push while
   ready is reserved first the same way. Before event 45 the chief re-reads `copilot-eval.yml`'s trigger paths on main (open PR
   #1123 proposes narrowing them): if a `backend/tests`-only PR no longer fires the paid run, no reservation is needed and the
   floor reading is still taken and recorded.
3. **The checks:** after it merges, `describe-service`, `describe-jobs` and a `capacity-readout` over a past window of at most two
   hours; the `docs/DEPLOYMENT.md` durable-tasks checklist completed from them; one read-only context (`durable-tasks-check-01`)
   checks the reading independently; record 22 (`record-22-reviewer-01`).
4. **Monday 2026-10-12, 08:20Z:** the armed check-in dispatches the 06:00–08:00Z `capacity-readout` and compares it with record 10's
   Monday and record 20's baseline (`monday-readout-20261012-01`).
5. **Then the checkpoint's Next queue:** the COO's G3 first-customer-part review and the G4 gate; B32's qualifying retained window;
   R1 waits on the founder's custody step-A answer.

## Registration (closure 172)

Closure 172 (574 → 582; recorded 22:53:10Z; amended in place before merge twice, 23:12Z and 2026-10-10 about 04:10Z, its scope
saying so) registers as actual: this session; the second successor session (reads only, every write held); `record-20-reviewer-01`
resolved to its launch-time identity (`launched-2026-10-09T1958Z`; five checks, the last bound to `86334d59`; the final head not
re-bound); the predecessor's read-back design workflow `wf_11203ef3-3cf` at workflow level (its agent identities are not recoverable
here; nothing from it enters the repository); and the first record-21 reviewer context (`launched-2026-10-09T2305Z`, ended by the
usage limit before a verdict, resolving the provisional `record-21-reviewer-01`). It pre-registers, before any launch by the
successor, `record-21-reviewer-02` (the fresh reviewer) and `record-22-reviewer-01`, and annotates `ops-readback-pr-01`, `durable-tasks-check-01` and
`monday-readout-20261012-01` as covering the contexts this session launches under them, each resolved to launch-time identities in a
later closure. The side effects of `record-20-reviewer-01` beyond its five reported checks are not independently disclosed: the
predecessor's transcript is not available to the successor, and the PR #1167 description records its verdicts. No context gains
source, reconciliation or judging eligibility; every earlier identity and adverse history is retained.

## Spend

No paid run since ledger event 44; no ledger event in this record. Recorded use against the authority 1.513044 (1,153 calls);
retained holds 1.881713; headroom 21.605243; cumulative 3,212 calls / USD 5.297293; 0 active reservations. The read-back PR's
`copilot-eval` run is reserved by event 45, which also records the founder's USD 5 floor and the fresh balance reading taken for it.

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
