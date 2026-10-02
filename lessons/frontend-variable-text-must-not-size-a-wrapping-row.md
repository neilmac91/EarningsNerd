# Keep variable-length text from sizing a wrapping row or an implicit grid track

Date: 2026-10-02   Area: frontend

**Context**: Two phone-width defects on `/dashboard` had one cause: a string whose length depends on
data decided the size of its container. (1) The page grid (`grid gap-8 lg:grid-cols-3`) and the
FilingFeed grid (`grid gap-4 sm:grid-cols-2`) declared no columns below `lg`/`sm`, so the phone
track was an implicit `auto` track. Its minimum is the widest descendant's min-content, and a
`truncate` (nowrap) company name has a min-content equal to its full width. The document was 669px
wide at 375px. (2) `SecondaryHeader` is a `flex-wrap` row, and the per-user subtitle
("Welcome back, <name or email>") wrapped it, so the header height and the `<main>` offset varied
by name (85px to 189px at 375px). The suggested fix, `min-w-0` + `truncate`, was measured and did
not work. Flexbox breaks lines on each item's max-content size, and `min-width: 0` does not shrink
that size, so the row still wrapped (121px vs 157px). The `nowrap` from `truncate` also pushed long
names past the viewport (467–480px).

**Rule**: When data-dependent text sits in a responsive grid, give the grid an explicit phone
template (`grid-cols-1` is `minmax(0, 1fr)`), not just `sm:`/`lg:` ones. When text must not move a
layout (a greeting, a name, an email), take it out of intrinsic sizing with `[contain:inline-size]`.
Then let its ancestors `grow` with `min-w-0`, and `truncate` it. Static content alone then decides
where the row wraps. Prove it in a real browser with short, long and email-only fixtures: the
offset of what follows must be identical. A CSS-string assertion proves nothing here.

**Evidence**: `frontend/components/SecondaryHeader.tsx`, `frontend/app/dashboard/page.tsx`,
`frontend/features/dashboard/components/FilingFeed.tsx`; the guard is
`frontend/tests/e2e/dashboard-phone-layout.spec.ts`. It fails on the pre-fix code (669px; header
offsets differ) and passes after. On the design-v3 stack (#1045 skeleton), `<main>` moved 154px →
190–258px when the user query resolved; with the fix it stays at 154px in every state.
