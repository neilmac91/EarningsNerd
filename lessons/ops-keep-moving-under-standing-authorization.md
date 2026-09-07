# Keep moving under a standing founder authorization; stop only at the boundaries still held

Date: 2026-09-07 · Area: ops / working style

**Context.** After three releases that each paused for an individual "approve the paid
Copilot run" decision, the founder approved the fourth and corrected the pattern: "going
forward, I need you to keep making progress and not constantly wait for my approvals." The
pauses had each cost a turn of wall-clock time on a queue whose value depends on throughput.

**Rule.** When the founder gives a standing authorization in their own words, treat it as
durable for the rest of the engagement and record it in `tasks/todo.md` the same day: proceed
through every step it covers without asking again, and keep the routine gates (draft-first,
full local gate, independent lens, one paid evaluation per backend PR at ready, fixes pushed as
draft) as the discipline that makes autonomy safe. Ask only for the boundaries the founder still
holds — production flags, capacity, prices, trial/promo/registration policy, legal, destructive
data or history operations, historical replay, locked contract tests, live email or job
execution as a test, live account actions, the AI provider — and state the single decision with
a reviewable scope when one is genuinely needed. Never widen a standing authorization silently:
say what it now covers in the ledger entry that records it.

**Evidence.** Founder message of 2026-09-07 on PR #754 ("approved. please proceed. going
forward, i need you to keep making progress and not constantly wait for my approvals");
`tasks/todo.md` E07b slice 2 record; `lessons/ops-continue-approved-engineering.md` (the
earlier form of the same rule, scoped to releases).
