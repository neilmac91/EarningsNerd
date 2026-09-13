# PR842 Copilot acceptance — 2026-09-13

Run 34734666066 (the paid run; draft skip 34734642550 is not evidence), artifact outputs/pr842-copilot/copilot-fidelity-34734666066/copilot-eval.json, source b6891b4de197379224172ac0856b2b69af722591. All 18 expected attempts completed and scored, all 18 passed, zero errors/failures, accepted=true. No new code blocker was found in the bounded preservation review.

Against #839third, all 18 whole input objects and actual tool_trace initial_messages/tool_schema/generation_options are exactly equal. Eleven answer strings are equal; seven vary. All 24 source-artifact SHA256 values were independently verified, and all six HTML/excerpt/sections/XBRL sets are byte-identical to #839third. Unlike #839third's deliberate metadata addition, this comparison needs no projection.

Thirty numeric chips remain verified. ASML three of three responses contain correct revenue EUR 32,667,300,000 and net income EUR 9,609,400,000, selected accession 0001628280-26-011378, annual 2025-01-01→2025-12-31. All seven text excerpts occur verbatim after whitespace normalization in the supplied source. Tesla's changed $97.69B and $7.08B prose correctly rounds selected $97,690M/$7,076M. BABA native CNY amounts and MSFT revenue/EPS remain correct. The AAPL supplemental scope issue from #839third does not occur in these AAPL samples.

**Should-fix existing text-citation scope class, observed on ASML run 0:** The supplemental sentence says the filing table confirms both sales and net income, while [3] quotes only “Total net sales 28,262.9 100.0 32,667.3 100.0 15.6”. Refutation 1: the actual excerpt contains no net-income row, so this is genuinely over-broad evidence scope. Refutation 2: primary [1]/[2] chips correctly certify both requested values, which refutes a wrong-number allegation but does not make supplemental [3] cover the second assertion. This pattern was previously observed on AAPL and is outside the operating-to-pretax source owner; do not claim universal citation quality merely from accepted=true.

This is read-only acceptance of the completed run. No extra source/model calls, tests, edits or publication were performed.
