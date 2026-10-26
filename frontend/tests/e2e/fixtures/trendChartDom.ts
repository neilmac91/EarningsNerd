/**
 * The trend charts as analysis-layout.spec.ts reads them: the spec renderer's data attributes (TrendChartSvg's
 * data-text and data-plot, its marks' data-series). Each reader runs in the page, so it is self-contained.
 */
import { expect, type Page } from '@playwright/test'

/** The page's four charts once each has drawn. The spec renderer adds its SVG only once Geist Mono's latin and
 *  latin-ext faces have loaded, or 1,500 ms have passed (G4, G3), after the chart's own element; the gallery waits for
 *  it the same way. */
export async function drawnCharts(page: Page) {
  const charts = page.locator('[data-analysis-chart]')
  await expect(charts).toHaveCount(4)
  await expect(page.locator('[data-analysis-chart] > svg'), 'each chart has drawn').toHaveCount(4)
  return charts
}

/** A period's x tick as the renderer prints it, with the typographic apostrophe ("Q3’23"). */
export const tickText = (period: string) => `${period.slice(4)}’${period.slice(2, 4)}`

/** Each chart's x tick labels, whether their glyphs are painted, and the geometry of its plotted marks. */
export function readTicksAndShapes(charts: Element[]) {
  return charts.map((chart) => ({
    name: chart.getAttribute('data-analysis-chart'),
    ticks: [...chart.querySelectorAll(':scope > svg text[data-text="x"]')].map((tick) => {
      const glyphs = [tick, ...tick.querySelectorAll('text,tspan')].filter((glyph) => !glyph.querySelector('tspan') && glyph.textContent?.trim())
      return {
        text: tick.textContent?.replace(/\s/g, '') ?? '',
        painted: glyphs.length > 0 && glyphs.every((glyph) => {
          const box = glyph.getBoundingClientRect()
          const style = getComputedStyle(glyph)
          return glyph.checkVisibility({ visibilityProperty: true, opacityProperty: true })
            && box.width > 0 && box.height > 0 && style.fill !== 'none' && Number(style.fillOpacity) > 0
        }),
      }
    }),
    // Rendered line/bar geometry makes this stronger than a period-count attribute.
    shapes: [...chart.querySelectorAll(':scope > svg [data-series]:not(text)')].map((shape) => ['d', 'x', 'y', 'width', 'height', 'cx', 'cy', 'points'].map((attr) => shape.getAttribute(attr))),
  }))
}

/** Each chart's y tick labels: drawn on one line, inside the axis that holds them, and whether the chart scrolls.
 *  The renderer sets every label 8 px left of its plot (D5), on one axis a panel. */
export function readAxes(charts: Element[]) {
  return charts.map((chart) => {
    const viewport = chart.closest('[data-analysis-chart-scroll]')!
    const svg = chart.querySelector(':scope > svg')!.getBoundingClientRect()
    const labels = [...chart.querySelectorAll(':scope > svg text[data-text="tick"]')]
    const gridLeft = svg.left + Number(chart.querySelector('g[data-plot]')!.getAttribute('data-plot')!.split(' ')[0])
    return {
      name: chart.getAttribute('data-analysis-chart'),
      scrolls: viewport.scrollWidth > viewport.clientWidth + 1,
      labels: labels.map((label) => label.textContent ?? ''),
      // The renderer prints each label as one text, no tspan.
      broken: labels.filter((label) => label.querySelectorAll('tspan').length !== 0).map((label) => label.textContent),
      outside: labels.flatMap((label) => {
        const box = label.getBoundingClientRect()
        const inside = box.left >= svg.left - 0.5 && box.right <= gridLeft - 8 + 0.5
        return inside ? [] : [`${label.textContent} at ${Math.round(box.left - svg.left)}–${Math.round(box.right - svg.left)} of ${Math.round(svg.width)}`]
      }),
    }
  })
}

/** Each chart's slot between x ticks and its painted x tick labels. */
export function readSlots(charts: Element[]) {
  return charts.map((chart) => {
    const viewport = chart.closest('[data-analysis-chart-scroll]')!
    const ticks = [...chart.querySelectorAll(':scope > svg text[data-text="x"]')]
    const xs = ticks.map((tick) => Number(tick.getAttribute('x')))
    return {
      name: chart.getAttribute('data-analysis-chart'),
      slot: Math.min(...xs.slice(1).map((x, i) => x - xs[i])),
      ticks: ticks.filter((tick) => tick.textContent?.trim()).length,
      scrolls: viewport.scrollWidth > viewport.clientWidth + 1,
    }
  })
}
