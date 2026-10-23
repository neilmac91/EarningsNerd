# Give a clip that holds an sr-only box a position, or the box escapes it and the page scrolls sideways

Date: 2026-10-15   Area: frontend

**Context**: It happened twice in one day. Merging main (#1311) into #1278 put each hero figure's XBRL
concept in its term as an sr-only span, and the term truncates (`dt.truncate`). At 390px with the browser
text doubled, the third term's span sat at its static place past the truncated "Diluted EPS" label, at
394.6px, and `/` scrolled 5px sideways: `tests/e2e/reflow-200.spec.ts` failed with "scrollWidth 395px
against clientWidth 390px". Its report said "past the edge: nothing outside a clipping box", because its
walk counted any ancestor with overflow as a clip. In #1309's admin tables, FeedbackRow's sr-only status
labels sat in a table inside an `overflow-x-auto` box, were laid out against the page outside the box's
clip, and took /admin/feedback to 1090px at 390px. Lint, typecheck and the unit suites were green both
times; only a browser measuring the page saw it.

**Rule**: Tailwind's `sr-only` is `position: absolute`, a 1px box at its static place. An overflow clip
(`truncate`, `line-clamp-*`, `overflow-hidden`, `overflow-x-auto`, any overflow other than visible) holds
an absolutely positioned box only when the clip is the box's containing block or contains it. The
containing block is the nearest ancestor with a position other than static (or a transform, filter or
contain). So when an element clips and an sr-only box, or any absolutely positioned one, renders inside
it, give the clipping element a position (`relative`), or give one to an element inside the clip that
holds the box. Then no unpositioned clip sits between the box and its containing block. Inside a nowrap,
truncated or scrolled container the box's static place can be far past the visible edge. An escaped box
then widens the document's scroll width though nothing paints there, and a phone scrolls sideways. Prove
a fix by the page's scroll width in a browser, at the width and text size where the clipped content
overflows; a class assertion proves only the class.

**Evidence**: `frontend/features/marketing/components/HeroExample.tsx` (the term's `relative`, 998e2315)
and the `/` case of `frontend/tests/e2e/reflow-200.spec.ts` at 390px and 200% text, on #1278's branch,
2026-10-15. Making the three terms relative in the live page took the scroll width from 395px to 390px.
#1344 (open, `claude/brave-bohr-hai5vi-admin-reflow`) gives the admin lists' scroll box,
`frontend/features/admin/components/TableScroll.tsx`, `relative overflow-x-auto`, and its
`frontend/tests/unit/admin-feedback-page.spec.tsx` pins that pair on the box beside a row's sr-only
label. Gate: the reflow-200 spec's page-width check on the routes it visits (/, /pricing, /waitlist,
/login, /register, the 404, /security, /privacy, /terms, /filing/3, /calendar and /search, at 390px at both
text sizes). On /search
the results list clips its rows, so that check cannot see a row's sr-only commas escape it;
`frontend/tests/unit/full-text-search.spec.tsx` pins the list's `relative overflow-hidden` classes,
which proves the classes, not the clip. Its report now walks past the
ancestors an absolutely positioned box escapes and names the box (dac23622: "past the edge: 395px span
", XBRL concept us-gaap:EarningsPerShareD""). #1344's admin spec pins its site once it lands. No static
scan reads this rule: the clip and the sr-only box can sit in different components (TableScroll clips
what FeedbackRow renders), so a scan of one element and its parent cannot see the pair. A route the e2e
spec does not visit is review-checked.
