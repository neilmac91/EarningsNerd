# A value guard reads the figure's sign and stated scale; tolerance covers only what the prose leaves open

**Date:** 2026-10-16 · **Area:** Copilot / citation trust

**Context:** The Copilot value guard (`copilot/fact_guards.py::_fact_matches_adjacent_number`) keeps
a fact chip only when a figure in its claim span matches the fact. It compared `abs(value)` and let
every non-percent figure match at any display scaling (÷1e3/1e6/1e9). So "Net income was $1.20
billion [F1]" on a $1.2B loss, "Revenue grew 15.3% [F1]" on a 15.3% decline, and "Revenue was $1.2
million [F1]" on $1.2B revenue each shipped a verified chip. The server's own claim certifier
already refused the sign case ("a negative filing value can never certify a positively stated
amount"), and `evals/copilot_scorers.py` reuses the guard, so the paid copilot eval was blind to the
same answers.

**Rule:** a guard that matches a stated figure against a trusted value may only relax what the
prose leaves open, never override what it states. Display-scaling tolerance belongs to a bare
number ("81.46" for $81.46B). A figure with its own scale word or `$` is read at face value, and so
is one in accounting parentheses with its unit outside them ("$(1.2) million").

The sign is read only where the prose states one, so the check stays falsification-only:

- A negative amount or margin written without a sign loses its chip when its own clause, or the
  label it follows ("Net income: $1.2B"), names a profit-type metric (income, profit, earnings, EPS,
  margin, cash flow) and its claim span holds no sign word (loss, deficit, negative, used, outflow).
  "Fell to" or "down" state a change, not a sign.
- A negative growth rate loses its chip to a rise stated in its own clause.
- A positive rate loses its chip to a figure written negative (a minus sign, "negative 15.3%", or
  the table form "(15.3)%"; "(15.3%)" in prose is an aside). A positive growth rate also loses it to
  a fall stated in its own clause.
- The change of a loss is not read: "the net loss narrowed" is a positive rate.

Do not demand sign wording the prose may lack. A comparative ("compared with $0.8 billion") sits in
a span the previous chip has bounded, away from the word "loss", and is correct. The prompt puts the
marker right after the figure, so a figure used attributively ("a $1.2 billion [F1] loss") has its
sign noun outside the span and keeps its chip. Read the profit name only where it names the figure:
an earlier clause names other items ("reflecting lower interest income, was $1.2 billion"). When
the guard picks out a figure for another check (currency), pick it by magnitude alone so the sign
rule cannot hide it from that check.

**Evidence:** `backend/app/services/copilot/figures.py` (`_figure_matches_value`,
`_figure_sign_agrees`, whose docstring lists the known false keeps), wired in `fact_guards.py`; gate
`backend/tests/unit/test_copilot.py::test_service_adjacency_reads_the_figure_sign_and_scale`,
`::test_value_guard_sign_rules`, `::test_resolver_keeps_a_loss_chip_unless_its_clause_names_a_profit`,
`::test_service_keeps_a_loss_chip_whose_sign_word_is_outside_its_clause` and
`::test_currency_guard_still_checks_a_negative_fact`, plus
`test_copilot_evals.py::test_fact_adjacency_flags_wrong_sign_and_wrong_scale` for the eval scorer.
The signed precedents: `copilot/claim_repair.py::_fact_certifies_claim` and
`tests/unit/test_eval_scorers.py::test_sign_flip_loss_reported_as_profit_is_a_contradiction`. Related:
`arch-bind-bare-table-figures-to-the-declared-scale.md` (a value and its unit are separate claims).
