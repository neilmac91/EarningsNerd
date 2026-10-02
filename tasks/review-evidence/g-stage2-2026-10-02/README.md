# G stage 2: does removing the step-3 clause restore 20-F tool use?

This stage was pre-registered in `tasks/copilot-tool-nonexecution-2026-09-30.md` ("Stage 1 outcome and stage 2 pre-registration"), committed on #1036 at `592d2541` before any stage-2 spend. The founder authorized it on 2026-10-02 ("Go with your recommendation on all open points"). Ceiling: USD 0.50, hard stop. Stage 1 is in `../g-stage1-2026-10-02/`.

## Arms and runs

**The arms:**
- **Arm A** is the main prompt `a88b6fb1`, run on #1036 at `592d2541`. That head is main `06ad809a` merged, so its `backend/app` equals main's.
- **Arm B** is main minus `", including when all cited figures use tool markers"` (51 characters at offset 2914), giving `16457055`, 5006 characters. It ran on #1054 at `e37d71da` (DO NOT MERGE), which is closed unmerged.

`g2_prompt_hash.txt` shows both hashes, computed by `g2_prompt_hash.py` from each tree's `SYSTEM_PROMPT` and `_build_messages()[0]`.

**The runs**, interleaved, each starting only after the previous one completed, 15:41–15:54Z, all off-peak:

| Run | Trigger | CI run | Artifact zip sha256 | Cost (USD) | Usage-bearing service events |
| --- | --- | --- | --- | --- | --- |
| A3 | #1036 ready | [37028750965](https://github.com/neilmac91/EarningsNerd/actions/runs/37028750965) | `2faf7318…` | 0.005905 | 18 |
| B1 | #1054 ready | [37029156902](https://github.com/neilmac91/EarningsNerd/actions/runs/37029156902) | `9fd89c2a…` | 0.032404 | 16 |
| A4 | #1036 draft→ready | [37029566102](https://github.com/neilmac91/EarningsNerd/actions/runs/37029566102) | `c0341064…` | 0.005491 | 18 |
| B2 | #1054 draft→ready | [37029964566](https://github.com/neilmac91/EarningsNerd/actions/runs/37029964566) | `e2b18a1f…` | 0.006103 | 16 |

**Cost notes:**
- B1 was the first call on the new prompt prefix. Its 183,459 cache-miss tokens, against about 5,800 in the other runs, explain its cost.
- Opening #1054 also ran one `eval-baseline` ([37028722712](https://github.com/neilmac91/EarningsNerd/actions/runs/37028722712): 70/70, USD 0.177093), which is not part of the measurement.
- **Stage 2 total: USD 0.226996 of 0.50.**

**Retained inputs.** The artifacts are `11236272278` (A3), `11236178105` (B1), `11236238450` (A4) and `11237206469` (B2), all expiring 2026-12-31. The full input digests are in `g2_precheck.txt`.

## Validity precondition: all four runs valid

The stage-1 `g_precheck.py` checked every run; its output is in `g2_precheck.txt`.
- **System prompt:** `a88b6fb1` in 36 of 36 arm-A rows and `16457055` in 36 of 36 arm-B rows.
- **Contexts:** all six equal the recorded values in every run.
- **Tool schema and options:** `b6958973` and deepseek-flash/2400/0.2 on every row.
- **Fingerprint:** `aeb56401` on all 131 logged calls (31, 36, 29 and 35 per run).

## Result (`g2_decide.txt`): clause-caused

| Run | ASML | BABA native | BABA viewed | 20-F tool-using | 10-K tool-using | Draws with tools |
| --- | --- | --- | --- | --- | --- | --- |
| A3 | --T | T-- | TT- | 1/3 | 3/3 | 13/18 |
| B1 | TTT | TTT | TTT | 3/3 | 3/3 | 18/18 |
| A4 | --- | --- | T-T | 1/3 | 3/3 | 11/18 |
| B2 | -TT | TTT | TTT | 3/3 | 3/3 | 17/18 |

**Arm totals:**

| Arm | 20-F question-runs tool-using | 20-F draws with tools | 10-K question-runs tool-using |
| --- | --- | --- | --- |
| A | **2/6** | 6/18 | 6/6 |
| B | **6/6** | 17/18 | 6/6 |

**Rule 2 applies:** "B ≥ 5/6 and A ≤ 2/6, clause-caused". The rules ahead of it do not fire: drift requires A ≥ 5/6, and A is 2/6. Neither arm is below 6/6 on 10-K, so no regression is recorded.

## Recorded alongside, not part of the decision

**Withheld rows.** `f_attribution.py` (sha256 `a88162d7…`) ran per run against that arm's own code. Each run exits 0, with 0 UNEXPLAINED and 0 published rows that F would withhold. Outputs: `*-f-attribution.json`.

| Arm | Published | Withheld by F |
| --- | --- | --- |
| A | 36/36 | none |
| B | 32/36 | 4 |

Arm B's four:
- B1 ASML d1 and d2: `quotation_not_in_source` ×2 each;
- B2 ASML d2: `quotation_not_in_source` ×2;
- B2 BABA viewed d1: `elided_quotation`.

The replay mismatches (A3 5, A4 7, B2 1) are tool-less draws where the server-side uncited-claim repair made an unrecorded lookup. This is the known limit, the same as stage 1.

**Arm B against the fix-candidate acceptance checks** in the diagnosis, over these two runs:

| Check | Result |
| --- | --- |
| 1. MSFT string-ID rejections | 0 (passes) |
| 2. AAPL/TSLA/MSFT tool use | 18/18 (passes) |
| 3. ASML | fails: withheld in 3 of 6 draws |
| 4. Composed-quote audit | fails: 4 rows |
| 5. Formal acceptance | fails: 16/18 with 2 errors in each run |

So arm B is **not a fix candidate** as it stands.

**ASML is withheld only on tool-using draws.** Across all eight G runs (stage 1 and stage 2, 144 rows):
- 11 rows were withheld by F, all of them on draws that called a tool;
- on ASML, 9 of 15 tool-using draws were withheld, and 0 of 9 tool-less ones.

The tool-using answer states the tool figures, then adds a narrative cross-check that quotes a table row with its other cells removed. Its JSON citation excerpt is the full, verified row. Restoring tool use therefore raises F withholding unless the answer prose also stops composing quotations.

**Next step, not authorized here:** one fix candidate combining arm B's deletion with an answer-text quotation rule. Quote only text copied contiguously from the filing, never a table row with cells removed, and state figures without quote marks. It would be judged against checks 1–5 with RUNBOOK's aggregates of at least three runs, under its own authorization and ceiling.

## Files

| File | Content |
| --- | --- |
| `g2_prompt_hash.py`, `g2_prompt_hash.txt` | Arm prompt hashes |
| `g2_precheck.txt` | Precondition tallies, fingerprints and input digests (`../g-stage1-2026-10-02/g_precheck.py`) |
| `g2_decide.txt` | Draw patterns and counts (`../g-stage1-2026-10-02/g_decide.py`) |
| `copilot_cost.txt` | Per-run cost (`../g-stage1-2026-10-02/copilot_cost.py`) |
| `A3-…`, `B1-…`, `A4-…`, `B2-…-f-attribution.json` | Per-row decision-F attribution |
