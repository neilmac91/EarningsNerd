# A colour rule moves a value into the ink; it never deletes the value

Date: 2026-10-12   Area: frontend, brand, copy

**Context**: PR #1251 made the Separate Signals Rule app-wide (sage never colours a number, D-030).
Two sites satisfied the gate by dropping the number instead of recolouring it: the dashboard feed's
"See all N companies" link became "See all companies", and the analysis narrative's "Show the N
figures behind this" disclosure lost its count. The founder's review of 2026-10-12 sent both back:
the base had computed the watchlist count for exactly that label, the count told the reader how much
was folded, and D-030 is a rule about colour, not about what the surface says.

**Rule**: When a colour, type or device rule forbids a value's current styling, restyle the value
and keep it rendered: a span in the secondary ink inside the sage control (`text-text-secondary-light
dark:text-text-secondary-dark`), fading with the control's disabled state where the control fades
(`group-aria-disabled:`). Remove a value only as a copy decision, named as a copy change in the PR's
What with its reason, never as the way to turn a gate green. `brandCopyRules.spec.ts` rule 2 stops at
a child with its own colour, so the wrapped count passes the gate on its own.

**Evidence**: PR #1251, the founder's review threads on
`frontend/features/dashboard/components/FilingFeed.tsx` (the overflow link) and
`frontend/features/analysis/components/NarrativePane.tsx` (the evidence summary), 2026-10-12, and the
commit on that PR that restores both counts; the resend cooldown on `frontend/app/check-email/page.tsx`
is the pattern.
