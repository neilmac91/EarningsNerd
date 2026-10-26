import type { AnalysisDataset } from '@/features/analysis/api/analysis-api'
import api from '@/lib/api/client'
import { downloadBlob } from '@/lib/downloadBlob'
import { formatInstant } from '@/lib/format'

/** The PNG header's source line and disclosure, the same under every chart renderer. The source data's sync time, an
 *  instant, prints as the day it falls on in the reader's zone (DataNotes prints the long form). */
export function exportSourceText(dataset: AnalysisDataset): { sourceNote: string; disclosure: string } {
  const sourceDate = formatInstant(dataset.data_as_of, 'MMM d, yyyy')
  return {
    sourceNote: `Source: SEC filings via EarningsNerd · ${sourceDate ? `data as of ${sourceDate}` : 'source refresh time unavailable'}`,
    disclosure: 'Research only. Not investment advice. Data may contain errors or omissions. earningsnerd.io/terms',
  }
}

/**
 * Dependency-free chart PNG export (audit enhancement 2): SVG serialization → canvas
 * rasterization, framed so a shared image is self-describing — a HEADER (company name, then
 * ticker · metric, then the series legend; the chart's SVG carries the plot only, never the
 * legend/title, which live in the card's HTML header) and a branded FOOTER (the EN mark plus the
 * "EarningsNerd" wordmark, so a viewer knows the source). Downloads go through the shared
 * lib/downloadBlob helper (its delayed revoke matters — a synchronous revoke can abort the
 * download on Safari/Firefox). Tabular export is the branded Excel workbook, built server-side
 * (`exportAnalysisXlsx`).
 */

export function exportFilename(dataset: AnalysisDataset, suffix: string, ext: string): string {
  const slug = suffix.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
  return `${dataset.ticker}_${dataset.period_key.replace(/\.\./g, '-')}_${slug}.${ext}`
}

// System-first sans — identical intent to the app's `body` stack (see tailwind.config.js:
// "-apple-system first BY DESIGN"). System fonts are synchronously available, so the canvas-drawn
// header and footer measureText/fillText deterministically without waiting on a webfont. (The plot's
// own Geist Mono travels inside its SVG image: embeddedFontFaces.)
const BRAND_FONT = '-apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", Roboto, system-ui, sans-serif'
const font = (weight: number, size: number) => `${weight} ${size}px ${BRAND_FONT}`

/** Nearest non-transparent ancestor background — the theme's actual panel color, so a dark-mode
 *  PNG isn't exported transparent (or white) behind the plot. */
function resolveBackground(el: HTMLElement): string {
  let node: HTMLElement | null = el
  while (node) {
    const bg = getComputedStyle(node).backgroundColor
    if (bg && bg !== 'transparent' && bg !== 'rgba(0, 0, 0, 0)') return bg
    node = node.parentElement
  }
  return '#ffffff'
}

/** Rasterize SVG markup in an isolated image document (data URI keeps the canvas untainted).
 *  Resolves null on load failure so callers can degrade instead of throwing. Waits for `decode()`
 *  where the browser has it, so embedded fonts have painted before the canvas draws the image; a
 *  `decode()` that rejects after the image loaded is not fatal, and the loaded image is drawn. */
async function loadSvgImage(markup: string): Promise<HTMLImageElement | null> {
  const image = new Image()
  image.decoding = 'sync'
  const loaded = new Promise<boolean>((resolve) => {
    image.onload = () => resolve(true)
    image.onerror = () => resolve(false)
  })
  image.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(markup)}`
  if (!(await loaded)) return null
  if (typeof image.decode === 'function') await image.decode().catch(() => undefined)
  return image
}

/** Code-point ranges of a `unicode-range` descriptor ("U+0000-00FF, U+0131, U+4??"); an empty
 *  descriptor covers every code point. Exported for tests. */
export function parseUnicodeRange(descriptor: string): [number, number][] {
  if (!descriptor.trim()) return [[0, 0x10ffff]]
  return descriptor.split(',').flatMap((part): [number, number][] => {
    const token = part.trim().replace(/^u\+/i, '')
    if (!token) return []
    if (token.includes('?')) return [[parseInt(token.replace(/\?/g, '0'), 16), parseInt(token.replace(/\?/g, 'f'), 16)]]
    const [start, end = start] = token.split('-')
    return [[parseInt(start, 16), parseInt(end, 16)]]
  })
}

const familyNames = (stack: string) => stack.split(',').map((name) => name.trim().replace(/^["']|["']$/g, '').toLowerCase()).filter(Boolean)

const fontFaceRules = (): CSSFontFaceRule[] => [...document.styleSheets].flatMap((sheet) => {
  try {
    return [...sheet.cssRules].filter((rule): rule is CSSFontFaceRule =>
      (typeof CSSFontFaceRule !== 'undefined' && rule instanceof CSSFontFaceRule) || rule.type === 5)
  } catch {
    return [] // a cross-origin sheet keeps its rules; the app's own fonts are same-origin (next/font)
  }
})

const faceDataCache = new Map<string, Promise<string | null>>()

/** A face file as a data URI, read once per page (several panels may export). Null on any failure. */
function faceDataUri(url: string): Promise<string | null> {
  let pending = faceDataCache.get(url)
  if (!pending) {
    // Through the shared client like every request (an absolute same-origin URL overrides its API base).
    pending = api.get<Blob>(url, { responseType: 'blob' })
      .then((response) => response.data)
      .then((blob) => new Promise<string | null>((resolve) => {
        const reader = new FileReader()
        reader.onload = () => resolve(typeof reader.result === 'string' ? reader.result : null)
        reader.onerror = () => resolve(null)
        reader.readAsDataURL(blob)
      }))
      .catch(() => null)
      .then((uri) => {
        if (!uri) faceDataCache.delete(url) // a later export may retry a failed read
        return uri
      })
    faceDataCache.set(url, pending)
  }
  return pending
}

/**
 * The page's webfont faces that the plot's text paints with, as `@font-face` rules whose sources are
 * data URIs: a webfont never loads into the isolated image document on its own, so without them the
 * PNG's plot drew in the platform monospace (1.5–1.7% of its pixels differed from the screen). For
 * each text, the first family of its resolved stack that the page serves from a file is the family it
 * paints in; of that family's faces, those whose `unicode-range` covers one of the text's characters
 * are embedded, each keeping that range, without which the subsets would shadow one another (latin-ext
 * carries † alone). Resolves null when a needed face cannot be read, or when the text paints in a
 * family the page loads from a stylesheet this script cannot read (one served from another origin):
 * the export then stops rather than paint a fallback. Exported for tests.
 */
export async function embeddedFontFaces(texts: { family: string; text: string }[]): Promise<string | null> {
  const rules = fontFaceRules()
  const declared = new Set(rules.map((rule) => familyNames(rule.style.getPropertyValue('font-family'))[0]))
  // The page's font set holds every face it loads, those of an unreadable sheet among them.
  const loaded = new Set<string>()
  if (typeof document.fonts?.forEach === 'function') document.fonts.forEach((face) => loaded.add(familyNames(face.family)[0]))
  const faces = rules.flatMap((rule) => {
    const source = /url\(\s*["']?([^"')]+)["']?\s*\)/.exec(rule.style.getPropertyValue('src'))
    return source ? [{ rule, url: new URL(source[1], rule.parentStyleSheet?.href ?? document.baseURI).href }] : []
  })
  const served = new Set(faces.map((face) => familyNames(face.rule.style.getPropertyValue('font-family'))[0]))
  const needed = new Map<string, (typeof faces)[number]>()
  for (const { family, text } of texts) {
    const codePoints = [...text].map((character) => character.codePointAt(0)!)
    const stack = familyNames(family)
    const at = stack.findIndex((candidate) => served.has(candidate) || (loaded.has(candidate) && !declared.has(candidate)))
    if (at < 0) continue // a system stack: the image paints it as the page does
    const name = stack[at]
    if (!served.has(name)) return null
    for (const face of faces) {
      if (familyNames(face.rule.style.getPropertyValue('font-family'))[0] !== name) continue
      const ranges = parseUnicodeRange(face.rule.style.getPropertyValue('unicode-range'))
      if (codePoints.some((point) => ranges.some(([start, end]) => point >= start && point <= end))) needed.set(face.url, face)
    }
  }
  const embedded: string[] = []
  for (const { rule, url } of needed.values()) {
    const uri = await faceDataUri(url)
    if (!uri) return null
    const descriptors = ['font-family', 'font-style', 'font-weight', 'font-stretch', 'unicode-range']
      .map((property) => [property, rule.style.getPropertyValue(property)] as const)
      .filter(([, value]) => value)
      .map(([property, value]) => `${property}:${value};`)
    embedded.push(`@font-face{${descriptors.join('')}src:url("${uri}");}`)
  }
  return embedded.join('')
}

// The EN monogram geometry — public/assets/earningsnerd-mark-sage.svg with the fill
// parameterized. Inlined (not fetched) so the stamp can't fail on a network/CSP hiccup and the
// canvas stays untainted.
const MARK_WIDTH = 94.6
const MARK_HEIGHT = 73.2

export function buildMarkSvg(fill: string): string {
  return (
    `<svg viewBox="0 0 ${MARK_WIDTH} ${MARK_HEIGHT}" width="${MARK_WIDTH}" height="${MARK_HEIGHT}" xmlns="http://www.w3.org/2000/svg">` +
    '<g transform="translate(0,-14.8)">' +
    '<path d="M2.8 28L26.2 28Q29 28 29 30.8L29 36.2Q29 39 26.2 39L12.9 39Q11.5 39 11.5 40.4L11.5 42.1Q11.5 43.5 12.9 43.5L23.2 43.5Q26 43.5 26 46.3L26 51.7Q26 54.5 23.2 54.5L12.9 54.5Q11.5 54.5 11.5 55.9L11.5 57.6Q11.5 59 12.9 59L26.2 59Q29 59 29 61.8L29 67.2Q29 70 26.2 70L2.8 70Q0 70 0 67.2L0 30.8Q0 28 2.8 28Z" fill="' +
    fill +
    '"></path>' +
    '<g transform="translate(0.92,6.98) scale(0.9193)">' +
    '<path d="M36.98 84.42L49.76 58.87Q50.65 57.08 51.54 58.87L65.21 86.2Q66.11 88 68.13 88L68.57 88Q70.59 88 71.49 86.2L93.87 41.43Q95.66 37.86 92.09 36.07L84.21 32.13Q80.64 30.34 78.85 33.92L69.24 53.13Q68.35 54.92 67.46 53.13L53.79 25.8Q52.89 24 50.87 24L50.43 24Q48.41 24 47.51 25.8L18.2 84.42Q16.41 88 20.41 88L31.19 88Q35.19 88 36.98 84.42Z" fill="' +
    fill +
    '"></path>' +
    '<path d="M101.76 42.95L101.05 12.49Q100.96 8.49 97.7 10.81L72.91 28.53Q69.65 30.85 73.23 32.64L98.27 45.16Q101.85 46.95 101.76 42.95Z" fill="' +
    fill +
    '"></path>' +
    '</g></g></svg>'
  )
}

/** Brand footer geometry — exported for tests. A slim strip UNDER the plot (not an in-plot
 *  overlay: live acceptance showed an overlaid mark colliding with the right-axis tick text and
 *  drowning against a same-hue bar — a footer is legible on every panel/theme with zero data
 *  collision). */
export const MARK_STAMP = {
  stripHeight: 33, // 25px mark plus one E-bar of clear space (11/73.2 of its height, 3.76px) above and below
  markHeight: 25, // about 32px wide: the bare mark's minimum size (smaller needs the app tile)
  inset: 12,
  alpha: 1, // opaque, bottom-right: the founder's call (decisions-log D-039), never a translucent watermark
  fillLight: '#3C6650', // brand-strong (the mark's own sage)
  fillDark: '#7FB295', // brand-dark: lightened sage, legible on the dark panel without glowing
  wordmarkSize: 14, // "EarningsNerd" wordmark after the mark
  wordmarkGap: 9, // mark → wordmark
} as const

/** Canvas mirrors of the text tokens (canvas draws hexes, not CSS vars): the footer's ink, and the header's and
 *  notes' unless the card passes its own (ExportInk). Gated in chart-export.spec against tailwind.config.js's
 *  `text.primary`/`text.secondary` so a palette change can't silently drift this copy (rule 12:
 *  the mirror is a machine-checked gate, not three comment-guarded literals a grep can't see). */
export const EXPORT_TEXT = {
  primary: { light: '#1A1A17', dark: '#EAECEF' },
  secondary: { light: '#374151', dark: '#D1D5DB' },
} as const

/** The two inks the header and notes paint: the company in `primary`, the subtitle, legend names and notes in
 *  `secondary`. A card whose own text takes other inks passes them (the trend charts' spec renderer passes its
 *  legend values' and legend names' inks, spec §3.8, which equal these since E194); otherwise the export takes
 *  EXPORT_TEXT for its theme. */
export interface ExportInk {
  primary: string
  secondary: string
}
const exportInk = (dark: boolean): ExportInk => (dark
  ? { primary: EXPORT_TEXT.primary.dark, secondary: EXPORT_TEXT.secondary.dark }
  : { primary: EXPORT_TEXT.primary.light, secondary: EXPORT_TEXT.secondary.light })

/** Draw the branded footer strip bottom-right, opaque, as the logo's lockup: the EN mark, then the
 *  "EarningsNerd" wordmark (like the site logo: upright ink "Earnings" + italic 600 sage "Nerd", so a
 *  shared image names its source rather than an ambiguous monogram). A mark decode failure still
 *  leaves the wordmark (branding never blocks a download). Coordinates are CSS px — the caller's
 *  retina scale is already applied. `footerTop` is the y where the strip begins (below the plot). */
async function drawBrandFooter(
  ctx: CanvasRenderingContext2D,
  width: number,
  footerTop: number,
  dark: boolean
): Promise<void> {
  const accent = dark ? MARK_STAMP.fillDark : MARK_STAMP.fillLight
  const ink = dark ? EXPORT_TEXT.primary.dark : EXPORT_TEXT.primary.light // the wordmark's "Earnings"
  const mark = await loadSvgImage(buildMarkSvg(accent))
  const markW = mark ? (MARK_STAMP.markHeight * MARK_WIDTH) / MARK_HEIGHT : 0
  const centerY = footerTop + MARK_STAMP.stripHeight / 2

  const upright = font(600, MARK_STAMP.wordmarkSize)
  const italic = `italic ${upright}` // the wordmark's "Nerd" (components/EarningsNerdLogo.tsx)

  ctx.save()
  ctx.globalAlpha = MARK_STAMP.alpha
  ctx.textBaseline = 'middle'
  ctx.textAlign = 'left'
  ctx.font = upright
  const w1 = ctx.measureText('Earnings').width
  ctx.font = italic
  const w2 = ctx.measureText('Nerd').width
  const textLeft = width - MARK_STAMP.inset - (w1 + w2)
  const lockupLeft = textLeft - (mark ? markW + MARK_STAMP.wordmarkGap : 0)
  // Skip the wordmark on a pathologically narrow export rather than overrun the left edge.
  const withWordmark = lockupLeft > MARK_STAMP.inset
  if (mark) {
    const markX = withWordmark ? lockupLeft : width - markW - MARK_STAMP.inset
    const markY = footerTop + (MARK_STAMP.stripHeight - MARK_STAMP.markHeight) / 2
    ctx.drawImage(mark, markX, markY, markW, MARK_STAMP.markHeight)
  }
  if (withWordmark) {
    ctx.font = upright
    ctx.fillStyle = ink
    ctx.fillText('Earnings', textLeft, centerY)
    ctx.font = italic
    ctx.fillStyle = accent
    ctx.fillText('Nerd', textLeft + w1, centerY)
  }
  ctx.restore()
}

/* ---------------------------------------------------------------------------
   Header strip — company, ticker · metric, and the series legend. The chart's
   <svg> carries the plot only; the company/metric/legend live outside it (the
   page picker and the card's heading and legend), so an exported PNG that
   serializes the SVG alone is unidentifiable. Redraw them onto the canvas from
   the same data that drives the UI, so a shared image says which company, which
   metric, and which series — with no drift from what the user saw.
--------------------------------------------------------------------------- */

/** One legend entry — label + its swatch color (the card's own legend, as TrendChartCard passes it
 *  from the chart model, so the image and the screen name the same series). */
export interface ChartLegendItem {
  label: string
  color: string
}

/** The self-describing frame drawn above the plot on export. */
export interface ChartExportHeader {
  /** Company name — the anchor identity (e.g. "Tesla, Inc."). */
  company: string
  /** Ticker (e.g. "TSLA") — paired with the metric in the subtitle. */
  ticker: string
  /** The panel/metric title (e.g. "Cash generation"). */
  title: string
  legend: ChartLegendItem[]
  sourceNote?: string
  disclosure?: string
  notes?: string[]
}

/** Header geometry — exported for tests. Three tiers mirroring a captioned financial chart:
 *  company (bold, text.primary), "ticker · metric" (medium, text.secondary), then the legend
 *  (text-xs with an 8–9px rounded swatch). Values in CSS px; the caller's retina scale is applied
 *  on top. */
export const HEADER_STAMP = {
  padX: 16,
  padTop: 14,
  padBottom: 14,
  companySize: 15,
  subtitleSize: 12,
  lineGap: 4, // company → subtitle
  legendGap: 11, // subtitle → first legend row
  legendSize: 12,
  swatch: 9,
  swatchRadius: 2,
  swatchGap: 6, // swatch → label (mirrors gap-1.5)
  itemGap: 16, // between legend items
  rowGap: 7, // between wrapped legend rows
} as const

const LEGEND_ROW_H = Math.max(HEADER_STAMP.legendSize, HEADER_STAMP.swatch)

/** A legend item with its measured label width — cached at layout time so the draw pass never
 *  re-measures (identical widths guaranteed). */
type LaidOutItem = ChartLegendItem & { width: number }

/**
 * Greedy line-wrap of the legend into rows that fit `maxWidth`. Pure (measurement injected) so the
 * wrap math is unit-testable without a canvas. An item wider than the whole row still lands on its
 * own row rather than looping forever. Exported for tests.
 */
export function layoutLegend(
  measure: (label: string) => number,
  legend: ChartLegendItem[],
  maxWidth: number
): LaidOutItem[][] {
  const rows: LaidOutItem[][] = []
  let row: LaidOutItem[] = []
  let x = 0
  for (const item of legend) {
    const width = measure(item.label)
    const itemWidth = HEADER_STAMP.swatch + HEADER_STAMP.swatchGap + width
    // Wrap only a non-empty row (an over-wide lone item stays on its own row rather than looping).
    // Every item after the first in a row is preceded by itemGap.
    if (row.length > 0 && x + HEADER_STAMP.itemGap + itemWidth > maxWidth) {
      rows.push(row)
      row = []
      x = 0
    }
    x += (row.length > 0 ? HEADER_STAMP.itemGap : 0) + itemWidth
    row.push({ ...item, width })
  }
  if (row.length > 0) rows.push(row)
  return rows
}

/** Total header-strip height: the company + subtitle lines are always present; `numRows` of legend
 *  add on top (0 = header without a legend, mirroring a single-series panel). */
export function headerHeight(numRows: number): number {
  let h =
    HEADER_STAMP.padTop +
    HEADER_STAMP.companySize +
    HEADER_STAMP.lineGap +
    HEADER_STAMP.subtitleSize
  if (numRows > 0) {
    h += HEADER_STAMP.legendGap + numRows * LEGEND_ROW_H + (numRows - 1) * HEADER_STAMP.rowGap
  }
  return h + HEADER_STAMP.padBottom
}

/** Wrap export qualifications without dropping words, even on a narrow mobile chart. */
export function layoutExportNotes(measure: (text: string) => number, paragraphs: string[], maxWidth: number): string[] {
  const lines: string[] = []
  for (const paragraph of paragraphs) {
    let line = ''
    for (const word of paragraph.trim().split(/\s+/)) {
      if (line && measure(`${line} ${word}`) > maxWidth) { lines.push(line); line = '' }
      // Long source dates/identifiers must not run off the edge either.
      let part = word
      while (measure(part) > maxWidth && part.length > 1) {
        let length = 1
        while (length < part.length && measure(part.slice(0, length + 1)) <= maxWidth) length += 1
        if (line) { lines.push(line); line = '' }
        lines.push(part.slice(0, length))
        part = part.slice(length)
      }
      line = line ? `${line} ${part}` : part
    }
    if (line) lines.push(line)
  }
  return lines
}

/** Fill a rounded swatch (falls back to a square where roundRect is unavailable — a 2px radius on
 *  a 9px square is imperceptible, so the fallback never reads as broken). */
function fillSwatch(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  size: number,
  radius: number,
  color: string
): void {
  ctx.fillStyle = color
  const rr = (ctx as CanvasRenderingContext2D & { roundRect?: unknown }).roundRect
  if (typeof rr === 'function') {
    ctx.beginPath()
    ctx.roundRect(x, y, size, size, radius)
    ctx.fill()
  } else {
    ctx.fillRect(x, y, size, size)
  }
}

/** Draw the company + "ticker · metric" subtitle + pre-laid-out legend rows into the top strip.
 *  Colors mirror the on-screen tokens: company = text.primary, subtitle/legend = text.secondary, or the card's own
 *  inks (ExportInk).
 *  `maxWidth` on each fillText condenses (never clips) a pathologically long string — a no-op for
 *  real company/metric names. */
function drawHeader(
  ctx: CanvasRenderingContext2D,
  header: ChartExportHeader,
  rows: LaidOutItem[][],
  width: number,
  { primary, secondary }: ExportInk
): void {
  const maxW = Math.max(1, width - 2 * HEADER_STAMP.padX)

  ctx.textBaseline = 'alphabetic'
  let top = HEADER_STAMP.padTop

  // Company — the anchor identity.
  ctx.font = font(600, HEADER_STAMP.companySize)
  ctx.fillStyle = primary
  ctx.fillText(header.company, HEADER_STAMP.padX, top + HEADER_STAMP.companySize, maxW)
  top += HEADER_STAMP.companySize + HEADER_STAMP.lineGap

  // Subtitle — "{ticker} · {metric}".
  const subtitle = header.ticker ? `${header.ticker} · ${header.title}` : header.title
  ctx.font = font(500, HEADER_STAMP.subtitleSize)
  ctx.fillStyle = secondary
  ctx.fillText(subtitle, HEADER_STAMP.padX, top + HEADER_STAMP.subtitleSize, maxW)
  top += HEADER_STAMP.subtitleSize

  if (rows.length === 0) return

  // Legend.
  top += HEADER_STAMP.legendGap
  ctx.font = font(400, HEADER_STAMP.legendSize)
  let rowTop = top
  for (const row of rows) {
    let x = HEADER_STAMP.padX
    for (const item of row) {
      const swatchY = rowTop + (LEGEND_ROW_H - HEADER_STAMP.swatch) / 2
      fillSwatch(ctx, x, swatchY, HEADER_STAMP.swatch, HEADER_STAMP.swatchRadius, item.color)
      x += HEADER_STAMP.swatch + HEADER_STAMP.swatchGap
      ctx.fillStyle = secondary
      ctx.textBaseline = 'middle'
      // maxWidth guard, uniform with the company/subtitle tiers: an over-wide lone label (wrapped
      // to its own row by layoutLegend) condenses instead of clipping past the strip's right edge.
      ctx.fillText(item.label, x, rowTop + LEGEND_ROW_H / 2, Math.max(1, width - x - HEADER_STAMP.padX))
      x += item.width + HEADER_STAMP.itemGap
    }
    rowTop += LEGEND_ROW_H + HEADER_STAMP.rowGap
  }
}

/**
 * Rasterize the panel's rendered SVG to a 2× PNG and download it: a company/metric/legend header,
 * the plot, then a branded footer — so the shared image is self-describing and sourced. Pass
 * `header` (company + ticker + metric title + the card's legend, from its chart model) to draw the frame;
 * omit it and the export degrades to the bare plot + footer.
 *
 * The SVG plot is rasterized in an isolated image document, where the page's CSS variables and
 * webfonts don't reach: each text node's font stack is resolved before serialization, and the
 * Geist Mono faces its characters need travel inside the SVG as data URIs (embeddedFontFaces), so
 * the PNG's plot paints the same glyphs as the screen. A face that cannot be read stops the export
 * (resolves false) rather than paint a fallback. The header/footer text is drawn directly on the
 * canvas (main document), so it uses the system sans immediately — no webfont wait.
 */
export async function exportPanelPng(
  container: HTMLElement,
  filename: string,
  { dark = false, header, ink = exportInk(dark) }: { dark?: boolean; header?: ChartExportHeader; ink?: ExportInk } = {}
): Promise<boolean> {
  const svg = container.querySelector('svg')
  if (!svg) return false
  const rect = svg.getBoundingClientRect()
  const width = Math.max(1, Math.round(rect.width))
  const height = Math.max(1, Math.round(rect.height))

  const clone = svg.cloneNode(true) as SVGSVGElement
  clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg')
  clone.setAttribute('width', String(width))
  clone.setAttribute('height', String(height))
  const sourceText = svg.querySelectorAll('text, tspan')
  const painted: { family: string; text: string }[] = []
  clone.querySelectorAll<SVGTextContentElement>('text, tspan').forEach((text, index) => {
    const computedFamily = getComputedStyle(sourceText[index]).fontFamily
    const family = computedFamily && !computedFamily.includes('var(') ? computedFamily : 'monospace'
    // Inline styles override existing presentation attributes. Replace both so the isolated
    // SVG, including nested tspans, contains no unresolved font variable or inherited page CSS.
    text.style.fontFamily = family
    text.setAttribute('font-family', family)
    painted.push({ family, text: text.textContent ?? '' })
  })
  const faces = await embeddedFontFaces(painted)
  if (faces == null) return false
  if (faces) {
    const style = document.createElementNS('http://www.w3.org/2000/svg', 'style')
    style.textContent = faces
    clone.insertBefore(style, clone.firstChild)
  }

  const image = await loadSvgImage(new XMLSerializer().serializeToString(clone))
  if (!image) return false

  const scale = 2 // retina-crisp output
  const canvas = document.createElement('canvas')
  const ctx = canvas.getContext('2d')
  if (!ctx) return false

  // Lay the legend out first (needs a font-set ctx to measure) so the header height — and thus the
  // canvas height — is known before we size the canvas. Sizing the canvas resets ctx state, so
  // everything below re-applies scale + fonts.
  let headH = 0
  let legendRows: LaidOutItem[][] = []
  if (header) {
    ctx.font = font(400, HEADER_STAMP.legendSize)
    legendRows = layoutLegend(
      (label) => ctx.measureText(label).width,
      header.legend,
      width - 2 * HEADER_STAMP.padX
    )
    headH = headerHeight(legendRows.length)
  }
  ctx.font = font(400, HEADER_STAMP.subtitleSize)
  const notes = header ? [header.sourceNote, ...(header.notes ?? []), header.disclosure].filter((note): note is string => !!note) : []
  const noteLines = layoutExportNotes((label) => ctx.measureText(label).width, notes, Math.max(1, width - 2 * HEADER_STAMP.padX))
  const noteLineHeight = 18
  const noteHeight = noteLines.length ? 16 + noteLines.length * noteLineHeight : 0

  canvas.width = width * scale
  canvas.height = (headH + height + noteHeight + MARK_STAMP.stripHeight) * scale
  ctx.fillStyle = resolveBackground(container)
  ctx.fillRect(0, 0, canvas.width, canvas.height)
  ctx.scale(scale, scale)
  if (header) drawHeader(ctx, header, legendRows, width, ink)
  ctx.drawImage(image, 0, headH, width, height)
  ctx.font = font(400, HEADER_STAMP.subtitleSize)
  ctx.fillStyle = ink.secondary
  ctx.textBaseline = 'top'
  noteLines.forEach((line, index) => ctx.fillText(line, HEADER_STAMP.padX, headH + height + 8 + index * noteLineHeight))
  await drawBrandFooter(ctx, width, headH + height + noteHeight, dark)

  const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/png'))
  if (!blob) return false
  downloadBlob(blob, filename)
  return true
}
