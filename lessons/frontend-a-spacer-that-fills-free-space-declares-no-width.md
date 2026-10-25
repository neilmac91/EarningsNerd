# Give a spacer that fills only free space basis-0 and a max width, never a width

Date: 2026-10-25   Area: frontend

**Context**: The metrics table hangs each figure's footnote marks in a gutter one mark wide, so a marked and
an unmarked figure end on one edge. The first version gave an unmarked figure a spacer of the gutter's width
(`w-[var(--mark-gutter)]`). In a fixed 76px period column a full nine-glyph change ("-2,448.5%") then
overflowed its cell by 3.9px and clipped: a declared width counts toward the flex line's min-content, so
the spacer took its 6.6px even where the figure needed every pixel.

**Rule**: A spacer that should take room only when room is free grows from nothing: `grow basis-0` with a
`max-w-[…]` cap, and no `w-`, `min-w-` or fixed `basis-`. Put the line's justification on the line itself
(`flex w-full justify-end`), so the content keeps its whole width and the spacer absorbs only the slack.
Prove it in a browser on the longest real value at the narrowest column; a class assertion cannot see
min-content.

**Evidence**: `frontend/features/analysis/components/DataNoteMark.tsx` (the `data-mark-gutter` spacer),
`frontend/features/analysis/components/SourceValue.tsx` and `MetricsTable.tsx` (`FIGURE_LINE`). Pinned by
`frontend/tests/unit/data-note-mark.spec.tsx` (the spacer declares no width) and, in a browser, by
`frontend/tests/e2e/analysis-layout.spec.ts` "analysis phone marks" (every glyph inside its cell at 390px).
