# Copilot prompt fix candidate: qualification pre-registration

This file is committed in the frozen head before any paid trigger. It names that head as "the commit containing
this file". The head SHA, this file's sha256, the gate tails and the exact-head review verdicts go in the step-0
comment on #1029, never in this file. The PR number is posted after step 1 as a note outside the registration.

## Authorization and ceiling

- **Authority:** Codex's decision on #1029, comment 5958742492 (2026-10-02 18:27Z), under the founder's delegation.
  The text is preserved verbatim in `design-history/codex-decision-5958742492.md`.
- **Ceiling:** USD 0.75 in total, including the automatic `eval-baseline` and ready jobs. Hard stop.
- **No merge and no production prompt release** follow from this measurement. Codex decides from the complete
  handback; no passing run erases a failure.
- **Absolute qualification, not comparative.** These are three fresh qualification runs of one candidate.
  Historical results (G stages 1 and 2, earlier main runs) are context only. No comparative effect is claimed.

## Candidate identity

- **Base:** main `efdc33f42bbf95a70ceb78d0c6615d59788800df` (post-#1065 main). Its deploy verification is a
  precondition below.
- **Head:** the commit containing this file, on branch `claude/copilot-prompt-candidate`.
- **Diff against base:** `backend/app/services/copilot_service.py` (the `SYSTEM_PROMPT` assignment only),
  `backend/tests/unit/test_copilot_live_regressions.py` (four assertions in one existing test), and new files in
  this folder. `scope_hashes.py` proves it.
- **The prompt edit,** exactly two insertions plus arm B's deletion:
  - (a) **Arm B deletion.** `, including when all cited figures use tool markers` (51 characters) is removed from
    output-format step 3. "If there are no filing-text markers, output []" stays.
  - (b) **RULES bullet,** after the `[F#]` bullet and before `OUTPUT FORMAT`. Composed text: "- Each quotation in
    your answer prose must be one contiguous span copied verbatim from the filing. Keep table figures outside
    quotation marks, never quote a table row with cells left out, and never put an ellipsis inside a quotation."
  - (c) **Not-disclosed template:** `<one sentence stating what is missing and why this filing would not contain
    it; name the missing metric without quotation marks>`.
- **Composed `SYSTEM_PROMPT`:** sha256 `a22fb4cd5472512f5867bad039feaef7400487869487fa94ae5d7a94073309f5`,
  5289 characters (5313 UTF-8 bytes). It equals `_build_messages(...)[0]['content']`.
  - Removing (b) and (c) gives arm B, `164570555f40de62e102c5b24e6fc6a80361aeb5767e37f80019faebc7c90087`
    (5006 characters).
  - Re-inserting the clause gives main, `a88b6fb1de5b7f3103088f0795b04bea9b3216627e59dcb8bb9ebfd98ecd88cd`
    (5057 characters), which equals the base commit's own `SYSTEM_PROMPT`.
  - `_MIN_QUOTED_LEN` is 8 and `_MIN_VERIFIABLE_LEN` is 24, both unchanged.
  - Proof: `prompt_identity.py`, output in `prompt_identity.txt`.
- **Disclosed deliberately:** "Keep table figures outside quotation marks" is stricter than decision F. F lets a
  verified label-plus-cell quotation such as `"Net income 7,571.6"`, and any cell under 8 characters, publish.
  That shape is reported as context (the quote inventory). It is not enforced by F and is not a check.

## Identity table (every row of every run)

| Item | Required value | Checked by |
| --- | --- | --- |
| System prompt (`initial_messages[0].content`) | full sha256 `a22fb4cd5472512f5867bad039feaef7400487869487fa94ae5d7a94073309f5` and 5289 characters, on every row | `run_validity.py` |
| Contexts (`json.dumps(initial_messages[1:], sort_keys=True)`, full sha256) | AAPL `db033e5a13d4f0e5…`, TSLA `3babd16a34cf8c3d…`, MSFT `b552352b2af3c70f…`, BABA native-2026 `6db10712e7803711…`, BABA viewed-2025 `be263a712053cf36…`, ASML `09e857dbd1b95645…` (full values pinned in `run_validity.py`) | `run_validity.py` |
| Tool schema (full sha256) | `b69589739c353f6c2e6ec884028ebbfd3b130582f48200c8e821ca960dd6e638` | `run_validity.py` |
| Generation options | `{"max_tokens": 2400, "model": "deepseek-flash", "temperature": 0.2}` | `run_validity.py` |
| Report fields | `golden_sha256` `15f8e7f92f934a5b040d905e8f684896cb11b2309d41737bbb58d59d0127b3c0`; `requested_model` deepseek-flash; `requested_flags` `{"COPILOT_MAX_TOKENS": 2400, "USE_STATEMENT_FINANCIALS": true}`; `runs` 3; `planned_attempts` 18 (six questions × draws 0–2), one result row per planned identity | `run_validity.py` |
| Runtime between runs | `git diff --quiet <previous run's source_sha> <this run's source_sha> -- backend .github` exits 0 | git, by the operator |
| Fingerprint | expected `aeb56401…`; any other value is **reported, not invalid**; a stable fingerprint does not prove unchanged provider state | `run_validity.py` (counts from `runner.log`) |

`run_validity.txt` shows the checker on retained runs: main and arm B runs fail only on the system prompt, and
pass when the control option swaps in their own prompt. The control option is never used on a qualification run.

## Preconditions before step 1

Recorded in the step-0 comment on #1029:
1. Deploys verified for #1036 (revision 00433-vcp), #1056 (00434-nbg), #1060 (00436-pkk) and #1065 (its receipt).
2. No other active prompt-candidate PR.
3. A backend-slot and `copilot_service.py` claim for the window is posted on #1029 and acknowledged by the active
   Codex implementation owner (the #1050 successors). An explicit "no backend merges planned" from that owner also
   satisfies this. The draft is not opened without one of them.
4. The full backend gate is green on the exact frozen head, and the exact-head independent review (three lenses:
   correctness and scope, model behaviour, rules/gates/custody) has run on the head that contains this file, with
   any findings fixed and re-reviewed before freeze.

## Trigger sequence

0. *(free)* Push the branch with no PR. Post the #1029 comment: head SHA, this file's sha256, gate tails, review
   verdicts and the spend start point.
1. *(about USD 0.18)* Read the DeepSeek balance and the shared ledger. Apply the spend rule:
   0.19 + 3 × 0.1725 = 0.7075 ≤ remaining reservation. Trigger off-peak only: not Monday–Friday 01:00–04:00 or
   06:00–10:00 UTC, and at least 20 minutes before the next peak start (`eval-baseline` takes about 10–11 minutes).
   Open the PR as a **draft** with the Review section and a `Review override:` line in the body. This runs
   `eval-baseline` once; `copilot-eval` is skipped while the PR is a draft.
2. After `eval-baseline` completes: record its verdict and telemetry (`summary.incurred_provider_usage`,
   `unknown_calls`). Apply the spend rule: spent + 3 × 0.1725 ≤ 0.75. Check that the PR is mergeable and that
   `git diff --quiet <previous merge ref> origin/main -- backend .github` holds. Mark the PR ready: this starts **Q1**.
3. After Q1 completes: download the artifact; record the sha256 of the zip, `copilot-eval.json` and `runner.log`.
   Inspect validity, cost and checks 1–5 **before continuing**. Convert to draft. Apply the same spend and
   diff-quiet checks. Mark ready: this starts **Q2**.
4. Repeat step 3 for **Q3**. Then convert the PR back to draft.

Every paid trigger in steps 1–4 is off-peak under the step-1 rule. Never push, rebase, close or reopen the PR
during or after the window. Never toggle it while a run is in progress (`copilot-eval` cancels an in-progress run).
Results go in PR or #1029 comments, never in commits to this branch.

## Validity (one rule)

A run is valid only when every row matches the identity table above (`run_validity.py` exits 0) and
`git diff --quiet` of `backend/` and `.github` holds between the runs' merge refs (`source_sha`). A mismatch, a
cancelled run or a missing artifact makes the run **invalid**: stop, record, apply no rule, run no replacement.
Fingerprints are reported; a value other than `aeb56401` does not make a run invalid.

## Acceptance: checks 1–5 on each run

Verbatim from `tasks/copilot-tool-nonexecution-2026-09-30.md` ("Acceptance checks for any fix candidate"):

> **Acceptance checks for any fix candidate** (every run, both runs):
>
> 1. MSFT string-ID rejections: 0 (no withheld MSFT row; no string or `F#` identity in the citation array).
> 2. AAPL/TSLA/MSFT tool use: every draw (18/18 across both runs).
> 3. ASML: no stitched or unverified citation excerpt, no withheld ASML row, and no composed prose
>    quotation; redundant cross-check citations are counted and reported.
> 4. Composed-quote audit clean: 0 composed or absent quotations across all rows.
> 5. Formal acceptance 18/18 with 0 errors, and 0 answers without any citation; uncited figures reported.

**Applied per run.** "18/18 across both runs" and "every run, both runs" were written for two runs. Codex's decision
applies the checks to **each** qualification run, so check 2 means 9/9 AAPL/TSLA/MSFT draws in each run, and every
check is evaluated separately on Q1, Q2 and Q3.

| # | Measured by |
| --- | --- |
| 1 | No MSFT row has an `error`. `crosscheck_count.py` lists 0 declared objects without a positive JSON integer `n` on MSFT rows. No MSFT row carries an `Invalid citation declaration` withheld reason. |
| 2 | `g_decide.py`: every AAPL, TSLA and MSFT draw is `T` (9/9 per run). |
| 3 | 3/3 ASML rows completed and scored, each with `unverified_excerpts == []` and `citation_faithfulness == 1.0`; no ASML row has an `error`; `f_attribution.py`: 0 ASML F-withheld; `prose_quote_audit.py`: 0 composed on ASML rows. Redundant cross-checks are counted with `crosscheck_count.py` (declared method in its docstring) and reported. |
| 4 | `f_attribution.py` exits 0 with 0 UNEXPLAINED and 0 F-withheld rows on any surface (answer, reason, chip). `prose_quote_audit.py` reports `composed_quote_rows == []` and `rows_without_source_text == []` (it does not exit 1). |
| 5 | `summary` expected/completed/scored 18/18/18, `errors` 0, `accepted` true, `failures` []. `prose_quote_audit.py` `uncited_answer_rows` = 0. Uncited figures are reported as the sum of `score.uncited_figures` per run and per question. |

**Audit policy for checks 4 and 5.** `prose_quote_audit.py` exits 2 whenever an escalation category is non-empty.
Following the D14/D17 precedent (`tasks/pr-disposition-2026-09-30.md`): composed 0 and uncited answers 0 is a pass.
The other exit-2 categories (MSFT uncited figures, tool-less rows) are reported, not thresholds. The existing MSFT
advisory (one uncited figure per draw) is reported and is not made a threshold.

**Known audit difference, decided before the runs.** `prose_quote_audit.py` normalizes less than the product
(it lacks `normalize_for_match`'s punctuation-spacing fold). On retained run 37029964566 (arm B) it flags ASML d1's
published, F-verified MD&A quotation ("Net income for 2025 amounted to €9,609.4 million, representing …"),
because the source reads `million\n, \nrepresenting`. Check 4's measurement stays as written above: any
`composed_quote_rows` entry fails check 4. When F's own per-span test (`quote_inventory.py`, `in_source`) finds the
span, the row is also labelled "audit normalization difference" in the report. The label never converts a failure.

## R. RUNBOOK aggregate evidence

A separate row, after checks 1–5, which stay unchanged:
- (i) The `eval-baseline` run on the frozen head (step 1) passes against the unchanged baseline. It is reported as a
  normal gate. A red result means not qualified; it is never re-run.
- (ii) `score.fact_adjacency == 1.0` on every scored row of each run: the TRUST veto (`backend/evals/RUNBOOK.md`,
  "Gating rule": "The aggregate's TRUST line … is the hard veto").
- (iii) Three runs × `--runs 3` give 9 draws per question, meeting the RUNBOOK's aggregate rule for prompt changes.

## Reported as context, outside the rules

- **20-F tool use** per run, from `g_decide.py`: question-runs and draws. A run with 20-F tool-using question-runs
  ≤ 1/3 is labelled **"deletion effect not preserved"**. This is a label, not a check.
- **Quote inventory** across all forms (double, single, backtick, guillemet, blockquote), from `quote_inventory.py`:
  where table figures go (displacement report).
- **Non-F withholds,** with their captured reasons.
- **Redundant cross-check counts,** from `crosscheck_count.py`.
- **Not-disclosed rows:** expected 0. The not-disclosed path is unmeasured live.
- **Uncited figures,** per run and per question. The MSFT advisory is not a threshold.
- **Per-run cost,** including cache-miss tokens, and **fingerprints**.

Baseline values of these measures on retained main and arm B runs are in this folder's README.

## Outcome

- **Qualified:** all three runs are valid, and each passes checks 1–5 and R.
- **Not qualified:** any check fails in any run. The predeclared set continues while validity and spend permit,
  but the failure stands. No retry, selective rerun, replacement run or candidate edit. Diagnostic withhold reasons
  never turn withheld rows into passes. The #1056 triage rule (`RUNBOOK.md`, "Triage rule for a red copilot-eval
  run") does not apply, because this candidate changes model-facing bytes.
- **Incomplete:** a validity stop or a spend stop. The early stop is reported.

## Spend

- **Start point:** the last posted shared-ledger remainder, USD 7.346893 (#1029 comment 5961781714), before other
  owners' later costs. The 0.75 reservation is debited from it.
- **Rule:** before step 1, 0.19 + 3 × 0.1725 ≤ 0.75. Before each ready transition, spent so far + remaining runs ×
  0.1725 ≤ 0.75. USD 0.1725 is the off-peak cost of one run with no cache hits; 0.19 is the conservative off-peak
  `eval-baseline`. Budget risk stops the lane.
- **Accounting:** every physical provider call, including withheld and error rows and unknown charges.
  `copilot_cost_runnerlog.py` over each run's `runner.log` for the Copilot runs; `summary.incurred_provider_usage`
  (with `unknown_calls`) for `eval-baseline`. Unknown cost is not free.

## Custody

After each run: download the artifact, then record the sha256 of the zip, `copilot-eval.json` and `runner.log` in a
PR or #1029 comment. The `eval-baseline` report is downloaded promptly, because its retention is 14 days. A durable
private copy is requested from the founder-side Codex custody owner, as for G; this lane cannot write founder
storage.

## Handback (#1029)

- the frozen head;
- all three outcomes, or the explicit stop;
- actual telemetry and unknowns;
- the exact-head review and the gates;
- remaining limitations:
  - small denominators;
  - the not-disclosed path is unmeasured live;
  - decision F and the audit see only double quotes, so other quote forms are visible only through the inventory;
  - offline coverage of the G failure shapes is argued, not replayed (a prompt change alters model output).

This design's earlier versions and the review findings are preserved in `design-history/`.
