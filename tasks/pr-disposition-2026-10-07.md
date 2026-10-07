# PR disposition sweep — 7 October 2026

Durable checkpoint for the founder-authorised disposition of every open pull request (12 at start:
#1111, #1110, #1108, #1107, #1102, #1097, #1096, #1095, #1081, #1074, #1035, #1009) and the
inventory of stale remote branches. Source instruction: the founder's live launch prompt of
2026-10-07 (the "PR disposition sweep" prompt). Structure and evidence standard follow
[`pr-disposition-2026-09-30.md`](pr-disposition-2026-09-30.md): checked means evidenced.

**Stage:** 0 and 1 complete; Stage 2 (execution) in progress under the founder approval of 21:08Z. Nothing in Stage 0 or
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

### Open PRs at start (git facts, 2026-10-07T19:43Z)

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
| #1035 | `codex/wave3-native-delivery-capability` | `23c948e9` | draft | 2 / 68 | none | 5 files +629 −56 | deployable backend (`backend/evals`, `backend/scripts`, tests; eval-baseline runs) |
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

### GitHub state and owners at start (Stage 0 readers, `wf_55262a8d-5f7`, read 19:44–19:51Z)

| PR | Last push (first run for the head) | Checks on head | Codex on head | Hold / flags | Owner → rule |
| --- | --- | --- | --- | --- | --- |
| #1111 | 19:27:10Z (run 37674586346) | all green incl. eval-baseline, copilot-eval 37674643226 | review 5447320533 completed 19:30:46Z on `e2b4db6`, 1 unresolved P2 | body: "Deployment held"; new-head live artifacts required before merge | Codex lane, pushed < 1 h → **observe-only** |
| #1110 | 19:23:13Z (run 37674087146) | all green; draft skips | 9 Codex reviews on older heads (last `e0f0086` 10:30:18Z); none on `0eac387` | none; DECISIONS-14 "Other executable work" item 2 names it | CODE RED chief, pushed < 1 h → **observe-only** |
| #1108 | 18:17:28Z (run 37665686446) | CI green; review-gate 37676954482 in progress (marked ready 19:45:58Z by the owner account) | review running since 19:46:03Z on `6f6d85b` | none | product lane (EN-03), pushed < 12 h, marked ready during this read → **observe-only** |
| #1107 | 18:18:37Z (run 37665833559; commits dated 00:34Z, pushed later) | CI green; review-gate 37676929238 in progress (marked ready 19:45:46Z) | review running since 19:45:50Z on `7d96c11` | none | product lane (EN-02), pushed < 12 h, live sibling #1108 → **observe-only** |
| #1102 | 2026-10-06T06:24:24Z | CI green; review-gate failed (no Codex review; Dependabot PRs do not trigger Codex) | none | none | Dependabot, no live owner → actionable |
| #1097 | 2026-10-05T07:46:44Z | review-gate failed; **secret-scan failed** (see below) | none | none | Dependabot → actionable |
| #1096 | 2026-10-05T07:46:30Z | **backend-tests failed**; secret-scan failed; copilot-eval failed (no secrets on Dependabot runs); review-gate failed | none | none | Dependabot → actionable |
| #1095 | 2026-10-05T07:44:39Z | **migrations-postgres failed**; secret-scan failed; copilot-eval failed (no secrets); review-gate failed; backend-tests green (SQLite) | none | none | Dependabot → actionable (founder decision: framework upgrade) |
| #1081 | 2026-10-03T22:36:01Z | all green; review-gate 37186090832 passed via the body's `Review override:` (Codex quota messages 5977375613, 5977510418 on 10-04) | none | mergeable_state `dirty` | idle 93 h → actionable |
| #1074 | 2026-10-03T03:10:12Z | green except Q1 copilot-eval (by design of the measurement) | summary 5965023258 completed on `437e245` | title and body: "measurement only, do not merge"; owner comment 5965114706 "Measurement complete: Not qualified … Do not merge." | measurement only, idle → **never merges**; keep vs close |
| #1035 | 2026-09-30T21:54:08Z | green; draft skips | none | **hold record 5962533770** (owner, 2026-10-02T22:34Z): held draft at unchanged `23c948e9` | **held** |
| #1009 | 2026-10-02T22:43:28Z | green; draft skips | older heads only (last 2026-09-28 on `561dc2b`) | **hold record 5920001935** (2026-09-30) and 5962292909 (2026-10-02) | **held** (pricing) |

**Codex review quota: available.** The last quota message is 6027196631 (#1106, 2026-10-06T23:16:47Z).
Codex completed reviews after it on #1109 (summary 6032808809, 2026-10-07T07:07:50Z), #1110 (nine
reviews 08:08–10:30Z) and #1111 (review 5447320533, 19:30:46Z), and is running on #1107 and #1108.
So the founder's quota-exhausted override clause does not apply to this run. Dependabot-opened PRs do
not trigger Codex by themselves; an owner `@codex review` comment is needed (precedent #998, #1013).

**Dependabot CI failures, root-caused from the job logs:**
- #1095 `migrations-postgres` (job 111663839337): `create_engine` raises `ModuleNotFoundError: No module
  named 'psycopg'`. SQLAlchemy 2.1 maps a bare `postgresql://` URL to the psycopg (v3) driver; this
  repository ships only `psycopg2-binary==2.9.13`. `backend-tests` passed only because it runs on
  SQLite. As merged, the deploy would fail to connect to Cloud SQL. **Blocker as-is.**
- #1096 `backend-tests` (job 111664425766): 1 failed / 5710 passed —
  `test_outlook_source_coverage.py::test_original_ford_complete_outlook_reaches_primary_and_forward_recovery_without_displacement`,
  the edgartools 5.59.1 Ford regression the 09-30 run held back (decision D). **Blocker as-is.**
- #1095–#1097 `secret-scan` (2026-10-05 runs): gitleaks scans every branch in the checkout and hit the
  EN-01 branch's `keyfocus` false positive; main pinned it at `f8091c53` (2026-10-05T09:23Z, after these
  runs). A rebase onto main clears it (#1102's later run passed).
- `copilot-eval` and `review-gate` cannot pass on a Dependabot-triggered run (no secrets; no automatic
  Codex review). Structural, not defects.

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

## Lanes (Stage 1 triage, main `335ad94b` after #1111 merged at 20:01Z)

Reviews: three lenses plus two independent refuters per blocker or should-fix; a finding stands only
when both refuters fail. Full outputs are retained outside git (session scratchpad `stage1/`).

| PR | Owner / lane | Behind · conflicts · CI · Codex | Confirmed findings | Proposed disposition | Paid spend |
| --- | --- | --- | --- | --- | --- |
| #1111 | Codex lane | **merged by its owner at 20:01:35Z** (`335ad94b`, head `5d9b0b25`); main CI 37678914838 success; `/health/detailed` healthy 20:34Z | at the reviewed `e2b4db62`, still true on main: (1) the runner's aggregate trace mixes both generations, so the RUNBOOK's F-attribution triage replay reports recovered rows UNEXPLAINED (`copilot_runner.py:242/259`, RUNBOOK:875); (2) decision F's withheld path now regenerates privately with no recorded decision superseding F / decision 2 | out of scope (merged); follow-ups | — |
| #1110 | CODE RED chief | 1 · none · green · Codex on older heads only | no blocker. Should-fix: lesson credits PR #1028 (constants came from #940); upload-area check skips `dispatch/` and root files; PR body describes `e0f00861`, no mutation proof for the last seven commits | observe-only | — |
| #1108 | product lane (EN-03) | 3 · none · green · Codex 5447544265 on `6f6d85b`; owner pushed again (`484a357a`) | no blocker. Should-fix: focus falls to `<body>` when the viewport crosses 768px while a chip-opened sheet is open (`FinancialMetricsTable.tsx:267`) | observe-only | — |
| #1107 | product lane (EN-02) | 3 · none · green · Codex running since 19:45:50Z | no blocker. Should-fix: sticky clause misses a split-literal z (`bottomChromeLadder.spec.ts:498`); DESIGN.md still claims revision `1a79637e`; the fixed-bottom-chrome rule has no gate. Preview in both themes not done | observe-only | — |
| #1102 | Dependabot (security) | 7 · none · green except review-gate (no Codex on Dependabot PRs) | none. Lock-only; 3 nodes changed, integrity = registry; compression and proxy-addr dev-only via `@lhci/cli`, source-map-js build-only; `npm audit` 23 → 20 (critical 1 → 0) | merge (`@codex review` first) | 0 |
| #1097 | Dependabot (minor) | 12 · none · secret-scan red (10-05 false positive, cleared on main), review-gate | none. Nits: Sentry 11.2 enables server Dedupe; posthog-js 1.435.6 starts recording the `oppref` ad-click id; Sentry source-map upload only exercised on Vercel. next 16.3.8 fixes GHSA-cjq9-62q9-8jv4 (SSRF; `images.remotePatterns` is configured) | after #1102: `@dependabot rebase`, re-gate, `@codex review`, merge | 0 |
| #1096 | Dependabot (pip minor) | 12 · none · **backend-tests red** | **blocker:** edgartools 5.59.1 reverses decision D / issue #1063 and fails the Ford outlook test; no upstream fix through 5.61.1 | maintainer replacement without edgartools; E1 validation; close #1096 as superseded | ≈0.20–0.40 |
| #1095 | Dependabot (sqlalchemy) | 12 · none · **migrations-postgres red** | **blockers:** SQLAlchemy 2.1 resolves a bare `postgresql://` URL to psycopg 3, which is not installed (`database.py:32`; the deploy would fail to connect); the PR lifts the deliberate `<2.1` cap set by #1010. Should-fix if adopted: psycopg 3 errors carry no `pgcode` (`subscription_webhook_service.py:137`); every bare-URL engine site must be covered | founder decision; recommend keep 2.0 and close | 0 |
| #1081 | Claude session, idle 93 h | 24 · `frontend/DESIGN_SYSTEM.md` · green on old head · no Codex (quota messages 10-04; body carries a 10-04 override) | no blocker. Should-fix: the grid rule lets a conditional branch borrow a sibling's base track (`eslint.gridBaseTrack.mjs:167`); the DESIGN_SYSTEM.md conflict (keep both paragraphs). The rule reports 0 errors on main + #1081 | integrate main, fix the gate gap with spec cases and one mutation proof, `@codex review`, merge | 0 |
| #1074 | measurement only | 38 · none · — | "Not qualified … Do not merge" (5965114706); Codex decided "Keep #1074 as the retained draft" (#1029 comment 5966195498); its 30 evidence files exist only on the branch; eval-baseline artifact 11262711816 expires 2026-10-17T03:20Z | keep (never merges) | 0 |
| #1035 | Codex lane, held | 69 · none · green (old) | hold record 5962533770 is factually stale: base moved 29 → 69 behind and #1084 changed the adapter and pinned owners it relies on | hold; refresh the hold record | 0 |
| #1009 | founder pricing hold | 41 · `pricing/page.tsx`, `tasks/todo.md` · green (old) | hold record 5920001935 is factually stale: it now conflicts in `pricing/page.tsx` as well; `check:pricing` exists; prerequisites unchanged | hold; refresh the hold record | 0 |

Merging integrated #1081 creates no conflict in #1107 (`7d96c11e`) or #1108 (`484a357a`) (worktree
simulation, main + #1081 with both DESIGN_SYSTEM.md paragraphs kept).

### Proposed merge train

1. #1102: frontend lock-only security patch; lowest risk; must precede #1097 (shared lockfile).
2. #1097: after `@dependabot rebase` onto the post-#1102 main; frontend; carries the next SSRF fix.
3. #1081: frontend; independent of 1–2; may interleave with the backend lane.
4. #1096 replacement: the only deployable backend merge; starts only after #1111's deploy is
   confirmed (deploy job green, migration tail, revision at 100%, health), then serial deploy
   verification of its own.
5. #1112 (this checkpoint): tasks-only, last.

### Stale-branch inventory (18 branches heading no open PR)

0 safe to delete, 4 keep, 14 ask. Keep: `claude/earnings-nerd-audit-plan-8iikp3`,
`claude/earningsnerd-sections-review-prompt-aw2u7c` (both D8, held), `codex/wave3-h25-capacity-probe`
(6 unique commits, no PR, cited by full SHA), `codex/wave3-thinking-low-pilot` (3 unique commits,
cited). Every other branch's head survives in `refs/pull/<n>/head` of a closed PR, but each is cited
by tasks/ evidence or its closing comment reserves the branch; none deleted without founder approval
by name.

### Dependabot alerts

Not readable (no alerts tool in this session). Inferred from the security group and lockfile audit:
#1102 closes compression (GHSA-vc2v-76pw-4v95, high), proxy-addr (GHSA-jqcg-44mw-7w3h, critical) and
source-map-js (GHSA-68fv-2mgg-jv7q, high); #1097 closes next GHSA-cjq9-62q9-8jv4 and the sharp
advisory; extract-zip #270 / #283 stay held (decision I).

## Final report

Pending.

## Log

- 19:41Z — `gh auth status`: token invalid; switched to the GitHub MCP connector. Main `f26debcb`.
- 19:42Z — DeepSeek balance USD 37.77 (floor 34.77).
- 19:43Z — Clone unshallowed; ahead/behind, merge-tree and pairwise sequential-merge simulation
  recorded above. #1035 merges cleanly with main (68 behind); #1009 conflicts in the pricing page
  and `tasks/todo.md`; #1081 conflicts in `frontend/DESIGN_SYSTEM.md`.
- 19:44Z — Stage 0 GitHub-state readers launched (workflow `wf_55262a8d-5f7`: checks, Codex review
  state, comments, runs per PR; repo-wide Codex quota evidence).
- 19:47Z — Checkpoint draft PR #1112 opened (tasks-only).
- 19:49–19:51Z — Stage 1 read-only workflows launched: three-lens reviews with two refuters per serious
  finding for #1081 (`wf_8f9a268e-3c0`), #1111 (`wf_223ecb9a-cf4`), #1110 (`wf_9e220d7e-580`), #1107
  (`wf_be4079c4-111`), #1108 (`wf_93a7f868-83c`); dependency analysis for #1102, #1097, #1096, #1095
  (`wf_46d39ae7-80a`); holds, #1074 and the branch inventory (`wf_697de371-944`).
- 19:51Z — Stage 0 readers complete (13/13). Codex quota available (see above). #1107 and #1108 were
  marked ready by the owner account at 19:45:46Z and 19:45:58Z, during this read.
- 19:52Z — Dependabot failure logs read: #1095 psycopg driver default (blocker), #1096 Ford regression
  (blocker), 10-05 secret-scan false positive (cleared on main).
- 20:01Z — #1111 merged by its owner (`335ad94b`) while its read-only review was running; main CI
  37678914838 success 20:13Z; `/health/detailed` healthy at 20:34:56Z (independent read).
- 20:07–20:40Z — Stage 1 workflows complete: holds/#1074/branches (`wf_697de371-944`), #1081, #1108,
  #1107, #1110, #1111 reviews, dependency analysis (`wf_46d39ae7-80a`). Recheck against `335ad94b`:
  no new conflicts; #1108 moved to `484a357a`.
- 20:50–20:57Z — Integrated-#1081 simulation (worktree outside the repo, removed): no conflict with #1107 or
  #1108. Stage 1 report sent to the founder; waiting for approval by number. Spend so far: USD 0.
- ~21:08Z — **Founder approval** (live session): "i authorise you to take action to progress as per
  the above plan. for any items pending my input, please analyse and determine the best path forward
  and proceed based on your recommendation." Recommendations adopted for the open choices:
  C1–C3 as planned; C4 replacement **with** edgartools moved out of the pip minor group (exclude, not
  ignore: each new edgartools release then gets its own PR that the Ford test gates); C5 keep
  SQLAlchemy 2.0, close #1095, Dependabot `ignore` for sqlalchemy semver-minor (2.0.x patches still
  flow), landed in the C4 replacement; C6 keep #1074 untouched (artifact 11262711816 preservation is a
  founder action before 2026-10-17T03:20Z); C7 refresh both hold records; C8 delete no branch; C9
  #1111 follow-ups queued, not implemented in this run (Codex lane, post-merge); C10 this run's USD
  3.00 treated as separately authorised, every paid run recorded here.
- 21:04Z (observed) — the owner account commented `@codex review` on #1102 (6046805313); Codex
  completed "Didn't find any major issues" on `24dc5957` (6046830986, 21:04:52Z).
- 21:09Z — New PR #1113 (`claude/implementation-launch-prompt-ofvuc1-en01-focus`, product lane,
  draft, opened 20:46Z): observe-only. Node 22.23.2 / npm 10.9.8 installed (SHA256 verified) for
  CI-parity gates. Worktrees: `/home/user/wt/pr1102` (local main + #1102 gate, never pushed),
  `/home/user/wt/pr1081`, `/home/user/wt/pr1096r`.
- 21:15Z — Lane workflow `wf_3832f533-85e` (implement → three-lens review → refuters → one fix round →
  delta re-review; local commits only) started for #1081 and the #1096 replacement.
