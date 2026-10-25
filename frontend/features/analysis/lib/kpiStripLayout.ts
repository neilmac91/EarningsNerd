/**
 * The width of a KPI value on one line, in rem, so the strip can choose its columns from its widest value rather than
 * from a fixed breakpoint (KpiStrip). The value is `text-2xl` (1.5rem) in the figure face, whose every glyph
 * advances 0.6em, currency code, separator and drawn minus included; its marks are `text-data-xs` (0.6875rem) in the
 * same face, each 2px (`ml-0.5`) after what precedes it (DataNoteMark). tests/unit/kpi-strip-layout.spec.tsx derives
 * these from the Tailwind tokens and the classes that draw them.
 */
export const KPI_FIGURE_ADVANCE = 0.6 * 1.5
export const KPI_MARK_ADVANCE = 0.6 * 0.6875
export const KPI_MARK_GAP = 0.125

/** A value's width on one line: its figure, then its dagger and note letters, if any. */
export function kpiValueWidth(text: string, calculated: boolean, letter?: string | null): number {
  const marks = [calculated ? '†' : '', letter ?? ''].filter(Boolean)
  return [...text].length * KPI_FIGURE_ADVANCE
    + marks.reduce((width, mark) => width + KPI_MARK_GAP + [...mark].length * KPI_MARK_ADVANCE, 0)
}
