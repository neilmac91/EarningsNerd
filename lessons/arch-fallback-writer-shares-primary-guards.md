# Label the AI-timeout fallback's money through the primary summary writer's helper, never a copy of the rule

**Date:** 2026-10-16, updated 2026-10-24 (F61 call 1) · **Area:** AI pipeline / summaries

**Context:** The primary summary writer's deterministic filler (`ai/markdown_render.py`) learned to
label XBRL money in the filer's reporting currency ("CNY 941.2B"), because a bare "$" on a foreign
filer's figure reads ~7x too large. The AI-timeout fallback (`fallback_summary.py`), which the one
orchestrator persists when the model times out, kept its own formatter with a hardcoded "$". Its
tests used USD inputs only, and it runs only on timeouts, so no one saw it. A 20-F filer whose
generation timed out got "Revenue: $941.2B" for CNY 941.2B, and the read path, which then matched
the number but not the currency, served it with an SEC-verified chip. A bug hunt found it. Review then
found a third writer of the same cells: the prior-period backfill both paths run before storing
(`schemas/summary.py` `attach_normalized_facts`) also hardcoded "$".

**Rule:** The timeout fallback is a summary writer too. Every writer of a summary's P&L table cells
labels money with `app/utils/numbers.py` `money_prefix_for`, never with an inline "$" or a copy of
the rule. When you change how the primary writer labels money, change the helper, so the fallback
and the backfill follow, and keep the parity test passing. Test each writer with foreign-filer
inputs as well as USD ones. A label is read back as well, by one grammar: the display parser
(`parse_display_number`) reads a figure's prefix, and the change-figure reader asks it which
currency that prefix names (`display_currency`), so the two cannot disagree. Its codes are
`ISO_4217_CURRENCIES` in the same module: every current national currency in ISO 4217 (List One less
its fund codes and the X-codes that name no currency) reads back, in capitals as the helper writes
it. The XBRL units choose the label, so a code outside that set, such as a withdrawn one (HRK, BGN),
is still written; its cell does not parse, so its row keeps no change figure. A new reader of money
cells uses the same two functions, or `display_scalars`, which applies them to each scalar a longer
cell holds. The SEC-verified chip is such a reader (`provenance_service.py` `build_metric_source`):
it verifies a figure only in the matched fact's currency, the point's own, else the filing's
`reporting_currency`, else USD. It reads the cell in its own case, scalar by scalar, and verifies
when the scalar that renders the figure names that currency, or when nothing in the cell names a
currency. A bare "¥" names none, so the chip refuses it, as the change-figure reader does. No
currency maps to "$" here. That is the backend's domestic default for XBRL that names no currency.
The frontend's rule for a payload without a currency is different: it shows no symbol
(`lessons/frontend-xbrl-amounts-carry-their-own-currency.md`).

Out of scope, and known: the fallback and the primary filler still differ on scale, on missing
values and on row labels. The primary has a K tier ("950.0K") where the fallback prints "950,000".
The primary drops a row with no current value where the fallback prints "Not disclosed". The labels
read "Net income" against "Net Income". The fallback also skips the primary's bank-total sanitizer
(`prepare_sections`). The parity test compares only the revenue row's money label, so do not
read it as full writer parity. `ai/bank_guards.py` and `ai/financing_comparison.py` keep older
copies of the prefix expression. They behave the same today; do not add another. The chip does
not read a suffix code ("941.2B USD") or a marker outside the grammar ("kr", "Fr"), so such a cell
counts as unlabelled and verifies on its number. A filing whose XBRL records no currency is read as
USD, so a non-USD figure stored with a "$" there keeps its chip until a regeneration or a
re-extraction records the currency.

**Evidence:** `app/utils/numbers.py` `money_prefix_for`, called by `ai/markdown_render.py`
`_apply_structured_fallbacks`, `fallback_summary.py` `generate_xbrl_summary` and
`schemas/summary.py` `attach_normalized_facts`; parity gate
`backend/tests/unit/test_fallback_summary_currency.py::test_the_fallback_labels_money_by_the_primary_path_rule`,
with the backfill pinned by `test_the_stored_fallback_backfills_a_zero_prior_in_the_filer_currency`
and `test_the_primary_path_backfill_labels_a_blank_prior_in_the_filer_currency` in the same file. A
pasted copy of the rule passes those output tests, so
`test_every_writer_takes_its_money_label_from_the_shared_helper` there reads the three writers'
source: each must call the shared helper, and neither it nor its formatter may carry a "$"-led or
"USD" literal. The readers are gated by
`backend/tests/unit/test_numbers.py::test_every_currency_a_money_label_can_carry_parses_and_names_its_code`,
which also pins the list itself by its count and digest, by
`backend/tests/unit/test_metric_delta_service.py::test_an_exact_change_binds_only_to_cells_in_the_facts_currency`
(a code glued to its figure, and "US$", which the change-figure reader once read as Singapore's
"S$"), and, for the stored fallback's change figure in AED, SAR and ILS (none before the full list),
by `test_the_stored_fallback_keeps_its_change_figure_in_any_reporting_currency`. The chip is gated
by `backend/tests/unit/test_provenance_service.py::TestBuildMetricSourceCurrency`, whose
`test_a_figure_is_sec_verified_only_in_its_facts_currency` crosses five fact currencies with every
label `money_prefix_for` writes for them, and through the summary read by
`test_the_summary_read_verifies_a_cny_filings_figure_only_in_cny`; `display_scalars` reads every
label in the ISO gate above, and `test_a_hostile_cell_is_read_scalar_by_scalar_in_linear_time` bounds
its time on long hostile cells. A new writer or reader is review-checked. The same
one-shared-predicate pattern for model-facing surfaces:
`lessons/arch-guard-every-model-facing-surface.md`.
