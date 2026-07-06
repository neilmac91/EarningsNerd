# Never set a global element-level color that surfaces opt out of

**Area:** design-system · **Date:** 2026-06-23

A global `h1–h6 { color: var(--heading-color) }` (warm brown in light) painted brown ink on the
always-dark hero when the site was in light theme — the "brown heading" bug. Element-level global
colors override the color a heading would otherwise inherit from its (dark) surface.

**Rule:** never set a global element-level *color* that surfaces opt out of. Keep global rules to
non-conflicting properties (font-family) and give each heading an explicit theme-pair color.
