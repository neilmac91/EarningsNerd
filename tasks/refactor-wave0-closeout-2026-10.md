# Wave 0 closeout — 2026-10-10

Wave 0 is complete. W0.G and C0/T0/F0/X0/O0/I0 are merged; their mutation evidence is retained
in the PRs below. The founder authorized Dead cleanup and extended the USD 5 balance floor to
this refactor programme on 2026-10-10. The USD 18 ceiling and per-trigger reservations remain.
Dead must merge with a verified backend deployment before I1 starts.

## Anchors and proof

| Item | Merged PR | Merge commit | Retained evidence |
|---|---|---|---|
| W0.G | [#1156](https://github.com/neilmac91/EarningsNerd/pull/1156) | `07bfaa639707` | Size budgets and AST proof; ceiling mutation failed, restored gate passed. Follow-up proof hardening: #1174 and #1177 (which folded #1179). See the PR’s Mutation proofs and Review sections. |
| C0 | [#1157](https://github.com/neilmac91/EarningsNerd/pull/1157) | `e1c4352be049` | C0.1–C0.4: rendering, progress labels, heartbeat timing/re-arm, pre-attempt stream failure. See the PR’s Mutation proofs and Review sections. |
| T0 | [#1158](https://github.com/neilmac91/EarningsNerd/pull/1158) | `0dbdbf1384bb` | T0.1–T0.6: all six trend anchor groups. See the PR’s Mutation proofs and Review sections. |
| F0 | [#1159](https://github.com/neilmac91/EarningsNerd/pull/1159) | `e9c18cb1ecbb` | F0.1–F0.6: all six facts anchor groups. See the PR’s Mutation proofs and Review sections. |
| X0 | [#1160](https://github.com/neilmac91/EarningsNerd/pull/1160) | `1f43d7f015a9` | X0.1–X0.6: transport and extraction behavior. See the PR’s Mutation proofs and Review sections. |
| O0 | [#1161](https://github.com/neilmac91/EarningsNerd/pull/1161) | `c69f90fe0810` | A1–A6: exact request snapshots and post-provider phases; raw/excerpt provenance separated in the reviewed fix. See the PR’s Mutation proofs and Review sections. |
| I0 | [#1162](https://github.com/neilmac91/EarningsNerd/pull/1162) | `a0315ac32fdb` | I0.1–I0.5: façade identity, currency selection, source provenance and deduplication. See the PR’s Mutation proofs and Review sections. |

Each PR records its failing mutation and restored passing control. This closeout cites those
records; it does not claim to have repeated every historical mutation. The anchor review’s
recorded 216-test combined runs are execution evidence, not a completed independent review:
it stopped at a usage limit before returning its report. Subsequent review findings and fixes
are recorded in the respective PRs.

Proof fixes landed in [#1174](https://github.com/neilmac91/EarningsNerd/pull/1174) (compound
headers and class property/descriptor handling) and [#1177](https://github.com/neilmac91/EarningsNerd/pull/1177)
(ADDED names that shadow moved-code reads, plus dunder/docstring coverage). A passing AST proof
still requires review of every ADDED symbol and the helper’s stated limits.

Current baseline on main `aa9cf45b6950b81ce005b6f59fd36685e7336274`, before Dead:

```text
ruff check .: All checks passed!
bandit -r app -ll: No issues identified. (0 medium, 0 high)
python -m pytest:
6576 passed, 39 skipped, 153 warnings in 91.45s (0:01:31)
```

The first sandboxed attempt had 6,575 passes and one loopback-bind PermissionError in the
network-gate self-test. The unchanged suite passed with loopback permission; no test was skipped
or weakened to get the baseline. Main CI [38053943458](https://github.com/neilmac91/EarningsNerd/actions/runs/38053943458)
is green on the same commit. The retained full-suite result includes all six anchor files,
size-budget gates and proof self-tests.

## Wave 0 spend

The rows below enumerate `copilot-eval.yml` history for the seven Wave 0 branches. Cost is the
sum of each job log’s `ai_call.estimated_cost_usd` values (six-decimal telemetry), not an invoice
or a provider-wallet delta. The cancelled #1156 reopen completed its calls and is counted in
full. All 10 skipped runs had no inference calls. These tests-only PRs incurred no summary
`eval-baseline` inference. Multiple draws predate the once-per-head gate and are preserved here,
not treated as permission to repeat them today.

The PR bodies preserve USD 0.06 reservations for paid triggers. The accidental #1156 reopen
was an unplanned trigger, disclosed there. Later runs are ready/review rounds or pushes for the
findings documented by that PR; identical-head ready rounds are shown explicitly. No retrospective
reservation is asserted for the unplanned reopen. Current reservation policy remains USD 0.06
per Copilot draw and USD 0.73 per summary-eval trigger.

| UTC date/time | PR | Head | Run | Result / calls | Estimated USD | Running USD |
|---|---|---|---|---|---:|---:|
| 2026-10-09 11:58:43 | #1156 | `6ba7f9c9` | [37927066597](https://github.com/neilmac91/EarningsNerd/actions/runs/37927066597) | skipped, 0 | 0.000000 | 0.000000 |
| 2026-10-09 12:16:30 | #1157 | `21f06939` | [37928960239](https://github.com/neilmac91/EarningsNerd/actions/runs/37928960239) | skipped, 0 | 0.000000 | 0.000000 |
| 2026-10-09 12:19:11 | #1158 | `834c2c36` | [37929240128](https://github.com/neilmac91/EarningsNerd/actions/runs/37929240128) | skipped, 0 | 0.000000 | 0.000000 |
| 2026-10-09 12:24:03 | #1159 | `53c1dd85` | [37929772958](https://github.com/neilmac91/EarningsNerd/actions/runs/37929772958) | skipped, 0 | 0.000000 | 0.000000 |
| 2026-10-09 12:26:43 | #1160 | `fc1f2c06` | [37930064650](https://github.com/neilmac91/EarningsNerd/actions/runs/37930064650) | skipped, 0 | 0.000000 | 0.000000 |
| 2026-10-09 12:29:20 | #1161 | `7335e225` | [37930350928](https://github.com/neilmac91/EarningsNerd/actions/runs/37930350928) | skipped, 0 | 0.000000 | 0.000000 |
| 2026-10-09 12:30:59 | #1162 | `d8a6446d` | [37930544123](https://github.com/neilmac91/EarningsNerd/actions/runs/37930544123) | skipped, 0 | 0.000000 | 0.000000 |
| 2026-10-09 12:50:12 | #1156 | `f29cde2e` | [37932659957](https://github.com/neilmac91/EarningsNerd/actions/runs/37932659957) | skipped, 0 | 0.000000 | 0.000000 |
| 2026-10-09 16:39:36 | #1157 | `13c3da14` | [37960700910](https://github.com/neilmac91/EarningsNerd/actions/runs/37960700910) | skipped, 0 | 0.000000 | 0.000000 |
| 2026-10-09 16:40:20 | #1161 | `48e2f7cd` | [37960789051](https://github.com/neilmac91/EarningsNerd/actions/runs/37960789051) | skipped, 0 | 0.000000 | 0.000000 |
| 2026-10-09 16:43:46 | #1158 | `834c2c36` | [37961202125](https://github.com/neilmac91/EarningsNerd/actions/runs/37961202125) | success, 36 | 0.006767 | 0.006767 |
| 2026-10-09 16:44:20 | #1159 | `53c1dd85` | [37961270283](https://github.com/neilmac91/EarningsNerd/actions/runs/37961270283) | success, 37 | 0.006948 | 0.013715 |
| 2026-10-09 16:44:57 | #1160 | `fc1f2c06` | [37961341507](https://github.com/neilmac91/EarningsNerd/actions/runs/37961341507) | success, 35 | 0.006584 | 0.020299 |
| 2026-10-09 16:45:27 | #1162 | `d8a6446d` | [37961405715](https://github.com/neilmac91/EarningsNerd/actions/runs/37961405715) | success, 36 | 0.006707 | 0.027006 |
| 2026-10-09 16:46:10 | #1156 | `f29cde2e` | [37961491439](https://github.com/neilmac91/EarningsNerd/actions/runs/37961491439) | success, 35 | 0.006494 | 0.033500 |
| 2026-10-09 16:51:01 | #1158 | `0450017c` | [37962060704](https://github.com/neilmac91/EarningsNerd/actions/runs/37962060704) | success, 34 | 0.006456 | 0.039956 |
| 2026-10-09 16:52:24 | #1157 | `13c3da14` | [37962221057](https://github.com/neilmac91/EarningsNerd/actions/runs/37962221057) | success, 38 | 0.007017 | 0.046973 |
| 2026-10-09 16:52:26 | #1161 | `48e2f7cd` | [37962225333](https://github.com/neilmac91/EarningsNerd/actions/runs/37962225333) | success, 35 | 0.006476 | 0.053449 |
| 2026-10-09 16:56:26 | #1160 | `493be74f` | [37962694400](https://github.com/neilmac91/EarningsNerd/actions/runs/37962694400) | success, 36 | 0.006884 | 0.060333 |
| 2026-10-09 16:56:28 | #1162 | `6e2901f4` | [37962697079](https://github.com/neilmac91/EarningsNerd/actions/runs/37962697079) | success, 37 | 0.007053 | 0.067386 |
| 2026-10-09 17:29:46 | #1156 | `f29cde2e` | [37966670586](https://github.com/neilmac91/EarningsNerd/actions/runs/37966670586) | cancelled, 35; accidental reopen | 0.006525 | 0.073911 |
| 2026-10-09 17:31:31 | #1156 | `0f9e9813` | [37966887344](https://github.com/neilmac91/EarningsNerd/actions/runs/37966887344) | success, 35 | 0.006715 | 0.080626 |
| 2026-10-09 17:36:33 | #1157 | `fe70d7fd` | [37967479957](https://github.com/neilmac91/EarningsNerd/actions/runs/37967479957) | success, 37 | 0.006860 | 0.087486 |
| 2026-10-09 17:36:35 | #1161 | `24bc462a` | [37967484361](https://github.com/neilmac91/EarningsNerd/actions/runs/37967484361) | success, 35 | 0.006501 | 0.093987 |
| 2026-10-09 17:51:20 | #1156 | `302ffb8a` | [37969197119](https://github.com/neilmac91/EarningsNerd/actions/runs/37969197119) | success, 34 | 0.006423 | 0.100410 |
| 2026-10-09 17:56:25 | #1157 | `b787b8e2` | [37969790917](https://github.com/neilmac91/EarningsNerd/actions/runs/37969790917) | success, 38 | 0.007153 | 0.107563 |
| 2026-10-09 18:21:51 | #1156 | `dcd3e57e` | [37972749096](https://github.com/neilmac91/EarningsNerd/actions/runs/37972749096) | success, 36 | 0.006835 | 0.114398 |
| 2026-10-09 18:37:16 | #1156 | `0d4fbeb0` | [37974547301](https://github.com/neilmac91/EarningsNerd/actions/runs/37974547301) | success, 34 | 0.006344 | 0.120742 |
| 2026-10-09 18:53:33 | #1156 | `973bf07d` | [37976422204](https://github.com/neilmac91/EarningsNerd/actions/runs/37976422204) | success, 34 | 0.006413 | 0.127155 |
| 2026-10-09 19:07:49 | #1156 | `c8e45eb9` | [37978091846](https://github.com/neilmac91/EarningsNerd/actions/runs/37978091846) | success, 34 | 0.006336 | 0.133491 |

Total: **USD 0.133491**, 20 runs with calls and 10 skipped. Remaining programme ceiling:
**USD 17.866509** before Wave 1. This is a programme limit, not available provider balance.

### Balance readings

These readings are the shared wallet, including production and unrelated programmes. They cannot
be subtracted to derive this lane’s spend. The original floor was USD 25; the founder superseded
it with USD 5 on 2026-10-10. The PR-body source for the historical readings is #1156’s Spend section;
#1157–#1162 reuse the relevant readings and link the same runs.

| UTC date/time | Balance USD | Free balance workflow | Reason |
|---|---:|---|---|
| 2026-10-09 12:49 | 28.38 | [37932600962](https://github.com/neilmac91/EarningsNerd/actions/runs/37932600962) | Wave 0 ready transitions |
| 2026-10-09 17:23 | 26.76 | [37965926460](https://github.com/neilmac91/EarningsNerd/actions/runs/37965926460) | Review-fix pushes |
| 2026-10-09 17:47 | 26.37 | [37968774003](https://github.com/neilmac91/EarningsNerd/actions/runs/37968774003) | Review-fix pushes |
| 2026-10-09 17:59 | 26.33 | [37970113249](https://github.com/neilmac91/EarningsNerd/actions/runs/37970113249) | #1156 review-fix push |
| 2026-10-09 18:28 | 25.87 | [37973467465](https://github.com/neilmac91/EarningsNerd/actions/runs/37973467465) | #1156 pre-push check |
| 2026-10-09 18:36 | 25.80 | [37974469687](https://github.com/neilmac91/EarningsNerd/actions/runs/37974469687) | #1156 immediately before push |
| 2026-10-09 18:53 | 25.46 | [37976355177](https://github.com/neilmac91/EarningsNerd/actions/runs/37976355177) | #1156 review-fix push |
| 2026-10-09 18:59 | 25.43 | [37977060651](https://github.com/neilmac91/EarningsNerd/actions/runs/37977060651) | #1156 pre-push check |
| 2026-10-09 19:07 | 25.43 | [37978030671](https://github.com/neilmac91/EarningsNerd/actions/runs/37978030671) | #1156 immediately before push |
| 2026-10-10 12:10 | 21.83 | [38050979625](https://github.com/neilmac91/EarningsNerd/actions/runs/38050979625) | Pre-cleanup status check; no inference |
| 2026-10-10 14:07 | 21.83 | [38058342515](https://github.com/neilmac91/EarningsNerd/actions/runs/38058342515) | Before Wave 1 Dead; USD 0.73 summary plus USD 0.06 Copilot reservations fit above the USD 5 floor |
