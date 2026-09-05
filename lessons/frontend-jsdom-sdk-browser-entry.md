# Resolve browser SDK imports as browser code in jsdom tests

Date: 2026-09-05   Area: frontend

**Context**: Sentry Next.js 10.73 pulls server-side bundler tooling through its Node entrypoint.
Vitest's jsdom tests then fail during import, before the application assertions run.

**Rule**: Scope any SDK browser-entry resolution to Vitest. Keep the real browser SDK and its
capture assertions available; do not suppress the failure by globally mocking the SDK or changing
production module resolution. Test the real browser entry and prove that removing the test-only
resolution reproduces the import failure.

**Evidence**: Dependabot PR #686 frontend CI job 101276604864 reported eighteen failed suites at
the orchestrion bundler's `fileURLToPath` call. The isolated Sentry candidate must carry the
reproduction, regression, mutation proof and complete frontend gates before leaving draft.
