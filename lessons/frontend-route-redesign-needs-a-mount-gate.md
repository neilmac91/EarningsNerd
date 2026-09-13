# A self-omitting section needs a source-level mount gate — render tests cannot see it go missing

Date: 2026-09-13   Area: frontend

**Context**: The 2026-09-10 landing revamp removed `<NotableFilings />` from `frontend/app/page.tsx`
and nothing went red. The component, `fetchNotableFilings` and `tests/unit/NotableFilings.spec.tsx`
all survived and kept passing in isolation, so every gate stayed green while the section was simply
absent from the page. `fetchNotableFilings` sat with zero callers for three days. It surfaced only
because W3-10's recorded done-criterion — "the homepage section renders in both themes after ISR" —
had become unsatisfiable, and even then the omission was deliberate and documented
(`frontend/lib/serverApi.ts`, `frontend/design/landing-redesign/RATIONALE.md:17`), so the defect was
not the removal but that nothing tied the route back to the flag decision that depended on it.

A section that returns `null` on empty data is invisible to a render test by design: absence IS its
correct behaviour whenever its flag is off or its list is empty. So no component test, e2e run
(CI Playwright has no backend, so every fetcher resolves `null`) or type check can distinguish
"correctly self-omitting" from "no longer on the page". The mount is only observable in the route
source.

**Rule**: When a data-driven section self-omits on empty, pin its mount in the route source, not in
a render test — an AST spec asserting the route renders the component and calls its fetcher
(`frontend/tests/unit/landing-sections-mounted.spec.ts`, modelled on
`pricing-server-render-guard.spec.ts`). A redesign may still drop the section; it just has to edit
the list, which makes the decision explicit instead of silent. Corollary: a route-level redesign
that drops a section must, in the same PR, either delete the component + fetcher + specs together,
or record the dormancy where the next reader will look — an orphaned fetcher with zero callers is
the smell.

**Second rule, learned in the same change**: re-mounting a dormant fetcher can silently retune the
page it joins. `/` declares no route-level `revalidate`, so Next takes the MINIMUM of its fetches;
mounting `fetchNotableFilings` at its old 900 s cut the whole homepage's ISR window from 3600 to
900. Measured, not assumed — `initialRevalidateSeconds` for `/` in `.next/prerender-manifest.json`
reads 900 at 900 and 3600 at 3600. Check that manifest before and after adding any server fetch to
a shared route.

**Evidence**: `d26289e5` (2026-09-10 landing revamp) removed the section;
`frontend/app/page.tsx` re-mount and `frontend/tests/unit/landing-sections-mounted.spec.ts` gate;
`tasks/handover-wave3-2026-09.md` W3-10 row.
