# Reach an SDK's internals only through what its shipped build keeps, and test them on that build

Date: 2026-10-31 · Area: frontend / telemetry

**Context.** #1552's consent guard (`frontend/lib/posthogConsent.ts`) read posthog-js's `_send_retriable_request`,
`_retryQueue` and `_requestQueue` by name. The typings declare them, but the npm builds the app uses rename them: the
package's `module` entry, which Next bundles, and `main`. So `client._send_retriable_request.bind(client)` threw
"Cannot read properties of undefined (reading 'bind')". The provider installed the guard before `posthog.init`, so
init never ran, for visitors who allowed analytics too. Browser PostHog has most likely recorded nothing since #1552
deployed. That is unconfirmed until someone reads the project's browser events. The API's account events
(`backend/app/services/posthog_client.py`) never depended on the browser, so this bug did not touch them. The trace was a console
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

(b) **Test the code on the builds the app and the test runner load, and on no other.** That means the entry the app
bundles, read from the package's own manifest as a bundler reads it (`module`, so long as there is no `exports` or
`browser` field), and the package entry the test runner resolves (`main` under Vitest). Which other builds keep the
renamed names changes between releases: in posthog-js 1.440.0 every `no-external` build and the ES5 build keep them,
while the CDN's `array.js` and `array.full.js` rename them. A stand-in client mirrors the shipped build: it has no
member the build renames.

(c) **Fail closed, per client, and loudly.** After the failure, nothing more leaves a client the guard cannot hold
through the paths the guard wraps, and the client loads no further script. That is enforced on the client itself, in
three layers:
- its own `is_capturing` reads false, so the SDK captures nothing for it;
- its `before_send` drops any event that still arrives;
- the guard's wrappers drop every request, flags and remote configuration included, and its script loading is
  switched off: posthog-js loads its remote configuration and extensions through script tags that no wrapper sees.
It is never enforced through the SDK's consent store. Every tab shares that store, so another tab's opt-in would
revive the failed client, and an opt-out the visitor did not choose would switch healthy tabs off. The failed client
keeps that store at the visitor's choice, as every healthy tab does, so a logout's `reset()` cannot leave it cleared.
The failure is reported to Sentry as an issue, once per page. The guard is installed only where it is needed (for
PostHog, after an allow), so a broken guard cannot report from every page view. Capturing nothing is not storing
nothing: posthog-js writes an identity and session data to the client's own storage while it captures nothing, so
the app identifies an account only while analytics is allowed, through one facade (`lib/analytics.ts`).

**Gate.** Partly gated, for posthog-js.

- `frontend/tests/unit/posthogConsentGuard.spec.tsx` runs the guard on real clients from the package entry and the
  `module` build. It plants each failure the guard must survive (queues out of sight, a second queue of either kind,
  no `__request_queue`), with another tab opted in, flag requests and script loading on and a credential URL, and
  through a logout's `reset()`. It also runs the provider on real clients, before an allow and with each of its
  failure paths, and pins that an account is identified only while analytics is allowed.
- `frontend/tests/e2e/telemetry-network.spec.ts` runs the transport in Chromium on the `module` build, and serves
  none of the package's other core builds. It fails any test after which a page reported a guard failure, or that
  made a request the fixture does not answer on the ingest host or on any host but the fixture site.
- `frontend/tests/unit/posthogShippedMembers.spec.ts` reads every file under `frontend/` that names posthog-js, and
  fails on a file kind it cannot read. It fails an underscore member that the `module` build lacks, wherever such a
  file reaches it: in code, in a stand-in (an object literal, a class or a parameter property), in a JSX attribute,
  as a bare string, or in a script held in a string. It also fails a string that names another copy of the client
  (rule (b)): a core build other than the manifest's entries in any token of the string, the `no-external`
  sub-package, the compiled source, or a package subpath. It fails a manifest field a bundler would read before
  `module`, and app code that identifies an account anywhere but `lib/analytics.ts`.

Review-checked. The scan plants each of these as a stated gap:

- a name, a build path or an identify call assembled at run time, or an identify through a destructured reference;
- the `full` sub-package, or a compiled source file other than `posthog-core`, named by a bare path segment;
- code held more than two strings deep;
- a file that handles a PostHog client without naming posthog-js;
- a kept name read off the wrong object (a name passes when the build has it anywhere).

The scan does not read another SDK's internals, or stand-ins for them, at all.

**Evidence.** On posthog-js 1.438.12, 1.438.19 and 1.440.0, `dist/module.mjs` and `dist/main.js` contain no
`_send_retriable_request`, `_retryQueue` or `_requestQueue`. `dist/array.full.no-external.js` keeps them (4, 7 and 6
hits in 1.440.0). On main's tree, the scan names 13 places that read a member the build lacks: the old guard, the
transport e2e and both stand-ins. Twelve read those three names; the e2e also read the batch queue's `_queue`. The unit gate and the e2e fail on #1552's guard with its production error. Pull request #1881
records those mutation proofs and a production-build check.
