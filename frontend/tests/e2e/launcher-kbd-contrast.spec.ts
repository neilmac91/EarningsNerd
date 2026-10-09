import { test, expect, type Page } from '@playwright/test'
import { textContrast, settled } from './fixtures/contrast'
import { answerApi, type Theme } from './fixtures/filing3Api'

/**
 * DC-KBD (critique v3.1): the ⌘K keycap on the filing page's floating "Ask this Filing" launcher
 * must be legible. Before, the keycap set a cream fill (bg-background-light, the same in both
 * themes) and no ink of its own, so it inherited the pill's label colour: white on cream in light
 * theme measured 1.11:1. It now takes the reference launcher's recipe (AskCopilotRail): a black/10
 * wash over the pill and a black/25 hairline, so its glyphs sit on a darkened pill fill.
 *
 * The contrast is computed from the browser's own resolved colours: the keycap's ink against its
 * fill composited over the pill, at rest and while the pointer is over the pill (the pill darkens).
 * Measured in Chromium at 1280x800 (the keycap is hidden below sm). The keycap is visual only — the
 * button's accessible name stays "Ask this Filing" — so this is a DOM measurement, not a
 * screen-reader test. CI runs with no backend: the API is answered by the shared filing-3 fixture.
 */

const launcher = (page: Page) => page.getByRole('button', { name: 'Ask this Filing', exact: true })

async function openFiling(page: Page, baseURL: string, theme: Theme) {
  await answerApi(page, baseURL, 'anon')
  await page.addInitScript((t: Theme) => {
    try {
      localStorage.setItem('theme', t)
      // Consent stored and the coachmark seen: nothing else is drawn near the launcher.
      localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: new Date().toISOString() }))
      localStorage.setItem('en:copilot-coachmark-v1', '1')
    } catch {}
  }, theme)
  await page.goto('/filing/3')
  await expect(launcher(page)).toBeVisible()
}

for (const theme of ['light', 'dark'] as const) {
  test(`the launcher's ⌘K keycap is legible in ${theme} theme, at rest and on hover`, async ({ page, baseURL }) => {
    await page.setViewportSize({ width: 1280, height: 800 })
    await openFiling(page, baseURL!, theme)
    const kbd = launcher(page).locator('kbd')
    await expect(kbd).toBeVisible()
    await expect(kbd).toHaveText('⌘K')
    await settled(launcher(page))
    expect(await textContrast(kbd), `${theme} keycap at rest`).toBeGreaterThanOrEqual(4.5)
    await launcher(page).hover()
    await settled(launcher(page))
    expect(await textContrast(kbd), `${theme} keycap on hover`).toBeGreaterThanOrEqual(4.5)
  })
}
