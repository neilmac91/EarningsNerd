# General complete-unit selector: offline result

**Do not integrate this selector into production yet.** General topic/quantitative/conditional signals recover known KO and XOM missing passages without issuer-specific selection rules, but the experiments expose displacement and source-association problems that prevent a small safe ranking PR. Proceed in stages: inventory, complete assembly, then ranking. No network, model work, repository edits or production action occurred.

Both scripts processed all 26 retained local HTML sources with EdgarTools 5.56.0 and blocked socket connections. Selection uses only general topic terms (tax, litigation, covenants, liquidity, outlook, investment, repurchases, impairment, restructuring, discontinuation and incorporation), quantitative markers and conditional language. Issuer names and known finding phrases occur only in a diagnostic check after decisions are frozen. Results and exact displaced passages are saved in `work/general-selector-prototype.json` and `work/general-selector-slack.json`; executable scripts have matching stems.

## Fixed reserve experiment

The first prototype reserves 12,000 characters from MD&A, preserving the financial allocation, and selects complete source units plus immediate neighboring units. It keeps the per-form character ceiling but displaces 674 units across the corpus. Source XPath, exact text, hash, role and character count for every displaced unit are recorded, not merely summarized.

| Case | Newly recovered known passage | Displaced characters | Material trade-off |
|---|---|---:|---|
| KO | Approximately $14B tax exposure | 6,154 | Equity income, other income and prior disposal gain, effective-tax explanation, liquidity and supplier-finance context |
| XOM | $27–29B investment guidance and reasonable-market-conditions buyback wording | 9,803 | Production volume tables/reconciliation definitions, Energy Products segment earnings table and driver explanations |
| INTC | Conditional 14A exit still missed | 0 | Already present in actual retained G03639–G03640; ranking does not address the synthesis failure |
| NVO | Exhibit 15.1 pointer still missed | 0 | Referenced exhibit evidence remains unavailable to this prototype; a pointer would not supply it |

This is not an acceptable improvement trade: XOM gains forward guidance while losing precisely the segment performance evidence another review finding requires. The first implementation also used bare text deduplication and admitted inline-XBRL continuation fragments without certifying rendered order. It is retained as a negative experiment, not proposed code.

## Unused-capacity experiment

The second variant makes no reserve eviction. It selects from available space under the same per-form ceiling, with 512 characters reserved for headings/separators and a maximum additional 12,000-character slice. It deduplicates complete context groups rather than individual text and fail-closes unresolved inline-XBRL continuation/hidden units, nested or oversized tables, unresolved header structure, and groups whose adjacent units are unavailable or cannot fit. Every failure carries an explicit reason in JSON. No text or table is cut to fit.

| Case | Protected baseline chars | Added chars | Final body chars | Diagnostic outcome |
|---|---:|---:|---:|---|
| KO | 54,562 | 11,881 | 66,443 | Tax passage recovered |
| XOM | 129,829 | 11,978 | 141,807 | Guidance and buyback condition recovered |
| INTC | 34,897 | 11,971 | 46,868 | 14A condition missed |
| NVO | 42,706 | 11,997 | 54,703 | Exhibit reference missed |

All 26 satisfy body plus reserved formatting space ≤ the respective 120,000/170,000-character ceiling; zero units are displaced from this variant’s baseline. **That is not preservation of the existing input:** conservative source exclusions shrink the baseline substantially. There are 10,040 explicitly unavailable units across the corpus, primarily unresolved inline-XBRL/hidden structure. Treating this fail-closed diagnostic as production would itself lose evidence. It demonstrates why source-unit assembly must be solved first.

## Constraints before integration

1. Inventory must cover actual cached `critical_excerpt` provenance and cache-hit bypasses. Preserve legacy excerpts and summaries; do not refresh or broadly invalidate them to make new coverage metadata appear complete. Unknown legacy provenance remains unknown.
2. Complete assembly must own every label, separator, recovery passage and final budget check. The current final `[:320000]` can split a supposedly complete unit after selection; replace that behavior only within a reviewed assembly change. These offline experiments exclude dense recovery and cached excerpts and therefore do not certify final production assembly.
3. Resolve inline-XBRL continuations into rendered order using a supported parsed representation; skipping them wholesale is not a safe production solution. A source XPath identifies bytes but does not prove semantic display order.
4. Immediate predecessor/successor grouping is only a diagnostic heuristic. It does not prove that a table’s footnotes, currency, definitions or conditional antecedent are adjacent. Until associations are certified, mark such groups unavailable; do not silently select the table alone. Oversized-table decomposition remains separate.
5. Rank from unused capacity and complete-boundary slack first. Protect statement and segment-driver groups explicitly before considering eviction. Measure lost coverage against the actual assembled baseline, not just a reconstructed canonical prefix. Display inventory omissions as evidence limitations and never equate search absence with filing absence.
6. Keep the actual retained-generator distinction: KO/XOM evidence is absent there; Intel 14A is present. A better selector cannot by itself fix analytical attention or judgment. NVO requires referenced-source acquisition/coverage through the existing transport in a separately bounded integration; no exhibit was fetched or read here.

An inventory-only PR can be justified once the data shape and cache-hit semantics are reviewed. A complete assembly PR needs source-order and association fixtures before wiring. A general-ranking PR is **not yet justified** by these results; it needs an eviction-free actual-baseline comparison and independent review of the preserved core evidence. Universe-wide pregeneration remains held.

Across all 26 filings, the fixed-reserve variant displaced **129,294 characters across 674 units**. The unused-capacity variant displaced **0 characters from its own reconstructed baseline**, but its conservative structural exclusions changed that baseline and therefore do not establish zero loss versus production. Both variants are negative integration evidence, saved for review.

## Whole-section expansion using remaining capacity

A simpler offline comparison preserves every existing prefix and dense-recovery component, then expands a supplied canonical section only when its entire text fits. Across all 26 retained sources, canonical-order expansion adds 1,255,835 characters (+30.79% over the assembled baseline). Cheapest-complete-expansion first adds 1,144,065 (+28.05%); both complete 30 sections across 21 inputs and remain within the current 320,000-character ceiling. The latter restores XOM's capex range and market-dependent buyback condition. Its different choices for XOM and Boeing demonstrate a general allocation trade-off, not universally superior selection.

A per-filing 10% growth ceiling adds 80,649 characters overall (+1.98%), completing eight sections, but does not recover the confirmed XOM omissions. XOM's full MD&A requires 75,464 additional characters, a 46.9% increase over its 160,904-character baseline. Character growth is not a token or dollar estimate. The larger variant would materially change serving input and attention; the smaller variant does not solve the motivating omission. Neither is adopted as a production fix in this checkpoint.

KO legal exposure remains outside the selected canonical section set, NVO's incorporated exhibit remains unacquired, and Intel's conditional 14A passage was already present. These need distinct source-acquisition or synthesis fixes. This comparison incurred no model calls, new SEC fetches or pregeneration.
