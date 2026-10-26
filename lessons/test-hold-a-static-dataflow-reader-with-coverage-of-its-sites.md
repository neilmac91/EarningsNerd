# A static reader of dataflow is never complete: let it name the sites, then run them and fail by line

Date: 2026-10-26   Area: test, backend

**Context**: `backend/tests/unit/test_data_note_reasons_have_words.py` (PR #1659) holds that every reason
code the backend writes has words. It began as an AST reader that follows a string into a `reasons` list.
Four review rounds each found a dataflow form it missed: a method's `self` offset, a loop target, a tuple
unpacking and an imported constant in the first; a parameter its own function rebinds (lost by the first
fix), a list filled by `append` under another name and a parameter's default in the second; and a tuple
loop target over a table (`for code, limit in CHECKS:`) in the third. Each fix widened the reader by the
forms a review had named. The second round added a runtime check, but it compared codes, not branches, and
drove only four of the five emitter modules, behind a comment that called the fifth undrivable. So a new
branch in a driven module, or any code in the fifth, still passed in a form the reader missed.

**Rule**:
- Expect the reader to be incomplete. Python's dataflow has no end of forms, so a reader that gains one
  form per review will be found short again. Give it the job it can finish: name every module that writes
  the thing the rule is about, and every line there that writes it (each site, each call that binds a
  parameter that flows to one, each literal it collects).
- Then run what it names. Drive every one of those modules through its writing branches, traced
  (`sys.settrace` works on 3.11 to 3.13; restore any tracer already set), and fail on three things:
  - a value written that breaks the rule (here, a code with no words);
  - a line the reader names that no driver executes, so a new branch fails by line until someone drives it;
  - a value a driver writes that the reader did not find in those modules, so a form the reader cannot
    follow fails wherever a run reaches it.
- Drive a module behind a database on an in-memory SQLite engine before calling it undrivable. Keep a
  written reason beside any line truly left to the reader alone.
- Keep the reader's header exact. Name what it follows and what it is known to miss, plant each miss with
  a literal it would collect if it reached the form, and say that a form on neither list is unknown. Say
  what the run cannot see too: a module where the reader finds nothing is outside both halves.
- Still take each form a review names from the language's whole family, not the one form named (see
  `test-gates-must-be-as-wide-as-their-rule.md`); the run is the backstop, not a licence for a narrow
  reader.

**Evidence**: PR #1659's review rounds 1 to 3 (2026-10-25 and 26) and their fix commits;
`backend/tests/unit/test_data_note_reasons_have_words.py` (`read_reasons`, `_drive`, `_executed` and
`test_the_drivers_reach_every_reason_writing_line_and_write_only_reasons_the_reader_finds`). Its mutation
proofs: a reconcile branch that writes a worded code the reader misses fails (c), a new branch the drivers
do not reach fails (b), and an unworded code in a form the reader misses fails (a) while the static test
passes.
