/**
 * The width of a KPI value on one line, in rem, so the strip can choose its columns from its widest value rather than
 * from a fixed breakpoint (KpiStrip). The value is `text-2xl` (1.5rem) in the figure face, whose glyphs advance 0.6em,
 * currency code, separator and drawn minus included; its marks are `text-data-xs` (0.6875rem) in the same face, each
 * 2px (`ml-0.5`) after what precedes it (DataNoteMark). tests/unit/kpi-strip-layout.spec.tsx derives these from the
 * Tailwind tokens and the classes that draw them.
 */
export const KPI_FIGURE_ADVANCE = 0.6 * 1.5
export const KPI_MARK_ADVANCE = 0.6 * 0.6875
export const KPI_MARK_GAP = 0.125
/** The glyphs past ASCII that Geist Mono draws at 0.6em and a value or a mark can print: the no-break spaces Intl puts
 *  after a code, the dagger, the minus, and the currency signs it has. It has no ₩ or ₫ (E203), which print in the
 *  monospace fallback or, where that lacks them too, the platform's own face; any glyph outside ASCII and this set
 *  counts a full em, so the budget never undercuts what paints. tests/e2e/analysis-layout.spec.ts measures each. */
export const KPI_FACE_GLYPHS = '\u00a0\u202f†−€£¥₹₪₱₽'

const glyphs = (text: string) =>
  [...text].reduce((sum, glyph) => sum + ((glyph >= ' ' && glyph <= '~') || KPI_FACE_GLYPHS.includes(glyph) ? 1 : 1 / 0.6), 0)

/** A value's width on one line: its figure, then its dagger and note letters, if any. */
export function kpiValueWidth(text: string, calculated: boolean, letter?: string | null): number {
  const marks = [calculated ? '†' : '', letter ?? ''].filter(Boolean)
  return glyphs(text) * KPI_FIGURE_ADVANCE
    + marks.reduce((width, mark) => width + KPI_MARK_GAP + glyphs(mark) * KPI_MARK_ADVANCE, 0)
}
