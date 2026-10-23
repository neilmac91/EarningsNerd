# Never drop a review stage to save model tokens: when it can no longer change what ships, spend it on a fresh review of the fix

Date: 2026-10-23   Area: ops, review

**Context**: #1530's high-tier pre-merge review (three Opus lenses, two Opus refuters per finding) found 17 should-fix
findings and queued 34 refuters. Seven had reported, each finding standing, when the session stopped the workflow to
save the rest of their spend. Two were running and 25 had not started; the 27 cut were one of the correctness lens's,
all ten of the rules lens's and all sixteen of the tests-and-gates lens's. Every finding had already been reproduced by its lens and
fixed in the working tree. The founder's next message: "please always ensure to do your best work. work you're proud
of. use lots of tokens to get this right". The stop saved tokens. It also left the fixes, 61 files, with no reader but
their author.

**Rule**:
- Never cut a review tier's agents for cost alone: AGENTS.md §5 sets the tier, and the founder wants the effort spent.
- When a stage can no longer change what ships (its findings are reproduced and fixed), replace it with one that can: an
  independent review of the fix diff, briefed with the code and not your conclusions, before the push.
- Where a push draws a paid eval run (`ops-reserve-eval-baseline-before-each-push.md`), review the fix commit before
  pushing it, so the findings ride the same push.
- State a cut stage's numbers from the workflow's record, not from memory: how many agents were queued, how many
  reported, and which lenses lost theirs.

**Evidence**: #1530, 2026-10-23. The workflow's record (run wf_8d13db62) shows the 34 refuters, seven reported and 27
cut; this lesson first said about fifteen, all the tests lens's, until the fix commit's own tests-and-gates reviewer
counted them. The founder's message followed the stop, and three fresh Opus lenses then reviewed the fix commit before
the push: no blockers, and their should-fix findings rode that push.
