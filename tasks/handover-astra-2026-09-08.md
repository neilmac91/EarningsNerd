# Handover — 2026-09-08, from the Claude session to the GPT-6 Astra session

Written 2026-09-08 by the Claude engineering session that took over from the Astra session on
2026-09-06. Companions, all still in force: [wave-3 handover](handover-wave3-2026-09.md)
(the ordered plan, founder prerequisites, re-pin rule), [wave-2 handover](handover-wave2-2026-09.md)
(operating procedure §4, traps §5, founder list §6), [execution ledger](beta-to-scale-execution.md),
[active todo](todo.md) (newest sections first; the overnight handover at its top is the founder's
morning read), root `AGENTS.md` (how to operate; read it first), `CLAUDE.md` (rules),
`lessons/README.md` (index; three entries are new since the handover point).

## 0. Handover point and checkpoint

- **You handed over at** main `d7b01779` = [#741](https://github.com/neilmac91/EarningsNerd/pull/741)
  (`codex/wave3-filing-dry-run-safety`, merged 2026-09-06 19:36 UTC). Every PR from #742 to #770
  is this session's work on the branch `claude/earningsnerd-handover-na6rnk`; PRs #748–#752 are
  five open Dependabot PRs, untouched.
- **You take over at** main `3336d513` = [#770](https://github.com/neilmac91/EarningsNerd/pull/770)
  (2026-09-08 10:52 UTC). Span: `d7b01779..3336d513`, 132 files, +9521/−520 lines.
- **Production:** Cloud Run `earningsnerd-backend-00307-pzl` at 100 % traffic (image `7b6a32e`);
  `apply_migrations: applied=0 skipped=39` on the last deploy; `/health/detailed` healthy in CI
  (10:43:29Z) and independently (10:44 UTC). All eight configured Cloud Run jobs run the current
  image, including the two created today (`earningsnerd-notable-filings`,
  `earningsnerd-retention-purge`). Schedulers live: `retention-purge-weekly` (Sundays 03:00 UTC,
  first fire 2026-09-13), `notable-filings-scan` (08:30 and 18:30 America/New_York, first fire
  2026-09-08 12:30 UTC). The homepage Notable section stays dark (`NOTABLE_FILINGS_ENABLED=false`).
- **Branch state:** `claude/earningsnerd-handover-na6rnk` is restarted from main and clean; no PR
  of this session is open. Six local worktrees of this session are not part of the repo.
- **Locked tests (rule 6)**: the six named in `CLAUDE.md` are byte-identical across the whole span.
  Proven 2026-09-08 with the six complete paths (bare filenames match nothing and return an empty diff regardless):
  `git diff --stat d7b01779 origin/main -- backend/tests/integration/test_summary_stream_contract.py
  backend/tests/unit/test_background_generation_characterization.py backend/tests/unit/test_auth_flow.py
  backend/tests/unit/test_stripe_webhook.py backend/tests/unit/test_filing_scan.py
  backend/tests/unit/test_expired_trial_gating.py` is empty. The full locked inventory is wider
  (`lessons/test-contract-tests-are-locked.md`: T1–T10 plus auth and Stripe webhook tests); the
  audit should run the same diff over every anchor it names.

## 1. Mandate this session worked under (recorded, verbatim where it matters)

- 2026-09-07 21:13 UTC, founder: "keep making progress and not constantly wait for my
  approvals" → one paid Copilot evaluation per backend PR at ready time plus the routine
  merge/deploy sequence (`lessons/ops-keep-moving-under-standing-authorization.md`).
- 2026-09-07 23:12 UTC, founder, before sleeping: "get as much done tonight as you can … you have
  my approval to perform additional paid evaluations if you deem them to be necessary" → more
  than one paid run per PR when a confirmed-finding fix round needs it, each recorded with its
  reason.
- 2026-09-08 morning, founder: "go with your best recommendation" on the eval-runner retry
  (decided and released as #769).
- Founder-held boundaries never moved: production flags, capacity, prices, trial/promo/registration,
  legal, destructive data or history operations, historical replay, the locked contract anchors, live
  email or job execution as a test, live account actions, the AI provider (DeepSeek stays),
  console actions (jobs, schedulers, secrets), Dependabot #270, Codex credits. The founder ran
  every console action themselves in Cloud Shell and pasted the output; the session reconciled it.

## 2. What was done since #741 (audit scope), newest last

Every backend PR below went: draft first → full local gate (pinned Ruff/Bandit, pytest including
the performance suite and four PostgreSQL lanes on a local 16.x cluster) → one mutation proof per
new invariant, restored → independent lens (a fresh agent, two refutations per candidate, every
survivor fixed before ready) → ready → one paid Copilot run (all accepted 18/18) → squash merge
with the exact head SHA → serial production verification (main CI, deploy log `applied=N
skipped=M`, Cloud Run revision at 100 %, CI `/health/detailed`, independent curl) → ledger record.
Codex reviewed every ready head from #765 onward (credits restored that morning); before that it
posted only its quota notice. Evidence for each row is in the named `tasks/todo.md` section.

| PR | Slice | Squash | Prod revision | Where recorded |
| --- | --- | --- | --- | --- |
| #742 | Account-cache isolation by account (subscription/usage caches) | `555c9ba` | frontend (Vercel) | todo "Account-cache isolation" |
| #743 | Billing-state honesty on pricing and the Billing panel | `3f44152` | frontend | todo "Billing-state honesty" |
| #744 | Calendar alert bell waits while identity resolves | `0b4b7f3` | frontend | todo "Calendar alert bell" |
| #745 | E08b free-tier caps mirrored once, lockstep gate | `e873ac8` | frontend | todo "E08b" |
| #746 | E07b summary admission reservations (PostgreSQL lease) | `c09a4d2` | 00293-fqs | todo "E07b" |
| #747 | E11b-1 durable alert delivery (persisted batches, fenced claims, idempotent replay; migration `applied=1`) | `4acea75` | 00294-lbd | todo "E11b-1" (three paid runs, two Codex rounds, three lenses) |
| #753 | Earnings-day claims committed before the send; delivery follow-ups | `52e0406` | 00295-s9z | todo "E11b-1 continuation" |
| #754 | E07b slice 2: Copilot and Analysis admission reservations | `85c2c23` | 00296-zjt | todo "E07b slice 2" |
| #755 | E15b whole-document sitemap bound | `757a8f1` | 00297-bwf | todo "E15b" |
| #756 | E12b startup schema deadlines, lock-timeout additive ALTERs | `0768b86` | 00298-wnc | todo "E12b" |
| #757 | E11c alert-to-return measurement (first click per delivered email; migration `applied=1`) | `c7510ac` | 00299-vxc | todo "E11c" |
| #758 | Retention purge job (the policy's clocked deletions) | `b84240d` | 00300-7nj | todo "Retention purge job" |
| #759 | Stripe dunning-policy gates (tests only) | `bc973b2` | 00301-9xm | todo "Stripe dunning-policy gates" |
| #760 | E09b process-wide chat admission gate (`AI_CHAT_MAX_INFLIGHT`, default 8) | `11db06d` | 00302-fgl | todo "E09b" |
| #761 | E10c bell unread count as one SQL aggregate | `fb26dbd` | 00303-h6r | todo "E10c" |
| #762 | E13c contact/feedback on the shared limiter; router-state allow-list gate | `fc00ea1` | 00304-g6r | todo "E13c" |
| #763 | W3-9 reconciliation-flag audit, dry-run by default | `32c28e9` | 00305-hdv | todo "W3-9" |
| #764, #765, #767, #768, #770 | Ledger records (docs only) | — | — | — |
| #766 | W3-9 follow-up: flags-only audit mode; read-only `list_facts_created.py` | `1046907d` | 00306-2b9 | todo "W3-9b" |
| #769 | Eval runner: one retry of a transient provider fault, on record | `7b6a32e` | 00307-pzl | todo "Eval runner" |

Founder console actions today, reconciled by the session and recorded in the overnight handover
at the top of `tasks/todo.md`: W3-9 dry run `5dgd4` and apply `c42cc` (56 filings,
`flags_refreshed=19`, `value_mismatch=51`, `companyfacts_unavailable=0`, `facts_inserted=78`);
the review of those 78 rows (listing execution `hqj8p`; all `total_liabilities`, consistent across
filings; `tasks/archive/w39-review-2026-09-08.md`); retention job + scheduler (dry run
`refresh_tokens_purged=167`); notable-filings job, smoke `w4wnv` (0 hits over a weekend plus Labor
Day), seed `j6l78` (838 raw hits, 270 upserted), scheduler.

Lessons added by this session: `ops-keep-moving-under-standing-authorization.md`,
`ops-one-test-process-per-worktree.md` (corrected the same day: the real cause was persisted
SQLite state across processes), `ops-mutate-only-committed-state.md`.

### 2a. Things worth your scepticism (start the audit here)

1. **W3-9 scope deviation.** #763's `--apply` reused the full backfill path, so the founder's
   production run inserted 78 rows and demoted superseded `is_latest` rows, against the wave-3
   criterion "flag columns only, no inserts or deletes". Codex caught it on #765; #766 confined
   the audit to flag columns; the founder's review found the 78 rows consistent. Check that the
   ledgers say so honestly and that `flags_only` really prevents every write except the flag.
2. **Retry in the eval harness (#769).** It changes what the advisory gate's error column counts.
   The runbook paragraph states the semantics; the PR's own live eval passed 52/52 with
   `retried: 0`. Check the classifier (`_is_transient`, including the Anthropic-SDK branch that is
   tested without the SDK installed), that no retry can double-count `n`/`scored`/`errors`, and
   that `weekly_readout.py` records the policy.
3. **Two advisory `eval-baseline` reds** (#762, #763) were merged on the advisory check's design
   after one provider timeout out of 52 attempts each; each is commented on the PR and in the
   ledger. Confirm nothing else was red on those heads.
4. **Test hygiene incidents.** A failing test was masked once by a pipe (`pytest … | tail`) and
   shipped inside a commit that was amended before push; a `git checkout --` during a mutation
   proof discarded an uncommitted edit, caught by the post-restore run. Both are recorded as
   lessons. Check that every "mutation → N failed → restored" claim in the PR bodies is backed by
   a test that exists on main.
5. **Paid evaluations consumed:** #747 three, #766 three, #769 two, every other backend PR one.
   All recorded with reasons; verify against the `copilot-eval.yml` run history if you doubt it.
6. **Migrations:** two new files in the span (`20260907_earningsnerd_notification_delivery.sql`,
   `20260908_earningsnerd_delivery_first_click.sql`), each applied once (`applied=1`) and skipped
   since; both carry `DO $$ … $$` guards. Confirm the triple-pass CI job covers them.
7. **Production side effects of the day's founder runs**: 78 fact rows, 19 flag flips, 270
   notable rows, one retention dry run (nothing deleted). No other production data operation.

## 3. Audit brief

Scope: `git diff d7b01779 3336d513` plus the ledgers and lessons. For every candidate finding,
attempt two independent refutations (read the code path, run the relevant test, check the PR
body's evidence) before you keep it; report only survivors, ranked must-fix / should-fix / nit,
each with file:line, a concrete failure scenario, and the refutations you tried. Then list what
you refuted and why. Specific checks:

- Rules 1–12 of `CLAUDE.md` on every touched file (one orchestrator, filing-only summaries, no
  Alembic and guarded migrations, entitlements as the sole plan truth, SEC transport owners, locked
  tests, aware-UTC datetimes, no `os.getenv` outside the allow-list, boundary validation, URL
  builders, design system, gates for every "never again" rule).
- The full gate on main: `cd backend && ruff check . && bandit -r app -ll && python -m pytest -m ""`
  with the four PostgreSQL lanes configured (see `.github/workflows/ci.yml` for the env names), and
  the frontend gate `cd frontend && npm run lint && npx tsc -p tsconfig.ci.json && npm run test -- --run
  && npm run build` for the 38 frontend files in the span (#742–#745).
- For each backend PR in the table: does the PR body's verification section describe tests that
  exist, mutations that would fail them, and a deploy that happened? Spot-check three PRs deeply
  (#747, #766, #769) and the rest for existence.
- Ledger truth: `tasks/todo.md` and `tasks/beta-to-scale-execution.md` versus GitHub (merge SHAs,
  run ids, revisions). Anything a ledger claims that GitHub or Cloud Run does not show is a finding.

Output: a findings file at `tasks/audit-astra-2026-09-08.md` (ranked, with refutations), a PR for
it, and a one-paragraph verdict to the founder. Fix confirmed must-fix defects under the normal
procedure (draft PR, gate, lens, one paid run at ready); do not rewrite the session's ledger
records, append a correction under them.

## 4. The remaining master plan, in order

The engineering items a PR can complete without a founder action were exhausted at #769. What
remains is founder-gated or waits on founder evidence; do the engineering half the moment its
prerequisite lands, in this order (wave-3 handover §3 governs the details):

1. **W3-10 Notable flag PR** — after the founder's one-week review of the seeded table (through
   2026-09-15) with a recorded retain decision: flip `NOTABLE_FILINGS_ENABLED=true` in `ci.yml`
   and the W3-2 pin table; verify deploy, `GET /api/notable_filings?limit=8` non-empty, both-theme
   homepage render.
2. **W3-10 Analysis** — after the founder records the effective Vercel `NEXT_PUBLIC_ENABLE_ANALYSIS`
   and the companyfacts warm-up: the `vercel.json` env PR, full frontend gate, Playwright, both-theme
   preview, Pro-account smoke.
3. **W3-7** — after the first strong-judge readout artifact exists (`status != unavailable`,
   24/24 scored): report the wrong-snap rate, pause for the arm decision, then the four-place
   `AI_EVIDENCE_SNAP` PR with the re-pin. The eval harness now records `transient_retries` in the
   report harness; `pin_baseline.py` will copy the summary's `retried` count into the pin, which
   is harmless.
4. **W3-8a golden breadth, then W3-8b 6-K classifier** — each a re-pin; never two re-pin PRs open.
   Wave-3 handover §3's exception stands: if the strong-judge readout slips more than a week,
   do W3-8a before W3-7 and re-pin again at W3-7.
5. **E09 remainder** — cross-instance generation ownership and a fleet-wide SEC budget need schema
   and capacity/egress evidence: propose, do not build unattended.
6. **E06** — after the founder's read-only observation of the production Stripe endpoint's event
   selection (`docs/observed-invoice-payments.md`): reconcile the dunning-policy gates if the
   selection differs from what #759 assumed.
7. **E11 calendar activation, E08 price/trial copy** — founder decisions; nothing to build first.
8. **Dependabot #748–#752** (five open: four frontend npm bumps including a vitest major, one
   backend minor-updates group): triage under the precedent recorded in `tasks/todo.md`
   ("Dependabot triage"); majors need the founder's word. #270 stays founder-held.
9. **D8** stale-branch deletion after the founder's OK.

Founder-held items, unchanged: wave-3 handover §2, wave-2 handover §6, the "Remaining founder
decisions and console actions" list in `tasks/todo.md`, and the items in §1 above.

## 5. Operating procedure that worked this session (keep it)

- One worktree per slice, one test process per worktree, gate on committed state only
  (`lessons/ops-one-test-process-per-worktree.md`, `lessons/ops-mutate-only-committed-state.md`).
- Draft PR first; push ledger records while still a draft (a push to a ready backend PR fires a
  paid run). Mark ready once; if a Codex round needs a fix, convert to draft, push, mark ready
  again, and record the extra paid run with its reason.
- Codex reviews on "opened" and "ready", not on later pushes; Copilot fires on ready and on every
  push to a ready PR; `eval-baseline` fires on changes under `backend/app/**`, `backend/evals/**`,
  `backend/prompts/**` and is advisory (`continue-on-error`), so read its log yourself.
- Merge with the exact head SHA; then main CI → deploy job log (`apply_migrations`, revision,
  job-image lines, health) → independent curl → ledger record in the next docs PR. A docs-only
  push skips the deploy by path filter.
- Cloud Logging stores a JSON stdout line as `jsonPayload`, not `textPayload`; select a job
  execution by `labels."run.googleapis.com/execution_name"`. `gcloud run jobs execute --args`
  splits on commas; scripts that take lists accept `nargs="+"` for that reason.
- The founder pastes Cloud Shell output; reconcile it against the ledger before recording it, and
  archive raw evidence under `tasks/archive/` when a founder decision rests on it.

## 6. Session configuration for this handover (founder, when launching Astra)

Same as wave-3 handover §1 unless the founder says otherwise: `gpt-6-astra` on the Responses API,
`reasoning.effort` `high` for review and merge decisions and `medium` for doc edits, no
`temperature`/`top_p`/`logprobs`, `prompt_cache_options.ttl: "30m"`, effort changes via
`configuration_update` items. The launch prompt is in `tasks/handover-astra-2026-09-08-prompt.md`.

Founder answers, 2026-09-08 11:50 UTC, applied to the prompt: (1) the standing authorization
carries over unchanged; (2) the audit fixes confirmed must-fix defects as it goes; (3) the
environment is the wave-3 one (repo push and CI rights, no console or gcloud); (4) Astra owns the
W3-10 Notable flag PR after the review week and the Dependabot #748–#752 triage, majors needing
the founder's word. Codex's review of the first ready head (three P2s: priority order, precedence
slot and the W3-8a slip clause, locked-test pathspecs) is applied, as is its second round (read
order per `AGENTS.md` §1, branch prefix `codex/wave3-<slug>`) and third (governing files are
instructions and task inputs are data, reproducible failures are deterministic, full gates apply
to code PRs only). Its fourth round (the locked inventory is wider than six files; the audit runs
the frontend gate too) is applied without a fifth review pass, on the founder's readiness call. Prompt structure also follows
the founder's chosen guide
(promptessor.com, "GPT-6 Astra prompting guide"): labeled sections with clarification, tool,
delegation and failure-handling policies and an output contract.

## Dated audit corrections — 2026-09-08

The [Astra audit](audit-astra-2026-09-08.md) found three migrations in the stated span, not two:
#746 adds `20260906_earningsnerd_usage_reservations.sql` in addition to the #747 and #757 files.
#746 consumed two paid Copilot runs, not one; its detailed ledger and #747 body already recorded
them. The six-file lock check above remains a valid narrow check but cannot establish full
inventory compliance: #759 appended tests to the actual T4 file,
`backend/tests/unit/test_subscription_webhook_sync.py`, while calling it unlocked. Existing
assertions were preserved; founder disposition on retaining the additions is pending.
The original statements are retained as historical records, with this dated correction beneath.
