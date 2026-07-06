# To change model behavior, edit the lead directive that causes it and pair the rule with a concrete worked example

**Area:** ai-evals · **Date:** 2026-07-01

The driver/outlook guardrail wave, gated with judged before/after (3 filings × 3 runs, subscription
`cli:sonnet`). **V1** (append two caveat bullets after the existing "state the PRIMARY driver"
directive) did NOTHING: mean faithfulness 3.00→3.11 (flat), causal-driver fabrications 6→8 — a buried
caveat loses to the unconditional lead directive it contradicts. **V2** (reword the LEAD directive to
be conditional — "give the driver ONLY as management states it; when the filing gives no cause, report
the movement alone" — + a prominent DO-NOT prohibition) cut the egregious source-contradicting causal
fabrications to ~1, held faithfulness, no deterministic regression, prose stayed decisive (2 PASS vs 1).
BUT the *mean* stayed flat (3.11) because the model's fabrication **redistributed** to modes the
guardrail doesn't touch: presenting derived figures as reported ("Services now 26.2% of sales"), debt
aggregations, inferred "tone: positive/cautious". **Rules:** (1) to change model behaviour, edit the
DIRECTIVE THAT CAUSES IT (make the lead conditional), not an appended caveat — caveats that contradict
a stronger nearby instruction are ignored. (2) A model has a roughly conserved "fabrication drive":
suppressing one mode (invented causes) surfaces others (derived-as-reported, tone) — expect whack-a-mole
and measure ALL modes, not just the one you targeted; the headline mean can stay flat while a specific
egregious pattern is genuinely fixed. (3) Ship the targeted, no-regression win anyway (precedent: Wave 2
shipped a no-regression refinement on a judge-visible gain) and make the redistributed modes the next
target: a "don't present a derived/aggregated figure as if reported; don't infer tone" guardrail.
**V3 UPDATE — a concrete negative EXAMPLE was the real unlock (show, don't just tell).** A reviewer
suggested pairing the existing with-cause example with a no-cause one — `report the movement alone
(e.g. "Capex rose 12% to $1.2B")`. Adding that single parenthetical to the (V2) conditional directive
moved the mean from 3.11 to **3.78** (before 3.00), took OUTLOOK fabrications to **0**, and HALVED the
runs with any fabrication (8/9→4/9) — NVDA went fully clean. So the rewritten directive (V2) reduced the
egregious pattern but the *example* (V3) is what lifted the headline: the model imitates a modeled
output far more reliably than it obeys an abstract rule. **Rule:** when a directive tells the model to
sometimes-omit something, give a concrete example of the omitting-output — a rule + its worked example
beats the rule alone by a wide margin. (Cost: it took a 4th judged sweep to see it; worth it.)
