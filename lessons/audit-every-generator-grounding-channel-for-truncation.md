# The judge-context rule applies to EVERY grounding channel — audit excerpt AND XBRL AND tool output for truncation caps

**Area:** ai-evals · **Date:** 2026-07-01

Wave 4a judged spot-check FAILed AAPL with faithfulness 2 and G3 "hallucination" flags on Free Cash
Flow, ROE/ROA, working capital and current ratio — all figures the model legitimately grounds on. A
probe settled it: the full standardized-metrics JSON is 12,244 chars, but `evals/runner._xbrl_to_text`
capped the judge's XBRL view at 8,000 (`json.dumps(metrics)[:8000]`), so ~1/3 of the metrics (the
*late* dict keys — FCF/ROE/ROA/WC/current ratio) fell out of the judge's view and were flagged as
unsupported. Same class of bug as the 60k-excerpt truncation, different channel (the XBRL block, not
the filing excerpt). Fix: raised the cap to 40,000 (`_XBRL_TEXT_CHAR_CAP`); the metrics JSON is small
and the judge already carries a 200k excerpt budget. **Rule:** the judge-context lesson applies to
EVERY channel the generator grounds on, not just the filing text — audit each source the generator
sees (excerpt AND XBRL AND any tool output) for its own truncation cap. When the judge flags a figure
you *know* is in the grounding, dump exactly what the judge received and check for a truncation
boundary before believing a regression.
