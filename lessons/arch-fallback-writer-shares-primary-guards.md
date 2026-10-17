# Label the AI-timeout fallback's money through the primary summary writer's helper, never a copy of the rule

**Date:** 2026-10-16 · **Area:** AI pipeline / summaries

**Context:** The primary summary writer's deterministic filler (`ai/markdown_render.py`) learned to
label XBRL money in the filer's reporting currency ("CNY 941.2B"), because a bare "$" on a foreign
filer's figure reads ~7x too large. The AI-timeout fallback (`fallback_summary.py`), which the one
orchestrator persists when the model times out, kept its own formatter with a hardcoded "$". Its
tests used USD inputs only, and it runs only on timeouts, so no one saw it. A 20-F filer whose
generation timed out got "Revenue: $941.2B" for CNY 941.2B, and the read path, which matches the
number but not the currency, served it with an SEC-verified chip. A bug hunt found it. Review then
found a third writer of the same cells: the prior-period backfill both paths run before storing
(`schemas/summary.py` `attach_normalized_facts`) also hardcoded "$".

**Rule:** The timeout fallback is a summary writer too. Every writer of a summary's P&L table
cells labels money with `app/utils/numbers.py` `money_prefix_for`, never with an inline "$" or a
copy of the rule. When you change how the primary writer labels money, change the helper, so the
fallback and the backfill follow, and keep the parity test passing. Test each writer with
foreign-filer inputs as well as USD ones. No currency maps to "$" here. That is the backend's
domestic default for XBRL that names no currency. The frontend's rule for a payload without a
currency is different: it shows no symbol (`lessons/frontend-xbrl-amounts-carry-their-own-currency.md`).

Out of scope, and known: the fallback and the primary filler still differ on scale, on missing
values and on row labels. The primary has a K tier ("950.0K") where the fallback prints "950,000".
The primary drops a row with no current value where the fallback prints "Not disclosed". The labels
read "Net income" against "Net Income". The fallback also skips the primary's bank-total sanitizer
(`prepare_sections`). The parity test compares only the revenue row's money label, so do not
read it as full writer parity. `ai/bank_guards.py` and `ai/financing_comparison.py` keep older
copies of the prefix expression. They behave the same today; do not add another.

**Evidence:** `app/utils/numbers.py` `money_prefix_for`, called by `ai/markdown_render.py`
`_apply_structured_fallbacks`, `fallback_summary.py` `generate_xbrl_summary` and
`schemas/summary.py` `attach_normalized_facts`; parity gate
`backend/tests/unit/test_fallback_summary_currency.py::test_the_fallback_labels_money_by_the_primary_path_rule`,
with the backfill pinned by `test_the_stored_fallback_backfills_a_zero_prior_in_the_filer_currency`
and `test_the_primary_path_backfill_labels_a_blank_prior_in_the_filer_currency` in the same file.
The same one-shared-predicate pattern for model-facing surfaces:
`lessons/arch-guard-every-model-facing-surface.md`.
