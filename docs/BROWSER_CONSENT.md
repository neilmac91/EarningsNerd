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

With the locked `posthog-js` 1.438.12, `before_send` runs when an event is captured, not when an
earlier batch or retry leaves. [posthogConsent.ts](../frontend/lib/posthogConsent.ts) therefore
guards the SDK's typed request and retry entry points. On withdrawal it drains batches, retry
queues and pending DOM-ready requests through denial guards. A request generation prevents a
late failed request from retrying after a subsequent allow. The adapter uses SDK internals;
rerun the actual transport tests and review those entry points on SDK upgrades.

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
- [telemetry-network.spec.ts](../frontend/tests/e2e/telemetry-network.spec.ts) uses the locked real
  PostHog browser bundle. Every request is fulfilled or blocked locally, including remote
  configuration. It checks queued batches, unload, offline retry, late failure, two-tab withdrawal
  and disabled replay even when fixture configuration enables it.

These tests do not prove production network configuration, processor agreements, retention or
international-transfer compliance. Check the deployed network before release; no provider
settings or production data are changed by this repair.
