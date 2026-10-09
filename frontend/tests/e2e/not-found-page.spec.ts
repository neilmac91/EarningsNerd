import { test, expect, type Page } from '@playwright/test'
import { textContrast } from './fixtures/contrast'

/**
 * CLEAN-R5 (critique v3.1): a URL the app cannot serve gets an EarningsNerd 404, not Next's stock
 * "404 | This page could not be found." — the page ground, a panel card, one h1, neutral copy and
 * a way back (home, and the dashboard), inside the site chrome, with a real 404 status. The same
 * app/not-found.tsx renders for every notFound() call (an unknown filing id or ticker the backend
 * 404s, a flag-gated route) and for any unmatched URL.
 *
 * CI runs e2e with no backend, where /filing/{id} resolves to "unavailable" rather than
 * "not-found" (lib/serverApi.ts), so the boundary is exercised here through an unmatched URL.
 * DOM and computed-colour checks only: this is not a screen-reader test.
 */

type Theme = 'light' | 'dark'
const MISSING = '/filings/999999999'

async function open404(page: Page, theme: Theme) {
  await page.addInitScript((t: Theme) => {
    try {
      localStorage.setItem('theme', t)
      localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: new Date().toISOString() }))
    } catch {}
  }, theme)
  const response = await page.goto(MISSING)
  expect(response?.status()).toBe(404)
}

for (const theme of ['light', 'dark'] as const) {
  test(`an unknown URL renders the branded 404 in ${theme} theme`, async ({ page }) => {
    await open404(page, theme)

    const main = page.getByRole('main')
    await expect(main).toHaveCount(1)
    await expect(main.getByRole('heading', { level: 1 })).toHaveText('Page not found')
    await expect(page.getByText('This page could not be found.')).toHaveCount(0)
    await expect(main.getByRole('link', { name: 'Go to the homepage' })).toHaveAttribute('href', '/')
    await expect(main.getByRole('link', { name: 'Open your dashboard' })).toHaveAttribute('href', '/dashboard')

    // Site chrome around it, and the skip link still lands on the layout's #main wrapper.
    await expect(page.getByRole('banner')).toBeVisible()
    await expect(page.getByRole('contentinfo')).toBeVisible()
    await expect(page.locator('#main')).toHaveCount(1)

    // Page ground = background, card = panel (DESIGN_SYSTEM §6), read from the theme's own tokens.
    const surfaces = await main.evaluate((el) => {
      const card = el.querySelector('[data-not-found-card]')
      const probe = (cls: string) => {
        const p = document.createElement('div')
        p.className = cls
        document.body.appendChild(p)
        const c = getComputedStyle(p).backgroundColor
        p.remove()
        return c
      }
      return {
        main: getComputedStyle(el).backgroundColor,
        card: card ? getComputedStyle(card).backgroundColor : null,
        background: probe('bg-background-light dark:bg-background-dark'),
        panel: probe('bg-panel-light dark:bg-panel-dark'),
      }
    })
    expect(surfaces.main).toBe(surfaces.background)
    expect(surfaces.card).toBe(surfaces.panel)

    // Body copy and the heading clear AA on the card.
    expect(await textContrast(main.getByRole('heading', { level: 1 }))).toBeGreaterThanOrEqual(4.5)
    expect(await textContrast(main.getByText(/link may be mistyped/))).toBeGreaterThanOrEqual(4.5)
  })
}

test('the 404 is a real page: Tab reaches its links, and Home leaves it', async ({ page }) => {
  await open404(page, 'light')
  const home = page.getByRole('main').getByRole('link', { name: 'Go to the homepage' })
  await home.focus()
  await expect(home).toBeFocused()
  await page.keyboard.press('Enter')
  await expect(page).toHaveURL(/\/$/)
})
