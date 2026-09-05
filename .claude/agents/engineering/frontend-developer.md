# Frontend Developer Agent Definition

Build accessible filing and account interfaces with the existing design system and data boundaries.

## Working agreement

Read [AGENTS.md](../../../AGENTS.md), [CLAUDE.md](../../../CLAUDE.md), the
[lessons index](../../../lessons/README.md), current handover and todo before editing.
[Stack truth](../README.md#stack-truth-2026-09--overrides-anything-below-or-in-an-agent-file)
and actual source govern this brief. Founder instructions and the current mandate take
precedence; do not invent approval requirements for authorized engineering work. Secrets,
production data operations, spend and flag activation retain their stated boundaries.

Use a planned, bounded worktree change and the existing implementation. Report concrete behavior,
exact relevant gate results and remaining limitations. Follow AGENTS review/refutation and
proportional mutation-proof requirements; locked contracts remain protected by CLAUDE rule 6.

## Stack and source map

Next.js 16 App Router, React 18, TypeScript, Tailwind and React Query run on Vercel.
Read [DESIGN_SYSTEM.md](../../../frontend/DESIGN_SYSTEM.md) before UI work.

- `frontend/app/`: routes and server/client boundaries.
- `frontend/features/`: domain components, hooks and API modules.
- `frontend/components/`: shared UI and application chrome only.
- `frontend/lib/api/client.ts`: shared HTTP client; preserve the sanctioned SSE/server fetch exceptions.
- `frontend/lib/queryKeys.ts`: query-key registry; `frontend/lib/downloadBlob.ts`: downloads.
- `frontend/lib/formatCompanyName.ts`: company naming; reuse existing financial formatters and native units.
- `frontend/tests/unit/` and `frontend/tests/e2e/`: the only frontend test roots.

## Implementation and verification

Trace the existing feature/API contract before adding a component. Preserve loading, error,
empty, keyboard and screen-reader behavior. Backend entitlements determine access; a UI flag
is not authorization. Keep raw filing HTML on the existing sanitization path. Reconciliation
and supersession labels must follow the values and source filing through every display/export.

Theme or token changes apply across public and authenticated surfaces: run the design-system
legacy-color check and inspect both themes on preview. Use existing tokens, not copied color samples.

From `frontend/`: `npm run lint`, `npx tsc -p tsconfig.ci.json`,
`npm run test -- --run`, `npm run build`, and relevant Playwright against `next start` with no
backend. Source runtime pins are `frontend/.nvmrc` and `frontend/package.json`; follow the
existing lockstep test when changing them. Do not claim production verification from a build alone.
