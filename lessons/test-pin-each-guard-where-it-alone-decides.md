# Pin each guard with an input only it decides, and re-run every mutation the guards share when one of them changes

Date: 2026-10-24   Area: test / mutation proofs

**Context**: #1530's takeaway figure pattern (`backend/app/services/provenance_service.py`,
`_NON_FIGURE_NUMBER_RE`) withholds a takeaway that states a figure beside a replaced one, through guards
that overlap: the unit lookahead `_NO_UNIT`, the one-or-two-digit listed number `_LISTED`, and the rule that
a number after a comma is listed only where the list goes on (`_LIST_GOES_ON`). Commit 66d8819c pinned each
unit word with a case after a comma-listed number ("See Note 7, 120 billion in revenue."), and every one of
those mutants died. Commit 3b74bf39 added the list rule, which withholds a count after a comma by itself. The
cases still passed, but on 3b74bf39 ten unit mutants survived: the cases no longer pinned the words they were
written for. Only a re-run of the whole mutation set on the new commit showed it; the new rule's own mutants
all died.

**Rule**:
- Pin a guard with an input that only that guard decides, one every other guard would let through. In a
  pattern of alternatives, set the case in the guard's own context: the figure pattern's units sit after a
  month's day or a figure shaped like a year, which the other branches read as a date ("June 25 per cent",
  "2025 billion").
- When a guard changes, re-run every mutation of the code it shares a decision with, not only the new guard's
  own: a test can keep passing and stop pinning.
- A mutant that survives because another guard already decides its input is an equivalent mutant (record it as
  one, with why) or a pin in the wrong place (move the test). Never leave it unexplained.

**Evidence**: #1530 commits 3b74bf39 (the list rule) and e040334a (the unit cases re-pinned), and
`backend/tests/unit/test_provenance_service.py::TestFiledFigureSwap::test_a_takeaway_that_states_a_number_is_withheld`.
The same branch's two equivalent mutants are recorded in its PR body: the clauses of `enrich_raw_summary`'s
early return, which never runs because the Risks projection always writes a list. Review-checked: no
mutation tool runs in CI.
