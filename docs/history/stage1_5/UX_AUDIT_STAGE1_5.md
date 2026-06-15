# UX Audit - Stage 1.5

## Scope
- `frontend/app/page.tsx`
- `frontend/app/login/page.tsx`
- `frontend/app/register/page.tsx`
- `frontend/app/company/[ticker]/page-client.tsx`
- `frontend/app/filing/[id]/page-client.tsx`
- `frontend/app/compare/page.tsx`
- `frontend/app/compare/result/page.tsx`
- `frontend/app/dashboard/page.tsx`
- `frontend/app/dashboard/watchlist/page.tsx`
- `frontend/app/pricing/page.tsx`

## Summary
The product is rich and visually compelling on the homepage and core filing flows, but several user-facing flows show inconsistent styling and navigation behaviors. Primary friction comes from inconsistent header patterns, uneven use of dark mode, and uneven error/empty/loading treatments. The experience also mixes high-polish pages with older, utilitarian layouts, which makes the product feel less cohesive.

## Findings

### P0 - Critical
- None observed.

### P1 - High
- Inconsistent header and navigation patterns across top-level pages.
  - Home uses a sticky branded header.
  - Pricing, Compare, Dashboard use a minimal header with a back link.
  - Filing pages use a full-bleed dark theme and a different header structure.
  - This inconsistency reduces perceived quality and increases user confusion.

- Mixed theming and visual density.
  - Some pages are dark-themed with rich gradients and components (`frontend/app/page.tsx`, filing pages).
  - Others remain flat, light-themed with minimal styling (`frontend/app/login/page.tsx`, `frontend/app/register/page.tsx`, older dashboard sections).
  - The overall product feels stitched together rather than unified.

### P2 - Medium
- Error and empty-state language varies widely and feels uneven.
  - Example: some pages show friendly guidance; others show raw error messages.
  - Users may not know what to do next after a failure.

- Inconsistent call-to-action patterns.
  - Some pages use filled buttons, others use links styled as text-only.
  - CTA hierarchy (primary vs secondary) varies by page.

- Mobile interaction patterns vary.
  - Some sections use large padding and card-based layouts.
  - Others collapse into dense tables or stacked rows without clear spacing rules.

### P3 - Low
- Minor typography inconsistencies (heading sizes, weights).
- Some older components use sharp radius while new sections use larger radii.

## Recommendations (Stage 1.5)
1. Standardize header/navigation pattern across all key pages.
2. Align theming tokens (colors, backgrounds, spacing, radius).
3. Normalize error/empty/loading states across top-level routes.
4. Establish consistent CTA hierarchy and spacing rules.
5. Ensure mobile layouts follow a uniform card/grid system.

## Suggested Quick Wins
- Update login/register/pricing to match the modern card aesthetic used on home.
- Add a consistent back navigation header component for secondary pages.
- Align common empty-state components to a consistent structure and tone.
