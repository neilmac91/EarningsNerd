# Cookie choices — implementation review

Reviewed **24 October 2026**. This is a source inventory, not a separate customer notice or a statement of legal compliance. The maintained website disclosure is the [privacy page](../../frontend/app/privacy/page.tsx). Release status and deployed behaviour must be checked against the final release revision.

## Browser choices

[CookieConsent.tsx](../../frontend/components/CookieConsent.tsx) presents the choices, and [browserConsent.ts](../../frontend/lib/browserConsent.ts) reads and validates local storage under `cookie_consent`. Optional PostHog and Vercel browser analytics require an enabling choice. **Allow analytics** enables analytics; **Essential only** refuses it. Session recording is disabled, including when an older stored choice allowed recording. Version 3 re-asks for older analytics allows while preserving valid older refusals. Every new visitor sees the choices; Do Not Track does not select or change them.

The Cookie settings button in the footer reopens the shared preferences dialog; the privacy page directs users there. Cancel/Escape do not save edited choices. Saving or clearing a choice applies it immediately in the current tab, before attempting persistence. If storage fails, the interface reports the limitation rather than claiming the choice was saved; reload/new-tab persistence cannot be guaranteed. Essential storage cannot be disabled through this optional-analytics control.

Open tabs follow storage changes. Where available, a same-origin BroadcastChannel also shares a refusal when a storage write fails. Without either channel, another tab cannot be guaranteed to learn that refusal. A failed refusal remains effective in the current tab until an explicit local choice; delayed storage events cannot restore a stale allow. Historical withdrawal events invalidate queued work even if another tab has already saved a later allow.

[posthog-provider.tsx](../../frontend/app/posthog-provider.tsx) applies choices to PostHog browser capture. [posthogConsent.ts](../../frontend/lib/posthogConsent.ts) guards the locked SDK's request and retry entry points and discards its pending batches/retries after withdrawal. [posthogPrivacy.ts](../../frontend/lib/posthogPrivacy.ts) configures telemetry sanitization and rejects recording payloads. PostHog session recording and Sentry replay stay disabled.

[private-analytics.tsx](../../frontend/app/private-analytics.tsx) mounts Vercel Analytics only with analytics consent and rejects new events through its send hook after withdrawal. An already loaded Vercel script remains in the document until a full navigation. A request already dispatched cannot be recalled, and withdrawal does not erase previously received provider data. See [Browser consent](../BROWSER_CONSENT.md) for the tested SDK boundary and its limits.

## Separate processing

The browser switches do not turn off account/quota records, server-side usage/cost telemetry or security/error reporting. Do not label every analytics/diagnostic flow as consent-gated or anonymous. The privacy page distinguishes these uses.

Authentication cookies and functional storage support sign-in, session state and social sign-in. Their implementation is in [the auth router](../../backend/app/routers/auth.py) and [refresh token service](../../backend/app/services/refresh_token_service.py). Verify actual deployed names, flags, durations and storage behaviour before publishing an itemised table; do not assume every functional cookie is HttpOnly or that every provider has the same lifecycle.

## Verification and further review

Regression coverage includes malformed and older choices, Cancel, focus return, failed persistence, reopening, cross-tab withdrawal, deferred SDK initialization and actual PostHog batch/retry transport. Run the current branch checks and inspect the preview after integration; earlier checks apply only to their recorded revisions. This document changes no stored cookie choices, account data or provider settings.

Confirm applicable consent/notice duties, actual production cookies and provider retention settings before asserting a complete cookie inventory. Privacy questions go to **privacy@earningsnerd.io**. Full personal identity details, an address, an entity or jurisdiction are not added.
