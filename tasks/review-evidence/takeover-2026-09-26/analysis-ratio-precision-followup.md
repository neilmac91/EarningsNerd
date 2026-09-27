# Analysis ratio precision — retained production finding

The signed-in quarterly AAPL 2026Q2/Q3 analysis says the current ratio is “exactly 1.00x” and there is no cushion. Its downloaded workbook retains `1.003294804655586`, current assets `149818000000`, current liabilities `149326000000` and positive working capital `492000000`. The original narrative/PDF/workbook are retained; this is an ordinary product observation, not an E7 verdict.

## Located cause and scope

At PR966 head `5440fff0398b5d40a363c8f28968f60a4943848e`, `backend/app/services/trend_analysis_service.py::_format_value` renders every `unit == "pure"` value with two decimal places. `compact_dataset_for_prompt` passes that same display value to the model. Thus the prompt loses the distinction between a ratio slightly above one, exactly one, and slightly below one. The model is also told not to calculate. The displayed ratio is reasonable UI rounding; treating that display as the entire model evidence is insufficient for exact threshold claims.

The cache-version contract at the top of that module requires bumping `PROMPT_VERSION` for a prompt or compact-dataset rendering change. Such a change lazily regenerates affected cached analyses when requested. This is separate from the filing-summary `p`/`q` candidate and must not be represented as evidence for PR942 or E7.

## Bounded correction and verification

Give the model enough code-owned precision to distinguish the threshold. Keep UI formatting separate from prompt evidence, and make clear that rounded display values do not establish equality or zero headroom. A deterministic above/equal/below-one cue based on the same source value is an alternative to printing many decimals; the implementation should choose one simple representation, with no model-side arithmetic.

Extend the existing prompt-rendering gate with values on both sides of one that display as `1.00x`, an exactly-one control, missing data and a normal ratio. Prove the old display-only rendering loses the distinction, restore the correction, and keep the existing numeric-citation scan compatible with the supplied precision. Preserve the captured production example as a regression input rather than regenerating it away.

Before calling this a narrative-quality improvement, inspect a bounded matched before/after output set for the captured quarterly case plus a below-one and an exact-one control. Set a concrete cost ceiling and retain all outcomes; do not select only a favorable rerun. Run the repository's normal backend checks and exact-head review, then verify the released cached/fresh behavior. A formatting unit test alone proves input preservation, not that the model avoids the false conclusion.

No prompt, cache version, model call or production setting was changed by this investigation.
