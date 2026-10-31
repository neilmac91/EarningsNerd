# Keep an underlined control's marks out of its flex row: wrap them in one item, so they stay inline-blocks

Date: 2026-10-25   Area: frontend

**Context**: The analysis figure's source button carries a dotted underline, and its footnote marks are
inline-block so the underline stops at the figure. In the metrics table the button became a flex row (the
figure, the marks and the mark gutter on one baseline, justified to the cell's edge). A flex row blockifies
its children, so the marks computed `display: block`, and a parent's text decoration reaches every in-flow
flex item: the underline ran again under each mark, raised with it ("$4.1B" then a second dotted run under
"†a"). Every unit spec passed, and the class lists still said `inline-block`; it showed only when the 2×
readout image was zoomed.

**Rule**: When a control with a text decoration becomes a flex or grid container, put anything that must
not carry the decoration inside one wrapper that is the item, so it stays an atomic inline (an inline-block
inside an ordinary box), or move the decoration onto a span around the text alone, whose own text then
has to be inline, not inline-block. Prove it in a browser by reading each such element's computed
`display` (blockification shows there, not in its classes); jsdom does not blockify.

**Evidence**: `frontend/tests/e2e/analysis-layout.spec.ts` "analysis phone marks" (every mark under an
underlined control computes `inline-block`; 596 findings over four runs on the build that drew the doubled
underline). The first fix wrapped the table's marks in one flex item; a readout then showed the underline
itself parted values from their change lines, so the table's figure controls now carry none
(`frontend/features/analysis/components/SourceValue.tsx`) and the check holds the KPI value's underline,
and any later flex control that carries one.
