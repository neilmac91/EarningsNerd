# Eyeball the deployed preview in both themes before declaring visual work done

Date: 2026-06-23   Area: frontend

**Context**: Every visual regression that round (brown heading, clashing gradients, invisible cards, blue info box) passed typecheck/lint/build/tests and was caught only by the user looking at the preview.

**Rule**: For any visual/theme work, "tests pass" is necessary but not sufficient. Review the deployed preview in both light and dark (or get a preview review) before declaring done.

**Evidence**: Brown heading, clashing gradients, invisible cards, blue info box — all green on typecheck/lint/build/tests, all caught only on the preview.

**Additional evidence (2026-09-06, E14a)**: Reusing the desktop HeroExample on the waitlist
passed semantic integration tests, but the 320 px preview collapsed the company-name element
to width 0 (scrollWidth 68) beside fixed badges/date. Two independent source refutations
upheld the measured issue. Responsive header grouping was corrected; the acceptance remains
actual mobile/both-theme preview, not a CSS-string assertion.

The first E14a header correction restored the issuer, but root's next 320 px screenshot
revealed card-edge clipping from the remaining layout constraints. The numeric DOM read
timed out, so this is screenshot evidence only. Mobile grid/card sizing and metric columns
were corrected separately; both mobile widths and desktop remain visual acceptance.

**Additional evidence (2026-09-28, Notable labels)**: A longer source-accurate badge passed the
full frontend suite but consumed 160 px as a sibling of the company column. The real component at
320 px and at the 640 px two-column transition collapsed that column to 30 px, overflowed its
contents, and wrapped the filing metadata into many narrow lines while the card itself reported no
overflow. A layout-equivalent first probe estimated 12–18 px of horizontal ticker/badge overlap;
the real component instead grew taller around the wrapped metadata, with a deliberately long
ticker intersecting the badge at 375 px. Moving the badge below the filing metadata removed both
forms of sibling competition in the real component. This evidence extends the existing
mobile/both-theme preview process; page-level overflow alone cannot detect internal collapse.
