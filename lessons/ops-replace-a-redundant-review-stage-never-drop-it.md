# Never drop a review stage to save model tokens: when it can no longer change what ships, spend it on a fresh review of the fix

Date: 2026-10-23   Area: ops, review

**Context**: #1530's high-tier pre-merge review (three Opus lenses, two Opus refuters per finding) still had about
fifteen refuters queued for the tests-and-gates lens. Each of that lens's findings had already been reproduced by
mutation and fixed in the working tree, so the session stopped the workflow to save their spend. The founder's next
message: "please always ensure to do your best work. work you're proud of. use lots of tokens to get this right". The
stop saved tokens. It also left the fixes, about sixty files, with no reader but their author.

**Rule**:
- Never cut a review tier's agents for cost alone: AGENTS.md §5 sets the tier, and the founder wants the effort spent.
- When a stage can no longer change what ships (its findings are reproduced and fixed), replace it with one that can: an
  independent review of the fix diff, briefed with the code and not your conclusions, before the push.
- Where a push draws a paid eval run (`ops-reserve-eval-baseline-before-each-push.md`), review the fix commit before
  pushing it, so the findings ride the same push.

**Evidence**: #1530, 2026-10-23. The workflow was stopped after the correctness lens's refuters had each confirmed
their finding. The founder's message followed, and the fix commit was then reviewed locally before the push.
