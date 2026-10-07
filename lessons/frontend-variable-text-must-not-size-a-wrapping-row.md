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

**Rule**: Every grid that sets its columns under a variant also sets its base track in the same
class string: `grid grid-cols-1 md:grid-cols-3`, not `grid md:grid-cols-3` (`grid-cols-1` is
`minmax(0, 1fr)`; use `grid-cols-[auto]` if a content-sized base is intended). When text must not move a
layout (a greeting, a name, an email), take it out of intrinsic sizing with `[contain:inline-size]`.
Then let its ancestors `grow` with `min-w-0`, and `truncate` it. Static content alone then decides
where the row wraps. Prove it in a real browser with short, long and email-only fixtures: the
offset of what follows must be identical. A CSS-string assertion proves nothing here.

**Evidence**: `frontend/components/SecondaryHeader.tsx`, `frontend/app/dashboard/page.tsx`,
`frontend/features/dashboard/components/FilingFeed.tsx`; the guard is
`frontend/tests/e2e/dashboard-phone-layout.spec.ts`. It fails on the pre-fix code (669px; header
offsets differ) and passes after. On the design-v3 stack (#1045 skeleton), `<main>` moved 154px →
190–258px when the user query resolved; with the fix it stays at 154px in every state.
`/dashboard/watchlist` had the same grid bug (496px at 320–390px; #1077). The sweep that followed
added `grid-cols-1` to the 20 remaining responsive grids and made the grid half of the rule a gate:
the custom ESLint rule `earningsnerd/responsive-grid-base-track` (`frontend/eslint.gridBaseTrack.mjs`,
pinned by `frontend/tests/unit/gridBaseTrackRule.spec.ts`). It tripped at exactly those 20 sites
before the fix and none after. A first draft was a `no-restricted-syntax` regex, and review found it
both too narrow and too wide. It saw one literal at a time, so it flagged `cx('grid grid-cols-1',
c && 'md:grid-cols-2')`. It missed `md:!grid-cols-3`, `group-hover/card:grid-cols-2` and
`grid-cols-none`. The rule now parses each token's variants and evaluates a whole class attribute
or `cx()` call together. A conditional branch (ternary arm, `&&`/`||`/`??` operand, `clsx` object key)
is checked with the text that always renders around it and never with a sibling branch. A later
review found the first version let `cx('grid', wide ? 'md:grid-cols-2' : 'grid-cols-1')` borrow the
other arm's base. It also skipped any literal inside a class unit that the unit did not walk (a
spread, an inline map lookup), so the gate failed open. Now a spread counts as written in place, and
text no unit reaches is checked on its own. Codex's review of the branch after its main merge found it demanded the
display's exact prefix, so it flagged `hidden md:grid sm:grid-cols-2`. It then suggested a
`md:grid-cols-1` that would override the two columns. Screens are min-width, so columns under a
smaller screen now count at every larger one. Other variants still have to match. The exact-head
review found one more fail-open shape. The arguments of any call, not just a class helper, counted as
always there, so `cx('grid', choose(wide, 'md:grid-cols-2', 'grid-cols-1'))` passed. Now only a
helper's arguments and the receiver of `.join`, `.filter(Boolean)` or `.trim` count; any other
call's inputs are checked on their own. Codex then found that a reset under a variant
(`grid grid-cols-1 sm:grid-cols-none md:grid-cols-2`) clears the tracks from `sm` up while a base sits
below it. Such a reset is now reported on its own; use `grid-cols-[auto]` for content-sized tracks.
