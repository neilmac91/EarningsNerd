# Give an LLM judge the same (or a superset of the) grounding the generator used

Date: 2026-07-01   Area: test

**Context**: The judge scored faithfulness 1.96 with 633 "G3 hallucinated_facts" flags across all 78 runs and judge_pass=0 — but the product was NOT fabricating: the judge was fed a 60k-char excerpt while the generator grounds on the full ~124–165k-char critical-sections excerpt, and on a 10-K capital-return/dividend/purchase-obligation/segment disclosures sit late in the document, past the judge's window. Deterministic numeric_precision was 1.0 the whole time. Raising the cap to 200k recovered faithfulness 2→4 and insight 3→4 on the identical summary.

**Rule**: When an LLM-judge verifies claims against a source, it MUST receive the same (or a superset of the) context the generator used — a smaller judge window manufactures false "unsupported claim" failures. Cross-check any judge gate against the deterministic scorers: when they disagree sharply (judge says fabricated, precision says clean), suspect the judge's context/instructions before believing a product regression. Verify by locating the flagged fact's char-offset in the actual grounding, not by trusting the judge's phrasing.

**Evidence**: Judge fed `excerpt[:60000]` vs generator `filing_sample = filing_excerpt` (~124–165k chars); AAPL FY25: $100B buyback at char 73,895, $0.26 dividend at 73,701 — both past the 60k window; faithfulness 1.96, 633 G3 flags, 78 runs; 200k cap recovered 2→4.
