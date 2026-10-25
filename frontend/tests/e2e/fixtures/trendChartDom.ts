/**
 * The trend charts as analysis-layout.spec.ts reads them, from either renderer: the spec renderer's data attributes
 * when the build sets NEXT_PUBLIC_CHARTS_V2 (TrendChartSvg's data-text and data-plot, its marks' data-series), and
 * today's Recharts layers otherwise, the selectors that spec read before step 6 (E194). Each reader runs in the page,
 * so it is self-contained and takes the renderer as its argument. Step 7 (E195) deletes the Recharts branches with
 * Recharts.
 */
import { expect, type Page } from '@playwright/test'

/** The build under test draws the spec renderer: the e2e-charts-v2 job builds, serves and tests with the flag. */
export const CHARTS_V2 = process.env.NEXT_PUBLIC_CHARTS_V2 === 'true'

/** Today's Recharts layers that the keyboard and notes case reads, on Recharts alone (E195 retires the case). */
export const RECHARTS = { bars: '.recharts-bar-rectangle path', tooltip: '.recharts-tooltip-wrapper' } as const

/** The page's four charts once each has drawn. The spec renderer adds its SVG only once Geist Mono has loaded, or
 *  1,500 ms have passed (G4), after the chart's own element; the gallery waits for it the same way. */
export async function drawnCharts(page: Page) {
  const charts = page.locator('[data-analysis-chart]')
  await expect(charts).toHaveCount(4)
  if (CHARTS_V2) await expect(page.locator('[data-analysis-chart] > svg'), 'each chart has drawn').toHaveCount(4)
  return charts
}

/** A period's x tick as each renderer prints it: the spec's typographic apostrophe ("Q3’23"), Recharts' ASCII one. */
export const tickText = (period: string, v2: boolean) => `${period.slice(4)}${v2 ? '’' : "'"}${period.slice(2, 4)}`

/** Each chart's x tick labels, whether their glyphs are painted, and the geometry of its plotted marks. */
export function readTicksAndShapes(charts: Element[], v2: boolean) {
  return charts.map((chart) => ({
    name: chart.getAttribute('data-analysis-chart'),
    // Recharts renders tick lines and labels in separate layers. Inspect the painted label layer: counting the line
    // groups can pass with twelve empty strings. The spec renderer names its x labels' role.
    ticks: [...chart.querySelectorAll(v2 ? ':scope > svg text[data-text="x"]' : '.recharts-xAxis-tick-labels .recharts-cartesian-axis-tick-label')].map((tick) => {
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
    shapes: v2
      ? [...chart.querySelectorAll(':scope > svg [data-series]:not(text)')].map((shape) => ['d', 'x', 'y', 'width', 'height', 'cx', 'cy', 'points'].map((attr) => shape.getAttribute(attr)))
      : [...chart.querySelectorAll('.recharts-line-curve,.recharts-area-curve,.recharts-bar-rectangle path,.recharts-bar-rectangle rect')].map((shape) => ['d', 'x', 'y', 'width', 'height'].map((attr) => shape.getAttribute(attr))),
  }))
}

/** Each chart's y tick labels: drawn on one line, inside the axis that holds them, and whether the chart scrolls.
 *  Recharts sizes each value axis from its labels and keeps an 8 px left and 16 px right margin; the spec renderer
 *  sets every label 8 px left of its plot (D5), on one axis a panel. */
export function readAxes(charts: Element[], v2: boolean) {
  return charts.map((chart) => {
    const viewport = chart.closest('[data-analysis-chart-scroll]')!
    const svgElement = chart.querySelector(v2 ? ':scope > svg' : 'svg.recharts-surface')!
    const svg = svgElement.getBoundingClientRect()
    const labels = [...chart.querySelectorAll(v2 ? ':scope > svg text[data-text="tick"]' : '.recharts-yAxis-tick-labels .recharts-cartesian-axis-tick-label')]
    const gridLeft = v2 ? svg.left + Number(chart.querySelector('g[data-plot]')!.getAttribute('data-plot')!.split(' ')[0]) : chart.querySelector('.recharts-cartesian-grid')!.getBoundingClientRect().left
    return {
      name: chart.getAttribute('data-analysis-chart'),
      scrolls: viewport.scrollWidth > viewport.clientWidth + 1,
      labels: labels.map((label) => label.textContent ?? ''),
      // Recharts wraps a label at a space into tspans; the spec renderer prints each as one text, no tspan.
      broken: labels.filter((label) => label.querySelectorAll('tspan').length !== (v2 ? 0 : 1)).map((label) => label.textContent),
      outside: labels.flatMap((label) => {
        const box = label.getBoundingClientRect()
        const inside = v2
          ? box.left >= svg.left - 0.5 && box.right <= gridLeft - 8 + 0.5
          : box.right <= gridLeft + 1 ? box.left >= svg.left + 8 - 0.5 : box.right <= svg.right - 16 + 0.5
        return inside ? [] : [`${label.textContent} at ${Math.round(box.left - svg.left)}–${Math.round(box.right - svg.left)} of ${Math.round(svg.width)}`]
      }),
    }
  })
}

/** Each chart's width a period (Recharts' grid over its periods, the spec renderer's slot between x ticks) and its
 *  painted x tick labels. */
export function readSlots(charts: Element[], { v2, periods }: { v2: boolean; periods: number }) {
  return charts.map((chart) => {
    const viewport = chart.closest('[data-analysis-chart-scroll]')!
    const ticks = [...chart.querySelectorAll(v2 ? ':scope > svg text[data-text="x"]' : '.recharts-xAxis-tick-labels .recharts-cartesian-axis-tick-label')]
    const xs = ticks.map((tick) => Number(tick.getAttribute('x')))
    return {
      name: chart.getAttribute('data-analysis-chart'),
      slot: v2 ? Math.min(...xs.slice(1).map((x, i) => x - xs[i])) : chart.querySelector('.recharts-cartesian-grid')!.getBoundingClientRect().width / periods,
      ticks: ticks.filter((tick) => tick.textContent?.trim()).length,
      scrolls: viewport.scrollWidth > viewport.clientWidth + 1,
    }
  })
}
