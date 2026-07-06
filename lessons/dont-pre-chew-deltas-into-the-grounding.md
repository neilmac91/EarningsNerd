# Don't pre-compute deltas (YoY%) into the grounding when the prompt also asks the model to explain changes — it fabricates causes

**Area:** ai-evals · **Date:** 2026-07-01

Wave 4a trialled appending an explicit "YoY: +X%" to each monetary grounding row (derived from the two
SEC-verified current/prior values — genuinely grounded). A judged before/after on AAPL (with the
now-fixed judge view, so the comparison was clean) was unambiguous: WITHOUT the YoY suffix faithfulness
was 4 and the cash-flow narrative was clean; WITH it faithfulness dropped to 2 and the model produced
two *fabricated* cash-flow causal attributions ("OCF fell due to higher tax payments"; "investing CF
turned positive as maturities increased") that directly contradicted the source cash-flow statement.
Mechanism: the salient delta (esp. investing CF +417.7%) + the Wave-2 "state the driver" directive =
the model invents a driver to explain the number. `numeric_precision` stayed 1.0 (no wrong *number*),
so only the judge caught it. **Rule:** a "figure amplifier" that surfaces a DERIVED comparative is not
faithfulness-neutral when the prompt also asks the model to explain changes — it manufactures
explanations. Ship the raw current/prior figures (let the reader/model see the trend) but DON'T
pre-chew deltas into the grounding unless paired with a groundedness guardrail ("attribute a cause
ONLY when the filing states it"). Dropped YoY for Wave 4a; kept the FCF relabel + working-capital
fallback (pure grounding, no delta-to-explain) + the judge-view fix. The driver-guardrail (which would
let YoY return safely) is the real prize — queued as a prose-wave item.
