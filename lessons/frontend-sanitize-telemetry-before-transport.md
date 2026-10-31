# Sanitize every telemetry transport before authentication data reaches it

Date: 2026-10-11, updated 2026-10-23   Area: frontend

**Context:** SDK event hooks do not cover every transport: PostHog flags read persisted person
properties, replay can already be compressed, and Vercel adds referrers after its event hook.

**Rule:** Strip URL queries/fragments at collection boundaries, including nested and persisted
attribution. Preserve PostHog's public ingestion token. Stop recording synchronously on credential
route entry and reject later snapshots from that document. For the initial release, the founder has
authorized disabling replay entirely: every document rejects snapshots and the provider never enables
recording. Keep the credential-route defenses for any future recording proposal. Test real SDK
capture/flags payloads and recording lifecycle, not only helper mocks.

**Evidence:** `frontend/lib/{telemetryPrivacy,posthogPrivacy,sentryConfig}.ts`,
`frontend/app/private-analytics.tsx`; gate `frontend/tests/unit/telemetryPrivacy.spec.tsx`.

The browser consent repair also tests queued/retried sends in
`frontend/tests/e2e/telemetry-network.spec.ts`; see `docs/BROWSER_CONSENT.md` for its transport limits.
