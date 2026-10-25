import { expect, test, type Locator } from '@playwright/test'
import { openAnalysis, type AnalysisTheme } from './fixtures/analysisLayoutApi'

/**
 * The trend charts' spec renderer in a browser (NEXT_PUBLIC_CHARTS_V2, E192, E193): how the route loads it, and how a
 * reader reads a chart (docs/design/analysis-trend-charts-spec-2026-10.md §3.9, §3.13, D13; DESIGN_SYSTEM.md §10): one
 * values stop a chart, the period walk with its tooltip and column wash in view, the pointer and touch, Escape, and the
 * tooltip's contrast and reflow under 200% text; and the states §3.9 and §3.10 add (E200): the bones a plot holds while
 * its font loads, the export busy while a PNG is drawn, and the plot row running to its new height on a toggle. The DOM checks of the drawing itself (D1–D3, D5, D6, D8–D10, D14, M6,
 * M19) run on the gallery, charts-v2-gallery.spec.ts, through fixtures/chartChecks.ts. CI's e2e-charts-v2 job builds
 * with the flag set; the main e2e job's build has it unset, and these cases skip there, where one case holds that the
 * flag-off route loads none of the renderer.
 */
const enabled = process.env.NEXT_PUBLIC_CHARTS_V2 === 'true'
const THEMES: AnalysisTheme[] = ['light', 'dark']
test.describe.configure({ mode: 'parallel' })
// Full font hinting, headless Chrome's default (CI's) and some desktops': at 1x it snaps every advance to a whole
// pixel unless the SVG asks for geometric precision, so D1 and D8 run in the case that can break them. The local
// browser's wrapper passes --font-render-hinting=none; the last flag wins.
test.use({ launchOptions: { args: ['--font-render-hinting=full'] } })

test.describe('trend charts with the flag unset', () => {
  test.use({ viewport: { width: 1280, height: 900 }, reducedMotion: 'reduce', serviceWorkers: 'block' })

  test('today’s charts draw, and the route loads none of the spec renderer', async ({ page, baseURL }) => {
    test.skip(enabled, 'Run against a server built with the flag unset, as production is.')
    // The renderer is its own chunk (TrendCharts' next/dynamic import); its panel attribute names it.
    const scripts: Promise<[string, string]>[] = []
    page.on('response', (response) => {
      const url = response.url()
      if (url.includes('/_next/static/') && url.endsWith('.js')) scripts.push(response.text().then((body) => [url, body]))
    })
    await openAnalysis(page, baseURL!, 'captured', 'light')
    await expect(page.locator('[data-analysis-chart] svg.recharts-surface')).toHaveCount(4)
    await expect(page.locator('g[data-panel]')).toHaveCount(0)
    const loaded = await Promise.all(scripts)
    expect(loaded.length).toBeGreaterThan(0)
    expect(loaded.filter(([, body]) => body.includes('data-axis-domain')).map(([url]) => url), 'scripts carrying the spec renderer').toEqual([])
  })
})

test.describe('trend charts v2 when the renderer’s chunk fails to load', () => {
  test.use({ viewport: { width: 1280, height: 900 }, reducedMotion: 'reduce', serviceWorkers: 'block' })

  test('the grid says the charts could not be drawn, and the rest of the analysis stands', async ({ page, baseURL }) => {
    test.skip(!enabled, 'Build and serve with NEXT_PUBLIC_CHARTS_V2=true, and set it for this test process.')
    // A stale client after a deploy: every script that carries the renderer fails to arrive.
    const aborted: string[] = []
    await page.route('**/_next/static/**/*.js', async (route) => {
      const response = await route.fetch()
      const body = await response.text()
      if (body.includes('data-axis-domain')) {
        aborted.push(route.request().url())
        await route.abort('failed')
      } else {
        await route.fulfill({ response, body })
      }
    })
    await openAnalysis(page, baseURL!, 'captured', 'light')
    // The chunk loader retries once before it gives up, so the fallback takes a few seconds.
    await expect(page.getByText('These charts could not be drawn.')).toBeVisible({ timeout: 15_000 })
    expect(aborted.length, 'the renderer’s chunk was requested and refused').toBeGreaterThan(0)
    await expect(page.locator('[data-analysis-chart]')).toHaveCount(0)
    await expect(page.getByRole('heading', { level: 1, name: 'Multi-Period Analysis' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Metrics by period' })).toBeVisible()
  })
})

/** WCAG's relative-luminance contrast of two computed colours ("rgb(…)"; an alpha ink is mixed over the ground). */
function contrast(ink: string, ground: string): number {
  const parse = (value: string) => value.match(/[\d.]+/g)!.map(Number)
  const [gr, gg, gb] = parse(ground)
  const [r, g, b, a = 1] = parse(ink)
  const mixed = [r * a + gr * (1 - a), g * a + gg * (1 - a), b * a + gb * (1 - a)]
  const luminance = ([x, y, z]: number[]) => {
    const [lx, ly, lz] = [x, y, z].map((channel) => {
      const c = channel / 255
      return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
    })
    return 0.2126 * lx + 0.7152 * ly + 0.0722 * lz
  }
  const [hi, lo] = [luminance(mixed), luminance([gr, gg, gb])].sort((p, q) => q - p)
  return (hi + 0.05) / (lo + 0.05)
}

/** How far a box runs past the viewport's sides (0 or less when it lies inside). */
async function overrun(viewport: Locator, target: Locator) {
  const [frame, box] = await Promise.all([viewport.boundingBox(), target.boundingBox()])
  if (!frame || !box) return Number.POSITIVE_INFINITY
  return Math.max(frame.x - box.x, box.x + box.width - frame.x - frame.width)
}

for (const theme of THEMES) for (const width of [1280, 390]) {
  test.describe(`trend charts v2 / reading a chart / ${theme} / ${width}px`, () => {
    test.use({ viewport: { width, height: 900 }, colorScheme: theme, reducedMotion: 'reduce', serviceWorkers: 'block' })

    test('one values stop a chart: Tab enters, reads the newest period, leaves and returns, under the brand ring', async ({ page, baseURL }) => {
      test.skip(!enabled, 'Build and serve with NEXT_PUBLIC_CHARTS_V2=true, and set it for this test process.')
      test.setTimeout(90_000)
      await openAnalysis(page, baseURL!, 'captured', theme)
      for (const viewport of await page.locator('[data-analysis-chart-scroll]').all()) {
        const card = viewport.locator('xpath=ancestor::section[1]')
        const overflow = await viewport.evaluate((element) => element.scrollWidth > element.clientWidth + 1)
        if (overflow) {
          await expect(viewport).toHaveAttribute('role', 'region')
          await expect(viewport).toHaveAttribute('tabindex', '0')
          await expect(viewport).toHaveAccessibleName(/chart\. Scroll horizontally to view all periods\./)
        } else {
          await expect(viewport).not.toHaveAttribute('role')
          await expect(viewport).not.toHaveAttribute('tabindex')
        }
        const stop = card.getByRole('slider', { name: /chart values$/ })
        await expect(stop).toHaveCount(1)
        // The values stop is a layer over the viewport: its box is the viewport's, and nothing in the plot takes a Tab.
        expect(await viewport.locator('[tabindex]').count(), 'no Tab stop inside the plot').toBe(0)
        const [frame, layer] = await Promise.all([viewport.boundingBox(), stop.boundingBox()])
        expect(Math.max(Math.abs(frame!.x - layer!.x), Math.abs(frame!.width - layer!.width), Math.abs(frame!.y - layer!.y))).toBeLessThanOrEqual(0.5)
        const newest = await stop.getAttribute('aria-valuemax')
        await card.getByRole('button', { name: /^(Expand|Collapse) chart$/ }).focus()
        await page.keyboard.press('Tab')
        if (overflow) {
          await expect(viewport).toBeFocused()
          expect(await viewport.evaluate((element) => getComputedStyle(element).boxShadow), 'the region’s own ring').not.toBe('none')
          await page.keyboard.press('Tab')
        }
        await expect(stop).toBeFocused()
        await expect(stop).toHaveAttribute('aria-valuenow', newest!)
        expect(await stop.evaluate((element) => getComputedStyle(element).boxShadow), 'the stop’s brand ring, around the viewport').not.toBe('none')
        const tooltip = card.locator('[data-chart-tooltip]')
        await expect(tooltip).toBeVisible()
        await expect(tooltip).toHaveAttribute('aria-hidden', 'true')
        expect(await overrun(viewport, tooltip), 'the tooltip lies inside the viewport').toBeLessThanOrEqual(0.5)
        expect(await overrun(viewport, card.locator('[data-chart-wash]')), 'the period’s column lies inside the viewport').toBeLessThanOrEqual(0.5)
        await page.keyboard.press('Tab')
        expect(await page.evaluate(() => document.activeElement?.closest('[data-analysis-chart-scroll]') ?? null)).toBeNull()
        await expect(tooltip).toHaveCount(0)
        await page.keyboard.press('Shift+Tab')
        await expect(stop).toBeFocused()
        if (overflow) {
          await page.keyboard.press('Shift+Tab')
          await expect(viewport).toBeFocused()
        }
      }
    })

    test('the period walk keeps its column and tooltip in view; a pointer reads without scrolling; Escape in two steps', async ({ page, baseURL }) => {
      test.skip(!enabled, 'Build and serve with NEXT_PUBLIC_CHARTS_V2=true, and set it for this test process.')
      test.setTimeout(120_000)
      await openAnalysis(page, baseURL!, 'captured', theme)
      const card = page.locator('section:has([data-analysis-chart])').first()
      const viewport = card.locator('[data-analysis-chart-scroll]')
      const stop = card.getByRole('slider')
      const tooltip = card.locator('[data-chart-tooltip]')
      const wash = card.locator('[data-chart-wash]')
      const gutter = card.locator('[data-chart-gutter] svg')
      const last = Number(await stop.getAttribute('aria-valuemax'))
      const settle = () => viewport.evaluate(async (element) => {
        let previous = element.scrollLeft
        for (let stable = 0, frame = 0; frame < 90 && stable < 5; frame++) {
          await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()))
          stable = Math.abs(element.scrollLeft - previous) < 0.1 ? stable + 1 : 0
          previous = element.scrollLeft
        }
      })
      /** The column lies in the plot's visible part: inside the viewport and clear of the sticky gutter. */
      const columnInView = async () => {
        await settle()
        const [frame, column, axis] = await Promise.all([viewport.boundingBox(), wash.boundingBox(), gutter.count().then((n) => (n ? gutter.boundingBox() : null))])
        const covered = axis ? Number(await card.locator('[data-chart-gutter] rect').first().getAttribute('width')) : 0
        return Math.max(frame!.x + covered - column!.x, column!.x + column!.width - frame!.x - frame!.width)
      }
      await card.getByRole('button', { name: 'Expand chart', exact: true }).focus()
      await page.keyboard.press('Tab')
      if (await viewport.getAttribute('tabindex')) await page.keyboard.press('Tab')
      await expect(stop).toBeFocused()
      for (let index = last; index >= 0; index--) {
        if (index < last) await page.keyboard.press('ArrowLeft')
        await expect(stop).toHaveAttribute('aria-valuenow', String(index))
        const valueText = (await stop.getAttribute('aria-valuetext'))!
        const header = (await tooltip.locator('p').textContent())!
        // The value text speaks what the tooltip shows: its period first, the end date spelled out.
        expect(valueText.startsWith(header.split(' · ')[0])).toBe(true)
        expect(valueText).not.toMatch(/[·—−]|\d[KMBT]\b/)
        expect(await columnInView(), `period ${index}: its column lies in the visible plot`).toBeLessThanOrEqual(0.5)
        expect(await overrun(viewport, tooltip), `period ${index}: its tooltip lies inside the viewport`).toBeLessThanOrEqual(0.5)
      }
      await page.keyboard.press('ArrowLeft')
      await expect(card.getByRole('status')).toHaveText('Oldest period.')
      await page.keyboard.press('End')
      await expect(stop).toHaveAttribute('aria-valuenow', String(last))
      await page.keyboard.press('ArrowRight')
      await expect(card.getByRole('status')).toHaveText('Newest period.')
      await page.keyboard.press('Home')
      await expect(stop).toHaveAttribute('aria-valuenow', '0')
      // Leaving and returning after the viewport moved: the kept period is brought back into view.
      await page.keyboard.press('Tab')
      await viewport.evaluate((element) => { element.scrollLeft = element.scrollWidth })
      await page.keyboard.press('Shift+Tab')
      await expect(stop).toBeFocused()
      await expect(stop).toHaveAttribute('aria-valuenow', '0')
      expect(await columnInView(), 'the kept period, revealed on return').toBeLessThanOrEqual(0.5)

      // A pointer reads the period under it without moving focus or the scroll; resting on the tooltip keeps it. The
      // pointer comes in under the keyboard's tooltip, which a pointer resting on would keep.
      const header = () => tooltip.locator('p').textContent()
      const target = await viewport.evaluate((element) => {
        const frame = element.getBoundingClientRect()
        return { x: frame.right - 30, y: frame.top + 260, left: element.scrollLeft }
      })
      await page.mouse.move(target.x, target.y)
      const hovered = await header()
      await expect(stop).toBeFocused()
      await expect(stop).toHaveAttribute('aria-valuenow', '0')
      expect(hovered!.split(' · ')[0], 'the pointer’s period, not the keyboard’s').not.toBe((await stop.getAttribute('aria-valuetext'))!.split(',')[0])
      expect(Math.abs(await viewport.evaluate((element) => element.scrollLeft) - target.left), 'pointing never scrolls').toBeLessThanOrEqual(0.5)
      // Up the column to the tooltip's middle, then across onto it: the tooltip sits flush beside its column.
      const tip = (await tooltip.boundingBox())!
      await page.mouse.move(target.x, tip.y + tip.height / 2, { steps: 4 })
      expect(await header()).toBe(hovered)
      await page.mouse.move(tip.x + tip.width / 2, tip.y + tip.height / 2, { steps: 8 })
      expect(await header(), 'the tooltip is hoverable (WCAG 1.4.13)').toBe(hovered)
      // The next key resumes the keyboard's own period.
      await page.keyboard.press('ArrowRight')
      await expect(stop).toHaveAttribute('aria-valuenow', '1')
      await expect(tooltip.locator('p')).not.toHaveText(hovered!)
      // Escape dismisses the pointer's tooltip; in an expanded card it then collapses it and returns focus.
      await page.mouse.move(target.x, target.y + 10)
      await expect(tooltip).toBeVisible()
      await expect(tooltip.locator('p')).toHaveText(hovered!)
      await card.getByRole('button', { name: 'Expand chart', exact: true }).click()
      await expect(card.getByRole('button', { name: 'Collapse chart', exact: true })).toBeFocused()
      await page.mouse.move(0, 0)
      await page.keyboard.press('Tab')
      if (await viewport.getAttribute('tabindex')) await page.keyboard.press('Tab')
      await expect(stop).toBeFocused()
      await expect(tooltip).toBeVisible()
      await page.keyboard.press('Escape')
      await expect(tooltip).toHaveCount(0)
      await expect(card.getByRole('button', { name: 'Collapse chart', exact: true }), 'the first Escape closes the tooltip alone').toBeVisible()
      await page.keyboard.press('Escape')
      const toggle = card.getByRole('button', { name: 'Expand chart', exact: true })
      await expect(toggle).toBeFocused()
      await expect(toggle).toHaveAttribute('aria-expanded', 'false')
    })

    test('the tooltip’s text clears 4.5:1 on its surface, and under 200% text it stays inside the chart', async ({ page, baseURL }) => {
      test.skip(!enabled, 'Build and serve with NEXT_PUBLIC_CHARTS_V2=true, and set it for this test process.')
      test.setTimeout(90_000)
      await openAnalysis(page, baseURL!, 'captured', theme, 2)
      for (const viewport of await page.locator('[data-analysis-chart-scroll]').all()) {
        const card = viewport.locator('xpath=ancestor::section[1]')
        await card.getByRole('slider').focus()
        await card.getByRole('slider').press('Home')
        const tooltip = card.locator('[data-chart-tooltip]')
        await expect(tooltip).toBeVisible()
        expect(await overrun(viewport, tooltip), 'inside the viewport’s sides').toBeLessThanOrEqual(0.5)
        const inks = await tooltip.evaluate((element) => {
          const ground = getComputedStyle(element).backgroundColor
          return [...element.querySelectorAll('p, span')].filter((node) => node.childElementCount === 0 && node.textContent?.trim())
            .map((node) => [node.textContent!, getComputedStyle(node).color, ground])
        })
        for (const [text, ink, ground] of inks) expect(contrast(ink, ground), `"${text}" on the tooltip`).toBeGreaterThanOrEqual(4.5)
      }
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), 'the page does not scroll sideways').toBe(true)
    })
  })
}

test.describe('trend charts v2 / 900px: a card that scrolls, with an expanded view that fits', () => {
  test.use({ viewport: { width: 900, height: 900 }, reducedMotion: 'reduce', serviceWorkers: 'block' })

  test('collapsing opens the card at its newest period again (spec §3.10)', async ({ page, baseURL }) => {
    test.skip(!enabled, 'Build and serve with NEXT_PUBLIC_CHARTS_V2=true, and set it for this test process.')
    await openAnalysis(page, baseURL!, 'captured', 'light')
    const card = page.locator('section:has([data-analysis-chart])').first()
    const viewport = card.locator('[data-analysis-chart-scroll]')
    const fromNewest = () => viewport.evaluate((element) => element.scrollWidth - element.clientWidth - element.scrollLeft)
    const overflows = () => viewport.evaluate((element) => element.scrollWidth > element.clientWidth + 1)
    expect(await overflows(), 'the two-column card scrolls').toBe(true)
    expect(await fromNewest()).toBeLessThanOrEqual(1)
    await viewport.evaluate((element) => { element.scrollLeft = 0 })
    await card.getByRole('button', { name: 'Expand chart', exact: true }).click()
    await expect.poll(overflows, { message: 'the expanded plot fits' }).toBe(false)
    await card.getByRole('button', { name: 'Collapse chart', exact: true }).click()
    await expect.poll(overflows).toBe(true)
    await expect.poll(fromNewest, { message: 'collapsed, at the newest period' }).toBeLessThanOrEqual(1)
  })
})

test.describe('trend charts v2 / a tap pins a tooltip', () => {
  test.use({ viewport: { width: 390, height: 900 }, hasTouch: true, isMobile: true, reducedMotion: 'reduce', serviceWorkers: 'block' })

  test('a tap shows its period’s tooltip, a second tap or a tap outside closes it', async ({ page, baseURL }) => {
    test.skip(!enabled, 'Build and serve with NEXT_PUBLIC_CHARTS_V2=true, and set it for this test process.')
    await openAnalysis(page, baseURL!, 'captured', 'light')
    const card = page.locator('section:has([data-analysis-chart])').first()
    const viewport = card.locator('[data-analysis-chart-scroll]')
    await viewport.scrollIntoViewIfNeeded()
    const tooltip = card.locator('[data-chart-tooltip]')
    const frame = (await viewport.boundingBox())!
    await page.touchscreen.tap(frame.x + frame.width - 24, frame.y + 120)
    await expect(tooltip).toBeVisible()
    await expect(card.locator('[data-chart-wash]')).toBeVisible()
    await page.touchscreen.tap(frame.x + frame.width - 24, frame.y + 120)
    await expect(tooltip).toHaveCount(0)
    await page.touchscreen.tap(frame.x + frame.width - 24, frame.y + 120)
    await expect(tooltip).toBeVisible()
    const heading = (await card.getByRole('heading', { level: 2 }).boundingBox())!
    await page.touchscreen.tap(heading.x + 4, heading.y + 4)
    await expect(tooltip).toHaveCount(0)
  })
})

test.describe('trend charts v2 / the states while a chart is not ready (spec §3.9; E200)', () => {
  test.use({ viewport: { width: 1280, height: 900 }, reducedMotion: 'reduce', serviceWorkers: 'block' })

  test('a plot holds its bones, busy, while its font loads, and draws once it arrives', async ({ page, baseURL }) => {
    test.skip(!enabled, 'Build and serve with NEXT_PUBLIC_CHARTS_V2=true, and set it for this test process.')
    // Hold every font file until the first card's bones have been read; the wait's 1,500 ms cap paints regardless.
    let release!: () => void
    const held = new Promise<void>((resolve) => { release = resolve })
    await page.route('**/_next/static/media/*.woff2', async (route) => { await held; await route.continue() })
    await page.addInitScript(() => {
      new MutationObserver((_, observer) => {
        const bones = document.querySelector('[data-trend-chart] [data-chart-bones]')
        if (!bones) return
        observer.disconnect()
        const card = bones.closest('section')!
        const box = bones.getBoundingClientRect()
        const parts = [...bones.querySelectorAll(':scope > div > div')].map((bone) => bone.getBoundingClientRect())
        Object.assign(window, { __bones: {
          busy: card.getAttribute('aria-busy'),
          hidden: bones.getAttribute('aria-hidden'),
          plot: card.querySelector('[data-analysis-chart] > svg') != null,
          height: box.height,
          parts: parts.length,
          painted: parts.every((part) => part.width > 0 && part.height > 0),
          inside: parts.every((part) => part.left >= box.left - 0.5 && part.right <= box.right + 0.5 && part.top >= box.top - 0.5 && part.bottom <= box.bottom + 0.5),
        } })
      }).observe(document, { childList: true, subtree: true })
    })
    const opened = openAnalysis(page, baseURL!, 'captured', 'light')
    const read = () => page.evaluate(() => (window as unknown as { __bones?: Record<string, unknown> }).__bones ?? null)
    await expect.poll(read, { message: 'a card drew its bones' }).not.toBeNull()
    const bones = (await read())!
    release()
    await opened
    expect(bones).toMatchObject({ busy: 'true', hidden: 'true', plot: false, height: 320, painted: true, inside: true })
    expect(bones.parts as number).toBeGreaterThan(8)
    await expect(page.locator('[data-analysis-chart] > svg')).toHaveCount(4)
    await expect(page.locator('[data-chart-bones]')).toHaveCount(0)
    await expect(page.locator('section[aria-busy]')).toHaveCount(0)
  })

  test('the export is busy while its PNG is drawn, then ready again', async ({ page, baseURL }) => {
    test.skip(!enabled, 'Build and serve with NEXT_PUBLIC_CHARTS_V2=true, and set it for this test process.')
    await openAnalysis(page, baseURL!, 'captured', 'light')
    const button = page.locator('[data-trend-chart="margins"]').getByRole('button', { name: 'Download chart as PNG', exact: true })
    await button.evaluate((element) => {
      const seen: (string | null)[] = []
      new MutationObserver(() => seen.push(element.getAttribute('aria-busy'))).observe(element, { attributes: true, attributeFilter: ['aria-busy'] })
      Object.assign(window, { __busy: seen })
    })
    await Promise.all([page.waitForEvent('download'), button.click()])
    await expect(button).not.toHaveAttribute('aria-busy')
    expect(await page.evaluate(() => (window as unknown as { __busy: (string | null)[] }).__busy), 'busy, then not').toEqual(['true', null])
    await expect(button).toBeEnabled()
  })
})

for (const motion of ['no-preference', 'reduce'] as const) test.describe(`trend charts v2 / a toggle with motion ${motion} (spec §3.10; E200)`, () => {
  test.use({ viewport: { width: 1280, height: 900 }, reducedMotion: motion, serviceWorkers: 'block' })

  test(motion === 'reduce' ? 'the plot row takes its new height at once' : 'the plot row runs to its expanded height, then sizes itself again', async ({ page, baseURL }) => {
    test.skip(!enabled, 'Build and serve with NEXT_PUBLIC_CHARTS_V2=true, and set it for this test process.')
    await openAnalysis(page, baseURL!, 'captured', 'light')
    const row = page.locator('[data-trend-chart="margins"] [data-analysis-chart-scroll]').locator('xpath=../..')
    const run = await row.evaluate(async (element) => {
      const before = element.getBoundingClientRect().height
      element.closest('section')!.querySelector<HTMLButtonElement>('button[aria-label="Expand chart"]')!.click()
      const heights: number[] = []
      let inline = ''
      await new Promise<void>((resolve) => {
        const started = performance.now()
        const tick = () => {
          if (!heights.length) inline = element.style.height
          heights.push(element.getBoundingClientRect().height)
          if (performance.now() - started < 600) requestAnimationFrame(tick)
          else resolve()
        }
        requestAnimationFrame(tick)
      })
      return { before, inline, heights, after: element.style.height }
    })
    const end = run.heights.at(-1)!
    expect(end, 'the expanded plot is taller').toBeGreaterThan(run.before + 100)
    expect(run.after, 'the row sizes itself once the run ends').toBe('')
    const between = run.heights.filter((height) => height > run.before + 1 && height < end - 1)
    if (motion === 'reduce') {
      expect(run.inline, 'no running height').toBe('')
      expect(between, 'no height between').toEqual([])
    } else {
      expect(run.inline, 'the row runs at a set height').toMatch(/^\d+(\.\d+)?px$/)
      expect(between.length, 'heights between the two').toBeGreaterThan(0)
    }
  })
})
