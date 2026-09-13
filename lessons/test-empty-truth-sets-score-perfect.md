# An empty truth set scores 1.0, not 0 — guard the decision, not the scorer

Date: 2026-09-13   Area: test

**Context**: The wave-3 plan's W3-8b design argued that 6-K goldens "have no XBRL facts, so the
recall/precision scorers score zero", and rested the safety case on the pin tool refusing such a
report. Both halves were false. `score_numeric_accuracy` returns `1.0, [], []` for an empty
ground truth (`backend/evals/scorers.py:161`) and `score_numeric_precision` returns `1.0` both
when `ground_truth` is empty and when no labeled field is checkable
(`backend/evals/scorers.py:272,296`). Those returns are deliberate: a filer that legitimately
omits a line must not be penalised. `pin_baseline.py` checked the *completeness* of the verified
set but never the *content* of an entry, so a hand-filled entry marked `verified` with no facts
would have been scored a perfect 1.0 on both dimensions and pinned. The harm is not a number
going up — `mean_numeric_accuracy` and `mean_numeric_precision` are already pinned at 1.0 by 26
genuinely checked filings — it is that the pinned means and `golden_set_size` would then rest on
less evidence than they claim, with one entry counted as measured that verified nothing. The
recall half of the behavior was already pinned by
`test_numeric_accuracy_no_ground_truth_is_not_penalized`; the precision half was not, and the plan
prose drifted the opposite way from both.

**Rule**: Never reason about a scorer's empty-input behavior from prose — read the early-return.
When "nothing to check" is a deliberate 1.0, the cost is not a visible zero but a number that
reads as measured and is not, so the guard belongs at a boundary that *consumes* the score,
never in the scorer, whose lenient return other filings depend on. Such a score usually has
more than one consumer: enumerate them and say which you actually guarded. Here
`pin_baseline.build_baseline` refuses a ground-truth-less entry, but `evals/regression_gate.py`
compares candidate means to the pin without ever checking the golden set they were measured on
(no `golden_set_sha256` anywhere in it; `golden_set_size` appears only in a print at `:279`),
so a vacuous entry can still be *measured* and pull a candidate run toward 1.0. Every numeric
`_HARD_GATES` entry is a `decrease` gate, so that dilution only ever loosens the gate. A design
note that asserts a scorer's behavior must cite the file:line it read.

**Evidence**: `tasks/handover-wave3-2026-09.md` W3-8b (corrected in the same PR as this lesson);
`backend/scripts/pin_baseline.py` vacuous-entry refusal;
`backend/tests/unit/test_eval_parity.py::test_pin_refuses_a_verified_entry_measured_on_no_ground_truth`;
`tasks/handover-astra-2026-09-13.md` §2a, which flagged the contradiction.
