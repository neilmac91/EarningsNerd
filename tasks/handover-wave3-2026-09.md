# Handover — wave 3, September 2026 (for the GPT-6 Astra session)

Written 2026-09-05 by the chief engineer after reviewing [PR #705](https://github.com/neilmac91/EarningsNerd/pull/705)
and the standalone wave-2 writeup. Companions: [wave-2 handover](handover-wave2-2026-09.md)
(operating procedure §4, traps §5, founder list §6 — still valid), [evidence ledger](wave2-ledger-2026-09.md),
[active todo](todo.md), root `AGENTS.md` (how to operate; read it first). Rules are in `CLAUDE.md`.

## 0. Checkpoint and review verdict

Current entry checkpoint (2026-09-06): [#707](https://github.com/neilmac91/EarningsNerd/pull/707)
merged `a7ad8f85`; [#708](https://github.com/neilmac91/EarningsNerd/pull/708) merged `6414e5bd`.
W3-0 verification and W3-1 observation are complete.
[Describe run 33996220468](https://github.com/neilmac91/EarningsNerd/actions/runs/33996220468),
job 101387131600, read serving revision `00270-4k6` at 100% and the separate pregenerate job;
both images matched #704 source/defaults. The service calendar filter is true; pregenerate is
unset with verified default false. All other proposed guard pins match that observation.
The founder approved preserving service=true / pregenerate=false on 2026-09-06, with the
Settings default unchanged. W3-2 implementation is active; merge, deployment and effective-pin
verification are pending. The following original review checkpoint remains historical evidence.

| Item | Observed 2026-09-05 |
|---|---|
| Original #705 checkpoint | `eddcfbb7a08465cce20881562850ad570ca05c25` (#705 merge); [main CI 33990124298](https://github.com/neilmac91/EarningsNerd/actions/runs/33990124298) green, deploy correctly skipped (docs only) |
| Verified backend | #704 `123f99eac2b758f0dc7e2b9fcbc2a0a6bbf8146c`; [run 33988401306](https://github.com/neilmac91/EarningsNerd/actions/runs/33988401306) `applied=0 skipped=34`, revision `00270-4k6`, healthy |
| Verified frontend | #697 (Vercel). Vercel is on **Pro** since 2026-09-05; the daily deploy quota in #705's body no longer applies |
| Open PRs / issues at original review | none |
| Codex review of #705 | GitHub bot reviewed `c660e9a1`; three independent manual lenses covered final head `34350292`, whose tree exactly matches merged `eddcfbb7`. W3-0 adds a verification pass. |

**Verdict on #705 and the writeup: sound and honest.** Every merge SHA, run id, gate tail and
"not complete" boundary checks out against GitHub and the code. Discrepancies found, each with its
disposition:

| # | Finding (verified at `eddcfbb7`) | Disposition |
|---|---|---|
| D1 | The service `ci.yml` line 510 `--update-env-vars` omits `NOTABLE_FILINGS_ENABLED`, `AI_EVIDENCE_SNAP`, `AI_FIGURE_TRACE_GATE`, `AI_FORWARD_QUOTE_GATE`, `USE_STRUCTURED_OUTPUT`, `CALENDAR_INDEX_FILTER_ENABLED` and `USE_STATEMENT_FINANCIALS`. `USE_STRUCTURED_OUTPUT` and `USE_STATEMENT_FINANCIALS` are already explicit in the eval job, not the service deploy line. Settings defaults apply only when no environment override exists; effective production values require W3-1 observation. C6 deploy-pin visibility was unmet at that checkpoint. | W3-1 observed; W3-2 source pins prepared, deployment pending |
| D2 | `backend/evals/RUNBOOK.md` (mandatory before AI changes) never mentions `AI_FALLBACK_BASE_URL` / `AI_FALLBACK_MODEL` (#701). A configured fallback silently changes which model produced an eval result. `docs/CONFIGURATION.md` does document them. | W3-2 adds exports, measured metadata and pin refusal; verification pending |
| D3 | All seven `.claude/agents/engineering/*.md` contain obsolete stack guidance: Render/Firebase/Alembic/GPT-4, frontend Vite/React Router (`frontend-developer.md:14`), or async SQLAlchemy (`api-architect.md:181`). README "Stack truth" provides precedence but does not repair or machine-gate those files. | `AGENTS.md` §2 now; W3-5 |
| D4 | Both refresh runs in the complete available history (2026-08-01 and 2026-09-01) failed on old source `e8ea339f`, which explicitly selected Wikipedia and supplied no FMP input; the Nasdaq-100 parser found no usable constituents table. Both revisions lacked an issue step, so no failure issue is expected from them. The current FMP auto-selection/issue path has not yet run; `FMP_API_KEY` was absent from repository secret names at review, which does not establish historical secret state. The founder has since supplied it in GitHub `Production`; metadata is verified, environment binding/refresh evidence remain pending. Next cron 2026-10-01; age gate trips 2026-10-16. | W3-3 |
| D5 | No scheduled production smoke; `frontend/tests/e2e/prod-smoke.spec.ts` is opt-in via `SMOKE_BASE_URL`. This gap hid a seven-week frontend/backend skew earlier. | W3-4 |
| D6 | Stale docs: `CONTRIBUTING.md` Node 20.x; briefs pointer to old DEPLOYMENT.md lines; briefs "#687 this PR"; dashboard plan config line numbers. | Fixed in the PR that added this file |
| D7 | Advisory `ecdsa 0.19.2 / PYSEC-2026-1325` has no upstream fix; python-jose is its only direct dependency parent in the inspected environment. Four production modules import jose. Inspected default HS256 signing and explicit RS256 OAuth verification do not use the vulnerable private-key operations; the exact pinned local runtime selects cryptography backends. This is not proof about every deployed/configured path and does not remove the advisory. The locked auth contract test has no jose import; two non-locked test modules do. | W3-6 |
| D8 | Two stale remote branches with no PR: `claude/earnings-nerd-audit-plan-8iikp3`, `claude/earningsnerd-sections-review-prompt-aw2u7c`. | Founder OK, then delete |
| D9 | The GitHub bot did not re-review after `c660e9a1`; final manual correctness/rules/evidence reviews covered `34350292`, and its tree equals the merge. Do not conflate the bot checkpoint with missing manual review. | W3-0 verified |
| D10 | Vercel quota caveat is moot (Pro). | Recorded above |
| D11 | Deploy trigger nuance: `ci.yml` line 430 deploys on any `^backend/` diff, **including `backend/tests/`**. Every rule-12 gate test therefore deploys (a no-op rebuild) and counts against "one unverified backend deploy at a time". Only docs, workflow and frontend changes are deploy-free. | `AGENTS.md` §6; PR grouping §4 |

Open engineering residuals carried from wave 2 (confirmed in code): historical reconciliation-flag
audit/repair (`facts_service.py` ~line 725: reprocessing skips existing identities); 6-K
classifier (`prompt_loader.py` routes every 6-K to one prompt; `summary_pipeline.py` 6-K branch
~lines 362-490) and 6-K goldens; golden breadth (zero REIT/utility/6-K entries; BRK.B is
`verified: false`); evidence-snap arming (held on the readout); Notable flip (held on the founder
week); Analysis flag PR (held on founder warm-up); weekly anomalies C/MS/WFC/GS (held on
`INTERNAL_JOB_TOKEN`).

## 1. Session configuration (founder, when launching Codex)

- Model `gpt-6-astra` on the Responses API (tool calling requires it).
- `reasoning.effort`: `high` for review and merge decisions, `medium` for doc edits. `none` is
  not supported. Do not set `temperature`, `top_p` or `logprobs`.
- `prompt_cache_options.ttl: "30m"`; change effort mid-conversation with `configuration_update`
  items, not by editing the request-level setting.
- System prompt: point at `AGENTS.md`. State that founder instructions supersede skill and agent
  files, that the wave-3 *engineering* items are pre-authorized, and the mandate below.

**Mandate (founder, 2026-09-05):** engineering merges and deploys are authorized, same as wave 2.
Founder-only items (secrets, console, spend, legal, production data operations) stay held.
Decisions already recorded: the agent MAY dispatch `ops.yml describe-service`,
`refresh-index-membership.yml` and the new prod-smoke workflow itself (one honest "Universe refresh
failed" issue before the FMP key exists is accepted); the two non-locked auth-test edits in W3-6 are
pre-approved as a documented rule-6 exception.

Update 2026-09-06: preserve the observed service calendar filter true as an intentional override;
pregenerate remains false. `FMP_API_KEY` secret-name metadata is verified in GitHub `Production`,
without reading its value. W3-2 binds the existing refresh job to that environment; W3-3 dispatch
follows W3-2 verified deployment. The earlier optional keyless failure demonstration is superseded;
do not remove a supplied credential to manufacture a failure. Strong-judge dispatch remains held.

## 2. Founder prerequisites (do not do these yourself; keep them visible)

| Founder action | Unblocks | Evidence to retain |
|---|---|---|
| Add `ANTHROPIC_API_KEY` as an Actions secret, then dispatch `data-quality-weekly.yml` | W3-7 | The `weekly-judged-readout-<run>` artifact with `status != unavailable` and 24/24 scored; the emailed report |
| `FMP_API_KEY` supplied in GitHub `Production` (metadata verified; founder step done) | W3-3 after W3-2 environment binding/deployment | Successful refresh and reviewed auto-PR still pending |
| Create the `earningsnerd-notable-filings` Cloud Run job + Scheduler per `docs/DEPLOYMENT.md` §12; seed `--days 7`; review one full subsequent week; record retain/kill | W3-10 Notable | Execution ids, counts, the week's review notes |
| Read the effective Vercel `NEXT_PUBLIC_ENABLE_ANALYSIS`; run the companyfacts warm-up (`scripts/sync_companyfacts.py`) on the seeded cohort | W3-10 Analysis | Deployment id, cohort, success/error counts |
| Grant the deployer SA access to `INTERNAL_JOB_TOKEN`; run `backfill_filing_history.py --tickers C,MS,WFC,GS` | Weekly-report anomalies | Live report coverage evidence |
| Seed/SIC/pregeneration/drain (D4) | after W3-7 | Preview/apply counts, execution ids |
| Approve deletion of the two stale branches (D8) | — | — |
| Everything in [wave-2 handover §6](handover-wave2-2026-09.md#6-founder-only-items-outstanding-do-not-do-these-yourself-keep-them-visible) not listed here (Cloud SQL, alerts, Vercel/launch, legal, licence) | — | as listed there |

## 3. Work items, in order

Every item: goal, files, gate (rule 12), verification, done, held-until. Cite exact tails in the
PR body. Re-read every file and line named here against `main` before editing; line numbers were
verified on 2026-09-05 and drift.

### W3-0 — Verify the post-bot-review tail of #705 (completed)
Additional review on 2026-09-06 checked `git diff c660e9a1..eddcfbb7`: 13 task Markdown files,
43 valid local links/anchors, all 52 earlier archives unchanged, original §7 and earlier ledger
copy preserved, and no product/document contradiction found. `git diff 34350292..eddcfbb7` is
empty: the final tree already had three independent manual reviews. The GitHub bot checkpoint
was earlier. Record this distinction and the bounded #706 claim corrections in the correction
PR [#707](https://github.com/neilmac91/EarningsNerd/pull/707), merged `a7ad8f85`; W3-1 cites that evidence. No application tests or production operation were needed.

### W3-1 — Ops visibility (completed #708; workflow-only, no deploy)
- **Goal:** make the effective production values of every guard flag readable from the repo's own
  `describe-service` dispatch, so W3-2's pins are provably behaviour-neutral.
- **Files:** `.github/workflows/ops.yml` — the `allow` set (~line 167) adds
  `NOTABLE_FILINGS_ENABLED, AI_EVIDENCE_SNAP, AI_FIGURE_TRACE_GATE, AI_FORWARD_QUOTE_GATE,
  USE_STRUCTURED_OUTPUT, CALENDAR_INDEX_FILTER_ENABLED, REGISTRATION_MODE, AI_FALLBACK_MODEL,
  AI_FALLBACK_BASE_URL` (never `AI_FALLBACK_API_KEY` or any secret); the NOT-SET loop (~line 183)
  iterates the same tuple and prints each flag's `Settings` default.
- **Gate:** the assertion lands in W3-2's test module (a `backend/tests/` change deploys; keep this
  PR deploy-free).
- **Verification:** YAML parse; existing `test_ops_workflow_is_dispatch_only_and_sets_lock_timeout`
  in `test_migration_lock_safety.py` still passes; dispatch `describe-service`; paste the output.
- **Done:** each flag prints `<NOT SET -> Settings default applies (...)>` or its value. If any
  guard flag is hand-set `true` in the console, stop and report before W3-2. This check found the
  calendar service override; the founder approved preserving it, clearing the W3-2 entry boundary.
  Actual observation and image/default validation are recorded in §0 above.

### W3-2 — Flag visibility, eval-env pins, fail-loud structure (backend tests: deploys)
One PR; three gates; RUNBOOK and docs corrected in the same PR.

**(a) Prod flag pins.** `.github/workflows/ci.yml`: append to the service `--update-env-vars`
(~line 510) and the pregenerate job `--update-env-vars` (~line 522):
`NOTABLE_FILINGS_ENABLED=false, AI_EVIDENCE_SNAP=false, AI_FIGURE_TRACE_GATE=false,
AI_FORWARD_QUOTE_GATE=false, USE_STRUCTURED_OUTPUT=false, USE_STATEMENT_FINANCIALS=true`.
Set `CALENDAR_INDEX_FILTER_ENABLED=true` on the service and false on pregenerate; the service
also keeps `ENABLE_FPI_FILINGS=true, STREAM_SECTION_REVEAL=true, REGISTRATION_MODE=invite_only`.
The calendar split is the founder-approved intentional override, preserving W3-1 observed values;
Settings stays false. This does not activate the Calendar UI or change another job configuration.
Gate `backend/tests/unit/test_prod_flag_visibility.py`: load `ci.yml` (reuse the `_step` /
`_executable` helpers pattern from `test_migration_lock_safety.py`), regex `--update-env-vars=(\S+)`
on the "Deploy Cloud Run service" step, split into a dict; assert every key in `PROD_ENV_PINS` is
present with its exact value; **bidirectional**: each pinned bool equals
`Settings.model_fields[name].default` unless the name is in
`INTENTIONAL_PROD_OVERRIDES = {"ENABLE_FPI_FILINGS", "STREAM_SECTION_REVEAL", "REGISTRATION_MODE", "CALENDAR_INDEX_FILTER_ENABLED"}`
(a default flip in `config.py` without a deploy-line change fails, and vice versa); **pipeline
parity**: the pregenerate job step carries identical values for the AI subset (`AI_EVIDENCE_SNAP,
AI_FIGURE_TRACE_GATE, AI_FORWARD_QUOTE_GATE, USE_STRUCTURED_OUTPUT, USE_STATEMENT_FINANCIALS`) —
rule 1, same orchestrator. **Eval parity**: the `eval-baseline` job env in `ci.yml` (~lines 281-294)
and the generation env in `data-quality-weekly.yml` must carry the same AI-subset values as the
service line (today the eval job sets only `USE_STRUCTURED_OUTPUT`, `USE_STATEMENT_FINANCIALS`,
`STREAM_SECTION_REVEAL`; add `AI_EVIDENCE_SNAP`, `AI_FIGURE_TRACE_GATE`, `AI_FORWARD_QUOTE_GATE`
explicitly) — extend `test_ci_parity_and_bounded_repeat_measurement` in `test_eval_parity.py`
to compare the job env against the service pins rather than against literals. Also assert the
`ops.yml` `allow` set is a superset of `PROD_ENV_PINS` keys (W3-1's gate).
Mutation proofs: delete `NOTABLE_FILINGS_ENABLED=false` from line 510 → fail; set
`AI_EVIDENCE_SNAP: bool = True` in `config.py` → fail; restore.

**(b) Fallback provenance.** Add `AI_FALLBACK_MODEL: ''` and `AI_FALLBACK_BASE_URL: ''` to the
eval-baseline run env in `ci.yml` (~lines 281-294), `data-quality-weekly.yml` (~lines 53-68) and
`copilot-eval.yml`. `evals/runner.py` harness block (~line 295) records `fallback_model` and
`fallback_base_url`. `scripts/pin_baseline.py` `build_baseline` refuses when `harness["fallback_model"]`
or `harness["fallback_base_url"]` is missing or non-empty, and refuses when the harness guard values the runner already records
(`ai_evidence_snap`, `ai_figure_trace_gate`, `ai_forward_quote_gate`, `use_structured_output`,
`use_statement_financials`) disagree with the service pins parsed from `.github/workflows/ci.yml`
(new `ValueError`s alongside the existing provenance checks ~lines 51-63). A new pin must then
match the committed service guard configuration; effective production still needs deploy observation.
Gate: extend `test_ci_parity_and_bounded_repeat_measurement` (`test_eval_parity.py`) and
`test_weekly_workflow_preserves_failure_evidence_and_operational_report` (`test_eval_measurement.py`)
with `env["AI_FALLBACK_MODEL"] == ""` and `== ""` for the base URL; add a copilot-eval assertion
beside them; add `'fallback-configured'` to the `defect` parametrization in `test_eval_parity.py`
(~line 142). RUNBOOK: Step 1 env block gains `export AI_FALLBACK_MODEL=` / `export
AI_FALLBACK_BASE_URL=` with "leave empty for every eval and pin"; "Re-pinning the baseline" notes
the refusal. Mutation proof: set `AI_FALLBACK_MODEL: 'x'` in the weekly workflow → fail.

**(c) Fail-loud structure for scheduled workflows.** Gate
`backend/tests/unit/test_scheduled_workflows_fail_loud.py`: for `refresh-index-membership.yml`
(and, once W3-4 lands, `prod-smoke.yml`) assert a `schedule` cron exists, `permissions.issues ==
"write"`, the last step has `if: failure()`, its env has `GH_TOKEN`, and its executable text
contains `gh issue create` and `gh issue comment`. Parametrize over a `SCHEDULED_FAIL_LOUD`
tuple so W3-4 adds one entry, not one test. Mutation proof: remove `if: failure()` → fail.

**Docs in the same PR:** `docs/CONFIGURATION.md` (guard-flag rows: "pinned explicitly in the
`ci.yml` deploy env"), `docs/DEPLOYMENT.md` §12 flag paragraph, `tasks/dark-surfaces-rollout-2026-09.md`
Notable step, `tasks/handover-wave2-2026-09.md` WS-9 status sentence (explicit W3-2 source pins;
merge/deployment still pending until observed). Bind the refresh job to GitHub `Production` and
correct FMP instructions; secret metadata availability is not successful refresh evidence.
**Verification:** `cd backend && ruff check . && bandit -r app -ll && python -m pytest` (paste the
tail); the four named gates individually; after merge: `deploy-backend` green, `applied=0
skipped=34`, `/health/detailed` healthy, then `describe-service` shows every pin.
**Entry satisfied:** W3-1 output reviewed and the calendar split explicitly approved.
**Remaining:** source gates, three independent reviews, required CI, merge and verified deployment.

### W3-3 — Universe refresh (founder key, then engineering verification; auto-PR deploys)
- **Credential prerequisite supplied:** `FMP_API_KEY` exists in GitHub `Production` (metadata
  verified, value unread). After W3-2 environment binding and verified deployment, dispatch
  `refresh-index-membership.yml`. Preserve actual success/failure evidence; do not manufacture
  a keyless failure now that the founder supplied the key.
- **Successful refresh:** draft PR "Refresh index membership (S&P 500 / Nasdaq 100)"
  on `automation/refresh-index-membership`; review added/removed tickers; merge (deploys because
  `backend/app/data/` changed; verify per `AGENTS.md` §6); close the issue with the PR link.
- **Deadline:** before the 2026-10-01 cron and the 2026-10-16 age trip (`MAX_UNIVERSE_AGE_DAYS =
  100` in `backend/tests/unit/test_index_membership_service.py`, `generated_on` 2026-07-07).
- **Never** raise `MAX_UNIVERSE_AGE_DAYS`; CI going red on 10-16 is the designed escalation.

### W3-4 — Daily production smoke (workflow-only, no deploy)
- **File:** `.github/workflows/prod-smoke.yml`: `schedule: '23 6 * * *'` (clear of the 06:00
  Monday pregenerate, 08:00 monthly refresh and 13:00 Monday weekly crons) plus `workflow_dispatch`
  with input `filing_path`; `permissions: contents: read, issues: write`; `concurrency: prod-smoke`;
  `timeout-minutes: 15`. Steps: checkout; setup-node 22.23.2; `npm ci` in `frontend`; Chromium
  install with the same timeout-then-fallback as `ci.yml` (~lines 354-357); **API probe** copied
  from the deploy job's health step (~line 551: `curl -fsS https://api.earningsnerd.io/health/detailed`,
  fail on `"unhealthy"`); **frontend probe** `SMOKE_BASE_URL=https://earningsnerd.io
  SMOKE_FILING_PATH=${{ inputs.filing_path || vars.SMOKE_FILING_PATH || '/filing/3' }} npx playwright
  test prod-smoke`; upload `playwright-report` on failure; failure-issue step cloned from
  `refresh-index-membership.yml` (title `Production smoke failed <date>`, `startswith` search,
  comment on the existing issue).
- **Gate:** add `prod-smoke.yml` to `SCHEDULED_FAIL_LOUD` in `test_scheduled_workflows_fail_loud.py`
  (that edit is a `backend/tests/` change: land it with W3-2 if W3-4 is ready in time, otherwise
  accept one no-op deploy). Extend `frontend/tests/unit/nodeVersionLockstep.spec.ts` to read
  every `.github/workflows/*.yml`, not only `ci.yml`, so the new `node-version` pin is gated.
- **Done:** one dispatched green run; one deliberate red dispatch (`filing_path=/filing/does-not-exist`)
  opens the issue; close it. Tick the prod-smoke line in `tasks/todo.md` Phase 1.
- **Founder row:** set repo variable `SMOKE_FILING_PATH` when the live example filing id is known.

### W3-5 — Agent-file stack debt (backend test: deploys)
- **Goal:** the seven `.claude/agents/engineering/*.md` files stop teaching a stack that does not
  exist, and a gate keeps them honest.
- **Files:** replace each file's "Key Files" / platform / code-sample blocks with the truth table
  from `.claude/agents/README.md` "Stack truth (2026-09)" and pointers to real files
  (`docs/ARCHITECTURE.md`, `app/database.py`, `.github/workflows/ci.yml`). Delete the fake
  `render.yaml`, `firebase.json`, `alembic upgrade head`, `AsyncSession` and `/api/v1` samples.
  Rewrite README "Stack truth" preamble to say the engineering files are refreshed and gated.
- **Gate:** `backend/tests/unit/test_agent_files_stack_truth.py` walks `.claude/agents/**/*.md`;
  forbidden regex `Firebase|Firestore|Alembic|Celery|\bVite\b|React Router|GPT-4|GPT-3\.5|AsyncSession|create_async_engine|/api/v1|render\.yaml|on Render|Render dashboard|Deploy to Render`
  (platform phrases only, so "render the chart" cannot trip); `engineering/` must have zero hits;
  a frozen shrink-only allowlist covers the non-engineering files that still trip (use the
  `_assert_frozen_allowlist` two-way pattern from `test_migration_lock_safety.py`).
- **Mutation proof:** insert "Firebase Authentication" into `backend-developer.md` → fail; restore.
- **Verification:** full backend gate; deploy verification (no-op).

### W3-6 — Replace `python-jose` with PyJWT (backend: deploys) — approved, after W3-2 and W3-5
- **Why:** removes the unfixable `ecdsa` advisory from an auth-critical dependency. Low urgency;
  bounded blast radius (four modules).
- **Files:** `backend/requirements.in` `python-jose[cryptography]` → `PyJWT[crypto]>=2.10,<3`;
  recompile with the command documented at the top of `requirements.txt`; confirm `ecdsa`,
  `python-jose`, `rsa`, `pyasn1` drop out. Call sites: `app/routers/auth.py`, `app/routers/watchlist.py`,
  `app/services/waitlist_service.py`, `app/services/oauth_verify.py`. Diffs: `JWTError` →
  `jwt.PyJWTError`; `leeway` becomes a keyword argument; JWKS via `jwt.PyJWK(key).key` (PyJWT does
  not accept a JWK dict); keep explicit `kid` selection; confirm `sub` is always a string (PyJWT
  ≥ 2.10 rejects non-string `sub`) and that tokens carrying `aud` request it.
- **Locked tests (rule 6):** `test_auth_flow.py`, Stripe webhook, SSE contract and background
  characterization must be byte-identical — prove with `git diff --stat main -- <those files>`
  empty. **Pre-approved non-locked edits (founder, 2026-09-05):** `test_security_hardening_week7.py`
  (mint/decode helper switches library) and `test_apple_signin.py` (the "raw JWK dict reaches
  decode" assertion becomes "the `PyJWK` built from the kid-matched key reaches decode"). State
  the pre-approval in the PR body.
- **Gate:** `backend/tests/unit/test_jwt_library_allowlist.py` — AST walk of `backend/app`,
  `backend/scripts`, `backend/main.py`, `backend/tests` for `import jose` / `from jose`;
  `requirements.txt` contains no `python-jose` or `ecdsa` line.
- **Verification:** full backend gate; `pip-audit -r backend/requirements.txt` no longer lists
  PYSEC-2026-1325; deploy verification; no live OAuth smoke (existing tests only).

### W3-7 — Arm `AI_EVIDENCE_SNAP` after the first strong-judge readout (backend: deploys)
- **Held until** the founder's readout artifact exists with `status != unavailable` and 24/24
  scored (the bar `test_eval_measurement.py` enforces). Judge-off, simulated or unavailable output
  does not count.
- **Step 1 (engineering, then pause):** read the artifact; report the wrong-snap rate from the
  persisted `evidence_snap_audit` counters and the figure-trace advisory. **Pause for the arm
  decision** — this pause is legitimate; no threshold is on record.
- **Step 2 (after the decision):** in one PR set `AI_EVIDENCE_SNAP` to `true` in **all four** places
  that the W3-2 parity gate ties together: the service deploy line, the pregenerate job line, the
  `eval-baseline` job env, and `data-quality-weekly.yml`'s generation env (the readout should measure
  what users see; update `test_eval_measurement.py`'s `== "false"` assertion with it). Move the key
  into `INTENTIONAL_PROD_OVERRIDES` (config default stays `False`). The eval job must carry the flag
  or the re-pin measures with snapping off while production snaps — `pin_baseline.py` refuses that
  mismatch after W3-2, and the parity gate fails before it. Then, from that branch, dispatch the eval
  workflow with `eval_runs=3` and no limit (a listed re-pin trigger: RUNBOOK "Re-pinning the
  baseline", armed guard raises the citation dimension), confirm the report's
  `harness.ai_evidence_snap` is `true`, run `python scripts/pin_baseline.py`, and commit
  `baseline_scores.json` in the same PR.
- **Then founder:** drain via `POST /api/admin/summaries/refresh-stale` (`dry_run=true` first,
  bounded batches).

### W3-8 — Golden breadth, then the 6-K classifier (backend: deploys; each re-pins)
- **Order matters:** any golden-set change alters the golden SHA the pin binds, so it is itself a
  re-pin PR. Never have two open PRs carrying a re-pin; do W3-8a after W3-7's re-pin has merged
  (or if the readout slips more than a week, do W3-8a first and re-pin again at W3-7).
- **W3-8a breadth:** add one REIT, one utility, one insurer (hand-fill BRK.B per RUNBOOK Step 2 /
  "verified" rules) and two small caps to `backend/evals/golden_set.json`; verify each entry's
  five fields; run the RUNBOOK smoke on one entry before the full run
  (`lessons/test-smoke-model-runs-before-sweeps.md`); full 3-run measurement; pin; PR body carries
  the report id and tails.
- **W3-8b 6-K classifier:** routing today is a static map in `app/services/prompt_loader.py`
  (`"6-K" → 6k-analyst-agent.md / 6k-structured-agent.md`) with EX-99 grounding in
  `summary_pipeline.py`'s 6-K branch. Design: a deterministic pre-classifier over the EX-99 text
  (earnings / governance / press-release; keyword and XBRL-presence heuristics, no model call)
  that selects among three 6-K prompt variants, and records `raw_summary["sixk_class"]` for audit.
  6-K goldens have no XBRL facts, so the recall/precision scorers score zero: add a 6-K scorer
  contract (hand-filled `ground_truth` from the press release, judge-off) before adding entries,
  or the pin tool refuses the report. Gates: classifier unit test over fixture exhibits; eval gate
  PASS on the re-pinned set. Rule 1 (one orchestrator) and rule 2 (filing-only) apply unchanged.

### W3-9 — Historical reconciliation-flag audit/repair (backend: deploys; founder executes)
- **Goal:** a bounded, dry-run-by-default capability to re-evaluate reconciliation flags on
  existing fact identities, which ordinary backfill and `--force` freshness bypass never touch.
- **Files:** add `refresh_flags: bool = False` to the reprocess entry in
  `app/services/facts_service.py` (the comment "Reprocessing still skips existing identities; it
  does not refresh their flags" marks the site) so the default path is byte-identical;
  `backend/scripts/audit_reconciliation_flags.py` (docstring header per CLAUDE.md) prints
  would-change counts per filing by default; `--apply` updates flag columns only, no inserts or
  deletes; optional `--tickers`, `--limit`.
- **Gate:** unit test proving the default path still skips existing identities and that
  `refresh_flags=True` changes only flag columns on a persisted ORM fixture.
- **Done:** merged and deployed; founder executes on the `earningsnerd-backfill-facts` job image and
  retains counts. No production execution by the agent.

### W3-10 — Dark-surface flips (held on founder evidence)
- **Notable:** after the founder's job + seed + one full week review with a recorded retain
  decision, PR flips `NOTABLE_FILINGS_ENABLED=true` in `ci.yml` line 510 and updates the W3-2 pin
  table (that test edit makes the PR deploy). Verify the deploy ran, `GET /api/notable_filings?limit=8`
  is non-empty, and the homepage section renders in both themes after ISR.
- **Analysis:** after the founder records the effective Vercel value and the warm-up evidence, PR
  adds `NEXT_PUBLIC_ENABLE_ANALYSIS: "true"` to `frontend/vercel.json` `env`; full frontend gate;
  Playwright with no backend; both-theme preview; production Pro-account smoke.
- **Calendar and Insiders stay off.** Not authorized by this document.

### D8 — Stale branches (after founder OK)
`git push origin --delete claude/earnings-nerd-audit-plan-8iikp3 claude/earningsnerd-sections-review-prompt-aw2u7c`.

## 4. PR grouping and deploy sequencing

| Order | PR | Deploys | Notes |
|---|---|---|---|
| 1 | W3-1 ops.yml | no | dispatch and paste output |
| 2 | W3-2 gates + pins + RUNBOOK + docs | yes | first backend deploy; verify fully before 3 |
| 3 | W3-4 prod-smoke workflow (+ lockstep spec) | no | may open while 2 is deploying |
| 4 | W3-5 agent files + gate | yes | after 2 verified |
| 5 | W3-3 auto-PR merge | yes | whenever the key arrives; serialize with 4/6 |
| 6 | W3-6 PyJWT | yes | after 4 verified |
| 7+ | W3-7 → W3-8a → W3-8b → W3-9 → W3-10 | yes | each held on its prerequisite; one re-pin in flight at a time |

Docs-only and workflow-only PRs interleave freely. Any `backend/` diff, tests included, deploys.

## 5. Re-pin rule

Re-pin `backend/evals/baseline_scores.json` only on a listed RUNBOOK trigger (model/prompt change,
armed guard, golden-set change, extraction-library bump), never to make a quality change look
flat, and never with a configured fallback provider. At most one open PR carries a re-pin.

## 6. Out of scope for wave 3

Calendar activation (Alpha Vantage licence), Insiders, the deferred appendix-06 items listed at
the bottom of `tasks/todo.md`, every founder console/secret/spend/legal row, and any change to
the locked contract tests beyond the pre-approved W3-6 edits.
