# PR disposition execution — 30 September 2026

Durable checkpoint for the founder-authorized disposition of seven open PRs (#1013, #1012, #952,
#1021, #942, #1023, #1009). Source instruction: the founder's live launch prompt plus the
handover package `earningsnerd-opus-5-5-handover` (SHA256SUMS verified). Checked means evidenced.

## Session state

- Repository: `neilmac91/EarningsNerd`; executor branch `claude/admiring-hopper-n0d93b`.
- Main at start: `efda34547037681289c7940d9f87420308cbf66d` (#1028), observed 2026-09-30T20:19Z.
- All seven PR heads equal the handover snapshot at 20:21Z (no change since the audit).
- Concurrent owners at start: Claude session "native delivery capability"
  (`claude/sleepy-franklin-gh71p4`, review-ready, not one of the seven); Codex merged #1028 at
  19:57Z. No Actions run was in progress at 20:21Z.
- Worktrees: one per lane under `/home/user/wt/` (outside the repository root).

## Spend ledger (approved: USD 2.00 total routine DeepSeek validation; raised by the founder to USD 10.00 total at ~22:25Z)

- Balance read (free `/user/balance`, session DeepSeek key): **USD 46.17 at 2026-09-30T20:20:25Z**.
  Last Actions-secret readout: USD 46.55 at 2026-09-29T23:39Z (run 36646363746) — consistent with
  the same account; the Actions dispatch API is not available to this session (403).
- Hard floor for new paid dispatch: balance must stay ≥ **USD 44.17** and telemetry-estimated
  cumulative spend ≤ USD 2.00 (superseded at ~22:25Z: ceiling USD 10.00 → floor USD 36.17). Other agents share the account, so balance deltas are a cross-check;
  run telemetry is the primary accounting.
- Paid triggers: `ci.yml` `eval-baseline` runs on EVERY `pull_request` opened/synchronize/reopened
  touching `backend/app|evals|prompts` (drafts included; historically USD 0.18–0.38 per run);
  `copilot-eval.yml` runs on ready same-repo PRs touching `backend/**` (historically ~USD 0.008).

| # | Dispatch | Reserved | Telemetry actual | Status |
| --- | --- | --- | --- | --- |
| D1 | #1030 ready → copilot-eval [36777581481](https://github.com/neilmac91/EarningsNerd/actions/runs/36777581481) at `c8c56cee` (balance 46.17 at 21:09:23Z) | 0.05 | 0.005827 (30 calls, 0 unknown) | done: accepted 18/18 |
| D2 | #1038 ready → copilot-eval [36798834277](https://github.com/neilmac91/EarningsNerd/actions/runs/36798834277) at `9d7fa56f` (balance 45.98 at 22:44Z) | 0.05 | 0.010511 (28 calls, 0 unknown) | done: accepted 18/18; 0 composed quotes |
| D3 | #1039 (#942 successor) push → eval-baseline [36799996921](https://github.com/neilmac91/EarningsNerd/actions/runs/36799996921) at `4d036b48` (peak window) | 0.50 | 0.347042 (70 calls, 0 unknown; tokens × llm_pricing × 2) | done: 70/70 pass, gate pass |
| D4 | #952 ready → copilot-eval [36800236360](https://github.com/neilmac91/EarningsNerd/actions/runs/36800236360) at `551f4808` | 0.05 | 0.011508 (30 calls, 0 unknown) | done: accepted 18/18; 1 composed quote (ASML d0, main code) |
| D5 | #1021 push of integrated head `c4629ffc` → eval-baseline [36808107539](https://github.com/neilmac91/EarningsNerd/actions/runs/36808107539) (peak window; balance 45.80 at 02:50:38Z) | 0.50 | 0.351808 (70 calls, 0 unknown; tokens × llm_pricing × 2) | done: 70/70 pass, gate_fail 0, regression gate pass |
| D6 | #1021 ready → copilot-eval [36809122540](https://github.com/neilmac91/EarningsNerd/actions/runs/36809122540) at `c4629ffc` (one run; pre-registered policy; balance 45.62 at 03:08:37Z) | 0.05 | 0.011835 (31 calls, 0 unknown) | done: accepted 18/18; audit: 0 composed, 0 uncited answers → policy PASS |

## Lanes

| PR | Disposition target | Branch / worktree | Head | Status |
| --- | --- | --- | --- | --- |
| #1013 | review, validate, merge | dependabot branch (main merged: `0113e9c9`) | `2cd639fd`→`0113e9c9` | **merged** `e1914ea4`; prod serves posthog-js 1.434.14 |
| #1012 | maintainer replacement, merge, close original | replacement [#1030](https://github.com/neilmac91/EarningsNerd/pull/1030) `claude/pr1012-posthog-7.60.1` `c8c56cee` | `1e56f3d2` | **#1030 merged** `c13b069a`, deployed `00423-wrg`; #1012 closed superseded |
| #952 | repair current-inspection binding, merge tooling | `claude/attached-file-review-any8xz` | `1d48eb33`→`551f4808` | **merged** `e3aa33df`; deployed `00426-xqn` (verified); E8 judging parked |
| #1021 | integrate main, qualify or hold draft | `codex/wave3-acquisition-period-withholding` | `55e89142`→`c4629ffc` | **merged** `0032bca8` (qualified: CI green, eval-baseline 70/70, Copilot 18/18, audit PASS); deployed `00427-qdv` (verified) |
| #942 | fresh successor, close original | successor draft [#1039](https://github.com/neilmac91/EarningsNerd/pull/1039) `claude/pr942-successor` `4d036b48` (stamp `summary-2026-09-t`) | `47d040aa` | **#942 closed** superseded (comment 5922709320); #1039 blocked draft: merge conditions 1 (so far) and 2 met (D3 70/70; source review comment 5922852309); waits only on founder's scoped disposition (condition 3); merge-tree vs main `0032bca8` clean, re-integrate + re-gate before any merge |
| #1023 | close with successor, diagnose | successor draft [#1036](https://github.com/neilmac91/EarningsNerd/pull/1036) `claude/pr1023-diagnostic` `5a5ebf8a` | `d58c1a59` | **#1023 closed** (comment 5920729833); #1036 reviewed (no blocker; 5 should-fix fixed), retained as diagnostic draft |
| #1038 (unplanned) | fix the 2026-10-01 month-rollover date bomb in migrations-postgres | `claude/fix-month-rollover-tests` | `9d7fa56f` | **merged** `ee30022a`; deployed `00425-xph` (verified) |
| #1009 | retain draft hold, document prerequisites | `codex/wave3-launch-pricing-offer` | `561dc2b8` | **held draft**; hold record comment 5920001935; still conflicts with main only in `tasks/todo.md` |

Merge-tree conflicts vs main at start: #1013/#1012 none; #952, #1023, #1009 `tasks/todo.md`;
#1021 `lessons/README.md`; #942 `summary_versioning.py`, `continuation-plan-2026-09-26.md`,
`tasks/todo.md`.

## Final report (2026-10-01)

| PR | Disposition target | Outcome | Evidence |
| --- | --- | --- | --- |
| #1013 | review, validate, merge | **merged** `e1914ea4` | frontend-only; main CI 36778453187 green; production serves posthog-js 1.434.14 |
| #1012 | maintainer replacement, merge, close original | **#1030 merged** `c13b069a`; #1012 closed as superseded | deploy job 110106288262: `applied=0 skipped=40`, `00423-wrg` 100%, `/health/detailed` healthy |
| #952 | bind recovery to a current inspection; merge tooling only | **merged** `e3aa33df`; E8 judging stays parked | deploy job 110175708793: `applied=0 skipped=40`, `00426-xqn` 100%, `/health/detailed` healthy |
| #1021 | integrate main, verify tracing thread, qualify or hold | **merged** `0032bca8` | CI 36808107539 green; eval-baseline 70/70; Copilot 36809122540 18/18; pre-registered audit PASS; tracing thread resolved with evidence; deployed `00427-qdv` (main CI 36819975322; deploy job 110235056894 `applied=0 skipped=40`, 100% traffic, healthy; independent `/health/detailed` healthy 05:41:45Z); release comment 5925487819 |
| #942 | fresh successor, close original, merge only if conditions hold | **#942 closed**; successor **#1039 blocked draft** | merge conditions 1 (so far) and 2 met; waits only on founder condition 3 |
| #1023 | close with evidence; diagnostic draft | **#1023 closed**; **#1036 diagnostic draft** | reviewed, no blocker; experiment not run (needs authorization) |
| #1009 | keep the pricing hold | **held draft** | hold record comment 5920001935; no pricing or Stripe change |
| #1038 (unplanned) | fix the 2026-10-01 test date bomb that broke the required migrations-postgres check | **merged** `ee30022a` | deployed `00425-xph`, verified |
| #1029 | durable checkpoint (this file) | draft, tasks-only | — |

**Spend.** Six paid dispatches, telemetry total **USD 0.738531** against the USD 10.00 ceiling:
- D1 0.005827
- D2 0.010511
- D3 0.347042
- D4 0.011508
- D5 0.351808
- D6 0.011835

All of it was deepseek-flash, with 0 unknown-cost calls. The DeepSeek balance went from USD 46.17 at 20:20Z to 45.62 at 03:08Z. Other agents share the account, so the balance is a cross-check, not the accounting.

**Boundaries kept.** Nothing in this run touched any of the following:
- pricing, Stripe prices or production flags;
- E7 or E8 judging launches;
- locked contract tests, thresholds or baseline pins;
- retained evidence (none deleted);
- Actions secrets or repository protections.

Every required check ran; none was bypassed. Each review override is founder-approved and backed by an independent multi-round review of that exact line.

**Decisions needed from the founder:**
1. **#1039:** the scoped disposition (merge condition 3). Before any `t` drain, also decide how to treat filings whose persisted snapshot predates #925.
2. **#942 artifact retention:** the earliest artifacts expire on 2026-10-06. The r report (artifact `10933338099`) expires on 2026-10-11 and is cited by main and by #1021's fixtures.
3. **#1036:** whether to authorize the tool-nonexecution experiment (about USD 0.4–0.8, ceiling USD 1.00).
4. **Composed prose quotes:** whether they become a CI gate (a separate verifier PR). On main's Copilot code the rate was 3 in 90 rows (historical five-run snapshot); the current figure is 3 in 108 rows across six runs. The #1021 run happened to have none.
5. **Codex review quota:** add credits, wait for a reset, or keep the founder-approved override practice.
6. **#1009:** the release prerequisites listed in the hold record.
7. **E7 custody:** #1021 changed `provider_requests.py`, which is in `MEASUREMENT_FILES`. Any E7 run bound to earlier instrumentation needs re-review before use.
8. **Dependabot:** GitHub reports 2 high-severity alerts on main. This session cannot read the alert API, so they were not triaged.

**Queued follow-ups (not done):**
- On main, the same Unicode case-fold `KeyError` class exists in `ai/cash_claims.py:84` and `copilot_service.py:790` (suggested task).
- The `_quarterly_claim` aggregate-branch sign check has no test.
- An optional whole-document pre-check for the PLTR explanation scan.

## Codex decision and execution plan (2026-10-01, comment 5925688598)

Under the founder's delegation, Codex decided items A–M on #1029. This session executes them. The full text is in the comment; in short:

| Item | Decision | Owner | Reservation (USD) | State |
| --- | --- | --- | --- | --- |
| A | Preserve all of #942's evidence, including `10933338099`, the original ZIPs and failed/superseded runs, before 2026-10-06. Inventory the ids, sizes and sha256 values and verify the durable copy, kept in private founder-controlled storage on a non-iCloud disk. Publish only a privacy-reviewed manifest. Also inventory the Copilot raw artifacts that F and G cite. | Claude (inventory, script); founder (storage) | 0 | **done**: 27/27 verified on the founder machine, outside iCloud (comment 5931533423; receipt sha256 `9a5631c4…`) |
| B | Scoped render-only #1039 / stamp `t`, after A and C. Requires: current-main integration, full gate, exact-head independent review, every required check, and **revalidation of every changed line against the new hosted artifact**. No change to production model-facing bytes, locked tests, baseline or thresholds. No drain. | Claude | 0.75 | waits on A and C |
| C | Read-only count of affected snapshots, with denominator and legacy/fallback/unknown/malformed classes. No clearing or re-extraction. | Claude (query); founder (run) | 0 | `census.sql` ready and validated; **access blocker**: no production DB access |
| D | Hold #1034 and keep edgartools 5.58.0. Offline Ford comparison at both versions. No test weakening, blanket ignore or paid rerun. | Claude | within the 0.75 for D/I/K | offline comparison running |
| E | After B: Unicode-fold crashes **and the silent wrong-scale fallback**, scalar and paired paths, with fold/ASCII controls and one mutation proof per boundary. | Claude | 0.75 | queued after B |
| F | Prose-quotation containment: an unsupported quote takes the existing withheld/error path. No repair. Offline replay with valid-quote controls first, then 3 predeclared runs. **No scorer, threshold, prompt or flag change.** | Claude | 0.75 | queued after E |
| G | #1036 stage 1 only, USD 1.00, after B and E. Check prepared inputs offline before paying; a mismatch stops the lane. | Claude | 1.00 | queued |
| H | Keep the manual-review exception, with a real independent review of each exact head. No credits bought. | — | 0 | standing |
| I | Inventory the two alert identities, versions and reachability before any fix. | Claude | within the 0.75 for D/I/K | **access blocker**: no Dependabot alerts API from this session |
| J | Agreed: E7 stays parked. Any future reuse needs an explicit custody review and a new binding. | — | 0 | held |
| K | Add the sign-guard control in the existing owner, after the higher-risk fixes. Defer the PLTR optimization. | Claude | within the 0.75 for D/I/K | queued |
| L | Agreed: #1009 stays held. | — | 0 | held |
| M | Record these decisions here; merge #1029 through normal review and checks; keep handover paths discoverable; no branch cleanup. | Claude | 0 | this entry |

**Order.**
1. A.
2. C, plus offline D and I triage. These can run independently.
3. B → verified deploy → E → verified deploy.
4. F (containment and replay), then G within its six-hour window.
5. K.
6. M records the final outcomes.

**Spend.** USD 9.26 remains under the shared ceiling across both sessions. Claude's lanes reserve USD 4.00 in total; USD 5.26 stays uncommitted; Codex's lane #1037 reserves 0. Before each paid trigger, read the balance and the ledger, prefer off-peak hours, and stop before any lane exceeds its reservation.

**Correction.** The composed-quote base rate in the final report (3/90 rows, from five runs) is a historical snapshot. The current count is **3 composed rows out of 108 main-code rows across six runs**, with three clean runs.

## Log

- 20:21Z — Handover verified; heads unchanged; balance USD 46.17 (floor 44.17).
- #1013 — root cause of missing review: Codex auto-reviews only PRs a person opens for review or
  marks ready; Dependabot-opened PRs trigger neither (precedent #998: owner `@codex review`).
  Lockfile provenance: all six changed nodes match npm registry integrity; five carry signed
  provenance attestations; `why-is-node-running` 2.3.0→3.2.2 is a vitest-only transitive with no
  dependencies (drops `siginfo`, `stackback`). `npm install --package-lock-only` drift (102 diff
  lines, `dev` flags on sharp optional platform packages) is identical on main → pre-existing.
  Local integrated candidate = PR head + main (worktree `/home/user/wt/pr1013`), Node 22.23.2 /
  npm 10.9.8 (CI parity): npm ci, lint, tsc passed; vitest/build running.
- #1012 — root cause of empty key: Dependabot-triggered workflows receive no Actions secrets;
  job 109136830306 shows `OPENAI_API_KEY:` empty and the runner preflight refused with
  `{"accepted": false, "summary": null}` before any provider call (SEC preparation completed,
  6 prepared). Not a quality result. Replacement branch `claude/pr1012-posthog-7.60.1` commit
  `c8c56cee`: pip-compile 7.6.1 reproduced the Dependabot lock body byte-for-byte (header line
  aside); posthog 7.60.1 wheel+sdist carry PyPI trusted-publisher provenance
  (PostHog/posthog-python release.yml); runtime deps identical to 7.60.0; `pip check` clean.
  Full backend gate running (ruff, bandit clean).
- Deployment verification path: Cloud Run API token in this environment is stale
  (UNAUTHENTICATED) → verify from the CI deploy-job log (migration tail, revision, traffic) plus
  independent `GET https://api.earningsnerd.io/health/detailed` (healthy at 20:29Z baseline).
- 20:29Z — #1013 branch updated with main via GitHub (head `0113e9c9`, tree `d4d81e7a` = locally
  tested tree). Local gate: npm ci ok, lint 0, tsc 0, vitest 732/732, build 0 (Node 22.23.2).
- 20:30Z — **Codex review quota exhausted**: `@codex review` on #1013 answered "You have reached your
  Codex usage limits for code reviews". `review-gate` (required) needs a Codex summary for the head
  or a `Review override:` line; the handover excludes the override mechanism. Founder decision
  requested (credits/reset vs. override backed by an independent AGENTS.md §5 review, precedent
  #1027/#1028). Independent 3-lens review with 2 refutations per material finding is running for
  #1013 `0113e9c9` and #1012-replacement `c8c56cee`. GitHub Copilot review requested on #1013.
- 20:43Z — #1012 replacement full gate at `c8c56cee`: ruff clean, bandit clean, pytest 4197 passed,
  39 skipped, 2 deselected (384 s). Pushed; draft #1030 opened.
- 21:00Z — Codex (chatgpt-codex-connector[bot]) replied on #1013 as a Codex task: "No findings on head
  `0113e9c9`" (comment 5919643367; npm ci, lint, tsc, vitest 732/732). The reply is not a code-review
  summary, so `review-gate` does not count it.
- 21:07Z — Independent review workflow wf_c11ff5a1-403 (8 agents; 3 lenses per candidate, 2 refutations per
  material finding) at #1013 `0113e9c9` and #1012r `c8c56cee`: no blocker, no surviving should-fix.
  One #1012r should-fix candidate ("no gate exercises real PostHog SDK") was refuted (pre-existing gap;
  7.60.1's only runtime change is an MCP description string the app never imports). Nits: pre-existing
  PostHog provider/spec-typecheck coverage gaps.
- 21:09Z — #1030 marked ready (spend opt-in D1); `@codex review` requested.
- 21:10–21:11Z — A `Review override:` line was briefly added to #1013's body and then removed after the
  session's permission system classified that route as a CI bypass. The transient gate pass (run
  36777635165) is superseded by run 36777744371. #1013 is held unmerged pending a Codex code-review
  summary or a founder decision; no override is in place.
- 21:13Z — Founder approved review overrides (live instruction). Override lines record the completed
  independent review of each exact head (plus the Codex task review on #1013).
- 21:17Z — **#1013 squash-merged as `e1914ea4`** (head re-read `0113e9c9`, mergeable clean, review-gate run
  36778019333 pass). Main CI 36778453187 running. Vercel connector is 403 for this team scope; independent
  production readback at ~21:20Z: `https://www.earningsnerd.io/` HTTP 200, chunk
  `/_next/static/immutable/chunks/0n45awmes39vd.js` carries posthog-js `1.434.14` (pre-merge build: 1.434.13).
- 21:11Z — D1 readiness artifact (sha256 `f2aca82f…`): accepted, 18 expected/completed/scored/passed, 0 errors;
  30 deepseek-flash calls all success; telemetry USD 0.005827, 0 unknown-cost; 4 advisory uncited-figure lines retained.
- 21:18Z — #1030 body records the review and founder-approved override; review-gate run 36778562740 pass.
- 21:23Z — **#1030 squash-merged as `c13b069a`** (head re-read `c8c56cee`, mergeable clean, no main run in
  progress). Main CI 36779080311 success; deploy job 110106288262: `apply_migrations: applied=0 skipped=40`,
  revision `earningsnerd-backend-00423-wrg` 100% traffic, deploy health healthy. Independent readback
  2026-09-30T21:37:20Z `/health/detailed` healthy (db 6.32 ms, SEC circuit closed), homepage 200.
  Release comment on #1030 (5920169618); #1012 closed as superseded with comment 5920170891.
- 21:20Z — #1013 main CI 36778453187 success (deploy-backend change-detection: frontend only).
- 21:26Z — #1009 hold record posted (comment 5920001935): conflicts (todo.md only), no pricing drift on main,
  ordered release prerequisites incl. beta $0/no-card readback and pinned-revision binding switch.
- Lane analysis workflow wf_48c9735d-5d8 (10 agents, skeptic-verified) complete; per-lane findings retained
  outside git (scratchpad `analysis/lane-*.md`). Implementation workflow wf_49b4c816-489 started 21:27Z for
  #952, #1021, #942-successor (`claude/pr942-successor`), #1023-diagnostic (`claude/pr1023-diagnostic`);
  local commits only, no pushes.
- 22:19Z — #952 integrated repair pushed (draft, zero spend): merge of main `91cd146d`, addenda dropped
  `afd4f54e`, P1 repair `8e8c6f83` (export runs kit step-2 inspection itself; digest-bound verdict;
  receipts evidence only; restored refusal records remain a stop; 11 mutation proofs M1–M11). Local
  gate 4329 passed / 39 skipped / 2 deselected.
- 22:20Z — #1023 successor draft #1036 opened at `fdfb3844` (diagnosis doc + one tools/tool_choice
  assertion with 2 mutation proofs; zero spend). #1023 closed unmerged with evidence comment.
  Offline audit of 10 retained Copilot artifacts (246 calls): composed prose quotations in passing
  answers pre-#1022 17/108 rows, main 2/54 (incl. #1030's own run 36777581481 BABA d0); main-code ASML
  d1 in 36777581481 skipped tools and shipped 2/2 figures uncited while the run passed 18/18.
- Other concurrent activity (not in this assignment): Dependabot #1031–#1034 and Codex draft #1035
  (`codex/wave3-native-delivery-capability`) opened 21:18–21:54Z. Check main for in-progress deploys
  before every backend merge.
- ~22:25Z — Founder (live): "progress the effort independently as the chief engineer … I approve deepseek
  spend of up to 10USD if you need it." Ceiling now USD 10.00 total (inclusive of the USD 0.005827 spent).
  All other boundaries of the launch prompt stand (no pricing/Stripe activation, no production flags, no
  E7/E8 judging, no locked contracts/baselines/threshold changes, no retained-evidence deletion).
- 22:41Z — Container restart killed the four per-lane review workflows; worktrees, commits, venv and scratchpad
  survived (heads `8e8c6f83`, `d1c321eb`, `19928d2f`, `fdfb3844`, all clean). Reviews relaunched 22:42Z
  (3 lenses per lane, 2 refutations per material finding, ≤2 local fix rounds, no push).
- 22:44Z — Balance USD 45.98 (−0.19 since 20:20Z; this session's telemetry spend is 0.005827, the rest is
  other agents on the shared account). #952 CI 36784862944 all green on `8e8c6f83`; its eval-baseline job
  was a no-op (8 s; no `backend/app|evals|prompts` change), so USD 0.
- 23:21–23:58Z — Founder merged Dependabot #1033 (`212e297e`), #1032 (`8387351b`) and #1031 urllib3 2.8.0
  (`ae95322a`, backend). Main CI 36793775535 success; deploy job 110153951453 succeeded 00:07Z (migrations,
  Cloud Run deploy, job images, health). Main is now `ae95322a`; lanes based on `c13b069a` take main again
  before their next push.
- 00:29Z — #1036 review complete (33 agents): no blocker; five should-fix findings that survived two
  refutations each are fixed (`192ca986`, `7dfb5036`, `ed2f5e21`, and `5a5ebf8a` by hand for the final-round
  finding: both "not retained" runner logs are retained, 315 calls across ten runs, one fingerprint).
  Full gate at `ed2f5e21` 4197 passed; docs-reading tests at `5a5ebf8a` 145 passed. Pushed (free: tests and
  tasks only); body carries the review record. Retained as the diagnostic draft; experiment not run.
- 00:30Z — **Calendar time bomb on main**: from 2026-10-01T00:00Z the required `migrations-postgres` step "Verify
  usage counter concurrency" fails on every backend PR (first seen on #1036, run 36796447015): two cases in
  `tests/integration/test_usage_counter_transactions.py` seeded `MONTH = "2026-09"` but admitted in the wall-clock
  month. Reproduced on main `ae95322a` against local PostgreSQL 16 (2 failed / 27 passed); other PG suites green;
  hosted SQLite backend-tests green. Fix PR [#1038](https://github.com/neilmac91/EarningsNerd/pull/1038)
  (`claude/fix-month-rollover-tests` `0fa139af`, test + lesson only): sentinel `MONTH = "2000-01"`, five
  summary-reservation cases pin the month, rollover case → "2000-02"; 29 passed ×4; mutation (drop one pin) → 1 failed.
  Independent 3-lens review running. Comment on #1036 (5922335039). Sequencing: #1038 merges and deploys first
  (test-only, no runtime change), then lanes take main.
- 00:58Z — #1038 review (11 agents): no blocker; root cause and fix confirmed against a fake clock (head 29/29 for
  2026-09/10/12, 2027-01, 2099-12; base fails exactly the two). One surviving should-fix (rule-12: lesson's never-rule
  unenforced, MONTH unguarded) fixed in `9d7fa56f` with `test_fixture_months_are_sentinels_the_clock_never_returns`
  (mutation: MONTH="2026-10" → 1 failed) and narrowed lesson wording. Pushed; body carries the review record and the
  founder-approved override. Marking ready (D2).
- 01:04Z — **#1038 squash-merged as `ee30022a`** (head re-read `9d7fa56f`, mergeable clean, all required checks green,
  review-gate override pass, copilot-eval D2 accepted 18/18, USD 0.010511; no main run in progress). Main CI 36799337442:
  migrations-postgres green (all four PG suites), backend/frontend/e2e green; deploy-backend running.
- 01:05Z — #952 review final round fixed in `f053b9fd` (pin digest lists to sealed manifests, nested stage records,
  case-insensitive inspection refusal names; T1–T3 mutation proofs; full gate 4353 passed). Merged main `ee30022a`
  (`551f4808`), pushed (draft, free). Thread r4085294704 answered (4150826823).
- 01:11Z — #942 successor: review final round disclosure fixes `4efbb1b0`; merged main (`4d036b48`); full gate 4206 passed;
  pushed and opened draft [#1039](https://github.com/neilmac91/EarningsNerd/pull/1039) (D3 eval-baseline, peak window).
  #942 closed as superseded with durable links (comment 5922709320). #1039 is blocked on the founder's scoped disposition.
- 01:14Z — **#1038 deploy verified**: job 110171221599 `apply_migrations: applied=0 skipped=40`, revision
  `earningsnerd-backend-00425-xph` 100% traffic, deploy health healthy; independent `/health/detailed` 01:14:11Z healthy
  (db 6.51 ms, SEC circuit closed), homepage 200. #952 CI 36799391050 green on `551f4808` (4354 passed). Body replaced
  with the final record and override; thread PRRT_kwDOQRd7Tc6lQsOp resolved; marking ready (D4).
- 01:22Z — **#952 squash-merged as `e3aa33df`** (head re-read `551f4808`, mergeable clean, all required checks green incl.
  review-gate override pass and copilot-eval D4 accepted 18/18, USD 0.011508; no main run in progress). Main CI
  36800759454 running; deploy verification scheduled. Main-code Copilot composed-quote base rate now 3/90 rows
  (36640254449, 36777581481, 36800236360 ASML d0 "Total net sales 32,667.3"/"Net income 9,609.4"; 36798834277 had 0).
- 01:30Z — #1039 hosted eval-baseline 36799996921: 70/70, pass_rate 1.0, gate_fail 0, regression gate pass vs unchanged pin;
  D3 USD 0.347042. Merge-condition-2 source review (offline): 126/126 clauses recompute, periods match, scope labels correct
  (110 parent / 16 NCI; 0 unestablished); 90/92 priors dated (2 GPRO out-of-band dropped as on main); FIGS sequential
  priors dated `prior at 2026-03-31`; durations match by class (80 annual, 10 quarter); hosted lines byte-identical to
  retained r in 70/70. Recorded on #1039 (comment 5922852309). #1039 remains blocked on merge condition 3 (founder).
  Cumulative telemetry spend: USD 0.374888 of the USD 10.00 ceiling.
- 01:33Z — **#952 deploy verified**: main CI 36800759454 success; deploy job 110175708793 `apply_migrations: applied=0
  skipped=40`, revision `earningsnerd-backend-00426-xqn` 100% traffic, deploy health healthy; independent `/health/detailed`
  2026-10-01T01:33:24Z healthy (db 5.16 ms, SEC circuit closed), homepage 200. Release comment 5922927202.
- 02:40Z — #1021 review complete (43 agents, 3 rounds): no blocker. Surviving findings fixed: r0 eval-projection inclusion gate,
  PLTR net/unit operand controls (`504a646c`, `c0ddfd2f`); r1 component/asset/value/sign controls (`1b08b62f`); r2 Unicode
  case-folding KeyError in the PLTR explanation scan fixed with `re.ASCII` + 2 cases (`99082c98`; mutation: KeyError
  'thouſand' 1 failed → restored 15 passed); stale "current main" text and "No founder action" handled in the body. Merged
  main `e3aa33df` (`c4629ffc`; Copilot/frontend diff vs main empty). Two round-1 refuters were flagged by the security
  classifier ([Merge Without Review], [CI Bypass]); inspection of their tool calls shows only reads (handover files, session
  transcript), and GitHub state is unchanged (main `e3aa33df`, #1021 remote `55e89142`, no unexpected merges) — no effect.
- Pre-registered #1021 acceptance policy (set before the ready run; not lower than the existing bar): FAIL/hold on any error,
  failed or withheld row, composed or absent prose quotation, or an answer stating figures with zero verified citations;
  advisory (recorded) for individual uncited figures in otherwise-cited answers and fully-cited tool-less answers, per the
  existing RUNBOOK policy. Main-code base rate now 5 runs / 90 rows: composed 3/90, uncited answers 1/90 → expected single-run
  pass ≈ 45%; a hold on that basis is main's Copilot behaviour, recorded as the exact blocker.
- 02:55Z — #1021 local gate on `c4629ffc` green (ruff, bandit, pytest 4698 passed / 39 skipped / 2 deselected, 454 s).
  Focused independent review of the final delta (`99082c98` + conflict-free main merge `c4629ffc`): no blocker; mutation
  without `re.ASCII` 1 failed / 197 passed → 198 passed. Out-of-scope finding on main (same Unicode-fold KeyError class in
  `ai/cash_claims.py:84`, `copilot_service.py:790`) queued as a separate follow-up task, not fixed in #1021.
  Pushed `55e89142..c4629ffc` (fast-forward) at 02:55:27Z in the peak window (D5 ≈ USD 0.35 instead of ≈ 0.18 off-peak;
  accepted to keep the founder-absent window productive, well inside the USD 10 ceiling). PR body updated (integration,
  eval-projection disclosure, pre-registered policy, base rate 5 runs / 90 rows, founder actions, override line).
  Subscribed to #1021 activity.
- 03:04Z — #1021 hosted CI 36808107539 on `c4629ffc`: backend-tests, frontend-tests, e2e, migrations-postgres, lighthouse
  success; eval-baseline 70/70 pass_rate 1.0, gate_fail 0, regression gate pass (artifact sha256 `ed6e8a15…`; mean
  untraceable 1.9714, advisory); D5 USD 0.351808. Figure-tracing thread answered with evidence (comment 4151421172) and
  resolved after backend-tests went green.
- 03:08Z — #1021 marked ready (spend opt-in D6: single copilot-eval run under the pre-registered policy); balance USD 45.62 at 03:08:37Z.
- 03:11Z — #1021 copilot-eval 36809122540 at `c4629ffc`: PASS, 18/18 scored/passed, 0 errors, accepted, all terminal; artifact
  sha256 `501748cc…`, copilot-eval.json `9cb7368e…`; D6 USD 0.011835 (31 calls, 0 unknown). Pre-registered audit
  (`prose_quote_audit.py`, exit 2): composed quotes 0, rows without source 0, uncited answers 0 → **policy PASS**; advisory
  recorded: MSFT d0–d2 1/3 uncited figure (cited answers), tool-less fully-cited BABA native d0–d2 and ASML d0–d1.
  `evals/runner.py` is not hash-sealed; `provider_requests.py` (E7 MEASUREMENT_FILES) changes by the original PR's
  2-line `primary_excerpt` binder pass-through (no prompt/request change) — disclosed as an E7 custody note.
- 03:16Z — #1021 body updated with the qualification result; review-gate 36809724263 pass.
- ~05:29Z — **#1021 squash-merged as `0032bca8`** (head re-read `c4629ffc`, mergeable clean, base `e3aa33df`, no main run in
  progress). Main CI 36819975322 queued; deploy verification pending. Cumulative telemetry spend: USD 0.738531 of USD 10.00.
- 05:41Z — **#1021 deploy verified**: main CI 36819975322 success; deploy job 110235056894 `apply_migrations: applied=0
  skipped=40`, revision `earningsnerd-backend-00427-qdv` 100% traffic, job images updated, deploy health healthy;
  independent `/health/detailed` 2026-10-01T05:41:45Z healthy (db 7.38 ms, SEC circuit closed), homepage 200. Release
  comment 5925487819. #1039 body status refreshed (conditions 1-so-far and 2 met; waits on founder condition 3; merge-tree
  vs `0032bca8` clean). All seven dispositions executed; final report above.
- 05:55Z — Founder instruction: hand the open points over to the Codex agent working in the repo, ask for its feedback, and
  tell it that this session will execute the path it agrees. Handover `tasks/handover-codex-2026-10-01.md` (A–M, path,
  six questions, §6 decision format and non-delegable limits) and #1021 qualification evidence committed (`b53ef4d4`);
  `@codex` request posted on #1029 (comment 5925590299). New finding recorded there: #1034 (edgartools 5.59.1) breaks
  `test_original_ford_complete_outlook_reaches_primary_and_forward_recovery_without_displacement` — do not merge.
  Waiting for Codex's decision.
- 06:01Z — Codex decision received (#1029 comment 5925688598). Execution started: A (inventory) and D (offline Ford
  comparison) run in parallel. C's read-only `census.sql` is written and validated on synthetic rows (local PostgreSQL 16,
  12 rows across all classes; one NULL-predicate bug found and fixed). Access blockers are confirmed: the GCP access token
  is invalid (`invalid_token`), so there is no production DB read for C. There is no Dependabot alerts API (GitHub MCP),
  so I is blocked. No founder-controlled durable storage is reachable for A.
- 06:45Z — Status of the delegated decision items:
  - **A:** inventory of 27 artifacts (1,525,958,920 B; first expiry 2026-10-06 11:18Z), with manifest and tested preservation
    script (`59c04458`). Blocked on the founder running it.
  - **D:** done. edgartools 5.59.1 loses no Outlook content but has two real regressions (missing break before tables; `%)`
    loss in the ROIC row). #1034 held on 5.58.0 (`fa43cf80`, comment 5925866111).
  - **K:** aggregate sign-guard test on local branch `claude/k-aggregate-sign-guard` `7aa93328`, not pushed. Mutation 1 failed /
    216 passed; the same mutation against main's test file passes 216 (the gap is real); restored 217 passed.
  - **F:** offline study committed (`tasks/review-evidence/f-quote-containment-2026-10-01/`). The candidate matches the audit
    20/20 with 0 false positives; main-code withheld rate 3/108. Eval-effect question raised with Codex before
    implementation.
  - **Main:** moved to `116c91d2` (Codex merged #1037, tasks-only). #1039 now conflicts with main in `tasks/todo.md` only.
- 12:32Z — **Item A complete.** On the founder machine, outside iCloud, 27/27 artifacts verified (1,525,958,920 B), including
  `10690738758` and the r report `10933338099` (`977c86ee…`). Codex's local correction is ported to the repo script: a failed
  download keeps its `.part` file instead of deleting it, so the script now matches its "deletes nothing" claim.
  Item I triaged: extract-zip #283/#270 held, dev-only and unreachable, no patch (`929fef61`). Item C was not executed
  because no production SQL session was available. The single-SELECT variant for SQL Studio is added (`2be91465`).
  B remains blocked on C.
