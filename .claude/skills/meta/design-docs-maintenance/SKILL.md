---
name: design-docs-maintenance
description: Open for any UI change. Which parts of DESIGN.md and frontend/DESIGN_SYSTEM.md it reads (§4's recipes by what the change touches), and how to keep both documents and the .impeccable/design.json sidecar in parity when a change touches documented tokens, typography, reusable component states or visual conventions.
version: 1.1.0
---

# Design-document maintenance

The parity procedure below was moved verbatim from `CLAUDE.md` ("Design documentation") on
2026-10-07 so the root file stays small; `frontend/tests/unit/designSnapshotParity.spec.ts` still
checks it. "Which sections to read" is maintained here; `frontend/tests/unit/designRecipeRoute.spec.ts`
checks its recipe names against §4.

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

A change of more than one kind below takes the widest reading. Any of them adds
`DESIGN_SYSTEM.md` §7–§11 for a marketing, theme, exemption, chart or motion change.

- Token, theme or typography change, or a rule that spans components (a brand sweep): both
  documents in full, then this skill.
- A new or changed reusable component: `frontend/DESIGN_SYSTEM.md` §1–§6 and §12, plus `DESIGN.md`
  from "Overview" on.
- Route-specific content or layout built from existing components and tokens, and nothing more:
  `DESIGN_SYSTEM.md` §1–§3, §5, §6 and §12, `DESIGN.md` from "Overview" on, and
  `DESIGN_SYSTEM.md` §4 by recipe; this is rule 11's reading for this kind of change. §4 is a
  catalog: some rules, then one fenced block of recipes named in its left column, then a short
  list. Read:
  - the rules before the recipe block and the list after it;
  - the shared recipes, whose rules a change can break without touching their component: Primary
    button, Secondary button, Wrapping button, Button size, Link as button, Accent text/link,
    Count control, Focus ring, Card / panel, Delta text, Data table hover, Solid chip, Status chip,
    Inline notice, Semantic card, Index list, Stacking and Metric cards;
  - the recipe of each existing component or surface the change uses or edits, which is the only
    way these recipes are read: Analysis evidence, Analysis periods, Analysis reading, Analysis
    reflow, Callout, Chat composer, Checkbox, Data note mark, Data notes strip, Ghost button, Hero
    example, Input, Password field, Provenance chip, Steady loading, Toast and Trust strip;
  - the triggered recipes, for what the change adds or changes:
    - a keyboard shortcut: Source pane, Wording changes and Search field (the filing page binds
      ⌘K and "/", its wording review list j, k, 1, 2 and the arrows; company search binds "/"
      and ⌘K);
    - a menu, dropdown, tooltip or explainer (anything anchored to a control that closes on
      Escape or an outside press, other than a field's list of suggestions): Popover;
    - a field with a list of suggestions or results (a combobox, as CompanySearch and
      WatchlistAddSearch are): Search field and Search option;
    - a control that removes itself, or a region that hides, while it may hold focus (a dismiss,
      a "Show all", an edit swap), for the focus hand-off: Source pane and Popover;
    - anything raised on the calendar page (a toast, a menu, a popover): Dialog and Popover;
    - a pressed toggle, a set of options of which one is chosen, or a tab list: Segmented ctrl,
      Wording changes, Company identity and Source pane;
    - a "summary ready" label: Company identity;
    - a filing's period, form-and-date line or verification count outside the filing page:
      Filing identity;
    - a change figure, a direction glyph (▲/▼), a risk-wording count or review progress outside
      the filing page: Section ledger, Compare periods and Wording changes;
    - a heading or quote drawn from a filing excerpt: Evidence rows;
    - a new state or sticky chrome on the filing page: Section ledger and Source pane;
    - a scroll box on either axis: Filing reader, Analysis table and Admin pages (a scripted
      scroll is a motion change: §11 too);
    - a filter, window or sort that changes how many items a list shows: Analysis table;
    - Copilot answer rendering (CopilotMessage, the Ask rail): Ask answer;
    - figure tiles outside /analysis: Analysis KPI.

  The ESLint design rules and the vitest gates catch the mechanical slips
  (`earningsnerd/direction-text-tokens` holds the 700-level clause for the direction text it
  reaches); the surface clause is checked in review.

A change that adds or edits a §4 recipe checks whether one of its rules can bind a change that
never touches its component. If one can, move that rule into the rules before §4's recipe block,
or name the recipe in the shared recipes or the triggered recipes above, in the same PR; if none
can, a new recipe joins the list of those read only through their component.
`frontend/tests/unit/designRecipeRoute.spec.ts` fails until every §4 recipe is in exactly one of
the three lists and every name in them is a §4 recipe, so a new or renamed recipe cannot go
unclassified; whether a rule binds other changes stays this check's judgment, not the spec's.
