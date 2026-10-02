# F1 measurement: three predeclared copilot-eval runs on #1049 head `89bd1e12` (2026-10-02)

The measurement plan was predeclared in the #1049 body before the ready transition. Each run produced 18 rows (`--runs 3`), and the three runs were made in sequence, each started only after the previous one completed. All three were off-peak. All outcomes are retained here.

| Run | Trigger | copilot-eval.json sha256 | Rows | F withheld | Published rows F would withhold | Chips checked / failing | Attribution | #1021 audit |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1, [36963789557](https://github.com/neilmac91/EarningsNerd/actions/runs/36963789557) | ready, 04:15:53Z | `aec28008…` | accepted 18/18, 0 errors | 0 | 0 | 54 / 0 | exit 0, 0 UNEXPLAINED | exit 2: composed 0, no-source 0, uncited answers 0 → policy PASS |
| 2, [36964503116](https://github.com/neilmac91/EarningsNerd/actions/runs/36964503116) | draft→ready, 04:25:40Z | `20492c44…` | accepted 18/18, 0 errors | 0 | 0 | 54 / 0 | exit 0, 0 UNEXPLAINED | exit 2: composed 0, no-source 0, **uncited answers 1 (ASML us-gaap-sales-net-income-2025 d1)** → founder escalation |
| 3, [36965303868](https://github.com/neilmac91/EarningsNerd/actions/runs/36965303868) | draft→ready, 04:36:41Z | `b161b0f6…` | accepted 18/18, 0 errors | 0 | 0 | 54 / 0 | exit 0, 0 UNEXPLAINED | exit 2: composed 0, no-source 0, uncited answers 0 → policy PASS |

## Totals

- **Withheld:** 0 of 54 rows and 0 of 3 runs. On main's code the same rule would have withheld 4 of 126 rows, in 4 of 7 runs.
- **Prose quotations:** 0 composed quotations on any surface in all 54 rows; 162 chips checked; 0 not-disclosed rows (S3 is unmeasured here).
- **Replay mismatches:** 22 in total, all on published rows. All share one known cause: the repair lookup is not recorded. None affects attribution, because no row was withheld.
- **Advisory audit rows, recorded and not policy failures:**
  - MSFT sales-diluted-eps: 1 of 3 figures uncited, in every run;
  - BABA and ASML: tool-less but fully cited answers.

## The one escalation: run 2, ASML d1

The answer reads: "For the year ended December 31, 2025, ASML reported total net sales of €32,667.3 million and net income of €9,609.4 million, both in euros."

| Property | Value |
| --- | --- |
| Tool results | 0 |
| Citations | 0 |
| Score | `passed` (numeric_recall 1.0, figure_coverage 0.0) |
| Quotation | none |

**F is not involved:**
- Replaying the row under F's code reproduces the published terminal event (fidelity True).
- F's check found nothing on the answer or on any of the 3 chips.
- F can only withhold a response. It cannot remove a citation or skip a tool call.

**The same row and class occurred on main's code** in run 36777581481 (D1, ASML d1 uncited answer).

**Why this is an escalation.** Under the #1021 pre-registered audit policy, an uncited answer is "founder decides, never an automatic pass". So F1's clause "every other row passes the unchanged applicable scoring/audit" is not established automatically, and F is held unmerged pending a founder or Codex decision.

**Resolved (2026-10-02 08:10Z).** The founder ruled that this escalation does not block F1 (#1029 comment 5947962998). F was merged as `f6e79a50` and deployed as `00429-vlm`, verified.

## Spend

| Row | Item | USD |
| --- | --- | --- |
| D9 | eval-baseline | 0.181062 |
| D10–D12 | the three copilot-eval runs | ≈0.005430, 0.005234 and 0.005282 |
| | **F total** | **0.197008** of the 0.75 reservation |

The shared remainder is 8.882130. The balance went from 45.44 at 04:00:58Z to 45.24 at 04:48:00Z.

## Method

- Each artifact was processed by `scratchpad/f1_process.sh` on the F head `89bd1e12`, using:
  - `prose_quote_audit.py` (from `../../pr1021-qualification-2026-10-01/`);
  - `f_attribution.py` (`../f1-attribution-2026-10-02/`, sha256 `a88162d7…`), always run with an explicit `--out`.
- The cost method uses off-peak tokens × llm_pricing over the service events that carry usage. Applied to D8, it gives 0.005803 against the recorded 0.005800.
