# Bake off a model swap the way prod runs it — hold every knob (thinking mode, tokens, temp) constant

**Area:** ai-evals · **Date:** 2026-07-01

Baking off GLM-5.2 vs DeepSeek: a 1-call smoke showed GLM returned EMPTY `content` under a normal
token budget because it's a reasoning model that spent the whole allowance on `reasoning_content`
first. DeepSeek-v4-pro is also a reasoning model, but the pipeline already disables its "thinking" for
deterministic extraction — gated on a `"deepseek" in model/base_url` check that GLM didn't match. Left
as-is, the bake-off would have compared DeepSeek-thinking-off against GLM-thinking-on (conflating model
with mode, plus truncation). Fix: generalize the gate to any reasoning model that accepts the z.ai-style
`extra_body={"thinking":{"type":"disabled"}}` switch. **Rule:** before an apples-to-apples model
bake-off via env-swap, smoke ONE real call and inspect the raw message (content AND reasoning_content);
hold every knob constant (thinking mode, max_tokens, temperature) so the only variable is the model.
Verdict: GLM-5.2 matched DeepSeek on quality but was ~48% slower and ~3.5× costlier → no adoption case;
kept as a validated env-swap failover.
