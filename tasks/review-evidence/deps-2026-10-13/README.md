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
| [#1282](https://github.com/neilmac91/EarningsNerd/pull/1282) | frontend `minor-updates` group, 7 updates | Replaced by [#1304](https://github.com/neilmac91/EarningsNerd/pull/1304), identical patch-id `0db98d69…`; marked ready for Codex (no paid run on this path) | #1304 body |
| [#1283](https://github.com/neilmac91/EarningsNerd/pull/1283) | backend `minor-updates` group, 7 updates | Replaced by [#1302](https://github.com/neilmac91/EarningsNerd/pull/1302), identical patch-id `c54a3f67…`; left as a draft until the `copilot-eval` reservation is written | #1302 body |
| [#1284](https://github.com/neilmac91/EarningsNerd/pull/1284) | stripe 15.6.1 → 16.0.0 (major) | **Held, do not merge as-is**: the SDK's pinned API version `2026-09-30.endive` removes `payment_method_types` from Checkout Session create, which `app/routers/subscriptions.py:216` still sends; founder decision pending | [comment 6148612685](https://github.com/neilmac91/EarningsNerd/pull/1284#issuecomment-6148612685) |
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

## #1284 (stripe 16.0.0): held

The SDK surface is compatible (every path parameter is already positional; `stripe.error`,
`Webhook.construct_event`, `RequestsClient`, `StripeClient(..., http_client=, max_network_retries=0)`
and `to_dict()` are unchanged), every dahlia → endive change to a field this code reads is additive,
and webhook payloads follow the endpoint's version, not the SDK pin. The full suite passes on
16.0.0 (7086 passed, ruff and bandit clean, pip-audit clean), which is exactly why the break is
invisible to CI: `tests/unit/test_checkout_session.py` mocks `Session.create`. Stripe's changelog
for endive states that passing `payment_method_types` to Checkout Session create "now returns a
`400` error", and 16.0.0's `checkout.SessionCreateParams` drops the key for
`allowed_payment_method_types`. The remediation is a maintainer PR that bumps and changes line 216
in the same commit (`allowed_payment_method_types: ["card"]` keeps today's behaviour; dropping the
line hands selection to the Dashboard), with a kwargs assertion in the checkout test; high tier.

## #1285 (edgartools 5.61.1): held

See `../edgartools-5.61.1-hold-2026-10-13/README.md`: the Outlook test fails as in CI, the `%)`
cell is still dropped from the ROIC row, three prose/table breaks are still missing, and 5.61.1's
security items do not reach this deployment.

## Open follow-ups

- #1302: write the `copilot-eval` reservation (DECISIONS-09 rule), mark ready, sequence the backend
  deploy against #1281 (F22).
- #1284: founder decision between `allowed_payment_method_types: ["card"]` and dynamic payment
  methods; then the combined bump-and-fix PR for high-tier review.
- React 19 before Next 17 (react, react-dom, @types/react), as a deliberate PR.
- Dependabot's #1282 and #1283 stay open until their replacements merge, then close as superseded,
  as #1097 and #1124 did; #1284 and #1285 stay open as trackers.
