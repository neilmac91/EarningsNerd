import type { AnalysisDataset, AnalysisSeries } from '@/features/analysis/api/analysis-api'
import { windowGrowth, windowRange } from '@/features/analysis/lib/growth'
import { downloadBlob } from '@/lib/downloadBlob'

/**
 * Dependency-free chart/table export (audit enhancement 2): PNG via SVG serialization →
 * canvas rasterization, CSV straight from the deterministic dataset. Downloads go through the
 * shared lib/downloadBlob helper (its delayed revoke matters — a synchronous revoke can abort
 * the download on Safari/Firefox).
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

const csvField = (value: string): string =>
  /[",\n]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value

/**
 * The whole dataset as CSV: one row per series, one column per period, plus the window figure
 * (CAGR for monetary series, pp change for percent series — the shared windowGrowth rule).
 * Values are RAW numbers (full precision, machine-usable in Excel); percent-series values are
 * the ×100 percentages exactly as the dataset stores them. A fully-computed Q4 column is marked
 * in its HEADER (" (computed Q4)") so derived estimates stay flagged without breaking the
 * numeric cells.
 */
export function datasetToCsv(dataset: AnalysisDataset): string {
  const derivedPeriods = new Set(
    dataset.periods
      .filter((period) =>
        dataset.series.some((s) =>
          s.points.some((p) => p.period === period.key && p.derived && p.value !== null)
        )
      )
      .map((period) => period.key)
  )
  const header = [
    'Metric',
    'Concept',
    'Unit',
    // "contains", not "is": balance-sheet instants in a Q4 column are real reported values
    // even when the flow rows are computed — the on-screen grid daggers per cell, a CSV can
    // only annotate the header.
    ...dataset.periods.map((p) =>
      derivedPeriods.has(p.key) ? `${p.key} (contains computed Q4 values)` : p.key
    ),
    'Window growth',
    'Window',
  ]

  const rows = dataset.series.map((series: AnalysisSeries) => {
    const byPeriod = new Map(series.points.map((p) => [p.period, p]))
    const win = windowGrowth(series)
    const window = windowRange(series)
    return [
      csvField(series.label),
      series.concept,
      csvField(series.unit + (series.percent ? ' (×100 percent)' : '')),
      ...dataset.periods.map((period) => {
        const value = byPeriod.get(period.key)?.value
        return value === null || value === undefined ? '' : String(value)
      }),
      win.value === null ? '' : `${String(win.value)}${win.isPercent ? ' pp' : ''}`,
      window ?? '',
    ].join(',')
  })

  return [header.map(csvField).join(','), ...rows].join('\n') + '\n'
}

export function downloadDatasetCsv(dataset: AnalysisDataset): void {
  const csv = datasetToCsv(dataset)
  // BOM: the CSV carries non-ASCII ("×100 percent") and Excel on Windows only decodes UTF-8
  // when the file leads with one.
  downloadBlob(
    new Blob(['﻿', csv], { type: 'text/csv;charset=utf-8' }),
    exportFilename(dataset, `${dataset.mode}-metrics`, 'csv')
  )
}