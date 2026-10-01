# PR #942 successor: deterministic return-ratio render (30 September 2026)

This branch (`claude/pr942-successor`, from main `c13b069a`) carries only the deterministic,
render-only part of [#942](https://github.com/neilmac91/EarningsNerd/pull/942), under the new content
stamp `summary-2026-09-t`. It follows the "next implementation tranche" in the
[p/q Fable disposition](../pr942-fable-2026-09-27/README.md): date the actual ratio comparator
(FIGS), keep issuer ROE/ROA intact beside the formula line (JPM), and name numerator scope only
where the selected source concept supports it (WMT). This record is engineering evidence. It is
not semantic acceptance, a Fable verdict or an adoption of q or r. #942 will be closed as
superseded by the orchestrator.

## What changes

The code-rendered `value_drivers.returns_on_capital` line changes on every surface (web, Markdown,
PDF and CSV all project the same field):

- Main renders: `Return on equity was 6.4% (prior 1.5%) (period net income / period-end equity, not annualized); return on assets 4.9% (...)`.
- The successor renders: `Period net income attributable to the parent / period-end equity, not annualized: 6.4% (prior at 2026-03-31: 1.5%); period net income attributable to the parent / period-end assets, not annualized: 4.9%.`

Each derived ratio is named by its formula and by the scope of that point's own selected
net-income concept. If the concept is missing or custom, the line says
`(numerator scope unestablished)`, which the shared projection does not treat as a placeholder.
The comparator gives the actual date of the prior point it uses. A prior without a usable date
is left out, while the current ratio still renders. When the prior point's scope differs from
the current point's, the prior clause adds its own basis. Prior selection, arithmetic, the ±200%
band and the positive-denominator rule are unchanged.

Each derived ratio point now keeps copies of its own numerator and denominator operands in the
standardized metrics (`xbrl_service.py`, ratio loop). That prevents the render from borrowing the
standalone net-income prior when a missing balance skips it. The net-income scope map moves to
`app/services/financial_basis.py`. `cash_claims` uses it without any behavior change.

## What does not change (model-facing bytes)

- **Grounding block.** Called without a point, `return_ratio_basis` returns main's exact text. The
  labels stay `Return on Equity` / `Return on Assets` with main's `basis:` suffix. A test compares
  the whole block for an operand-bearing fixture with main's captured output
  (`test_return_ratios_own_their_selected_operands_across_periods`). The offline replay below found
  70/70 identical blocks on real retained metrics.
- **Copilot.** Copilot JSON-dumps the raw `Filing.xbrl_data`. #942's `:463` hunk added `raw_tag` to
  equity/assets instance points, and that hunk is not ported. The real-producer test asserts that
  those raw points keep main's exact key set (`period`, `value`, `form`, `accn`, `currency`), so an
  added key under any name fails it, not only `raw_tag`. Operand copies exist only in the
  standardized metrics, which Copilot does not read. FinancialFact rows read only named point keys.
- The prompt text, form prompts, ONE-HOME rule, `summary_schema`, flags, `baseline_scores.json`,
  the golden set, scorers, judge code (`JUDGE_CONTRACT_VERSION`) and locked contract tests are all
  unchanged. The cash labels and debt wording are also unchanged.
- **Eval-side inputs that do change.** The eval harness JSON-dumps the standardized metrics, and
  the operand copies go with them into three places:
  - the judge's XBRL block (`evals/runner.py:214`, read at `judge.py:148`);
  - the candidate-arm generator prompt (`_xbrl_to_text`, `runner.py:84-90`, used at `:478`);
  - re-judging of retained grounding (`judge_report.retained_grounding`, which the weekly
    strong-judge readout also uses).

  On the 64 grounded rows of the retained r report, the judge's XBRL text grows by 13.7% on
  average and 20.9% at most. The largest is 25,298 characters, under the 40,000 cap. The copies
  only repeat points already in the same JSON. The r-era `retained-p-precheck.json` lists this
  delta under `allowed_r_xbrl_deltas.return_ratio_points`. Any later semantic comparison should
  judge both arms on the same runtime.
- The rendered line is produced after the primary and recovery model calls have finished
  (`_assemble_structured_summary`). It is a code-owned slot that figure-trace and the attribution
  scans exclude.

## Lineage and retained decisions

| Item | Durable link |
| --- | --- |
| q head (formula labels) | [`accb5a3e`](https://github.com/neilmac91/EarningsNerd/commit/accb5a3eba0d9072777a6df52fe7c9a2aa79fbff) |
| r dated-comparator head | [`1ec2546f`](https://github.com/neilmac91/EarningsNerd/commit/1ec2546fc655c0fc6793602f0b7b6cd33b25e730) |
| r code head | [`e17b6b63`](https://github.com/neilmac91/EarningsNerd/commit/e17b6b6309c61399541244f72435c25163c602e3) |
| r evidence head (measured) | [`47d040aa`](https://github.com/neilmac91/EarningsNerd/commit/47d040aa53e89d2e1fa78c26ee688d5a49338133); merge-base `b63bee6b` |
| r evidence (branch-only) | [financial-candidate-r-2026-09-27](https://github.com/neilmac91/EarningsNerd/tree/47d040aa53e89d2e1fa78c26ee688d5a49338133/tasks/review-evidence/financial-candidate-r-2026-09-27), [return-ratio-stamp-2026-09-23](https://github.com/neilmac91/EarningsNerd/tree/47d040aa53e89d2e1fa78c26ee688d5a49338133/tasks/review-evidence/return-ratio-stamp-2026-09-23) |
| p/q Fable verdicts | [main evidence](../pr942-fable-2026-09-27/README.md): p 48/70 negative, q 40/70; q fails 5/18 negative controls on G4/G5 and adds nine gate identities (seven G3, two G2); [semantic review](../pr942-fable-2026-09-27/semantic-adoption-review.md) |
| q3 baseline pin | Declined: citation fidelity 0.9648 → 0.9532 not applied; `baseline_scores.json` unchanged |
| Retained-p reuse precheck | Failed: full source provenance 6/70, statement-source identity 66/70 ([precheck](https://github.com/neilmac91/EarningsNerd/blob/47d040aa53e89d2e1fa78c26ee688d5a49338133/tasks/review-evidence/financial-candidate-r-2026-09-27/retained-p-precheck.json), [hold comment](https://github.com/neilmac91/EarningsNerd/pull/942#issuecomment-5856807917)) |
| r measurement | CI [36324847604](https://github.com/neilmac91/EarningsNerd/actions/runs/36324847604): 70/70, zero errors or retries; Copilot [36324856693](https://github.com/neilmac91/EarningsNerd/actions/runs/36324856693): 18/18. Telemetry USD 0.382361 (not an invoice). |

### r source-review defects and owners

| Defect (retained r output) | Owner |
| --- | --- |
| WMT run 1: debt maturities lose the table's millions unit | #992 (merged, stamp `s`) |
| FIGS run 1: statutory-tax comparator moved to the YoY comparison | #1019 (merged) |
| AAPL +6.5% vs 6.4% delta | #977 (merged) |
| JPM run 0: 2023 acquisition gain called "prior year" | [#1021](https://github.com/neilmac91/EarningsNerd/pull/1021) `acquisition_period.py` |
| FIGS run 0: Adjusted-EBITDA reconciliation additions called deductions | #1021 `reconciliation_directions.py` |
| PLTR run 0: aggregate other income assigned to one component (cause) | #1021 `statement_relationship._CAUSE_CLAIM` |
| FIGS ratio comparator, model-authored prose side | Held (model-facing tranche). The rendered line is dated by this successor. |
| JPM net-interest-income drivers transferred to total revenue | Unowned; held |
| EPS/share-count attribution instruction (JPM q run-0 G4) | Unowned; held |
| PLTR run 1: cost-of-revenue driver presented as the gross-margin cause | Unowned; held |

### Open #942 review threads

- [r4079438509](https://github.com/neilmac91/EarningsNerd/pull/942#discussion_r4079438509) (advance
  the content stamp) is answered by `summary-2026-09-t`. `q` and `r` stay reserved.
- [r4080047443](https://github.com/neilmac91/EarningsNerd/pull/942#discussion_r4080047443) (rename
  ROE/ROA in the model instruction) belongs to the held model-facing tranche. Until that tranche
  lands, model-authored prose can still say "ROE" for the derived value.

`codex/wave3-thinking-low-pilot` (head `c805815b`) builds on `47d040aa` and so carries stamp `r`. Its
disposition should be recorded when #942 closes.

## Retained Actions artifacts

The Actions artifacts are the only GitHub-hosted copies. The operator should keep copies before
they expire. A copy of the r zip is held in the implementer scratchpad for the operator.

| Run | Head | Artifact | Artifact digest (sha256) | Report SHA-256 | Expires (UTC) |
| --- | --- | --- | --- | --- | --- |
| 35719785433 | `accb5a3e` | 10690738758 | `125c0a4f…2a660` | `8e488b9a…` | 2026-10-06 11:18 |
| 35831800595 | `d129dd24` | 10737173810 | `2e0d7fa0…1d931` | `9bb75722…` | 2026-10-07 07:42 |
| 35834524871 | `aab234fb` | 10738219665 | `23c86a9d…bbf56` | `c34cc1eb…` | 2026-10-07 08:09 |
| 36272463033 (p control) | `c8c90ace` | 10915948634 | `da84150b…14316` | `6715966b…` | 2026-10-10 21:28 |
| 36276521637 (q2) | `2a00fcfa` | 10917259386 | `5425a280…c6829` | `4b548a72…` | 2026-10-10 22:41 |
| 36276551360 (q3) | `2a00fcfa` | 10916803846 | `c32a93fe…114ec` | `3e0f7584…` | 2026-10-10 22:45 |
| 36278111326 (docs push) | `be1f98f4` | 10917902118 | `43fcd898…aa9f0` | `c4cc4a70…` | 2026-10-10 23:11 |
| 36324847604 (r) | `47d040aa` | 10933338099 | `977c86eec309a283ce6125d349d0a691284d7eac2b25612df515069f4fdcc5a2` | `deaa1b52c85bbab1bbcd19b7e55ab483b58ec465d6523272931cbd67e6c7f80b` | 2026-10-11 14:19 |
| 36324856693 (Copilot) | `47d040aa` | 10933995935 | `d22272db61e5a4ccc16f30fe146408fcf3e7a4e0b522c495f3c41dc45397e4e4` | n/a | 2026-12-26 14:08 |

The artifact ids, digests and expiry times come from the Actions API on 30 September. For r, the
zip and report digests were recomputed from a fresh download and both match. The other report
SHA prefixes come from the lane analysis and were not re-downloaded here. The report `deaa1b52`
is load-bearing beyond #942: main and #1021 fixtures cite it.

## Offline replay of the retained r outputs

All 70 retained r outputs from artifact 10933338099 were re-rendered through main `c13b069a` (a
`git archive` copy) and through the successor at `438fd37a`. The replay ran only the grounding
builder, `_apply_structured_fallbacks` and the section projection. It made no model or network call.
Every changed line and its per-clause source checks are listed in
[replay-r-returns.json](replay-r-returns.json).

- **Model-facing bytes:** the grounding block is identical in 70/70 results.
- **Changed output:** the returns line changed in 64/64 results that have one. The six 6-K results
  have no line in either renderer. No other section field changed, and no Markdown line outside
  the returns line changed.
- **Parity with r:** the successor line matches the retained r line byte for byte in 70/70 results,
  so the render is r's, without r's model-facing changes.
- **Values and scope:** 126 ratio clauses were checked against the retained operands. In all 126,
  the value recomputes from numerator ÷ denominator, the operand periods equal the ratio period,
  and the scope names the numerator concept: 110 `us-gaap:NetIncomeLoss` (parent) and 16
  `ProfitLoss` (including NCI). By line, 56 are parent and 8 include NCI (F, JD, NVO, TSM). No
  clause renders `(numerator scope unestablished)`.
- **Comparators:** 92 clauses have a prior point. 90 render with a date. Two are dropped by the
  unchanged ±200% band (GPRO ROE, both runs), exactly as main drops them. No prior was dropped for
  a missing date, and the lines with a prior (52) are the same set as on main. Of the dated
  priors, 88 are year-over-year (364 or 365 days). Two are sequential: FIGS 10-Q ROE, both runs,
  `prior at 2026-03-31`, 91 days. That comparison was previously labelled only "prior", which is
  the retained q G5. Every rendered prior's numerator duration matches the current one. In this
  cohort every prior numerator equals the net-income metric's prior, so no basis note appears.
- **Denominator scope limit:** the label names only the numerator scope. The denominator concept
  differs in entity scope in six ROE clauses: F and JD pair NCI-inclusive `ProfitLoss` with parent
  `StockholdersEquity`, and RIVN pairs parent `NetIncomeLoss` with NCI-inclusive equity. Main
  renders the same numbers without any scope. Naming the denominator would need the equity/assets
  concept that the dropped `:463` hunk supplied, which is Copilot-facing. It stays a follow-up.

Production caches differ from r: r's retained metrics carry operands because r had the operand
copy. With the successor, operands are derived from the net-income point at generation time.
Generation reads the persisted `Filing.xbrl_data` snapshot first (`xbrl_service.py:676-680`).
Scope names therefore depend on that snapshot:

- **Snapshots written since #925 (2026-09-19, `b8e11f36`)** carry net-income `raw_tag` on the
  primary instance path, so the scope renders.
- **Companyfacts-fallback points** have no concept and render `(numerator scope unestablished)`.
- **Snapshots written before #925** have no net-income `raw_tag`. A `t` refresh of such a filing
  renders `(numerator scope unestablished)` on both clauses. That holds for the stale drain
  (`summary_refresh.py:125`), the admin `refresh-stale` path (`admin.py:946`) and
  `precompute --force`, none of which clears `xbrl_data`. Only paths that clear the snapshot
  re-extract and name the scope: the Pro regenerate route (`summaries.py:253`) and the admin
  clear and reset endpoints (`admin.py:466`, `:516`, `:732`).

The label stays truthful, but these lines say less. Neither the offline replay nor a hosted eval
run covers this population, because both extract fresh. Before any `t` drain, count the filings
whose snapshot has no net-income `raw_tag`, and decide whether to clear and re-extract them
first. Existing cached summaries are not regenerated by this PR.

## Held model-facing tranche (one owner per rule)

These corrections change what the model reads. They stay out of this PR and need their own later
content identity and the unchanged RUNBOOK grounding-candidate bar: no G4/G5 on the 18 negative
controls, no new G2/G3, two generated runs per arm and Fable judging. None of that is authorized
in this lane. Measuring them costs at least four 70-summary runs (about USD 0.7–1.5 off-peak),
plus Fable capacity.

| Rule | Single owner |
| --- | --- |
| Formula-named, scope-qualified ratio labels and prior abstention in the grounding block; ONE-HOME "(ROE/ROA)" rename (thread r4080047443) | Held tranche |
| Selected-cash naming, changed together in the render label, `cash_flow_basis`, the grounding label and the form-prompt FCF wording (a render-only rename recreates #942's own P1 naming contradiction) | Held tranche |
| Debt absence and subtotal wording limited to selected standardized XBRL, changed in the render and `debt_grounding_lines` together | Held tranche |
| EPS/share-count attribution in the 10-K/10-Q/20-F prompts | Held tranche |
| `FINANCIAL_EXPLANATION_SUPPORT`: a component's causes and offsets stay on that component | Held tranche |
| `FINANCIAL_DRIVER` net-interest-income-versus-total-revenue example (JPM transfer) | Held tranche |
| Level-versus-change cause of other income (PLTR) | #1021 `statement_relationship` only; the held tranche must not add a prompt clause for it |
| Issuer reconciliation direction (FIGS) | #1021 `reconciliation_directions` only; the held tranche must not add a "keep the stated reconciliation" clause |
| Acquisition period (JPM) | #1021 `acquisition_period` only |
| Rendered ratio formula, scope, dated comparator and operand custody | This successor |
| Denominator entity scope in the ratio label | Unowned follow-up (needs a Copilot-facing concept change) |
| PLTR run-1 gross-margin cause | Unowned |

A merge-tree simulation of this branch with #1021 (`55e89142`) conflicts only in
`lessons/README.md`, which is the existing conflict between #1021 and main. No production or test
file overlaps.

## Local verification on committed code

Six mutations were applied to committed code, tested, and restored with `git checkout --` into a
clean tree. Each targeted run used a fresh `PYTHONPYCACHEPREFIX`. The first four ran on `438fd37a`.
The last two ran on `16ea2559`, which tightened the Copilot raw-shape gate from "no `raw_tag`" to
main's exact key set (`test_accession_xbrl_extraction.py:897`). Production code there is identical
to `438fd37a`. Those runs used the three owner files plus `test_copilot_citation_repair.py`. Before
the tightening, the sixth mutation passed all 228 tests in those files.

| Mutation | Failing | Restored |
| --- | --- | --- |
| Remove the ratio operand copy (`xbrl_service.py`) | 25 failed, 87 passed (`KeyError: 'numerator'`; all seven narrative custody cases and the 18 real-producer rows) | 112 passed |
| Drop the date guard in `_ratio_clause` | 3 failed, 104 passed (the undated prior renders `22.4%`) | 107 passed |
| Borrow the sibling net-income scope in the render | 8 failed, 160 passed (JPM exact line and all seven custody cases) | 168 passed |
| Relabel the grounding ROE row with the formula text | 8 failed (grounding equals main's bytes; JPM grounding row) | 8 passed |
| Restore #942's `:463` hunk, so equity/assets raw points carry `raw_tag` (Copilot-facing `Filing.xbrl_data` shape) | 18 failed, 210 passed (all at `test_accession_xbrl_extraction.py:897`: extra item `'raw_tag'`) | 228 passed |
| Add a differently named key (`concept`) to the equity/assets raw points instead | 18 failed, 210 passed (all at `:897`: extra item `'concept'`) | 228 passed |

The first attempt at the sibling-scope mutation contained a Python 3.11 f-string quoting error, so
tests failed at collection. That run proves nothing and was discarded. It is recorded here
because it happened. The full backend gate result for the exact PR head is in the PR body.
