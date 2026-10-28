/**
 * The width of a KPI value on one line, so the strip can choose its columns from its widest value rather than from a
 * fixed breakpoint (KpiStrip). The value is `text-2xl` (1.5rem) in the figure face, a monospace face whose glyphs share
 * one advance, currency code, separator and drawn minus included. Its mark, the letter a figure carries only where its
 * note questions the number (D-061; no figure carries a dagger), is `text-data-xs` (0.6875rem) in the same face, 2px
 * (`ml-0.5`) after the figure (DataNoteMark). The face's metrics give 0.6em, but a browser that
 * draws whole pixels rounds it (14px for 14.4 at 24px, 29px for 28.8 at 48px, in Chrome 156's headless shell on
 * Linux), so KpiStrip measures both advances where it paints (--kpi-figure, --kpi-mark) and this module counts glyphs;
 * 0.6em stands until the strip has measured. tests/unit/kpi-strip-layout.spec.tsx derives these from the Tailwind
 * tokens and the classes that draw them.
 */
import { dataFaceDraws } from '@/lib/format'

const FIGURE_EM = 1.5
const MARK_EM = 0.6875
export const KPI_FIGURE_ADVANCE = 0.6 * FIGURE_EM
export const KPI_MARK_ADVANCE = 0.6 * MARK_EM
export const KPI_MARK_GAP = 0.125
/** A value's glyphs on one line: its figure's and its mark's (a note letter) that the face draws (lib/format's
 *  dataFaceDraws: ASCII and DATA_FACE_GLYPHS, which tests/e2e/analysis-layout.spec.ts measures in Geist Mono itself),
 *  and the rest in rem: those the face lacks at 1.25em each, and the 2px before the mark. fmtCurrency prints a code
 *  where the face lacks a currency's sign (E203), so a value reaches the 1.25em only by another path; that is wider
 *  than any face found to draw one: DejaVu Sans Bold's ₩ is 1.103em and Inter Black's 1.112em, ₫ peaks at 0.696em,
 *  and Chromium draws the narrow no-break space in "F CFA" as a 0.3em space. */
export interface KpiGlyphs {
  figure: number
  mark: number
  rest: number
}

/** A glyph the face lacks, in ems of its own text. */
const MISSING_EM = 1.25
const tally = (text: string, em: number) => [...text].reduce(
  ([drawn, rest], glyph) => (dataFaceDraws(glyph) ? [drawn + 1, rest] : [drawn, rest + em]), [0, 0])

export function kpiValueGlyphs(text: string, letter?: string | null): KpiGlyphs {
  const marks = letter ? [letter] : []
  const [figure, figureRest] = tally(text, MISSING_EM * FIGURE_EM)
  const [mark, markRest] = tally(marks.join(''), MISSING_EM * MARK_EM)
  return { figure, mark, rest: figureRest + markRest + marks.length * KPI_MARK_GAP }
}

/** A value's width on one line in rem, with its marked letter if it has one, at the face's 0.6em advances unless given
 *  the measured ones. */
export function kpiValueWidth(text: string, letter?: string | null, figure = KPI_FIGURE_ADVANCE, mark = KPI_MARK_ADVANCE): number {
  const glyphs = kpiValueGlyphs(text, letter)
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
