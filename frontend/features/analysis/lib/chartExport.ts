import type { AnalysisDataset } from '@/features/analysis/api/analysis-api'
import { downloadBlob } from '@/lib/downloadBlob'

/**
 * Dependency-free chart PNG export (audit enhancement 2): SVG serialization → canvas
 * rasterization, framed so a shared image is self-describing — a HEADER (company name, then
 * ticker · metric, then the series legend; the Recharts SVG carries the plot only, never the
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
// "-apple-system first BY DESIGN"). System fonts are synchronously available, so canvas
// measureText/fillText render deterministically without waiting on a webfont (the Geist webfont
// never resolves inside the isolated SVG image doc anyway — the module's documented limitation).
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
 *  Resolves null on decode failure so callers can degrade instead of throwing. */
async function loadSvgImage(markup: string): Promise<HTMLImageElement | null> {
  const image = new Image()
  image.decoding = 'sync'
  const loaded = new Promise<boolean>((resolve) => {
    image.onload = () => resolve(true)
    image.onerror = () => resolve(false)
  })
  image.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(markup)}`
  return (await loaded) ? image : null
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
  stripHeight: 32,
  markHeight: 20,
  inset: 12,
  alpha: 0.85,
  fillLight: '#3C6650', // brand-strong (the mark's own sage)
  fillDark: '#7FB295', // lightened sage — legible on the dark panel without glowing
  wordmarkSize: 14, // "EarningsNerd" wordmark next to the mark
  wordmarkGap: 9, // wordmark → mark
} as const

/** Canvas mirrors of the text tokens (canvas draws hexes, not CSS vars) — the single source for
 *  every ink the header/footer paint. Gated in chart-export.spec against tailwind.config.js's
 *  `text.primary`/`text.secondary` so a palette change can't silently drift this copy (rule 12:
 *  the mirror is a machine-checked gate, not three comment-guarded literals a grep can't see). */
export const EXPORT_TEXT = {
  primary: { light: '#1A1A17', dark: '#D7DADC' },
  secondary: { light: '#374151', dark: '#9CA3AF' },
} as const

/** Draw the branded footer strip bottom-right: the "EarningsNerd" wordmark (two-tone like the site
 *  logo — ink "Earnings" + sage "Nerd", so a shared image names its source rather than an
 *  ambiguous monogram) followed by the EN mark. A mark decode failure still leaves the wordmark
 *  (branding never blocks a download). Coordinates are CSS px — the caller's retina scale is
 *  already applied. `footerTop` is the y where the strip begins (below the plot). */
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

  ctx.save()
  ctx.globalAlpha = MARK_STAMP.alpha
  ctx.font = font(600, MARK_STAMP.wordmarkSize)
  ctx.textBaseline = 'middle'
  ctx.textAlign = 'left'
  const w1 = ctx.measureText('Earnings').width
  const w2 = ctx.measureText('Nerd').width
  const markX = width - markW - MARK_STAMP.inset
  const textRight = markX - (mark ? MARK_STAMP.wordmarkGap : 0)
  const textLeft = textRight - (w1 + w2)
  // Skip the wordmark on a pathologically narrow export rather than overrun the left edge.
  if (textLeft > MARK_STAMP.inset) {
    ctx.fillStyle = ink
    ctx.fillText('Earnings', textLeft, centerY)
    ctx.fillStyle = accent
    ctx.fillText('Nerd', textLeft + w1, centerY)
  }
  if (mark) {
    const markY = footerTop + (MARK_STAMP.stripHeight - MARK_STAMP.markHeight) / 2
    ctx.drawImage(mark, markX, markY, markW, MARK_STAMP.markHeight)
  }
  ctx.restore()
}

/* ---------------------------------------------------------------------------
   Header strip — company, ticker · metric, and the series legend. The Recharts
   <svg> carries the plot only; the company/metric/legend live outside it (the
   page picker + TrendCharts' <h3>/PanelLegend), so an exported PNG that
   serializes the SVG alone is unidentifiable. Redraw them onto the canvas from
   the same data that drives the UI, so a shared image says which company, which
   metric, and which series — with no drift from what the user saw.
--------------------------------------------------------------------------- */

/** One legend entry — label + its swatch color (exactly the shared `legendItems` the panel
 *  passes to both its on-screen PanelLegend and its plotted series). */
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
 *  Colors mirror the on-screen tokens: company = text.primary, subtitle/legend = text.secondary.
 *  `maxWidth` on each fillText condenses (never clips) a pathologically long string — a no-op for
 *  real company/metric names. */
function drawHeader(
  ctx: CanvasRenderingContext2D,
  header: ChartExportHeader,
  rows: LaidOutItem[][],
  width: number,
  dark: boolean
): void {
  const primary = dark ? EXPORT_TEXT.primary.dark : EXPORT_TEXT.primary.light
  const secondary = dark ? EXPORT_TEXT.secondary.dark : EXPORT_TEXT.secondary.light
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
 * `header` (company + ticker + metric title + the panel's shared `legendItems`) to draw the frame;
 * omit it and the export degrades to the bare plot + footer.
 *
 * Known limitation (documented in the audit): the SVG plot is rasterized in an isolated image
 * document, where webfonts (Geist Mono) don't load — axis labels fall back to the system
 * monospace in CHART_FONT's stack. The header/footer text is drawn directly on the canvas (main
 * document), so it uses the system sans immediately — no webfont wait. Metrics are close;
 * embedding the font as a data URI is the upgrade path if pixel-identical axis text ever matters.
 */
export async function exportPanelPng(
  container: HTMLElement,
  filename: string,
  { dark = false, header }: { dark?: boolean; header?: ChartExportHeader } = {}
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

  canvas.width = width * scale
  canvas.height = (headH + height + MARK_STAMP.stripHeight) * scale
  ctx.fillStyle = resolveBackground(container)
  ctx.fillRect(0, 0, canvas.width, canvas.height)
  ctx.scale(scale, scale)
  if (header) drawHeader(ctx, header, legendRows, width, dark)
  ctx.drawImage(image, 0, headH, width, height)
  await drawBrandFooter(ctx, width, headH + height, dark)

  const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/png'))
  if (!blob) return false
  downloadBlob(blob, filename)
  return true
}
