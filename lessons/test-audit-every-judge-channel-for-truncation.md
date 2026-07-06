# Audit every grounding channel the judge sees for its own truncation cap

Date: 2026-07-01   Area: test

**Context**: Wave 4a's judged spot-check FAILed AAPL with faithfulness 2 and G3 "hallucination" flags on FCF, ROE/ROA, working capital, and current ratio — all legitimately grounded. The full standardized-metrics JSON is 12,244 chars but the judge's XBRL view was capped at 8,000, so the late dict keys fell out of view and were flagged as unsupported. Same class as the 60k-excerpt truncation, different channel.

**Rule**: The judge-context lesson applies to EVERY channel the generator grounds on, not just the filing text — audit each source the generator sees (excerpt AND XBRL AND any tool output) for its own truncation cap. When the judge flags a figure you know is in the grounding, dump exactly what the judge received and check for a truncation boundary before believing a regression.

**Evidence**: `evals/runner._xbrl_to_text` capped at `json.dumps(metrics)[:8000]`; full metrics JSON 12,244 chars; fix raised `_XBRL_TEXT_CHAR_CAP` to 40,000 (judge already carries a 200k excerpt budget).
