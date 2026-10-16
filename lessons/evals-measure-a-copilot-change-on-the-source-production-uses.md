# Measure a Copilot change on the source production uses, and record which source it was

Date: 2026-10-16   Area: evals

**Context**: #1111 (2026-10-07) added three quotation-guidance lines to the Copilot's system prompt. Its
copilot-eval draws passed, but every one prepared its sources from the regex fallback. SEC had begun refusing
edgartools' filing index on about 2026-10-06, and the eval's preparation recorded each missing section set as
`null` without raising anything (`tasks/review-evidence/edgartools-homepage-403-2026-10-15/`). Across every retained generation, the new lines
took ASML's text-citation use from 6–9% to 74% of first answers. On BABA FY2025's sections source, the one production
uses, the share went from 10% to 3 of 3, and every one of those three was withheld. Nobody saw it until #1350
restored sections and the eval went red. Every copilot-eval draw of the nine days between was measured on the same
fallback.

**Rule**: Before accepting a Copilot draw as evidence for a model-facing change, read the artifact's
`preparation.json` and the rows' source hashes, and confirm that every source that should have sections was
prepared with them. A draw on the regex fallback measures a different prompt input; it does not accept the change.
Record each revision of the Copilot's system messages (the first generation and both retries) in the RUNBOOK's
"Copilot prompt revisions" table, with the source its measurement used, in the PR that makes it. Classify a red
draw's generations before deciding its cause: a row that recovers on its retry hides how often the first generation
fails.

**Evidence**: `tasks/review-evidence/copilot-table-excerpt-retry-2026-10-16/README.md` (finding 3, and the corpus
scripts). Gate: `backend/tests/unit/test_copilot_prompt_revisions.py` fails when the current first-generation or
retry bytes have no row in the table, or a row has no measured source or no existing evidence path. For eval-baseline
the source check is gated since #1347 (`backend/evals/regression_gate.py`'s native-section floor). Review checks the
rest: a copilot-eval draw's prepared sources until E80 in `tasks/todo.md` lands, what a row says, a row overwritten in
both the table and the test's list, and the model-facing bytes that have no row (the context message, tool schemas
and generation options).
