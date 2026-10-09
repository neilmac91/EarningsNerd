# Decision record 20 — the record-19 PR merged (PR #1155; thirteenth deploy-skip proof); three later deploys by other writers kept every pin; the founder's instruction of 2026-10-09 on the open items: each analysed and decided (the durable-tasks post-deploy checks taken on by the chief; the squash default and custody step A recommended and prepared for the founder, who alone can act on them); a capacity baseline; the read-back PR and the Monday readout planned; closure 171 (chief, 2026-10-09)

Recorded 2026-10-09T19:56:39Z, amended 2026-10-09T20:44:22Z after the record-20 review and its delta check, by the chief
(`https://claude.ai/code/session_01GWYV7WXWstgVGQG43YcSM8`).
Context: record 19 merged to main as `8ff4c532` (PR #1155, 2026-10-09T12:37:28Z); main has since moved to `25da25bb` through other
writers' PRs; this branch was restarted from `25da25bb`. Records only: no code, workflow, migration, cloud, IAM or production
change in this PR; no provider call; no reservation; no source material opened.

## PR #1155 review record closed (decision record 19)

The pre-registered reviewer `record-19-reviewer-01` (closure 170; launched 11:56Z) kept one context for five checks: `b836df67`
**no blocker** (4 should-fixes and 4 nits, applied in `dd1cf951`); `dd1cf951` **no blocker** (1 should-fix and 2 nits, applied in
`2cd2e050`); `2cd2e050` **no blocker** (1 should-fix, applied in `cb6b6ea6`); `cb6b6ea6` **no blocker** (1 optional nit, applied
in `b754b0ec`); `b754b0ec` **no blocker and no findings, bound to `b754b0ec`**. PR #1155 left draft at 12:29:47Z with no paid run
(tasks-only; its `eval-baseline` job took the path filter's skip). Codex reviewed `b754b0e` (summary Completed 12:32:49Z) with no
findings; `review-gate` passed at 12:33:16Z; squash-merged `8ff4c532` at 12:37:28Z with the expected head and an explicit title and
message. Main CI run 37931265611 green; `deploy-backend` job 113825085908 ran the switch report (`DURABLE_TASKS_ENABLED=true
TASKS_WORKER_URL=set`) and the change detector, which printed "No deployable backend changes - skipping deploy.", and skipped every
deploy step, 6 to 17 (**thirteenth deploy-skip proof**).

## Production after record 19: three deploys by other writers kept every pin

Three other writers' PRs merged with deployable backend changes after the stage-2 deploy. Each `deploy-backend` log (public; read
by the chief) shows the same switch report, 0 of 41 migrations applied, the API service command carrying both SEC pins and
`ENABLE_INSIDER_ACTIVITY=false`, four more pin pairs (task worker, pregenerate, the six-job loop, backfill-facts), all eight jobs
updated (none missing) and a healthy check:

| PR | Merge | `deploy-backend` job | Window (UTC) | API service revision | Task worker revision |
|---|---|---|---|---|---|
| #1146 (filing page) | `cc2282ac` | 113823179214 | 12:40:02–12:42:40Z | `earningsnerd-backend-00452-cns` | `earningsnerd-task-worker-00005-dlq` |
| #1147 (company page) | `29493b53` | 113912761140 | 16:15:52–16:19:33Z | `earningsnerd-backend-00453-wg4` | `earningsnerd-task-worker-00006-vgx` |
| #1148 (homepage) | `1a31b298` | 113924685529 | 16:45:05–16:47:41Z | `earningsnerd-backend-00454-tph` | `earningsnerd-task-worker-00007-7fx` |

This rests on the echoed commands and their success; the last read-back of the live configuration was record 19's (11:41–11:52Z).
Every deploy re-asserts the pins from `ci.yml`, as stage 2 intended; the read-back PR below makes each deploy checkable without
reading its log.

## The founder's instruction (2026-10-09, about 19:45Z)

"Proceeds with the implementation of the next steps. in terms of the open points "still with me", for decisions pending, please
analyse the pros and cons of each and come up with a recommended approach. from this, proceed with the implementation of the
associated actions. for tasks, please complete them - use lots of tokens to ensure you do work you're proud of. for optional steps,
go for it."

The chief reads it as: carry out the next steps already planned (records 19 and 20); take on the one task still with the founder,
the durable-tasks post-deploy checks, and complete it; decide the two optional items on their merits and act on them as far as the
chief's tools reach. It authorises no IAM, cloud or production change (`docs/DEPLOYMENT.md`: "IAM changes require the founder's
specific approval") and it does not adopt record 16's form (b), which takes effect only on the founder's own named line.

## The three open items — analysis and decision

**1. Durable-tasks post-deploy checks (a task; the founder was the rollout owner).** `docs/DEPLOYMENT.md` lists them: the
current-head CI run, API detailed health, the service at minimum one instance and 1 GiB, the worker's command and revision,
authenticated task success, then task retries and errors, API latency and SQL connections before expanding workload.
- Options: (a) the founder runs them by hand in the Google Cloud console; (b) the chief runs them through read-only operations,
  extending those operations where they cannot see a check; (c) leave them.
- Pros of (b): the founder delegated the task; every check becomes repeatable evidence in the repository's own workflow under the
  existing keyless identity, with outputs restricted to aggregates; it adds no IAM and no production change. Cons: a small code PR
  (workflow, readout script, tests and docs), reviewed like any other, and one reserved `copilot-eval` run on leaving draft
  (it touches `backend/tests`), plus one more, reserved first, for each later push while it is ready; permissions the Ops
  identity lacks show up as recorded denials, not answers.
- **Decision: (b).** Done now with existing operations: the CI runs and health (each deploy's own check), API latency, SQL
  connections and error logs (the baseline below). Not yet visible to any operation: the service's minimum instances and memory,
  the worker's command, sizing, ingress and invoker policy, the worker's request outcomes, and the Cloud Tasks queue's depth and
  attempt outcomes. The read-back PR adds exactly those, then the chief dispatches the operations and completes the checklist in the
  next record.

**2. The repository's squash default (optional; record 18, chief defect 7).** GitHub offers four defaults for a squash merge made
without an explicit message: the default message, the pull request title, the title and commit details, and the title and
description.
- Pros of "Pull request title and description": a merge by any writer that passes no message carries the reviewed text instead of
  the branch's intermediate commit messages (the chief-defect-7 failure); review records here are written into PR descriptions; no
  runtime effect; reversible at any time.
- Cons: it changes every writer's default; long descriptions (sections, links, the generator footer) become commit bodies on main;
  a description edited after review flows in unreviewed.
- **Decision: recommend "Pull request title and description".** The chief keeps passing an explicit title and message on every
  merge either way. It is a repository-wide setting that changes every writer's default, which record 18 left outside the
  chief's remit, so the chief does not change it (whether this session's GitHub access could is untested) and it is the
  founder's click: Settings → General → Pull Requests → under "Allow squash merging", set "Default commit message" to
  "Pull request title and description".

**3. Custody step A for R1 (optional; record 16).** One metadata-only request to the custody side, relayed once by the founder,
answered from retained controls; its outcomes A, B and C were fixed in advance.
- Pros of relaying now: it is the only route record 16 leaves to end the R1 hold on assurance terms; it is metadata only, costs the
  chief nothing and asks no hashing; each outcome is already decided, so the answer converts directly into release, form (b) or the
  founder-only choices.
- Cons: custody minutes (the founder decides whether they count against the 136 remaining); outcome C is plausible (the committed
  evidence shows pre-recovery references for at most about 17 of the 69), which would surface choices W1–W5; it does not touch the
  current D3 or durable-task work.
- **Decision: recommend relaying now, and recommend that the founder also give the chief, in the founder's own words, the
  conditional adoption "If the answer is outcome B, I adopt record 16's form (b) for R1".** Form (b) binds only controls retained
  before recovery that all agree, which keeps the assurance record 05 sought and saves a round trip. Only the founder can relay
  (the chief has no channel to the custody side), and only the founder's own line, reaching the chief, adopts form (b). Record 16
  expected that line after the answer; given earlier, it changes the timing only: the chief shows the founder its outcome
  classification and counts before any comparison runs, and the founder can withdraw the line until then. The prepared relay text
  is in the appendix below.

## Capacity baseline (read-only `capacity-readout`, run 37982853743)

Window 2026-10-09T17:45:00Z to 19:45:00Z, observed at 19:49:49Z, all on revision `earningsnerd-backend-00454-tph`. Aggregates only:
- API requests 1,138: 997 × 200, 59 × 302, 23 × 401, 59 × 404, no 5xx.
- API latency over 1,139 samples: mean 60.4 ms; bucket upper bounds p50 ≤ 46.0 ms, p90 ≤ 158.7 ms, p95 ≤ 174.5 ms, p99 ≤ 255.5 ms.
- Cloud SQL backends per one-minute sample: 3–4 on the application database, 5–6 in all, against `max_connections` 25 (3 reserved
  for superusers); the current snapshot showed 6 client backends.
- No log entry at error severity and no pool-exhaustion signature for the service or any job.
- `filing-scan` ran at 18:00 and 19:00 UTC, each succeeded with no retry; no other job ran in the window. The receipt marks the
  `filing-scan` execution source `partial` (`page_limit`: 500 retained executions inspected); the database job ledger, which is
  not truncated, shows the same two runs.

The task worker and the queue are outside this receipt by design today; the read-back PR adds them.

## Plan

1. **This record's PR**, then the **read-back PR** (closure 171's label `ops-readback-pr-01`): `describe-service` reports the API
   service's minimum and maximum instances, CPU, memory and CPU allocation, and the task worker's revision, traffic, command,
   sizing, ingress, allow-listed env values (both SEC pins included) and whether its invoker policy admits the public; it fails
   on a public invoker, tagged or split worker traffic, or a pin other than 1. `describe-jobs` prints both SEC pins per job and
   fails when one is not 1. `capacity-readout` adds the worker's request counts and latencies, the queue's depth and attempt
   outcomes, and the worker's error-level logs, aggregates only. Tests and docs in the same PR. It deploys nothing (workflow,
   `ops/`, `backend/tests` and docs only); `copilot-eval` runs once on leaving draft, reserved first at USD 0.060000, and once
   more for each later push while it is ready (or each return to ready after a draft push), each such run reserved first.
2. **The checks**: after it merges, the chief dispatches `describe-service`, `describe-jobs` and a `capacity-readout`, completes
   the `docs/DEPLOYMENT.md` checklist, and has one read-only context (`durable-tasks-check-01`) check the reading independently.
3. **Monday 2026-10-12**: a self check-in is armed for 08:20Z to dispatch the 06:00–08:00Z `capacity-readout`, the first Monday
   window with every process pinned and backfill-facts at 07:30, compared with record 10's Monday and this baseline
   (`monday-readout-20261012-01` for any analysis context).

## Registration (closure 171)

Closure 171 (569 → 574) resolves closure 170's `record-19-reviewer-01` to its launch-time identity (11:56Z; five checks) and
pre-registers, before any launch: `record-20-reviewer-01` (this record's reviewer, one context for the review and its deltas);
`ops-readback-pr-01` (every context of the read-back PR: design, review, refuters and delta reviewer); `durable-tasks-check-01`
(the independent check of the post-deploy checklist); `monday-readout-20261012-01` (any context analysing Monday's readout).

Side effects of `record-19-reviewer-01`, from its transcript and reports (as amended after this record's review): 68 read-only
GitHub requests over five rounds (41 `gh api --method GET`, logged in its scratchpad; 14 read-only GitHub MCP calls; 13 GETs of
signed job-log URLs into its scratchpad); the runtime-records gate under the network guard, five runs with no attempt: the first
(11:57Z) in the chief's detached review worktree, then a full checkout (the gate reads only the runtime records and the four
tabled deliverables under `tasks/readiness-2026-09-21/beta`, nothing under the two excluded directories), the others in scratchpad
archives excluding the two directories; one recursive `grep -rlc 'run\.app'` (which lists matching file names) over the four
`s2-delta*` scratch directories (12:10:49Z), whose `tree/` copies then still held both excluded directories, so grep read their
files: its output was filtered to drop every `/tree/` path and nothing from them was printed (the chief deleted those copies at
12:15Z); count-only `run.app` greps of other agents' scratch logs; reads, through its own scripts, which redacted, masked or
printed only selected fields, of the permitted excerpts of the chief's transcript (the excluded-directory line reduced to its
path, line number, length and a route flag), of the transcripts of the three `wf_5b0ebda7-c4f` agents (with that workflow's
journal and meta files), `record-18-reviewer-01` and the stage-2 delta reviewer, and of the journals of `wf_41c365bd-3e9` and
`wf_9110300a-448` (event-type counts, agent ids and labels only); path-only `find` sweeps of the filesystem and `/tmp`; hash-only
`git log` scans of the repositories under `/tmp`, `/root`, `/home`, `/opt` and `/var/tmp`, and `git cat-file -e` checks of scratch
and `/tmp` repositories and of the repository itself (paths, flags and hashes only); two raw deploy logs redacted and the raw
copies deleted; tool outputs the runner saved for it, redacted; one fragment of an already-expired signed-URL query shown in its
own tool output early on and written nowhere; one refusal by a built-in safety check (below); no repository write, no SEC,
production, `run.app` or Google Cloud request.

**Two refusals by a built-in safety check (not classifier denials).** Claude Code's built-in check refuses an `rm` whose target it
cannot resolve, such as an unguarded shell variable. It refused the record-19 reviewer's `rm -f $L/$f/job.log` at 12:04:16Z (not
run; re-issued at 12:04:21Z as `rm -f "${L:?}/${f:?}/job.log"`, which the check allowed) and the chief's own deletion loop over 19
stale scratch repositories at 12:21:59Z during the record-19 cleanup (not run; re-issued at 12:22:06Z with `"${SP:?}/${r:?}"`),
which record 19 did not disclose. `APPOINTMENTS.json`'s `classifier_denials` lists the auto-mode classifier's permission denials.
This check is a static guard on a command's form whose message asks for the guarded form, and re-issuing the same deletion in that
form is what it asks rather than a route around a denial, so neither refusal is added to that list; decision records disclose
them.

The chief's own reads and actions since record 19: the three deploy logs above and the deploy-skip job's log (public); the read-only
`capacity-readout` run 37982853743, which also reads a current connection snapshot through the Cloud SQL proxy in a read-only
transaction; the self check-in armed for Monday.

## Spend

No paid run since ledger event 44; no ledger event in this record. Recorded use against the authority 1.513044 (1,153 calls);
headroom 21.605243; cumulative 3,212 calls / USD 5.297293. The read-back PR's `copilot-eval` run will be reserved before it fires.

## Founder actions this record needs

1. **Squash default (optional, recommended):** Settings → General → Pull Requests → "Allow squash merging" → "Default commit
   message": "Pull request title and description".
2. **Custody step A (optional, recommended now):** send the prepared relay (appendix) once to the custody side; if you agree,
   also tell the chief, in your own words, "If the answer is outcome B, I adopt record 16's form (b) for R1" (now or with the
   answer).

The durable-tasks post-deploy checks are no longer with the founder: the chief runs them (above).

## Appendix: the prepared step-A relay

Record 16's request (its five fields, the qualifying-control definition from its outcomes and its rules), worded for the founder
to send once to the custody side; nothing is added to or removed from what record 16 asks. The conditional form-(b) line is not
part of the relay: it reaches the chief in the founder's own words.

```text
R1 custody step A (CODE RED decision record 16): one metadata-only request, relayed once, no deadline. Please answer from
retained custody controls as they are:

1. designating_control: which retained control designates the set released to the registered planner: its SHA-256, byte
   count, retention time (UTC) and one line of provenance (no path); and that set's count by category (bootstrap-side /
   predecessor-side / other; selected inputs / governing controls). If the designated set lies outside the 69 (category ii:
   H20's frozen source packets or source units under PR1084's offline custody; category iii: the predecessor planner's
   private clean inputs named in R1-STATUS.md), say so by category. If no retained control designates it, say so in one
   sentence.
2. reference_controls: each retained control that carries, per member of that set, both SHA-256 and byte length: its
   identity, bytes, retention time (UTC), one line of provenance (no path), and how many members it covers with both values.
   Consider at least: the receipt template; the 2026-10-04T08:09:23Z custody receipt (beyond the triple); handback v2
   b3ef723d…; and PR1084's pinned packet-contract and unit-manifest identities.
3. coverage: members covered by at least one qualifying reference control; members uncovered; members covered by references
   that disagree.
4. single_manifest: whether one retained control alone enumerates every member with both values.
5. minutes_used: the custody minutes this answer took (the founder says whether they count as preparation against the 136
   remaining).

A qualifying control was retained by the custody process before the 2026-10-05 recovery packaging and is none of: either
recovery ZIP; any custody-tool output (the 2026-10-05 custody report 7caab414… included); the controls package ceed7244…
used as a manifest; the scope decision b7f0510c…; the allowlist successor's hash used as a manifest identity; the E7 triple;
any list or manifest computed from current bytes.

Rules: no hashing or comparison of any member file; no new manifest; no file names, paths, per-file hashes or contents to the
chief; no input to any planner; stop at the first concrete discrepancy and still return the counts.
```
