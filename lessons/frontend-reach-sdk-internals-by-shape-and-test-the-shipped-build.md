# Reach an SDK's internals by their shape, never by a private name, and test them on the build the app ships

Date: 2026-10-31 · Area: frontend / telemetry

**Context.** #1552's consent guard (`frontend/lib/posthogConsent.ts`) read posthog-js's `_send_retriable_request`,
`_retryQueue` and `_requestQueue` by name. The typings declare them, but the npm builds the app uses rename them: the
package's `module` entry, which Next bundles, and `main`. So `client._send_retriable_request.bind(client)` threw
"Cannot read properties of undefined (reading 'bind')". The provider installed the guard before `posthog.init`, so
init never ran, for visitors who allowed analytics too. Production PostHog has most likely recorded nothing since
#1552 deployed; the project's event volume confirms it. The only trace was a console line, seen on all 48 headless
page loads checked on 2026-10-31. CI stayed green for three reasons. The transport e2e
loaded `dist/array.full.no-external.js`, a CDN-style build that keeps the names. The unit tests' stand-in clients
defined `_send_retriable_request`. And `tsc` reads the typings, not the build. The withdrawal drain's
`client._retryQueue?.unload()` would have failed silently even without the throw: under `?.` a renamed member is a
no-op.

**Rule.**

(a) Never reach an SDK member by a private name (a leading underscore, or one its documentation does not list). A
shipped build may rename it while the typings keep it, and the renamed name changes with every release (posthog-js's
retry queue field was `Bu` in 1.438.12, `Ch` in 1.438.19 and `Ph` in 1.440.0). Reach it by its shape instead: the
methods and back-references every build keeps. Throw when the shape is not found exactly once.

(b) Test code that depends on an SDK on the entry the app bundles: read it from the package's own `module` field, as
the bundler does, never from a CDN or `full` build. A stand-in client mirrors the shipped build: it has no member the
build renames.

(c) A guard that fails closed also fails loudly. It reports to Sentry as an issue, once per page, not only to the
console. It runs only where it is needed (for PostHog, after an allow), so a broken guard cannot flood Sentry from
every page view.

**Gate.** Partly gated, for posthog-js. `frontend/tests/unit/posthogConsentGuard.spec.tsx` runs the guard on real
clients from the package entry (`main` under Vitest) and from the `module` build. It also runs the provider on a real
client, plus two planted failures: a client without `_send_request`, and one whose queues the guard cannot see. Both
must stay off and report once. `frontend/tests/e2e/telemetry-network.spec.ts` runs the transport in Chromium on the
`module` build, read from `package.json`. Another SDK's internals, and a stand-in for one, are review-checked.

**Evidence.** On posthog-js 1.438.12, 1.438.19 and 1.440.0, `dist/module.mjs` and `dist/main.js` have no
`_send_retriable_request`, `_retryQueue` or `_requestQueue`. `dist/array.full.no-external.js` keeps them (4, 7 and 6
hits in 1.440.0). The new unit spec and the e2e spec fail on #1552's guard and pass on the shape-based one; the pull
request records the mutation proof and a production-build check.
