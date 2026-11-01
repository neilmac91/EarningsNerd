# Browser consent

This describes the application boundary, not a legal-compliance certification or verification of
production provider settings. API account events remain independent of the browser choice (D-051).
The banner, its dialog and the footer's **Cookie settings** remain the browser analytics control;
Do Not Track and Global Privacy Control do not override that choice (D-049).

## Choice and withdrawal

- [browserConsent.ts](../frontend/lib/browserConsent.ts) is the sole storage reader. Version 3
  accepts actual booleans and a valid stored schema; earlier allows require a fresh choice. Valid
  earlier refusals remain refusals. Recording is unavailable, including on a legacy recording allow.
- Saving or clearing applies immediately in memory before fallible storage. A failed write shows
  a failure message, never “saved”; the choice still applies in that document. Removal of a stale
  allow is attempted. A failed refusal/clear remains latched until an explicit choice in that
  document; delayed storage notifications cannot restore the stale allow. If all storage writes
  fail, reload/new-tab persistence cannot be promised.
- Storage events synchronize other tabs, including key removal and `localStorage.clear()`.
  An optional same-origin BroadcastChannel also shares a refusal when writing fails. Without
  shared storage or this channel, another document cannot be guaranteed to learn that refusal.
- Historical refusal/removal/clear notifications invalidate queued work even if another tab has
  already saved a later allow. This withdrawal revision is separate from the latest choice.
  An unsequenced failed-write broadcast is treated conservatively as a refusal, in either order
  with storage notifications; an explicit choice in the receiving document releases that latch.
- Event payloads never grant consent. Consumers reread the validated store, including after
  asynchronous SDK initialization. The provider tree stays mounted, preserving page drafts,
  focus and account identification; subscription lookup failure still identifies by id alone.

## Telemetry boundary

PostHog loads after analytics consent. Recording is disabled in application configuration and
`$snapshot` payloads are rejected even on otherwise safe routes. Sentry replay remains disabled;
its error diagnostics and data-scrubbing configuration are separate from browser analytics.

With the locked `posthog-js` 1.440.0, `before_send` runs when an event is captured, not when an
earlier batch or retry leaves. [posthogConsent.ts](../frontend/lib/posthogConsent.ts) therefore
guards the two places every request that carries data leaves through: `_send_request` and the
retry queue's `retriableRequest`. The scripts posthog-js loads (its remote configuration and the
extensions that configuration enables) go around both and carry no event data. The npm builds the
app ships rename some of the client's private members, among them the three the guard once read,
so it finds the retry and batch queues by their shape, never by those names. On withdrawal it
drains batches, retry queues and pending DOM-ready requests through denial guards. A request
generation prevents a late failed request from retrying after a subsequent allow. PostHog starts
only after the guard is installed.

After a guard failure, nothing more leaves that client through either wrapper, and it loads no
further script. Its own `is_capturing` reads false, so the SDK captures nothing for it. Its
`before_send` drops any event that still arrives. The guard's wrappers drop every request, flags
and remote configuration included, and its script loading is switched off, so its remote
configuration falls back to a request the wrappers drop. A request already on the wire is not
recalled, and a script loaded before the failure keeps running. posthog-js keeps its own consent in
a store that all tabs share and that `reset()` clears. A failed client keeps that store at the
visitor's choice, as every healthy tab does; its own capturing never depends on it. The failure
reaches Sentry once. The adapter uses SDK internals; rerun the actual transport tests and review
those entry points on SDK upgrades.

Capturing nothing is not storing nothing: posthog-js writes an identity to its cookie and local
storage on `identify()` and `reset()`, and session data when something reads the session, even
while capturing is off. [analytics.ts](../frontend/lib/analytics.ts) therefore identifies an
account only while analytics is allowed.

A request already dispatched cannot be recalled, and withdrawal does not erase previously
received provider data. There is no claim of historical erasure here. Native transport work
already started, including compression or browser-managed delivery, is outside this recall limit.

Vercel analytics loads only after consent. Its installed React package has no unload operation:
the script remains until a full navigation, while the component unmounts and its `beforeSend`
hook rejects new events. Tests exercise the locked React package and application send hook; they
do not certify every version of Vercel's remotely served script or recall its dispatched requests.

## Verification

- [browserConsent.spec.ts](../frontend/tests/unit/browserConsent.spec.ts): malformed schema,
  migration, failed writes/removal, current-tab notification and cross-tab events.
- Existing dialog/footer/provider tests preserve choice labels, equal button weight, focus return,
  page state and identity fallback. They also cover truthful save failure and deferred initialization.
- [telemetryPrivacy.spec.tsx](../frontend/tests/unit/telemetryPrivacy.spec.tsx) retains real-SDK
  credential sanitization and Sentry-envelope checks; replay payloads are always rejected.
- [posthogConsentGuard.spec.tsx](../frontend/tests/unit/posthogConsentGuard.spec.tsx) runs the guard
  on real clients from the package entry and the `module` build. Allowed sends leave. A withdrawn
  choice's queued and retried requests do not, nor does the retry of one already in flight. It
  plants each failure the guard must survive, with flag requests and script loading on and a
  credential URL. Nothing such a client captures or requests leaves, it loads no script, those
  calls store no credential URL, it keeps the store every tab shares at the visitor's choice
  through a logout's reset, and it reaches Sentry once. It runs the provider on real clients: off
  before an allow, on after it, off after a refusal, with each failure path planted, and an account
  identified only while analytics is allowed.
- [posthogShippedMembers.spec.ts](../frontend/tests/unit/posthogShippedMembers.spec.ts) reads every
  file under `frontend/` that names posthog-js. It fails an underscore member that code, a test
  stand-in or a script held in a string reaches and the `module` build lacks. It also fails a test
  that names another posthog-js build, by its file name or a package subpath. Its header lists what
  stays out of its reach.
- [telemetry-network.spec.ts](../frontend/tests/e2e/telemetry-network.spec.ts) runs the package's
  `module` build, the one Next bundles, in Chromium. Every request is fulfilled or blocked locally,
  including remote configuration, and the SDK's lazy-loaded extensions come from the package's own
  copies, as PostHog's CDN serves them. A request it does not answer, on the ingest host or any
  other, fails the test that made it. It checks queued batches, unload, offline retry and its
  resumption after a new allow, late failure, two-tab withdrawal and disabled replay even when
  fixture configuration enables it.

These tests do not prove production network configuration, processor agreements, retention or
international-transfer compliance. Check the deployed network before release; no provider
settings or production data are changed by this repair.
