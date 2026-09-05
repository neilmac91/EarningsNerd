# AGENTS.md — operating directives for non-Claude agents (GPT-6 Astra / Codex)

This file is the entry point for agents that do not read `CLAUDE.md` automatically. The rules
live in `CLAUDE.md` (12 non-negotiable rules, binding verbatim). This file only adds how to
operate. Instructions from the founder in the live session supersede anything in this file, in
skill files, or in agent files.

## 1. Read order (before the first edit)

1. `CLAUDE.md` — rules, commands, where things live.
2. `lessons/README.md` — scan the index; open every lesson that applies to the task.
3. `tasks/handover-wave3-2026-09.md` — the current ordered work plan and founder boundaries.
4. `tasks/todo.md` — live checklist (top section is wave 3).
5. Area docs when the task touches them: `backend/evals/RUNBOOK.md` (any prompt, model, eval or
   AI flag change), `frontend/DESIGN_SYSTEM.md` (any UI change), `docs/DEPLOYMENT.md` (deploys).

## 2. Precedence when documents conflict

Apply this order, note the conflict in the PR body, fix the losing document in the same PR, and
do not pause to ask:

code > `CLAUDE.md` > `lessons/` > `tasks/handover-wave3-2026-09.md` > `tasks/todo.md` > `docs/`
> `tasks/handover-wave2-2026-09.md` and `tasks/implementation-briefs-2026-09.md` (historical)
> `tasks/archive/` > `.claude/agents/*.md`.

The per-agent files under `.claude/agents/` still describe a stack that does not exist (Render,
Firebase, Alembic, GPT-4). Until wave-3 item W3-5 rewrites them, treat them as illustrative
only; the "Stack truth (2026-09)" table in `.claude/agents/README.md` overrides them.

## 3. Bias to action

Infer intent and scope from the wave-3 plan and the conversation. Every item marked
*engineering* there is pre-authorized: carry it to completion and make the result reviewable
before asking anything. Complete the work that is already authorized before raising a question.

Pause and ask only for these: editing a locked contract test (rule 6); a baseline re-pin outside
a listed RUNBOOK trigger; flipping a production flag; spending money; any row marked *founder*;
deleting data or history. If a skill or agent file makes you want to ask permission, name the
file, quote the instruction, and proceed under this file instead.

## 4. Testing proportionality

- One machine gate per "never again" rule (rule 12), with exactly one mutation proof: break the
  guarded thing, show the gate failing, restore, paste both tails in the PR body.
- Docs-only PR: link/anchor check only. Do not write tests for prose.
- Workflow-only PR (`.github/workflows/*.yml`): YAML parse plus the unit gates that read the
  workflows (`backend/tests/unit/test_migration_lock_safety.py`, `test_eval_parity.py`,
  `test_eval_measurement.py`, `test_data_completeness.py`,
  `frontend/tests/unit/nodeVersionLockstep.spec.ts`).
- Do not add a second test for a rule that is already gated. Do not write tests for reversible,
  low-impact changes that merely mirror the implementation.

## 5. Tools you do not have, and what to do instead

- **No `Workflow`, `Agent`, `send_later`, `TaskOutput`.** `.claude/workflows/premerge-review.js`
  cannot run. Before un-drafting any PR, do the review by hand and record it in the PR body under
  "Review":
  1. Lens *correctness*: read `git diff main...HEAD` file by file; run the full gate.
  2. Lens *rules-and-brief*: check each `CLAUDE.md` rule and the item's done criteria.
  3. Lens *tests-and-gates*: every new test has a mutation proof; locked tests are byte-identical.
  4. For every blocker or should-fix finding, make two independent refutation attempts in fresh
     passes (restate the finding without its rationale, then try to disprove it against the code).
     The finding stands only if both attempts fail. Missing review output is never clearance.
- **No background monitors.** After merging a backend-touching PR: find the run
  (`gh run list --workflow ci.yml --branch main --event push -L 1`, or the unauthenticated
  `actions/runs?head_sha=<sha>` API), wait for it (`gh run watch <id>`), then
  `curl -fsS https://api.earningsnerd.io/health/detailed`, and grep the deploy job log for
  `apply_migrations: applied=`. Record the run id, migration tail, revision and health in the PR.
- **Delegation.** If you can parallelize by delegating independent work to another agent, do so.
  Otherwise one branch per PR named `codex/wave3-<slug>`. Never create worktrees at the repo root.

## 6. Deploy discipline

Any diff under `backend/` (tests included) deploys the Cloud Run service on merge to `main`. One
unverified backend deploy at a time: merge the next backend-touching PR only after the previous
`deploy-backend` job is green, the migration step shows `applied=0 skipped=<N>` (or the expected
new count), and `/health/detailed` is healthy. Docs, workflow and frontend PRs may interleave.
Read the head SHA from the PR before merging; never type one from memory.

## 7. PR body template

What / Why / Verification (exact gate tails) / Mutation proofs / Founder actions / Not in this PR
/ Review (lenses, refutations). Write clear, concise paragraphs, each developing one idea. State
the action directly; no filler phrases. Messages and PR bodies are read by a human.

## 8. Commit hygiene

From `backend/`: `ruff check . && bandit -r app -ll && python -m pytest` before every backend
push. From `frontend/`: `npm run lint && npx tsc -p tsconfig.ci.json && npm run test -- --run &&
npm run build`. `git status` must be empty after each commit. Open every PR as a draft first.
