# A colour rule moves a value into the ink; it never deletes the value

Date: 2026-10-12   Area: frontend, brand, copy

**Context**: PR #1251 made the Separate Signals Rule app-wide (sage never colours a number, D-030).
Two sites satisfied the gate by dropping the number instead of recolouring it: the dashboard feed's
"See all N companies" link became "See all companies", and the analysis narrative's "Show the N
figures behind this" disclosure lost its count. The founder's review of 2026-10-12 sent both back:
the base had computed the watchlist count for exactly that label, the count told the reader how much
was folded, and D-030 is a rule about colour, not about what the surface says. The first repair put
the count in a secondary-ink span inside the still-sage control. The review of `cc2df56`
(2026-10-13) found that this left the feed link reading in two inks, and the check-email countdown
fading to 2.2:1 on cream, while every other count control in the PR rested in the ink.

**Rule**: When a colour, type or device rule forbids a value's current styling, change the styling
and keep the value rendered. A control that carries a count takes the count control recipe
(`frontend/DESIGN_SYSTEM.md`, beside the accent link): the whole label rests in the secondary ink as
one text run and turns sage only under the pointer, and a countdown on a control that waits rests in
the same ink at full strength. Do not satisfy the rule with a sage label around a count in its own
span: the label reads in two inks, and in an inline-flex control the span becomes its own flex item,
which breaks the hover underline. Remove a value only as a copy decision, named as a copy change in
the PR's What with its reason, never as the way to turn a gate green.

**Evidence**: PR #1251, the founder's review threads on
`frontend/features/dashboard/components/FilingFeed.tsx` (the overflow link) and
`frontend/features/analysis/components/NarrativePane.tsx` (the evidence summary), 2026-10-12, and the
commit on that PR that restores both counts; the review of `cc2df56`, whose fix moved the feed link
and the countdown on `frontend/app/check-email/page.tsx` to the count control recipe.
`frontend/tests/unit/filingFeedOverflowCount.spec.tsx` and `narrative-pane.spec.tsx` keep the two
counts rendered; `brandCopyRules.spec.ts` rule 2 keeps them out of sage, and its count-control check
(added after the review of `88f801c`, which found the recipe claiming a gate it did not have) fails a
control resting in sage that holds its count in a span of its own ink, the form `cc2df56` shipped.
