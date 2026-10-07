---
name: design-docs-maintenance
description: Keep DESIGN.md, frontend/DESIGN_SYSTEM.md and the .impeccable/design.json sidecar in parity when a change touches documented tokens, typography, reusable component states or visual conventions. Load only for such a change; routine UI work does not need it.
version: 1.0.0
---

# Design-document maintenance

Moved verbatim from `CLAUDE.md` ("Design documentation") on 2026-10-07 so the root file stays
small. The rules are unchanged; `frontend/tests/unit/designSnapshotParity.spec.ts` still checks them.

[DESIGN.md](../../../../DESIGN.md) is the root visual reference: the design direction, portable
token snapshot and reusable component patterns.
[frontend/DESIGN_SYSTEM.md](../../../../frontend/DESIGN_SYSTEM.md) remains the detailed
implementation guide, including exceptions and the existing theme/token done-gate.
[.impeccable/design.json](../../../../.impeccable/design.json) supplies preview components and
metadata that extend the Markdown frontmatter; it is documentation, not a runtime theme or
component library. Token definitions in `frontend/tailwind.config.js`, `frontend/app/globals.css`,
and the actual components take precedence over stale documentation, under the conflict rules in
[AGENTS.md](../../../../AGENTS.md#2-precedence-when-documents-conflict).

When a change affects documented tokens, typography, reusable component states or visual
conventions, refresh the affected `DESIGN.md` content and sidecar together in that PR. Update
`frontend/DESIGN_SYSTEM.md` when its implementation guidance changes. Keep the snapshot's source
revision and verification limits accurate. A route-specific content change that leaves the
documented system intact does not require regenerating the snapshot. A routing-only edit to
`DESIGN.md` (links or wording outside the frontmatter and the narrative the sidecar duplicates) can
leave the sidecar unchanged. Impeccable then flags it in that working copy (the context check's
`design-sidecar-stale` and the hook/live panel's "DESIGN.md is newer than .impeccable/design.json")
because it compares file modification times, not content; both notices are expected, so do not touch
the sidecar only to reset timestamps. Content parity is checked by
`frontend/tests/unit/designSnapshotParity.spec.ts` (frontmatter vs token sources, sidecar vs
frontmatter, duplicated narrative, specimen palette roles and panel fit). For a source-based
refresh, run Impeccable's `document` command when available (`/impeccable document` in Claude Code,
`$impeccable document` in Codex), then drop the synthetic tonal ramps it adds and re-apply the
panel-fit rules to regenerated specimens (the spec names each failure); otherwise update from the
same source files. When specimens change, render them with
`frontend/scripts/impeccable-panel-harness.mjs`, which models the CSS the app actually serves. The
live panel reads the sidecar only from `<project root>/.impeccable/design.json`; boot it from the
repository root with a root `.impeccable/live/config.json` targeting `frontend/app/layout.tsx`
rather than moving or copying the sidecar. Apply the existing change-area checks in AGENTS.md and
CLAUDE.md rule 11.

## Which sections to read for which UI change

- Token, theme or typography change: both documents in full, then this skill.
- A new or changed reusable component: `frontend/DESIGN_SYSTEM.md` §1–§6 and §12, plus the
  `DESIGN.md` "Components" and "Do's and Don'ts" sections.
- Route-specific content or layout that uses existing components and tokens: `DESIGN_SYSTEM.md`
  §1–§3 and §12 only. The ESLint design rules and the vitest gates catch the rest.
