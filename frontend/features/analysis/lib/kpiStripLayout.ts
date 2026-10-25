/**
 * The width of a KPI value on one line, so the strip can choose its columns from its widest value rather than from a
 * fixed breakpoint (KpiStrip). The value is `text-2xl` (1.5rem) in the figure face, a monospace face whose glyphs share
 * one advance, currency code, separator and drawn minus included; its marks are `text-data-xs` (0.6875rem) in the same
 * face, each 2px (`ml-0.5`) after what precedes it (DataNoteMark). The face's metrics give 0.6em, but a browser that
 * draws whole pixels rounds it (14px for 14.4 at 24px, 29px for 28.8 at 48px, in Chrome 156's headless shell on
 * Linux), so KpiStrip measures both advances where it paints (--kpi-figure, --kpi-mark) and this module counts glyphs;
 * 0.6em stands until the strip has measured. tests/unit/kpi-strip-layout.spec.tsx derives these from the Tailwind
 * tokens and the classes that draw them.
 */
const FIGURE_EM = 1.5
const MARK_EM = 0.6875
export const KPI_FIGURE_ADVANCE = 0.6 * FIGURE_EM
export const KPI_MARK_ADVANCE = 0.6 * MARK_EM
export const KPI_MARK_GAP = 0.125
/** The glyphs past ASCII a value or a mark prints that Geist Mono draws at its one advance: the no-break space Intl puts
 *  after a code, the dagger, and the currency signs en-US formats print for every ISO 4217 code that Geist Mono has. Any
 *  other glyph prints in another face (₩ and ₫, E203; the narrow no-break space in "F CFA", which Chromium draws as a
 *  0.3em space) and counts 1.25em, wider than any face found to draw one: DejaVu Sans Bold's ₩ is 1.103em and Inter
 *  Black's 1.112em, ₫ peaks at 0.696em. tests/e2e/analysis-layout.spec.ts measures each in Geist Mono itself. */
export const KPI_FACE_GLYPHS = '\u00a0†€£¥₹₪₱'
/** The glyphs a value can print that Geist Mono lacks: the e2e's control, none of which may take the face's advance. */
export const KPI_MISSING_GLYPHS = '\u202f₩₫'

/** A value's glyphs on one line: its figure's and its marks' (the dagger, the note letters) that the face draws, and the
 *  rest in rem: those the face lacks at 1.25em each, and the 2px before each mark. */
export interface KpiGlyphs {
  figure: number
  mark: number
  rest: number
}

/** A glyph the face lacks, in ems of its own text. */
const MISSING_EM = 1.25
const own = (glyph: string) => (glyph >= ' ' && glyph <= '~') || KPI_FACE_GLYPHS.includes(glyph)
const tally = (text: string, em: number) => [...text].reduce(
  ([drawn, rest], glyph) => (own(glyph) ? [drawn + 1, rest] : [drawn, rest + em]), [0, 0])

export function kpiValueGlyphs(text: string, calculated: boolean, letter?: string | null): KpiGlyphs {
  const marks = [calculated ? '†' : '', letter ?? ''].filter(Boolean)
  const [figure, figureRest] = tally(text, MISSING_EM * FIGURE_EM)
  const [mark, markRest] = tally(marks.join(''), MISSING_EM * MARK_EM)
  return { figure, mark, rest: figureRest + markRest + marks.length * KPI_MARK_GAP }
}

/** A value's width on one line in rem, at the face's 0.6em advances unless given the measured ones. */
export function kpiValueWidth(text: string, calculated: boolean, letter?: string | null, figure = KPI_FIGURE_ADVANCE, mark = KPI_MARK_ADVANCE): number {
  const glyphs = kpiValueGlyphs(text, calculated, letter)
  return glyphs.figure * figure + glyphs.mark * mark + glyphs.rest
}

/** The widest of these values as a CSS length, at the advances the strip measures. A value another matches or exceeds
 *  in every term is left out, since it can never be the widest. */
export function kpiWidestCss(values: KpiGlyphs[]): string {
  const kept = values.filter((value, index) => !values.some((other, at) =>
    at !== index && other.figure >= value.figure && other.mark >= value.mark && other.rest >= value.rest
      && (other.figure > value.figure || other.mark > value.mark || other.rest > value.rest || at < index)))
  const term = ({ figure, mark, rest }: KpiGlyphs) =>
    `calc(${figure} * var(--kpi-figure) + ${mark} * var(--kpi-mark) + ${Math.ceil(rest * 10000) / 10000}rem)`
  return `max(${kept.map(term).join(', ')})`
}
