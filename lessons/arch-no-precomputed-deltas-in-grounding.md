# Don't pre-chew derived deltas into the grounding without a groundedness guardrail

Date: 2026-07-01   Area: arch

**Context**: Wave 4a trialled appending an explicit "YoY: +X%" to each monetary grounding row (genuinely grounded, derived from two SEC-verified values). A clean judged before/after on AAPL: without the suffix faithfulness was 4; with it, 2 — plus two fabricated cash-flow causal attributions directly contradicting the source. Mechanism: salient delta + the "state the driver" directive = the model invents a driver. Only the judge caught it.

**Rule**: A "figure amplifier" that surfaces a DERIVED comparative (e.g. YoY%) is not faithfulness-neutral when the prompt also asks the model to explain changes — it manufactures explanations. Ship the raw current/prior figures (the reader/model sees the trend) but DON'T pre-chew deltas into the grounding unless paired with a groundedness guardrail ("attribute a cause ONLY when the filing states it").

**Evidence**: Faithfulness 4→2 with YoY suffix; fabricated "OCF fell due to higher tax payments" and "investing CF turned positive as maturities increased"; investing CF +417.7% delta; `numeric_precision` stayed 1.0.
