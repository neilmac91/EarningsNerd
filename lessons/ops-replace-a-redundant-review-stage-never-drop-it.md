# Never cut review agents to save model tokens, neither a stage nor a report's own refuter pair: when a stage can no longer change what ships, spend it on a fresh review of the fix

Date: 2026-10-23, updated 2026-11-01 (#1855)   Area: ops, review

**Context**: #1530's high-tier pre-merge review (three Opus lenses, two Opus refuters per finding) found 17 should-fix
findings and queued 34 refuters. Seven had reported, each finding standing, when the session stopped the workflow to
save the rest of their spend. Two were running and 25 had not started; the 27 cut were one of the correctness lens's,
all ten of the rules lens's and all sixteen of the tests-and-gates lens's. Every finding had already been reproduced by its lens and
fixed in the working tree. The founder's next message: "please always ensure to do your best work. work you're proud
of. use lots of tokens to get this right". The stop saved tokens. It also left the fixes, 61 files, with no reader but
their author.

#1855 cut the same tier another way. Once two lenses reported should-fixes, a Sonnet call grouped the reports it judged
to be one defect, and each group shared one pair of Opus refuters instead of a pair per report. By its own figures it
saved about three Opus calls per high-tier review (380 to 278 should-fix refuter calls over 35 past runs). It saved no
time unless the refuters would have queued, since the grouping ran before any refuter started and the refuters run in
parallel. What it gave up were independent attempts on the defects several lenses agree on, the likeliest to be real:
in 5 of 34 past duplicate groups the separate pairs had split, and the copy that stood was right. #1855's body set that
risk out, and records that the founder chose to keep it on 2026-10-31. On 2026-11-01 the founder decided to remove it
and keep its severity fix.

**Rule**:
- Never cut a review tier's agents for cost alone: AGENTS.md §5 sets the tier, and the founder wants the effort spent.
- One refuter pair per report is part of the tier: never share a pair among the reports of one defect, from one lens or
  several, since each pair is an independent chance for a real defect to stand (partly gated by
  `frontend/tests/unit/premergeReviewWorkflow.spec.ts`, whose header lists the reviews it runs and what stays out of
  its reach).
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

#1855, merged as 2a2136f6 on 2026-10-31; its body gives the 380-to-278 count, the 5-of-34 split and the 2026-10-31
decision. The spec gates the pair per report in four cases: one parses the script for the ways to an agent its header
lists and is scored on planted sources; one runs a defect reported twice with every combination of its refuters'
answers; one does the same for two reports identical in every field; one sweeps reviews of many shapes, each refuter's
answer drawn on its own. They fail when an agent other than the lenses and the refuters runs, when a refuter is shown
anything its report alone would not show it (outside the identical reports, whose prompts are compared as a whole), or
when a report's outcome, or the review's, differs from what each report's own refuters' answers give. Five review
rounds of the gate on #1915, with two refuters on each finding, and the reviews of its last two fixes found forms of
grouping that its earlier versions let through: a larger review, votes coupled by title or by a quoted line, a refuter
shown other reports' words or a lens's summary, an agent reached through an alias, the runtime's `workflow` or the stack
of a harness that ran the script outside strict mode, a missing vote borrowed on a real PR, draws that tied a report's
two refuters together, a review with a nit, copies identical in every field, a PR called the way AGENTS.md §5 documents
or with its tier set on the batch, and a script that carries what a run writes into `args` over to the next run. Of
the mutants they built, the gate as it landed kills every one that breaks the rule in the reviews it runs, and its
header names what remains out of its reach, such as a change that tells the runtime from the harness, which the review
of #1915's fix 6641a58b..56163b8d raised.
