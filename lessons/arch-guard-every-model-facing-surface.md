# Suppress a value on EVERY model-facing surface, or the model parrots what the render dropped

**Date:** 2026-07-10 · **Area:** AI pipeline / grounding

**Context:** T5.3 added a ±200% plausibility band so the machine-authored §4 returns line drops
near-zero-equity ROE noise (HD-class "1644.4%"). The band was applied at RENDER only; the grounding
narrative (`_XBRL_NARRATIVE_SPEC`) still fed the model "Return on Equity: 1644.4%". Since the
figure gate is dollars-only, a restated "ROE of 1,644%" in `capital_allocation` prose would sail
through unpoliced — landing directly under the machine line that had just suppressed that exact
figure. The founder's staff review caught the asymmetry (#621): the sibling fix in the same PR
(negative-equity sign-flips) had been correctly applied at the DERIVATION, healing every surface
at once; the band class wasn't.

**Rule:** a value-quality guard (band, floor, plausibility filter) protects nothing if any
model-facing surface still carries the value. When you can't heal at the derivation (the value is
arithmetically true and other consumers — trend, excel, provenance — legitimately want it), apply
the guard at EVERY surface the model reads (grounding narrative) and every surface it's compared
against (render), from ONE shared predicate/constant so the surfaces cannot drift — and pin the
sharing with an identity test. Checklist when adding any such guard: (1) derivation healable? do it
there; (2) else enumerate model-facing surfaces: prompt grounding, schema examples, re-ask
snippets, rendered output the model might be judged against; (3) one predicate, imported
everywhere, identity-pinned.

**Evidence:** `app/services/ai/xbrl_narrative.py` (`returns_ratio_in_band` /
`RETURNS_RATIO_BAND_PCT`, banded narrative loop) shared into `markdown_render._ratio_clause`;
identity pin `tests/unit/test_xbrl_narrative_section.py::TestReturnsBand::test_render_and_narrative_share_one_predicate`;
PR #621 staff review finding 1. Sibling precedent: negative-equity ROE killed at derivation
(`xbrl_service.py` denominator > 0) — the preferred seam when all consumers should lose the value.
