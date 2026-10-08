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
| #1107 | 18:18:37Z (run 37665833559; commits dated 00:34Z, pushed later) | CI green; review-gate 37676929238 in progress (marked ready 19:45:44Z) | review running since 19:45:50Z on `7d96c11` | none | product lane (EN-02), pushed < 12 h, live sibling #1108 → **observe-only** |
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
| D1 | #1119 (replaces #1096) `eval-baseline` by workflow dispatch on `claude/pr1096-deps-without-edgartools` at `76d2ba6d`, run [37695333206](https://github.com/neilmac91/EarningsNerd/actions/runs/37695333206), 22:18:33Z (off-peak; balance 37.57 at 22:18:07Z) | 0.40 | **0.175148** (70 calls, 0 unknown; off-peak tokens × `llm_pricing`) | done: expected=attempted=scored=70, errors 0, pass_rate 1.0, gate_fail_rate 0.0; regression gate PASS (2 warnings: untraceable dollar figures 1.614 advisory; `mean_citation_fidelity` 0.8615 vs pinned 0.9648, checked below); artifact 11515377659 sha256 `ff36d3a2…` |
| D2 | #1119 ready transition 22:18:41Z → `copilot-eval` run [37695352886](https://github.com/neilmac91/EarningsNerd/actions/runs/37695352886) at `76d2ba6d` (one run, E1 precedent) | 0.05 | **0.006611** (35 calls, 0 unknown, 0 peak) | done: **accepted, 18/18, 0 errors**; fingerprint `aeb56401`; artifact 11515695532 sha256 `e6af7057…` |
| D3 | #1127 (replaces Dependabot #1124: openai 3.24.0, posthog 7.62.1) `eval-baseline` by workflow dispatch on `claude/pr1124-backend-minor-updates` at `4fbec187`, run [37704631398](https://github.com/neilmac91/EarningsNerd/actions/runs/37704631398), 23:51:46Z (off-peak; balance 36.83 at 23:51:42Z) | 0.40 | **0.175076** (70 calls, 0 unknown; off-peak tokens × `llm_pricing`) | done: expected=attempted=scored=70, errors 0, pass_rate 1.0, gate_fail_rate 0.0; regression gate PASS (2 warnings: untraceable dollar figures 1.4 advisory; `mean_citation_fidelity` 0.8514 vs pinned 0.9648, the same harness fallback as D1); artifact 11519073370 sha256 `e3378f1f…` |
| D4 | #1127 ready transition 23:52:01Z → `copilot-eval` run [37704656898](https://github.com/neilmac91/EarningsNerd/actions/runs/37704656898) at `4fbec187` (one run, E1 precedent) | 0.05 | **0.006423** (34 calls, 0 unknown, 0 peak) | done: **accepted, 18/18, 0 errors**; artifact 11518798415 sha256 `60495688…` |
| | **Total** | | **0.363258** of 3.00 | |

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

## Final report (2026-10-08)

**Count.**
- **Open at the start:** 12 PRs. 7 of them reached a final state during the run: merged, replaced
  and closed, or closed. #1074 closes once this PR lands its evidence on main. That leaves 4 open on
  purpose: #1009 and #1035 are held, and #1108 and #1110 belong to live lanes.
- **Opened during the run:** 16 PRs. One is this checkpoint, #1112 (19:47Z). The other 15 are
  #1113–#1127: 3 by this session (#1116, #1119, #1127), 4 by Dependabot (#1114, #1115, #1124, #1125)
  and 8 by live lanes. Each has a state in the second table.
- **Open at the end:** 12 at 00:16Z, just before this PR merged. They are #1009, #1035, #1074, #1108,
  #1110, #1112, #1113, #1118, #1120, #1121, #1123 and #1126. Merging this PR and closing #1074 brings
  the count to **10**:
  - 2 held: #1009 and #1035;
  - 8 owned by live lanes: #1108, #1110, #1113, #1118, #1120, #1121, #1123 and #1126.

  28 PRs passed through the run: 12 open at the start and 16 opened during it. The sweep merged 7:
  #1102, #1081, #1116, #1119, #1125, #1127 and this PR. It closed 5 without merging: #1095, #1097,
  #1096 and #1124, plus #1074 right after this PR. Owner lanes merged 4 (#1111, #1107, #1117 and
  #1122), and Dependabot closed 2 of its own (#1114 and #1115).

### Open at start

| PR | Disposition | Outcome | Evidence |
| --- | --- | --- | --- |
| #1111 | observe-only (Codex lane, pushed < 1 h) | **merged by its owner** `335ad94b` (20:01Z) | deploy job 112992821258: `applied=0 skipped=41`, `00445-g7m` 100%, health verified; independent `/health/detailed` healthy 20:34:56Z; follow-ups below |
| #1110 | observe-only (CODE RED chief) | **open**, owner lane | Stage 1 should-fix findings recorded in the Lanes table; no confirmed blocker, so no comment |
| #1108 | observe-only (product lane EN-03) | **open**, owner lane | one should-fix (focus after crossing 768px with a chip-opened sheet open); no comment |
| #1107 | observe-only (product lane EN-02) | **merged by its owner** `aa17bcb8` (21:17Z) | Stage 1 should-fix findings are follow-ups |
| #1102 | merge | **merged** `fa7bf415` | Codex review completed with no findings; local gate on main+PR; Vercel production success; `www` 200; comment 6047011816 |
| #1097 | maintainer replacement | **#1116 merged** `b96457d1`; #1097 **closed** | cherry-pick with identical patch-id; local gate 1129/1129; Codex no findings; comment 6047344689 |
| #1096 | maintainer replacement without edgartools 5.59.1 | **#1119 merged** `111e8ce4`, deployed; #1096 **closed** | D1 70/70 PASS; D2 18/18; three-lens exact-head review clean; deploy job 113066259541 (first Buildx deploy): `applied=0 skipped=41`, `00446-vhw` 100%, healthy; release comment 6048886899; comment 6048731593 |
| #1095 | founder decision → keep SQLAlchemy 2.0 | **closed** | comment 6046972898; the Dependabot `ignore` for sqlalchemy semver-minor landed in #1119 |
| #1081 | integrate main, fix the gate gap, review, merge | **merged** `4e8252be` | two review rounds; four Codex rounds (three P2s fixed, two fail-closed P2s answered); the final rule reports exactly the 20 fixed sites on main; Vercel production success 23:56:08Z; `www` and `/pricing` 200; comment 6049249453 |
| #1074 | measurement only, never merges | **closed, never merged**, right after this PR merges | its 30 evidence files land on main with this PR (`tasks/review-evidence/prompt-candidate-2026-10-02/`), and the closing comment points there. The closure is verified in the founder message, not in this file, because this file merges first |
| #1035 | hold | **held draft** | hold record refreshed: comment 6046968560 |
| #1009 | hold (pricing) | **held draft** | hold record refreshed: comment 6046965161 |

### Opened during the run

| PR | Owner / lane | Outcome |
| --- | --- | --- |
| #1112 | this checkpoint | merged as the run's last step after a Codex review of its exact head. The merge SHA is in the founder message |
| #1113 | product lane (EN-01 follow-up) | **open**, observe-only. One should-fix: no test pins the `setTimeout(0)` reset of the in-panel click marker (`FilingWorkspace.tsx:220`) |
| #1114, #1115 | Dependabot (sharp security group; next 16.4.0) | closed 21:38–21:39Z after #1116 merged; not closed by this session |
| #1116 | this session (replaces #1097) | **merged** `b96457d1` |
| #1117 | Codex lane (CI, Buildx build cache) | **merged by its owner** `d4c977f5` |
| #1118, #1120, #1121, #1123, #1126 | live Claude and Codex lanes, drafts | **open**, observe-only |
| #1119 | this session (replaces #1096) | **merged** `111e8ce4`, deployed and verified |
| #1122 | Codex lane (durable background tasks) | **merged by its owner** `6393518c` at 23:19Z; deploy job 113068536115 succeeded (`00447-hlv` 100%, healthy) |
| #1124 | Dependabot pip (openai 3.24.0, posthog 7.62.1) | **closed** as superseded by #1127 (comment 6049316739) |
| #1125 | Dependabot frontend (4 updates) | **merged** `0a5eeccc`: Codex no findings; local gate; independent review clean; Vercel production success; comment 6049203118 |
| #1127 | this session (replaces #1124) | **merged** `41248d01`, deployed and verified. Deploy job 113080756294: `applied=0 skipped=41`; `00448-qk7` at 100% from 00:10:40Z; in-job health healthy at 00:11:20Z; independent `/health/detailed` 200 healthy at 00:12:01Z. Release comment 6049437703 |

### Spend

Four paid runs, all off-peak and all deepseek-flash, with 0 unknown-cost calls. Telemetry total
**USD 0.363258** against the USD 3.00 ceiling (D1 0.175148, D2 0.006611, D3 0.175076, D4 0.006423). The DeepSeek
balance went from USD 37.77 at 19:42Z to 36.83 at 23:51Z. Other agents share the account, so the
balance is a cross-check, not the accounting.

### Boundaries kept

- No force-push or history rewrite. No push to main or to any `dependabot/*` branch; Dependabot
  changes went through maintainer replacements or Dependabot's own PR.
- Untouched: locked contract tests, baseline pins and thresholds, production flags, prices, trial,
  promo, registration, Stripe, the AI provider and model, secrets, repository settings and rulesets,
  and `tasks/code-red-20261004/`. The nearest any merge came: #1081 added a base `grid-cols-1` to one
  class string each in `app/pricing/page.tsx`, `PricingSection.tsx`, `AuthShell.tsx` and
  `admin/invites/page.tsx`. That is layout only, with no change to price, plan or registration
  logic. #1009, the pricing hold, already conflicted in `pricing/page.tsx`.
- Held items stay held: #1009, #1035, Dependabot alert #270 and D8 (its two branches kept). No PR
  marked "do not merge" or "measurement only" was merged.
- No branch was deleted by hand, and none of the 18 stale-inventory branches was touched.
  **Correction (Stage 3):** this line first read "No branch was deleted", which was wrong. The
  repository has `delete_branch_on_merge: true`, so GitHub removed the head branch of every PR merged
  in the run. That covers the sweep's merges (#1102, #1116, #1119, #1125, #1081 and #1127) and the
  owner-lane merges (#1111, #1107, #1117 and #1122). Dependabot deleted its own branches when
  #1095, #1096, #1097 and #1124 closed. Every one of those heads is kept in `refs/pull/<n>/head`, and
  the merged ones are also on main as squash commits. Merging this PR removes
  `claude/pr-disposition-sweep-64s71l` the same way. Repository settings are out of scope, so the
  setting was left alone.
- Every merge waited for: green checks, including Vercel; a completed Codex review of the exact head
  (no override was used, since quota was available); no standing blocker or should-fix; and a
  re-read head SHA with squash + `expectedHeadSha`. One case needs saying: #1081 merged with two Codex
  P2s on its exact head. Both were reproduced and both are fail-closed false positives on shapes that
  do not exist in the tree. They were answered, resolved and put to the founder as decision 5. Backend merges were serial, each confirmed by its
  deploy job, migration tail, revision at 100% and `/health/detailed`.
- Refused or missing access was logged and not routed around:
  - the `gh` token is invalid;
  - Dependabot alerts are unreadable;
  - the connector defangs bot @-mentions. This was seen for `@dependabot` (comment 6046998252);
    `@codex` was not tried and is assumed to behave the same.
- Observe-only PRs got no push, merge, close or comment from this session.

### Decisions needed from the founder

1. **#1074's eval-baseline artifact 11262711816 expires 2026-10-17T03:20Z.** Its private copy is
   still unconfirmed. The three copilot-fidelity artifacts expire 2027-01-01.
2. **#1074 closure (a change from C6, "keep").** Its pre-registration, tools and review history now
   live on main (landed by this PR), and the results stay in the #1029 and #1074 comments. So the
   retained draft no longer protected anything. Reopen it if you want the draft kept.
3. **Eval harness section-extraction fallback.** Every 7 October eval-baseline run fell back to regex
   section extraction for 35/35 filings, against edgartools for 31/35 on 2–4 October. That drives
   `mean_citation_fidelity` to 0.818–0.871 (8 runs) against the pinned 0.9648, a gate warning on every run.
   `backend/evals/runner.py::_get_grounding` swallows the exception (`except Exception: sections =
   None`), so the cause is silent. The same call path is used in production. Worth a diagnosis PR.
4. **Branch deletion (approval by name).** The merged sweep branches need no decision: GitHub's
   delete-on-merge setting already removed them (see Boundaries kept), and it removes this PR's branch
   when it merges. Stage 1's 14 "ask" branches are still there. Each is cited in tasks/ evidence or
   reserved by a closing comment:
   - `claude/earnings-nerd-bundle-reconstruct-j65fj5`
   - `claude/g-stage1-arm-c`
   - `claude/g-stage2-arm-b`
   - `claude/practical-gauss-tdet7t`
   - `claude/stoic-albattani-wulur7`
   - `codex/measure-attribution-verify`
   - `codex/measure-n-control-2`
   - `codex/wave3-capacity-measurement`
   - `codex/wave3-copilot-typed-evidence`
   - `codex/wave3-e8-n-pilot`
   - `codex/wave3-return-ratio-basis`
   - `codex/wave3-segment-margin-basis`
   - `codex/wave3-supported-financial-explanations`
   - `codex/wave3-verify-ranking-measure`
5. **#1081's grid gate: build an interval-aware evaluator?** It would remove the two fail-closed
   false positives Codex found: arbitrary `min-[…]` screens, and a reset that applies only while the
   element is hidden. Neither shape is in the tree today.
6. **Frontend `npm audit` on main**, unchanged by this run's merges: 19 findings (2 moderate, 17
   high); production-only, 7 (2 moderate, 5 high). This session cannot read Dependabot alerts, so
   they are not triaged here. The only alert signal it can see is GitHub's push banner: 4 open on
   main (3 high, 1 moderate) at 00:17Z. One of them is likely the held extract-zip #270.
7. **Holds.** #1009 (pricing) and #1035 (native delivery) keep their prerequisites, as listed in the
   refreshed hold records.

### Queued follow-ups (not done)

- **#1111 (Codex lane).**
  - The runner's aggregate trace mixes both generations, so the RUNBOOK's F-attribution triage
    replay reports recovered rows as UNEXPLAINED (`copilot_runner.py:242/259`, RUNBOOK:875).
  - Decision F's withheld path now regenerates privately, but no recorded decision supersedes F or
    decision 2.
- **#1107, #1108, #1110, #1113:** the Stage 1 should-fix findings above, for their owner lanes.
- **CI:** `eval-baseline` skips requirements-only diffs, such as an openai bump, on pull_request
  events. This run used workflow dispatch instead (D1, D3). A path-filter change would make it
  automatic.
- **Process gap:** this session's GitHub connector defangs bot @-mentions. This was seen for
  `@dependabot` and assumed for `@codex`, so Codex reviews were triggered by draft→ready cycles.

### Stage 3 (independent verification)

Stage 3 ran as workflow `wf_a62e9e1a-2e7` from 00:04 to 00:21Z: three fresh read-only agents, none
of which had seen the run. Each checked the record against primary sources (the REST API, PR
timelines, job logs, git objects and live `/health/detailed`). They made 243 checks in total.

| Lens | Checks | Confirmed | Discrepancies (all fixed in this file unless noted) |
| --- | --- | --- | --- |
| PR outcomes and comments | 108 | Every merge SHA and time; every closure; every head SHA; all cited comment IDs; #1081's 5 Codex threads all answered and resolved; holds unchanged; no sweep comment on any observe-only PR; 12 open at start, 15 + this PR opened | **wrong:** "8 of 12" (it is 7, with #1074 pending); "no branch was deleted"; decision 4 named four branches already gone; two closing comments said a branch stayed (now edited in place). **imprecise:** #1074's evidence was written as already on main; the #1112 count; #1108's head at 20:40Z; six timestamps off by 2–5 s |
| Deploys, health and spend | 58 | All four deploys (`00445`–`00448`, `applied=0 skipped=41`, healthy); the spend recomputed from every `ai_call` line comes to exactly USD 0.363258; all runs off-peak and deepseek-flash; artifact IDs and sha256 prefixes; no other paid steps on session branches | **imprecise:** decision 3's range (now 0.818–0.871 across 8 runs); #1122's merge happened before #1119's deploy started, not during it; #1119's release comment blamed the push-run skip on the path filter (edited in place: it is the job-level `if`). **unverifiable:** the session's own health reads and DeepSeek balance reads (the record already treats balance as a cross-check) |
| Boundaries | 77 | The six merges touch no locked file, workflow, `backend/app`, prompt, eval or code-red path; no secrets; extract-zip unchanged; this branch touches only `tasks/`; the 30 #1074 files are byte-identical to `437e245c`; all 18 inventoried branches present; no force-push; every squash tree equals the merge-tree of its cited head; Codex completed on every exact merged head | **imprecise:** branch auto-delete also covered the four owner-lane merges; #1081's layout edits to the pricing and auth files; `@codex` defanging is assumed, not observed; #1081 merged with two answered Codex P2s; the README's fidelity range. **unverifiable:** that `expectedHeadSha` was passed (GitHub does not record it; every merged head matches the head re-read before merging), and alert #270 (alerts API 403) |

None of the lenses found a boundary breach or a wrong merge.

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
  marked ready by the owner account at 19:45:44Z and 19:45:56Z, during this read.
- 19:52Z — Dependabot failure logs read: #1095 psycopg driver default (blocker), #1096 Ford regression
  (blocker), 10-05 secret-scan false positive (cleared on main).
- 20:01Z — #1111 merged by its owner (`335ad94b`) while its read-only review was running; main CI
  37678914838 success 20:13Z; `/health/detailed` healthy at 20:34:56Z (independent read).
- 20:07–20:40Z — Stage 1 workflows complete: holds/#1074/branches (`wf_697de371-944`), #1081, #1108,
  #1107, #1110, #1111 reviews, dependency analysis (`wf_46d39ae7-80a`). Recheck against `335ad94b`:
  no new conflicts; #1108 moved to `54856d48` (it moved again to `484a357a` at about 20:56Z, and is now
  at `72b2d6c3`).
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
- 21:09–21:11Z — New PR #1113 (`claude/implementation-launch-prompt-ofvuc1-en01-focus`, product lane,
  draft, opened 20:46Z): observe-only. Node 22.23.2 / npm 10.9.8 installed (SHA256 verified) for
  CI-parity gates. Worktrees: `/home/user/wt/pr1102` (local main + #1102 gate, never pushed),
  `/home/user/wt/pr1081`, `/home/user/wt/pr1096r`.
- 21:11Z — Lane workflow `wf_3832f533-85e` (implement → three-lens review → refuters → one fix round →
  delta re-review; local commits only) started for #1081 and the #1096 replacement.
- 21:11–21:12Z — #1111's deploy confirmed before any backend merge of this run: deploy job
  112992821258 success, `apply_migrations: applied=0 skipped=41`, revision
  `earningsnerd-backend-00445-g7m` serving 100%, "Verify health" step green; independent
  `/health/detailed` healthy at 20:34:56Z.
- 21:12–21:13Z — Hold records refreshed (facts changed): #1009 comment 6046965161, #1035 comment
  6046968560. #1095 closed with evidence comment 6046972898 (keep SQLAlchemy 2.0). #1074 kept
  unchanged (no comment; its 10-03 records are current).
- 21:14Z — #1102 local gate on main `335ad94b` + `24dc5957` (worktree `/home/user/wt/pr1102`, Node
  22.23.2, npm 10.9.8): npm ci ok, lint 0, tsc 0, vitest 1106/1106, build 0. The 10-06 review-gate
  failure (no Codex review then) re-run via the Actions API after Codex's completed review of `24dc595`.
- 21:14Z — Read-only review of new observe-only #1113 started (`wf_9431c59e-422`). #1113 shares
  `frontend/DESIGN_SYSTEM.md` with #1081: simulate before #1081 merges.
- 21:15:08Z — **#1102 merged** `fa7bf415` (head `24dc5957` re-read, `expectedHeadSha` pinned). Vercel
  production status success 21:15:47Z; `www.earningsnerd.io` 200; evidence comment 6047011816.
- 21:15Z — **Access gap:** the GitHub connector defangs bot mentions in comments it posts
  (`@dependabot rebase` arrived on #1097 as "·@·d·ependabot r·ebase", comment 6046998252, with an
  appended footer). This session therefore cannot issue `@dependabot` or `@codex` commands; not routed
  around. Consequences: #1097 goes by maintainer replacement (cherry-pick of Dependabot's commit onto
  current main; nothing pushed to the Dependabot branch); Codex reviews are triggered by a draft→ready
  transition, which Codex reviews automatically.
- 21:17:36Z — #1107 merged by its owner (`aa17bcb8`, frontend). Observe-only in this run; its Stage 1
  should-fix findings move to follow-ups. #1108 now conflicts with main in `tasks/todo.md` (its owner's
  lane); #1081's lane must re-integrate main and re-lint #1107's new files before pushing.
- 21:22Z — #1097 replacement branch `claude/pr1097-frontend-minor-updates` = main `aa17bcb8` +
  cherry-pick `-x` of `b0438bdc` (clean; package.json shows exactly the 8 reviewed versions); gate running.
- 21:27:20Z — #1097 replacement **#1116** opened (draft) at `52cf7a23` (main `aa17bcb8` + cherry-pick of
  `b0438bdc`, identical patch-id `68e807d1…`). Local gate: npm ci ok, lint 0, tsc 0, vitest 1129/1129,
  build 0 (Next.js 16.3.8); lockfile regeneration drift is the class main already has (63 lines on
  main; 111 here from sharp's extra platform packages). Marked ready 21:27:28Z (frontend only: no paid
  job); Codex review triggered by the ready transition, completed 21:32:21Z with no findings.
- 21:30Z — #1113 read-only review (`wf_9431c59e-422`): no blocker; one should-fix confirmed (no test
  pins the in-panel click marker's `setTimeout(0)` reset, `FilingWorkspace.tsx:220`); 4 nits.
  Observe-only: reported, not commented.
- 21:37Z — **#1116 merged** `b96457d1` (head `52cf7a23` re-read; CI 37689522607 green; review-gate
  37689536809 pass). #1097 closed as superseded (comment 6047344689).
- 22:13:46Z (observed) — #1117 (`codex/wave3-backend-build-cache`, ci only) merged by its owner:
  the deploy job now builds with Buildx and a GHA cache. No deploy ran (workflow-only change), so the
  #1119 merge is the first backend deploy on the new build path. #1114 and #1115 (Dependabot sharp
  and next 16.4.0) opened and closed during the run (not by this session). #1118 (new draft,
  `claude/agent-workflow-cost`, 22:10Z): observe-only. #1110 was marked ready by the chief at 22:17:44Z.
- 22:18Z — #1096 replacement pushed (`76d2ba6d`; lane workflow round 1 confirmed one should-fix, a
  README overstatement of the sqlalchemy ignore's reach, fixed in `76d2ba6d`; round 2 running) and
  opened as **#1119**; D1 dispatched (the Actions dispatch API worked this run); marked ready 22:19Z
  (D2 + Codex review). Balance USD 37.57 at 22:18:07Z.
- 22:17Z — Lane workflow `wf_3832f533-85e` stopped by an operator interrupt during its round-2 delta
  reviews (#1081 `4cba0bf9`, #1096r `76d2ba6d`); no round-2 result was recorded. Both heads get fresh
  exact-head reviews instead (below).
- 22:22–22:30Z — #1074's 30 evidence files (`tasks/review-evidence/prompt-candidate-2026-10-02/`,
  unchanged from `437e245c`; no `backend/` file) landed on this checkpoint branch (`6e5e3aee`) so
  #1074 can close after this PR merges without stranding its pre-registration, tools and review
  history. Gates on that tree: backend pytest 5759 passed, 39 skipped; frontend vitest 1129/1129;
  `test_review_evidence_links` passes; the relative link to `../g-stage2-2026-10-02/README.md`
  resolves. D1/D2 results recorded (`405565db`).
- 22:39Z — Independent exact-head review of #1119 `76d2ba6d` started (`wf_fb41f1a6-737`, two
  lenses, two refuters per serious finding; a first launch with a mistyped main SHA was stopped
  before any result and relaunched with `d4c977f5`).
- 22:42Z — #1081 worktree: main `d4c977f5` merged into `4cba0bf9` with no conflict (`d7514ddf`,
  local). New open PRs since the last entry: #1120 (product lane EN-05, draft, 22:24Z): observe-only.
  Simulated merges of `d7514ddf` with #1108, #1110, #1113, #1118 and #1120 are clean, and every
  frontend file they change lints clean under #1081's rule (`eslint --stdin` on the merged trees).
- 22:44Z — Exact-head review of #1081 `d7514ddf` started (`wf_f00af592-b15`).
- 22:45Z — #1081 local gate on `d7514ddf` (Node 22.23.2, npm 10.9.8): npm ci ok, lint 0, tsc 0,
  vitest 147 files / 1204 tests, build 0.
- ~22:50Z — **Container restart.** Both running reviews (`wf_fb41f1a6-737` for #1119,
  `wf_f00af592-b15` for #1081) were lost before any result; the disk (worktrees, local commits,
  toolchain) survived. Relaunched unchanged at 22:54Z: #1119 `wf_8e1db8eb-fd7`, #1081
  `wf_ddbc4a5f-497`.
- 22:55–22:56Z — #1081 pushed `53cc2762..d7514ddf` (fast-forward). Diff vs main touches only
  `frontend/` and `lessons/`; the 20 layout-class edits are byte-identical to the 10-04 head (only
  the rule, its spec, the lesson and `DESIGN_SYSTEM.md` changed). PR body updated: re-integration
  record, current gate, the stale 10-04 `Review override` line withdrawn so the review gate needs a
  real Codex review of this head. Draft→ready cycle at 22:56Z to trigger it.
- 22:58Z — Codex review of #1081 `d7514dd`: one P2 finding (thread 4212882992). The rule demanded
  the display's exact variant, so it flagged valid `hidden md:grid sm:grid-cols-2`, and its message
  suggested `md:grid-cols-1`, which would override the two columns. Reproduced (4 failing cases),
  fixed in `1a81a1ba` (local; a smaller screen's columns cover a larger screen's display). Gate:
  lint 0, tsc 0, vitest 1211, build 0.
- 23:08Z — #1081 exact-head review `wf_ddbc4a5f-497` (d7514ddf): **one should-fix confirmed** by
  both refuters. Inside a class unit, any call's arguments counted as always-rendered, so
  `cx('grid', choose(wide, 'md:grid-cols-2', 'grid-cols-1'))`, `.at(i)` and `.filter(pred)` lent a
  base. Also four nits:
  - arbitrary `[grid-template-columns:…]` columns are unchecked;
  - `[&:has(>img)]:` is dropped as styling another element;
  - a base supplied by every ternary arm is flagged;
  - CLAUDE.md rule 11 and the `eslint.config.mjs` comment are stale.

  Merge integrity is clean (the merge's patch-id equals main's own diff), and no `DESIGN.md` or
  sidecar refresh is owed. Fixed in `b3b03a8c` (local): helper arguments only, plus the receiver
  of `.join`, `.filter(Boolean)` or `.trim`. Carried in the same commit: the first two nits fixed,
  the third documented as fail-closed, the docs updated. Proofs:
  - the reverted CallExpression case fails 5 of the 94 spec cases;
  - the final rule over main `d4c977f5` reports exactly the 20 sites the PR fixes (16 files) and
    nothing else.
- 23:10Z — #1119 exact-head review `wf_8e1db8eb-fd7` (`76d2ba6d`, three lenses): **no blocker, no
  should-fix**. It re-verified the lock against #1096, the openai and fastapi wheel diffs, the
  dependabot.yml semantics and both cited jobs. Nits (not pushed; README corrections land through
  this checkpoint): the evidence README's release-boundary paragraph predates the push; the
  python-dotenv 1.2.4 note omits the `KEY=   # comment` parser fix (local `.env.example` only).
- 23:11:45Z — #1119 head `76d2ba6d` re-read, main `d4c977f5` unchanged, all checks green (CI
  37695329830, Vercel success, review-gate success after Codex's completed no-findings review).
  Evidence comment 6048726325. **#1119 merged** `111e8ce4` (squash, `expectedHeadSha` pinned).
- 23:12Z — **#1096 closed** as superseded (comment 6048731593). Main CI 37700883978 started; the
  deploy follows the test jobs.
- 23:17Z — #1081 pushed `d7514ddf..b3b03a8c` (fast-forward) after a full local gate on `b3b03a8c`:
  lint 0, tsc 0, vitest 1223, build 0. Every frontend file of #1108, #1110, #1113, #1118 and #1120
  re-linted clean under the final rule; #1009's conflict set is unchanged (`pricing/page.tsx`,
  `tasks/todo.md`, the same against main). Codex thread 4212882992 answered and resolved. PR body
  updated; draft→ready at 23:18Z (Codex review of `b3b03a8`). Delta review `wf_d497c7b3-60c`
  started. Safety-net check-in re-armed for 00:10Z (`trig_01YUfB3jk3jvQgbBQ2wbbW3t`).
- 23:21Z — Codex on #1081 `b3b03a8`: one P2 (thread 4213020281). A responsive `grid-cols-none`
  after a valid base (`grid grid-cols-1 sm:grid-cols-none md:grid-cols-2`) clears the tracks but
  passes. Pre-existing since the rule's first version; `1a81a1ba` also let
  `hidden md:grid sm:grid-cols-2 md:grid-cols-none` through. No file in the tree uses
  `grid-cols-none`. Fix drafted locally: any reset under a variant is reported on its own, with a
  `grid-cols-[auto]` hint. Mutation proof: without it, both cases pass (96/98).
- 23:24:05Z — **#1119 deploy verified** (deploy job 113066259541, the first Buildx deploy):
  - build and push about 82 s;
  - `apply_migrations: applied=0 skipped=41`;
  - revision `earningsnerd-backend-00446-vhw` at 100% (`100% LATEST`);
  - all 8 job images updated;
  - "Verify health" healthy;
  - independent `/health/detailed` 200 healthy at 23:24:50Z (database 6.13 ms, SEC circuit closed).

  Release comment 6048886899. The release record was added to
  `tasks/review-evidence/deps-minor-2026-10-07/README.md`.
- 23:29:52Z (observed) — Codex lane #1122 (`codex/wave3-durable-background-tasks`) merged by its owner at
  23:19:32Z (`6393518c`). At that moment #1119's main CI run 37700883978 was still running its test
  jobs; its deploy job started at 23:20:37Z. The two deploys ran one after the other, not together. Its deploy job 113068536115 succeeded: revision
  `earningsnerd-backend-00447-hlv` at 100%, "Deployed 6393518 and verified healthy" (with
  `DURABLE_TASKS_ENABLED=false`). Independent `/health/detailed` 200 healthy at 23:41:29Z.
- 23:36–23:47Z — #1081 rounds:
  - Delta review `wf_d497c7b3-60c` of `d7514ddf..b3b03a8c`: no blocker or should-fix, six nits.
  - `ccc1bbf3`: a column reset under a variant is reported on its own (the Codex P2 on `b3b03a8c`).
  - `daf52468`: carries the nits, including `SCREENS` pinned against `tailwind.config.js`.
  - Codex on `daf52468`: P2, a combinator next to `&` inside `:where()` was dropped. Fixed in `1846bc78`.

  Gates at each head: lint 0, tsc 0, vitest 1227 then 1229, build 0. The final rule still reports exactly
  the 20 PR sites on main. Codex threads 4212882992, 4213020281 and 4213129431 were answered and resolved.
- 23:38–23:47Z — New PRs during the run:
  - #1121 (Codex lane, email setup, draft), #1123 (Claude lane, copilot-eval paths, draft) and #1126
    (Claude lane, agent-workflow gates, draft): live owners, observe-only.
  - #1124 (Dependabot pip, 2 updates) and #1125 (Dependabot frontend, 4 updates), both opened 23:14Z: no
    live owner, so taken through the same process. #1124's group excludes edgartools, which shows #1119's
    `dependabot.yml` change works.
- 23:43–23:51Z — **#1125 merged** `0a5eeccc` (head `1b657b51` re-read, `expectedHeadSha` pinned):
  - Codex triggered by a draft→ready cycle; no findings.
  - `review-gate` 37703530386 success.
  - Local gate on main + PR: vitest 1129, build 0; `npm audit` unchanged versus main.
  - Independent review `wf_f3cb3d7c-25a`: no findings (lock scope and integrity, Sentry PII, posthog
    consent).
  - Vercel production success 23:51:58Z; `www` 200 at 23:52:32Z. Evidence comment 6049203118.
- 23:50–23:52Z — **#1124 replacement #1127** (`claude/pr1124-backend-minor-updates`, `4fbec187` = main
  `6393518c` + `cherry-pick -x` of `3ce33352`, identical patch-id):
  - pip-tools 7.6.1 reproduces the lock byte for byte; a second compile is identical; 100/100 pins match.
  - Gate: `pip check` clean, ruff clean, bandit 0 medium/high, `pip-audit` clean, pytest 5811 passed.
  - SDK review: no findings. openai 3.24's client, errors and streaming are byte-identical to 3.23; only
    the JSON key order of the request body changes. posthog 7.62.1 touches only `posthog.ai`, unused here.
  - Opened as a draft at 23:51Z, D3 dispatched 23:51:46Z, ready 23:52:01Z (D4 + Codex).
- 23:52–23:56Z — **#1081 merged** `4e8252be` (head `1846bc78` re-read; CI 37704184147 green;
  review-gate success; `clean`; simulated merge onto main `0a5eeccc` clean). Before the merge, two more
  Codex P2s on `1846bc78` were answered without a build (threads 4213192961 and 4213192965), with
  the decision put to the founder. Both are fail-closed false positives on shapes absent from the
  tree: arbitrary `min-[…]` screens, and a reset that applies only while the element is hidden.
  Vercel production success 23:56:08Z; `www` and `/pricing` 200. Evidence comment 6049249453.
- 23:54–00:01Z — #1127 results:
  - D4 copilot-eval 37704656898: accepted 18/18, USD 0.006423.
  - Codex on `4fbec18`: no findings.
  - D3 eval-baseline 37704631398: 70/70 PASS, USD 0.175076.
  - PR CI 37704612545: green.
- 00:02Z — Head `4fbec187` re-read; 23/23 checks green; `clean`. Evidence comment 6049314355.
  **#1127 merged** `41248d01`; **#1124 closed** as superseded (comment 6049316739). The deploy is
  watched.
- 00:12Z — **#1127 deploy verified.** Main CI 37705611585 on `41248d01` succeeded. In deploy job
  113080756294:
  - `apply_migrations: applied=0 skipped=41`;
  - revision `earningsnerd-backend-00448-qk7` serving 100 percent from 00:10:40Z;
  - all 8 job images updated;
  - "Deployed 41248d0 and verified healthy" at 00:11:20Z.

  Independent `/health/detailed` 200 healthy at 00:12:01Z. Release comment 6049437703.
- 00:04–00:16Z — **Stage 3** (`wf_a62e9e1a-2e7`, three fresh read-only agents, lenses: PR outcomes,
  deploys and spend, boundaries). Corrections applied in this file:
  - The record said no branch was deleted. In fact the repository's delete-on-merge setting and
    Dependabot removed the branches of merged and closed PRs (see Boundaries kept).
  - My closing comments 6048731593 (#1096) and 6049316739 (#1124) said the branch was left in place.
    Both were edited in place with a correction and the `refs/pull/<n>/head` SHA.
  - Count wording fixed (7 of 12 final, 16 opened including this PR). Decision 3's range is now
    0.818–0.871 across 8 runs.
  - Timestamps corrected to the API values: #1102 merged 21:15:08Z and its Vercel deploy 21:15:47Z;
    #1107 merged 21:17:36Z; #1107 and #1108 marked ready 19:45:44Z and 19:45:56Z; #1116 opened
    21:27:20Z; #1110 marked ready 22:17:44Z; the D2 and D4 ready transitions were 22:18:41Z and
    23:52:01Z.
  - #1108's head at 20:40Z was `54856d48`, not `484a357a`. #1122's merge came before #1119's deploy
    job started; the two deploys ran one after the other.
