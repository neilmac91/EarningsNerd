# Edit the directive that causes the behavior and pair it with a worked example

Date: 2026-07-01   Area: arch

**Context**: The driver/outlook guardrail wave, judged before/after (3 filings × 3 runs, subscription `cli:sonnet`). V1 (appended caveat bullets) did NOTHING: faithfulness 3.00→3.11, fabrications 6→8. V2 (conditional lead directive + prominent DO-NOT) cut egregious source-contradicting causal fabrications to ~1 but the mean stayed flat as fabrication redistributed (derived-as-reported "Services now 26.2% of sales", debt aggregations, inferred tone). V3 — adding one concrete negative example to the conditional directive — moved the mean 3.11→3.78 (before 3.00), took OUTLOOK fabrications to 0, and halved flagged runs 8/9→4/9; NVDA went fully clean.

**Rule**: (1) To change model behaviour, edit the DIRECTIVE THAT CAUSES IT (make the lead conditional), not an appended caveat — caveats that contradict a stronger nearby instruction are ignored. (2) When a directive tells the model to sometimes-omit something, give a concrete example of the omitting-output — a rule + its worked example beats the rule alone by a wide margin. (3) A model has a roughly conserved "fabrication drive": suppressing one mode surfaces others — measure ALL modes, not just the targeted one; ship the targeted no-regression win anyway and make the redistributed modes the next target.

**Evidence**: V1: 3.00→3.11, causal fabrications 6→8; V3 example `report the movement alone (e.g. "Capex rose 12% to $1.2B")` → mean 3.78, OUTLOOK fabrications 0, runs flagged 8/9→4/9. Cost: a 4th judged sweep.
