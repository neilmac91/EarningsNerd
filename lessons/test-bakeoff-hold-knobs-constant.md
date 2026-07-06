# Bake off model swaps with every knob held constant, verified by one raw-inspected call

Date: 2026-07-01   Area: test

**Context**: Baking off GLM-5.2 vs DeepSeek: the smoke showed GLM returned EMPTY `content` because it's a reasoning model that spent the whole token allowance on `reasoning_content`. The pipeline already disables DeepSeek's thinking for deterministic extraction — gated on a `"deepseek" in model/base_url` check GLM didn't match — so the bake-off would have compared DeepSeek-thinking-off against GLM-thinking-on. Verdict: GLM-5.2 matched quality but was ~48% slower and ~3.5× costlier → no adoption; kept as a validated env-swap failover.

**Rule**: Before an apples-to-apples model bake-off via env-swap, smoke ONE real call and inspect the raw message (content AND reasoning_content); hold every knob constant (thinking mode, max_tokens, temperature) so the only variable is the model. Generalize provider-specific gates (e.g. thinking-disable) beyond substring checks on one vendor's name.

**Evidence**: `"deepseek" in model/base_url` gate; fix generalized to `extra_body={"thinking":{"type":"disabled"}}` for any reasoning model accepting the z.ai-style switch; GLM-5.2 ~48% slower, ~3.5× costlier.
