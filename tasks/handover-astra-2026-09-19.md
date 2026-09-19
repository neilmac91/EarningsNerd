# Handover — 2026-09-19, chief engineer role to GPT-6 Astra

This is the authoritative state of EarningsNerd at the handover. Where it disagrees with an older
handover or with an unchecked row in `tasks/todo.md`, this file wins and the older text is history.
Every identifier below was read from GitHub, the Actions logs or the live service on 2026-09-19;
re-read GitHub `main` before acting, because the repository will have moved.

## 1. Where things stand

**Product and production.** The Cloud Run service `earningsnerd-backend` serves revision
`earningsnerd-backend-00367-t8t` at 100% (deployed by main CI run `35285580415` for #912,
`apply_migrations: applied=0 skipped=39`); `/health/detailed` is healthy for database, Redis
(disabled in production by design) and the SEC circuit. Later merges #913–#915 were documentation
and did not deploy. Generation runs on DeepSeek `deepseek-flash` with thinking off, under prompt
stamp `summary-2026-09-o`. Production AI flags, pinned in `.github/workflows/ci.yml` and last read
on the live service on 2026-09-17: `AI_EVIDENCE_SNAP=true`; `AI_ATTRIBUTION_GATE=false`;
`AI_ATTRIBUTION_VERIFY=false`; `AI_FORWARD_QUOTE_GATE=false`; `AI_FIGURE_TRACE_GATE=false`.

**Money.** DeepSeek balance USD 76.68, read by workflow run `35457885585` at 2026-09-19T17:22Z.
A full `eval-baseline` run (35 filings × 2) costs about USD 0.30.

**Open pull requests.** Dependabot #916 (soupsieve 2.8.4 → 2.9) and #917 (anyio 4.13.0 → 4.14.2).
Both pass backend tests and fail `copilot-eval` and `review-gate`, which can never pass on a
Dependabot branch (it receives no repository secrets). Nothing else is open.

## 2. What the last stretch of work established (September 16–19)

The line of work was the founder's #805 question: summaries that state a *cause* the filing never
gives ("revenue rose, driven by strong demand"). Everything is merged and recorded; the reading order
is the numbered list at the foot of this file.

1. **#805 was assessed and closed** ([assessment](pr805-assessment-2026-09-16.md)). Its idea — one
   shared "support" condition for every model-authored explanation — was right; its wording let a
   cause rest on signed figures alone.
2. **The strong judge became an acceptance instrument for any eval artifact.** `evals.judge_report`
   (#898, #900) judges a PR's retained `eval-report-<run_id>` artifact locally on the founder's Claude
   subscription as `cli:claude-fable-5-1`. Judge contract version 2 adds **G4 unsupported cause** and
   **G5 basis mismatch** to G2 fabricated comparatives and G3 hallucinated facts.
3. **The corrected prompt `summary-2026-09-o` is released and confirmed** (#899; drained 48/48).
   Measured on two control runs and three candidate runs under one judge
   ([results](review-evidence/pr805-path/fable-judge-results-2026-09-18.md)): negative judgments
   80.0% → 55.8% (30% fewer), unsupported causes 61% → 35% (42% fewer), and every candidate run beats
   every control run on negatives, G4 and G5. **The first report of this said "halved"; that was one
   run and it was wrong** — see the [correction](review-evidence/pr805-path/variance-correction-2026-09-17.md).
4. **Fable and Opus agree on G4 for 87% of attempts** (Cohen's kappa 0.71) on the same artifact; overall
   verdict kappa 0.60, G5 kappa 0.48. The instrument is reasonably robust to the judge for the defect
   that matters most. Never mix judges across runs anyway.
5. **A code-owned attribution gate and a model verifier are built and dormant.** The lexical gate
   (`ai/attribution_gate.py`, #903/#905) finds causal clauses and the source passages that bear on
   them; alone, its drop decision is 47% precise, so **it can no longer delete text by itself**
   (#908). A single bounded model call (`ai/attribution_verify.py`, `AI_ATTRIBUTION_VERIFY`) decides;
   a "stated" verdict must quote a passage it was given. First real measurement
   ([record](review-evidence/pr805-path/verifier-first-measurement-2026-09-18.md)): drop precision
   65%, three correct rescues, no wrong rescue. Half the wrong drops were evidence the verifier never
   received; #912 fixed the passage ranking (proving passage supplied for 8 of 9 stated clauses
   offline, up from 6). **The gate surfaces only about 45% of the attempts the judge fails for G4** —
   recall is the larger gap. Both flags stay off.

## 3. What to doubt first

- **Single runs.** The `o` candidate varies about twice as much between runs as sampling would
  explain (19 points across three runs) while the control does not (3 points across two). Quote any
  prompt effect from at least two runs and report the range
  (`lessons/evals-accept-a-prompt-change-on-two-runs-not-one.md`).
- **The ledger's unchecked rows.** Many were closed by later work without being ticked (#840, #843
  and #845 merged on 13 September; `engines.node` is already `>=22.22.2 <23`). Section 5 is the open
  list; confirm against GitHub before starting anything that looks unfinished.
- **Tool success messages.** Several local tools and background watchers in this repository reported
  completion while having done nothing (an eval job that skipped on a workflow-only change, a judge
  run whose 70 verdicts were all "claude CLI exit 1"). Read the artifact, not the exit status.

## 4. Environment and access

- **Workspace.** The founder's Codex workspace sits under iCloud Drive's Documents, where
  `fileproviderd` stalls every git and shell command for minutes. Work in a clone outside iCloud; the
  last session used `~/Codex-local/earningsnerd-w3-7` with a Python 3.12 venv at
  `~/Codex-local/venv-w3-7` (`lessons/ops-keep-worktrees-out-of-icloud-documents.md`).
- **Full local gate.** `~/Codex-local/run-w3-7-gate.sh` runs ruff, bandit and `pytest -m ""` with the
  four PostgreSQL lanes on a local PostgreSQL 15 at port 55433. If it prints `connection refused`, run
  `~/Codex-local/start-pg15.sh` first (data in `~/Codex-local/pg15-data`, role `earningsnerd`). The
  last green full gate on `main` code was 3,380 tests.
- **The strong judge.** `claude -p` on the founder's subscription (standalone CLI at
  `~/.local/bin/claude`, logged in). The Fable quota can run out; an exhausted quota returns exit 1
  with an empty stderr and the reason only in the JSON `result`. Probe `is_error` before a long run
  (`lessons/ops-the-subscription-judge-has-a-usage-limit.md`); never substitute another model. If you
  cannot run `claude` in your environment, the founder runs `/judge-readout` in a Claude session or
  hands judging to a Claude agent, as on 2026-09-18 ([handover](handover-fable-judge-2026-09-18.md)).
- **Provider key and balance.** The DeepSeek key exists only as a CI secret. Read the balance by
  dispatching `.github/workflows/deepseek-balance.yml` and reading its log.
- **gcloud.** Read-only access works when the founder's credential is fresh; it expires, and only the
  founder can renew it (`gcloud auth login` in a terminal). When it is stale, verify deploys from the
  CI deploy log and `curl -fsS https://api.earningsnerd.io/health/detailed`.
- **Merging.** Ruleset 23561253 on `main` requires `backend-tests`, `frontend-tests`, `e2e-tests`,
  `migrations-postgres`, `lighthouse` and `review-gate`, squash only, no bypass. `review-gate` passes on
  a completed Codex review of the exact head or a PR-body line `Review override: <reason>` (ten
  characters or more). The Codex review allowance has been exhausted since 2026-09-16.
- **Measuring a change without shipping it.** Open a draft PR that is never merged; it must touch a
  path under `backend/app`, `backend/evals` or `backend/prompts` or the `eval-baseline` job skips; if
  it changes the eval environment, `test_eval_parity` fails by design. Close it once the artifact is
  captured (#906 and #911 are the precedents).

## 5. What remains — reconciled open list

**Engineering, unblocked (do these):**

| # | Item | Next step |
| --- | --- | --- |
| E1 | Dependabot #916, #917 | Take both through one `codex/wave3-*` branch (precedent #870, #872): full gate, `eval-baseline`, one Copilot run, merge, serial deploy verification; then close the Dependabot PRs as superseded. |
| E2 | Verifier, step 1 | Re-measure with the #912 ranking fix: measurement-only branch with `AI_ATTRIBUTION_VERIFY` on in the eval env, judge the artifact, hand-read every flagged clause against its excerpt. |
| E3 | Verifier, step 2 | Tighten the verify prompt against the Pfizer failure: a verbatim same-line, same-amount restatement was rejected as "not stated" with the passage in hand. |
| E4 | Verifier, step 3 | Recall: the lexical finder surfaces about 45% of judge-G4 attempts. Study the 12 misses in the Fable-judged verification artifact before designing anything. |
| E5 | Code-owned residuals | KO segment operating margins (segments filler divides by XBRL segment revenue that includes intersegment amounts); AMZN issuer-defined versus conventional free cash flow in the cash card; SE cash-conversion line on a different net-income basis from the prose; AAPL distributions versus operating cash flow ([plan](financial-relationship-next-2026-09-13.md)); BABA 20-F filing 327 returns `partial` on regeneration (XBRL enrichment). |
| E6 | Scorer profiles | BRK.B financial depth (an insurer's highlights are premiums and float) and GPRO delta sign on a negative base. Touching a scorer is a listed re-pin trigger. |
| E7 | Quality acceptance specification (master plan P0) | Freeze the rubric, severity definitions, the 30-filing × 3 unseen holdout manifest and a spending ceiling ([plan](ceo-implementation-plan-2026-09-08.md), section "What world-class acceptance must demonstrate"). Prepare offline; the founder accepts it. |
| E8 | `o` variance lead | Test whether the `o` prompt makes generation less consistent: more paired runs, same judge. |
| E9 | E09 proposal | Read the database job-outcome table (the last unread item) and finish the proposal ([package](e09-proposal-next-2026-09-13.md)). Proposal only. |

**Recurring:** the weekly readout. `data-quality-weekly.yml` generates on Mondays and the judging
runs on the Fable subscription (`.claude/skills/meta/judge-readout/SKILL.md` is the procedure). The
next generation is Monday 2026-09-21.

**Waiting on the founder (raise each once, with evidence, then move on):**

| Decision | Why it matters |
| --- | --- |
| **Cloud SQL automated backups and point-in-time recovery are disabled** on the live database | The largest open operational risk; a restore rehearsal into an isolated target is also unproven. Also found: a stopped Postgres 18 instance still billed, and a Monday schedule overlap at 50 connections against a 25 default. |
| Notable filings: retain or kill | The review week ended 2026-09-15; the decision is overdue. |
| Analysis (W3-10): run the companyfacts warm-up and name a Pro test account | `scripts/sync_companyfacts.py` has never run as a job. |
| Arming `AI_ATTRIBUTION_VERIFY`, then `AI_ATTRIBUTION_GATE`, in production | Only after E2–E4 show the drop decision no longer deletes sourced analysis. |
| Independent quality acceptance and the unseen holdout | Human review capacity and spend; the gate to universe-wide pregeneration. |
| Controlled invite-only beta | Recruitment and commitments are the founder's. |
| Stripe (E06) | Needs a natural payment after the 13 September event configuration; no test payment. |

**Held until the founder says otherwise (never touch):** universe-wide pregeneration; historical
repair or replay; production flags, capacity, prices, trial, promo and registration; legal decisions;
destructive data or history operations; new locked-anchor exceptions; live jobs, email or account
actions as tests; AI provider or model changes; security or secret changes; future dependency
majors; Dependabot alert #270; D8 (deleting two stale remote branches); purchasing credits.

## 6. Reading order

1. `AGENTS.md`, then `CLAUDE.md` (the twelve rules are binding verbatim).
2. This file.
3. `lessons/README.md`, then the lessons named above.
4. `backend/evals/RUNBOOK.md`, sections "Weekly strong-judge measurement" and "Judging a pull
   request's eval artifact".
5. The #805 path, in order: [assessment](pr805-assessment-2026-09-16.md),
   [variance correction](review-evidence/pr805-path/variance-correction-2026-09-17.md),
   [gate precision](review-evidence/pr805-path/attribution-gate-precision-2026-09-17.md),
   [attribution guard plan](attribution-guard-plan-2026-09-17.md),
   [verifier measurement](review-evidence/pr805-path/verifier-first-measurement-2026-09-18.md),
   [Fable results](review-evidence/pr805-path/fable-judge-results-2026-09-18.md).
6. The master plan: [CEO implementation plan](ceo-implementation-plan-2026-09-08.md).
7. `tasks/todo.md` from the top down to "September 16", as the record of how this state was reached.
