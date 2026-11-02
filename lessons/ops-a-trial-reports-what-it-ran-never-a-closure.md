# Report what a trial ran and nothing more: it never closes a backlog item, a green rerun never names a cause, and a status past a gate is admission only

Date: 2026-11-02 · Area: ops / integration reporting

**Context**: In programme EN-BETA-2026-11, PB-05's integration trials merged each workstream's pull request over
`main` and PB-05's own, then ran a probe for each requirement. The reports posted on #1952 and #1963 said
"E29 (6) is met" and "E29 (5) is met" from probes of the usual path. They also asked that whichever pull request
merged second record both items as done in `tasks/todo.md`.

The chief's reviews on those pull requests, posted before the reports, had kept both items open:
- E29 (6) until the required account-ID stage the founder approved lands with its tests;
- E29 (5) until the completion fails safely without its lock, the pending-handoff lifecycle is settled, and the
  rollout and rollback plan is recorded.

The chief's review on #1954 had the reports corrected. Two earlier corrections in the same cycle were of the same
kind:
- a CI failure that did not recur was offered as settled by a green rerun, though no cause was ever found;
- the journey's 400 past the Pro gate was offered as capability evidence, though it shows only that the entitlement
  admits the account.

**Rule**:
- **Report what ran, not a verdict.** A trial or probe report states what ran and what it showed, in those words
  ("a mismatch answers 409 on this path"). It never gives a verdict on a backlog item ("E29 (6) is met"), and it
  never asks another pull request to mark an item done.
- **Read the reviewer first.** Before writing about a backlog item, read the latest review conditions on the pull
  request that carries it, and say which stay open. Closure is the reviewer's call against those conditions.
- **A rerun is not a diagnosis.** A failure that does not recur stays recorded as diagnosed, cause undetermined,
  until a cause is shown.
- **A status past a gate is admission.** Link the test that runs the path through, or record the capability as
  unproven.
- **Correct wrong claims in place.** Fix the comment or body line itself, with a dated note saying what changed, so
  the record no longer carries the claim.

Review-checked: the rule is about report wording, which no test reads.

**Evidence**:
- PB-05's reports on #1952 (comment 6588244462) and #1963 (comment 6588247995), edited at 22:00 UTC on 2026-11-02
  with correction notes.
- The chief's reviews on #1952 (6587525778), #1963 (6587527350) and #1954 (6586885583, 6589168811).
- #1954's body: the completion list, the PB-02 test links for Multi-Period Analysis and the exports, and the
  `test_sec_document_deadline` record in Verification.
- `docs/ops/closed-beta-acceptance.md` section 3, the E29 paragraph.
