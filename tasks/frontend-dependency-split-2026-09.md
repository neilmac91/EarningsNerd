# Frontend dependency split — September 2026

Owner: Frontend Developer. Source: handover §5.4 and Dependabot PR #686.

- [ ] Land the 13 non-Sentry updates from #686, preserving the resolved Sentry SDK tree.
- [ ] Run lint, CI TypeScript, the full Vitest suite, production build and Playwright against
  `next start` with no backend; record exact output in the PR.
- [ ] Handle Sentry 10.73 separately: reproduce its server/bundler import failure under jsdom,
  resolve the browser SDK within Vitest, preserve real capture assertions, and run every gate.
- [ ] Chief engineer: adversarially review each candidate and close #686 only when superseded.

No production flags, console changes, or weakened tests belong to this split. Each candidate
stays draft until its own gate evidence exists. Founder actions: none.
