# CI Playwright runs against `next start` with NO backend — specs must tolerate a dead API

Date: 2026-07-06   Area: test

**Context**: The e2e job boots only the frontend; there is no API server, so every spec
implicitly asserts the UI degrades gracefully when fetches fail. This is by design (it
gates deploys cheaply) and it means e2e green says nothing about backend integration —
prod telemetry and the eval gate are the real end-to-end signals.

**Rule**: Don't "fix" e2e specs by adding backend dependencies or mock servers; write
them to tolerate dead-API states. Don't cite e2e green as evidence for a backend
behavior change — use the eval gate / prod validation for that.

**Evidence**: `.github/workflows/ci.yml` e2e job (no backend service);
`tasks/architecture-refactor-plan.md` (soak rationale: "CI e2e runs with no backend").
