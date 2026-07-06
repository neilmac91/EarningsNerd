# CI e2e (Playwright) runs with NO backend — prod telemetry is the only real end-to-end signal

**Area:** testing · **Date:** 2026-07-06

The frontend e2e suite runs against the built frontend with no backend attached. So a flag flip or behavior change that only manifests when frontend + backend + real data interact is NOT covered by CI at all.

**Rule:** for any change gated on a flag/soak (e.g. the S1/S4 flips), prod PostHog/Sentry telemetry is the only real end-to-end validation — CI green is necessary but not sufficient. Ride such changes on a flag + observation window before removing the old path.
