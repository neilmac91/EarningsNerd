# Audit — Astra takeover, 2026-09-08

The audited span is `d7b01779..3336d513` (#741 to #770): 132 files, +9521/−520.
Current main at audit start was `1fe1f156` (#771), which adds the handover documents only.
Three independent lenses covered correctness, rules/brief/tests, and GitHub/ledger evidence;
the lead reconciled their findings. Candidate findings survived only after two independent
refutation attempts. This report distinguishes observed evidence from prior-session claims.

## Verdict and disposition

The recorded releases and production checkpoints are supported by GitHub evidence, but the
session is not a clean pass. One runtime must-fix loses pending alerts across a crash during
envelope replacement. One historical boundary finding misclassified the actual locked T4 file.
The runtime fix is being verified separately. The founder approved retaining #759's
additions on 2026-09-08 as a specific lock exception; this resolves the historical boundary disposition. A smaller provider-admission cleanup gap and documentation inaccuracies
are recorded below. No live email, job test, replay, account action or console operation was
performed by this audit.

## Must-fix findings

**M1 — Pending alert replacement can lose durable work.**
`backend/app/services/notification_delivery_service.py:485` at the audit endpoint calls
`park_and_release` (which commits at line 316), then separately calls `create_batch`.
A user switches from realtime to digest while a two-day-old filing is pending; a process death
or insertion exception after the first commit leaves a terminal suppressed batch with no items
and no replacement. The next digest's selection window excludes that filing, so the alert is
lost without a later failure count. Refutation 1: traced both helpers and confirmed the release
is committed rather than part of the replacement transaction. Refutation 2: injected replacement
failure through the real ORM/drain, reopened a fresh session, and ran the next digest: old batch
suppressed, zero owned items, zero sent logs and zero sends. This is not recovered by the scheduler.
Fix: `codex/wave3-delivery-atomic-rebuild` commits the fenced release and replacement together;
failed insertion/collision retains the old claim and items for retry after lease expiry.
Release evidence will be appended after deployment.

**M2 — #759 crossed the actual T4 file lock without a recorded exception.**
`backend/tests/unit/test_subscription_webhook_sync.py:289` adds 95 lines, while
`tasks/todo.md`'s “Stripe dunning-policy gates” record and
[PR #759](https://github.com/neilmac91/EarningsNerd/pull/759) call that file unlocked.
The misleading planned filename `test_stripe_downgrade.py` never became the anchor's home:
[the actual completion record](architecture-refactor-plan.md) at lines 78–83 identifies this
file, including the past-due money-OFF test. A future engineer trusting the exemption could
weaken that anchor without approval. Refutation 1: resolved the planned inventory against the
completion record and original commit `2b41718d`; both identify T4's real home. Refutation 2:
compared the full diff and fetched #759's body/comments/reviews: no deleted symbol or documented
contract approval. The old file is an exact byte prefix, so no existing assertion was weakened
and no runtime regression is attributed to these additions. The file remains untouched by this
audit. A dated ledger correction is appended. On 2026-09-08 the founder explicitly approved retaining
the additions. This is a retention decision, not a claim that the original edit was pre-approved;
future edits remain subject to the existing lock.

## Should-fix findings

**S1 — Chat admission releases before transport cleanup.**
`backend/app/services/ai/copilot_chat.py:65` exits the admission context before the outer
`finally` awaits `close_stream` at line 87. On early consumer closure, a queued request can
start while the previous provider transport is still closing; counters can report a peak of one
while two transports remain open. Refutation 1: traced async-context unwinding and the SDK close
path, including generator `aclose`. Refutation 2: exercised the real SDK with a mock transport,
limit one, and paused the first response's `aclose`; the second yielded while the first transport
was still open. This is a bounded cleanup overlap, not evidence of unbounded generation. Recorded
for a later code PR under the instruction to leave should-fixes unless a tiny in-scope change.

**S2 — Migration inventory omits the reservations migration.**
`tasks/handover-astra-2026-09-08.md:122` says two new files; there are three, including
`20260906_earningsnerd_usage_reservations.sql` (#746). An operator following that inventory could
omit the admission schema from review. Refutation 1: the endpoint diff and #746 body both identify
the new file. Refutation 2: #746's deploy independently records `applied=1 skipped=36`, followed
by #747's 1/37 and #757's 1/38. CI's glob includes all three. Dated correction appended below the
original handover record.

**S3 — Paid-evaluation summary understates #746.**
`tasks/handover-astra-2026-09-08.md:120` says every other backend PR had one paid evaluation;
#746 had two, so the summary understates spend. Refutation 1: successful workflow runs
[34061837988](https://github.com/neilmac91/EarningsNerd/actions/runs/34061837988) and
[34063706652](https://github.com/neilmac91/EarningsNerd/actions/runs/34063706652) ran on distinct
heads. Refutation 2: #747's body and its todo continuation explicitly acknowledge the two approved
#746 runs. This is a summary error, not evidence of unauthorized spending. Dated correction appended.

## Nits and evidence limitations

**N1 — Overnight introduction compresses away a migration.** `tasks/todo.md:7` at the audit
endpoint says `applied=0` for all seven overnight releases; #757 applied one. Refutation 1:
its detailed ledger already says one. Refutation 2: deploy job `101883531459` independently shows
`applied=1 skipped=38`. The historical introduction remains intact with a dated correction beneath it.

Historical local mutation executions and independent curls cannot be reconstructed from GitHub
alone. The named tests and asserted branches exist, but that does not prove every historical local
failure count. In particular, #747's final body summarizes mutations instead of retaining every
exact red/green tail. Founder Cloud Shell evidence is the supplied archive, not a new console
observation. We verified CI health in all deploy logs and independently queried current health;
we do not claim to have replayed historical curls, Vercel serving observations or production jobs.

## Gates run by this audit

On committed main `1fe1f156`, Python 3.11.16, pinned Ruff 0.16.6/Bandit 1.9.4 and disposable
PostgreSQL 15, all four CI-named lanes were configured: `STRIPE_CONCURRENCY_TEST_DATABASE_URL`,
`USAGE_CONCURRENCY_TEST_DATABASE_URL`, `LOGIN_CONCURRENCY_TEST_DATABASE_URL`, and
`DELIVERY_CONCURRENCY_TEST_DATABASE_URL`. Full gate, including performance: Ruff, Bandit and pytest exited 0. Exact Ruff/pytest tails:

```text
All checks passed!
================= 2729 passed, 27 warnings in 90.09s (0:01:30) =================
```

The first full backend attempt had 2727 passes and two PDF errors because this newly provisioned
Python could not locate macOS `libgobject`. Restoring native-library discovery and rerunning the
entire gate produced the result above. The first frontend run was stopped because it overlapped
pytest in the same worktree; it was not counted. Frontend then ran in a separate clean worktree
on the same committed main, using CI-pinned Node 22.23.2:

```text
 Test Files  103 passed (103)
      Tests  569 passed (569)
   Duration  43.26s (transform 4.59s, setup 9.63s, import 168.79s, tests 14.00s, environment 85.77s)
✓ Compiled successfully in 8.6s
```

Independent `curl -fsS https://api.earningsnerd.io/health/detailed` returned healthy at timestamp
`1788883729.3877954`: database 11.66 ms, Redis disabled/healthy, SEC breaker closed/healthy.
This health response does not independently expose a revision or traffic assignment; those are
verified from the latest deploy log.

## Full locked inventory

Blob comparisons at both exact endpoints, not empty diffs against nonexistent pathspecs, show
T1 SSE, T2 background, T3's account-required successor, T5 expired trial, T7 filing scan,
T8 refresh replay, T9 companyfacts fixture, T10 frontend parser contract, auth flow, and
`test_stripe_webhook.py` byte-identical. T4 differs as M2 states. T6 is explicitly deferred in
the completion record; no imaginary file was counted as a passing comparison.

## Refuted candidates and seven scepticism checks

1. **W3-9 still inserts or stamps in flags-only mode:** refuted by the early return on identity
   misses and the conditional processed timestamp; independent ORM tests snapshot insertion,
   demotion and timestamps through both service and CLI. Source/value mismatch and unavailable
   companyfacts preserve flags. The earlier 78 inserts/19 flag changes are acknowledged in both
   ledgers and the supplied [founder review](archive/w39-review-2026-09-08.md), not hidden or replayed.
2. **#769 retries quality failures or double-counts denominators:** refuted by one final row per
   requested attempt and totals derived from those rows, then by deterministic retry/exhaustion/
   non-transient tests. Anthropic optional-SDK classification has explicit class/status tests.
   Weekly readout passes and records the policy. The PR's live run scored 52/52 with zero errors
   and `retried:0`; it did not exercise a live retry.
3. **#762/#763 concealed other red checks:** refuted by workflow jobs and independent check-runs/
   commit statuses. Each had only advisory eval-baseline red (52 attempted/51 scored/one timeout,
   remaining pass rate 1.0), disclosed on its PR and ledger. Required CI and paid Copilot succeeded.
4. **Missing test homes behind mutation claims:** every backend PR's named homes/assertions exist.
   Deep #747 tests cover ordinary rebuild, fences, replay, ambiguity and cascades but missed M1's
   crash seam. Deep #766/#769 guards match their documented mutations. Source coverage confirms
   plausibility, not historical local execution; the limitation above remains explicit.
5. **Unrecorded paid rounds:** workflow history confirms #746 two; #747 three; #766 three; #769 two;
   each other backend PR one. The detailed records explain fix rounds. S3 corrects the summary.
6. **New migrations not triple-tested:** refuted by CI's full-glob execution and logs showing
   #747 38/0 → 0/38 → 38/0 and #757 39/0 → 0/39 → 39/0. The three new files are guarded;
   later production deploys skip them. S2 corrects the inventory.
7. **Founder job effects omitted:** the ledgers retain the 78 fact rows, 19 flag flips, 270 Notable
   rows and retention dry-run counts, with W3-9's scope deviation and subsequent review. There is
   no evidence in the available records of another production data operation; lack of console
   access prevents independently proving a universal absence claim.
   Parsing the supplied archive independently reproduced 78 rows/39 accessions/two each,
   ids 16062–16139, 77 reconciled/one flagged, 16 non-latest rows and 18 repeated-period groups
   with agreeing values; per-filing apply totals sum to 78 inserted/19 refreshed/51 mismatches.

All twelve rules were checked across touched application files. No new orchestrator, cross-filing
summary input, entitlement authority, SEC transport bypass, env-access bypass or filing URL builder
was found. New timestamps follow the existing aware/naive boundaries. Frontend account isolation
uses generation checks, cancellation/removal and user-scoped keys; independent active-observer and
late-response tests cover those paths. Copy and identity guards have regression tests; the work
adds no theme migration. Cross-tab cookie ordering is outside the claimed guarantee. The rule-6
inventory error is M2, rather than an invented blanket clean result.

## Release evidence reconciliation

All 19 code PR squash SHAs and all 15 backend main CI runs match. Each deploy log records the
listed migration tail, revision at 100% traffic and healthy detailed health. Every subsequent
backend merge happened after the preceding deploy completed. Frontend main CI runs #742–#745
also succeeded. The table records observed GitHub evidence, not guessed identifiers.

| PR | Merge | CI run | Deploy job | Migration | Revision |
|---|---|---|---|---|---|
| #746 | `c09a4d22` | 34064160001 | 101570260527 | `apply_migrations: applied=1 skipped=36` | `earningsnerd-backend-00293-fqs` |
| #747 | `4acea759` | 34156032956 | 101848504445 | `apply_migrations: applied=1 skipped=37` | `earningsnerd-backend-00294-lbd` |
| #753 | `52e04062` | 34158297001 | 101855139863 | `apply_migrations: applied=0 skipped=38` | `earningsnerd-backend-00295-s9z` |
| #754 | `85c2c23a` | 34163025781 | 101869064189 | `apply_migrations: applied=0 skipped=38` | `earningsnerd-backend-00296-zjt` |
| #755 | `757a8f17` | 34164749968 | 101873968238 | `apply_migrations: applied=0 skipped=38` | `earningsnerd-backend-00297-bwf` |
| #756 | `0768b865` | 34167002241 | 101880433011 | `apply_migrations: applied=0 skipped=38` | `earningsnerd-backend-00298-wnc` |
| #757 | `c7510ac9` | 34168106895 | 101883531459 | `apply_migrations: applied=1 skipped=38` | `earningsnerd-backend-00299-vxc` |
| #758 | `b84240d9` | 34169903896 | 101888565690 | `apply_migrations: applied=0 skipped=39` | `earningsnerd-backend-00300-7nj` |
| #759 | `bc973b20` | 34170515351 | 101890252557 | `apply_migrations: applied=0 skipped=39` | `earningsnerd-backend-00301-9xm` |
| #760 | `11db06dc` | 34172096044 | 101894737694 | `apply_migrations: applied=0 skipped=39` | `earningsnerd-backend-00302-fgl` |
| #761 | `fb26dbd4` | 34173005187 | 101897275114 | `apply_migrations: applied=0 skipped=39` | `earningsnerd-backend-00303-h6r` |
| #762 | `fc00ea10` | 34174484398 | 101901577645 | `apply_migrations: applied=0 skipped=39` | `earningsnerd-backend-00304-g6r` |
| #763 | `32c28e91` | 34175879213 | 101905538285 | `apply_migrations: applied=0 skipped=39` | `earningsnerd-backend-00305-hdv` |
| #766 | `1046907d` | 34194937694 | 101961157398 | `apply_migrations: applied=0 skipped=39` | `earningsnerd-backend-00306-2b9` |
| #769 | `7b6a32e6` | 34216384213 | 102029849295 | `apply_migrations: applied=0 skipped=39` | `earningsnerd-backend-00307-pzl` |

