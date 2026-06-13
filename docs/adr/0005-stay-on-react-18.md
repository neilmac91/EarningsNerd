# ADR 0005 — Stay on React 18 under Next.js 16

- **Status:** Accepted (2026-06-13)
- **Deciders:** EarningsNerd maintainers
- **Context:** audit item **M6** (React 18 ↔ Next 16 "major mismatch")

## Context

The audit flagged a potential major-version mismatch: the frontend runs **React 18**
(`react`/`react-dom` `^18.2.0`) on **Next.js 16** (`next` `16.2.9`), and Dependabot proposes
bumping React to the v19 major. The concern was that Next 16 "expects" React 19.

On inspection, **Next 16.2.9 explicitly supports React 18 in its `peerDependencies`**:

```
react:     "^18.2.0 || 19.0.0-rc-... || ^19.0.0"
react-dom: "^18.2.0 || 19.0.0-rc-... || ^19.0.0"
```

So this is **not a hard mismatch**. React 18 is a first-class, supported peer for Next 16;
Next merely *also* supports (and markets) React 19. Nothing is broken by staying on 18.

A React 19 major bump, by contrast, is a **framework-major migration** with real surface:
- React 19 API changes (e.g. ref-as-prop, removed legacy APIs, changes to `act`/test utils);
- peer realignment across the UI stack (`react-markdown`, `recharts`,
  `@testing-library/react`, `@types/react*`);
- our own components and the e2e/unit suites would need a full re-verification pass.

The payoff for this product right now is low: we use no React 19-only feature, and the
current stack builds, type-checks, lints, and passes e2e on React 18.

## Decision

**Stay on React 18** under Next.js 16 for now. Do **not** take the Dependabot React-major
bump. Keep `react`/`react-dom`/`@types/react*` pinned on the 18 line.

Revisit the React 19 upgrade as a **deliberate, scoped migration** (its own branch, gated on
`npm run build` + `tsc` + Playwright e2e + a manual smoke pass) when one of these holds:
- we want a React 19-only capability, or
- a dependency we need drops React 18 support, or
- a future Next major removes React 18 from its peer range.

## Related: `postcss` / `next` security advisories

The audit also noted `postcss`/`next` advisories whose "real" fix the audit expected in a
**Next 16.3 stable** release. As of 2026-06-13, **Next 16.3 has no stable release** — only
`16.3.0-canary.*` pre-releases exist on npm. We will not ship a canary to production.

**Decision:** remain on `next@16.2.9`; re-evaluate the bump when **16.3 (or later) ships a
stable release**, then upgrade and re-verify (build + e2e). Until then this is tracked,
not actioned.

## Consequences

**Positive**
- Avoids a high-risk, low-reward framework-major migration.
- Keeps the supported, green-CI stack stable.
- Documents *why* the Dependabot React PR is intentionally not merged, so it isn't
  reopened reflexively.

**Negative / costs**
- We forgo React 19 features and stay one major behind; the gap widens over time.
- Dependabot will keep surfacing the React-major PR; reviewers should close it with a
  pointer to this ADR rather than merging.
