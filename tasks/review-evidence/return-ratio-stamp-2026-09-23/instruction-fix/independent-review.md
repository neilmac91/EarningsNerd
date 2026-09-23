# Independent review: formula-named return instruction fix

Reviewed read-only at `3235d42e10d8adfc3e47c4a6046bdcb99ff07749`, comprising `992a0845f29530fae85766f22d6ac092a57a9efc` plus the assertion correction in `3235d42e`, against published head `d129dd246d9ca593751ecf13a4f2f067a930dd92`.

## Conclusion

No actionable finding remains in this two-commit change. The production diff is limited to replacing the remaining generator instruction's issuer-facing `ROE/ROA` label with the same formula-basis helper already used by the grounding and deterministic render surfaces. The second commit closes the initially narrow assertion gap by rejecting either token independently in the captured request prompt.

This is a code and evidence review, not a semantic evaluation of generated summaries. I did not call a model or run pytest. The root-supplied exact-final gate reports 3,500 passed, 29 warnings, zero failures/errors/skips, all four PostgreSQL lanes and both performance lanes, with Ruff, Bandit, and pip check passing.

## Three-lens review

### Correctness: pass

- `openai_service.py` imports `return_ratio_basis` from `app.services.ai.xbrl_narrative` and interpolates it into the actual `ONE HOME PER NUMBER` instruction. The generated wording is `period net income / period-end equity, not annualized` and the corresponding assets formula, matching the deterministic labels.
- The async regression test captures `create_kwargs` at `_request_content`, then reads `messages[1].content`. It therefore checks the assembled user prompt submitted at the provider boundary, rather than checking a disconnected template fragment.
- The JPM-shaped metrics exercise both current and prior derived ratios. The test checks the formula labels and values in the grounding block, deterministic `returns_on_capital`, and captured request prompt.
- The change does not rewrite filing prose. `filing_sample` is still interpolated unchanged under `CRITICAL FILING EXCERPTS`, so a genuine issuer-reported `Return on Equity`, `Return on Assets`, `ROE`, or `ROA` in retained source text remains source text. The new wording applies only to the application's derived-ratio instruction and deterministic labels.

### Contract and lifecycle: pass

- `SUMMARY_PROMPT_VERSION` is `summary-2026-09-q`, whose adjacent history explicitly records the formula-name change and says older rows become stale without scheduling replay. `is_stale` compares the stored prompt version to that constant, so older `p` rows remain refresh-eligible.
- The schema version remains unchanged, consistent with a content-label correction that does not alter the section taxonomy.
- The helper is shared rather than duplicated: grounding uses `return_ratio_basis` directly, `markdown_render.py` imports the same function for deterministic rendering, and the generator instruction now imports that function as well.

### Security, performance, and maintainability: pass

- No new input parsing, I/O, network behavior, persistence path, or authorization surface is introduced.
- The two constant-time helper calls occur during prompt construction and have no meaningful performance impact.
- The production change is one imported helper and one instruction line. The test's provider-boundary capture makes future wording drift observable without making an external call.

## Refutation attempts

1. **Could the test pass from the grounding block while the instruction still says `ROE/ROA`?** No. The captured prompt includes both, and `assert "ROE" not in prompt and "ROA" not in prompt` independently detects the old combined spelling and either separately retained acronym. This is the gap corrected by `3235d42e`.
2. **Could it inspect a synthetic string rather than the actual provider request?** No. `_request_content` is replaced at the service instance boundary, and the test extracts `messages[1].content` from the exact `create_kwargs` passed by `generate_structured_summary`.
3. **Could the change erase genuine issuer labels from filing evidence?** No production transformation was added. The retained filing excerpt is interpolated unchanged; only an application-authored instruction changed. The fixture omits issuer labels so its negative assertion targets application-authored prompt text, while static inspection confirms source prose is not normalized or replaced.
4. **Could grounding, rendering, and instruction labels drift independently?** The three production surfaces resolve their wording through `app.services.ai.xbrl_narrative.return_ratio_basis`; the existing identity check also pins the renderer's imported helper to that module object.
5. **Could existing persisted `p` summaries remain incorrectly current?** No. The checked tree has `SUMMARY_PROMPT_VERSION = "summary-2026-09-q"`, and the stale predicate compares stored prompt versions against it.
6. **Could this require a schema bump?** No serialized field or section key changes. Only the human-readable basis attached to the existing derived-return fields changes; the prompt stamp is the repository's content-version mechanism for that class.

## Scope limits

This review confirms the prompt assembly, shared formula naming, source-label preservation by non-transformation, and prompt-version mechanism. It does not claim that any model will follow the instruction or that existing rows were regenerated.
