# UX Pattern Analysis - Stage 1.5

## Scope
Reviewed UX patterns across key routes and components:
- `frontend/app/`
- `frontend/components/`

## Pattern Inventory

### Loading States
- Present in most pages, but styling and placement vary.
- Some pages use centered spinners on full-screen (`dashboard`, `watchlist`).
- Filing pages use skeletons for charts/summary sections.
- Recommendation: unify loading visual style and messaging.

### Error States
- Error handling is consistent in structure (alert card + message) but not consistent in tone.
- Some pages show raw error messages, others use friendly copy.
- Some errors provide action buttons, others don't.
- Recommendation: adopt a standard error block with optional retry + help text.

### Empty States
- Watchlist page includes a rich empty state CTA.
- Company pages and compare pages have minimal empty states.
- Recommendation: standard empty-state component with headline, guidance, and CTA.

### CTA Hierarchy
- Primary CTA styles vary (rounded-full gradient on home, square buttons elsewhere).
- Secondary CTAs vary between text link and outline buttons.
- Recommendation: define CTA styles in a shared UI pattern guide and reapply.

### Layout Density
- Some pages are high-density (dashboard data sections).
- Others are airy (home, filing detail).
- Recommendation: align spacing scale and card padding across pages.

### Theme Consistency
- Dark mode is used heavily on filing pages and the homepage.
- Login/register/pricing are mostly light with minimal dark styling.
- Recommendation: align page-level backgrounds and card styles across themes.

## Quick-Win Targets
1. Standardize error + empty state blocks.
2. Standardize back-navigation headers for secondary pages.
3. Harmonize button styling and rounded corners.
4. Normalize page background + card styling in light/dark.
