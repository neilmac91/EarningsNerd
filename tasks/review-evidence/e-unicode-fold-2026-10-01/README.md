# Item E release evidence: #1040 (2026-10-01)

#1040 makes the finite claim parsers fold case in ASCII only. It was squash-merged as `02628e57` from head `da4f66a0`.

## Paid runs

| Row | Run | Result | Cost (telemetry) |
| --- | --- | --- | --- |
| D7 | eval-baseline [36868705889](https://github.com/neilmac91/EarningsNerd/actions/runs/36868705889) | 70/70 scored, gate_fail 0, regression gate PASS. One advisory warning: mean untraceable dollar figures 2.1. | USD 0.175062 (70 calls, 0 unknown, off-peak) |
| D8 | copilot-eval [36870677818](https://github.com/neilmac91/EarningsNerd/actions/runs/36870677818) | **accepted 18/18, 0 errors**. This is the pre-stated readiness criterion. | USD 0.005800 (30 calls, 0 unknown, off-peak) |

Artifact digests:
- D7: `387746354bf261af42c90edc2f1f15942eef827b1d4a05148d26515128d65a8e`
- D8: `ad0905ad11e1cefe359be99b458f001350ed716dddb10a76f6c8668ef8ae23d5`
- D8 `copilot-eval.json`: sha256 `f385ff74…e3d5`

## Advisory prose-quote audit (D8)

The audit is `copilot-36870677818-prose-quote-audit.json`, produced by `../pr1021-qualification-2026-10-01/prose_quote_audit.py`. It exited 1. Before the ready transition this audit was declared advisory for E, because containment is item F.

- **Composed quotes:** one row, AAPL `sales-gross-profit-2025` run 2. It quotes "Total net sales 416,161" (23 characters) and "Gross margin 195,201" (20 characters). Both are **below F's 24-character floor**, so F's rule would not withhold this row either. This is a live instance of F's disclosed short-composition limit.
- **Grounding escalations:**
  - uncited answers: 0;
  - rows with one uncited figure: 4 (AAPL run 2; MSFT `sales-diluted-eps-2025` runs 0–2);
  - tool-less rows: 6.

  The D6 main-code run 36809122540 had 3 uncited-figure rows and 5 tool-less rows.
- **Not attributable to E.** None of the 18 answers contains a fold letter (İ ı ſ K) or a non-ASCII digit. E's grammars therefore behave identically to main on every answer in this run, and these rows are main-code model variance.
