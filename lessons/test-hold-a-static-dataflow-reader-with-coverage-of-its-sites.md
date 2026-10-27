# A static reader of dataflow is never complete: let it name the sites, then run them and fail by line

Date: 2026-10-26   Area: test, backend

**Context**: `backend/tests/unit/test_data_note_reasons_have_words.py` (PR #1659) holds that every reason
code the backend writes has words. It began as an AST reader that follows a string into a `reasons` list.
Each of seven review rounds found dataflow forms it missed: a method's `self` offset, a loop target, a tuple
unpacking and an imported constant in the first; a parameter its own function rebinds (lost by the first
fix), a list filled by `append` under another name and a parameter's default in the second; a tuple loop
target over a table (`for code, limit in CHECKS:`) in the third; and in the fourth, that table filled by
`append` (bound as the row, not as a list of rows), a nested index, a table's starred rows, `reversed()` and
a bare call bound to another module's function of the same name; in the fifth, a name bound to the list on a
line a driver ran, written through in a branch none did; in the sixth, the reverse (a list filled under
another name in such a branch, then stored as the reasons or folded into them) and a loop or `with` target
bound to the list; in the seventh, a generator's element over an iterable no driver fills, on a line a driver
ran, and a list folded in through `dict.fromkeys`. Each fix widened the reader by the forms a review had named. The second round added a
runtime check, but it compared codes, not branches, and drove only four of the five emitter modules, behind
a comment that called the fifth undrivable. The third held it by line, but nothing tested the line naming
(dropping it passed every test), and a write the reader could not see named no line, so it escaped both
halves: an alias, a setdefault, or any write in a module with no site the reader knew.

**Rule**:
- Expect the reader to be incomplete. Python's dataflow has no end of forms, so a reader that gains one
  form per review will be found short again. Give it the job it can finish: name every module that writes
  the thing the rule is about, and every line there that writes it (each site, each call that binds a
  parameter that flows to one, each literal it collects).
- Name every line in those modules that mentions the thing at all (here any name, attribute, keyword or
  string `reasons`, and any local name tied to it, to a fixpoint, each way: assigned from an expression that
  mentions it, or held by a site's value or by what a tied name is assigned), not only the writes the reader
  recognises: a write in a form it misses usually names the list somewhere in its function. A name tied only
  by a read of `reasons` is tied both ways like any other, and a comprehension's names count across its
  function, so a line that cannot write a reason can be required: drive it, or name it with why none can run
  it. Hold every other
  mention in the codebase to a named list of exempt and read-only functions, held exact, so a new module
  that writes in a missed form usually fails too.
- Then run what it names. Drive every one of those modules through its writing branches, traced
  (`sys.settrace` works on 3.11 to 3.13; restore any tracer already set), and fail on three things:
  - a value written that breaks the rule (here, a code with no words);
  - a named line that no driver executes, so a new branch fails by line until someone drives it;
  - a value a driver writes that the reader did not find in those modules, so a form the reader cannot
    follow fails wherever a run reaches it.
- Test the naming itself: assert the lines the reader names on a planted module (a site, a binding call, a
  literal on a line apart from its site), and that each emitter module has lines to run. Name the line that
  runs, not the line a literal sits on: CPython folds a display of constants into one constant loaded at its
  first line, so its other lines never run.
- Key a line left to the reader alone by function and line text, with its reason, and fail an entry that
  names no unreached line or more than one, so a shifted line number or a repeated line cannot excuse another.
- Drive a module behind a database on an in-memory SQLite engine before calling it undrivable. Keep a
  written reason beside any line truly left to the reader alone.
- Keep the reader's header modest and true. Name what it follows and what it is known to miss, plant each
  miss with a literal it would collect if it reached the form, and say that a form on neither list is
  unknown. List what escapes by class, not as a closed list, and plant an example of each class the gate
  can hold. Here a code the reader misses passes where no value the run gathers holds it, by six classes: a
  write the reader misses, on a line no driver runs that the run does not name (a helper's parameter, a
  function's return, a closure's variable); a key built at run time; what a module's top level or a class
  body writes, read but not required, or holds as a key; a function exempt or read-only by a wrong reason,
  or any line named undriven; a value no driver evaluates in a write a driver runs, or on a line one runs (an
  arm of a conditional, `or` or `and`, a comprehension's or generator's element over an iterable no driver
  fills, `reasons.extend(change.code for change in changes)`, or a write after a one-line `if`), since the
  run holds lines, not the values in them; and a value a driver writes where the run does not gather it.
- State each class as the edge of what the mechanism reads (the lines it names, the values it gathers),
  not as the forms found so far, and start from what an escape needs (here, a code the reader misses that no
  gathered value holds), so a form not yet seen falls inside a class by construction and the docs stay true
  as the code grows.
- Stop when the remaining escapes are classes no cheap rule closes. Five rounds of "one more form" is the
  sign: close the realistic ones, state the rest, and move on.
- Still take each form a review names from the language's whole family, not the one form named (see
  `test-gates-must-be-as-wide-as-their-rule.md`); the run is the backstop, not a licence for a narrow
  reader.

**Evidence**: PR #1659's review rounds 1 to 7 (2026-10-25 to 27) and their fix commits;
`backend/tests/unit/test_data_note_reasons_have_words.py` (`read_reasons`, `_drive`, `_executed` and
`test_the_drivers_reach_every_reason_writing_line_and_write_only_reasons_the_reader_finds`). Its mutation
proofs: a reconcile branch that writes a worded code the reader misses fails (c), a new branch the drivers
do not reach fails (b), and an unworded code in a form the reader misses fails (a) while the static test
passes; in round 4, an alias or a setdefault in an undriven branch, an f-string code in the lineage
backfill and a new module that writes one fail (b) or the guard, and dropping the reader's line naming fails
the planted test; in round 5, the same alias or setdefault bound on a driven line and written through in an
undriven branch fails (b), while a helper's parameter written in an undriven branch passes, as the header
says; in round 6, a list filled with an f-string in an undriven branch and then stored as the reasons
(`"reasons": codes`, `reasons=codes`) or folded into them (`reasons.extend(extra)`), and a write through
a `for` or `with` target bound to the list, each fail (b); in round 7, the same list folded in through
`dict.fromkeys` fails (b), while a generator's element over an iterable no driver fills passes, as the
header's fifth class says.
