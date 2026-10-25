import { test, expect, type Locator, type Page } from '@playwright/test'
import { answerAnalysisApi, openAnalysis, runAnalysis } from './fixtures/analysisLayoutApi'

/**
 * N17, in a real Chromium: the floating feedback launcher (FeedbackWidget, a 44px circle 20px from a phone's left and
 * bottom edges) rested over the analysis headline figures after Run, so "$14.3B" read "4.3B" (three blind evaluators,
 * severity 3). It now steps aside without moving: while its box, 8px around, meets a region the page marks
 * `data-launcher-keep-clear` (the KPI strip), it goes to `opacity-0 pointer-events-none`; keyboard focus brings it
 * back, and it never yields while its own dialog is open. It keeps its place and its rung (bottomChromeLadder.spec.ts).
 *
 * At 390x844 (touch), in both themes, under reduced motion (the fade is then instant), for a signed-in Pro reader
 * (`en_session_active`, set before the page opens: the analysis fixture's session cookie alone never shows the
 * launcher):
 *   (a) each headline figure scrolled to the launcher's centre height: the launcher is transparent and, where its box
 *       covers the figure, the point takes the figure, not the launcher; a tap there opens the figure's evidence;
 *   (b) the strip 100px above the launcher's band: the launcher is opaque and takes its own centre;
 *   (c) while it yields, focus brings it back, its dialog keeps it shown, and blur steps it aside again;
 *   (d) at rest right after Run it follows the same rule: as openAnalysis leaves the page, and with the strip landing
 *       under it when the reader scrolled the form before Run, where only the page's growth (no scroll) reports it.
 * The strip is found by its structure, never by the mark, so a strip that loses its mark fails on what the reader
 * sees. Mutation (on committed state): removing `data-launcher-keep-clear` from KpiStrip.tsx fails (a) and (d).
 *
 * CI runs e2e with no backend: openAnalysis answers the API in the browser (fixtures/analysisLayoutApi.ts).
 */

const GAP = 8 // lib/launcherKeepClear's LAUNCHER_KEEP_CLEAR_GAP
type Box = { top: number; bottom: number; left: number; right: number }

const launcher = (page: Page) => page.getByRole('button', { name: 'Send feedback', exact: true })
/** The KPI strip's root, the dl's parent, located without its keep-clear mark. */
const strip = (page: Page) => page.locator('dl:has([data-analysis-kpi])').locator('..')
const values = (page: Page) => page.locator('[data-analysis-kpi] [data-kpi-value]')
const opacity = (loc: Locator) => loc.evaluate((el) => getComputedStyle(el).opacity)
const boxOf = (loc: Locator): Promise<Box> =>
  loc.evaluate((el) => {
    const r = el.getBoundingClientRect()
    return { top: r.top, bottom: r.bottom, left: r.left, right: r.right }
  })
/** The launcher's rule: a region meets its box grown by the gap. */
const meets = (launcherBox: Box, region: Box) =>
  region.left < launcherBox.right + GAP && region.right > launcherBox.left - GAP && region.top < launcherBox.bottom + GAP && region.bottom > launcherBox.top - GAP
/** Where the launcher's box covers `box`: the centre of the two boxes' intersection, or null when they do not meet. */
const coveredPoint = (launcherBox: Box, box: Box) => {
  const left = Math.max(launcherBox.left, box.left)
  const right = Math.min(launcherBox.right, box.right)
  const top = Math.max(launcherBox.top, box.top)
  const bottom = Math.min(launcherBox.bottom, box.bottom)
  return left < right && top < bottom ? { x: (left + right) / 2, y: (top + bottom) / 2 } : null
}
/** document.elementFromPoint at (x, y) is the element or inside it (consent-bar-yields.spec.ts's hitsItself, at a point). */
const hitsAt = (loc: Locator, point: { x: number; y: number }) =>
  loc.evaluate((el, { x, y }) => {
    const at = document.elementFromPoint(x, y)
    return at === el || el.contains(at)
  }, point)
const centreOf = (box: Box) => ({ x: (box.left + box.right) / 2, y: (box.top + box.bottom) / 2 })
const scrollBy = (page: Page, dy: number) =>
  page.evaluate((dy) => window.scrollTo({ top: window.scrollY + dy, behavior: 'instant' }), dy)

/** The launcher steps aside: transparent, and every figure its box covers takes the pointer there. Returns how many
    figures it covered, so a check that met none cannot pass empty. */
async function expectStepsAside(page: Page, at: string) {
  await expect.poll(() => opacity(launcher(page)), `${at}: the launcher fades`).toBe('0')
  const launcherBox = await boxOf(launcher(page))
  let covered = 0
  for (const value of await values(page).all()) {
    const point = coveredPoint(launcherBox, await boxOf(value))
    if (!point) continue
    covered++
    expect(await hitsAt(value, point), `${at}: "${await value.textContent()}" takes the pointer where the launcher sits`).toBe(true)
  }
  return covered
}

async function expectRests(page: Page, at: string) {
  await expect.poll(() => opacity(launcher(page)), `${at}: the launcher shows`).toBe('1')
  expect(await hitsAt(launcher(page), centreOf(await boxOf(launcher(page)))), `${at}: the launcher takes its own centre`).toBe(true)
}

for (const theme of ['light', 'dark'] as const) {
  test.describe(`feedback launcher keep-clear / ${theme} / 390x844 phone`, () => {
    test.use({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, colorScheme: theme, reducedMotion: 'reduce', serviceWorkers: 'block' })

    test('right after Run it follows the rule; over each headline figure it steps aside and the figure takes the pointer; clear of the strip it returns; focus brings it back', async ({ page, baseURL }) => {
      test.setTimeout(60_000)
      await page.addInitScript(() => localStorage.setItem('en_session_active', '1'))
      await openAnalysis(page, baseURL!, 'legacy', theme)
      await expect(launcher(page)).toBeVisible()
      await expect(values(page)).toHaveCount(4)

      // (d) At rest right after Run: the state the rule gives for where the strip landed.
      expect(await page.evaluate(() => window.scrollY), 'Run leaves the page where it was').toBe(0)
      if (meets(await boxOf(launcher(page)), await boxOf(strip(page)))) await expectStepsAside(page, 'at rest after Run')
      else await expectRests(page, 'at rest after Run, the strip clear of the launcher')

      // (a) Each figure at the launcher's centre height.
      let covered = 0
      let tapped = false
      for (const [index, value] of (await values(page).all()).entries()) {
        const label = await page.locator('[data-analysis-kpi] dt').nth(index).textContent()
        const target = centreOf(await boxOf(launcher(page))).y
        await scrollBy(page, centreOf(await boxOf(value)).y - target)
        expect(Math.abs(centreOf(await boxOf(value)).y - target), `${label}: centred on the launcher`).toBeLessThan(1)
        const here = await expectStepsAside(page, `${label} at the launcher's height`)
        covered += here
        if (here && !tapped) {
          // A tap where the launcher sits reaches the figure, which opens its evidence.
          const point = coveredPoint(await boxOf(launcher(page)), await boxOf(value))!
          await page.touchscreen.tap(point.x, point.y)
          const evidence = page.getByRole('dialog', { name: new RegExp(`^${label} · `) })
          await expect(evidence).toBeVisible()
          await page.keyboard.press('Escape')
          await expect(evidence).toHaveCount(0)
          tapped = true
        }
      }
      expect(covered, 'the launcher covered the left-hand figures').toBeGreaterThanOrEqual(2)
      expect(tapped).toBe(true)

      // (b) The strip 100px above the launcher's band.
      const band = (await boxOf(launcher(page))).top - GAP
      await scrollBy(page, (await boxOf(strip(page))).bottom - (band - 100))
      expect(Math.round((await boxOf(strip(page))).bottom), 'the strip ends 100px above the band').toBe(Math.round(band - 100))
      await expectRests(page, 'the strip 100px above the band')

      // (c) Back over the first figure: focus brings the launcher back, its dialog keeps it shown, blur steps it aside.
      const first = values(page).first()
      await scrollBy(page, centreOf(await boxOf(first)).y - centreOf(await boxOf(launcher(page))).y)
      await expectStepsAside(page, 'over the first figure')
      await launcher(page).focus()
      await expect.poll(() => opacity(launcher(page)), 'focus brings it back').toBe('1')
      expect(await hitsAt(launcher(page), centreOf(await boxOf(launcher(page)))), 'focused, it takes the pointer').toBe(true)
      await page.keyboard.press('Enter')
      const dialog = page.getByRole('dialog', { name: 'Send feedback' })
      await expect(dialog).toBeVisible()
      expect(await opacity(page.getByRole('button', { name: 'Close feedback', exact: true })), 'its dialog keeps it shown').toBe('1')
      await page.keyboard.press('Escape')
      await expect(dialog).toHaveCount(0)
      await expect(launcher(page)).toBeFocused()
      expect(await opacity(launcher(page)), 'focus returned by the dialog shows it').toBe('1')
      await launcher(page).blur()
      await expectStepsAside(page, 'blurred over the first figure')
    })

    test('a run that lands the strip under the launcher, with no scroll after it, leaves the figures uncovered', async ({ page, baseURL }) => {
      // (d) N17's rest state: the reader scrolled the form a little, then ran. The strip mounts under the launcher and
      // no scroll follows, so only the page's growth reports it.
      await page.addInitScript((theme) => {
        localStorage.setItem('theme', theme)
        localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: '2026-10-10T00:00:00Z' }))
        localStorage.setItem('en_session_active', '1')
      }, theme)
      const traffic = await answerAnalysisApi(page, baseURL!)
      await page.goto('/analysis?ticker=META')
      await expect(page.getByRole('button', { name: 'Run analysis', exact: true })).toBeVisible()
      await expect(launcher(page)).toBeVisible()
      await page.evaluate(() => window.scrollTo({ top: 60, behavior: 'instant' }))
      await runAnalysis(page, 'quarterly')
      await page.evaluate(() => document.fonts.ready)
      await expect(page.locator('html')).toHaveClass(theme === 'dark' ? /\bdark\b/ : /^(?!.*\bdark\b)/)
      expect(traffic.unexpectedApi).toEqual([])
      expect(await page.evaluate(() => window.scrollY), 'no scroll after Run').toBe(60)

      expect(meets(await boxOf(launcher(page)), await boxOf(strip(page))), 'the strip landed under the launcher').toBe(true)
      expect(await expectStepsAside(page, 'the strip mounted under the launcher'), 'the launcher covered a figure').toBeGreaterThanOrEqual(1)
    })
  })
}
