# Analysis candidate 2: hold, stop paid prompt iteration

27 September 2026. Exact candidate `a87de702fce943fdb04eb5dedaf4dfc22c85cfca`. This is Codex/Astra engineering review of retained outputs, not Fable judging or E7 acceptance.

All 12 prescribed outputs completed in 24 physical DeepSeek Flash calls, every call ended `stop`, no error events, no missing usage. Conservative reservations were USD 0.2206425 within the USD 1 / 36-call ceiling. Uncached peak-rate usage estimate is USD 0.0437847; invoice charge is unknown. The [public custody summary](analysis-second-candidate-hold.json) pins the private per-call audit and retained output hashes. No redraw occurred.

## What worked

All six threshold diagnostics distinguish the unrounded current ratio correctly: reconstructed AAPL 1.0032948047 remains above one, synthetic 0.996 is below one, synthetic 1 is equal. This is a narrow six-output finding, not overall quality clearance. Their surrounding prose still has weaknesses (for example AAPL draw 1 says current liabilities and assets grew by roughly the same amount despite a USD 8.981B working-capital reduction).

The explicit missing-period citation in the previous JPM quarterly output is absent in this retained result. Some previous derived percentages and forecasts also disappeared. These are unmatched draws; a causal improvement is not established.

## Release-blocking findings

Root read all twelve completed narratives and the six real-output citation lists. A full 30-binding pass was not repeated once multiple independent semantic blockers established the prewritten hold condition. No complete narrative fidelity score is claimed.

| Output | Retained claim and source | Refutation 1 | Refutation 2 | Outcome |
| --- | --- | --- | --- | --- |
| WMT annual | FCF USD 14.9B is said to comfortably exceed NI USD 21.9B on a conversion basis. Dataset values are 14.923B and 21.893B. | FCF growth 17.9% exceeds NI growth 12.6%, but the sentence explicitly compares the dollar levels. | Both operand citations are genuine; that cannot make the inequality true. Conversion is below one. | Material cash-quality inversion remains. |
| GOOGL annual | OCF growth 31.5% is called comfortably ahead of NI growth, earlier given as 32.0%. | OCF level exceeds NI level; the sentence explicitly says growth. | Rounding cannot reverse the roughly half-point difference. | Wrong direction of comparison. |
| JPM annual | FY2025 equity 362.4B is followed by citations 18 and 19: FY2024 equity 344.758B and two-year CAGR 5.1%. | The FY2025 number does exist in the dataset, so the number itself is not fabricated. | Neither displayed marker supplies that FY2025 amount; a CAGR cannot replace the missing period/value citation. | Real period/value citation mismatch. |
| JPM quarterly | Profit growth allegedly outpaced noninterest income in both quarters: 27.1% vs 17.6%, then 28.3% vs 30.1%. | First quarter passes, second fails; the statement says both. | Source figures and rates are correct; the relation is false even with all automated counters at zero. | Deterministic citation checks do not establish semantic truth. |
| JPM quarterly | Watch for 2026Q2 cash-flow and EPS gaps to be filled. | Q2 cash flow is missing, but diluted EPS is present at 7.70, marker F18, official Q2 10-Q accession 0001628280-26-054343. | Q4 EPS is missing, but the watch clause explicitly names 2026Q2. | Missing-data claim names the wrong period/concept. |

The new uncited-figure detector also warns on threshold constants such as 1.00x, so counter totals require interpretation. They are warning telemetry, not a release score.

## Decision and next engineering step

Do not push or release the combined candidate. Keep production prompt/cache version `trends-v4`; preserve the candidate, both paid runs and all failed outputs. Do not buy a third prompt draw to seek a favorable answer.

A warning-only extraction would be technically separable, but would not fix false comparisons and would add uncalibrated warnings. It is not the next release priority. Finish source-first Risks and operational recovery/export work first.

The next Analysis design should make numerical assertions a data-owned surface: period-labelled observations, exact operands, sign/threshold/comparison results and citations rendered from the dataset. A model may select or explain an approved observation, but must not independently invent its arithmetic or period binding. Qualitative causes need explicit evidence or must remain questions. Before another paid measurement, demonstrate the five failures above cannot be emitted through the chosen representation, including counterexamples and absence claims. Keep the existing Analysis route, entitlement, dataset service and PDF flow; do not build a second pipeline. This is a proposed bounded design, not implemented or accepted quality evidence.
