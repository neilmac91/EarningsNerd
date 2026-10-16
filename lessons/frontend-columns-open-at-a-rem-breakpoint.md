# Open columns that hold words or a one-line control at a breakpoint in rem, so enlarged text keeps one column until they fit

Date: 2026-10-16   Area: frontend

**Context**: The calendar-search PR's rendered check found that at a 768px viewport with the browser's text
doubled, the site footer took /, /pricing, /calendar and /search to 812px. Tailwind's screens are in px, so
`md:grid-cols-[1.5fr_1fr_1fr_1fr]` opened four columns at 768px whatever the text size, and an `fr` column
never shrinks below its longest word: at 200% the Legal column ran past the edge. On the same tree the final CTA
card's `md:grid-cols-2` split the card from 780 to 880px, and its one-line "See a live example" (a Button keeps
one line above a 24rem viewport, 768px at 200%) ran past its half, taking / to 886px. Lint, typecheck and the
unit suites were green, and the reflow spec's phones never reached md. Its first crops failed as well:
Playwright's full-page capture drops CDP `Page.setFontSizes`, so after one the page reads a 16px root again
(9,539px tall at 200%, 3,020px after the capture, on /pricing at 390px) and every later box is measured at the
default size.

**Rule**: When a breakpoint opens columns whose content cannot shrink (column titles, link words, a one-line
Button, a figure), write it in rem with an arbitrary media variant, `[@media(min-width:48rem)]:` for md. A media
query's rem is the browser's text size, so it is the same 768px at the default size and 1536px under a 200% text
setting, where the columns fit. A px screen (`md:`) stays right for columns whose content wraps. Prove it in a
browser at the breakpoint's px width with the text doubled (`Page.setFontSizes`, standard 32), confirm the
setting took (the root's 32px, the rem query not matching), and take viewport captures, never full-page ones,
of the 200% state.

**Evidence**: `frontend/components/Footer.tsx`, `frontend/features/marketing/components/CtaBanner.tsx`; the
tablet pass of `frontend/tests/e2e/reflow-200.spec.ts` (768 and 834px at 200% text over its route loop): red on
main's build (812px on every route with the footer at 768px, 863px on / at 834px), green on the branch. Partly
gated: the pass covers the routes it visits; a px breakpoint on another route is review-checked.
