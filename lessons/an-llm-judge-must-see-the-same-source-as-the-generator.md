# An LLM judge must get the same (or superset) context the generator did, or it invents 'hallucinations'

**Area:** ai-evals · **Date:** 2026-07-01

The judge scored faithfulness 1.96 with 633 "G3 hallucinated_facts" flags across all 78 runs and
judge_pass=0 — alarming, and it looked like the product was fabricating figures. It was NOT: the judge
was fed `excerpt[:60000]` while the generator grounds on the FULL critical-sections excerpt
(`filing_sample = filing_excerpt`, ~124–165k chars). On a 10-K, capital-return / dividend / purchase-
obligation / segment disclosures sit LATE in the document (AAPL FY25: $100B buyback at char 73,895,
$0.26 dividend at 73,701 — all past the 60k window). Told to "fail when in doubt," the judge flagged
real facts it simply couldn't see. Deterministic `numeric_precision` was 1.0 the whole time and was
right. Raising the cap to 200k recovered faithfulness 2→4 and insight 3→4 on the *identical* summary.
**Rule:** when an LLM-judge verifies claims against a source, it MUST receive the same (or a superset
of the) context the generator used — a smaller judge window manufactures false "unsupported claim"
failures. Cross-check any judge gate against the deterministic scorers: when they disagree sharply
(judge says fabricated, precision says clean), suspect the judge's context/instructions before
believing a product regression. Verify by locating the flagged fact's char-offset in the actual
grounding, not by trusting the judge's phrasing.
