import { test, expect, type Locator, type Page } from '@playwright/test'
import { answerAnalysisApi, openAnalysis, runAnalysis } from './fixtures/analysisLayoutApi'

/**
 * N17, in a real Chromium: the floating feedback launcher (FeedbackWidget, a 44px circle 20px from a phone's left and
 * bottom edges) rested over the analysis headline figures after Run, so "$14.3B" read "4.3B" (three blind evaluators,
 * severity 3). It now steps aside without moving: while its box, 8px around, meets a region the page marks
 * `data-launcher-keep-clear` (the KPI strip, and the results header over it that names the run, MPA WP4b), it goes to
 * `opacity-0 pointer-events-none`; keyboard focus
 * (`focus-visible:`) brings it back, and it never yields while its own dialog is open. It keeps its place and its rung
 * (bottomChromeLadder.spec.ts).
 *
 * At 390x844 (touch), in both themes, under reduced motion (the launcher's transition is then none, read from the
 * computed style, and the fast token's 150ms opacity fade where motion is allowed), for a signed-in Pro reader:
 * the fixture answers /api/auth/me, and the current-user query FeedbackWidget observes mounts the launcher for the
 * reader it confirms; the session marker a login sets (`en_session_active`) is set before the page opens, as a real
 * reader's is:
 *   (a) each headline figure scrolled to the launcher's centre height: the launcher is transparent and, where its box
 *       covers the figure, the point takes the figure, not the launcher; a tap there opens the figure's evidence;
 *   (b) the strip 100px above the launcher's band: the launcher is opaque and takes its own centre;
 *   (c) a focus its dialog returns after a pointer close (the close button tapped) leaves it stepped aside over a
 *       figure, the figure taking the pointer; a key brings it back (Enter opens its dialog, which keeps it shown, and
 *       the focus an Escape close returns shows it); blur steps it aside again;
 *   (d) at rest right after Run it follows the same rule: as openAnalysis leaves the page, and with the results landing
 *       under it when the reader scrolled the form before Run, where only the page's growth (no scroll) reports it: a
 *       60px scroll lands the header there, its text where the launcher rested opaque before the header was marked;
 *   (e) the header's last line at the launcher's foot, the strip more than 8px below it: the launcher steps aside for
 *       the header alone, and the header's text takes the pointer where the launcher sits.
 * The strip and the header are found by their structure and their own attribute, never by the mark, so a region that
 * loses its mark fails on what the reader sees. Mutations (on committed state): removing `data-launcher-keep-clear`
 * from KpiStrip.tsx fails (a); removing it from ResultsHeader.tsx fails (d) and (e).
 *
 * CI runs e2e with no backend: openAnalysis answers the API in the browser (fixtures/analysisLayoutApi.ts).
 */

const GAP = 8 // lib/launcherKeepClear's LAUNCHER_KEEP_CLEAR_GAP
type Box = { top: number; bottom: number; left: number; right: number }

const launcher = (page: Page) => page.getByRole('button', { name: 'Send feedback', exact: true })
/** The KPI strip's root, the dl's parent, located without its keep-clear mark. */
const strip = (page: Page) => page.locator('dl:has([data-analysis-kpi])').locator('..')
const values = (page: Page) => page.locator('[data-analysis-kpi] [data-kpi-value]')
/** The results header, by its own attribute, never by the keep-clear mark. */
const header = (page: Page) => page.locator('[data-analysis-results-header]')
/** The header's text as painted: a box per piece of each line. */
const textBoxes = (loc: Locator): Promise<Box[]> =>
  loc.evaluate((el) => {
    const range = document.createRange()
    range.selectNodeContents(el)
    return [...range.getClientRects()].filter((r) => r.width && r.height).map((r) => ({ top: r.top, bottom: r.bottom, left: r.left, right: r.right }))
  })
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

/** The launcher steps aside: transparent, and every figure and piece of the header's text its box covers takes the
    pointer there. Returns how many figures and header pieces it covered, so a check that met none cannot pass empty. */
async function expectStepsAside(page: Page, at: string) {
  await expect.poll(() => opacity(launcher(page)), `${at}: the launcher fades`).toBe('0')
  const launcherBox = await boxOf(launcher(page))
  let figures = 0
  for (const value of await values(page).all()) {
    const point = coveredPoint(launcherBox, await boxOf(value))
    if (!point) continue
    figures++
    expect(await hitsAt(value, point), `${at}: "${await value.textContent()}" takes the pointer where the launcher sits`).toBe(true)
  }
  let text = 0
  for (const piece of await textBoxes(header(page))) {
    const point = coveredPoint(launcherBox, piece)
    if (!point) continue
    text++
    expect(await hitsAt(header(page), point), `${at}: the results header's text takes the pointer where the launcher sits`).toBe(true)
  }
  return { figures, text }
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

      // Reduced motion: no transition at all. Where motion is allowed, the opacity fade takes the fast token.
      const transition = () => launcher(page).evaluate((el) => {
        const style = getComputedStyle(el)
        return { property: style.transitionProperty, duration: style.transitionDuration }
      })
      expect((await transition()).property, 'reduced motion: no transition').toBe('none')
      await page.emulateMedia({ reducedMotion: 'no-preference' })
      expect(await transition(), 'motion allowed: the colour and opacity changes take duration-fast').toEqual({ property: 'color, background-color, opacity', duration: '0.15s' })
      await page.emulateMedia({ reducedMotion: 'reduce' })
      expect((await transition()).property).toBe('none')

      // (d) At rest right after Run: the state the rule gives for where the header and the strip landed.
      expect(await page.evaluate(() => window.scrollY), 'Run leaves the page where it was').toBe(0)
      const atRest = await boxOf(launcher(page))
      if (meets(atRest, await boxOf(strip(page))) || meets(atRest, await boxOf(header(page)))) await expectStepsAside(page, 'at rest after Run')
      else await expectRests(page, 'at rest after Run, the strip and the header clear of the launcher')

      // (a) Each figure at the launcher's centre height.
      let covered = 0
      let tapped = false
      for (const [index, value] of (await values(page).all()).entries()) {
        const label = await page.locator('[data-analysis-kpi] dt').nth(index).textContent()
        const target = centreOf(await boxOf(launcher(page))).y
        await scrollBy(page, centreOf(await boxOf(value)).y - target)
        expect(Math.abs(centreOf(await boxOf(value)).y - target), `${label}: centred on the launcher`).toBeLessThan(1)
        const here = (await expectStepsAside(page, `${label} at the launcher's height`)).figures
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

      // (c) A pointer close returns focus to the launcher, which must not hold it opaque over the figures: open the
      // dialog with a tap, close it with a tap on its close button, then scroll the first figure under it.
      const dialog = page.getByRole('dialog', { name: 'Send feedback' })
      await launcher(page).tap()
      await expect(dialog).toBeVisible()
      await dialog.getByRole('button', { name: 'Close', exact: true }).tap()
      await expect(dialog).toHaveCount(0)
      await expect(launcher(page), 'the dialog returns focus to the launcher').toBeFocused()
      const first = values(page).first()
      await scrollBy(page, centreOf(await boxOf(first)).y - centreOf(await boxOf(launcher(page))).y)
      expect((await expectStepsAside(page, 'focused by a pointer close, over the first figure')).figures, 'it covered the first figure').toBeGreaterThanOrEqual(1)
      await expect(launcher(page), 'it keeps the focus while it steps aside').toBeFocused()
      // A key brings it back. A bare key press (Shift opens nothing) turns the focus it holds into keyboard focus.
      await page.keyboard.press('Shift')
      await expect.poll(() => opacity(launcher(page)), 'a bare key press brings it back').toBe('1')
      // Enter opens its dialog, which keeps it shown; Escape returns a focus that shows it.
      await page.keyboard.press('Enter')
      await expect(dialog).toBeVisible()
      expect(await opacity(page.getByRole('button', { name: 'Close feedback', exact: true })), 'its dialog keeps it shown').toBe('1')
      await page.keyboard.press('Escape')
      await expect(dialog).toHaveCount(0)
      await expect(launcher(page)).toBeFocused()
      await expect.poll(() => opacity(launcher(page)), 'keyboard focus brings it back').toBe('1')
      expect(await hitsAt(launcher(page), centreOf(await boxOf(launcher(page)))), 'focused from the keyboard, it takes the pointer').toBe(true)
      await launcher(page).blur()
      await expectStepsAside(page, 'blurred over the first figure')

      // (e) The header's last line at the launcher's foot: the strip lies more than 8px below, so the header alone
      // steps it aside, and its text takes the pointer where the launcher sits.
      await scrollBy(page, (await boxOf(header(page))).bottom - (await boxOf(launcher(page))).bottom)
      expect(Math.round((await boxOf(header(page))).bottom), 'the header ends at the launcher\'s foot').toBe(Math.round((await boxOf(launcher(page))).bottom))
      expect(meets(await boxOf(launcher(page)), await boxOf(strip(page))), 'the strip lies clear of the launcher').toBe(false)
      expect((await expectStepsAside(page, "the header's last line at the launcher's foot")).text, 'the launcher covered the header\'s text').toBeGreaterThanOrEqual(1)
    })

    test('a run that lands the results under the launcher, with no scroll after it, leaves them uncovered', async ({ page, baseURL }) => {
      // (d) N17's rest state: the reader scrolled the form a little, then ran. The results mount under the launcher and
      // no scroll follows, so only the page's growth reports it. At 60px it is the header that lands there, the strip
      // just below the launcher's 8px: before the header was marked, the launcher rested opaque over its words.
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

      expect(meets(await boxOf(launcher(page)), await boxOf(header(page))), 'the header landed under the launcher').toBe(true)
      const covered = await expectStepsAside(page, 'the results mounted under the launcher')
      expect(covered.figures + covered.text, 'the launcher covered a figure or the header\'s text').toBeGreaterThanOrEqual(1)
    })
  })
}
