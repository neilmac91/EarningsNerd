# Decision record 19 — the record-18 PR merged (PR #1149; twelfth deploy-skip proof); D3 stage 2 merged and deployed (PR #1151): every production process now runs both SEC limiters at 1, the insider endpoint is switched off and the dead fuzzy-search fallback is gone; the founder moved `backfill-facts-weekly`; ledger events 39–44; chief defect 8 (a search printed one line of an excluded directory); closure 170 (chief, 2026-10-09)

Recorded 2026-10-09T11:54:08Z, amended 2026-10-09T12:16:25Z after the record-19 review, by the chief
(`https://claude.ai/code/session_01GWYV7WXWstgVGQG43YcSM8`). Context: record 18 merged to main as
`76d45732027f43dfb7cb81dc0f6d4a97903b90b5` (PR #1149, 2026-10-09T09:02:04Z); D3 stage 2 merged as
`ae5b0f1c606346e2e1e6902145f03e729cb80a21` (PR #1151, 2026-10-09T11:32:19Z) and deployed; this branch was restarted from
`ae5b0f1c`. Records only: no code, workflow, migration, cloud, IAM or production change in this PR; no provider call; no
reservation; no source material opened.

## PR #1149 review record closed (decision record 18)

The pre-registered reviewer `record-18-reviewer-01` (closure 169; launched 08:26Z) kept one context for three checks: `297a95cb`
**no blocker** (3 should-fixes and 8 nits, applied in `fc22bd04`); `fc22bd04` **no blocker** (3 optional nits, applied in
`347da335`); `347da335` **no blocker, bound to `347da335`**. PR #1149 left draft at 08:53:14Z with no paid run (tasks-only).
Codex reviewed `347da33` (summary Completed 08:55:53Z) with no findings; `review-gate` passed at 08:56:02Z; squash-merged
`76d45732` at 09:02:04Z with the expected head and an explicit title and message. Its description, last edited at 08:48:19Z,
still said the same context "re-checks `fc22bd04`" when it merged; the squash message states the final review. Main CI run
37908677284 green; `deploy-backend` job 113750915246 skipped every deploy step, 5 to 16 (**twelfth deploy-skip proof**); its
environment block, printed at 09:09:49Z, showed `DURABLE_TASKS_ENABLED: true` and `TASKS_WORKER_URL` set.

## D3 stage 2 — merged (PR #1151)

**Opened.** At 09:02:23Z the chief restarted the branch at `76d45732` and cherry-picked the three reviewed local commits
(`b50d8dd2`, `79fde1b1`, `ffefef67`); the patch is byte-identical to the one the delta reviewer passed (`d8508571` on
`4c0563ad`). 120 targeted tests passed under the network gate with no attempt; ruff and bandit were clean. Ledger event 39
reserved USD 0.730000 at 09:04:20Z; the branch was pushed at 09:04:43Z and PR #1151 opened as a draft at 09:05:21Z. Its one
`eval-baseline` run (37909028862, 70 of 70 scored) cost USD 0.360096 (event 40; one errored call reported no usage and is recorded
at the dearest call of the run, USD 0.006853). Event 41 reserved USD 0.060000 at 09:20:39Z; the PR left draft at 09:20:58Z; its
one `copilot-eval` run (37910693958, accepted 18 / 18) cost USD 0.012763 (event 42).

**Codex's P2 and the fourth commit.** Codex reviewed `ffefef6` at 09:23:13Z with one P2: with the service pinned to 1 request per
second, a synchronous precompute dry run of 21 to 100 jobs outlasts the `/internal` route's 30 s timeout. The chief capped the dry
run at 20 jobs (tickers × forms), rejected larger previews with 400 before any SEC call, and added a test that ties the cap to the
route's timeout at the pinned rate (two mutants fail it). A stop hook flagged the unpushed commit (`4b7b3523`); a push to the
ready PR fires two paid runs, so the chief moved the commit to a local branch and reset the designated branch to its pushed head
instead of pushing it unreserved. The delta reviewer's third round found **no blocker** on `4b7b3523` (eight mutants of the cap
each fail the new test; 189 targeted tests passed under the network gate with no attempt), with two should-fixes on the draft PR
description and one wording nit (a 20-job preview "normally fits"; a mega-filer's full-history load or other SEC traffic on the
instance can still push it past 30 s). The chief amended the commit to `daab3df1` (wording only) and fixed the description; the
fourth round found **no blocker and no findings, bound to `daab3df1`** (the same 189 tests passed, no attempt). On `daab3df1` the
full backend suite behind the gate gave 5,834 passed, 39 skipped and 2 deselected, with
no attempt. Event 43 reserved USD 0.790000 (one `eval-baseline` and one `copilot-eval` run) at 09:38:08Z; the chief answered and
resolved the Codex thread and pushed at 09:38:30Z. The two runs cost USD 0.358240 (37912586500, 70 of 70) and USD 0.012884
(37912586726, accepted 18 / 18), USD 0.371124 in all (event 44).

**Gate.** A push does not trigger a Codex review. The push's `review-gate` run (37912584204) was cancelled at 09:40:06Z by the run
the description edit started in the same concurrency group (37912649291), and that run failed at 10:00:34Z after its 20-minute
wait. The chief commented `@codex review` at 10:01:02Z, which re-ran it; Codex found no major issues on `daab3df1` (10:04:00Z) and
the gate passed at 10:04:19Z. The PR then waited only on the founder. One safety-net check-in (armed 10:06:07Z) fired at 10:57Z,
found nothing new and was not re-armed; the founder was told.

**The founder's scheduler change.** At 11:31Z the founder sent the Cloud Shell output of `gcloud scheduler jobs update http
backfill-facts-weekly --location=us-west1 --schedule="30 7 * * 1"` and of its describe: schedule `30 7 * * 1`, time zone
`Etc/UTC`, state ENABLED, updated 2026-10-09T11:30:47Z, next run 2026-10-12T07:30:00Z (the last attempt, 2026-10-05T07:00:01Z, ran
at the old time). With it, every scheduled window is at most 8 requests per second configured and 10 with the task worker, as the
gate models; a handover second can reach 12.

**Merge.** The chief re-read the repository variables in the newest `deploy-backend` log (job 113750915246, 09:09:49Z): unchanged.
PR #1151 was squash-merged at 11:32:19Z with the expected head `daab3df1` and an explicit title and message (`ae5b0f1c`).

## The stage-2 deploy, verified

**Deploy log.** Main CI run 37924352506 green; `eval-baseline` skipped on the push to main (no paid run). `deploy-backend` job
113801322188 (11:37:33Z to 11:40:11Z) ran every step:
- the new switch report printed `DURABLE_TASKS_ENABLED=true TASKS_WORKER_URL=set` at 11:37:38Z, its first output on a main push;
- the change detector decided to deploy; the image was built from `ae5b0f1c`; migrations applied 0 and skipped 41;
- the task worker's revision `earningsnerd-task-worker-00004-lhq` took 100% of its traffic at 11:38:52Z, its env update carrying
  both pins;
- the API service's revision `earningsnerd-backend-00451-26p` took 100% at 11:39:21Z, its env update carrying
  `SEC_RATE_LIMIT_PER_SECOND=1`, `EDGAR_RATE_LIMIT_PER_SEC=1` and `ENABLE_INSIDER_ACTIVITY=false`;
- the pregenerate job, the six other scheduled jobs and backfill-facts were updated with both pins (none missing);
- the health check reported healthy (database 6.05 ms, SEC circuit closed) at 11:40:02Z: "Deployed ae5b0f1 and verified healthy."

**Production.** The chief dispatched the read-only `ops.yml` `describe-service` on main (run 37925254037, 11:41:05Z to 11:41:30Z,
success): 100% of traffic on `earningsnerd-backend-00451-26p`, the latest ready revision, with no tagged target;
`SENTRY_RELEASE = 'ae5b0f1c…'`; `SEC_RATE_LIMIT_PER_SECOND = '1'`, `EDGAR_RATE_LIMIT_PER_SEC = '1'`, `ENABLE_INSIDER_ACTIVITY =
'false'`, `DURABLE_TASKS_ENABLED = 'true'`; the pregenerate job runs image `backend:ae5b0f1` with both pins at `'1'`; service and
revision `maxScale` 2. **Every production process now runs both per-process SEC limiters at 1**: the API service (at most two
instances), the task worker and the eight scheduled jobs. The service and the pregenerate job were read back; the worker and the
seven other jobs rest on the deploy's echoed commands and their success (below). With the switch read back as `'false'`, the
public insider endpoint answers 404 by the code at `ae5b0f1c` (not probed) and its company-page panel stays dark.

**Independent check.** A read-only verification workflow (`wf_5b0ebda7-c4f`, 11:42–11:51Z, run under the stage-2 label and
registered in closure 170) had one agent read the deploy log against the workflow at `ae5b0f1c`, one read the `describe-service`
log, and an adversarial refuter re-read both. All three returned VERIFIED and nothing was refuted: every echoed deploy script line
matched its source; all eight jobs were updated and none skipped; the image pushed as `backend:ae5b0f1` has the digest the serving
revision runs (`b36edcd7…`). The refuter named the evidence limits: the task worker's pins and the pin values on seven of the
eight jobs are proven by the deploy's echoed `--update-env-vars` commands and their success, not read back; `/health/detailed`
names no revision; the pregenerate job's image is a mutable tag. The chief then dispatched the read-only `describe-jobs` (run
37926372299, 11:52:03Z to 11:52:32Z, success): all eight jobs run `backend:ae5b0f1` with `taskCount` 1 and their production pools,
and each carries `SEC_RATE_LIMIT_PER_SECOND` and `EDGAR_RATE_LIMIT_PER_SEC` as plain values (that operation prints names, not
values). No operation reads back the worker's env or the jobs' pin values; extending `describe-jobs` and `describe-service` to
print them is queued as a small chief follow-up.

## Chief defect 8 — a search printed one line of an excluded directory

At 09:23:27Z, looking for callers of `/internal/jobs/precompute` while applying Codex's P2, the chief ran `grep -rn` over the
repository without excluding either directory, so it traversed both. It printed one line from the review-evidence directory and
none from acceptance:
`tasks/review-evidence/returns-current-period-guard-2026-10-02/README.md` (a route-table row naming the route). No file there was
opened or read further, and the line informed nothing in the change. Rule (unchanged): repository-wide searches by executive
contexts use `git grep` with `':!tasks/readiness-2026-09-21/acceptance/' ':!tasks/review-evidence/'`. No machine gate: the
repository cannot see the chief's shell commands, and a root ignore file would steer ripgrep-based tools but not `grep -r`.

## Registration (closure 170)

Closure 170 (564 → 569) resolves closure 169's `record-18-reviewer-01` to its launch-time identity (08:26Z; three checks)
and closure 167's `d3-stage-2-pr-01`, now that the stage-2 PR has merged and its deploy is verified, to 27 identities: the design
workflow's nine (closure 168), the review workflow's fourteen and the delta reviewer (closure 169), and the three agents of the
read-only deploy verification (`wf_5b0ebda7-c4f`, registered here). It pre-registers this record's reviewer
(`record-19-reviewer-01`, one context for the review and its deltas) before launch.

Side effects, from the transcripts:
- `record-18-reviewer-01`: 28 read-only `gh api --method GET` requests, each logged in its scratchpad (seven job-log downloads
  following GitHub's redirect to log storage: one `copilot-eval`, two `deploy-backend`, four `eval-baseline`), and 2 read-only
  GitHub MCP calls (review threads of PR #1132 and PR #1145); the runtime-records gate under the network guard (four runs, no
  attempt): the first in the chief's detached review worktree (a full checkout), the others in scratchpad archives, of which
  the full ones excluded the two directories; one `git archive` of `fc22bd04`'s whole `tasks/` tree (08:48:36Z) put both
  directories in its scratchpad (only a top-level listing printed; removed at 08:48:47Z); its two raw `deploy-backend` logs
  contain the private worker URL (kept in its scratchpad, never printed); a read-only listing of pytest's temporary directory;
  writes only to its scratchpad; no repository write, no SEC or provider request.
- `d3-stage-2-delta-reviewer-01`, rounds two to four (08:30–08:38Z, 09:25–09:30Z, 09:31Z): scratch extracts of `d8508571`,
  `4b7b3523` and `daab3df1`, each with a throwaway `git init`, and mutation harnesses in its scratchpad; the extracts were
  plain `git archive` copies, so they held both excluded directories, and `git add -A` hashed their files (round one's extract
  of `7465926f` did the same, which closure 169 did not disclose); its searches there were limited to `backend/tests` and
  `tests/unit` and nothing under the two directories was opened; targeted tests under the network gate (no attempt), ruff and
  bandit there; read-only git commands in the repository, its repository searches excluding the two directories; a read of the
  installed edgartools source; 0 network commands; no repository write.
- Deploy verification (`wf_5b0ebda7-c4f`): `verify:deploy-log` made 3 read-only GitHub MCP calls and 1 GET of a signed job-log
  URL; `verify:describe-service` 5 and 2; `refute:deploy-claim` 7 and 2. All three ran read-only git commands in the repository
  and wrote only to the chief's scratchpad, where all three left raw job logs that contain the private service URLs (kept there,
  never quoted). `verify:deploy-log` also ran a local `pip show`, a filesystem-wide `find` for the installed edgartools
  `httpclient.py` (paths only) and a read of that file, and its own comparison script with `python3 -I`; the refuter ran a
  comparison script with `python3 -I`. No request to SEC, Google Cloud or any production host; no repository write.

**Scratch copies of the excluded directories.** The review above showed that scratch copies of the repository hold both
excluded directories, just as the checkout does. At 12:14–12:15Z the chief removed ten stale scratch worktrees (saving two
worktrees' uncommitted diffs first) and deleted the 65 copies of the two directories left in other scratch extracts, listing
paths only and reading nothing. Only this PR's review worktree keeps them, as a checkout. Rule (from this record): an agent's
repository copy excludes the two directories (`git archive <sha> -- . ':!tasks/readiness-2026-09-21/acceptance'
':!tasks/review-evidence'`), which the chief's review prompts now state for every copy. No machine gate: scratch copies
are outside the repository.

## Spend

Ledger events 39–44 (PR #1151's four paid runs under three reservations), each publish preceded and followed by a readback:

| Event | Written | Kind | Figures |
|---|---|---|---|
| 39 | 09:04:20Z | reservation: `eval-baseline` on opening the draft (head `ffefef67`) | 0.730000 |
| 40 | 09:19:54Z | settlement of 39 (run 37909028862) | actual 0.360096, 71 calls (one errored call at an estimate of 0.006853); released 0.369904 |
| 41 | 09:20:39Z | reservation: `copilot-eval` on leaving draft | 0.060000 |
| 42 | 09:26:40Z | settlement of 41 (run 37910693958) | actual 0.012763, 34 calls; released 0.047237 |
| 43 | 09:38:08Z | reservation: both runs of the push of `daab3df1` | 0.790000 |
| 44 | 10:02:18Z | settlement of 43 (runs 37912586500 and 37912586726) | actual 0.371124 (0.358240 + 0.012884), 104 calls; released 0.418876 |

209 calls, USD 0.743983, no excess over any reservation. Recorded use against the authority 0.769061 → 1.513044 (944 → 1,153
calls); headroom 22.349226 → 21.605243; cumulative 3,212 calls / USD 5.297293; holds unchanged. No `@codex review` comment and no
merge to main fired a paid run. This record's PR fires none.

**Observation for the CPO (no action by the chief).** Both `eval-baseline` runs on PR #1151 passed with the regression gate's
advisory warning on `mean_citation_fidelity`: 0.8296 and 0.8527 against a baseline of 0.9648. The four runs on other writers'
PRs earlier that morning, before stage 2 (record 18), read 0.832, 0.8566, 0.859 and 0.8361, so the shortfall predates stage 2,
which changed no prompt, model or summary path.

## Founder actions this record needs

1. **Durable tasks (rollout owner, unchanged):** the post-deploy checks in `docs/DEPLOYMENT.md`.
2. **Custody step A (optional, no deadline; unchanged).**
3. **Squash default (optional; unchanged from record 18):** "Default to pull request title and description".

Nothing for D3 remains with the founder. The first Monday with the whole fleet pinned and backfill-facts at 07:30 is 2026-10-12.
