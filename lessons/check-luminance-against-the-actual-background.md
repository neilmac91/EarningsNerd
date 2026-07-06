# Verify a surface's luminance delta vs the background it sits on, not just that a token exists

**Area:** design-system · **Date:** 2026-06-23

A CTA/card used `bg-brand-weak` (#ECF2EE) as its fill on the cream page (#F4F3EE) — a ~1.02:1
surface contrast (brand-weak is actually *darker* than cream), so the card was invisible. It was a
valid token and a valid dark pair, but unreadable.

**Rule:** for surfaces, verify the **luminance delta vs the background it sits on**, not just that a
token exists. Lift cards with a *lighter* fill (`panel-light`) + a soft `shadow-e*`; brighten on
hover, never darken. `brand-weak` is an accent/tint, not a card fill.
