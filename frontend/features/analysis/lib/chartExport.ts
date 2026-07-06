import type { AnalysisDataset } from '@/features/analysis/api/analysis-api'
import { downloadBlob } from '@/lib/downloadBlob'

/**
 * Dependency-free chart PNG export (audit enhancement 2): SVG serialization → canvas
 * rasterization. Downloads go through the shared lib/downloadBlob helper (its delayed revoke
 * matters — a synchronous revoke can abort the download on Safari/Firefox). Tabular export is
 * the branded Excel workbook, built server-side (`exportAnalysisXlsx`).
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

/**
 * Rasterize the panel's rendered SVG to a 2× PNG and download it.
 *
 * Known limitation (documented in the audit): the SVG is rasterized in an isolated image
 * document, where webfonts (Geist Mono) don't load — axis labels fall back to the system
 * monospace in CHART_FONT's stack. Metrics are close; embedding the font as a data URI is the
 * upgrade path if pixel-identical text ever matters.
 */
export async function exportPanelPng(
  container: HTMLElement,
  filename: string
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

  const source = new XMLSerializer().serializeToString(clone)
  const svgUrl = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(source)}`

  const image = new Image()
  image.decoding = 'sync'
  const loaded = new Promise<boolean>((resolve) => {
    image.onload = () => resolve(true)
    image.onerror = () => resolve(false)
  })
  image.src = svgUrl
  if (!(await loaded)) return false

  const scale = 2 // retina-crisp output
  const canvas = document.createElement('canvas')
  canvas.width = width * scale
  canvas.height = height * scale
  const ctx = canvas.getContext('2d')
  if (!ctx) return false
  ctx.fillStyle = resolveBackground(container)
  ctx.fillRect(0, 0, canvas.width, canvas.height)
  ctx.scale(scale, scale)
  ctx.drawImage(image, 0, 0, width, height)

  const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/png'))
  if (!blob) return false
  downloadBlob(blob, filename)
  return true
}
