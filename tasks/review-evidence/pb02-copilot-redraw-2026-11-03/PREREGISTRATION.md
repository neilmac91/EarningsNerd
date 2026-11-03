# Pre-registration: one further `copilot-eval` draw on PB-02's accepted code (2026-11-03)

Committed on #1955 before the paid run it causes. This file is the only change in its commit. It names that commit as
"the head containing this file"; the head's SHA and the run links go in #1955's comments, never in this file.

## Authority

- **The chief's predeclaration** on #1955, issuecomment-6600170576 (2026-11-03 09:37 UTC), under
  `backend/evals/RUNBOOK.md`'s triage rule for a red copilot-eval run (lines 1082 to 1094: "A predeclared protocol
  that needs several draws of the same code gives each draw its own head, a commit that changes only its evidence
  folder, and says so in its preregistration") and the authorized release workflow.
- **Release.** Code release is founder-authorized, and the chief owns the ready mark and the merge
  (issuecomment-6599610372). No merge, production configuration change or live grant follows from this file.

## The original run, which stays in the record

- **Run.** `copilot-eval` run 41609164901 on head `ff15b23e5b028910c2d869979f9d13f3794d24cb`, drawn by the chief's
  ready mark at 09:12:39 UTC.
- **Verdict.** FAIL / incomplete. Expected 18, completed 18, scored 16, passed 16, execution errors 2.
- **The two errors.** MSFT `sales-diluted-eps-2025` draw 1 and ASML `us-gaap-sales-net-income-2025` draw 2.
  - Each is a `ValueError` at `answer_or_score`, labelled `operationally incomplete attempt`, with no withheld reason.
  - The run's log shows exactly two `ai_call` outcomes `timeout`, at 75.0 s each, and two
    `stream_chat_with_tools failed for deepseek-flash` lines. Every other call succeeded.
- **The triage rule.** Its condition (1) fails, since a provider failure or a timeout is not a named
  publication-withhold reason. So the red run blocks and is not recorded as not caused by the PR (#1955,
  issuecomment-6599963526). This file does not change that result, and no later result erases it.
- **The same head's other checks.** `eval-baseline` passed: CI 41609164854, job 125826418056, PASS with no hard
  regressions, 70 of 70 scored, 0 errors. Codex's review found nothing.

## The measurement

- **Exactly one additional full standard draw.** The unchanged `copilot-eval.yml`: 6 questions × 3 runs = 18
  attempts, on the head containing this file, whose parent is `ff15b23e`. The commit's single push while the pull
  request is ready starts it, and the workflow's once-per-head gate allows the new head one draw.
- **Unchanged.** The runtime (the backend requirements and the model configuration), the prompts, the sources (the
  golden set and its prepared sources), the harness (runner and scorers), the thresholds and the acceptance rules.
  The head's `backend/`, `frontend/`, `docs/`, `lessons/` and `.github/` trees are byte-identical to `ff15b23e`'s, and
  this folder is the only change. Both are checked before the push: the diff's names, and each tree's hash.
- **No selective-case retry, and no repeated draws until green.**

## Outcome rules

- **Green**, by the workflow's own unchanged acceptance: reported on #1955 with the head and the run links, beside
  the original red. The merge decision is the chief's.
- **Any red, for any reason**, a provider failure included: the protocol stops. It is reported on #1955 for diagnosis
  and decision, and nothing is drawn again.
- **Cancelled or void**, a superseding event included: it counts as this protocol's one draw and is reported as such.
  Nothing is drawn again.

## Spend

The push re-runs `eval-baseline` on the whole diff (USD 0.73) and draws `copilot-eval` on the new head (USD 0.06).
The USD 0.79 is reserved in #1955's body before the push (`lessons/ops-reserve-eval-baseline-before-each-push.md`).
No balance is recorded here; the chief checked it privately.
