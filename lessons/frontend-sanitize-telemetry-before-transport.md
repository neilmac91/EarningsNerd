# Sanitize every telemetry transport before authentication data reaches it

Date: 2026-10-11   Area: frontend

**Context:** SDK event hooks do not cover every transport: PostHog flags read persisted person
properties, replay can already be compressed, and Vercel adds referrers after its event hook.

**Rule:** Strip URL queries/fragments at collection boundaries, including nested and persisted
attribution. Preserve PostHog's public ingestion token. Stop recording synchronously on credential
route entry and reject later snapshots from that document; an ordinary fresh document may record
with consent. Test real SDK capture/flags payloads and recording lifecycle, not only helper mocks.

**Evidence:** `frontend/lib/{telemetryPrivacy,posthogPrivacy,sentryConfig}.ts`,
`frontend/app/private-analytics.tsx`; gate `frontend/tests/unit/telemetryPrivacy.spec.tsx`.
