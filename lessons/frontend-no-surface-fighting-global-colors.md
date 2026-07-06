# Never set a global element-level color that surfaces must opt out of

Date: 2026-06-23   Area: frontend

**Context**: A global `h1–h6 { color: var(--heading-color) }` (warm brown in light) painted brown ink on the always-dark hero when the site was in light theme — the "brown heading" bug. Element-level global colors override what a heading would inherit from its (dark) surface. Note: CLAUDE.md's Type v2 later reintroduced a `--heading-color` global that is theme-safe by construction, superseding the blanket per-heading prescription — but the underlying rule (globals must not fight the surface) is exactly why the new global had to be theme-aware, so the lesson stands.

**Rule**: Never set a global element-level color that surfaces opt out of. Keep global rules to non-conflicting properties (font-family) and give each heading an explicit theme-pair color. (Per the later Type v2 system: any heading-color global must be theme-safe by construction.)

**Evidence**: `h1–h6 { color: var(--heading-color) }` global; brown ink on the always-dark hero in light theme.
