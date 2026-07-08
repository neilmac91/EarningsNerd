import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  EXPORT_TEXT,
  HEADER_STAMP,
  exportFilename,
  exportPanelPng,
  headerHeight,
  layoutLegend,
} from '@/features/analysis/lib/chartExport'
import type { AnalysisDataset } from '@/features/analysis/api/analysis-api'
import tailwindConfig from '../../tailwind.config.js'

vi.mock('@/lib/downloadBlob', () => ({ downloadBlob: vi.fn() }))
import { downloadBlob } from '@/lib/downloadBlob'

// Tabular export left this module for the server-built Excel workbook (owner decision D1) —
// what remains client-side is the PNG path and its filename convention.
const quarterly: AnalysisDataset = {
  ticker: 'TST',
  company_name: 'Test Co',
  mode: 'quarterly',
  period_key: '2024Q3..2024Q4',
  periods: [
    { key: '2024Q3', fiscal_year: 2024, fiscal_period: 'Q3', period_end: '2024-09-30' },
    { key: '2024Q4', fiscal_year: 2024, fiscal_period: 'Q4', period_end: '2024-12-31' },
  ],
  series: [
    {
      concept: 'revenue',
      label: 'Revenue, net',
      unit: 'USD',
      percent: false,
      cagr: null,
      points: [
        { period: '2024Q3', value: 310_000_000, marker: 'F1' },
        { period: '2024Q4', value: 330_000_000, marker: 'F2', derived: true },
      ],
    },
  ],
  inflections: [],
}

describe('exportFilename', () => {
  it('slugs the suffix and folds the period-range dots', () => {
    expect(exportFilename(quarterly, 'Top line & growth', 'png')).toBe(
      'TST_2024Q3-2024Q4_top-line-growth.png'
    )
  })

  it('names the Excel workbook exactly like the backend Content-Disposition', () => {
    // AnalysisPageClient downloads the xlsx under exportFilename(dataset, `${mode}-metrics`,
    // 'xlsx') — the same "{ticker}_{range}_{mode}-metrics.xlsx" the route header advertises,
    // so the two names can never disagree.
    expect(exportFilename(quarterly, `${quarterly.mode}-metrics`, 'xlsx')).toBe(
      'TST_2024Q3-2024Q4_quarterly-metrics.xlsx'
    )
  })
})

describe('EXPORT_TEXT token mirror', () => {
  // Rule 12 gate: canvas draws hexes, not CSS vars — this fails the moment the export inks drift
  // from tailwind.config.js's text tokens (the drift class rule 11's app-wide change invites).
  const text = (
    tailwindConfig as {
      theme: { extend: { colors: { text: Record<string, { light: string; dark: string }> } } }
    }
  ).theme.extend.colors.text

  it('mirrors tailwind text.primary', () => {
    expect(EXPORT_TEXT.primary).toEqual(text.primary)
  })

  it('mirrors tailwind text.secondary', () => {
    expect(EXPORT_TEXT.secondary).toEqual(text.secondary)
  })
})

describe('layoutLegend', () => {
  // Deterministic measure: each glyph is 7px wide (font metrics are stubbed in jsdom anyway).
  const measure = (label: string) => label.length * 7

  it('keeps every item on one row when they fit', () => {
    const rows = layoutLegend(measure, [{ label: 'A', color: '#111' }, { label: 'B', color: '#222' }], 1000)
    expect(rows).toHaveLength(1)
    expect(rows[0].map((i) => i.label)).toEqual(['A', 'B'])
  })

  it('wraps to a new row when the next item overflows maxWidth', () => {
    // Each item ≈ swatch(9)+gap(6)+7px label = 22px; itemGap 16px. Two fit in ~60px, the third wraps.
    const legend = [
      { label: 'A', color: '#111' },
      { label: 'B', color: '#222' },
      { label: 'C', color: '#333' },
    ]
    const rows = layoutLegend(measure, legend, 60)
    expect(rows).toHaveLength(2)
    expect(rows[0].map((i) => i.label)).toEqual(['A', 'B'])
    expect(rows[1].map((i) => i.label)).toEqual(['C'])
  })

  it('caches each label width so the draw pass never re-measures', () => {
    const rows = layoutLegend(measure, [{ label: 'Gross', color: '#111' }], 1000)
    expect(rows[0][0].width).toBe('Gross'.length * 7)
  })

  it('places an over-wide single item on its own row rather than looping', () => {
    const rows = layoutLegend(measure, [{ label: 'a very long series label', color: '#111' }], 20)
    expect(rows).toHaveLength(1)
  })
})

describe('headerHeight', () => {
  it('reserves the company + subtitle lines even with no legend', () => {
    expect(headerHeight(0)).toBe(
      HEADER_STAMP.padTop +
        HEADER_STAMP.companySize +
        HEADER_STAMP.lineGap +
        HEADER_STAMP.subtitleSize +
        HEADER_STAMP.padBottom
    )
  })

  it('grows with each wrapped legend row', () => {
    expect(headerHeight(2)).toBeGreaterThan(headerHeight(1))
    expect(headerHeight(1)).toBeGreaterThan(headerHeight(0))
  })
})

/* -------------------------------------------------------------------------
   exportPanelPng — the regression guard for the "no legend / no identity in
   exports" bug. The Recharts SVG carries the plot only; the export must redraw
   the company, ticker · metric, and every legend label onto the canvas, plus
   the "EarningsNerd" wordmark footer. jsdom has no real 2d context, so both
   the canvas and the SVG/mark <img> decode are stubbed.
------------------------------------------------------------------------- */
const HEADER = {
  company: 'Tesla, Inc.',
  ticker: 'TSLA',
  title: 'Cash generation',
  legend: [
    { label: 'Operating CF', color: '#3E8E84' },
    { label: 'Free cash flow', color: '#B8812F' },
    { label: 'Net income (right)', color: '#5B7CC0' },
  ],
}

describe('exportPanelPng header', () => {
  // A fake <img> whose src setter resolves the decode (jsdom never fires onload).
  class FakeImage {
    onload: (() => void) | null = null
    onerror: (() => void) | null = null
    decoding = 'auto'
    set src(_value: string) {
      Promise.resolve().then(() => this.onload?.())
    }
  }

  let fillTexts: string[]
  let fillArgs: { text: string; maxWidth?: number }[]
  let ctx: Record<string, unknown>

  beforeEach(() => {
    vi.stubGlobal('Image', FakeImage)
    fillTexts = []
    fillArgs = []
    ctx = {
      fillStyle: '',
      font: '',
      textBaseline: '',
      globalAlpha: 1,
      fillRect: vi.fn(),
      fillText: vi.fn((text: string, _x: number, _y: number, maxWidth?: number) => {
        fillTexts.push(text)
        fillArgs.push({ text, maxWidth })
      }),
      measureText: (t: string) => ({ width: t.length * 7 }),
      scale: vi.fn(),
      drawImage: vi.fn(),
      save: vi.fn(),
      restore: vi.fn(),
      beginPath: vi.fn(),
      fill: vi.fn(),
      roundRect: vi.fn(),
    }
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(ctx as never)
    vi.spyOn(HTMLCanvasElement.prototype, 'toBlob').mockImplementation(function (
      this: HTMLCanvasElement,
      cb: BlobCallback
    ) {
      cb(new Blob(['png'], { type: 'image/png' }))
    } as never)
    vi.mocked(downloadBlob).mockClear()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  const PLOT_W = 560

  function makeContainer(): HTMLElement {
    const container = document.createElement('div')
    container.style.backgroundColor = 'rgb(251, 250, 246)'
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
    // jsdom reports a 0×0 rect; give it a realistic plot size so the footer/legend layout is real.
    svg.getBoundingClientRect = () =>
      ({ width: PLOT_W, height: 224, top: 0, left: 0, right: PLOT_W, bottom: 224, x: 0, y: 0, toJSON() {} }) as DOMRect
    container.appendChild(svg)
    document.body.appendChild(container)
    return container
  }

  it('draws the company, ticker · metric subtitle, and every legend label', async () => {
    const ok = await exportPanelPng(makeContainer(), 'x.png', { dark: false, header: HEADER })
    expect(ok).toBe(true)
    expect(fillTexts).toContain('Tesla, Inc.')
    expect(fillTexts).toContain('TSLA · Cash generation')
    expect(fillTexts).toContain('Operating CF')
    expect(fillTexts).toContain('Free cash flow')
    expect(fillTexts).toContain('Net income (right)')
    expect(downloadBlob).toHaveBeenCalledOnce()
  })

  it('stamps the EarningsNerd wordmark in the footer', async () => {
    await exportPanelPng(makeContainer(), 'x.png', { dark: false, header: HEADER })
    // Two-tone wordmark: "Earnings" (ink) + "Nerd" (sage), so the source is obvious.
    expect(fillTexts).toContain('Earnings')
    expect(fillTexts).toContain('Nerd')
  })

  it('maxWidth-guards all three header tiers (company, subtitle, legend labels)', async () => {
    await exportPanelPng(makeContainer(), 'x.png', { dark: false, header: HEADER })
    const maxWidthOf = (t: string) => fillArgs.find((a) => a.text === t)?.maxWidth
    expect(maxWidthOf('Tesla, Inc.')).toBeTypeOf('number') // company
    expect(maxWidthOf('TSLA · Cash generation')).toBeTypeOf('number') // subtitle
    expect(maxWidthOf('Operating CF')).toBeTypeOf('number') // legend label — the uniformity fix
  })

  it('offsets the plot below the header strip', async () => {
    await exportPanelPng(makeContainer(), 'x.png', { dark: false, header: HEADER })
    const drawImage = ctx.drawImage as ReturnType<typeof vi.fn>
    // The plot is the drawImage call at x=0; its y must equal the reserved header height for the
    // legend as it actually wraps at this plot width (the export measures with the same stub).
    const rows = layoutLegend((s) => s.length * 7, HEADER.legend, PLOT_W - 2 * HEADER_STAMP.padX)
    const plotCall = drawImage.mock.calls.find((c) => c[1] === 0)
    expect(plotCall?.[2]).toBe(headerHeight(rows.length))
  })

  it('degrades to the bare plot (no header identity) when no header is passed', async () => {
    const ok = await exportPanelPng(makeContainer(), 'x.png', { dark: true })
    expect(ok).toBe(true)
    // No company/metric/legend text — but the brand footer wordmark is still stamped.
    expect(fillTexts).not.toContain('Tesla, Inc.')
    expect(fillTexts).not.toContain('TSLA · Cash generation')
    expect(fillTexts).toContain('Earnings')
    const drawImage = ctx.drawImage as ReturnType<typeof vi.fn>
    const plotCall = drawImage.mock.calls.find((c) => c[1] === 0)
    expect(plotCall?.[2]).toBe(0) // plot flush to the top — no header reserved
  })
})
