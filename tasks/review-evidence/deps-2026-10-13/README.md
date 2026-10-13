# Dependabot queue, 13 October 2026: dispositions for #1282–#1285

Scope: the four `fix(deps)` pull requests Dependabot opened on 12 October 2026 (22:57–22:59 UTC),
all on base `3da1c52`. Every Dependabot head fails `review-gate`, because Codex reviews a maintainer
pull request when it is marked ready and never a Dependabot one, and the three backend heads also
fail `copilot-eval`, because Dependabot-triggered runs get no Actions secrets
(`tasks/decisions-2026-10-09-design-followups.md`, decision D). The dispositions follow the
maintainer-replacement precedent (#1116 for #1097, #1127 for #1124, #1119 for #1096) and the two
standing holds (issue #1063 for edgartools; dependency majors are founder-held).

| PR | Bump | Disposition | Record |
| --- | --- | --- | --- |
| [#1282](https://github.com/neilmac91/EarningsNerd/pull/1282) | frontend `minor-updates` group, 7 updates | Replaced by [#1304](https://github.com/neilmac91/EarningsNerd/pull/1304), identical patch-id `0db98d69…`; merged as `95ac033` (16:13 UTC); #1282 closed as superseded | #1304 body; release record below |
| [#1283](https://github.com/neilmac91/EarningsNerd/pull/1283) | backend `minor-updates` group, 7 updates | Replaced by [#1302](https://github.com/neilmac91/EarningsNerd/pull/1302), identical patch-id `c54a3f67…`; marked ready under the founder's merge instruction (paid `copilot-eval` draw, green); merged as `6113751` (16:18 UTC); #1283 closed as superseded | #1302 body; release record below |
| [#1284](https://github.com/neilmac91/EarningsNerd/pull/1284) | stripe 15.6.1 → 16.0.0 (major) | Replaced by [#1305](https://github.com/neilmac91/EarningsNerd/pull/1305): the same commit (identical patch-id `3489c8e5…`) plus the one change the SDK forces, `allowed_payment_method_types: ["card"]` in `app/routers/subscriptions.py`, because the SDK's pinned API version `2026-09-30.endive` removes `payment_method_types` from Checkout Session create; high tier, 0 blockers; merged as `{{MERGE1305}}`; #1284 closed as superseded | #1305 body; [comment 6148612685](https://github.com/neilmac91/EarningsNerd/pull/1284#issuecomment-6148612685); release record below |
| [#1285](https://github.com/neilmac91/EarningsNerd/pull/1285) | edgartools 5.58.0 → 5.61.1 | **Held** under issue #1063: both 5.59.1 regressions persist on the Ford fixture | [`../edgartools-5.61.1-hold-2026-10-13/`](../edgartools-5.61.1-hold-2026-10-13/README.md), [comment 6148225509](https://github.com/neilmac91/EarningsNerd/pull/1285#issuecomment-6148225509) |

## Method

- **Environments.** One Python 3.11.17 environment per lock (main, #1283, #1284, #1285), each
  installed from that lock's `requirements.txt` plus `requirements-dev.txt`. Node 22.23.2 and npm
  10.9.8 for the frontend, matching `frontend/.nvmrc` and CI.
- **Patch identity.** For each replacement, `git diff-tree -p <sha> | git patch-id --stable` is
  equal for Dependabot's commit and the `cherry-pick -x` onto main `dc2d2d4`, so each replacement
  carries exactly Dependabot's change.
- **Lock reproduction** (pip 26.2.1, pip-tools 7.6.1, as in `../deps-minor-2026-10-07/`): a
  no-upgrade compile seeded from the PR's lock, and a compile seeded from main's lock with
  `--upgrade-package` for the bumped pins only. Both reproduce #1283's and #1284's
  `requirements.txt` byte for byte.
- **Independent dependency analysis**, one Opus lens per PR: release notes for every version in each
  range, upstream wheel or tarball diffs, and a grep of this repository's call sites. Findings are
  recorded in the replacement bodies and in the hold comments.
- **Gates** ran on each head's tree with provider keys unset and no PostgreSQL service, as in CI.

## #1282 → #1304 (frontend)

Gate on Node 22.23.2: `npm ci` ok; `npm run lint` exit 0; `npx tsc -p tsconfig.ci.json` exit 0;
`npm run build` exit 0 ("Next.js 16.4.0 (Turbopack)", compiled successfully); vitest 192 files, 2036/2036 passed in 353.9 s.
A first vitest pass under two concurrent pytest suites on the same four cores had 18 timeouts at
the 5-second default, all in test setup, none a failed assertion; the clean rerun is the figure
above. `npm install --package-lock-only` drift is the class main already shows: 111 lines, all
`dev: true` additions and `libc` field removals on the sharp platform packages, no version change.

Analysis: 0 blockers, 0 should-fix, 2 nits. Next 16.4.0's Turbopack, image, caching, route-matching
and proxy changes touch nothing this repository relies on (the one `next/image` is `unoptimized`;
no parallel, intercepting or catch-all routes; ISR on Vercel). Sentry 11.5/11.6 keep the same
default integrations, sampling and Next 16 hooks; on Vercel the Node runtime now holds the function
up to two seconds after the response to flush. PostHog 1.436–1.438 keep the same autocapture,
recording, consent and bootstrap behaviour; every new capture is opt-in; the real-transport e2e
covers the flags refactor. Playwright 1.64's breaking changes (device `screen`, JSX in test files,
hidden iframes) touch nothing in `tests/e2e`. The nits: (1) 16.4.0 adds a build-time deprecation,
"React 18 support is deprecated in Next.js 16 and will be removed in Next.js 17" (absent from the
16.3.8 package, present in 16.4.0's `server/config.js`), so react, react-dom and @types/react move
to 19 before Next 17; (2) 16.4.0 adds `experimental.agentUpgrade` with default `'security'`
(`lib/upgrade/` exists only in 16.4.0): under a detected coding agent, `next build` consults the
npm advisory API and can fail with `SecurityFatalError` when the installed Next is affected; CI and
Vercel return before any network call. Turning it off is a `next.config.js` change, high tier,
the founder's call.

## #1283 → #1302 (backend)

Gate on #1283's lock: `ruff check .` (0.17.0) "All checks passed!"; `bandit -r app -ll` 0 medium,
0 high; `python -m pytest` 7086 passed, 39 skipped; `uv pip check` 122 packages compatible;
`pip-audit -r requirements.txt` no known vulnerabilities; `requirements-eval.txt` resolves.

Analysis: 0 blockers, 0 should-fix, 1 nit (json-repair 0.64.0 inserts a missing opening `{` when
that one insertion makes the input valid JSON; a strictly better recovery on the AI-output path, so
the advisory `eval-baseline` artifact on the head is worth a glance). FastAPI 0.143.0's only
functional change is that OTel auto-configuration is now opt-in (the repo's telemetry probe reports
`FASTAPI_TELEMETRY_INERT 0.143.0`); pydantic 2.14.0 serializes `NormalizedFact` identically and
pydantic-settings 2.15.0 tolerates the `model_config` non-mutation; openai 3.28.0's client,
streaming and exception modules are byte-identical to 3.24.0; posthog 7.67.0's `capture` surface is
unchanged; ruff 0.17.0 changes nothing in E4/E7/E9 and the effective rule list is identical.

## #1284 → #1305 (stripe 16.0.0)

The SDK surface is compatible (every path parameter is already positional; `stripe.error`,
`Webhook.construct_event`, `RequestsClient`, `StripeClient(..., http_client=, max_network_retries=0)`
and `to_dict()` are unchanged), every dahlia → endive change to a field this code reads is additive,
and webhook payloads follow the endpoint's version, not the SDK pin. The full suite passes on
16.0.0 with the old key still in place, which is exactly why the break is invisible to CI:
`tests/unit/test_checkout_session.py` mocks `Session.create`. Stripe's changelog for endive states
that passing `payment_method_types` to Checkout Session create "now returns a `400` error", and
16.0.0's `checkout.SessionCreateParams` drops the key for `allowed_payment_method_types`.

The remediation is #1305, under the founder's instruction to resolve what is not ready: the bump
and the fix in one squash commit, because neither half can precede the other (stripe 15 on dahlia
answers the new key with `parameter_unknown`; stripe 16 on endive answers the old key with 400).
Card-only is kept: `allowed_payment_method_types: ["card"]` filters the account's Dashboard
payment-method configuration, which was read before the PR opened (`GET
/v1/payment_method_configurations`, live, read-only: card available and on). The gate moved into
the checkout test helper every cohort test goes through: the removed key is absent, the new key is
`["card"]`, and every key sent is one the installed SDK declares for the call, so the next
endive-style removal fails in the suite. Mutation proofs on the committed head: old key restored,
11 failed / 9 passed; an undeclared key added, 11 failed / 9 passed; restored, 20 passed. Gate on
`faff471` under a fresh 3.11.17 environment from the PR's lock: ruff clean, bandit 0 medium /
0 high, 7086 passed / 39 skipped, `pip check` clean. Review: three Opus lenses, 0 blockers, three
should-fixes (the Dashboard read, the body's rollback and post-deploy items, the PR head), two Opus
refuters per should-fix (the Dashboard check stands twice; the coupled-rollback sentence stands once
and is refuted once as redundant under squash merges and revision rollback; the post-deploy
Checkout check stands); nits applied. Dynamic payment methods (dropping the parameter) stay a
product decision for the founder.

## #1285 (edgartools 5.61.1): held

See `../edgartools-5.61.1-hold-2026-10-13/README.md`: the Outlook test fails as in CI, the `%)`
cell is still dropped from the ROIC row, three prose/table breaks are still missing, and 5.61.1's
security items do not reach this deployment.

## Release record

- 16:13 UTC: #1304 merged as `95ac033` (frontend group). Vercel served the new bundle: the
  production chunk carries posthog-js `LIB_VERSION="1.438.7"` (curl readback); no backend deploy.
- 16:13 UTC: #1300 merged as `02411fb` (this directory and the edgartools hold; records only).
- 16:18 UTC: #1302 merged as `6113751` (backend group). `deploy-backend` [job 115418160027](https://github.com/neilmac91/EarningsNerd/actions/runs/38429472853/job/115418160027)
  succeeded at 16:45 UTC, `apply_migrations: applied=0 skipped=43`, revisions `earningsnerd-backend-00504-flk`
  and `earningsnerd-task-worker-00054-pjv` at 100%, `/health/detailed` healthy in the job and on a readback at
  16:46 UTC; its `copilot-eval` draw passed 18/18 (36 calls, estimated USD 0.006607).
- #1305 merged as `{{MERGE1305}}` (stripe 16 + checkout fix). `deploy-backend`: {{DEPLOY1305}}
- Paid `copilot-eval` draws on #1302 and #1305 ran under the founder's merge instruction without a
  prior reservation line; {{COST}}. The private ledger is the chief's to settle (todo F23).
- Dependabot #1282, #1283 and #1284 closed as superseded with a pointer to each replacement; #1285
  stays open as the edgartools tracker under #1063.

## Open follow-ups

- Founder, after #1305's deploy (F23): open the monthly and the yearly Checkout preview as the free
  test account (user id 9) and confirm a Stripe page with a card form, unsubmitted; check the account
  API version and the webhook endpoint version in Stripe Workbench against `2026-09-30.endive`;
  decide later whether to hand payment-method selection to the Dashboard.
- `.claude/skills/payments/stripe-best-practices/SKILL.md:83` still teaches `payment_method_types`
  for `setupIntents.create`; v16 no longer declares it on SetupIntent or PaymentIntent create (E22).
- React 19 before Next 17 (react, react-dom, @types/react), as a deliberate PR (E21).
- edgartools: #1285 stays held under #1063 until the Outlook and table-seam regressions are fixed
  upstream.
