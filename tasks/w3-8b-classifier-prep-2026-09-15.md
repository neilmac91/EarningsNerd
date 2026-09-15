# W3-8b preparation — 6-K classes observed on real exhibits, September 15, 2026

Unpaid, read-only preparation for the W3-8b 6-K pre-classifier. Fourteen recent 6-Ks from the seven FPI golden issuers were listed and grounded through the application's own paths (`sec_edgar_service.get_filings(cik, ["6-K"], limit=2)` then `get_sixk_text`), stored under `outputs/w3-8b/exhibits/` with a hashed manifest (`outputs/w3-8b/manifest.json`, agent workspace; not tracked). No model call, database write or production action.

## What the sample contains

| Issuer | Accession | Grounding chars | Content (from the exhibit head) | Draft class |
|---|---|---:|---|---|
| ASML | 0001628280-26-048235 | 12,907 | Q2 2026 results press release | earnings |
| JD | 0001193125-26-347753 | 120,000 (cap) | Q2 and interim 2026 results | earnings |
| SE | 0001193125-26-344596 | 57,759 | Q2 2026 results | earnings |
| PDD | 0001104659-26-100534 | 40,700 | Q2 2026 unaudited results | earnings |
| ASML | 0001628280-26-026703 | 4,171 | AGM results | governance |
| SE | 0001193125-26-364238 | 3,338 | AGM notice | governance |
| BABA | 0001104659-26-105208 | 14,182 | Hong Kong monthly return (share movements) | needs a fourth class: regulatory |
| BABA | 0001193125-26-365894 | 4,324 | completion of HK$80B share placing | press_release (capital action) |
| JD | 0001193125-26-326847 | 3,667 | HKEX announcement wrapper | press_release |
| TSM | 0001046179-26-000658 | **31** | monthly revenue report; primary document is the content | no exhibit body |
| TSM | 0001046179-26-000552 | **31** | dividend adjustment notice | no exhibit body |
| PDD | 0001104659-26-099679 | **28** | (primary document only) | no exhibit body |
| NVO | 0001171843-26-005925 | none | extractor returned `None` | not grounded |
| NVO | 0001171843-26-005795 | none | extractor returned `None` | not grounded |

## Draft heuristic (deterministic, no model call)

Counts over the first 60,000 characters: earnings cues (`results`, `revenue`, `net income`, `earnings per share`, `quarter ended`, `six months ended`, `fiscal year|quarter` …), governance cues (`annual general meeting`, `AGM`, `board of directors`, `appointment`, `resignation`, `dividend`, `share repurchase`, `proxy`, `notice of meeting` …) and money tokens. `earnings` when ≥ 4 earnings cues and ≥ 8 money tokens; else `governance` when ≥ 3 governance cues; else `press_release`. On this sample it places all four results releases and both AGM items correctly. Two corrections before it becomes the W3-8b classifier: add a `regulatory` class for exchange monthly returns (HKEX FF301 "Monthly Return" wording, share-movement tables) so they are never summarised as governance events, and treat capital-action releases (placings, buyback completions) as `press_release` with a capital-action flag rather than governance. Fixture exhibits for the unit test can be excerpted from the four earnings, two governance, one regulatory and two press-release items above (short, attributed excerpts, no full exhibits in the tree).

## Grounding defect found on the way (fixed separately)

When a 6-K has no EX-99 body, `_extract_sixk_text_sync` still returns the cover header alone ("Reporting month: September 2026", 28–31 characters). That string is truthy, so `summary_pipeline`'s fallback to the primary document (`get_filing_document`) never runs, and the model is asked to summarise a one-line grounding. TSM's monthly revenue and dividend 6-Ks and one PDD 6-K hit this; both NVO 6-Ks returned `None` and would have fallen back correctly. The fix is to return `None` from the extractor when there is no body, so the existing fallback engages; it is published as [#875](https://github.com/neilmac91/EarningsNerd/pull/875) with a unit test and one mutation proof.

## Ground truth and the scorer contract

6-K goldens carry no XBRL facts; `score_numeric_accuracy` and `score_numeric_precision` return 1.0 on an empty truth set (`lessons/test-empty-truth-sets-score-perfect.md`), and `pin_baseline.py` refuses a verified entry with no ground truth. For W3-8b, hand-fill `ground_truth` for the earnings-class 6-Ks from the press release (revenue, net income, EPS/ADS where stated, in the reporting currency), keep governance/regulatory/press-release items out of the numeric truth set (or give them a distinct non-numeric contract before adding them), smoke one entry, then the authoritative three-run pin. One re-pin in flight at a time: W3-7's re-pin (when its readout exists) and W3-8b's must not overlap.

## Not done here

No prompt variants were written, no classifier was wired, no golden entries were added and no paid measurement ran.
