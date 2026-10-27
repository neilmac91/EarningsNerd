# Before you change a file, read the open rows its next writer owns, and carry or answer each in the same pull request

Date: 2026-10-26 · Area: ops / records

**Context.** E92 was a POSTPONE row owned by "the next functional change to `summary_stages`". It carried D-046's
F35: the pipeline's stream sentences change with that change, never in a pull request that opens the pipeline for
copy alone (D-046's reason: its stream tests are locked and its strings eval-pinned, though neither pinned these
sentences, #1671 found). The row was written on 2026-10-18
(#1384); four pull requests changed `summary_stages` after it and merged without it: #1545, #1585, #1660 (E214) and
#1670 (E216). None of their bodies names E92, and E216's four review lenses, briefed on its own row and the files it
touched, did not raise it. E217 (#1671), the next such change, found E92 while recording its own scope and carried
it.

**Rule.** Before the first commit that changes a file, grep `tasks/todo.md` for rows whose owner names that file,
its directory or its role: "the next writer of `X`", "the next functional change to `Y`", "the next writer of a
flag-off runner in `Z`". Carry each such row in the same pull request, or say in its body why not; a row deferred
until "the next change" is not deferred past it. A review lens's brief names the files the change touches and asks
the same question.

**Gate.** Partly gated. `backend/scripts/review_gate.py` (`review-gate`, a required check on `main`) fails a pull
request that changes a file whose path holds, as whole segments, a path an open row's owner names in backticks,
until its title, body or a commit message names each such row (E218). It reads the base branch's `tasks/todo.md` as
it runs; the owner is the parenthetical after the row's id and disposition, and only a segment of it that names a
next change ("next writer of", "the next functional change to", "the next PR that changes") names paths, so a tier
note ("high tier for `internal.py`") binds nothing. `backend/tests/unit/test_review_gate.py` pins that reading. On
the live file it fails a span in such a segment that names no tracked file (a call of a function that a code file
the row leaves to its next change defines, outside the test roots, such as `isXbrlCitation()` beside
`copilot-api.ts`, is excepted, so the row holds the function's own file), a segment that says "next" and names a
path in a phrase the gate does not bind ("the next edit of"; the framework's name and paths aside), and a
parenthetical that would bind in a row whose head the gate does not read: the check could hold none of them. What an
owner asks of a change ("the next functional change"), whether the body's answer holds, and an owner that names a
role instead of a path ("the next mail writer", "the next writer of each router named") stay a reading.

**Evidence.** E92 (`tasks/todo.md`, written by #1384 and deleted by #1671); D-046 in `docs/brand/decisions-log.md`;
#1545, #1585, #1660 and #1670 (each changed `summary_stages` and merged without it); #1671 (E217, which carries it).
