# Keep moving under a standing founder authorization: mark finished work ready and merge it, and stop only at the boundaries still held

Date: 2026-09-07 · Area: ops / working style

**Context.** After three releases that each paused for an individual "approve the paid
Copilot run" decision, the founder approved the fourth and corrected the pattern: "going
forward, I need you to keep making progress and not constantly wait for my approvals." The
pauses had each cost a turn of wall-clock time on a queue whose value depends on throughput.

**Rule.** When the founder gives a standing authorization in their own words, treat it as
durable for the rest of the engagement and record it in `tasks/todo.md` the same day: proceed
through every step it covers without asking again, and keep the routine gates (draft-first,
full local gate, independent lens, one paid evaluation at ready for a PR that touches the
`copilot-eval` workflow's `paths:` filter (`backend/**` before #1123, the eval's own inputs after it), fixes pushed as
draft) as the discipline that makes autonomy safe. Ask only for the boundaries the founder still
holds — production flags, capacity, prices, trial/promo/registration policy, legal, destructive
data or history operations, historical replay, locked contract tests, live email or job
execution as a test, live account actions, the AI provider — and state the single decision with
a reviewable scope when one is genuinely needed. Never widen a standing authorization silently:
say what it now covers in the ledger entry that records it.

**Widened 2026-09-07 (evening).** Before going to sleep the founder said: "proceed … please get
as much done tonight as you can … you have my approval to perform additional paid evaluations
if you deem them to be necessary." The authorization now covers more than one paid Copilot run
per PR that starts the run when a re-run is needed (a fix pushed after ready, or a second evaluation that a
finding makes worthwhile), still one at a time and each recorded with its reason. The held
boundaries above are unchanged.

**Evidence.** Founder message of 2026-09-07 on PR #754 ("approved. please proceed. going
forward, i need you to keep making progress and not constantly wait for my approvals");
`tasks/archive/todo-ledger-through-2026-10-07.md` E07b slice 2 record; `lessons/ops-continue-approved-engineering.md` (the
earlier form of the same rule, scoped to releases).


**Updated authority and spend hold — 2026-09-08 (CEO planning request).** The founder delegated
direct account access and necessary edits, replacing the earlier blanket console/live-account
restriction for this work. Use existing access to obtain facts directly and carry out reversible,
evidence-supported corrections; retain normal code gates and document each account change.
The founder specifically withheld universe-wide pregeneration until they have full confidence
in world-class filing analysis. That instruction supersedes its earlier D4 spend approval.
Existing eight-ticker example refreshes are a different workload, verified from the actual job
command; do not silently broaden either approval. A green regression or completed re-pin is not
the founder's quality acceptance or permission to release universe spend. See
[the implementation plan](../tasks/ceo-implementation-plan-2026-09-08.md) for the proposed evidence
program and the remaining specific decisions. This is an operator authorization record, not a
claim that a new software budget/quality gate has already been implemented.

**Release queue exception — 2026-10-12.** Neil authorized the existing `AGENTS.md` §5
per-PR review exception for this coordinated release queue when hosted Codex review allowance
is exhausted and every Claude finding has a concrete fix or a reasoned disposition. Verify the
quota response, bind the substitute review to the actual head and obtain a successful required
review gate. This queue-specific authorization changes neither required application/security
checks nor branch protection, budgets, purchases, owner merges or founder holds; it creates no
standing exception for later work. The existing review-gate parser enforces the documented
mechanism. First execution: [#1261](https://github.com/neilmac91/EarningsNerd/pull/1261), all seven
checks successful before normal squash `55b2d557`, with the future #1253 fixture obligation retained.

**The ready mark — 2026-10-20.** Finished pull requests waited as drafts "so the founder marks it
ready", because the ready transition starts the paid `copilot-eval` draw (#1436 and #1437 said so in
their bodies). The founder corrected it: "Please don't wait for me to mark stuff ready. If it's
ready, then please proceed with the necessary steps to get it sorted and ready for merging (and then
merge it)" (quoted on #1436, comment 6300785612). The session driving a pull request marks it ready
itself once its local gates, its tier review, the draft's CI and Codex's review of the draft head
are done; `review-gate`, `copilot-eval` and the merge follow the mark. When the ready transition
starts a paid draw, the session reads the balance first (`deepseek-balance.yml`) and writes the
reservation on the pull request: the reason, the expected cost and the amount reserved under the
rule `AGENTS.md` §6 names (`DECISIONS-09`). The CODE RED ledger is the chief's to write, so another
session states the reservation on the pull request, reads the balance again after the draw and posts
that reading there too. Since record 29 the chief's records have kept other writers' paid runs
outside the ledger (before it, record 27's event 67 recorded one dependency sweep's runs, at todo
row E23's request); whether the ledger should settle them is the founder's call
(`tasks/code-red-20261004/runtime/control/DECISIONS-38.md`, founder action 10). §3 already
authorizes that bounded spend after the balance read. A pull request whose diff touches
`backend/app/`, `backend/evals/` or `backend/prompts/` also draws before the mark, on every push,
draft or not, so the session reserves for that from its opening (`eval-baseline`;
`ops-reserve-eval-baseline-before-each-push.md`). The session merges the pull request
once Codex and CI are green and the draw is green or triaged as not the pull request's by
`backend/evals/RUNBOOK.md`'s rule for a red `copilot-eval` run, never drawn again to get a green
one; one that deploys the backend merges alone, after the previous deploy is verified, and its own
deploy is verified after it (§6). When the session that opened a pull request has gone quiet (no
push, comment or CI run of its own for an hour after its body named the next step), the principal
session, which the founder runs as principal engineer, drives it the same way: it says so on the
pull request first, and stops if the opening session answers there. A ready or merge call that the
session's permission check refuses is a stop: report it, and do not retry it through another tool.
Whether the CODE RED chief may merge its own records pull requests without a word for each stays the
founder's row F52. Every boundary above and in `AGENTS.md` §3 stays held. This section is recorded
here, as the 2026-09-08 and 2026-10-12 ones are, because `tasks/todo.md`'s handover block holds five
lines and is the CODE RED chief's. First use: #1436, marked ready after a USD 13.06 balance read and
merged as `707d80e5`.

**Correction rounds on a records pull request — 2026-10-22.** Record 46's pull request (#1488) took three commits
after its record (Codex's two P1s restated as hand checks; the fact-check's thirty-two corrections with Codex's P2;
the reviewer's first pass), each also bringing the record's account of main up to date, and each one a push, a CI
run, a Codex review and a round of draft-gate failures, while main moved six times under it. The founder said: "Merge
1488 when ready. as there's been 4 corrections already, unless there's a real issue identified, make progress and move
towards merging." The chief marked #1488 ready at 2026-10-22T19:13:44Z, before the reviewer had returned any result on
its head `b0befd2` (its latest, the first pass, was bound to `7680850`): a deviation, because missing review output is
never clearance (`AGENTS.md` section 5). The founder then said: "merge it once CI and the reviewer are clean." The
delta check bound no blocker to `b0befd2`; its should-fix and three of its four nits went to record 47 instead of a
fourth correction, and the fourth, on the pull request's body, into the body's fifth version after the merge. The
merge, `888cf06a` at 19:31:15Z, came after CI's success on `b0befd2` (19:21:48Z), the ready mark's own Codex review,
completed with no unresolved finding (F58), and the delta check's verdict
(`tasks/code-red-20261004/runtime/control/DECISIONS-46.md`'s "After the cutoff" for the commits; DECISIONS-47 for the
rest). This section records one pull request and sets no rule: no gate can tell a real issue from a nit (rule 12;
`AGENTS.md` section 4), and no merge step changes.
