# G stage 1: is main's 20-F tool nonexecution caused by #1022's step-3 wording?

This is item G of the delegated decision on #1029 (comment 5925688598): "#1036 stage 1 only, USD 1.00, after B and E. Check prepared inputs offline before paying; a mismatch stops the lane." The design, the validity precondition and the decision rules were pre-registered in `tasks/copilot-tool-nonexecution-2026-09-30.md` on #1036 before any spend, and they were applied unchanged.

## Arms and runs

The arms are:
- **Arm A** is the main prompt (`a88b6fb1`), run on #1036 at `a35e8342`, which is main `287d018d` merged.
- **Arm C** is main plus the pre-#1022 step-3 line, verbatim (`93dc6565`), run on #1053 at `9041f04a`. That PR is an experiment and is closed unmerged.

The four runs were interleaved A, C, A, C and finished within 20 minutes, all off-peak. Each run started only after the previous one completed.

| Run | Trigger | CI run | Artifact zip sha256 | Cost (USD) | Usage-bearing service events |
| --- | --- | --- | --- | --- | --- |
| A1 | #1036 ready 11:58:04Z | [37003942265](https://github.com/neilmac91/EarningsNerd/actions/runs/37003942265) | `eb5b7959…` | 0.005384 | 17 |
| C1 | #1053 ready 12:04:53Z | [37004589548](https://github.com/neilmac91/EarningsNerd/actions/runs/37004589548) | `d3dc6fb2…` | 0.006006 | 14 |
| A2 | #1036 draft→ready 12:10:20Z | [37005114216](https://github.com/neilmac91/EarningsNerd/actions/runs/37005114216) | `566c8b60…` | 0.005330 | 18 |
| C2 | #1053 draft→ready 12:14:50Z | [37005546506](https://github.com/neilmac91/EarningsNerd/actions/runs/37005546506) | `13ddcd86…` | 0.006460 | 15 |

Opening #1053 also ran one `eval-baseline` (D18, USD 0.177645), because the arm changes `backend/app`. It is not part of the measurement. **G spent USD 0.200825 in total, against a 1.00 reservation.**

**Correction, 2026-10-02.** The costs above sum usage from service events only, so they miss the provider calls behind withheld rows. Counting every provider call in each `runner.log` gives the following (`../g-stage2-2026-10-02/copilot_cost_runnerlog.txt`):

| Run | Cost (USD) |
| --- | --- |
| A1 | 0.005853 |
| C1 | 0.007619 |
| A2 | 0.005330 |
| C2 | 0.007807 |

Stage 1 totals **USD 0.204254**. The 1.00 ceiling is unaffected.

## Retained inputs

The raw `copilot-eval.json` files are about 10 MB each and are not committed. Each run's zip is a GitHub artifact, and its digest equals the sha256 above:

| Run | Artifact id | Expires |
| --- | --- | --- |
| A1 | `11224618474` | 2026-12-31T11:58:04Z |
| C1 | `11225536799` | 2026-12-31T12:04:54Z |
| A2 | `11225252695` | 2026-12-31T12:10:20Z |
| C2 | `11225578263` | 2026-12-31T12:14:51Z |

Item A's preservation manifest predates these runs and does not include them. Keeping them past their expiry needs the same founder-side tool.

The tool outputs are committed here:
- `g_precheck.txt`: per-run hash tallies (18 rows each), fingerprints per run, and the sha256 of each input. The script's own `fingerprints` field is `{}`, because service events do not carry `system_fingerprint`. The fingerprint counts come from each artifact's `runner.log`, extracted with `grep -o '"system_fingerprint": *"[^"]*"' runner.log | sort | uniq -c`;
- `g_decide.txt`: draw patterns and question-run counts;
- `copilot_cost.txt` and `copilot_cost.py`: cost per run.

The decision rules are quoted from `tasks/copilot-tool-nonexecution-2026-09-30.md` on draft branch `claude/pr1023-diagnostic` at `a35e8342` (#1036).

## Validity precondition: all four runs valid

`g_precheck.py` checks every row; the hashes are sha256 prefixes per the design. All 72 of 72 rows matched:

| Field | Expected value | Match |
| --- | --- | --- |
| System prompt | `a88b6fb1` (arm A), `93dc6565` (arm C) | 18/18 in each run |
| Contexts | AAPL `db033e5a13d4`, TSLA `3babd16a34cf`, MSFT `b552352b2af3`, BABA native-2026 `6db10712e780`, BABA viewed-2025 `be263a712053`, ASML `09e857dbd1b9` | 6/6 in every run |
| Tool schema | `b6958973` | every row |
| Generation options | deepseek-flash, 2400, 0.2 | every row |

The provider fingerprint was `aeb56401…` on all 129 logged calls (30, 35, 28 and 36 per run), so there was no provider-side change.

## Result (`g_decide.py`): prompt-caused

A question-run is tool-using when at least 2 of its 3 draws call a tool.

| Run | ASML | BABA native | BABA viewed | 20-F tool-using | 10-K tool-using | Draws with tools |
| --- | --- | --- | --- | --- | --- | --- |
| A1 | T-T | --- | --T | 1/3 | 3/3 | 12/18 |
| A2 | -T- | --- | --- | 0/3 | 3/3 | 10/18 |
| C1 | TTT | TT- | TTT | 3/3 | 3/3 | 17/18 |
| C2 | TTT | TTT | TTT | 3/3 | 3/3 | 18/18 |

**Totals by arm:**

| Arm | 20-F question-runs | 20-F draws with tools | 10-K question-runs | 10-K draws with tools |
| --- | --- | --- | --- | --- |
| A | **1/6** | 4/18 | 6/6 | 18/18 |
| C | **6/6** | 17/18 | 6/6 | 18/18 |

**The rule that applies** is "Prompt-caused: C ≥ 5/6 and A ≤ 2/6". Both arms match their records (pre-#1022 17/18, main 1/9), so the recorded contrast reproduces within one window. Neither arm is below 6/6 on 10-K, so no regression is recorded. **Stage 2 needs new authorization.** Its design: arm B is main minus the clause "including when all cited figures use tool markers", interleaved with A.

## What the checks recorded (context, not part of the decision rule)

Arm C restores tool use, but **it is not a fix candidate as it stands.** Its answers more often compose or elide prose quotations, which decision F withholds.

| Arm | Published | F-withheld | Other execution errors |
| --- | --- | --- | --- |
| A | 35/36 | 1 (A1 ASML d0, composed quotations) | 0 |
| C | 29/36 | 6 | 1 |

Arm C's withheld and errored rows:
- **ASML (5 of 6 draws):**
  - `quotation_not_in_source` in 3 draws (C1 d0; C2 d0, d2);
  - two `elided_quotation` each in 2 draws (C1 d1, d2).
- **BABA viewed C2 d1:** `elided_quotation`.
- **BABA native C1 d2:** a tool-less answer with an `Invalid citation declaration`, the existing referenced-citation path, not F.

Arm C would therefore fail the design's fix-candidate acceptance checks 3–5 (ASML, composed-quote audit, 18/18 with 0 errors).

The offline F attribution (`f_attribution.py`, sha256 `a88162d7…`) exits 0 on every run, with **0 UNEXPLAINED** and 0 published rows that F would withhold. A2's 8 replay mismatches are the 8 tool-less 20-F draws. In those, the server-side uncited-claim repair made a `get_financial_fact` lookup that the run does not record; this is a known limit of the replay tool.

## Files

- `g_precheck.py`, `g_decide.py`: the precondition and decision tools.
- `A1-37003942265-f-attribution.json`, `C1-37004589548-f-attribution.json`, `A2-37005114216-f-attribution.json`, `C2-37005546506-f-attribution.json`: the per-row F attribution for each run.
