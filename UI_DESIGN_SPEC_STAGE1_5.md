# UI Design Spec - Stage 1.5

## Design Goals
- Unify secondary pages with homepage brand polish.
- Establish consistent header/back navigation pattern.
- Standardize CTA hierarchy and error/empty blocks.

## Components

### Secondary Page Header
Structure:
- Left: back navigation + brand icon/wordmark
- Right: Theme toggle or primary action

Visual:
- Border bottom, subtle background blur
- Consistent padding and typography

### CTA Hierarchy
- Primary: filled button with brand gradient or primary color
- Secondary: outlined or text button
- Consistent radius and size across pages

### Error / Empty Blocks
- Card with icon, headline, guidance copy, and CTA
- Consistent spacing, radius, and background

## Target Pages
- Login, Register, Pricing, Compare, Dashboard, Watchlist

## Implementation Notes
- Use existing Tailwind tokens.
- Preserve dark mode compatibility.
