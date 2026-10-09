# Triage a red copilot-eval run by the RUNBOOK rule; never re-run it to get a green one

Date: 2026-10-09   Area: ops / evals

**Context**: On #1148 (the homepage part of the design critique; no Copilot code), `copilot-eval`'s
first attempt went red on four heads. Each time one row ended `publication withheld: Unverified or
ambiguous referenced citation`:
- BABA `viewed-native-revenue-2025` at `5fe2e49` (run 37935449192) and at `4acc25a` (37946561164);
- ASML `us-gaap-sales-net-income-2025` at `c815e69` (37943905552) and at the final head `d594ed3`
  (37958886664).

The agent re-ran two of them, `5fe2e49` and `d594ed3`. Each second attempt passed, and the PR was
merged on the second re-run's green. The other two reds were followed by pushes that changed code.

The RUNBOOK's founder-approved triage rule (2026-10-02) covered decision-F reasons only and said every
other withhold "blocks as before". It also said a run "is never re-run to obtain a green result
outside a predeclared protocol". The two re-runs broke both clauses.

The reds were not the PR's. All 17 such rows from 3 to 9 October come from two questions, where the
model cites table or KPI cells as an elided or too-short excerpt: "Revenue from third parties ...
996,347 ... 137,300", and "€32.7bn total net sales", one character under the floor. The whole-excerpt
check correctly withholds those. All four #1148 rows replay to their recorded reasons offline under
main's code. A re-run's green is a second draw from the same stochastic model, so it says nothing
about the first red.

**Rule**: When `copilot-eval` is red, read each errored row's reason in `copilot-eval.md` and apply the
RUNBOOK triage rule. Since 2026-10-09 it covers any named publication withhold, with the offline replay
and the other four conditions. Record the outcome in a PR comment either way.

Never draw again on the same code to get a green result:
- **Re-run, toggle, reopen.** Never re-run the job, toggle the PR from draft to ready, or close and
  reopen it on an unchanged head. The workflow refuses all three: it draws once per head commit, and
  a later run on a head that already drew reports that draw's verdict and spends nothing. Nothing in
  the PR body exempts a head.
- **A push only to draw again.** Never push a commit that changes nothing under `backend/` or
  `.github/` just to draw again, outside a predeclared protocol. The gate does not catch this, because
  it keys on the head commit. Gating it is follow-up 11 in
  `tasks/decisions-2026-10-09-design-followups.md`, the founder's call.

When the rule's conditions do not hold, the PR waits for a green run from a push that changes the
code, or for the founder. A predeclared protocol that needs several draws of the same code gives each
draw its own head (a commit that changes only its evidence folder), as its preregistration says.

**Evidence**: runs 37935449192 and 37958886664 (attempt 1 red, attempt 2 green, each re-run by the
agent); runs 37943905552 and 37946561164 (red, followed by pushes that changed code); #1148 merged as
`1a31b29`; the attribution and rates in `tasks/decisions-2026-10-09-design-followups.md` (decision D)
and the replays in `tasks/review-evidence/copilot-eval-triage-2026-10-09/`; the gate in
`.github/workflows/copilot-eval.yml`, `backend/scripts/copilot_eval_draw_gate.py` and
`backend/tests/unit/test_copilot_eval_rerun_refusal.py`.
