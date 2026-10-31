# Reach an SDK's internals only through what its shipped build keeps, and test them on that build

Date: 2026-10-31 · Area: frontend / telemetry

**Context.** #1552's consent guard (`frontend/lib/posthogConsent.ts`) read posthog-js's `_send_retriable_request`,
`_retryQueue` and `_requestQueue` by name. The typings declare them, but the npm builds the app uses rename them: the
package's `module` entry, which Next bundles, and `main`. So `client._send_retriable_request.bind(client)` threw
"Cannot read properties of undefined (reading 'bind')". The provider installed the guard before `posthog.init`, so
init never ran, for visitors who allowed analytics too. Browser PostHog has most likely recorded nothing since #1552
deployed. That is unconfirmed until someone reads the project's browser events. The API's account events
(`backend/app/services/posthog_client.py`) never depended on the browser and kept flowing. The trace was a console
line, seen on all 48 headless page loads checked on 2026-10-31. Sentry's console integration kept it as a log line,
which raises no issue.

CI stayed green for three reasons:

- The transport e2e loaded `dist/array.full.no-external.js`, a CDN-style build that keeps the names.
- The unit tests' stand-in clients defined `_send_retriable_request`.
- `tsc` reads the typings, not the build.

Even without the throw, the withdrawal drain's `client._retryQueue?.unload()` did nothing: under `?.`, a renamed
member is a silent no-op.

**Rule.**

(a) **Never depend on a member a shipped build renames.** The typings keep such a member, so `tsc` cannot see the
break, and the renamed name changes with every release: posthog-js's retry queue field was `Bu` in 1.438.12, `Ch` in
1.438.19 and `Ph` in 1.440.0. Reach it by its shape instead: the methods and back-references every build keeps. Throw
when the shape is not found exactly once. A private name the build does keep (posthog-js's `_send_request`,
`__request_queue`, `__loaded`, `_instance`) may be used, on two conditions: a test on the shipped build pins it, and
the code fails closed when it is missing.

(b) **Test the code on builds that rename members the way the bundled one does.** That means the entry the app
bundles, read from the package's own manifest as a bundler reads it (`module`, so long as there is no `exports` or
`browser` field), and the package entry the test runner resolves (`main` under Vitest). Never test on a CDN or `full`
build, which keeps the names. A stand-in client mirrors the shipped build: it has no member the build renames.

(c) **Fail closed, per client, and loudly.** A client the guard cannot hold sends no events for the rest of the page.
That is enforced on the client itself, through its own `before_send`. It is never enforced through the SDK's consent
store, which every tab shares: another tab's opt-in would revive the failed client, and the failed client's opt-out
would switch healthy tabs off. The failure is reported to Sentry as an issue, once per page. The guard is installed
only where it is needed (for PostHog, after an allow), so a broken guard cannot report from every page view.

**Gate.** Partly gated, for posthog-js.

- `frontend/tests/unit/posthogConsentGuard.spec.tsx` runs the guard on real clients from the package entry and the
  `module` build. It plants each failure the guard must survive (queues out of sight, a second queue of either kind,
  no `__request_queue`), with another tab opted in. It also runs the provider on real clients, before an allow and
  with each of its failure paths.
- `frontend/tests/e2e/telemetry-network.spec.ts` runs the transport in Chromium on the `module` build, and fails any
  test after which a page reported a guard failure.
- `frontend/tests/unit/posthogShippedMembers.spec.ts` fails any underscore member that code or a stand-in under
  `frontend/` reaches in a file that names posthog-js, when the `module` build lacks it. It also fails if posthog-js
  gains an `exports` or `browser` field.

Review-checked:

- a name assembled at run time, which the scan's planted gap records;
- a file that handles a PostHog client without naming posthog-js;
- another SDK's internals, and stand-ins for them.

**Evidence.** On posthog-js 1.438.12, 1.438.19 and 1.440.0, `dist/module.mjs` and `dist/main.js` contain no
`_send_retriable_request`, `_retryQueue` or `_requestQueue`. `dist/array.full.no-external.js` keeps them (4, 7 and 6
hits in 1.440.0). On main's tree, the scan names the 13 places that read them: the old guard, the transport e2e and
both stand-ins. The unit gate and the e2e fail on #1552's guard with its production error. Pull request #1881
records those mutation proofs and a production-build check.
