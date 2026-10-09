# Decision record 18 — the record-17 PR merged (PR #1132; tenth deploy-skip proof); the backend suite made hermetic and gated (PR #1145; eleventh deploy-skip proof); D3 stage 2 reviewed, fixed and held for the founder's scheduler change; `eval-baseline`'s cost measured; ledger events 37–38; chief defect 7 (a squash message); closure 169 (chief, 2026-10-09)

Recorded 2026-10-09T08:25:13Z, amended 2026-10-09T08:47:35Z after the record-18 review and the stage-2 delta reviewer's second round, by the chief (`https://claude.ai/code/session_01GWYV7WXWstgVGQG43YcSM8`). Context: record 17 merged to main as
`1868ddf8f38362c333b6779caf3301d7ee75e063` (PR #1132, 2026-10-09T06:42:33Z); the backend test-hermeticity change merged as
`4c0563add744da7207c729564cfebc5f184e7f17` (PR #1145, 2026-10-09T08:01:22Z); this branch was restarted from `4c0563ad`. Records
only: no code, workflow, migration, cloud, IAM or production change in this PR; no provider call; no reservation; no source
material opened.

## PR #1132 review record closed (decision record 17)

The record-17 reviewer (`record-17-reviewer-01`, closure 168) reviewed the first head `30cae1c4`: **no blocker**; four
should-fixes and nine nits, applied in `deb75843` (record 17); its context then ended with a container restart. The fresh delta
reviewer pre-registered in the amended closure 168 (`record-17-delta-reviewer-01`) reviewed `deb75843`: **no blocker**; three
should-fixes (decision 60's closure count; the founder's pending scheduler change described as done in five places; a stale PR
title and body) and five nits, applied in `078efee5`; the same context re-checked `078efee5`: **no blocker, no new findings, bound
to `078efee5`**. PR #1132 left draft at 06:36:46Z with no paid run (tasks-only). Codex reviewed `078efee` (summary Completed
06:40:13Z) with one P2 comment: that the company-search fuzzy fallback's SEC downloads run on the edgartools executor rather than
the event loop. The chief checked it offline with a fake `EdgarCompany` whose `name` property records its thread: the constructor
ran on the executor (`edgar__0`), but `_transform_company` read `edgar_company.name` on the event-loop thread (`MainThread`),
which in edgartools 5.58.0 triggers the lazy submissions download, and the build then failed on the `sic` keyword. The record
stood; the chief answered the thread with that evidence and resolved it. `review-gate` passed at 06:40:38Z; squash-merged
`1868ddf8` with the expected head `078efee5`. Main CI run 37894950107 green; `deploy-backend` job 113706433465 skipped every
deploy step, 5 to 16 (**tenth deploy-skip proof**). Its environment block, printed at 06:51:05Z, showed `DURABLE_TASKS_ENABLED:
true` and `TASKS_WORKER_URL` set.

## Chief defect 7 — PR #1132's squash message on main

The chief merged PR #1132 without an explicit commit message, so the squash commit `1868ddf8` on main carries the branch's three
commit messages. The second of them says "backfill-facts moved to Monday 07:30 by the founder" and the first that stage 2 "goes
back to the founder with options A, B and C" and gives closure 168's count as 506 → 531 (final 532); all were superseded before
merge by the reviewed record (the move is pending; the founder chose option A). Main's history is not rewritten; `DECISIONS-17.md`
is authoritative. From PR #1145 on, the chief passes an explicit squash title and message stating the merged state. A machine
control exists: the repository's squash default (`squash_merge_commit_message: COMMIT_MESSAGES`, title `COMMIT_OR_PR_TITLE`) is
what copied the branch's messages, and setting it to the pull request's title and body would make a merge without an explicit
message carry the reviewed text. It is a repository setting, outside the chief's remit and affecting every writer, so it is put to
the founder (action 4 below); until then the practice is recorded here and in `APPOINTMENTS.json`.

## The backend suite made hermetic and gated (PR #1145)

Pre-registered by record 17 as `test-hermeticity-pr-01`. A read-only investigation workflow (`wf_1a3eae82-0ee`, seven agents,
2026-10-08 20:33–22:03Z) found every leak, designed the gate and its fixes, and refuted its own plan; the chief applied the result
as `024ed36d` (full suite behind the gate: 5,828 passed, 0 attempts). PR #1145 opened as a draft at `57f1ac53` (the same tree on
main `1868ddf8`).

**What landed.** `backend/tests/support/network_gate.py`, registered by `tests/conftest.py`, blocks and records DNS lookups of
non-local names (a reverse `getnameinfo` of a non-local address included) and `connect`, `connect_ex`, `sendto` and `sendmsg` to
non-loopback endpoints, port 53 or a configured loopback proxy; it clears the `*_proxy` variables and sets `NO_PROXY=*`. Each
attempt fails the test it was made for, in any report phase (a skip or an xfail does not hide it); an attempt no running test
owns fails the session. Its self-test (`tests/unit/test_network_gate.py`) proves it in-process and in pytester children. The
fixes fake each boundary with no assertion changed: the on-visit EFTS history seam in two files, search and quotes in the smoke
company tests, and the two edgartools enrichment seams for three allowlisted stream files (none a locked rule-6 anchor; a test
keeps the anchors off that allowlist). `tests/conftest.py` pins `SENTRY_DSN`, `POSTHOG_API_KEY`, `RESEND_API_KEY`,
`ALPHA_VANTAGE_API_KEY` and `TURNSTILE_SECRET_KEY` empty. `CLAUDE.md`'s Tests bullet and
`lessons/test-conftest-hermetic-env.md` state the gate and its limits.

**Review.** A lean three-lens review (`wf_eec547ad-e4d`: correctness, tests and gates, policy and scope; three refuters) of
`024ed36d`: **no blocker**. Refuters confirmed two should-fixes: the self-test did not pin the setup, teardown, skip and xfail
branches (two gate mutants survived), and a developer `backend/.env` with `RESEND_API_KEY` turned 10 tests red, the locked
`test_auth_flow.py` among them, with a gate hint that pointed at editing the test. A third (a rule-6 paragraph) was refuted as
already in the PR body. Both should-fixes and every nit were applied in `de180582` (five self-test mutants each fail it; full
suite 5,829 passed, 0 attempts). The single delta reviewer (`test-hermeticity-delta-reviewer-01`) found **no blocker** on
`de180582` with six nits (among them a development `.env` with `TURNSTILE_SECRET_KEY` failing 18 auth and form tests with no
network attempt), applied in `c8f660a4`; the same context found **no blocker** on `c8f660a4` with three cosmetic nits, two
handled by a reflow (`f30ec068`; `git diff --word-diff` against `c8f660a4` shows no changed word) and one in the PR body.
The delta reviewer did not re-check `f30ec068`; Codex reviewed it.

**Merge.** Ledger event 37 reserved USD 0.060000 at 07:48:27Z; the PR left draft at 07:48:48Z; the one paid `copilot-eval` run
(37901177082, accepted 18 / 18) cost USD 0.013699 (event 38). Codex reviewed `f30ec06` (Completed 08:00:10Z) with one P2 comment:
that `getnameinfo` given a hostname falls through to a live DNS lookup. It does not: CPython resolves the sockaddr with
`AI_NUMERICHOST`, so `getnameinfo(("localhost", 443), …)` fails with `gaierror` although `getaddrinfo("localhost", 443)` resolves,
and under `strace` the hostname call made no `socket`, `connect` or `sendto` call and opened no resolver file. The chief answered
the thread with that evidence and resolved it; no push (a push would have fired a further paid run). `review-gate` passed at
08:00:21Z; squash-merged `4c0563ad` with an explicit message. Main CI run 37902419633 green; `deploy-backend` job 113730224808
skipped every deploy step, 5 to 16 (**eleventh deploy-skip proof**); its environment block, printed at 08:08:54Z, again showed
`DURABLE_TASKS_ENABLED: true` and `TASKS_WORKER_URL` set.

## D3 stage 2 — reviewed, fixed and held

Under closure 167's label `d3-stage-2-pr-01`, the chief implemented option A locally (`3656ba46` on `da636f6c`): the insider
endpoint behind `ENABLE_INSIDER_ACTIVITY` (off unless set), the always-failing fuzzy-search fallback deleted, both SEC pins on the
API service, a deploy step that prints the repository's variable-driven switches (chief defect 6's rule-12 enforcement), the
budget gate rewritten for the pinned fleet, and the docs.

**Review.** A lean three-lens review (`wf_9110300a-448`: correctness, tests and gates, docs and ops; eleven refuters) of
`3656ba46`: **no blocker**. Refuters confirmed four should-fixes (one raised by two lenses): the deploy did not keep the insider
switch off (a hand-set `true` would survive every later deploy); the switch-report gate read only the job env and checked the
step's source, not its output; the overlap model ignored Cloud Run task retries (each attempt restarts its timeout, so a retried
pregenerate can meet backfill-facts); and the service bootstrap commands were unpinned. They downgraded six others to nits
(queue-induced breaker opens; the company-search test's sentinel; the update gate's readable forms; the scheduler precondition;
post-deploy verification; the rollback text). The chief applied all of them and every nit but one in `5c18a8ea`: the deploy pins
`ENABLE_INSIDER_ACTIVITY=false`; the switch gate checks printed output and fails a repository variable read outside the job env;
the update gate fails closed on any unreadable update-shaped line or unresolvable script (as of `7465926f`; the delta reviewer
then found the four bypasses below, closed in `d8508571`); the schedule gate pins time zones, the EFTS crons and per-attempt task
timeouts; the insider switch is a route dependency; the docs add retries, the bootstrap pins, the breaker and dry-run limits,
post-deploy verification and the revert caveat. 24 gate bypasses were mutation-checked; each fails the right test. Not done: a
single-flight lock for cold ticker-file loads (a class-level asyncio lock binds to one event loop when contended; the cost it
removes is one ticker-file download per concurrent cold miss, at each cold start and each 24-hour cache expiry, Redis being off in
production).

**Rebased and held.** After PR #1145 merged, the two commits were cherry-picked onto `4c0563ad` as `1fac8e09` and `7465926f`; the
patch is byte-identical to the reviewed one. Behind the new gate the full suite gave 5,833 passed, 39 skipped (the PostgreSQL
concurrency files), 2 deselected, with 0 gate reports and 0 lookups reaching the second guard; the performance lane passed 2. The
single delta reviewer (`d3-stage-2-delta-reviewer-01`) reviewed `7465926f` before any push: **no blocker** (149 and 173 targeted
tests passed under the network guard with no attempt; ruff and bandit clean; 14 gate mutants, each failing the right test). It
found three PR-body should-fixes (the service env map's last entry, the report step's position, the count of downgraded findings)
and eight nits: the 6-K text timeout in `docs/OPERATIONS.md` (30 s, not 15 s); four gate bypasses (a root-level script shadowing a
`backend/` script of the same path, a create on a line that also holds `update-traffic`, the `vars['…']` index syntax, a
workflow-level `env` read from a variable); an extension-less script missing from the gate's not-covered list; the insider route
answering 405 to POST and staying in the OpenAPI schema; the dry-run cap's wording in `internal.py`; and PR-body wording. The
chief applied them in `d8508571` (four bypasses closed, each mutation-checked; extension-less scripts named as not covered; the
6-K figure, the insider comment and the dry-run text corrected; behind the gate the full suite again gave 5,833 passed, 39 skipped
and 2 deselected, 0 gate reports). The same context re-checked it: **no blocker, bound to `d8508571`** (179 targeted tests passed
with no network attempt; every fix and the earlier mutants mutation-checked), with notes on the draft PR description only, applied
to it. The change is held on a local branch, unpushed: the session has one designated branch, so a stage-2 PR opened now would
block this record until the founder's scheduler change, and the branch could not then be restarted for records without a force
push (classifier denial 8). It goes up after this record merges; it merges only after the founder confirms the
`backfill-facts-weekly` move.

## `eval-baseline`'s cost measured

The stage-2 PR touches `backend/app/`, so `eval-baseline` (70 summary generations, deterministic scorers, no judge) runs on every
push to it, draft or not. No run of it was in the ledger. The chief read the public job logs of the four most recent runs that
executed (on other writers' PRs #1135, #1138, #1141 and #1146, 2026-10-09 06:44–07:46Z; only their logs were read): USD 0.351572,
0.361439, 0.361183 and 0.351671 (70 or 71 `ai_call` lines each, all at peak pricing). Per the record-09 rule each push to the
stage-2 PR is reserved at the dearest measured run × 2, rounded up: **USD 0.730000**, in addition to the `copilot-eval`
reservation (USD 0.060000) when it leaves draft or is pushed while ready. The stage-2 PR is therefore reviewed locally first and
pushed once.

## Registration (closure 169)

Closure 169 (532 → 564) resolves closure 168's provisional labels to launch-time identities: `record-17-reviewer-01` (launched
2026-10-08T20:32Z), `record-17-delta-reviewer-01` (2026-10-09T06:15Z; two rounds) and `test-hermeticity-pr-01` (the investigation
workflow's seven, the review workflow's six and the delta reviewer, 07:30Z, two rounds). It registers, under closure 167's still
provisional `d3-stage-2-pr-01`, the stage-2 review workflow's fourteen and its delta reviewer (08:04Z), and pre-registers this
record's reviewer (`record-18-reviewer-01`, one context for the review and its deltas) before launch. The closure was amended in
place before merge after this record's review (corrected counts and side-effect disclosures; no identity added, removed or
reordered).

Side effects, from the transcripts:
- `record-17-reviewer-01`: 98 read-only `gh api --method GET` requests in 29 commands, loops expanded (two `actions/variables`
  reads refused with 403), job logs saved to its scratchpad tools directory; no repository write, no SEC or provider request.
- `record-17-delta-reviewer-01`: round one 25 GETs in 15 commands (six job-log downloads following GitHub's redirect to log
  storage), round two 2 GETs; scratchpad writes; the runtime-records gate under the network guard.
- Hermeticity investigation (`wf_1a3eae82-0ee`): one agent made 4 GETs in 2 commands (commit history and one PR body); the refuter
  of the plan started a PostgreSQL 16 cluster in its scratchpad under `unshare --user`, listening on 127.0.0.1:55432 only, to run
  CI's four concurrency files behind the gate (65 passed), then stopped it, and wrote two synthetic `.env` files (Sentry and
  PostHog values on `.invalid` hosts) that it left in place (the chief removed them at 08:45:49Z); the design and synthesis agents
  wrote gate drafts in scratchpad copies; no repository write, no SEC request. Probes used `.invalid` names or 192.0.2.0/24
  (blocked) or stayed on loopback: the design agent ran a non-forwarding decoy proxy on 127.0.0.1 with the proxy variables pointed
  at it, and the plan's refuter ran loopback listeners (one received an HTTP CONNECT line); nothing left the machine.
- Hermeticity review (`wf_eec547ad-e4d`): the tests-and-gates lens first tried `initdb` via `su postgres` (06:36:15Z), then
  started a PostgreSQL 16 cluster in its scratchpad as the `postgres` user via `setpriv` with `CAP_DAC_READ_SEARCH`, on
  127.0.0.1:55432 only, and stopped it; the policy lens used scratch `.env` files with dummy values and removed them (06:54:10Z
  and 07:08:20Z); its refuter wrote two with a dummy `RESEND_API_KEY` and left them (the chief removed them at 08:45:49Z); one
  refuter made 2 GETs (PR #1145); no repository write.
- Stage-2 review (`wf_9110300a-448`): scratch clones and exports only; mutation harnesses in scratch; one lens's pytest run in the
  chief's scratchpad worktree touched that worktree's gitignored `backend/earningsnerd.db`; no GitHub, SEC or production request.
- `test-hermeticity-delta-reviewer-01`: 2 GETs (PR #1145 head and body, one per round); scratch extracts left in its scratchpad
  and dummy `.env` files removed; its pytester runs, like the chief's and other reviewers' runs of the gate's self-test, wrote
  pytest's own temporary directories outside the scratchpad (`pytest-of-root`, rotated by pytest); no repository write.
- `d3-stage-2-delta-reviewer-01`: a scratch extract of `7465926f` (a throwaway `git init` inside it), a mutation harness and probe
  files in its scratchpad (mutations, helper scripts and probe files removed; the extract and harness left); read-only git
  commands in the repository; 0 network commands (no `gh`, fetch or push; no SEC, Yahoo or production request); no repository
  write.

## Spend

Ledger events 37–38 (PR #1145): reservation USD 0.060000 at 07:48:27Z (`cb4a7d50…`, 113,220 B, version 38); settlement at
07:55:01Z at the actual USD 0.013699 (36 calls, all at peak pricing; USD 0.046301 released; `54b94cd8…`, 114,888 B, version 39).
Recorded use against the authority 0.769061 (944 calls); headroom 22.349226; cumulative 3,003 calls / USD 4.553310. This record's
PR fires no paid run.

## Founder actions this record needs

1. **Move `backfill-facts-weekly` (unchanged from record 17):** `gcloud scheduler jobs update http backfill-facts-weekly
   --location=us-west1 --schedule="30 7 * * 1"`, then check it with `gcloud scheduler jobs describe backfill-facts-weekly
   --location=us-west1 --format="value(schedule,timeZone)"` (expect `30 7 * * 1` and `Etc/UTC`). Tell the chief when it is done;
   the stage-2 PR merges only after that.
2. **Durable tasks (rollout owner, unchanged):** the post-deploy checks in `docs/DEPLOYMENT.md`.
3. **Custody step A (optional, no deadline; unchanged).**
4. **Squash default (optional; new):** in the repository's settings (General → Pull Requests → Allow squash merging), choose
   "Default to pull request title and description", so a squash merge without an explicit message carries the reviewed PR text
   instead of the branch's commit messages (chief defect 7). It changes the default for every writer.
