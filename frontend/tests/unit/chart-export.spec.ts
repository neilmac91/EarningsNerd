import { crc32, deflateSync } from 'node:zlib'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  chartDataNotes,
  embeddedFontFaces,
  EXPORT_DPI,
  EXPORT_SCALE,
  EXPORT_TEXT,
  HEADER_STAMP,
  exportFilename,
  exportPanelPng,
  exportSourceText,
  headerHeight,
  layoutLegend,
  layoutExportNotes,
  MARK_STAMP,
  parseUnicodeRange,
  withPngResolution,
} from '@/features/analysis/lib/chartExport'
import type { AnalysisDataset } from '@/features/analysis/api/analysis-api'
import { groupDataNotes } from '@/features/analysis/lib/dataNotes'
import { FCF_DEFINITION } from '@/features/analysis/lib/provenance'
import tailwindConfig from '../../tailwind.config.js'

vi.mock('@/lib/downloadBlob', () => ({ downloadBlob: vi.fn() }))
import { downloadBlob } from '@/lib/downloadBlob'
vi.mock('@/lib/api/client', () => ({ default: { get: vi.fn() } }))
import api from '@/lib/api/client'

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

describe('exportSourceText', () => {
  // The PNG's subtitle names the run's window as the file name, the PDF and the workbook do (periodLabels.ts).
  it.each([
    { run: 'an annual run', period_key: 'FY2016..FY2025', period: 'FY2016–FY2025' },
    { run: 'a quarterly run', period_key: '2024Q3..2024Q4', period: 'Q3 2024–Q4 2024' },
    { run: 'a one-period run', period_key: 'FY2024..FY2024', period: 'FY2024' },
  ])('names the period range of $run: $period', ({ period_key, period }) => {
    expect(exportSourceText({ ...quarterly, period_key }).period).toBe(period)
  })
})

/* -------------------------------------------------------------------------
   The PNG's declared resolution. Chunks are built and read here with node:zlib's CRC-32, so the module's own CRC
   is checked against another implementation.
------------------------------------------------------------------------- */
const SIGNATURE = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a])
function chunk(type: string, data: Uint8Array = new Uint8Array()): Buffer {
  const body = Buffer.concat([Buffer.from(type, 'latin1'), data])
  const bytes = Buffer.alloc(body.length + 8)
  bytes.writeUInt32BE(data.length, 0)
  body.copy(bytes, 4)
  bytes.writeUInt32BE(crc32(body), body.length + 4)
  return bytes
}
/** A whole PNG of one RGBA pixel, in the brand sage. */
const IHDR = chunk('IHDR', Buffer.from([0, 0, 0, 1, 0, 0, 0, 1, 8, 6, 0, 0, 0]))
const IDAT = chunk('IDAT', deflateSync(Buffer.from([0, 0x3c, 0x66, 0x50, 0xff])))
const IEND = chunk('IEND')
const png = (...chunks: Buffer[]) => new Uint8Array(Buffer.concat([SIGNATURE, ...chunks]))
/** Each chunk in file order: its type, its data and whether its CRC is node:zlib's. */
function readChunks(bytes: Uint8Array) {
  const buffer = Buffer.from(bytes.buffer, bytes.byteOffset, bytes.byteLength)
  expect(buffer.subarray(0, 8)).toEqual(SIGNATURE)
  const chunks: { type: string; data: Buffer; crcMatches: boolean }[] = []
  for (let offset = 8; offset < buffer.length;) {
    const length = buffer.readUInt32BE(offset)
    chunks.push({
      type: buffer.toString('latin1', offset + 4, offset + 8),
      data: buffer.subarray(offset + 8, offset + 8 + length),
      crcMatches: buffer.readUInt32BE(offset + 8 + length) === crc32(buffer.subarray(offset + 4, offset + 8 + length)),
    })
    offset += 12 + length
  }
  return chunks
}
const physOf = (data: Buffer) => ({ x: data.readUInt32BE(0), y: data.readUInt32BE(4), unit: data[8] })

describe('withPngResolution', () => {
  it('declares 144 dpi in a pHYs chunk right after IHDR, in pixels a metre, and keeps every other byte', () => {
    const input = png(IHDR, IDAT, IEND)
    const tagged = withPngResolution(input, EXPORT_DPI)
    expect(EXPORT_DPI).toBe(144)
    const chunks = readChunks(tagged)
    expect(chunks.map((entry) => entry.type)).toEqual(['IHDR', 'pHYs', 'IDAT', 'IEND'])
    expect(chunks.every((entry) => entry.crcMatches)).toBe(true)
    expect(physOf(chunks[1].data)).toEqual({ x: 5669, y: 5669, unit: 1 })
    // The chunk's exact bytes after the signature and IHDR (8 + 25): length 9, "pHYs", 5669 twice, the metre, the CRC.
    expect(Buffer.from(tagged.subarray(33, 54)).toString('hex')).toBe('0000000970485973000016250000162501495224f0')
    expect(Buffer.concat([tagged.subarray(0, 33), tagged.subarray(54)])).toEqual(Buffer.from(input))
  })

  it('rounds the resolution to the nearest pixel a metre', () => {
    const resolution = (dpi: number) => physOf(readChunks(withPngResolution(png(IHDR, IDAT, IEND), dpi))[1].data)
    expect(resolution(72)).toEqual({ x: 2835, y: 2835, unit: 1 }) // 2834.6
    expect(resolution(96)).toEqual({ x: 3780, y: 3780, unit: 1 }) // 3779.5
  })

  it('replaces any pHYs the encoder wrote, wherever it stood, with its own', () => {
    const encoders = chunk('pHYs', Buffer.from([0, 0, 0x0b, 0x13, 0, 0, 0x0b, 0x13, 1])) // 2835, 72 dpi
    const chunks = readChunks(withPngResolution(png(IHDR, encoders, IDAT, encoders, IEND), EXPORT_DPI))
    expect(chunks.map((entry) => entry.type)).toEqual(['IHDR', 'pHYs', 'IDAT', 'IEND'])
    expect(chunks.every((entry) => entry.crcMatches)).toBe(true)
    expect(physOf(chunks[1].data)).toEqual({ x: 5669, y: 5669, unit: 1 })
  })

  it('passes bytes that are not a PNG through unchanged', () => {
    const whole = png(IHDR, IDAT, IEND)
    for (const [name, bytes] of [
      ['text', new TextEncoder().encode('png')],
      ['nothing', new Uint8Array()],
      ['the signature alone', png()],
      ['a first chunk that is not IHDR', png(IDAT, IEND)],
      ['a chunk cut short', whole.subarray(0, whole.length - 3)],
      ['a chunk header cut short', whole.subarray(0, 8 + IHDR.length + 5)],
    ] as const) expect(withPngResolution(bytes, EXPORT_DPI), name).toBe(bytes)
  })
})

describe('chartDataNotes', () => {
  it('keeps report letters and reason sentences while limiting references to plotted values and YoY', () => {
    const dataset = structuredClone(quarterly)
    const series = dataset.series[0]
    const passed = { version: 1 as const, method: 'reported' as const, validation: 'passed' as const, reasons: [], formula: null, inputs: [] }
    series.points[0].provenance = passed
    series.points[1].provenance = { ...passed, validation: 'needs_review', reasons: ['source_conflict'] }
    series.points[1].yoy = 0.2
    series.points[1].yoy_provenance = { ...passed, method: 'calculated', validation: 'needs_review', reasons: ['legacy_calculation'] }
    series.points.push({ period: 'FY1999', value: 1, reconciled: false })
    const grouped = groupDataNotes(dataset)
    const panel = chartDataNotes(dataset, [series], grouped, true)
    expect(panel.panelNotes.map((note) => note.letter)).toEqual(['a', 'b'])
    expect(panel.exportNotes).toContain(`Note a: ${grouped.notes[0].message} Revenue, net (Q4 2024).`)
    expect(panel.exportNotes).toContain(`Note b: ${grouped.notes[1].message} Revenue, net YoY (Q4 2024).`)
    expect(panel.exportNotes.join(' ')).not.toContain('1999')
    expect(chartDataNotes(dataset, [series], grouped, false).panelNotes.map((note) => note.letter)).toEqual(['a'])
  })

  it('preserves gaps, legacy calculation labels and the cash-flow definition in standalone exports', () => {
    const dataset = structuredClone(quarterly)
    const series = dataset.series[0]
    series.concept = 'free_cash_flow'
    series.label = 'Free cash flow'
    series.points = [{ period: '2024Q4', value: 1_700_000_000, derived: true }]
    const panel = chartDataNotes(dataset, [series], groupDataNotes(dataset), false)
    expect(panel.unavailable).toEqual(['Free cash flow: unavailable for Q3 2024.'])
    expect(panel.exportNotes).toContain('Includes figures calculated by EarningsNerd.')
    expect(panel.exportNotes).toContain(FCF_DEFINITION)
    expect(panel.exportNotes.some((note) => note.includes('Not available in this dataset.'))).toBe(true)
    expect(panel.exportNotes.filter((note) => note.includes('Q3 2024'))).toHaveLength(1)
    const withoutRecordedNotes = chartDataNotes(dataset, [series], { ...groupDataNotes(dataset), noteFor: () => null }, false)
    expect(withoutRecordedNotes.exportNotes).toContain('Free cash flow: unavailable for Q3 2024.')
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

  it("draws the lockup's accent in brand-strong on the light export and brand-dark on the dark one", () => {
    const brand = (tailwindConfig as { theme: { extend: { colors: { brand: Record<string, string> } } } }).theme.extend
      .colors.brand
    expect(MARK_STAMP.fillLight).toBe(brand.strong)
    expect(MARK_STAMP.fillDark).toBe(brand.dark)
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

describe('standalone export qualification layout', () => {
  it('preserves source, gaps and disclaimer when they wrap on narrow charts', () => {
    const notes = ['Source: SEC filings. Cash flow unavailable for 2024Q2.', 'Not investment advice.']
    const lines = layoutExportNotes((text) => text.length * 7, notes, 140)
    expect(lines.join(' ')).toBe(notes.join(' '))
    expect(lines.every((line) => line.length * 7 <= 140)).toBe(true)
  })
  it('keeps long source references inside the image without dropping characters', () => {
    const text = '000132680124000012'
    const lines = layoutExportNotes((value) => value.length * 7, [text], 35)
    expect(lines.join('')).toBe(text)
    expect(lines.every((line) => line.length <= 5)).toBe(true)
  })
})

/* -------------------------------------------------------------------------
   Font embedding. jsdom's CSS parser drops a face's `src` and `unicode-range`, so the page's sheets
   are stubbed with rules shaped as a browser serializes next/font's faces. What the browser then
   paints from them is gated by tests/e2e/chart-export-fidelity.spec.ts.
------------------------------------------------------------------------- */
const MONO = '__Geist_Mono_9a1b'
const MONO_STACK = `${MONO}, __Geist_Mono_Fallback_9a1b, "Geist Mono", ui-monospace, monospace`
const LATIN = 'U+0-FF, U+131, U+152-153, U+2BB-2BC, U+2C6, U+2DA, U+2DC, U+304, U+308, U+329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD'
const LATIN_EXT = 'U+100-2BA, U+2BD-2C5, U+2C7-2CC, U+2CE-2D7, U+2DD-2FF, U+304, U+308, U+329, U+1D00-1DBF, U+1E00-1E9F, U+1EF2-1EFF, U+2020, U+20A0-20AB, U+20AD-20C0, U+2113, U+2C60-2C7F, U+A720-A7FF'
const CYRILLIC = 'U+400-45F, U+490-491, U+4B0-4B1, U+2116'

/** The page's sheets as a browser serializes next/font's: the mono family's subsets, its metric-matched
 *  local fallback, another family, a non-face rule, and a cross-origin sheet whose rules can't be read.
 *  Each test passes its own `tag`, so its faces get their own URLs (the module reads a face once per
 *  page). Returns a face file's resolved URL. */
function stubPageFaces(tag: string) {
  const sheet = { href: `http://localhost:3000/_next/static/${tag}/css/app.css` }
  const face = (descriptors: Record<string, string>) => ({
    type: 5,
    parentStyleSheet: sheet,
    style: { getPropertyValue: (name: string) => descriptors[name] ?? '' },
  })
  const mono = (subset: string, range: string) => face({
    'font-family': `"${MONO}"`, 'font-style': 'normal', 'font-weight': '100 900', 'font-display': 'swap',
    src: `url("../media/${subset}.woff2") format("woff2")`, 'unicode-range': range,
  })
  const rules = [
    mono('cyrillic', CYRILLIC),
    mono('latin-ext', LATIN_EXT),
    mono('latin', LATIN),
    face({ 'font-family': '"__Geist_Mono_Fallback_9a1b"', src: 'local("Arial")', 'size-adjust': '134.59%' }),
    face({ 'font-family': '"__Inter_5c2d"', 'font-style': 'normal', 'font-weight': '100 900', src: 'url("../media/inter-latin.woff2") format("woff2")', 'unicode-range': LATIN }),
    { type: 1, style: { getPropertyValue: () => '' } },
  ]
  const crossOrigin = { href: 'https://cdn.example.test/x.css', get cssRules(): never { throw new DOMException('cross-origin', 'SecurityError') } }
  vi.spyOn(document, 'styleSheets', 'get').mockReturnValue([crossOrigin, { ...sheet, cssRules: rules }] as never)
  return (subset: string) => `http://localhost:3000/_next/static/${tag}/media/${subset}.woff2`
}

/** Serve each face file through the mocked shared client, recording the URLs read. */
function serveFaces(fail: (url: string) => boolean = () => false) {
  const read: string[] = []
  vi.mocked(api.get).mockImplementation(async (url: string) => {
    read.push(url)
    if (fail(url)) throw new Error('network')
    return { data: new Blob([url.split('/').at(-1)!], { type: 'font/woff2' }) }
  })
  return read
}

describe('parseUnicodeRange', () => {
  it('reads single points, spans and wildcards, in either case and with or without zero padding', () => {
    expect(parseUnicodeRange('U+0000-00FF, U+0131, u+4??')).toEqual([[0, 0xff], [0x131, 0x131], [0x400, 0x4ff]])
    expect(parseUnicodeRange('U+0-FF, U+2020')).toEqual([[0, 0xff], [0x2020, 0x2020]])
  })

  it('treats a face without a range as covering every code point', () => {
    expect(parseUnicodeRange('')).toEqual([[0, 0x10ffff]])
    expect(parseUnicodeRange('  ')).toEqual([[0, 0x10ffff]])
  })
})

describe('embeddedFontFaces', () => {
  // Braced: a function returned from beforeEach runs as its teardown, and mockReset returns the mock.
  beforeEach(() => {
    vi.mocked(api.get).mockReset()
  })
  afterEach(() => vi.restoreAllMocks())

  it('embeds only the subsets whose range covers the painted characters, each keeping its descriptors', async () => {
    const url = stubPageFaces('digits')
    const read = serveFaces()
    const css = await embeddedFontFaces([{ family: MONO_STACK, text: '$10B' }, { family: MONO_STACK, text: '−18,093%' }])
    expect(read).toEqual([url('latin')])
    expect(css).toMatch(/^@font-face\{[^}]*\}$/)
    expect(css).toContain(`font-family:"${MONO}";`)
    expect(css).toContain('font-style:normal;')
    expect(css).toContain('font-weight:100 900;')
    expect(css).toContain(`unicode-range:${LATIN};`)
    expect(css).toContain('src:url("data:font/woff2;base64,')
    expect(css).not.toContain('font-display') // a descriptor the isolated image has no use for
  })

  it('embeds every subset that claims a character, so the browser falls through them as on the page', async () => {
    // Both the latin and latin-ext subsets claim U+2020; only one of the two files carries the glyph.
    const url = stubPageFaces('dagger')
    const read = serveFaces()
    const css = await embeddedFontFaces([{ family: MONO_STACK, text: '$4.2B†' }])
    expect(read.sort()).toEqual([url('latin'), url('latin-ext')].sort())
    expect(css?.match(/@font-face/g)).toHaveLength(2)
    expect(css).toContain(`unicode-range:${LATIN_EXT};`)
    expect(css).not.toContain(CYRILLIC)
  })

  it('takes the first family of the stack the page serves from a file, skipping local fallbacks', async () => {
    const url = stubPageFaces('stacks')
    const read = serveFaces()
    // The fallback family leads this stack but is served by local() only, so Geist Mono paints.
    await embeddedFontFaces([{ family: `__Geist_Mono_Fallback_9a1b, ${MONO}, monospace`, text: '0%' }])
    expect(read).toEqual([url('latin')])
    read.length = 0
    // A system stack names no served family: nothing to embed, nothing read.
    expect(await embeddedFontFaces([{ family: 'ui-monospace, Menlo, monospace', text: '0%' }])).toBe('')
    expect(read).toEqual([])
  })

  it('reads each face once however many texts and exports need it', async () => {
    stubPageFaces('once')
    const read = serveFaces()
    const texts = [{ family: MONO_STACK, text: '$1B' }, { family: MONO_STACK, text: '$2B' }]
    const first = await embeddedFontFaces(texts)
    expect(await embeddedFontFaces(texts)).toBe(first)
    expect(read).toHaveLength(1)
  })

  it('resolves null when a needed face cannot be read, and reads it again on the next export', async () => {
    const url = stubPageFaces('retry')
    let down = true
    const read = serveFaces(() => down)
    expect(await embeddedFontFaces([{ family: MONO_STACK, text: '$1B' }])).toBeNull()
    down = false
    expect(await embeddedFontFaces([{ family: MONO_STACK, text: '$1B' }])).toContain('data:font/woff2;base64,')
    expect(read).toEqual([url('latin'), url('latin')])
  })

  it('stops when the text paints in a family loaded from a sheet it cannot read', async () => {
    // A cross-origin stylesheet (a CDN) hides its rules, while the page's font set still lists its faces.
    stubPageFaces('remote')
    const read = serveFaces()
    // jsdom has no FontFaceSet; the browser's lists every face the page loads, by family.
    Object.defineProperty(document, 'fonts', { configurable: true, value: { forEach: (each: (face: { family: string }) => void) => [{ family: '"Remote Mono"' }, { family: `"${MONO}"` }].forEach(each) } })
    try {
      expect(await embeddedFontFaces([{ family: '"Remote Mono", ui-monospace, monospace', text: '$1B' }])).toBeNull()
      // A family the readable sheet serves still embeds, wherever an unreadable one stands later in its stack.
      expect(await embeddedFontFaces([{ family: `${MONO}, "Remote Mono", monospace`, text: '$1B' }])).toContain('data:font/woff2;base64,')
      expect(read).toHaveLength(1)
    } finally {
      delete (document as { fonts?: unknown }).fonts
    }
  })

  it('embeds nothing on a page that serves no webfont', async () => {
    vi.spyOn(document, 'styleSheets', 'get').mockReturnValue([] as never)
    expect(await embeddedFontFaces([{ family: MONO_STACK, text: '$1B' }])).toBe('')
    expect(api.get).not.toHaveBeenCalled()
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
  let imageSources: string[]
  // A fake <img> whose src setter resolves the decode (jsdom never fires onload).
  class FakeImage {
    onload: (() => void) | null = null
    onerror: (() => void) | null = null
    decoding = 'auto'
    set src(value: string) {
      imageSources.push(value)
      Promise.resolve().then(() => this.onload?.())
    }
  }

  let fillTexts: string[]
  let fillArgs: { text: string; maxWidth?: number }[]
  let ctx: Record<string, unknown>

  beforeEach(() => {
    imageSources = []
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

  it('names the period range last in the subtitle, from the header both renderers spread', async () => {
    const header = { ...HEADER, ...exportSourceText({ ...quarterly, period_key: 'FY2022..FY2024' }) }
    await exportPanelPng(makeContainer(), 'x.png', { dark: false, header })
    expect(fillTexts).toContain('TSLA · Cash generation · FY2022–FY2024')
    expect(fillTexts).not.toContain('TSLA · Cash generation')
  })

  it('downloads the canvas PNG at the export scale, declaring the export resolution', async () => {
    let canvasWidth = 0
    vi.mocked(HTMLCanvasElement.prototype.toBlob).mockImplementation(function (this: HTMLCanvasElement, cb: BlobCallback) {
      canvasWidth = this.width
      cb(new Blob([png(IHDR, IDAT, IEND)], { type: 'image/png' }))
    } as never)
    expect(await exportPanelPng(makeContainer(), 'x.png', { header: HEADER })).toBe(true)
    // tests/e2e/chart-export-fidelity.spec.ts compares the plot with a screenshot at 2×: tag the file, never rescale it.
    expect(EXPORT_SCALE).toBe(2)
    expect(canvasWidth).toBe(PLOT_W * EXPORT_SCALE)
    expect(downloadBlob).toHaveBeenCalledOnce()
    const [blob, filename] = vi.mocked(downloadBlob).mock.calls[0]
    expect(filename).toBe('x.png')
    expect(blob.type).toBe('image/png')
    const chunks = readChunks(new Uint8Array(await blob.arrayBuffer()))
    expect(chunks.map((entry) => entry.type)).toEqual(['IHDR', 'pHYs', 'IDAT', 'IEND'])
    expect(physOf(chunks[1].data)).toEqual({ x: 5669, y: 5669, unit: 1 })
  })

  it('stamps the EarningsNerd wordmark in the footer', async () => {
    await exportPanelPng(makeContainer(), 'x.png', { dark: false, header: HEADER })
    // Two-tone wordmark: "Earnings" (ink) + "Nerd" (sage), so the source is obvious.
    expect(fillTexts).toContain('Earnings')
    expect(fillTexts).toContain('Nerd')
  })

  it('stamps the logo lockup: the mark first, at its minimum size, then upright "Earnings" and italic 600 "Nerd" in the accent', async () => {
    // Record the paint order with the font and ink each call ran under.
    const calls: Array<{ op: string; x: number; w?: number; h?: number; font?: string; fill?: string }> = []
    // The plot is drawn at x=0 (the header test below relies on it); the footer's mark is the other image.
    ctx.drawImage = vi.fn((_image: unknown, x: number, _y: number, w?: number, h?: number) => {
      calls.push({ op: x === 0 ? 'plot' : 'mark', x, w, h })
    })
    ctx.fillText = vi.fn((text: string, x: number) => {
      fillTexts.push(text)
      calls.push({ op: text, x, font: ctx.font as string, fill: ctx.fillStyle as string })
    })
    // "Nerd" is measured in the face it is drawn in, so the lockup's right edge holds the inset.
    const measured: Record<string, string> = {}
    ctx.measureText = (text: string) => {
      measured[text] = ctx.font as string
      return { width: text.length * 7 }
    }
    await exportPanelPng(makeContainer(), 'x.png', { dark: false, header: HEADER })
    expect(measured.Nerd).toMatch(/^italic 600 14px /)
    const markIndex = calls.findIndex((c) => c.op === 'mark')
    const earningsIndex = calls.findIndex((c) => c.op === 'Earnings')
    const nerdIndex = calls.findIndex((c) => c.op === 'Nerd')
    expect(markIndex, 'the mark is stamped').toBeGreaterThanOrEqual(0)
    const mark = calls[markIndex]
    // The bare mark at 32px wide or more (25px tall); smaller would need the app tile.
    expect(mark.h).toBeGreaterThanOrEqual(25)
    expect(mark.w).toBeGreaterThanOrEqual(32)
    // Mark, then wordmark: painted first and set to the wordmark's left.
    expect(markIndex).toBeLessThan(earningsIndex)
    expect(earningsIndex).toBeLessThan(nerdIndex)
    expect(mark.x + (mark.w ?? 0)).toBeLessThanOrEqual(calls[earningsIndex].x)
    expect(calls[earningsIndex].font).toMatch(/^600 14px /)
    expect(calls[nerdIndex].font).toMatch(/^italic 600 14px /)
    expect(calls[earningsIndex].fill).toBe(EXPORT_TEXT.primary.light)
    expect(calls[nerdIndex].fill).toBe(MARK_STAMP.fillLight)
  })

  // D-039 (the founder's call): the lockup is drawn opaque in the bottom-right corner, in either theme.
  it.each([
    { dark: false, accent: MARK_STAMP.fillLight },
    { dark: true, accent: MARK_STAMP.fillDark },
  ])('stamps the lockup opaque and bottom-right (dark: $dark)', async ({ dark, accent }) => {
    const calls: Array<{ op: string; x: number; y: number; w?: number; h?: number; alpha: number; fill?: string }> = []
    ctx.drawImage = vi.fn((_image: unknown, x: number, y: number, w?: number, h?: number) => {
      calls.push({ op: x === 0 ? 'plot' : 'mark', x, y, w, h, alpha: ctx.globalAlpha as number })
    })
    ctx.fillText = vi.fn((text: string, x: number, y: number) => {
      fillTexts.push(text)
      calls.push({ op: text, x, y, alpha: ctx.globalAlpha as number, fill: ctx.fillStyle as string })
    })
    let canvasHeight = 0
    vi.mocked(HTMLCanvasElement.prototype.toBlob).mockImplementation(function (this: HTMLCanvasElement, cb: BlobCallback) {
      canvasHeight = this.height / 2 // the export's retina scale; footer geometry is in CSS px
      cb(new Blob(['png'], { type: 'image/png' }))
    } as never)
    await exportPanelPng(makeContainer(), 'x.png', { dark, header: HEADER })
    const mark = calls.find((c) => c.op === 'mark')!
    const earnings = calls.find((c) => c.op === 'Earnings')!
    const nerd = calls.find((c) => c.op === 'Nerd')!
    expect(MARK_STAMP.alpha).toBe(1)
    for (const call of [mark, earnings, nerd]) expect(call.alpha, `${call.op} is drawn opaque`).toBe(1)
    expect(nerd.fill).toBe(accent)
    expect(imageSources.at(-1)).toContain(encodeURIComponent(`fill="${accent}"`))
    // Right: the wordmark ends at the inset from the right edge (the stub measures 7px a glyph).
    expect(nerd.x + 'Nerd'.length * 7).toBe(PLOT_W - MARK_STAMP.inset)
    // Bottom: the mark sits inside the last strip of the canvas.
    expect(mark.y).toBeGreaterThanOrEqual(canvasHeight - MARK_STAMP.stripHeight)
    expect(mark.y + (mark.h ?? 0)).toBeLessThanOrEqual(canvasHeight)
    // One lockup: the mark ends exactly one wordmarkGap before "Earnings", so a mark that drifts
    // from the wordmark (another corner, a wider gap) fails here.
    expect(mark.x + (mark.w ?? 0) + MARK_STAMP.wordmarkGap).toBe(earnings.x)
    // Clear space (LOGO_README.md): one E-bar, 11 of the mark's 73.2 viewBox units, above and below.
    const clearSpace = ((mark.h ?? 0) * 11) / 73.2
    expect(mark.y - (canvasHeight - MARK_STAMP.stripHeight), 'clear space above the mark').toBeGreaterThanOrEqual(clearSpace)
    expect(canvasHeight - (mark.y + (mark.h ?? 0)), 'clear space below the mark').toBeGreaterThanOrEqual(clearSpace)
  })

  it('carries resolved text and tspan font stacks into the isolated SVG image', async () => {
    const container = makeContainer()
    const svg = container.querySelector('svg')!
    svg.setAttributeNS('http://www.w3.org/2000/xmlns/', 'xmlns', 'http://www.w3.org/2000/svg')
    svg.innerHTML = '<text font-family="var(--font-geist-mono), ui-monospace, monospace" style="font-family: var(--font-geist-mono), ui-monospace, monospace" fill="#6B7280" stroke="#FBFAF6" stroke-width="3" paint-order="stroke">$10B<tspan style="font-family: var(--font-geist-mono), Menlo, monospace">aa</tspan></text>'
    const sourceMarkup = svg.outerHTML
    const originalComputedStyle = window.getComputedStyle.bind(window)
    const families = ['"Geist Mono", ui-monospace, monospace', '"Geist Mono", Menlo, monospace']
    const sourceText = [...svg.querySelectorAll('text, tspan')]
    // jsdom does not resolve custom-property inheritance. Supply the browser's computed
    // result, then inspect what the real export passes across the isolated-image boundary.
    vi.spyOn(window, 'getComputedStyle').mockImplementation((element, pseudo) => {
      const style = originalComputedStyle(element, pseudo)
      const index = sourceText.indexOf(element)
      if (index >= 0) Object.defineProperty(style, 'fontFamily', { value: families[index] })
      return style
    })
    expect(await exportPanelPng(container, 'font.png')).toBe(true)
    const markup = decodeURIComponent(imageSources[0].split(',').slice(1).join(','))
    const isolated = new DOMParser().parseFromString(markup, 'image/svg+xml')
    expect(isolated.querySelector('parsererror')?.textContent).toBeUndefined()
    expect([...isolated.querySelectorAll('text, tspan')].map(text => (text as SVGTextContentElement).style.fontFamily)).toEqual(families)
    expect([...isolated.querySelectorAll('text, tspan')].map(text => text.getAttribute('font-family'))).toEqual(families)
    expect(markup).not.toContain('var(')
    expect(isolated.documentElement.textContent).toBe('$10Baa')
    expect(isolated.querySelector('text')?.getAttribute('stroke')).toBe('#FBFAF6')
    expect(isolated.querySelector('text')?.getAttribute('stroke-width')).toBe('3')
    expect(isolated.querySelector('text')?.getAttribute('paint-order')).toBe('stroke')
    expect(svg.outerHTML).toBe(sourceMarkup)
  })

  /** A plot whose text resolves to the Geist Mono stack, as the browser computes it from the variable. */
  function monoContainer(text: string): HTMLElement {
    const container = makeContainer()
    const svg = container.querySelector('svg')!
    svg.setAttributeNS('http://www.w3.org/2000/xmlns/', 'xmlns', 'http://www.w3.org/2000/svg') // jsdom serializes it once only so
    svg.innerHTML = `<style>.x{}</style><text font-family="var(--font-geist-mono), monospace">${text}</text>`
    const originalComputedStyle = window.getComputedStyle.bind(window)
    vi.spyOn(window, 'getComputedStyle').mockImplementation((element, pseudo) => {
      const style = originalComputedStyle(element, pseudo)
      if (element.tagName === 'text') Object.defineProperty(style, 'fontFamily', { value: MONO_STACK })
      return style
    })
    return container
  }

  it('carries the faces the plot paints with into the isolated SVG image, ahead of everything else', async () => {
    stubPageFaces('export')
    serveFaces()
    expect(await exportPanelPng(monoContainer('$10B'), 'font.png')).toBe(true)
    const isolated = new DOMParser().parseFromString(decodeURIComponent(imageSources[0].split(',').slice(1).join(',')), 'image/svg+xml')
    const first = isolated.documentElement.firstElementChild!
    expect(first.tagName).toBe('style')
    expect(first.textContent).toMatch(new RegExp(`^@font-face\\{font-family:"${MONO}";.*src:url\\("data:font/woff2;base64,[^"]+"\\);\\}$`))
    expect(downloadBlob).toHaveBeenCalledOnce()
  })

  it('draws the loaded image when decode() rejects after load, as WebKit has done for SVG images', async () => {
    class DecodeRejects extends FakeImage {
      decode = () => Promise.reject(new DOMException('decode failed', 'EncodingError'))
    }
    vi.stubGlobal('Image', DecodeRejects)
    expect(await exportPanelPng(makeContainer(), 'x.png', { header: HEADER })).toBe(true)
    expect(ctx.drawImage).toHaveBeenCalled()
    expect(downloadBlob).toHaveBeenCalledOnce()
  })

  it('stops, downloading nothing, rather than paint the plot in a fallback font', async () => {
    stubPageFaces('export-down')
    serveFaces(() => true)
    expect(await exportPanelPng(monoContainer('$10B'), 'font.png')).toBe(false)
    expect(imageSources).toEqual([]) // the plot was never rasterized
    expect(downloadBlob).not.toHaveBeenCalled()
  })

  it('renders source, missing periods and disclaimer into the downloaded image', async () => {
    await exportPanelPng(makeContainer(), 'x.png', { header: { ...HEADER,
      sourceNote: 'Source: SEC filings · data as of 2024-02-02',
      notes: ['Operating cash flow: unavailable for 2024Q2.'],
      disclosure: 'Research only. Not investment advice.',
    } })
    expect(fillTexts.join(' ')).toContain('Source: SEC filings · data as of 2024-02-02')
    expect(fillTexts.join(' ')).toContain('Operating cash flow: unavailable for 2024Q2.')
    expect(fillTexts.join(' ')).toContain('Research only. Not investment advice.')
    expect(downloadBlob).toHaveBeenCalledOnce()
  })

  // A card's inks here are unlike either theme's, so a header or footer that kept the default would show.
  it.each([
    { name: 'the theme’s text inks by default', dark: true, ink: undefined, primary: EXPORT_TEXT.primary.dark, secondary: EXPORT_TEXT.secondary.dark },
    { name: 'the light theme’s by default', dark: false, ink: undefined, primary: EXPORT_TEXT.primary.light, secondary: EXPORT_TEXT.secondary.light },
    { name: 'a dark card’s own inks when it passes them', dark: true, ink: { primary: '#123456', secondary: '#654321' }, primary: '#123456', secondary: '#654321' },
    { name: 'a light card’s own inks when it passes them', dark: false, ink: { primary: '#123456', secondary: '#654321' }, primary: '#123456', secondary: '#654321' },
  ])('paints the header and notes in $name', async ({ dark, ink, primary, secondary }) => {
    const fills = new Map<string, string>()
    ctx.fillText = vi.fn((text: string) => fills.set(text, ctx.fillStyle as string))
    await exportPanelPng(makeContainer(), 'x.png', { dark, ink, header: { ...HEADER, sourceNote: 'Source: SEC filings', notes: ['A note.'] } })
    expect(fills.get('Tesla, Inc.')).toBe(primary)
    for (const text of ['TSLA · Cash generation', 'Operating CF', 'Source: SEC filings', 'A note.']) expect(fills.get(text), text).toBe(secondary)
    // The footer's wordmark keeps the theme's own ink.
    expect(fills.get('Earnings')).toBe(dark ? EXPORT_TEXT.primary.dark : EXPORT_TEXT.primary.light)
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
