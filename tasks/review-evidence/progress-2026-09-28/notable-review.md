# Notable source-only acceptance review

## Result

The frozen 12-card packet produced 8 passes, 0 false positives, and 4 indeterminate rows. All eight readable indices matched accession, form, and filed date. The all-row pass rate is 66.7%; determinate precision is 100% (8/8). An indeterminate row is not counted as a pass.

No sample row was replaced. No database, cloud configuration, feature flag, model, email, or GitHub mutation occurred.

## Retrieval and custody

The one-shot runner used release commit `1c8a017e49e2dbe98a7612a0d445b4b883d9b80d` and `SECEdgarServiceCompat.get_filing_attachment_bytes`, which owns the shared limiter, circuit breaker, identity header, redirect rejection, and bounded entity read. The first five physical calls failed before receiving an HTTP response; the breaker then rejected seven calls locally. The runner recorded all 12 failures and made no retries.

The follow-up plan permits an official SEC web open only when the application transport is unavailable. The fallback opened the 12 exact SEC index URLs and the primary documents for the seven readable 8-K indices. Eight index pages and six primary pages rendered; four indices and one primary returned tool errors. These are 14 confirmed rendered SEC pages, below the 24-response cap. Cached-ref reopens and text finds inspected already-returned pages. No proxy, search result, exhibit, or related filing was used.

The repository transport returned no source bytes, and the official web opener exposed normalized text with line locators rather than response bytes. Therefore the source-file count is zero and no raw-source SHA-256 is claimed. Exact hashes for the frozen inputs, runner, and transport ledger are in `source-custody.json`.

## Verdicts

| Ticker | Reason | Verdict | Source locator | Candidate wording limit |
|---|---|---|---|---|
| RIME | acquisition | pass | Index lines 9-15, 30-38; primary Items 1.01/2.01, lines 96-100, 142-143 | Completed asset acquisition; keep the separate future equity option distinct. |
| INBP | annual_report | indeterminate | Official index inaccessible | Do not infer a 10-K from the packet alone. |
| SGMOQ | bankruptcy | indeterminate | Official index inaccessible | Do not show bankruptcy language without readable Item 1.03 evidence. |
| MGLD | earnings_results | pass | Index lines 9-15, 31-32; primary Item 2.02, lines 88-90 | Fiscal-year and fourth-quarter results announced; the release was furnished. |
| PUMP | executive_change | pass | Index lines 9-15, 29-31; primary Item 5.02, lines 63-69 | Officer resignation and interim appointment. Item 5.02 alone is not enough for other cards. |
| BOXL | ipo_filing | pass | Index lines 9-15, 27-30, 50-52 | Say “S-1 registration statement filed”; do not say an IPO priced or completed. |
| AIAI | material_agreement | pass | Index lines 9-15, 31-33; primary Item 1.01, lines 82-88 | Agreement creates a discretionary equity facility; $200 million was not already raised. |
| AXON | material_agreement | pass | Index lines 9-15, 30-33; primary Item 1.01, lines 89-94, 136-146 | Prefer “convertible-notes and underwriting agreements” to the generic label. |
| GRNQ | material_agreement | pass | Index lines 9-15, 31-33; primary Item 1.01, lines 93-104 | Signed agreement for a pending subsidiary sale; do not say the disposition completed. |
| CD | material_agreement | indeterminate | Official index inaccessible | Suppress or use neutral 8-K wording pending readable source. |
| AETN | material_agreement | indeterminate | Official index inaccessible | Suppress or use neutral 8-K wording pending readable source. |
| OPTU | restatement | pass | Index lines 9-15, 29-33; primary inaccessible | Say “non-reliance disclosed”; do not claim a restatement was completed or amended statements were filed. |

`verdicts.json` contains every official URL, exact per-row locator, metadata result, reason result, and aggregate breakdown.

## Aggregate context and recommendation

The seven-day ledger contains 312 unique accessions from 291 issuers, zero duplicate accessions, eight reason buckets, and 0.938-day median / 1.521-day p95 first-observed age. That establishes freshness and uniqueness, not semantic precision.

The readable source subset has no false positives and shows that useful, source-faithful card wording is possible. Coverage is still incomplete: the only bankruptcy card, the only annual-report card, and two of five material-agreement cards are indeterminate. The source review therefore supports retaining the implementation while deferring activation until the four unresolved rows receive a bounded successful source read or the product suppresses source-unverified cards. It does not authorize `NOTABLE_FILINGS_ENABLED`; root retains the final feature and release decision.
