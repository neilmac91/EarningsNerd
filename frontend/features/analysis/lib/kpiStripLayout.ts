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
/** The glyphs past ASCII a value or a mark prints that Geist Mono draws at 0.6em: the no-break space Intl puts after a
 *  code, the dagger, and the currency signs en-US formats print for every ISO 4217 code that Geist Mono has. Any other
 *  glyph counts a full em, so the budget never undercuts what paints: ₩ and ₫ (E203), which print in another face, and
 *  the narrow no-break space in "F CFA", which Chromium draws as a 0.3em space and another engine may take from another
 *  face. tests/e2e/analysis-layout.spec.ts measures each in Geist Mono itself. */
export const KPI_FACE_GLYPHS = '\u00a0†€£¥₹₪₱'
/** The glyphs a value can print that Geist Mono lacks: the e2e's control, none of which may measure 0.6em there. */
export const KPI_MISSING_GLYPHS = '\u202f₩₫'

const glyphs = (text: string) =>
  [...text].reduce((sum, glyph) => sum + ((glyph >= ' ' && glyph <= '~') || KPI_FACE_GLYPHS.includes(glyph) ? 1 : 1 / 0.6), 0)

/** A value's width on one line: its figure, then its dagger and note letters, if any. */
export function kpiValueWidth(text: string, calculated: boolean, letter?: string | null): number {
  const marks = [calculated ? '†' : '', letter ?? ''].filter(Boolean)
  return glyphs(text) * KPI_FIGURE_ADVANCE
    + marks.reduce((width, mark) => width + KPI_MARK_GAP + glyphs(mark) * KPI_MARK_ADVANCE, 0)
}
