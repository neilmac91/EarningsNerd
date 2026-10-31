# #1039 (item B) merge condition 2: source review of every changed returns line in the hosted 70-run

**What this is.** An offline, provider-free check: no network, provider keys unset. It covers every rendered `value_drivers.returns_on_capital` line in B's hosted `eval-baseline` report, checked against that run's own retained `xbrl_grounding` operands.

**Inputs.**
- **Hosted run:** CI [36993299710](https://github.com/neilmac91/EarningsNerd/actions/runs/36993299710), on head `583b9f8a`. The harness source is `fdbea0fb`, the PR merge ref with parents `f6e79a50` and `583b9f8a`; its tree `1a7f5def` is identical to `583b9f8a`'s.
- **Artifact:** `eval-report-36993299710`, zip sha256 `83437857…` (equal to GitHub's artifact digest). The report `eval_20261002T101321Z.json` has sha256 `08672385ce1490a67a4b08c90af25d1fdc9d8ae7b64dadba261078eb43371d2c`.
- **Run result:** 70/70 scored, pass_rate 1.0, gate_fail 0, errors 0, regression gate PASS.

**Tool.** `revalidate.py`, sha256 `90e0b98d…`. It ran from a clean worktree detached at `583b9f8a`, which was still clean, including ignored files, afterwards. Main's renderer is a `git archive` of `f6e79a50` (`backend/`), rendered in a subprocess. Run as:

```
python revalidate.py eval_20261002T101321Z.json hosted-36993299710.json \
  --main-backend <archive of f6e79a50>/backend --main-label "git archive f6e79a50 backend"
```

The full method is in the script's docstring. For each result it re-renders `raw_sections` with the result's own grounding, under both B and main. Then:
- the hosted field and the hosted Markdown line must equal B's re-render, byte for byte;
- each ratio clause is parsed and compared with its point's own operand copies for value, operand periods, numerator duration and scope label;
- each prior must render dated, carry the correct date, and stay in band.

## Result: exit 0, 0 failures, 0 warnings (`hosted-36993299710.json`, sha256 `cd001668…`)

| Check | Result |
| --- | --- |
| Grounding block, main vs B | identical in 70 of 70 |
| Returns lines changed vs main | 64 of 64 lines; the 6 6-K results (ASML, SE, PDD ×2) have no line on either side |
| Other section fields / other Markdown lines changed | 0 / 0 |
| Hosted field equals B's re-render | 70 of 70 |
| Hosted Markdown line equals the re-render | 70 of 70 |
| Ratio clauses checked | 126: value recomputed from operands 126, stored value matches 126, scope label matches the numerator concept 126, operand periods match 126 |
| Numerator scope | attributable to the parent: 56 lines; including noncontrolling interests: 8 (concepts `us-gaap:NetIncomeLoss` 110, `ifrs-full:ProfitLoss` 8, `us-gaap:ProfitLoss` 8 clauses) |
| `(numerator scope unestablished)` clauses | **0**; none to list. A hosted eval extracts fresh, so it never reaches the 58-snapshot legacy population (see below) |
| Priors | 92 prior points. 90 render dated with the correct date, value, operand periods and duration class. 2 are dropped out of band (GPRO 10-K ×2, prior ROE −285.0%), the same as main. 0 are dropped as undated |
| Sequential priors | 2 (FIGS 10-Q ×2, ROE, 91 days), both reading `prior at 2026-03-31: 1.5%`, dated and not YoY |
| Prior gaps (days) | 365: 80, 364: 8, 91: 2 |
| Prior-basis notes | 0 needed; 90 of 90 correct |

These counts reproduce, line for line, the offline replay of the retained r report (`dryrun-r-deaa1b52.json`: 64 lines, 126 clauses, the same scope split and the same gaps). The hosted run is therefore consistent with the pre-merge evidence.

## Validation of the tool (before this run)

- **Dry run** on the retained r report (`deaa1b52`) reproduces every count in B's `replay-r-returns.json` and all 126×21 per-clause fields.
- **Negative controls** (`negctl.py`, `negctl.log`): 21 of 21 caught. They cover:
  - hosted-field and Markdown tampering;
  - a date-guard mutation whose hosted output equals its re-render;
  - mis-dated, undated and out-of-band priors;
  - duration, basis-note, scope and operand tampering.

## Census population, not covered here

The 58 untagged retained snapshots, 47 of them with summaries (#1029 comment 5942525078), are not exercised by a hosted eval or by this check, because both extract fresh. B renders those lines as the truthful `(numerator scope unestablished)`. The exact-head review simulated that by stripping operands: 64 of 64 render the unestablished scope. No drain or refresh is authorized.

## Spend

Ledger row D13: off-peak 10:03–10:13Z; 70 calls, 0 unknown; tokens × off-peak pricing = **USD 0.173515**, within B's 0.75. The balance went from 45.24 (10:02:49Z) to 45.06 (10:16:59Z).
