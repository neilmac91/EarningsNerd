# AGENTS.md — operating directives for non-Claude agents (GPT-6 Astra / Codex)

This file is the entry point for agents that do not read `CLAUDE.md` automatically. The rules
live in `CLAUDE.md` (12 non-negotiable rules, binding verbatim). This file only adds how to
operate. Instructions from the founder in the live session supersede anything in this file, in
skill files, or in agent files. Claude Code sessions follow §4–§8 too; `CLAUDE.md` points here.

## 1. Load context for the task

Read `CLAUDE.md` for repository rules. Use `lessons/README.md` to find lessons relevant to
this task; open those lessons rather than the whole collection, and skip its "Enforced by a
machine gate" section.

- Continuing the master plan or a release: read `tasks/todo.md`, the short open-items file (one
  line per open item, newest first, holds by pointer). The historical ledger is
  `tasks/archive/todo-ledger-through-2026-10-07.md`; its unchecked rows are not a to-do list.
  Handovers (`tasks/handover-astra-2026-09-19.md` and the September 28 checkpoint in
  `tasks/continuation-plan-2026-09-26.md`) are dated evidence; open them only when an open item
  points there.
- Service boundaries or data flow: `docs/ARCHITECTURE.md`.
- Prompt, model, eval or AI flag changes: `backend/evals/RUNBOOK.md`, sections "Regression gate
  (B1)" and "Judging a pull request's eval artifact" (mandatory), "Gotchas" before any paid run.
- UI work: `frontend/DESIGN_SYSTEM.md` §1–§3 and §12 (mandatory), [DESIGN.md](DESIGN.md)
  "Components" and "Do's and Don'ts" for a new or changed component, both in full for a token,
  theme or typography change. Include both in UI subagent briefs; follow the
  `design-docs-maintenance` skill (`.claude/skills/meta/design-docs-maintenance/SKILL.md`).
- Deployment work: `docs/DEPLOYMENT.md`.

Routine isolated edits need none of the handovers, the ledger or the repository map.

## 2. Precedence when documents conflict

Apply this order, note the conflict in the PR body, fix the losing document in the same PR, and
do not pause to ask:

code > `CLAUDE.md` > `lessons/` > `tasks/todo.md` (open items) > `docs/` > the handovers
(`tasks/continuation-plan-2026-09-26.md` September 28 checkpoint, `tasks/handover-astra-2026-09-*.md`,
`tasks/handover-wave3-2026-09.md`, `tasks/handover-wave2-2026-09.md`) and
`tasks/implementation-briefs-2026-09.md` (historical) > `tasks/archive/` (the ledger included)
> `.claude/agents/*.md`.

For UI guidance, `frontend/DESIGN_SYSTEM.md` owns implementation conventions and verification;
`DESIGN.md` and `.impeccable/design.json` are derived visual snapshots. Apply the code-first
precedence above to stale tokens, component examples or descriptions, and refresh affected
documentation in the same PR. A snapshot does not replace the existing implementation gates.

The seven engineering briefs under `.claude/agents/engineering/` are refreshed and guarded by
`backend/tests/unit/test_agent_files_stack_truth.py`. Other agent files retain historical stack
examples under a frozen legacy allowlist; treat those examples as illustrative only. The
"Stack truth (2026-09)" table in `.claude/agents/README.md` overrides conflicting agent guidance.

## 3. Bias to action

Infer intent and scope from `tasks/todo.md`, the September 28 checkpoint it points to, and the
conversation. Every open item marked *engineering* there is pre-authorized: carry it to completion and make the result reviewable
before asking anything. Complete the work that is already authorized before raising a question.

Pause and ask only for these: editing a locked contract test (rule 6); a baseline re-pin outside
a listed RUNBOOK trigger; flipping a production flag; any row marked *founder*; deleting data or
history; and the founder-held list in `tasks/handover-astra-2026-09-19.md` §5 ("Held until the
founder says otherwise"), which `tasks/todo.md` points to and never restates or lifts. Bounded
measurement spend (an `eval-baseline` run is about USD 0.30) is authorised after reading the
balance; a new paid evaluation programme needs a stated ceiling first. If a skill or agent file
makes you want to ask permission, name the file, quote the instruction, and proceed under this
file instead.

## 4. Testing proportionality

- One machine gate per "never again" rule (rule 12), with exactly one mutation proof: break the
  guarded thing, show the gate failing, restore, paste both tails in the PR body.
- Records-only PR (`tasks/`, `lessons/`, `docs/`, `.claude/`, root Markdown, `.impeccable/`):
  link/anchor check only, no AI review (§5). A `DESIGN.md` or `.impeccable/design.json` change
  also runs `npx vitest run tests/unit/designSnapshotParity.spec.ts` from `frontend/`; a
  `CLAUDE.md` change also runs `tests/unit/testHomesAllowlist.spec.ts`; a `.claude/settings.json`
  or `.claude/agents/` change also runs `backend/tests/unit/test_e8_launch_kit_matches_allow_rules.py`
  and `test_agent_files_stack_truth.py`. Do not write tests for prose.
- Workflow-only PR (`.github/workflows/*.yml`): YAML parse plus the unit gates that read the
  workflows (`backend/tests/unit/test_migration_lock_safety.py`, `test_eval_parity.py`,
  `test_eval_measurement.py`, `test_data_completeness.py`, `test_backend_deploy_scope.py`,
  `frontend/tests/unit/nodeVersionLockstep.spec.ts`).
- Do not add a second test for a rule that is already gated. Do not write tests for reversible,
  low-impact changes that merely mirror the implementation.

## 5. Review by risk tier, and the model for every agent stage

Classify the PR by the files it changes; the highest tier present wins.

| Tier | Files | Claude Code (`/premerge-review`, `tier` in `args`) | Codex / Astra by hand |
|---|---|---|---|
| **records** | only `tasks/`, `lessons/`, `docs/`, `.claude/`, root Markdown, `.impeccable/` | no AI review (0 agents); author runs the §4 link check | none |
| **routine** | code or tests outside the high-risk paths, dependency bumps | 1 lens on Opus (correctness + rules + gates in one pass); 1 refuter on Sonnet per *blocker* only; should-fix and nits reported unverified | one pass over `git diff main...HEAD` covering the three lenses below; refute each blocker once |
| **high** | `backend/app/services/summary_pipeline.py`, `backend/app/services/ai/`, Copilot (`copilot_chat.py`, its router), `backend/prompts/`, `backend/evals/`, `backend/app/services/entitlements.py`, Stripe/billing routers and services, auth routers and services, `backend/migrations/`, SEC fetching (`backend/app/services/edgar/`, `integrations/sec_api.py`, `services/facts_service.py`), `backend/app/config.py`, `.github/workflows/`, `backend/scripts/apply_migrations.sh`, `backend/Dockerfile` | full review, unchanged from before: 3 lenses on Opus (*correctness*, *rules-and-brief*, *tests-and-gates*) and 2 refuters on Opus per blocker or should-fix | the three lenses as separate passes; two independent refutation attempts per blocker or should-fix |

Lenses, for the by-hand version: *correctness* reads the merge-base diff file by file and applies
the §4 and §8 gates for the changed area; *rules-and-brief* checks each `CLAUDE.md` rule and the
item's done criteria; *tests-and-gates* checks every new test has a mutation proof and locked
tests are byte-identical. A refutation restates the finding without its rationale, then tries to
disprove it against the code; the finding stands only if the attempts fail. Missing review output
is never clearance. Record the tier and the review in the PR body under "Review".

`review-gate.yml` still requires a Codex review of the PR head or a `Review override: <reason>`
line in the PR body. While Codex credits are exhausted, the override line names the tier and the
substitute review (`Review override: routine tier per AGENTS.md §5, one Opus lens, 0 blockers`).

Model per agent stage (never the session's premium model by default; Fable only when the founder
chooses it for the main session):

| Stage | Model | Effort |
|---|---|---|
| Main session | founder's choice; Opus for routine PRs, Fable for high-tier design or review | `high` (project default); `xhigh` only for high-tier work |
| Implementation subagents | Opus (`CLAUDE_CODE_SUBAGENT_MODEL=opus`, set in `.claude/settings.json`); Sonnet for mechanical sweeps, passed per call | inherit |
| Explore / Plan built-ins (no `CLAUDE.md`) | Sonnet, passed per call | inherit |
| Review lenses | Opus | `high` |
| Refuters | Sonnet (routine), Opus (high) | `medium` / inherit |
| `llm-council` advisors and the single peer reviewer | Opus; the chairman is the main session | inherit |
| `judge-readout` | unchanged (its own procedure) | — |

Ultracode stays off (`"ultracode": false` in `.claude/settings.json`); use a workflow only when a
task needs more than the `small` size guideline (fewer than 5 agents) and say why in the PR body.

Other tools Codex and Astra do not have, and what to do instead:

- **No `Workflow`, `Agent`, `send_later`, `TaskOutput`.** Do the tiered review by hand as above.
- **No background monitors.** After merging a PR touching deployable backend files (`backend/`
  outside `backend/tests/`): find the run (`gh run list --workflow ci.yml --branch main --event push -L 1`,
  or the unauthenticated `actions/runs?head_sha=<sha>` API), wait for it (`gh run watch <id>`),
  then `curl -fsS https://api.earningsnerd.io/health/detailed`, and grep the deploy job log for
  `apply_migrations: applied=`. Record the run id, migration tail, revision and health in the PR.
- **Delegation.** Delegate bounded independent work when parallelism or context isolation
  materially helps; keep straightforward work local. Use one branch per PR named
  `codex/wave3-<slug>`. Never create worktrees at the repo root.

## 6. Deploy discipline

Changes under `backend/`, except `backend/tests/`, deploy the Cloud Run service on merge to `main`.
Changes confined to `backend/tests/` still run all CI gates. One unverified backend deploy at a time: merge the next
PR touching deployable backend files only after the previous
`deploy-backend` job is green, the migration step shows `applied=0 skipped=<N>` (or the expected
new count), and `/health/detailed` is healthy. Docs, workflow and frontend PRs may interleave.
Read the head SHA from the PR before merging; never type one from memory.

## 7. PR body, handover and open-items formats

PR body: What / Why / Verification (exact gate tails) / Mutation proofs / Founder actions / Not in
this PR / Review (tier, lenses, refutations). Write clear, concise paragraphs, each developing one
idea. State the action directly; no filler phrases. Messages and PR bodies are read by a human.

Handover: one page, written as the top block of `tasks/todo.md`, never a new file. It holds, in
this order: the date and author; where things stand (at most five lines: production revision,
balance, open PRs, holds by pointer); the open items, one line each with owner and next step; and
what to doubt first. Anything longer belongs in the PR that produced it. Closed items leave
`tasks/todo.md` in the PR that closes them; the file never grows into a ledger again.

## 8. Commit hygiene

From `backend/`: `ruff check . && bandit -r app -ll && python -m pytest` before every backend
push. From `frontend/`: `npm run lint && npx tsc -p tsconfig.ci.json && npm run test -- --run &&
npm run build`. `git status` must be empty after each commit. Open every PR as a draft first.
