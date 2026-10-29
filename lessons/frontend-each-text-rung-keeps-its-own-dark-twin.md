# Twin each text rung with its own dark rung: tertiary with tertiary-dark, secondary with secondary-dark

Date: 2026-10-25   Area: frontend

**Context**: The dark secondary ink was gray-400 (#9CA3AF, APCA Lc -48.6 on the dark panel), too faint
for 12px copy, and the founder approved raising it to gray-300 (#D1D5DB, -77.3). But tertiary-dark was
gray-600 and banned as text, so 140 class strings had paired `text-text-tertiary-light` with
`dark:text-text-secondary-dark`, and the input placeholders, list markers and the prose link underline did
the same. Raising the secondary value alone would have brightened every caption, placeholder and timestamp
to body-copy ink in dark (a placeholder would have matched the typed value), erasing the hierarchy the
light theme keeps.

**Rule**: A light text class takes the dark token of its own rung. When a dark rung is unusable, fix the
token, never borrow the next rung: give it a text-safe value and re-pair. Before changing a token's value,
census its twins by the light class they sit beside (`git grep` over class strings and `@apply` blocks,
every variant prefix included) and move the crossed ones first, asserting each site.

**Evidence**: `frontend/tailwind.config.js` (`text.tertiary.dark` #9CA3AF, `text.secondary.dark` #D1D5DB);
the sweep touched 57 files plus `components/ui/Input.tsx`, `Modal.tsx`, `StreamingSummaryDisplay.tsx`,
`MonthView.tsx` and `app/globals.css`. Partly gated by `frontend/tests/unit/themePairs.spec.ts` ("keeps
tertiary and secondary on their own rungs in dark"), which reads every class list and `@apply` block the
twin rule reads; a twin that names a rung through a variable is review-checked.
