# PR #808 final-head summary assessment

The second summary assessment, CI `34691090937`, job `103546340083`, was downloaded separately to `work/pr808-flash-summary-second`. Its retained report is `eval_20260912T113555Z.json`, SHA-256 `6889a3dde5ef17decb030b9c53cb7c087cb0850a0727714da4e8d8a9d2c9ffc6`. This is a fresh acceptance analysis of that artifact, not a relabeling of the first run. No model call, rerun, repository edit or test was performed by this review.

The metadata, source identity and paid-call accounting checks pass. The artifact scores all 52 attempts, with 100% schema validity and deterministic pass rate; those numerical gates do not detect the narrative omissions below. Its `total_cost_usd: 0.0` must not be represented as a free run: retained token/call accounting establishes real provider usage, including one call without token telemetry. The generated narrative still contains material debt-scope mistakes, so this is acceptance of the bounded provenance change and execution integrity, not certification of world-class analysis or permission for universe-wide pregeneration.

## Final execution and cohort

Both report harness and `ci-execution.txt` identify `c0999c8df55751a8a7a5d3e2941e312ed7aa541d`. Independent `git show` confirms its parents are main `65b9243f9739803594e0e73e10f371648a19378c` and gated candidate `0e6b076b3e1112c7e11fb3170b64c941d880a18f`. Both executed synthetic merge and candidate have exactly the same whole tree, `4e87653befe116784a3b75a727cb35ddd04e37a1`. Thus this artifact does execute the final correction's tree.

All 52 identities are present, two attempts for each of 26 filings, with no duplicates, outer retries or terminal errors. Every source-provenance object (including accession/hash fields), complete retained grounding excerpt and coverage inventory equals the #818 Flash reference. All harness fields other than source SHA match that reference, including golden hash and unchanged feature flags. The same checks also pass against the first #808 Flash report, and **the entire XBRL structures equal that first report exactly**.

Against #818, the only XBRL changes are the same 362 observed qualified raw-tag additions: 198 cash-equivalents, 96 noncurrent-long-term-debt, 32 long-term-debt, 12 cash-plus-restricted-cash, and 24 IFRS cash-equivalents observations. Current/prior/series repetition and paired attempts are included in those counts. No inferred number, currency, date, computed change or unrelated field differs. Exact concepts and all per-identity results are in `work/pr808-flash-summary-second-metadata.json`; the zero-difference first/second comparison is `work/pr808-flash-summary-first-second-metadata.json`.

## Usage conservation

The separately retained actual job log is `work/pr808-flash-summary-second.log`. Offline reconciliation of row, incurred and summary counters with its actual call records passes with no failures: **53 summary-primary calls**, including **one unknown-usage call**, zero outer retries and no terminal errors. Recorded totals are 2,166,940 prompt tokens, 198,171 completion tokens, 2,157,050 cache-hit tokens and 9,890 cache-miss tokens. Reasoning tokens remain unavailable rather than zero. Actual observed model labels are `deepseek-flash`. The unknown call is counted; these known-token totals do not assert its unreported cost. Evidence: `work/pr808-flash-summary-second-usage.json`.

## Targeted semantic debt-scope check

This check freshly read both second-run leverage paragraphs for WMT, COIN, ASML, Ford, Sea, Novo and MercadoLibre and cross-checked the suspect debt components against retained source anchors and first/#818 outputs. It did not reread all 26 complete filings or certify every generated section.

| Case | Final-run result | Disposition and two refutations |
| --- | --- | --- |
| WMT 0 | Total debt $44.8B explicitly includes $6.6B short borrowings, $3.5B current long-term debt and $34.6B noncurrent debt. | This targeted statement is now correctly scoped. |
| WMT 1 | Calls $38.2B “total debt” while separately mentioning $6.6B short borrowings. | Material omission persists. Refutation 1: the source long-term schedule at offset 66,000 gives $38,166M including $3,542M current portion; the balance sheet at 12,975 separately gives $6,596M short borrowings, so combined debt is $44,762M. Refutation 2: both #818 attempts and first #808 show the same pattern, so no newly established data regression. |
| COIN 0 / 1 | Run 0 separately gives $5.94B noncurrent, $1.27B current and $564.6M short borrowings; run 1 calls $7.2B “total debt”. | Run 1's omission persists. Refutation 1: source near offset 1,208 separates $564,610 thousand borrowings from the $1,271,056 thousand current portion. Refutation 2: #818 and first #808 run 1 already omit the same component. |
| ASML 0 and 1 | Both describe “total debt” as €2,709M noncurrent plus €691.7M short borrowings. | Material omission of the €990.2M current portion. Refutation 1: the source table at offset 154,673 reconciles €3,699.2M long-term debt to €990.2M current and €2,709M noncurrent; ECP carrying €691.7M is separately at 159,209, giving €4,390.9M combined carrying debt. Refutation 2: every supplied source and XBRL observation is identical to the first #808 assessment; #818 already exhibited incomplete total-debt aggregation, although this attempt omits a different component. Truthful metadata alone does not enforce aggregation, and this variant must remain in the quality backlog. |

Ford distinguishes Company and Ford Credit debt; MercadoLibre's leverage paragraphs explicitly label current plus noncurrent liabilities. Sea and Novo still lack structured debt series, and their excerpt limitations must not be converted into claims of no debt. The final review does not infer missing values.

## Decision

No metadata/data-conservation regression survives. Preserve the first and second reports separately, including the failed first Copilot check and its correction history. This final summary evidence supports the bounded metadata release; it does not erase the repeated material narrative findings. Total-debt aggregation needs a subsequent explicit scope fix and targeted acceptance evidence. Universe-wide pregeneration remains on hold, and final Copilot acceptance belongs to its own artifact review.
