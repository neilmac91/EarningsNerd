# Handover — September 14, 2026, dependency-currency and structural-gate continuation

Read [AGENTS](../AGENTS.md), [CLAUDE](../CLAUDE.md), the [September 13 handover](handover-astra-2026-09-13.md)
and the lessons index. This continues that checkpoint; it does not supersede it. Every hold and
doubt recorded there still stands except where this document says otherwise, and nothing here
claims the master plan or world-class quality is complete.

## 0. Handover points

The September 13 checkpoint handed over at implementation point `8667f990` (#845) with production on
`earningsnerd-backend-00342-bmf`. Main was at `79c036e5` (#849) when this session began; documentation
and Notable-remount commits between those points are not this session's work.

Main is now `272d47cca99e9304cf5df32395df77bddab2f155` (#853). Read GitHub main before resuming rather
than trusting this tip.

**Production backend is `earningsnerd-backend-00344-kj9`, image tag `812a49d`, serving 100% of traffic.**
Main CI [34777738357](https://github.com/neilmac91/EarningsNerd/actions/runs/34777738357), deploy job
103779316952, `apply_migrations: applied=0 skipped=39`. Two tagged revisions remain at 0% traffic
(`00022-nic` / `deepseek`, `00029-kev` / `ds-prod`) — unchanged by this deploy, not cleaned up.
Health was verified twice independently: the job's own probe at 19:34:35Z (`healthy`, DB 8.47 ms) and
a separate curl at 19:36:45Z (`healthy`, DB 8.02 ms). The EDGAR breaker read `closed` with
`total_requests: 0` in both, consistent with a freshly started revision.

Two later merges (#852, #853) are frontend/docs only. `deploy-backend` ran on both and its own
change-detection step skipped every deploy step, so **the backend has not moved since `812a49d`**.

## 1. Standing mandate and boundaries

Unchanged from September 13 and preserved in full. Universe-wide pregeneration still waits for the
founder's explicit world-class quality confidence; historical replay remains held separately; flags,
capacity, prices/trial/promo/registration, provider changes, destructive history/data, legal decisions,
unapproved locked-anchor changes and live jobs/email/accounts as tests remain held. DeepSeek stays.
The T4-retention and T9 duration-fixture approvals remain historical scoped exceptions.

**One boundary has been consumed.** The September 13 document recorded that "the WeasyPrint #840
question was asked once and is pending" and that major-version merge approvals remain specific. The
founder gave that specific approval in this session — *"Proceed with #840 and dependabots"* — which
covered un-drafting #840 (the paid trigger), merging it (the deploy), and taking the three prepared
frontend majors forward. That approval is spent on those four PRs. It is **not** a standing grant for
future major versions; the next one needs its own ask.

No new paid measurement rounds were run, so no new recorded reason was required. No DeepSeek spend,
no eval sweep, no assessment. The only paid CI job across the whole session was one `copilot-eval`
run on #840 (job 103777863312, `success`, 19:20:19–19:23:01Z, 2m42s).

## 2. Completed engineering and evidence

| PR | Merge | What |
| --- | --- | --- |
| #850 | `3fd6bed3` | Design-system done-gate + one-test-home gate (CLAUDE.md rule 12) |
| #851 | `d2540603` | Filing dates render as the filed calendar day, not a UTC-midnight instant |
| #840 | `812a49d3` | WeasyPrint 69.0 → 70.0; **deployed**, revision `00344-kj9` |
| #852 | `99c9a922` | vitest 5.0.0, jsdom 30.0.1, @types/jsdom 30.0.0, jest-dom 7.0.1 |
| #853 | `272d47cc` | Override-direction gate, two lessons, `tasks/todo.md` record |

#749, #750 and #751 are **closed as superseded**, each with its own reasoning comment rather than a
bare close. Dependabot did not close them; this session did, after verifying main carries all four
versions. Closing a Dependabot PR unmerged means it will not recreate that bump — acceptable here
because main already has the versions, but do not repeat the pattern where it would not.

#840 resolves Dependabot alert #284 / CVE-2026-55073 by removing the affected package rather than
dismissing the alert. The default branch reported **2 high vulnerabilities** in a push banner after
these merges, down from 3. That count is from a banner, not an enumeration — do not assume which two.

New structural gates, all in `frontend/tests/unit/`:
`designSystemDoneGate.spec.ts`, `testHomesAllowlist.spec.ts`, `filing-date-local-day.spec.tsx`
(TZ-pinned, with a control assertion that the timezone actually makes the bug observable),
`postcssOverrideLockstep.spec.ts`, `overrideDirectionGate.spec.ts`. `eslint.config.mjs` gained
`DATE_RULES` and `CALENDAR_FIELD_RULES`, appended to all three existing `no-restricted-syntax` blocks
— ESLint flat config **replaces** rather than merges that option on override, so a new block silently
disables earlier gates. That trap is warned about at `eslint.config.mjs:155-160`; respect it.
(`:81-83` is a different point — why the calendar-date selectors match descendants rather than
direct children, since a `TSAsExpression` wrapper defeated `>`. `:83-86` is not a range worth
citing at all: it straddles that note's last sentence, a blank line, and the start of a separate
KNOWN RESIDUAL comment.)

Three new lessons: `test-gates-must-be-as-wide-as-their-rule.md` (#850),
`frontend-overrides-rot-when-the-constrained-package-moves.md` and
`ops-write-down-the-second-anomaly-before-chasing-the-first.md` (#853).

Dependency state now: `weasyprint==70.0`; `vitest ^5.0.0`, `jsdom ^30.0.1`, `@types/jsdom ^30.0.0`,
`@testing-library/jest-dom ^7.0.1`, `semver ^7.8.5` (newly declared, test-only). `overrides.postcss`
is the literal `^8.5.15` — the self-referencing `"$postcss"` form had to go because npm 10.9.7 cannot
resolve a `$name` reference through vitest 5's expanded peer set and aborts the whole install.
`overrides.jsdom` was **removed**, not bumped; undici now resolves to 8.10.2.

## 2a. What the next session should doubt first

- **The override gate has never fired in anger.** It reports 0 backward findings, which is a
  measurement of today's tree, not evidence of future coverage. It was proven to fire by two committed
  fixtures and one real reintroduce-and-`npm install` mutation. Its nested-resolution path is
  exercised by exactly one real case (npm nested the reintroduced undici under `jsdom` rather than
  hoisting it). Treat broader coverage as unproven.
- **`lessons/test-vitest4-mock-error-tracking.md` may now be stale and was NOT checked.** It names
  vitest 4 three times and states that vitest 4 re-reports a handled error through a `vi.fn`-mocked
  module. The repo is on vitest 5. All 640 tests pass, but that lesson is preventative — no test
  currently exercises the pattern — so passing proves nothing about it. Resolving it needs a
  deliberate experiment, not a read. Until then the lesson's applicability is unknown.
- **No production PDF was generated after the WeasyPrint deploy.** #840's evidence is its author's
  fixture comparison plus CI export controls (28 passed, including real PDF bytes and
  portrait/landscape), and a rebased CI run against current backend (3222 passed / 39 skipped / 2
  deselected). The revision is healthy and serving; that is not the same as a verified production
  export. If PDF export matters before the next release, exercise it.
- **No production frontend smoke followed the test-stack majors.** The 634 pre-existing tests passed
  unchanged on the new stack with no spec edits, Playwright ran in CI against `next start` with no
  backend, and Vercel reported Ready. Nothing beyond that was checked by hand.
- **`engines.node` is looser than the truth.** It is `"22.x"`; jsdom 30's real floor is `^22.22.2`.
  `.nvmrc` and every CI `node-version` are on 22.23.2 so nothing is broken, but a contributor on
  22.10 would now get a cryptic failure. It was left alone deliberately: `nodeVersionLockstep.spec.ts`
  pins that exact string, and narrowing it changes that gate's contract.
- **The 6 dev-only high-severity npm findings under `@lhci/utils` are unchanged**, before and after
  the majors — measured with `npm audit --package-lock-only`, 0 in production dependencies either way.
  `npm audit fix --force` wants a breaking Lighthouse-CI major. Those three majors were **version
  currency, not a security fix**; an earlier claim in this session that they closed open alerts was
  wrong and is corrected in #852's body.
- **Frontend unit suite runtime is now ~73 s**, with vitest reporting jsdom created 112 times and 36%
  of tracked time in environment setup. It suggests `pool: 'vmThreads'` or `isolate: false`. Not
  acted on — an isolation change needs its own evaluation, not a drive-by.

## 3. Verification discipline

Unchanged from September 13 in substance. Deltas worth carrying:

Proofs ran on committed state; #853's real mutation was performed after its commit and the tree
restored from HEAD with a reinstall, verified back to undici 8.10.2 with `overrides.jsdom` absent.

The CI spend model was established empirically rather than from config alone, and matters for every
future draft decision: `eval-baseline` fires on `backend/app|backend/evals|backend/prompts` with **no**
draft exclusion; `copilot-eval` fires on `backend/**` **AND** `!draft`, so **un-drafting a
backend-touching PR is the paid trigger**; `deploy-backend` fires on any `^backend/` diff pushed to
main. #852 and #853 un-drafted with zero spend precisely because they touch no `backend/` path —
confirmed by check-run count, not assumed.

A stale-green CI run is a real failure mode: #840's branch was 10 commits behind a backend that had
moved 20+ files, and its original green run proved nothing about current main. It was updated via
GitHub's update-branch (a merge commit, not a rebase — never rewrite history on someone else's
branch) and re-run before merge.

## 4. Remaining master plan, in governing order

Unchanged from September 13 except the Dependencies row.

| Item | What remains |
| --- | --- |
| W3-10 Notable | Retain decision after review week through September 15, then owned flag PR. As of September 14 the review week has **not** closed, so the decision is not yet due; it falls due once September 15 passes. Provisioning/seed already done; do not rerun. |
| W3-10 Analysis | Effective Vercel flag true already observed. Warm-up cohort/count/error evidence and actual Pro frontend acceptance remain. |
| W3-7 | September 7 weekly artifact still unavailable, 0/24. Blocked on the founder's `ANTHROPIC_API_KEY` and a `data-quality-weekly.yml` dispatch. |
| W3-8a then 8b | Unpaid breadth/classifier/scorer preparation exists. Missing REIT/utility/insurer/additional small caps and 6-K coverage; BRK.B unverified. Never two re-pin PRs. |
| E09 | Finish read-only caller/job/scheduler/DB/provider/SEC inventory when consoles work. No fleet build yet. |
| E06 | Natural delivery/signature/application attribution evidence still needed; no replay or test payment. |
| **Dependencies** | **748/749/750/751/752 and #840 all resolved this session.** #270 remains held. Remaining, unowned: the 6 dev-only `@lhci/utils` findings (breaking Lighthouse-CI major), and `engines.node` vs jsdom 30's real floor. |
| D8 | Exact two stale branches remain held for destructive approval. |

## 5. Founder actions still pending

Enumerated for the founder in this session and still outstanding:
`ANTHROPIC_API_KEY` plus a `data-quality-weekly.yml` dispatch (blocks W3-7, W3-8a, W3-8b); the Notable
retain/kill decision, which falls due after the review week closes on September 15; Vercel `NEXT_PUBLIC_ENABLE_ANALYSIS` and the companyfacts
warm-up; a `RESEND_WEBHOOK_SECRET` console check; the "Allow GitHub Actions to create and approve pull
requests" repository setting; `INTERNAL_JOB_TOKEN` for the deployer service account; the W6
`DEEPSEEK_API_KEY` rotation; and D8 stale-branch deletion approval.

Added September 14, and **not a recommendation** — a decision to make, with a trap named.

`lessons/ops-a-review-you-triggered-is-a-review-you-wait-for.md` has no machine enforcement. The
obvious candidate is branch protection on `main` requiring a pull-request review before merge, with
bypass disabled and administrators included (without that qualifier it constrains nobody, since
merges here run as the administrator).

**Do not enable it as stated.** Verified against the API: this repository has exactly one
collaborator, `neilmac91`, role admin. GitHub does not let a pull-request author approve their own
pull request, there is no second account, and Codex comments are not approving reviews. Enabling
required approval with administrator bypass disabled would block every merge until the protection
was manually weakened again. Provisioning an independent eligible approver is a prerequisite, not a
detail, and is itself a founder decision.

The alternative is a required status check on the current head that passes on either an observable
review for that head or an explicitly recorded override with a reason. That is buildable and does
not deadlock during a review-service outage, because the override branch stays available — and it
mechanically enforces what the rule actually says, which is "wait, or write down why you did not".
It is not built here. Building it, and any branch-protection change, are founder decisions.

## 6. Next practical actions

Read GitHub main and open PR state first. #805 remains open, in draft, **held** — its reserved `e`
prompt never shipped, only its first paid assessment round has run, and it still needs a coherent
correction and review decision. Do not revive it or launch a second assessment.

The Notable retain/kill decision is the nearest dated item but is not yet due — the review week runs
through September 15. Do not force it early. Of the technical gaps above, the vitest 4 lesson and a
production PDF exercise are the two cheapest to close and the two most likely to be quietly wrong,
and neither waits on a date. No background execution is implied by this checkpoint, and no quality or universe hold
has moved.
