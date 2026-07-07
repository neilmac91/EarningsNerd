import type { AnalysisDataset } from '@/features/analysis/api/analysis-api'
import { downloadBlob } from '@/lib/downloadBlob'

/**
 * Dependency-free chart PNG export (audit enhancement 2): SVG serialization → canvas
 * rasterization, finished with a subtle EarningsNerd mark bottom-right (owner request — branding
 * on shared chart images, "subtle, not in your face"). Downloads go through the shared
 * lib/downloadBlob helper (its delayed revoke matters — a synchronous revoke can abort the
 * download on Safari/Firefox). Tabular export is the branded Excel workbook, built server-side
 * (`exportAnalysisXlsx`).
 */

export function exportFilename(dataset: AnalysisDataset, suffix: string, ext: string): string {
  const slug = suffix.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
  return `${dataset.ticker}_${dataset.period_key.replace(/\.\./g, '-')}_${slug}.${ext}`
}

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
} as const

/** Draw the branded footer strip: plot-matched background, EN mark bottom-right. Failure =
 *  export proceeds without the mark (never block a download over branding); the strip itself is
 *  already painted by the caller's background fill. Coordinates are CSS px — the caller's retina
 *  scale is already applied. */
async function drawBrandFooter(
  ctx: CanvasRenderingContext2D,
  width: number,
  plotHeight: number,
  dark: boolean
): Promise<void> {
  const mark = await loadSvgImage(buildMarkSvg(dark ? MARK_STAMP.fillDark : MARK_STAMP.fillLight))
  if (!mark) return
  const h = MARK_STAMP.markHeight
  const w = (h * MARK_WIDTH) / MARK_HEIGHT
  const y = plotHeight + (MARK_STAMP.stripHeight - h) / 2
  ctx.save()
  ctx.globalAlpha = MARK_STAMP.alpha
  ctx.drawImage(mark, width - w - MARK_STAMP.inset, y, w, h)
  ctx.restore()
}

/**
 * Rasterize the panel's rendered SVG to a 2× PNG (theme-matched background, watermarked) and
 * download it.
 *
 * Known limitation (documented in the audit): the SVG is rasterized in an isolated image
 * document, where webfonts (Geist Mono) don't load — axis labels fall back to the system
 * monospace in CHART_FONT's stack. Metrics are close; embedding the font as a data URI is the
 * upgrade path if pixel-identical text ever matters.
 */
export async function exportPanelPng(
  container: HTMLElement,
  filename: string,
  { dark = false }: { dark?: boolean } = {}
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
  canvas.width = width * scale
  canvas.height = (height + MARK_STAMP.stripHeight) * scale
  const ctx = canvas.getContext('2d')
  if (!ctx) return false
  ctx.fillStyle = resolveBackground(container)
  ctx.fillRect(0, 0, canvas.width, canvas.height)
  ctx.scale(scale, scale)
  ctx.drawImage(image, 0, 0, width, height)
  await drawBrandFooter(ctx, width, height, dark)

  const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/png'))
  if (!blob) return false
  downloadBlob(blob, filename)
  return true
}
