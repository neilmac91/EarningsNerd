/* =============================================================================
   chart-engine.spec.ts — the trend-chart spec's model checks (features/analysis/lib/charts)
   -----------------------------------------------------------------------------
   The engine plans every tick, label, glyph and pixel before a renderer draws, so the spec's model
   checklist (docs/design/analysis-trend-charts-spec-2026-10.md §6; its §0.5 lists which checks) runs
   here, on real filed datasets (fixtures/chart-datasets.json: 19 datasets chosen for their cases, from 73
   measured), for every chart, both views and a phone, a card and an expanded width. The named cases below pin the behaviours the
   step-1 data required, each on the dataset that showed it.

   Out of reach here, by design: what a renderer draws (the DOM checks D1–D14 belong to the renderer's
   own spec) and the PNG export (chart-export.spec.ts and tests/e2e/chart-export-fidelity.spec.ts).
============================================================================= */
import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

import type { AnalysisDataset } from '@/features/analysis/api/analysis-api'
import { captionBacking, columnOf, gutterCover, gutterCuts, gutterOverlayWidth, LABELLED_MAX_SLOT, layoutChart, MIN_SLOT, minChartWidth, noteGlyphs, OFF_GLYPH, OFF_ROW, slotAt, STRIP_LABEL_X, textWidth, VALUES_DONT_FIT, type ChartLayout } from '@/features/analysis/lib/charts/layout'
import { buildChartModel, CHART_IDS, type ChartId, type ChartModel, type ChartView } from '@/features/analysis/lib/charts/model'
import { chartReadouts } from '@/features/analysis/lib/charts/readout'
import { compactMoney, fixed, moneyFormat, moneyPrefix, MINUS, niceAxis, percentFormat, tooltipMoney } from '@/features/analysis/lib/charts/scale'
import { groupDataNotes, noteMarksFigure, resolveDataNotes } from '@/features/analysis/lib/dataNotes'
import { currencySymbol, dataFaceDraws } from '@/lib/format'
import { MIXED_NOTES, questioned, withMixedNotes } from './chartPlan'

// The fixture's datasets and MIXED_NOTES, which meets every kind of note a band can (chartPlan.ts).
const FIXTURE = withMixedNotes(JSON.parse(readFileSync('tests/unit/fixtures/chart-datasets.json', 'utf8')) as {
  datasets: Record<string, { case: string; dataset: AnalysisDataset }>
})
const DATASETS = Object.entries(FIXTURE.datasets)
const dataset = (name: string) => structuredClone(FIXTURE.datasets[name].dataset)
const WIDTHS: Record<ChartView, number[]> = { card: [342, 502], expanded: [390, 1030] }
/** The SVG glyph set (spec G2): printable ASCII plus ’ − — ↑ ↓ ·. Geist Mono's subsets carry each at 0.6 em; ▲ ▼
 *  and the thin space exist in neither, so they are never planned. † left the set with the band's dagger (D-061, E194). */
const SVG_GLYPHS = /^[\x20-\x7e’−—↑↓·]*$/
const MARKERS = ['circle', 'square', 'triangle']

/** Every string the renderer will print inside the SVG, from the model and the plan alone. */
function svgStrings(model: ChartModel, layout: ChartLayout): string[] {
  const strings: string[] = []
  for (const box of layout.panels) {
    const { panel } = box
    strings.push(...panel.axis.ticks.map(panel.axis.format.tick), ...(panel.caption ? [panel.caption] : []))
    strings.push(...box.bars.flatMap((bar) => (bar.label ? [bar.label.text] : [])), ...box.gaps.map((gap) => gap.text))
    for (const band of [box.offAbove, box.offBelow]) for (const item of band?.items ?? []) strings.push(item.text, '↑', '↓')
    strings.push(...box.nearZero.map((label) => label.text))
  }
  strings.push(...model.periods.flatMap((period) => period.tick), ...noteGlyphs(model, layout).map((glyph) => glyph.text), 'Notes')
  if (layout.view === 'expanded') strings.push(...model.strip.flatMap((row) => [row.label, ...Object.values(row.cells)]))
  return strings
}

describe.each(DATASETS)('%s: the spec model checks', (name, { dataset: source }) => {
  for (const chart of CHART_IDS) for (const view of ['card', 'expanded'] as const) {
    it(`${chart} · ${view}`, () => {
      const ds = structuredClone(source)
      const notes = resolveDataNotes(ds)
      const model = buildChartModel(chart, ds, notes)
      if (model.unavailable) {
        expect(model.panels, 'a chart that does not apply draws nothing').toEqual([])
        expect(model.unavailable.length).toBeGreaterThan(20)
        return
      }
      const layouts = WIDTHS[view].map((width) => layoutChart(model, width, view))
      // M8: the height depends on the view and mode only, so a card never shifts as its width settles.
      expect(new Set(layouts.map((layout) => layout.height)).size).toBe(1)
      if (view === 'card') expect(layouts[0].height).toBe(320)
      layouts.forEach((layout, i) => expect(layout.width, 'M6: below the minimum the SVG keeps its width and scrolls in its card').toBe(Math.max(WIDTHS[view][i], minChartWidth(model, view))))
      for (const [i, layout] of layouts.entries()) {
        expect(layout.slot, 'A7: a slot never falls below its minimum').toBeGreaterThanOrEqual(MIN_SLOT - 1e-9)
        // A4/A7: a chart widens past its container only as far as LABELLED_MAX_SLOT, and only when that gives its
        // labels a tier; a chart that still prints none kept its minimum.
        const fitSlot = (WIDTHS[view][i] - layout.gutter - 8) / model.periods.length
        if (model.panels.some((panel) => panel.marks.some((mark) => mark.labelled))) expect(layout.slot, 'A7: widened at most to LABELLED_MAX_SLOT').toBeLessThanOrEqual(Math.max(fitSlot, LABELLED_MAX_SLOT) + 1e-9)
        // A chart that still prints no labels took no widening, and its labels miss at its minimum too (so a wider
        // container never loses labels its minimum holds).
        const base = layout.gutter + 8 + MIN_SLOT * model.periods.length
        const atMinimum = layoutChart(model, 0, view)
        if (layout.valuesDontFit) {
          expect(minChartWidth(model, view), 'A4: no widening for labels it cannot fit').toBe(base)
          expect(atMinimum.valuesDontFit, 'A4: labels that miss at the container missed at the minimum').toBe(true)
        }
        const texts = svgStrings(model, layout)
        for (const text of texts) {
          expect(text, 'M12: glyphs Geist Mono carries').toMatch(SVG_GLYPHS)
          expect(text, 'the typographic apostrophe (spec §0.4 row 27)').not.toContain("'")
        }
        for (const box of layout.panels) {
          const { ticks, step, domain, format } = box.panel.axis
          ticks.slice(1).forEach((tick, i) => expect(Math.abs(tick - ticks[i] - step), 'M1: uniform ticks').toBeLessThan(step * 1e-6))
          expect(ticks, 'M2: zero is a tick').toContain(0)
          expect(ticks.length - 1, 'A1: the tick cap').toBeLessThanOrEqual(box.panel.nmax)
          // M4: tick labels are 11 px (a 13 px line box), so gridlines keep at least 17 px apart; the tightest
          // is the quarterly card's growth panel, 70 px over its cap of 4.
          if (ticks.length > 1) expect(Math.abs(box.y(ticks[1]) - box.y(ticks[0])), 'M4: gridline spacing').toBeGreaterThanOrEqual(17)
          const labels = ticks.map(format.tick)
          expect(new Set(labels.filter((label) => /[1-9]/.test(label)).map((label) => label.replace(/[^KMBT%]/g, ''))).size, 'M3: one unit per axis').toBeLessThanOrEqual(1)
          expect(labels[ticks.indexOf(0)], 'M3: zero prints bare').toMatch(/^(\$0|0%)$/)
          if (format.kind === 'money') {
            // M3: a money axis takes the next unit before a tick needs four integer digits ("$1,000M" reads "$1B").
            for (const label of labels) expect(label.replace(/[^\d.]/g, '').split('.')[0].length, `M3: ${label}`).toBeLessThanOrEqual(3)
          }
          expect(Math.max(...labels.map(textWidth)) + 8, 'M5: the gutter holds the widest tick').toBeLessThanOrEqual(layout.gutter + 1e-9)
          const percent = format.kind !== 'money'
          for (const mark of box.panel.marks) for (const point of mark.points) {
            if (point.value == null) continue
            const outside = point.value > domain[1] + 1e-9 || point.value < domain[0] - 1e-9
            if (percent) expect(Boolean(point.offscale), `M11: ${mark.label} ${point.period} is flagged exactly when it leaves the axis`).toBe(outside)
            else expect(outside, `M11: amounts never clip (${mark.label} ${point.period})`).toBe(false)
          }
          for (const band of [box.offAbove, box.offBelow]) for (const item of band?.items ?? []) {
            expect(item.left, 'L1: off-scale text starts inside the SVG').toBeGreaterThanOrEqual(0)
            expect(item.left + OFF_GLYPH + textWidth(item.text), 'L1: and ends inside it').toBeLessThanOrEqual(layout.width)
          }
          const labelled = box.panel.marks.find((mark) => mark.labelled)
          if (labelled && layout.width >= 502) expect(box.labels.decimals, 'A4: a label tier fits at card width').not.toBeNull()
          // M10: one scale per panel, so the drawn order of two series is their true order.
          const lines = box.panel.marks.filter((mark) => mark.kind === 'line')
          for (let a = 0; a < lines.length; a++) for (let b = a + 1; b < lines.length; b++) {
            for (const p of lines[a].points) {
              const q = lines[b].points.find((other) => other.period === p.period)
              if (p.value == null || q?.value == null || p.offscale || q.offscale || p.value === q.value) continue
              expect(Math.sign(box.y(q.value) - box.y(p.value)), `M10: ${p.period}`).toBe(Math.sign(p.value - q.value))
            }
          }
          // A13 and M21: every bar sits on its slot centre, anchored at the zero rule on its value's side and
          // never across it, at least 2 px long; the 2 px minimum is drawn exactly when the true length is shorter.
          const pointOf = (seriesKey: string, period: string) => box.panel.marks.find((mark) => mark.seriesKey === seriesKey)!.points.find((point) => point.period === period)!
          for (const bar of box.bars) {
            const point = pointOf(bar.seriesKey, bar.period)
            expect(bar.x + bar.width / 2, 'M13: on the slot centre').toBeCloseTo(layout.x(bar.period), 9)
            expect(bar.height, 'A13: at least 2 px').toBeGreaterThanOrEqual(2)
            if (bar.value >= 0) expect(bar.y + bar.height, `M21: ${bar.seriesKey} ${bar.period} rests on the zero rule`).toBeCloseTo(bar.zero, 9)
            else expect(bar.y, `M21: ${bar.seriesKey} ${bar.period} hangs from the zero rule`).toBeCloseTo(bar.zero, 9)
            expect(bar.stub, 'A13: the stub stands for a true length under 2 px').toBe(Math.abs(box.y(Math.max(domain[0], Math.min(domain[1], bar.value))) - bar.zero) < 2)
            expect(bar.clipped, 'a clipped bar is an off-scale value').toBe(Boolean(point.offscale))
            const printed = box.panel.marks.find((mark) => mark.seriesKey === bar.seriesKey)!.labelled && box.labels.decimals != null
            expect(Boolean(bar.label), 'A4: every bar of a labelled panel prints its value, or none does').toBe(printed)
            if (bar.label) expect(bar.label.text).toBe(format.value(bar.value, box.labels.decimals!))
          }
          // A4, checked apart from its planner: printed bar labels stay inside the SVG and clear of each other,
          // each an 11 px line box (9 px above its baseline, 2 below) with 1 px between any two.
          const boxes = box.bars.flatMap((bar) => bar.label ? [{ ...bar.label, x: bar.x + bar.width / 2, w: textWidth(bar.label.text) }] : [])
          for (const a of boxes) {
            expect(a.x - a.w / 2, `L1: the ${a.text} label starts inside the SVG`).toBeGreaterThanOrEqual(0)
            expect(a.x + a.w / 2, `L1: the ${a.text} label ends inside it`).toBeLessThanOrEqual(layout.width)
          }
          boxes.forEach((a, i) => boxes.slice(i + 1).forEach((b) => {
            const apart = a.x + a.w / 2 + 1 <= b.x - b.w / 2 || b.x + b.w / 2 + 1 <= a.x - a.w / 2 || a.y + 2 + 1 <= b.y - 9 || b.y + 2 + 1 <= a.y - 9
            expect(apart, `A4: the ${a.text} and ${b.text} labels overlap`).toBe(true)
          }))
          // M18: a bar slot without a value prints "—", or "n/m" when the growth is not meaningful.
          const barMarks = box.panel.marks.filter((mark) => mark.kind !== 'line')
          expect(box.bars.length + box.gaps.length, 'every bar slot is a bar or a printed gap').toBe(barMarks.reduce((sum, mark) => sum + mark.points.length, 0))
          for (const gap of box.gaps) expect(gap.text).toBe(barMarks.some((mark) => mark.points.some((point) => point.period === gap.period && point.nm)) ? 'n/m' : '—')
          // M13: every non-zero signed stub prints its value or records the drop (its value is then in the strip).
          for (const bar of box.bars) {
            if (!bar.stub || bar.value === 0 || !box.panel.marks.some((mark) => mark.seriesKey === bar.seriesKey && mark.kind === 'signedBar')) continue
            expect(box.nearZero.some((label) => label.period === bar.period) !== box.nearZeroDropped.includes(bar.period), `M13: ${bar.period}`).toBe(true)
          }
          // A13b: a non-zero signed bar too short to show its sign prints its value, with the sign.
          for (const label of box.nearZero) {
            const point = box.panel.marks[0].points.find((p) => p.period === label.period)!
            expect(Math.abs(box.y(point.value!) - box.y(0))).toBeLessThan(2)
            expect(label.text.startsWith(MINUS)).toBe(point.value! < 0)
          }
        }
        const glyphs = noteGlyphs(model, layout)
        for (const glyph of glyphs) {
          expect(Math.abs(glyph.x - layout.x(glyph.period)) + textWidth(glyph.text) / 2, 'M6: note glyphs fit their slot').toBeLessThanOrEqual(layout.slot / 2)
        }
        glyphs.forEach((a, i) => glyphs.slice(i + 1).filter((b) => b.period === a.period).forEach((b) => {
          expect(Math.abs(a.x - b.x) - (textWidth(a.text) + textWidth(b.text)) / 2, `A5: ${a.text} and ${b.text} keep apart`).toBeGreaterThanOrEqual(1.5 - 1e-9)
        }))
        expect(layout.valuesDontFit, 'A4: the card says so exactly when a labelled panel prints no labels')
          .toBe(layout.panels.some((box) => box.panel.marks.some((mark) => mark.labelled) && box.labels.decimals == null))
        // L1: a label below a negative bar keeps inside its panel's band: its baseline, plus a descent, above the end
        // of the panel's bottom pad (the gap before the next panel, or the period axis).
        layout.panels.forEach((box, i) => {
          const next = layout.panels[i + 1]
          const bandEnd = next ? next.regionTop - (layout.view === 'expanded' ? 16 : 10) : layout.xTickY - 13
          for (const bar of box.bars) if (bar.label && bar.value < 0) expect(bar.label.y + 2, `L1: ${bar.label.text}`).toBeLessThanOrEqual(bandEnd + 1e-9)
        })
        // §3.10: the value strip is collision-free by construction: each cell inside its slot, the first clear of
        // the row's short name.
        if (layout.view === 'expanded') {
          model.strip.forEach((row, r) => {
            expect(layout.stripRowY[r]).toBeGreaterThan(layout.stripTop!)
            for (const [period, cell] of Object.entries(row.cells)) expect(textWidth(cell) + 4, `§3.10: ${row.short} ${period}`).toBeLessThanOrEqual(layout.slot + 1e-9)
            const first = model.periods[0].key
            expect(STRIP_LABEL_X + textWidth(row.short), `§3.10: ${row.short} clears its first cell`).toBeLessThanOrEqual(layout.x(first) - textWidth(row.cells[first]) / 2 - 2 + 1e-9)
          })
        }
      }
      // M9: palette slots and marker shapes in order over the series present; no slot skipped.
      const drawn = model.panels.flatMap((panel) => panel.marks).filter((mark) => mark.kind !== 'growth')
      if (chart !== 'topline') {
        expect(drawn.map((mark) => mark.color)).toEqual(drawn.map((_, i) => i))
        drawn.filter((mark) => mark.kind === 'line').forEach((mark, i) => expect(mark.marker).toBe(MARKERS[i]))
      }
      // A5: each band cell lists its letters in the footnotes' order (a … z, aa …).
      const footnoteOrder = model.footnotes.map((note) => note.mark)
      for (const cell of Object.values(model.notesBand ?? {})) {
        const letters = cell.map((glyph) => glyph.text).filter((text) => /^[a-z]+$/.test(text))
        expect(letters).toEqual([...letters].sort((a, b) => footnoteOrder.indexOf(a) - footnoteOrder.indexOf(b)))
      }
      // M7: every letter in the band is explained by a footnote, and every lettered footnote is in the band.
      const bandLetters = new Set(Object.values(model.notesBand ?? {}).flat().map((glyph) => glyph.text).filter((text) => /^[a-z]+$/.test(text)))
      const footnoteLetters = new Set(model.footnotes.map((note) => note.mark).filter((mark) => /^[a-z]+$/.test(mark)))
      expect([...bandLetters].sort()).toEqual([...footnoteLetters].sort())
      // D-061 (spec §3.3's note): a band letter is a note that questions the number; a gap's footnote leads with no
      // letter, and no chart draws or keys a †, beside a name, a number or anywhere else (G6).
      const byLetter = new Map(notes.notes.map((note) => [note.letter, note]))
      for (const letter of bandLetters) expect(noteMarksFigure(byLetter.get(letter)), `${letter} questions the number`).toBe(true)
      const prose = [model.title, model.subtitle, ...model.legend.flatMap((item) => [item.label, item.value ?? '']),
        ...model.panels.map((panel) => panel.caption ?? ''), ...model.footnotes.flatMap((note) => [note.mark, note.text])]
      for (const text of prose) expect(text, 'G6').not.toContain('†')
      // M18: every growth slot without a value is explained, as structural, unavailable or n/m.
      if (chart === 'topline') {
        const growth = model.panels[1].marks[0].points
        if (growth.some((point) => point.value == null && !point.nm)) expect(model.footnotes.some((note) => note.mark === '—')).toBe(true)
        if (growth.some((point) => point.nm)) expect(model.footnotes.some((note) => note.mark === 'n/m')).toBe(true)
      }
      if (model.panels.some((panel) => panel.marks.some((mark) => mark.kind === 'line' && mark.points.some((point) => point.offscale)))) {
        expect(model.footnotes.some((note) => note.mark === '↓↑')).toBe(true)
      }
    })
  }
})

const ADVANCE_HALF = 3.3

const model = (name: string, chart: ChartId, transform?: (ds: AnalysisDataset) => void) => {
  const ds = dataset(name)
  transform?.(ds)
  return buildChartModel(chart, ds)
}
const ticks = (m: ChartModel, panel = 0) => m.panels[panel].axis.ticks.map(m.panels[panel].axis.format.tick)
/** What the card prints at each of a panel's slots: the bar's label, or the gap's "—" or "n/m". */
const labelsOf = (m: ChartModel, panel: number) => {
  const box = layoutChart(m, 502, 'card').panels[panel]
  return box.panel.marks[0].points.map((point) => box.bars.find((bar) => bar.period === point.period)?.label?.text ?? box.gaps.find((gap) => gap.period === point.period)?.text)
}

describe('the cases the step-1 data required', () => {
  it('REGN FY2025: free cash flow ($4.08B) is drawn below net income ($4.50B) on one cash axis', () => {
    const m = model('REGN_annual', 'cash')
    const box = layoutChart(m, 502, 'card').panels[0]
    const at = (concept: string) => box.panel.marks.find((mark) => mark.seriesKey === concept)!.points.find((point) => point.period === 'FY2025')!.value!
    expect(at('free_cash_flow')).toBeLessThan(at('net_income'))
    expect(box.y(at('free_cash_flow'))).toBeGreaterThan(box.y(at('net_income')))
    expect(m.panels).toHaveLength(1)
    expect(m.legend.map((item) => `${item.label} ${item.value}`)).toEqual(['Operating CF $4.98B', 'Free cash flow $4.08B', 'Net income $4.50B'])
  })

  it('REGN top line: one unit, "$0", every bar and growth bar labelled, the first year structural', () => {
    const m = model('REGN_annual', 'topline')
    expect(m.subtitle).toBe('FY2016–FY2025 · fiscal years end Dec · USD')
    expect(ticks(m, 0)).toEqual(['$0', '$5B', '$10B', '$15B', '$20B'])
    expect(ticks(m, 1)).toEqual([`${MINUS}50%`, '0%', '+50%', '+100%'])
    expect(labelsOf(m, 0)).toEqual(['$4.9B', '$5.9B', '$5.1B', '$6.6B', '$8.5B', '$16.1B', '$12.2B', '$13.1B', '$14.2B', '$14.3B'])
    expect(labelsOf(m, 1)).toEqual(['—', '+20.8%', `${MINUS}12.4%`, '+27.4%', '+29.6%', '+89.1%', `${MINUS}24.3%`, '+7.8%', '+8.3%', '+1.0%'])
    expect(m.footnotes).toContainEqual({ mark: '—', text: 'YoY growth needs the same period a year earlier; none for FY2016.' })
    expect(m.footnotes).toContainEqual({ mark: '', text: 'YoY growth is calculated by EarningsNerd from reported figures.' })
  })

  it('A9: a 52/53-week year ending in early February reads January; quarterly windows name the year end too', () => {
    expect(model('LOVE_annual', 'cash').subtitle).toContain('fiscal years end Jan')
    expect(model('CPRT_annual', 'cash').subtitle).toContain('fiscal years end Jul')
    expect(model('AAPL_quarterly', 'margins').subtitle).toBe('Q4 ’23–Q3 ’26 · fiscal year ends Sep · % of revenue')
    expect(model('XOM_quarterly', 'topline').subtitle, 'no FY or Q4 row: the segment is left out').toBe('Q2 ’26 · USD')
  })

  it('PLUG equity: a −$3.6M year gets room, not an empty −$2B interval, and prints its value', () => {
    const m = model('PLUG_annual', 'balance')
    const equity = m.panels.find((panel) => panel.id === 'equity')!
    expect(equity.axis.domain).toEqual([-200_000_000, 6_000_000_000])
    expect(ticks(m, 1)).toEqual(['$0', '$2B', '$4B', '$6B'])
    const box = layoutChart(m, 502, 'card').panels[1]
    expect(box.nearZero.map((label) => `${label.period} ${label.text}`)).toEqual(['FY2016 $85M', 'FY2017 $70M', `FY2018 ${MINUS}$3.6M`, 'FY2019 $130M'])
  })

  it('BYND: negative equity on its own signed scale; −$997K prints in its own unit', () => {
    const m = model('BYND_annual', 'balance')
    expect(ticks(m, 1)).toEqual([`${MINUS}$1.0B`, `${MINUS}$0.5B`, '$0', '$0.5B'])
    expect(m.legend.find((item) => item.label === 'Equity')!.value).toBe(`${MINUS}$997K`)
  })

  it('RIVN: a zero base is n/m, a missing prior year is unavailable, +2,915% is clipped and printed true', () => {
    const m = model('RIVN_annual', 'topline')
    expect(labelsOf(m, 0).slice(0, 4)).toEqual(['—', '$0', '$0', '$55.0M'])
    expect(labelsOf(m, 1)).toEqual(['—', '—', 'n/m', 'n/m', '+2,915%', '+167.4%', '+12.1%', '+8.4%'])
    expect(m.panels[1].marks[0].points.find((point) => point.period === 'FY2022')!.offscale).toBe('above')
    expect(m.footnotes).toContainEqual({ mark: 'n/m', text: 'Not meaningful: the prior-year figure was zero or of the opposite sign (FY2020–FY2021).' })
    expect(m.footnotes).toContainEqual({ mark: '—', text: 'YoY growth needs the same period a year earlier; none for FY2018–FY2019.' })
  })

  it('LCID margins: −18,093% does not flatten the axis; the clipped values are flagged for the edge band', () => {
    const m = model('LCID_annual', 'margins')
    expect(ticks(m)[0]).toBe(`${MINUS}600%`)
    const box = layoutChart(m, 502, 'card').panels[0]
    expect(box.offBelow!.items.map((item) => item.period).sort()).toEqual(['FY2019', 'FY2019', 'FY2020', 'FY2020', 'FY2021', 'FY2021'])
    expect(box.offBelow!.items.find((item) => item.seriesKey === 'net_margin' && item.period === 'FY2020')!.text).toBe(`${MINUS}18,093%`)
  })

  it('a bank, an insurer and a REIT: the top line falls back, and a chart that does not apply says why', () => {
    expect(model('JPM_annual', 'topline').title).toBe('Net interest income & growth')
    expect(model('JPM_annual', 'margins').unavailable).toBe('Margins need revenue. JPMorgan Chase & Co reports net interest income instead; see Net interest income & growth.')
    // Missing debt never reads as no debt: its item stays, first as in canonical order, with a footnote. An absent free
    // cash flow is not listed.
    const balance = model('JPM_annual', 'balance')
    expect(balance.legend.map((item) => [item.label, item.absent])).toEqual([['Long-term debt · not in dataset', true], ['Cash', false], ['Equity', false]])
    expect([balance.legend[0].value, balance.legend[0].color], 'an absent series has no value and claims no palette slot').toEqual([undefined, null])
    expect(balance.legend.map((item) => item.color)).toEqual([null, 0, 1])
    expect(balance.footnotes).toContainEqual({ mark: '', text: 'Long-term debt isn’t in this dataset for this window (not shown as zero).' })
    expect(model('JPM_annual', 'cash').legend.map((item) => item.label)).toEqual(['Operating CF', 'Net income'])
    const pgr = model('PGR_quarterly', 'topline')
    expect(pgr.title).toBe('Premiums earned & growth')
    // Premiums earned is calculated in two Q4s (the year less its first three quarters): a footnote names them, and no
    // band glyph marks them (D-061).
    expect(pgr.footnotes).toContainEqual({ mark: '', text: 'Calculated by EarningsNerd from reported figures: Premiums earned Q4 ’24, Q4 ’25.' })
    expect(model('O_annual', 'topline').unavailable).toBe('No top-line figure in this company’s filed data (revenue, net interest income or premiums earned).')
    expect(model('O_annual', 'margins').unavailable).toBe('Margins need revenue, which is not in this company’s filed data.')
  })

  it('review notes: a record-only one letters nothing, and one that questions the number letters each period once (D-061)', () => {
    // REGNPN's simulated flags are legacy_calculation, record-only: no letter, no line; the data notes keep them.
    const recorded = model('REGNPN_annual', 'margins')
    expect(recorded.notesBand).toBeNull()
    expect(recorded.footnotes.map((note) => note.mark)).toEqual([''])
    expect(recorded.legend.map((item) => item.label), 'an absent gross margin is not listed').toEqual(['Operating', 'Net'])
    const m = model('REGNPN_annual', 'margins', questioned)
    expect(m.notesBand).toEqual({ FY2023: [{ text: 'a' }], FY2024: [{ text: 'a' }], FY2025: [{ text: 'a' }] })
    expect(m.footnotes[0].mark).toBe('a')
    expect(m.footnotes[0].text).toMatch(/^Operating margin and Net margin FY2023–FY2025: /)
  })

  it('MIXED_NOTES, the sweeps’ own dataset: only a questioned value or comparison letters, an n/m one included (D-061)', () => {
    const ds = dataset(MIXED_NOTES)
    expect(resolveDataNotes(ds).notes.map((note) => [note.letter, note.kind, noteMarksFigure(note)]), 'every kind a band can meet')
      .toEqual([['a', 'review', true], ['b', 'review', false], ['c', 'review', true], ['d', 'unknown', false], ['e', 'unavailable', false]])
    const band = (chart: ChartId) => Object.fromEntries(Object.entries(buildChartModel(chart, ds).notesBand ?? {}).map(([period, glyphs]) => [period, glyphs.map((glyph) => glyph.text)]))
    expect(band('topline'), 'a questioned comparison, on a number and on an n/m').toEqual({ FY2024: ['a'], FY2025: ['c'] })
    expect(buildChartModel('topline', ds).footnotes.slice(0, 2)).toEqual([
      { mark: 'a', text: 'Revenue YoY FY2024: Available sources disagree on this figure.' },
      { mark: 'c', text: 'Revenue YoY FY2025: The source inputs cover incompatible reporting periods.' },
    ])
    expect(band('margins'), 'operating margin’s questioned flags; net margin’s record-only ones letter nothing').toEqual({ FY2023: ['a'], FY2024: ['a'], FY2025: ['a'] })
    expect(band('cash'), 'free cash flow’s unrecorded checks letter nothing').toEqual({})
    expect(band('balance'), 'a gap letters nothing').toEqual({})
  })

  it('a gap in the window: the year after it is unavailable, not structural, and a zero base is found by its key', () => {
    // The backend's annual axis keeps only the fiscal years that have rows, so a window can skip one.
    const gap = model('REGN_annual', 'topline', (ds) => {
      ds.periods = ds.periods.filter((period) => period.key !== 'FY2019')
      for (const series of ds.series) series.points = series.points.filter((point) => point.period !== 'FY2019')
      const revenue = ds.series.find((s) => s.concept === 'revenue')!
      revenue.points.find((point) => point.period === 'FY2020')!.yoy = null
      revenue.points.find((point) => point.period === 'FY2018')!.yoy = null
    })
    // FY2018 and FY2020 stand side by side in the window, but a run never spans the year it skips.
    expect(gap.footnotes).toContainEqual({ mark: '—', text: 'YoY growth needs the same period a year earlier; none for FY2016, FY2018, FY2020.' })
    const zeroBase = model('REGN_annual', 'topline', (ds) => {
      const revenue = ds.series.find((s) => s.concept === 'revenue')!
      ds.periods = ds.periods.filter((period) => period.key !== 'FY2019')
      revenue.points = revenue.points.filter((point) => point.period !== 'FY2019')
      Object.assign(revenue.points.find((point) => point.period === 'FY2018')!, { value: 0 })
      revenue.points.find((point) => point.period === 'FY2020')!.yoy = null
    })
    // FY2020's year-earlier period, FY2019, is the gap, so FY2018's zero is not its base.
    expect(zeroBase.panels[1].marks[0].points.find((point) => point.period === 'FY2020')!.nm).toBeFalsy()
  })

  it('a company with revenue but no margin series says the margins are missing, not the revenue, whatever else it reports', () => {
    const m = model('REGN_annual', 'margins', (ds) => { ds.series = ds.series.filter((s) => !s.concept.endsWith('_margin')) })
    expect(m.unavailable).toBe('Margin figures aren’t in this company’s filed data.')
    // Net interest income beside revenue: revenue is the top line (D16), so no sentence points at an NII chart.
    const both = model('REGN_annual', 'margins', (ds) => {
      const revenue = ds.series.find((s) => s.concept === 'revenue')!
      ds.series = [...ds.series.filter((s) => !s.concept.endsWith('_margin')), { ...structuredClone(revenue), concept: 'net_interest_income', label: 'Net interest income' }]
    })
    expect(both.unavailable).toBe('Margin figures aren’t in this company’s filed data.')
  })

  it('a review note on an n/m comparison marks its band cell, as its footnote names it', () => {
    const m = model('REGN_annual', 'topline', (ds) => {
      delete (ds as { data_notes?: unknown }).data_notes
      Object.assign(ds.series.find((s) => s.concept === 'revenue')!.points.find((point) => point.period === 'FY2024')!, {
        yoy: 'nm', yoy_provenance: { version: 1, method: 'calculated', validation: 'needs_review', reasons: ['source_conflict'], formula: null, inputs: [] },
      })
    })
    const note = m.footnotes.find((footnote) => footnote.text.includes('Revenue YoY FY2024'))!
    expect(m.notesBand?.FY2024?.map((glyph) => glyph.text)).toContain(note.mark)
  })

  it('a negative top line keeps its labels inside panel A, with a label pad under it', () => {
    const m = model('REGN_annual', 'topline', (ds) => {
      ds.periods = ds.periods.slice(-4)
      for (const point of ds.series.find((s) => s.concept === 'revenue')!.points) if (point.value != null) point.value = -point.value
    })
    const layout = layoutChart(m, 502, 'card')
    expect(layout.panels[0].bars.every((bar) => bar.label), 'the labels print').toBe(true)
    const lowest = Math.max(...layout.panels[0].bars.map((bar) => bar.label!.y))
    // Panel A's band ends at its bottom pad, the 10 px gap before panel B's region.
    expect(lowest + 2).toBeLessThanOrEqual(layout.panels[1].regionTop - 10)
  })

  it('more than 26 notes: band cells keep letter order, and two-letter glyphs do not overlap', () => {
    const review = (reasons: string[]) => ({ version: 1 as const, method: 'reported' as const, validation: 'needs_review' as const, reasons, formula: null, inputs: [] })
    const ds = dataset('REGN_annual')
    delete (ds as { data_notes?: unknown }).data_notes
    let n = 0
    for (const s of ds.series.filter((series) => ['revenue', 'net_income', 'operating_cash_flow'].includes(series.concept))) {
      for (const point of s.points) if (point.value != null) point.provenance = review([`reason_${n++}`])
    }
    // Letters follow report order, so three FY2020 balance points that share earlier reasons get a one-letter and
    // two two-letter notes between them.
    const at = (concept: string, period = 'FY2020') => ds.series.find((s) => s.concept === concept)!.points.find((point) => point.period === period)!
    at('cash_and_equivalents').provenance = review(['reason_28'])
    at('shareholders_equity').provenance = review(['reason_2'])
    at('long_term_debt').provenance = review(['reason_27'])
    // FY2017's long-term debt is a gap: its note is unavailable, so it letters nothing (D-061).
    expect(at('long_term_debt', 'FY2017').value).toBeNull()
    at('long_term_debt', 'FY2017').provenance = review(['reason_27'])
    const m = buildChartModel('balance', ds)
    const letterOf = new Map(groupDataNotes(ds).notes.filter((note) => note.kind === 'review').map((note) => [note.reasons[0], note.letter]))
    expect(m.notesBand!.FY2017, 'a gap letters nothing').toBeUndefined()
    const cell = m.notesBand!.FY2020.map((glyph) => glyph.text)
    const expected = ['reason_2', 'reason_27', 'reason_28'].map((reason) => letterOf.get(reason)!).sort((a, b) => (a.length - b.length) || a.localeCompare(b))
    expect(cell, 'letter order: a … z, aa …').toEqual(expected)
    expect(cell.map((letter) => letter.length), 'one letter, then two').toEqual([1, 2, 2])
    expect(cell, 'a plain string sort would put the two-letter ones first').not.toEqual([...cell].sort())
    const placed = noteGlyphs(m, layoutChart(m, 502, 'card')).filter((glyph) => glyph.period === 'FY2020')
    placed.slice(1).forEach((glyph, i) => expect(glyph.x - placed[i].x - (textWidth(glyph.text) + textWidth(placed[i].text)) / 2).toBeCloseTo(1.5, 9))
  })

  it('the expanded value strip: short names, equity’s bar swatch, and slots that hold every cell', () => {
    const m = model('REGN_annual', 'balance')
    expect(m.strip.map((row) => [row.short, row.swatch, row.marker ?? null])).toEqual([['Long-t', 'line', 'circle'], ['Cash', 'line', 'square'], ['Equity', 'bar', null]])
    const narrow = layoutChart(model('REGN_annual', 'margins'), 358, 'expanded')
    expect(narrow.width, 'a narrow expanded view scrolls rather than crowd its strip').toBeGreaterThan(358)
  })

  it('a phone card widens the top line to the narrowest width that prints its labels, up to 42 px a period (A4, A7)', () => {
    const planAt = (name: string, width: number) => {
      const plan = layoutChart(model(name, 'topline'), width, 'card')
      return [plan.width, plan.valuesDontFit]
    }
    // At 36 px a period REGN's six-glyph labels ("$4.86B") collide; they first fit 465 px wide (41.6 px a period).
    expect(planAt('REGN_annual', 342)).toEqual([465, false])
    expect(planAt('PLUG_annual', 342)).toEqual([432, false])
    // RIVN fits its card at 36 px, but not its growth labels ("+2,915%"): it widens and scrolls too.
    expect(planAt('RIVN_annual', 342)).toEqual([382, false])
    // LCID needs 41.7 px a period, which its 342 px card already gives: no scroll for a whole-pixel slot.
    expect(planAt('LCID_annual', 342)).toEqual([342, false])
    // A chart wide enough already is never widened, a top line that fits at 36 px keeps it (AAPL: 409 px at 342),
    // and a chart with no labels keeps 36 px.
    expect(planAt('REGN_annual', 502)).toEqual([502, false])
    const aapl = model('AAPL_annual', 'topline')
    const aaplAt342 = layoutChart(aapl, 342, 'card')
    expect([aaplAt342.width, aaplAt342.valuesDontFit]).toEqual([aaplAt342.gutter + 8 + MIN_SLOT * aapl.periods.length, false])
    expect(minChartWidth(aapl)).toBe(aaplAt342.width)
    const margins = model('REGN_annual', 'margins')
    expect(minChartWidth(margins)).toBe(layoutChart(margins, 342, 'card').gutter + 8 + MIN_SLOT * margins.periods.length)
  })

  it('labels no slot up to 42 px can hold leave the card to say so, without widening it (A4)', () => {
    const chf = model('REGN_annual', 'topline', (ds) => {
      for (const series of ds.series) if (!series.percent) for (const point of [series, ...series.points]) point.unit = 'CHF'
    })
    const plan = layoutChart(chf, 502, 'card')
    expect([plan.width, plan.valuesDontFit]).toEqual([502, true])
    expect(minChartWidth(chf), 'widening that cannot fit the labels is not taken').toBe(plan.gutter + 8 + MIN_SLOT * chf.periods.length)
    expect(plan.panels[0].bars.every((bar) => bar.label == null)).toBe(true)
    expect(VALUES_DONT_FIT).toBe('Values don’t fit at this width. The metrics table lists them.')
  })

  it('a one-period window: an empty growth panel shows its zero rule alone', () => {
    expect(ticks(model('XOM_quarterly', 'topline'), 1)).toEqual(['0%'])
  })
})

describe('reading a chart: the slot under a pointer, a period’s column and the sticky gutter (§3.9, A7)', () => {
  it.each(DATASETS.map(([name]) => name))('%s', (name) => {
    for (const chart of CHART_IDS) {
      const model = buildChartModel(chart, dataset(name))
      if (model.unavailable) continue
      for (const width of [342, 502]) {
        const layout = layoutChart(model, width, 'card')
        // §3.9's hit target: every x of a slot's full width reads its period, and nothing in the gutter or right pad.
        model.periods.forEach((period, i) => {
          const column = columnOf(layout, period.key)
          expect(column.width).toBe(layout.slot)
          expect(column.left + column.width / 2).toBeCloseTo(layout.x(period.key), 9)
          for (const x of [column.left + 0.001, layout.x(period.key), column.left + column.width - 0.001]) expect(slotAt(layout, x)).toBe(i)
        })
        expect(slotAt(layout, layout.plotLeft - 0.001)).toBeNull()
        expect(slotAt(layout, layout.plotRight)).toBeNull()
        // A7's gutter covers the plot's own at rest; scrolled, out to the next slot boundary, so no column shows cut.
        expect(gutterCover(layout, 0)).toBe(layout.plotLeft)
        for (const scroll of [1, layout.slot / 2, layout.slot, layout.slot * 2.25, layout.width - width]) {
          const cover = gutterCover(layout, scroll)
          expect(cover).toBeGreaterThanOrEqual(layout.plotLeft - 1e-9)
          expect(cover).toBeLessThan(layout.plotLeft + layout.slot)
          const boundary = (scroll + cover - layout.plotLeft) / layout.slot
          expect(Math.abs(boundary - Math.round(boundary)), 'the cover ends on a slot boundary').toBeLessThan(1e-6)
        }
        expect(gutterOverlayWidth(layout)).toBe(Math.max(layout.plotLeft, ...layout.panels.map(captionBacking)))
        for (const box of layout.panels) {
          if (box.captionY != null && box.panel.caption) expect(captionBacking(box)).toBeGreaterThanOrEqual(textWidth(box.panel.caption) + 4)
        }
      }
    }
  })
})

describe('A7’s sticky gutter never shows a printed value in part, at any scroll', () => {
  /** Every text the plan prints, by kind, as its box: x from its planned centre or left, y the band it sits in. */
  function texts(model: ChartModel, layout: ChartLayout) {
    const boxes: { kind: string; period: string; x0: number; x1: number; y0: number; y1: number }[] = []
    const centred = (kind: string, period: string, x: number, text: string, baseline: number) =>
      boxes.push({ kind, period, x0: x - textWidth(text) / 2, x1: x + textWidth(text) / 2, y0: baseline - 10, y1: baseline + 3 })
    for (const box of layout.panels) {
      for (const bar of box.bars) if (bar.label) centred('bar label', bar.period, bar.x + bar.width / 2, bar.label.text, bar.label.y)
      for (const gap of box.gaps) centred('gap', gap.period, gap.x, gap.text, gap.y)
      for (const label of box.nearZero) centred('near zero', label.period, label.x, label.text, label.y)
      for (const band of [box.offAbove, box.offBelow]) for (const item of band?.items ?? []) {
        const y0 = band!.top + OFF_ROW * item.row
        boxes.push({ kind: 'off-scale', period: item.period, x0: item.left, x1: item.left + OFF_GLYPH + textWidth(item.text), y0, y1: y0 + OFF_ROW })
      }
    }
    for (const period of model.periods) for (const line of period.tick) centred('x tick', period.key, layout.x(period.key), line, layout.xTickY)
    if (layout.stripTop != null) model.strip.forEach((row, i) => {
      for (const period of model.periods) centred('strip cell', period.key, layout.x(period.key), row.cells[period.key], layout.stripRowY[i])
    })
    for (const glyph of noteGlyphs(model, layout)) centred('note glyph', glyph.period, glyph.x, glyph.text, layout.notesY)
    return boxes
  }

  it.each(DATASETS.map(([name]) => name))('%s', (name) => {
    for (const chart of CHART_IDS) {
      const model = buildChartModel(chart, dataset(name))
      if (model.unavailable) continue
      for (const view of ['card', 'expanded'] as const) for (const viewport of [300, 342]) {
        const layout = layoutChart(model, viewport, view)
        const boxes = texts(model, layout)
        // Only a bar label and an off-scale value run past their column; the cover takes every other text with its column.
        for (const box of boxes) if (box.kind !== 'bar label' && box.kind !== 'off-scale') {
          const column = columnOf(layout, box.period)
          expect(box.x0, `${chart} ${view}: ${box.kind} inside its column`).toBeGreaterThanOrEqual(column.left - 1e-9)
          expect(box.x1, `${chart} ${view}: ${box.kind} inside its column`).toBeLessThanOrEqual(column.left + column.width + 1e-9)
        }
        for (let scroll = 1; scroll <= layout.width - viewport; scroll += 1.5) {
          const cover = gutterCover(layout, scroll)
          const edge = scroll + cover
          const cuts = gutterCuts(layout, scroll, cover)
          for (const box of boxes) {
            if (box.x0 >= edge || box.x1 <= edge) continue
            // Cut by the edge: the rest of its box lies under a cut the gutter draws.
            const hidden = cuts.some((cut) => cut.x <= cover + 1e-9 && cut.x + cut.width >= box.x1 - scroll - 1e-9 && cut.y <= box.y0 + 1e-9 && cut.y + cut.height >= box.y1 - 1e-9)
            expect(hidden, `${chart} ${view} at ${scroll}: a ${box.kind} shows in part`).toBe(true)
          }
        }
      }
    }
  })
})

describe('amounts carry their filer’s currency, never a default dollar sign', () => {
  const inUnit = (unit: string) => (ds: AnalysisDataset) => {
    for (const series of ds.series) if (!series.percent) {
      series.unit = unit
      for (const point of series.points) point.unit = unit
    }
  }

  it('a yen filer reads in yen, a franc filer by its code, an amount with no currency with no symbol', () => {
    expect(ticks(model('REGN_annual', 'topline', inUnit('JPY')))).toEqual(['¥0', '¥5B', '¥10B', '¥15B', '¥20B'])
    expect(model('REGN_annual', 'topline', inUnit('JPY')).subtitle).toBe('FY2016–FY2025 · fiscal years end Dec · JPY')
    expect(ticks(model('REGN_annual', 'cash', inUnit('CHF')))[1]).toBe('CHF 2B')
    expect(ticks(model('REGN_annual', 'cash', inUnit('CAD')))[1]).toBe('CA$2B')
    const bare = model('REGN_annual', 'cash', inUnit('pure'))
    expect(ticks(bare)).toEqual(['0', '2B', '4B', '6B', '8B', '10B'])
    expect(bare.subtitle).toBe('FY2016–FY2025 · fiscal years end Dec')
  })

  it.each([
    ['topline', 'revenue'],
    ['cash', 'net_income'],
    ['balance', 'cash_and_equivalents'],
  ] as const)('amounts in two currencies never share a scale: %s', (chart, concept) => {
    const mixed = model('REGN_annual', chart, (ds) => { ds.series.find((s) => s.concept === concept)!.points[3].unit = 'EUR' })
    expect(mixed.panels).toEqual([])
    expect(mixed.unavailable).toMatch(/more than one currency/)
  })

  it('a won or dong filer reads by its code, since Geist Mono draws neither sign (E203)', () => {
    expect(ticks(model('REGN_annual', 'cash', inUnit('KRW')))[1]).toBe('KRW 2B')
    expect([moneyPrefix('KRW'), moneyPrefix('VND'), moneyPrefix('INR'), moneyPrefix('ILS'), moneyPrefix('PHP')]).toEqual(['KRW ', 'VND ', '₹', '₪', '₱'])
    // XOF's "F CFA" holds a narrow no-break space (U+202F), which no Geist Mono face draws, so it prints its code too.
    expect(moneyPrefix('XOF')).toBe('XOF ')
    // Over the ISO 4217 list, every glyph that a prefix prints is one the data face draws (G2).
    const printed = Intl.supportedValuesOf('currency').flatMap((code) => [...moneyPrefix(code)])
    expect([...new Set(printed)].filter((glyph) => !dataFaceDraws(glyph))).toEqual([])
    expect(printed, 'the list is the one Intl prints from').toEqual(expect.arrayContaining(['₹', '₪', '₱', '€', '£', '¥']))
  })

  it('currencySymbol reads ISO 4217 codes only', () => {
    expect([currencySymbol('USD'), currencySymbol('JPY'), currencySymbol('EUR'), currencySymbol('GBP')]).toEqual(['$', '¥', '€', '£'])
    expect([currencySymbol('shares'), currencySymbol(''), currencySymbol(null), currencySymbol('usd')]).toEqual([null, null, null, null])
    // Well-formed, but no currency: a code Intl knows nothing of, and XXX ("no currency"), print no symbol.
    expect([currencySymbol('ABC'), currencySymbol('XXX')]).toEqual([null, null])
    const abc = model('REGN_annual', 'cash', inUnit('ABC'))
    expect([ticks(abc)[1], abc.subtitle]).toEqual(['2B', 'FY2016–FY2025 · fiscal years end Dec'])
  })
})

describe('A1 and A2: ticks and printed values', () => {
  it('the densest legal grid, zero-anchored, never appending the data max', () => {
    expect(niceAxis([4.86e9, 16.07e9], 5).ticks).toEqual([0, 5e9, 10e9, 15e9, 20e9])
    expect(niceAxis([-12, 89], 4)).toMatchObject({ ticks: [-50, 0, 50, 100], step: 50 })
  })

  it('the unit follows the largest tick, so no axis prints "−$1,000M"', () => {
    const axis = niceAxis([-0.997e9, 0.3e9], 4)
    const format = moneyFormat([-0.997e9, 0.3e9], axis.step, axis.ticks, 'USD')
    expect(axis.ticks.map(format.tick)).toEqual([`${MINUS}$1.0B`, `${MINUS}$0.5B`, '$0', '$0.5B'])
  })

  it('zero is "$0" and "0%"; minus is U+2212; a value under 2 significant figures prints in its own unit', () => {
    const format = moneyFormat([16e9], 5e9, [0, 5e9, 10e9, 15e9, 20e9], 'USD')
    expect([format.tick(0), format.value(-997_000, 1), format.value(27.1e6, 2), format.value(-1.2e9, 1)]).toEqual(['$0', `${MINUS}$997K`, '$27.1M', `${MINUS}$1.2B`])
    expect([percentFormat(25, true).tick(0), percentFormat(10, false).tick(0), percentFormat(25, true).value(-13.4)]).toEqual(['0%', '0%', `${MINUS}13.4%`])
    expect([compactMoney(-3.588e6, 'USD'), compactMoney(85.1e6, 'USD'), compactMoney(-997e3, 'USD')]).toEqual([`${MINUS}$3.6M`, '$85M', `${MINUS}$997K`])
  })

  it('F$: an own-unit value that rounds to 1,000 steps up a unit, keeping its significant figures', () => {
    const format = moneyFormat([16e9], 5e9, [0, 5e9, 10e9, 15e9, 20e9], 'USD')
    expect([format.value(999_950, 1), format.value(9_996_000, 0), format.value(0.5, 0)]).toEqual(['$1.00M', '$10.0M', '$0.50'])
    expect([compactMoney(999_600, 'USD'), compactMoney(-999_960_000, 'USD'), compactMoney(9.96e6, 'USD')]).toEqual(['$1.0M', `${MINUS}$1.0B`, '$10M'])
  })

  it('A2 past two decimals: a growth panel within ±0.1% prints exact, distinct ticks', () => {
    const axis = niceAxis([0, 0.1], 4)
    expect(axis.ticks.map(percentFormat(axis.step, true).tick)).toEqual(['0%', '+0.025%', '+0.050%', '+0.075%', '+0.100%'])
  })

  it('F% and d0 test the rounded value: 999.96% is "1,000%", and 999.7M on a $B axis is "$1.00B"', () => {
    expect([percentFormat(10, false).value(999.96), percentFormat(10, true).value(-999.97, 1)]).toEqual(['1,000%', `${MINUS}1,000%`])
    const format = moneyFormat([999.7e6, 400e6], 0.25e9, [0, 0.25e9, 0.5e9, 0.75e9, 1e9], 'USD')
    expect([format.d0, format.value(999.7e6), format.value(400e6)]).toEqual([2, '$1.00B', '$0.40B'])
  })

  it('M15: every printed value rounds as the metrics table rounds, half away from zero on the decimal', () => {
    // Each half is a hair under it as a double (143.35 is 143.3499…), where toFixed rounds down: "143.3", "30.1".
    expect([fixed(143.35, 1), fixed(30.15, 1), fixed(0.35, 1), fixed(46.995, 2), fixed(4.0805, 3)]).toEqual(['143.4', '30.2', '0.4', '47.00', '4.081'])
    // At each call site: a percent panel's values, an amount at its axis's precision, and in its own unit.
    expect([percentFormat(10, false).value(30.15), percentFormat(10, true).value(-0.35)]).toEqual(['30.2%', `${MINUS}0.4%`])
    const format = moneyFormat([200e6], 50e6, [0, 50e6, 100e6, 150e6, 200e6], 'USD')
    expect([format.value(143.35e6, 1), tooltipMoney(-46.995e6, 'USD'), compactMoney(3.55e6, 'USD')]).toEqual(['$143.4M', `${MINUS}$47.00M`, '$3.6M'])
  })

  it('A1 at any magnitude: a KRW 120,000T axis still steps uniformly', () => {
    expect(niceAxis([3e16, 1.2e17], 5)).toMatchObject({ step: 2.5e16, ticks: [0, 2.5e16, 5e16, 7.5e16, 1e17, 1.25e17] })
  })

  it('A1 under 0.001: the grid reaches as far down as the data, so zero is never doubled', () => {
    expect(niceAxis([0.0004, 0.0008], 8)).toMatchObject({ ticks: [0, 0.0001, 0.0002, 0.0003, 0.0004, 0.0005, 0.0006, 0.0007, 0.0008], step: 0.0001 })
  })
})

/* -----------------------------------------------------------------------------
   Golden plans: everything a renderer reads from the engine for the six datasets the plan names (REGN,
   LCID, PLUG, BYND, JPM, PGR), as printed strings and positions to 0.1 px, at a card width and the
   expanded width. A change to the engine's output shows here as a diff to review, never silently. After
   an intended change, `npx vitest run tests/unit/chart-engine.spec.ts -u` rewrites them.
----------------------------------------------------------------------------- */
const GOLDEN = ['REGN_annual', 'LCID_annual', 'PLUG_annual', 'BYND_annual', 'JPM_annual', 'PGR_quarterly']

function plan(model: ChartModel, layout: ChartLayout) {
  const px = (value: number) => Math.round(value * 10) / 10
  return {
    title: model.title,
    subtitle: model.subtitle,
    unavailable: model.unavailable,
    frame: { width: layout.width, height: layout.height, gutter: layout.gutter, slot: px(layout.slot), barWidth: layout.barWidth, growthBarWidth: layout.growthBarWidth, xTickY: px(layout.xTickY), stripTop: layout.stripTop, stripRowY: layout.stripRowY, notesY: px(layout.notesY), valuesDontFit: layout.valuesDontFit },
    periods: model.periods.map((period) => [period.key, px(layout.x(period.key)), ...period.tick]),
    panels: layout.panels.map((box) => {
      const { axis } = box.panel
      const printed = (value: number) => axis.format.value(value, box.labels.decimals ?? axis.format.d0)
      const clamp = (value: number) => Math.max(axis.domain[0], Math.min(axis.domain[1], value))
      return {
        id: box.panel.id,
        caption: box.panel.caption,
        bands: [box.regionTop, box.captionY, px(box.top), px(box.height)],
        ticks: axis.ticks.map((tick) => [axis.format.tick(tick), px(box.y(tick))]),
        labelDecimals: box.labels.decimals,
        marks: box.panel.marks.map((mark) => ({
          kind: mark.kind, series: mark.seriesKey, label: mark.label, color: mark.color, marker: mark.marker ?? null, labelled: mark.labelled,
          points: mark.points.map((point) => point.value == null
            ? [point.period, point.nm ? 'n/m' : '—']
            : [point.period, printed(point.value), px(box.y(clamp(point.value))), ...(point.offscale ? [point.offscale] : [])]),
        })),
        bars: box.bars.map((bar) => [bar.period, bar.seriesKey, px(bar.x), px(bar.y), bar.width, px(bar.height), ...(bar.stub ? ['stub'] : []), ...(bar.clipped ? ['clipped'] : []), ...(bar.label ? [bar.label.text, px(bar.label.y)] : [])]),
        gaps: box.gaps.map((gap) => [gap.period, gap.text, px(gap.x), px(gap.y)]),
        offScale: [box.offAbove, box.offBelow].map((band) => band && { top: px(band.top), depth: band.depth, items: band.items.map((item) => [item.period, item.seriesKey, item.text, px(item.left), item.row]) }),
        nearZero: box.nearZero.map((label) => [label.period, label.text, px(label.x), px(label.y)]),
      }
    }),
    legend: model.legend.map((item) => [item.label, item.value ?? null, item.color, item.swatch, item.marker ?? null, item.absent]),
    notes: noteGlyphs(model, layout).map((glyph) => [glyph.period, glyph.text, px(glyph.x)]),
    footnotes: model.footnotes.map((note) => [note.mark, note.text]),
    strip: layout.view === 'expanded' ? model.strip.map((row) => [row.short, row.color, row.swatch, row.marker ?? null, row.cells]) : [],
  }
}

/** Two-space JSON with arrays of plain values kept on one line, so a changed value is a one-line diff. */
const golden = (value: unknown) => `${JSON.stringify(value, null, 2).replace(/\[\s+((?:(?:"(?:[^"\\]|\\.)*"|-?[\d.e+-]+|true|false|null),?\s*)+)\]/g, (_, items: string) => `[${items.trim().split(/,\s*\n\s*/).join(', ')}]`)}\n`

describe.each(GOLDEN)('%s: the golden plan', (name) => {
  it('matches its committed plan in every chart and view', async () => {
    const plans = Object.fromEntries(CHART_IDS.map((chart) => {
      const ds = dataset(name)
      const notes = resolveDataNotes(ds)
      const m = buildChartModel(chart, ds, notes)
      // The tooltip's header and rows, then the values stop's spoken sentence, one line a period (readout.ts): view-independent,
      // so once a chart.
      const readout = chartReadouts(m, ds, notes).map((period) => [period.header, ...period.rows.map((row) => `${row.label}: ${row.text}`), period.announcement])
      return [chart, { card: plan(m, layoutChart(m, 502, 'card')), expanded: plan(m, layoutChart(m, 1030, 'expanded')), readout }]
    }))
    await expect(golden(plans)).toMatchFileSnapshot(`fixtures/chart-golden/${name}.json`)
  })
})
