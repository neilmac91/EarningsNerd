# Give the AI-timeout fallback every figure guard the primary summary writer has, through one shared helper

**Date:** 2026-10-16 · **Area:** AI pipeline / summaries

**Context:** The primary summary writer's deterministic filler (`ai/markdown_render.py`) learned to
label XBRL money in the filer's reporting currency ("CNY 941.2B"), because a bare "$" on a foreign
filer's figure reads ~7x too large. The AI-timeout fallback (`fallback_summary.py`), which the one
orchestrator persists when the model times out, kept its own formatter with a hardcoded "$". Its
tests used USD inputs only, and it runs only on timeouts, so no one saw it. A 20-F filer whose
generation timed out got "Revenue: $941.2B" for CNY 941.2B, and the read path, which matches the
number but not the currency, served it with an SEC-verified chip. A bug hunt found it.

**Rule:** The timeout fallback is a summary writer too. When you add or change a guard on how the
primary writer labels, scales or suppresses a figure, apply it to `fallback_summary.py` in the same
PR by calling one shared helper (never a copy of the rule), and add a parity test that runs both
writers on the same non-default input (a non-USD currency, a negative value, a missing period) and
asserts they agree. Test the fallback with foreign-filer inputs as well as USD ones.

**Evidence:** `app/utils/numbers.py` `money_prefix_for`, called by `ai/markdown_render.py`
`_apply_structured_fallbacks` and `fallback_summary.py` `generate_xbrl_summary`; parity gate
`backend/tests/unit/test_fallback_summary_currency.py::test_the_fallback_labels_money_by_the_primary_path_rule`.
The currency rule itself: `lessons/frontend-xbrl-amounts-carry-their-own-currency.md`. The same
one-shared-predicate pattern for model-facing surfaces: `lessons/arch-guard-every-model-facing-surface.md`.
