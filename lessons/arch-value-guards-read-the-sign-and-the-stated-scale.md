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
number ("81.46" for $81.46B); a figure with its own scale word or `$` is read at face value. A
signed value needs the figure's own sign evidence: for a negative value, a minus sign, accounting
parentheses or a loss/decline word in the claim; a positive rate is contradicted by a figure written
negative, and a positive growth rate also by a decline word in the figure's own clause with no
growth word there. Keep such checks falsification-only (keep-evidence read over the whole claim
span, contradiction read in the figure's clause), and when the guard picks out a figure for another
check (currency), pick it by magnitude alone so the sign rule cannot hide it from that check.

**Evidence:** `backend/app/services/copilot/figures.py` (`_figure_matches_value`,
`_figure_sign_agrees`), wired in `fact_guards.py`; gate
`backend/tests/unit/test_copilot.py::test_service_adjacency_reads_the_figure_sign_and_scale`,
`::test_value_guard_sign_rules` and `::test_currency_guard_still_checks_a_negative_fact`. The signed
precedents: `copilot/claim_repair.py::_fact_certifies_claim` and
`tests/unit/test_eval_scorers.py::test_sign_flip_loss_reported_as_profit_is_a_contradiction`. Related:
`arch-bind-bare-table-figures-to-the-declared-scale.md` (a value and its unit are separate claims).
