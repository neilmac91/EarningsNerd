# Triage a red copilot-eval run by the RUNBOOK rule; never re-run it to get a green one

Date: 2026-10-09   Area: ops / evals

**Context**: On #1148 (the homepage part of the design critique; no Copilot code), `copilot-eval`
went red twice, each time with one row `publication withheld: Unverified or ambiguous referenced
citation`: BABA `viewed-native-revenue-2025` at `5fe2e49` (run 37935449192), and ASML
`us-gaap-sales-net-income-2025` at the final head `d594ed3` (run 37958886664). Both times the agent
re-ran the job, the second attempt passed, and the PR was merged on the second re-run's green. The
RUNBOOK's founder-approved triage rule (2026-10-02) covered decision-F reasons only, said every other
withhold "blocks as before", and said a run "is never re-run to obtain a green result outside a
predeclared protocol". Both clauses were broken. The reds were not the PR's. All 17 such rows from 3
to 9 October come from two questions, where the model cites table or KPI cells as an elided or
too-short excerpt ("Revenue from third parties ... 996,347 ... 137,300"; "€32.7bn total net sales",
one character under the floor). The whole-excerpt check correctly withholds those. Both #1148 rows
replay to the same reasons offline under main's code. A re-run's green is a second draw from the same
stochastic model, so it says nothing about the first red.

**Rule**: When `copilot-eval` is red, read each errored row's reason in `copilot-eval.md` and apply the
RUNBOOK triage rule. Since 2026-10-09 it covers any named publication withhold, with the offline replay
and the other four conditions. Record the outcome in a PR comment either way. Never re-run the job,
and never toggle a PR from draft to ready on an unchanged head to draw again, outside a predeclared
protocol. When the rule's conditions do not hold, the PR waits for a green run from a new push, or for
the founder. The workflow now draws once per head commit: a re-run attempt, a toggle or a reopen on a
head that already drew reports that draw's verdict and spends nothing. A predeclared protocol draws
again only by naming its committed preregistration in the PR body (`Copilot-eval protocol: <path>`).

**Evidence**: runs 37935449192 and 37958886664 (attempt 1 red, attempt 2 green, each re-run by the
agent); #1148 merged as `1a31b29`; the attribution and rates in
`tasks/decisions-2026-10-09-design-followups.md` (decision D) and the replays in
`tasks/review-evidence/copilot-eval-triage-2026-10-09/`; the gate in
`.github/workflows/copilot-eval.yml`, `backend/scripts/copilot_eval_draw_gate.py` and
`backend/tests/unit/test_copilot_eval_rerun_refusal.py`.
