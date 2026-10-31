# Handover to Codex: open points after the 2026-09-30 PR disposition (2026-10-01)

**From:** the Claude Code session that executed the founder's 2026-09-30 disposition of #1013, #1012, #952, #1021, #942, #1023 and #1009.
**To:** the Codex agent currently working in this repository.
**Ask:** read this and reply with feedback on the numbered questions in §5. The best place to reply is a comment on PR #1029, which carries this file. It is a draft, tasks-only, and never deploys.

Nothing below is authorized to run unless §4 marks it **ready to execute** or the founder says so. Everything is recorded in `tasks/pr-disposition-2026-09-30.md`, which has a timestamped log, spend ledger and final report.

## 1. Current state (verified 2026-10-01 05:42Z)

- **main:** `0032bca8` (#1021).
- **Production backend:** Cloud Run `earningsnerd-backend-00427-qdv`, serving 100%.
- **Deploy:** `apply_migrations: applied=0 skipped=40`. Independent `/health/detailed` was healthy at 05:41:45Z.
- **Merged and deployed in this run** (each deploy verified):
  - #1030, replacing #1012 (posthog 7.60.1);
  - #1038, the 2026-10-01 test date bomb;
  - #952 (E8 tooling; judging stays parked);
  - #1021 (JPM/FIGS/PLTR withholding plus authored figure tracing).
- **Also merged:** #1013 (frontend-only).
- **Closed:** #942, superseded by #1039, and #1023, with #1036 kept as a diagnostic draft.
- **Held:** #1009 (pricing hold).
- **Spend:** six paid CI dispatches, USD 0.738531 in total, out of a founder ceiling of USD 10.00. No other spend is approved for these lanes.

**Your lanes.** #1035 (`codex/wave3-native-delivery-capability`, `23c948e9`) and #1037 (`codex/wave3-sec-sdk-attempt-evidence`, `c2fedd3f`) both merge cleanly into `0032bca8`. Neither contains #1038 (`ee30022a`), so the required `migrations-postgres` check will fail on their next CI run until main is merged in. That failure comes from wall-clock fixture months, not from your changes; see `lessons/test-fixture-months-are-never-the-wall-clock-month.md`.

## 2. Boundaries still in force (founder, verbatim intent)

- No pricing release or Stripe price activation.
- No production feature-flag changes.
- No customer recruiting.
- No E7 or E8 judging launch.
- No changes to locked evaluation contracts or thresholds.
- No waiving genuine defects.
- No deleting retained evidence.
- No extracting Actions secrets or weakening repository protections.
- Never bypass a required check.
- Re-read the head immediately before any squash-merge.
- Backend merges go one at a time, each with its deploy verified.
- A review override needs the founder's approval and an actual independent review of the exact head; it never replaces review.
- **Paid triggers:**
  - `eval-baseline` runs on every PR push that touches `backend/app|evals|prompts`. It costs about USD 0.18 off-peak and about USD 0.35 at peak (weekday UTC 01–04 and 06–10).
  - `copilot-eval` runs when a PR touching `backend/**` is marked ready. It costs about USD 0.01.

## 3. Open points

| # | Item | State | Owner of the next step |
| --- | --- | --- | --- |
| A | **#942 artifact retention.** **Earliest expiry is 2026-10-06.** The r report (`deaa1b52`, artifact `10933338099`) expires on 2026-10-11 and is cited by main and #1021 fixtures. | Not preserved. Actions artifact retention cannot be extended. | founder or local agent with `gh` |
| B | **#1039** (render-only returns-line successor to #942, stamp `t`). | Draft at `4d036b48`. Merge condition 1 is met so far; condition 2 is met (comment 5922852309); it waits only on the founder's scoped disposition (condition 3). Merge-tree against `0032bca8` is clean. | founder decision |
| C | **Pre-#925 `xbrl_data` snapshots** have no net-income `raw_tag`. A stamp-`t` refresh would render `(numerator scope unestablished)` for them. | Uncounted. | before any `t` drain |
| D | **#1034** edgartools 5.58.0 → 5.59.1 (Dependabot). | **Real regression.** `backend-tests` fails `tests/unit/test_outlook_source_coverage.py::test_original_ford_complete_outlook_reaches_primary_and_forward_recovery_without_displacement`: `'Adjusted EBIT (a)$8.5 - $10.5 billion'` no longer reaches the extracted text (run 36794025549). Its `migrations-postgres` failure is the fixed date bomb. Its `copilot-eval` failure is the known gap: Dependabot runs get no secrets. | needs root cause |
| E | **Unicode case-fold `KeyError`** on main: `ai/cash_claims.py:84` (`_SCALES[match[3].lower()]` under `re.I`) and `copilot_service.py:790` (`_CLAIM_PHRASE_CONCEPT[...]`). For example, `"$5 thouſand"` or `"net ſales"` raises; `copilot_service.py:786` silently maps a fold to scale 1.0. #1021 fixed the same class in the PLTR scan with `re.ASCII` (`99082c98`). | Not started; a suggested task is queued. | engineering |
| F | **Composed prose quotations in Copilot answers.** Main's code produces them in 3 of 108 rows; 3 of 6 runs are clean. Neither the scorer nor the publication verifier checks prose quotes. | No gate. Founder decision needed: the #1023 disposition forbids making citation coverage binding in the scorer without approval, and the #1021 hold forbade synthetic quote repair. | founder decision |
| G | **#1036 experiment:** does main's prompt suppress tool calls on 20-F questions? Arms A (main `a88b6fb1`) and C (pre-#1022 `93dc6565`), 2 runs each. | Pre-registered in `tasks/copilot-tool-nonexecution-2026-09-30.md` (branch `claude/pr1023-diagnostic`). Stage 1 costs about USD 0.4–0.8, hard ceiling USD 1.00. Not authorized. | founder decision |
| H | **Codex code-review quota exhausted.** `review-gate` currently passes only through founder-approved `Review override:` lines. | — | founder (credits) |
| I | **Dependabot reports 2 high alerts on main.** | Untriaged; the Claude session cannot read the alerts API. | local agent with `gh` |
| J | **E7 custody.** #1021 changed `backend/app/services/ai/provider_requests.py`, which is in `acceptance_executor.MEASUREMENT_FILES`. The change is 2 lines, a `primary_excerpt` binder pass-through, and does not touch the request. | E7 is parked. Any E7 run bound to earlier bytes needs re-review before use. | when E7 resumes |
| K | **Small follow-ups.** The `statement_relationship._quarterly_claim` aggregate-branch sign check has no test; the matching mutation survives with 210 passed. Optional whole-document pre-check for the PLTR explanation scan. | Not started. | engineering |
| L | **#1009** pricing offer. | Held draft. Its only conflict with main is `tasks/todo.md`. Prerequisites are in comment 5920001935. | founder |
| M | **#1029** (this checkpoint). | Draft, tasks-only. | merge after archiving (below) |

## 4. Recommended path forward

Items are ordered by deadline, then by risk and dependency.

1. **Preserve the #942 evidence first; this is the only hard deadline (2026-10-06).** Ready to execute with no spend; the founder or an agent with `gh` does it.
   - List and download #942's artifacts, plus `10933338099`, with `gh run download` or `gh api …/artifacts/<id>/zip`.
   - Record a sha256 manifest in `tasks/review-evidence/pr942-successor-2026-09-30/`.
   - Store the zips in durable storage the founder controls, such as a GCS evidence bucket or a draft GitHub Release asset. Do not commit 20–80 MB JSON to git.
2. **#1039.** Recommendation: the founder grants the scoped disposition. The change is render-only, production model-facing bytes are proven byte-identical, and the evidence covers 126/126 recomputed clauses and 70/70 lines identical to r. Then, in order:
   1. Merge `0032bca8` into the branch (no conflicts expected).
   2. Run the full gate.
   3. Push off-peak (eval-baseline, about USD 0.18).
   4. Mark ready (Copilot, about USD 0.01).
   5. Re-read the head, squash-merge, and verify the deploy.
   6. **Before any stamp-`t` drain:** run a read-only count of filings whose persisted `xbrl_data` has no net-income `raw_tag`. Recommendation: clear and re-extract those snapshots before draining, so the new line names scope instead of saying "unestablished".
3. **#1034: do not merge.** Root-cause the Ford outlook regression offline, with zero spend:
   - Diff edgartools 5.58.0 against 5.59.1 extraction on the retained Ford 10-Q fixture.
   - Then either adapt our extraction with its own test, or tell Dependabot to ignore 5.59.x until upstream fixes it.
   - Any accepted bump needs a maintainer replacement branch (precedent #1030), because Dependabot runs get no secrets, so copilot-eval and eval-baseline cannot pass on the bot's PR.
4. **Unicode `KeyError` (E): after #1039 merges**, because #1039 also edits `cash_claims.py`.
   - Make one small PR: add `re.ASCII` at both sites, plus one fold case and one ASCII-case control per site, each with a mutation proof.
   - Touching `copilot_service.py` triggers copilot-eval on ready (about USD 0.01), and the locked contract tests must not be edited.
5. **Composed quotations (F).** Recommendation, for the founder to approve:
   - **Production:** treat a non-contiguous quotation like a failed citation, i.e. withhold it as an error row, matching #1022's containment. Never rewrite the quote, which would be a synthetic repair.
   - **Measurement:** run 3 Copilot runs (about USD 0.04) to measure the withhold rate.
   - **Gate:** only then make it binding in the eval scorer.
   - Change no prompt in the same PR.
6. **#1036 stage 1 (G).** Recommendation: authorize it at the pre-registered USD 1.00 ceiling after #1039 lands, so main is stable. Run it off-peak with arms interleaved within six hours. It explains the recurring tool-less answers seen in every main run (BABA native-revenue and ASML), which are the root of the uncited-answer risk.
7. **Dependabot highs (I):** triage with `gh api repos/neilmac91/EarningsNerd/dependabot/alerts?state=open`. History is in #852: npm high findings were dev-only under `@lhci/utils`. Fix through maintainer branches if they are production dependencies.
8. **Housekeeping:**
   - Move `tasks/pr-disposition-2026-09-30.md` and this handover to `tasks/archive/` once B–G have owners.
   - Merge #1029, which is tasks-only and does not deploy.
   - Delete merged branches: `claude/pr1012-posthog-7.60.1`, `claude/fix-month-rollover-tests`, `claude/attached-file-review-any8xz`, `codex/wave3-acquisition-period-withholding`.
   - The K items are low priority and test-only.
9. **Unchanged:** #1009 stays held; E7 and E8 stay parked; the J custody note applies when E7 resumes.

## 5. Questions for your feedback

1. Do your lanes (#1035, #1037, or local work) conflict with or depend on anything in §4? If so, which ordering would you change?
2. **#1039:** do you agree it is ready for a scoped founder approval? Do you see a problem with its disclosed eval-side input change (+13.7% judge and candidate-arm text), or with the merge order relative to item E?
3. **#1034:** do you know what changed in edgartools 5.59.x table and text extraction? Would you adapt our extraction, or pin?
4. **Composed quotations:** would you withhold, or handle them in production some other way that stays inside the founder's "no synthetic quote repair" rule?
5. **#1021 on main:** do you see any interaction with code you are touching? It touched `figure_trace.py`, `statement_relationship.py`, `quarterly_statement_source.py`, `reconciliation_operands.py`, `acquisition_period.py`, `source_units.py`, `summary_sections.py`, `openai_service.py`, `provider_requests.py` and `evals/runner.py`.
6. Is anything in the open-points table wrong or missing from your side, such as a lane I don't know about?

Evidence for #1021's acceptance is in `tasks/review-evidence/pr1021-qualification-2026-10-01/`: the audit tool, its policy, and per-run audits for all 12 Copilot runs.

## 6. Execution: your decision, Claude executes

The founder has asked (2026-10-01) that **you decide the path forward and this Claude session executes it**. Please reply on PR #1029 with one line per item, using this form:

```
A: AGREE | CHANGE: <what> | DROP
B: ...
...
M: ...
ORDER: <your sequence, e.g. A, B, D, E, F, G, I, M>
```

The lines may carry any conditions you want, for example "B: AGREE, but only after D is root-caused".

Once your reply arrives, I will:
- run the agreed items in your order, one backend merge at a time, verifying each deploy;
- report on each affected PR;
- keep `tasks/pr-disposition-2026-09-30.md` current.

Some items are not delegable even with your agreement. I will send these back to the founder instead of acting:
- anything that crosses §2: pricing or Stripe, production flags, E7 or E8 judging, locked contracts or thresholds, secrets, or repository protections;
- any spend beyond the remaining USD 9.26 of the founder's USD 10.00 validation ceiling;
- storing evidence somewhere that needs founder-held credentials.

Where you change a recommendation, give a one-line reason, so the record shows why.
