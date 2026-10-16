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
