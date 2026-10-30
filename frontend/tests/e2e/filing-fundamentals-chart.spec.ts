import { test, expect, type Locator, type Page } from '@playwright/test'
import { answerApi, FUNDAMENTALS, type Theme } from './fixtures/filing3Api'

/**
 * Financial trends mounts on the filing page (E195 D). Production builds the card (frontend/vercel.json sets
 * NEXT_PUBLIC_ENABLE_FINANCIAL_CHARTS) and so does CI's e2e job, so on a build without the flag every case here fails:
 * the card never mounts. It renders nothing on an error and for a filing with no featured series, so no render test
 * can see it go missing from the page (lessons/frontend-route-redesign-needs-a-mount-gate.md).
 *
 * On /filing/3, answered by fixtures/filing3Api.ts (production's payload for the filing, four series kept), in both
 * themes at 390 and 1280px: the card's heading and its plot mount, the picker opens on revenue and offers every series
 * the fixture holds, and for each one, chosen in turn, the plot prints that series' fiscal years, read from the fixture,
 * as text in its SVG, and the page does not scroll sideways. The heading also stands over the loading state, so what
 * only a drawn plot shows is counted from the input (lessons/test-probes-assert-what-only-success-renders.md); every
 * point of the fixture holds a value, so either renderer prints each year.
 *
 * The probes do not depend on the renderer: the plot is the card's `data-testid="fundamentals-chart"` and the SVG text
 * inside it, which the Recharts chart draws today and the trend charts' engine will draw once Financial trends moves
 * onto it, adding its own assertions here. CI runs e2e with no backend (lessons/test-e2e-runs-without-backend.md).
 */

const VIEWPORTS = [
  { width: 390, height: 844, isMobile: true, hasTouch: true },
  { width: 1280, height: 900, isMobile: false, hasTouch: false },
]
const THEMES: Theme[] = ['light', 'dark']

/** The card: the nearest section around its heading. */
const financialTrends = (page: Page) =>
  page.getByRole('heading', { level: 2, name: 'Financial trends', exact: true }).locator('xpath=ancestor::section[1]')

/** Every year the plot's SVG prints as text, in order: a year axis's tick labels, whichever renderer draws them. */
const drawnYears = (plot: Locator) =>
  plot.evaluate((root) => {
    const years = new Set<number>()
    for (const text of root.querySelectorAll('svg text')) {
      for (const match of (text.textContent ?? '').matchAll(/(?<!\d)(?:19|20)\d{2}(?!\d)/g)) years.add(Number(match[0]))
    }
    return [...years].sort((a, b) => a - b)
  })

/** The document's widths and, for a failure message, the widest boxes past the viewport's right edge. */
const widths = (page: Page) =>
  page.evaluate(() => {
    const root = document.documentElement
    const past = [...document.querySelectorAll('body *')]
      .map((el) => ({ el, right: el.getBoundingClientRect().right }))
      .filter(({ right }) => right > root.clientWidth + 0.5)
      .sort((a, b) => b.right - a.right)
      .slice(0, 6)
      .map(({ el, right }) => `${Math.round(right)}px ${el.tagName.toLowerCase()} "${(el.textContent ?? '').replace(/\s+/g, ' ').trim().slice(0, 40)}"`)
    return { scrollWidth: root.scrollWidth, clientWidth: root.clientWidth, past }
  })

test.describe.configure({ mode: 'parallel' })

for (const { width, height, isMobile, hasTouch } of VIEWPORTS) {
  test.describe(`Financial trends on /filing/3 at ${width}px`, () => {
    test.use({ viewport: { width, height }, isMobile, hasTouch })

    for (const theme of THEMES) {
      test(`${theme}: the card and its plot mount, each series prints its years, and the page does not scroll sideways`, async ({ page, baseURL }) => {
        await answerApi(page, baseURL!, 'anon')
        // Consent answered and the first-run coachmark seen: neither belongs to this card.
        await page.addInitScript((chosen: Theme) => {
          try {
            localStorage.setItem('theme', chosen)
            localStorage.setItem('en:copilot-coachmark-v1', '1')
            localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: new Date().toISOString() }))
          } catch {}
        }, theme)
        await page.goto('/filing/3')

        const card = financialTrends(page)
        await expect(card).toBeVisible()
        expect(await page.evaluate(() => document.documentElement.classList.contains('dark')), `the ${theme} theme took`).toBe(theme === 'dark')
        const picker = card.getByRole('combobox', { name: /^Metric\b/ })
        await expect(picker).toHaveValue('revenue')
        const offered = await picker.locator('option').evaluateAll((options) => options.map((option) => (option as HTMLOptionElement).value))
        expect([...offered].sort(), 'the picker offers every series the fixture holds').toEqual(FUNDAMENTALS.concepts.map((series) => series.concept).sort())

        const plot = card.getByTestId('fundamentals-chart')
        for (const concept of offered) {
          await picker.selectOption(concept)
          const years = FUNDAMENTALS.concepts.find((series) => series.concept === concept)!.points.map((point) => point.fiscal_year)
          await expect(plot, `${concept}: the plot mounts`).toBeVisible()
          await expect.poll(() => drawnYears(plot), { message: `${concept}: the plot prints the series' fiscal years` }).toEqual([...years].sort((a, b) => a - b))
          await page.evaluate(() => document.fonts.ready)
          const { scrollWidth, clientWidth, past } = await widths(page)
          expect(scrollWidth, `${concept}: scrollWidth ${scrollWidth}px against clientWidth ${clientWidth}px; past the edge: ${past.join('; ') || 'nothing'}`).toBeLessThanOrEqual(clientWidth)
        }
      })
    }
  })
}
