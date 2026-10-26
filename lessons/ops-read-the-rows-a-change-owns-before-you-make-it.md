# Before you change a file, read the open rows its next writer owns, and carry or answer each in the same pull request

Date: 2026-10-26 · Area: ops / records

**Context.** E92 was a POSTPONE row owned by "the next functional change to `summary_stages`". It carried D-046's
F35: the pipeline's stream sentences change with that change, never in a pull request that opens the pipeline for
copy alone, since its stream tests are locked and its strings eval-pinned. The row was written on 2026-10-18
(#1384); four pull requests changed `summary_stages` after it and merged without it: #1545, #1585, #1660 (E214) and
#1670 (E216). None of their bodies names E92, and E216's four review lenses, briefed on its own row and the files it
touched, did not raise it. E217 (#1671), the next such change, found E92 while recording its own scope and carried
it.

**Rule.** Before the first commit that changes a file, grep `tasks/todo.md` for rows whose owner names that file,
its directory or its role: "the next writer of `X`", "the next functional change to `Y`", "the next writer of a
flag-off runner in `Z`". Carry each such row in the same pull request, or say in its body why not; a row deferred
until "the next change" is not deferred past it. A review lens's brief names the files the change touches and asks
the same question.

**Gate.** Review-checked. A row's owner is prose, and whether a change is "functional" is a reading of it, so no
machine check sees the match.

**Evidence.** E92 (`tasks/todo.md`, written by #1384 and deleted by #1671); D-046 in `docs/brand/decisions-log.md`;
#1545, #1585, #1660 and #1670 (each changed `summary_stages` and merged without it); #1671 (E217, which carries it).
