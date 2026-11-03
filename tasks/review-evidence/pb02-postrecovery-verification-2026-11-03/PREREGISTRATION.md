# Pre-registration: one post-recovery verification of PB-02's accepted code (2026-11-03)

Committed on #1955 before the paid runs it causes. This file is the only change in its commit. It names that commit as
"the head containing this file"; the head's SHA, the executed merge candidate and the run links go in #1955's
comments, never in this file.

## Authority and precondition

- **The protocol.** The founder approved **one** additional complete verification after DeepSeek reports its API
  incident resolved, within the existing per-push reservation, relayed by the chief on #1955 in issuecomment-6601934314
  (2026-11-03 10:58 UTC). It is a new, bounded post-recovery protocol. It is not a waiver and not an open-ended
  retry, and any further failure stops it.
- **The precondition.** The commit is pushed once, while the pull request is ready, and only after the chief confirms
  on #1955 that the incident is resolved and that a fresh private balance check is done. The chief confirmed it in
  issuecomment-6602189928 (2026-11-03 11:07 UTC): DeepSeek's official incident record marks recovery at 10:48 UTC,
  and root has completed the prerequisites.
- **No other change.** This file changes no source, no model, no fixture and no threshold. No review round and no
  further draw follow from it. The current head's review gate is root's.

## The record it adds to; nothing in it is erased

- **`copilot-eval` run 41609164901**, the ready mark's draw. It ran on `Merge ff15b23e into 86479c66`: 16 of 16 scored
  passed, with 2 provider timeouts.
- **`copilot-eval` run 41613482231**, the predeclared follow-up draw. It ran on `Merge ef786cb8 into 7523d61c`: 4 of 4
  scored passed, with 14 provider errors, ten of them DeepSeek 503 "Service is too busy". That protocol is
  exhausted (issuecomment-6600507820, issuecomment-6601934314).
- **The same push's `eval-baseline`** (job 125840992448) failed on 22 execution errors, all DeepSeek 503s; its 48
  scored outputs showed no quality regression (issuecomment-6600744817).

## The verification

- **The runs.** The push's `copilot-eval` draw on the head containing this file, whose parent is `ef786cb8`: the
  unchanged workflow and its full fixtures (6 questions × 3 runs = 18 attempts), at the ordinary thresholds and
  acceptance. The same push's `eval-baseline` runs on the whole diff, at the ordinary thresholds.
- **What they execute.** Both run on the pull request's merge candidate, which is `actions/checkout`'s default for a
  `pull_request` event, not on its head alone. The exact executed merge candidate, its commit and its base, is read
  from each run's log and recorded on #1955 with the outcomes. **This is not an identical-runtime comparison with any
  earlier draw**: main's merges since those draws are part of what runs.
- **What does not change.** The head's `backend/`, `frontend/`, `docs/`, `lessons/`, `.github/`, `.claude/` and
  `ops/` trees stay byte-identical to `ff15b23e`'s, which the chief accepted, and against its parent `ef786cb8` this
  folder is the only change. Both are checked before the push.

## Outcome rules

- **Complete success**, meaning `copilot-eval` accepted and `eval-baseline` PASS by their ordinary rules: reported on
  #1955 with the head, the executed merge candidate and every run link. The decision is the chief's and the founder's.
- **Any failure, for any reason**, a provider failure included: the protocol stops. It is reported on #1955 with all
  outcomes, and nothing is drawn again.
- **Cancelled or void**, a superseding event included: it counts as the one verification and is reported as such.

## Spend

The push re-runs `eval-baseline` on the whole diff (USD 0.73) and draws `copilot-eval` on the new head (USD 0.06):
USD 0.79, the existing per-push reservation. It is recorded in #1955's body before the push
(`lessons/ops-reserve-eval-baseline-before-each-push.md`). No balance is recorded here; it is checked privately.
