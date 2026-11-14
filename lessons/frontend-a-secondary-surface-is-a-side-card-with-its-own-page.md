# A feature for a subset of readers enters a page as a side card that links to its own page, never as a section above the page's subject

Date: 2026-11-14   Area: frontend

**Context**: Insider (Form 4) activity shipped for beta accounts as a full-width section at the top of
the company page: a window control, a signal, three tiles and a table of trades, above the filings
(ADR 0009, steps 3 and 4). The founder saw it on production the same day: "the placement of the
'Insider activity' section overpowers the company filing pages. most of my users will be primarily
interested in the quarterly and annual filings, whereas the 'insider activity' will be interesting to a
smaller subset of users, so i don't want to distract from this", and asked for "a separate tab and/or
module on the company page (such as the 'Compare periods' module)". The section had been placed where
the old, switched-off panel was mounted, and no step of the design asked what the page is for.

**Rule**: A page has one subject (the company page: its filings; the filing page: the summary). Before
mounting a new surface on it, say who reads the new surface. When it serves a subset of the page's
readers:

1. it enters as a card in the page's side column, to the recipe of the cards already there (Compare
   periods: `frontend/DESIGN_SYSTEM.md` §4), after the page's subject in the DOM, so on a phone it
   follows the subject;
2. the card says its answer in a few lines and links to a page of its own, which holds the controls,
   the table and the detail;
3. the card mounts only when it has something to show, so it never opens an empty column or appears
   and goes;
4. nothing of the surface sits above the page's subject.

A top-level entry (a header link, a page that spans companies) is a separate decision the founder
makes; do not add one with the card.

**Evidence**: `frontend/app/company/[ticker]/page-client.tsx` (the side column),
`frontend/features/insiders/components/InsiderActivityCard.tsx`,
`frontend/app/company/[ticker]/insiders/` (the page). Gates:
`frontend/tests/unit/company-insiders-placement.spec.tsx` (the filings are the first thing in the
company page's main region, with no insider table or window control on it; the card after Compare
periods; no card or column for a reader with nothing to see) and
`frontend/tests/e2e/insider-activity-panel.spec.ts` (the card beside the filings from 64rem and under
them below, in a browser). They hold insider activity; the rule for the next such surface is this
file's.
