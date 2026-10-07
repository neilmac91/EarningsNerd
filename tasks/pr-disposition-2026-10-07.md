# PR disposition sweep — 7 October 2026

Durable checkpoint for the founder-authorised disposition of every open pull request (12 at start:
#1111, #1110, #1108, #1107, #1102, #1097, #1096, #1095, #1081, #1074, #1035, #1009) and the
inventory of stale remote branches. Source instruction: the founder's live launch prompt of
2026-10-07 (the "PR disposition sweep" prompt). Structure and evidence standard follow
[`pr-disposition-2026-09-30.md`](pr-disposition-2026-09-30.md): checked means evidenced.

**Stage:** 0 (preflight) recorded; Stage 1 (read-only triage) in progress. Nothing in Stage 0 or
Stage 1 pushes, comments, labels, reviews or merges anything except this checkpoint.

## Session state

- Repository `neilmac91/EarningsNerd`; executor branch `claude/pr-disposition-sweep-64s71l` (the
  branch this session was assigned; it carries this file instead of `claude/pr-disposition-2026-10-07`).
- Main at start: `f26debcb43f8c49eeca34e76cef6bc0e394a920e` (#1109, CODE RED decision record 14),
  observed 2026-10-07T19:41Z.
- Access: the `gh` CLI token in this container is invalid (`gh auth status`: "The token in GH_TOKEN
  is invalid"). GitHub reads go through the GitHub MCP connector (PRs, checks, Actions runs,
  comments: readable). **Gap:** no tool in this session reads the Dependabot alerts API, so alerts
  are not listed from the API (see Stage 1).
- Local clone was shallow at start; unshallowed before computing ahead/behind and merge-tree results.
- Worktrees for Stage 2 (if approved): `/home/user/wt/<lane>`, outside the repository root.

### Open PRs at start (git facts, 2026-10-07T19:45Z)

| PR | Branch | Head | Draft | Ahead / behind main | Conflicts with main (merge-tree) | Diff vs merge base | Deploy class |
| --- | --- | --- | --- | --- | --- | --- | --- |
| #1111 | `codex/wave3-copilot-quotation-recovery` | `e2b4db62` | draft | 2 / 0 | none | 8 files +677 −41 | deployable backend (`backend/app` → eval-baseline) |
| #1110 | `claude/vigilant-goodall-633yx3` | `0eac3877` | draft | 22 / 0 | none | 3 files +574 | `backend/tests` + lessons (no deploy) |
| #1108 | `claude/implementation-launch-prompt-ofvuc1-en03` | `6f6d85bf` | draft | 6 / 2 | none | 18 files +1951 −80 | frontend + docs/tasks |
| #1107 | `claude/implementation-launch-prompt-ofvuc1` | `7d96c11e` | draft | 5 / 2 | none | 29 files +2199 −117 | frontend + CLAUDE.md, DESIGN.md, lessons, tasks |
| #1102 | `dependabot/npm_and_yarn/frontend/security-patches-2d036ed59c` | `24dc5957` | ready | 1 / 6 | none | lockfile only, +18 −9 | frontend |
| #1097 | `dependabot/npm_and_yarn/frontend/minor-updates-f1334c1047` | `b0438bdc` | ready | 1 / 11 | none | package.json + lockfile, +483 −407 | frontend |
| #1096 | `dependabot/pip/backend/minor-updates-3fd4bbb8da` | `a31f9094` | ready | 1 / 11 | none | 4 requirements files, +18 −13 | deployable backend (requirements only: eval-baseline skips) |
| #1095 | `dependabot/pip/backend/sqlalchemy-2.1.2` | `cf995353` | ready | 1 / 11 | none | requirements.in/.txt, +2 −2 | deployable backend (requirements only) |
| #1081 | `claude/zealous-albattani-6ti8cx` | `53cc2762` | ready | 3 / 23 | `frontend/DESIGN_SYSTEM.md` | 22 files +400 −22 | frontend + lessons |
| #1074 | `claude/copilot-prompt-candidate` | `437e245c` | draft | 10 / 37 | none | 32 files +4695 −2 | `backend/app` + tasks (measurement only) |
| #1035 | `codex/wave3-native-delivery-capability` | `23c948e9` | draft | 2 / 68 | none | 5 files +629 −56 | deployable backend (`backend/app`) |
| #1009 | `codex/wave3-launch-pricing-offer` | `be11df3a` | draft | 14 / 40 | `frontend/app/pricing/page.tsx`, `tasks/todo.md` | 13 files +405 −156 | frontend + docs/tasks |

Dependency versions (from the diffs):
- #1096: anthropic 1.9.0→1.11.0, edgartools 5.58.0→**5.59.1**, fastapi 0.141.1→0.142.2,
  openai 3.20.0→3.23.0, posthog 7.60.1→7.62.0, python-dotenv 1.2.3→1.2.4, ruff 0.16.9→0.16.10
  (dev), new transitive opentelemetry-api 1.45.0. edgartools 5.59.1 is the version the 09-30 run
  held back (decision D: two real Ford regressions, comment 5925866111; #1034 held on 5.58.0).
- #1095: sqlalchemy 2.0.54→2.1.2 (pin range `<2.1` → `<2.2`).
- #1097: @sentry/nextjs ^11.0.0→^11.2.0, @tanstack/react-query ^5.103.2→^5.104.0, next
  16.3.6→16.3.8, posthog-js ^1.434.14→^1.435.6, @types/node, eslint-config-next 16.3.8, sharp
  ^0.35.3→^0.35.5, vitest ^5.0.2→^5.0.3.
- #1102: compression 1.8.1→1.8.2, proxy-addr 2.0.7→2.0.8, source-map-js 1.2.1→1.2.2 (security group).

### Pairwise file overlaps and serial-merge chains (simulated sequential merges)

| Pair | Shared files | Sequential merge result |
| --- | --- | --- |
| #1095 × #1096 | `backend/requirements.in`, `requirements.txt` | conflict on `requirements.in` in either order → serial, rebase between |
| #1107 × #1108 | `DESIGN.md`, `frontend/DESIGN_SYSTEM.md`, `tasks/todo.md` | conflict on `tasks/todo.md` in either order |
| #1081 × #1107 / #1108 | `frontend/DESIGN_SYSTEM.md` | #1081 already conflicts with main there; also conflicts after either |
| #1009 × #1081 | `frontend/app/pricing/page.tsx`, `PricingSection.tsx` | #1009 and #1081 each conflict with main; not simulated further |
| #1009 × #1097 | `frontend/package.json` | after #1097, #1009 still conflicts only where it already does |
| #1097 × #1102 | `frontend/package-lock.json` | git-clean in either order; lockfile must be regenerated (`@dependabot rebase`) |
| #1074 × #1111 | `backend/app/services/copilot_service.py` | clean in either order |
| #1107 × #1110 | `lessons/README.md` | clean |
| #1009 / #1035 / #1107 / #1108 / #1111 | `tasks/todo.md` | clean pairwise except as listed |

## Spend ledger (ceiling: USD 3.00 for the whole run)

- Balance read (free `GET /user/balance`, session DeepSeek key, as the 09-30 run did):
  **USD 37.77 at 2026-10-07T19:42:12Z**. Floor for new paid dispatch: **USD 34.77**, and telemetry
  total ≤ USD 3.00. Other agents share the account, so run telemetry is the primary accounting and
  the balance is a cross-check.
- Paid triggers: `ci.yml` `eval-baseline` on every `pull_request` event touching
  `backend/app|evals|prompts` (drafts included; about USD 0.18–0.38 a run; requirements-only diffs
  skip it); `copilot-eval.yml` on ready same-repo PRs touching `backend/**` (about USD 0.01 a run).

| # | Dispatch | Reserved | Telemetry actual | Status |
| --- | --- | --- | --- | --- |
| — | none yet | — | — | — |

## Lanes

Filled at the end of Stage 1 (owner, disposition, approval needed, expected spend).

## Final report

Pending.

## Log

- 19:41Z — `gh auth status`: token invalid; switched to the GitHub MCP connector. Main `f26debcb`.
- 19:42Z — DeepSeek balance USD 37.77 (floor 34.77).
- 19:45Z — Clone unshallowed; ahead/behind, merge-tree and pairwise sequential-merge simulation
  recorded above. #1035 merges cleanly with main (68 behind); #1009 conflicts in the pricing page
  and `tasks/todo.md`; #1081 conflicts in `frontend/DESIGN_SYSTEM.md`.
- 19:50Z — Stage 0 GitHub-state readers launched (workflow `wf_55262a8d-5f7`: checks, Codex review
  state, comments, runs per PR; repo-wide Codex quota evidence).
