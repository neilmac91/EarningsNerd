# Pre-registration: the Copilot citation retry on the sections source (2026-10-16)

Committed on the pull request before any paid run it causes. It fixes what the live measurement is, what makes it
valid, what accepts the change and what happens if it is red. The RUNBOOK's "Gating rule" applies: the eligibility
half is a guard change, proven offline (see [`README.md`](README.md), "Verification"). The guidance half is
model-facing text and needs a live `--runs 3` aggregate.

## The change being measured

| Composition | SHA-256 prefix | Change |
| --- | --- | --- |
| First generation (`SYSTEM_PROMPT`) | `d46ef28f000a` | unchanged |
| Retry after a decision-F rejection | `f3b340db1e35` | unchanged |
| Retry after a citation failure | `ae01453ef90d` | new: `_EVIDENCE_RETRY_GUIDANCE` + `_CITATION_EXCERPT_RETRY_GUIDANCE` |

Eligibility also changes: a short excerpt and a twice-declared referenced number may now buy the one retry.

## The measurement

This is the PR head's single `copilot-eval` draw, triggered by marking the PR ready after the high-tier review. It is
the unchanged workflow: 6 questions × 3 runs = 18 attempts, prepared through main's production path. Since #1350 that
path uses the sections source again. One draw per head (`copilot_eval_draw_gate.py`).

**Validity.** If any condition fails, the draw is not evidence for or against the change. It is reported as void and
is never replaced by drawing the same head again.
- `preparation.json`: status `complete`, `USE_EDGARTOOLS_SECTIONS` true, edgartools `5.58.0`.
- The BABA FY2025 row's source text hashes to `be4499769327`, the sections source of runs 37191781211 and 38817393205.
- Every row's first-generation system message hashes to `d46ef28f000a`.
- Every retry generation hashes to `f3b340db1e35` after a decision-F reason, or to `ae01453ef90d` after "Unverified or
  ambiguous referenced citation".

**Acceptance, the repository's unchanged bar.** `accepted: true`: 18 of 18 scored and passed, zero execution errors,
and no trust or accuracy veto.

**Readout (descriptive, not gating).** For each question, the readout records:
- the first generation's text-citation use and verify verdict;
- the retries taken, and whether each retry published;
- for BABA FY2025, the excerpt shapes.

It is set beside the corpus baselines in the README: findings 3 to 5, and the 3/3 terminal withholds of run 38817393205.

**Power, stated before the draw.** One draw holds 3 BABA FY2025 attempts.
- If the sections first generation fails as it did on 2026-10-15 (3 of 3), the draw passes BABA only if every retry
  publishes: p³ for a per-retry recovery p.
- That is 0.44 at p = 0.76 (today's generic retry on the regex fallback), 0.73 at 0.9, and 0.86 at 0.95.
- So a red draw is possible even if the change helps. A green draw shows only that recovery is not low. A single draw
  sets a direction, not an effect size.

## If the draw is red

No same-head re-draw, and no push made only to draw again (RUNBOOK triage rule; this PR changes the publication boundary,
so the triage rule's condition 2 excludes it). The artifact is classified with [`classify_corpus.py`](classify_corpus.py)
and the outcome decides the next step:

1. **BABA rows withheld after their citation retry also failed.** The guidance is not enough on the sections source. The
   PR returns to draft. The next step is the first-generation candidate in the README (a whole-row rule in
   `SYSTEM_PROMPT`), as a real code change on a new head that draws once. That candidate needs its own measurement.
2. **A row on another question is withheld or vetoed.** Its first generation is byte-identical to main's, so the cause
   must be traced in its retry generation, if any, or in the run itself. Until it is explained, the PR stays blocked.
3. **Void (an operational failure, or a validity condition above failed).** Reported to the founder, who decides whether a
   new head may draw.

## Spend

The reservation rule (CODE RED record 09) prices each run at the dearest measured comparable run times a stated factor:
- `copilot-eval`: USD 0.028449 (run 38817393205) × 2 = **USD 0.06** per draw.
- `eval-baseline`: USD 0.349055 (job 116704813130) × 1.5 = **USD 0.53** per push that changes `backend/app` or
  `backend/evals`.

This PR plans one of each, USD 0.59 reserved. The ceiling for the whole measurement is **USD 2.00**, which covers
one further head if outcome 1 above leads to the first-generation candidate.

The latest balance read was USD 36.55 on 2026-10-15 at 23:32 UTC (`deepseek-balance.yml`, job 116727558184), against
a floor of USD 5. The CODE RED ledger is the chief's. This file is the reservation record, and the PR body reports the
actual cost from `ai_call` telemetry.

## Addendum 1 (2026-10-16, after draw 1): the first-generation candidate

Draw 1 ([run 38860895429](https://github.com/neilmac91/EarningsNerd/actions/runs/38860895429)) was valid and red,
17 of 18, so outcome 1 applied. The README's "Draw 1" and "Addendum 1" sections give the reading and the change.
This addendum is committed before the new head's draw.

| Composition | SHA-256 prefix | Change from draw 1 |
| --- | --- | --- |
| First generation (`SYSTEM_PROMPT`) | `c221b7e3c5c2` | four lines: the whole-row exception and the exact-copy sentence |
| Retry after a decision-F rejection | `34d01dadbac0` | inherits the new `SYSTEM_PROMPT`; guidance unchanged |
| Retry after a citation failure | `bf240eb01f4c` | inherits the new `SYSTEM_PROMPT`; guidance unchanged |

**Measurement.** The new head's single copilot-eval draw, after the high-tier review of the new lines. It runs the
same workflow with the same 18 attempts.

**Validity.** These are the conditions above, with these hashes in place of draw 1's:
- every first generation is `c221b7e3c5c2`;
- a decision-F retry is `34d01dadbac0`;
- a citation retry is `bf240eb01f4c`.

**Acceptance.** The repository's bar: `accepted: true`, 18 of 18.

**Readout.** This adds to draw 1's readout:
- **Text-citation use per question.** AAPL, TSLA and MSFT cited no filing text in 1,170 first generations, so on
  them the new lines can only add text citations. That is reported, not gated; any such citation is checked as every
  citation is.
- **Generations that are not first generations.** Every retry is reported with its outcome.

**Record.** The RUNBOOK row's "Measured on" cell is written before this draw. Once the PR is ready, every push to
it draws again (`copilot_eval_draw_gate.py` allows one draw per head), so a commit that only added the run would buy
a second draw of the same code. If the PR merges, the run and its readout go into the README in a records-only
follow-up on main.

**If this draw is red.** No further code head goes into this PR without the founder's decision. The artifact is
classified and reported, and the ceiling's remainder stays unspent. If a question other than BABA FY2025 regresses,
the four lines are the cause, since nothing else the first generation sees changed.

**Spend.** For the drawn head: USD 0.53 reserved for `eval-baseline` and USD 0.06 for the draw. Cumulative spend stays
under the USD 2.00 ceiling. Spent before it: `eval-baseline` on `200bcddd`, USD 0.178346 plus one errored call; on
`1ccfa33f`, USD 0.356388; on `1d885415`, USD 0.353111. Draw 1: USD 0.025871. That is USD 0.913716, so USD 1.50 with
the drawn head's reservations.

## Addendum 2 (2026-10-16, after draw 2): the merge with main

Draw 2 ([run 38878772611](https://github.com/neilmac91/EarningsNerd/actions/runs/38878772611)) was valid and green,
18 of 18 with no retry (README, "Draw 2"). Before the PR could merge, main merged #1347 (E28 option 1), which conflicts
with this branch. The conflict is resolved by a merge commit. Once a PR is ready, every new head draws, so the merge head
gets its own draw. This addendum is committed in the same push, before that draw.

**What the merge head's draw is.** It is the same code measured again: the prompt bytes are unchanged, and #1347's
draw prepared byte-identical sources for all six questions (README, "Main's #1347 and the merge"). It is a requirement
for merging, not a replacement for draw 2. Draw 2 stays the pre-registered measurement, and this draw is reported beside
it.

**Validity.** These are addendum 1's conditions:
- every first generation is `c221b7e3c5c2`;
- a decision-F retry is `34d01dadbac0`;
- a citation retry is `bf240eb01f4c`;
- the six sources hash as in the README's table.

A changed source hash means #1347 or a later main change moved a source. The draw is then reported with the change named.

**Acceptance.** The repository's bar on the head that merges: `accepted: true`, 18 of 18.

**If it is red.** The PR does not merge. There is no further draw: no re-run and no push made only to draw again. The
artifact is classified and reported to the founder with draw 2 beside it, and the founder decides.

**Spend.** The reservation rule, with the dearest measured runs:
- `eval-baseline`: USD 0.362652 (on `ff6836cf`) × 1.5 = USD 0.54;
- the draw: USD 0.065977 (draw 2) × 2 = USD 0.13.

Spent so far is USD 1.342345, plus one errored call:
- `eval-baseline`: USD 0.178346, 0.356388, 0.353111 and 0.362652;
- the draws: USD 0.025871 and 0.065977.

With these reservations the total is USD 2.02, over the USD 2.00 ceiling, so the ceiling for the whole measurement
becomes **USD 2.25**. Both runs fall in off-peak hours, so the expected cost is about USD 0.25. The balance was
USD 27.53 at 16:59 UTC on 2026-10-16 (`deepseek-balance.yml`, job 117092209369), against the USD 5 floor.
