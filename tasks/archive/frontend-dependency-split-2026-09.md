# Frontend dependency split — September 2026

Owner: Frontend Developer. Source: handover §5.4 and Dependabot PR #686.

- [x] Implement the 13 non-Sentry updates from #686, preserving the resolved Sentry SDK tree.
- [x] Run lint, CI TypeScript, the full Vitest suite, production build and Playwright against
  `next start` with no backend; record exact output in the PR.
- [ ] Handle Sentry 10.73 separately: reproduce its server/bundler import failure under jsdom,
  resolve the browser SDK within Vitest, preserve real capture assertions, and run every gate.
- [ ] Chief engineer: adversarially review each candidate and close #686 only when superseded.

No production flags, console changes, or weakened tests belong to this split. Each candidate
stays draft until its own gate evidence exists. Founder actions: none.

Non-Sentry candidate #694: clean Node 22.23.2 installation, lint and CI TypeScript pass;
Vitest 93 files / 474 tests pass; production build passes; Playwright against `next start`
without a backend passes 21 tests with 3 existing skips. Every `@sentry/*` package entry remains identical to main. Review identified unrelated
OpenTelemetry, import-in-the-middle and cjs-module-lexer lock churn; those transitive entries
were restored from main before the final gate. Separate Sentry candidate: #695.
