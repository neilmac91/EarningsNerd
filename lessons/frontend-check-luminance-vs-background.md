# Verify surface luminance against the actual background, not token validity

Date: 2026-06-23   Area: frontend

**Context**: A CTA/card used `bg-brand-weak` as its fill on the cream page — a ~1.02:1 surface contrast (brand-weak is actually darker than cream), so the card was invisible. It was a valid token and a valid dark pair, but unreadable.

**Rule**: For surfaces, verify the luminance delta vs the background it sits on, not just that a token exists. Lift cards with a lighter fill (`panel-light`) + a soft `shadow-e*`; brighten on hover, never darken. `brand-weak` is an accent/tint, not a card fill.

**Evidence**: `bg-brand-weak` (#ECF2EE) on cream (#F4F3EE) — ~1.02:1 surface contrast.
