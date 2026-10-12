# A probe asserts what only a successful render shows, counted from its input; a heading that also frames the error state proves nothing

Date: 2026-10-11   Area: test

**Context**: `measure-current.mjs` waited for the "AI trend analysis" heading before measuring. After #1225, the
fixture builder's completion carried `narrative_presentation: null`, which the current frontend refuses:
`decodeNarrativePresentation` throws, and the page shows its evidence error under that same heading. The
harness still recorded all 20 configurations with exit 0. The founder's review of `c7fc65e` found it, and it
reproduced with the builder's own output against a stamped current-`main` build.

**Rule**: Make a harness or e2e probe wait for, and count, what only a successful render shows, with the
expected count taken from the input, so that a refused or failed response fails the run. Here that is every
citation of the completion, as a narrative chip and as a Sources row. Headings, containers, landmarks and a
spinner's absence also stand over error states, so they are never the success signal.

**Evidence**: `tasks/analysis-redesign-2026-10/harness/measure-current.mjs` (`narrativeCitations`, `sourceRows`).
The proofs on #1197: the earlier harness passed the null-envelope fixtures, and the new one fails them ("found 0
and 0") and passes the committed ones (39 and 39).
