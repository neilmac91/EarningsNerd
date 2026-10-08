import { test, expect, type Locator, type Page } from '@playwright/test'
import { answerApi, type Theme, type Who } from './fixtures/filing3Api'

/**
 * EN-05c: every keyboard stop in the site chrome shows the brand focus ring (DESIGN_SYSTEM.md §4,
 * `shadow-ring-brand` / `shadow-ring-brand-dark`), never the browser's default outline, in both themes,
 * in a real Chromium. On main the logo link, the theme toggle, the filing page's "← Back", the mobile
 * menu button and its links, the account and notification menus' items, the page header's back link,
 * the footer's Logo.dev link and the auth header's logo drew Chromium's `outline: auto` instead.
 *
 * Each case walks the page with the keyboard (Tab from the top, Enter to open a menu) and reads the
 * computed style of every stop it passes: the ring's box-shadow present and no visible outline (the
 * recipe's `outline-none` is a 2px transparent outline). The static gate is
 * tests/unit/siteChromeFocusRing.spec.ts; this is the rendered proof. CI runs e2e with no backend
 * (lessons/test-e2e-runs-without-backend.md): fixtures/filing3Api.ts answers the API in the browser.
 * Computed style only: nobody looked at a screen here, and this is not a contrast measurement.
 */

const RING: Record<Theme, string> = { light: 'rgba(79, 122, 99, 0.5)', dark: 'rgba(127, 178, 149, 0.55)' }

async function visit(page: Page, baseURL: string, path: string, who: Who, theme: Theme) {
  await answerApi(page, baseURL, who)
  await page.addInitScript((t) => {
    try {
      localStorage.setItem('theme', t)
      localStorage.setItem('en:copilot-coachmark-v1', '1')
      localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: new Date().toISOString() }))
    } catch {}
  }, theme)
  await page.goto(path)
}

interface Stop {
  name: string
  focusVisible: boolean
  boxShadow: string
  outline: string
}

/** The focused element's name and the focus styles it computes to. */
const current = (page: Page): Promise<Stop> =>
  page.evaluate(() => {
    const el = document.activeElement as HTMLElement | null
    if (!el || el === document.body) return { name: 'BODY', focusVisible: false, boxShadow: '', outline: '' }
    const s = getComputedStyle(el)
    const visibleOutline = s.outlineStyle !== 'none' && s.outlineColor !== 'rgba(0, 0, 0, 0)' && s.outlineWidth !== '0px'
    return {
      name: (el.getAttribute('aria-label') ?? el.textContent ?? '').trim().replace(/\s+/g, ' ').slice(0, 40),
      focusVisible: el.matches(':focus-visible'),
      boxShadow: s.boxShadow,
      outline: visibleOutline ? `${s.outlineStyle} ${s.outlineWidth} ${s.outlineColor}` : 'none',
    }
  })

/** The stop shows the brand ring for `theme` and no outline (polled: some controls transition box-shadow). */
async function expectRing(page: Page, theme: Theme) {
  await expect
    .poll(async () => {
      const s = await current(page)
      return `${s.name} | focus-visible ${s.focusVisible} | ring ${s.boxShadow.includes(RING[theme])} | outline ${s.outline}`
    })
    .toMatch(/\| focus-visible true \| ring true \| outline none$/)
}

/**
 * Tabs from where focus is until `until` is focused (bounded), checking every stop inside `scope`
 * (a stop outside it, like the page's own content, is passed over). Returns the stops' names.
 */
async function tabThrough(page: Page, theme: Theme, scope: Locator[], until: Locator, max = 25): Promise<string[]> {
  const names: string[] = []
  for (let i = 0; i < max; i += 1) {
    await page.keyboard.press('Tab')
    const inScope = await page.evaluate(
      (els) => els.some((el) => el.contains(document.activeElement)),
      await Promise.all(scope.map((s) => s.elementHandle())),
    )
    if (inScope || (await until.evaluate((el) => el === document.activeElement))) {
      names.push((await current(page)).name)
      await expectRing(page, theme)
    }
    if (await until.evaluate((el) => el === document.activeElement)) return names
  }
  throw new Error(`never reached the stop; passed ${names.join(' · ')}`)
}

/** The filing page header's "← Back" (the arrow glyph is part of its name; its text reads "←Back"). */
const backOf = (page: Page) => page.getByRole('button', { name: '← Back', exact: true })
const siteHeader = (page: Page) => page.locator('header:has(a[aria-label="EarningsNerd home"])')

for (const theme of ['light', 'dark'] as const) {
  test.describe(`site chrome focus ring, ${theme}`, () => {
    test.describe('desktop 1440x900', () => {
      test.use({ viewport: { width: 1440, height: 900 } })

      test('a visitor: skip link, logo, nav, theme toggle, account links, then the filing page’s Back', async ({ page, baseURL }) => {
        await visit(page, baseURL!, '/filing/3', 'anon', theme)
        const backButton = backOf(page)
        await expect(backButton).toBeVisible()
        await expect(siteHeader(page).getByRole('link', { name: 'Log in' })).toBeVisible()
        const names = await tabThrough(page, theme, [siteHeader(page), page.getByRole('link', { name: 'Skip to main content' })], backButton)
        expect(names).toEqual(expect.arrayContaining(['Skip to main content', 'EarningsNerd home', `Switch to ${theme === 'light' ? 'dark' : 'light'} mode`, 'Log in', '←Back']))
      })

      test('a signed-in user: the account and notification menus’ items', async ({ page, baseURL }) => {
        await visit(page, baseURL!, '/filing/3', 'pro', theme)
        const account = page.getByRole('button', { name: 'Account menu' })
        await expect(account).toBeVisible()
        await tabThrough(page, theme, [siteHeader(page)], account)
        await page.keyboard.press('Enter')
        const menu = page.getByRole('menu', { name: 'Account' })
        await expect(menu).toBeVisible()
        const items = await tabThrough(page, theme, [menu], menu.getByRole('menuitem', { name: 'Log out' }))
        expect(items).toEqual(expect.arrayContaining(['Dashboard', 'Watchlist', 'Settings', 'Log out']))
        await page.keyboard.press('Escape')

        const bell = siteHeader(page).getByRole('button', { name: /notifications/i })
        await bell.focus()
        await expectRing(page, theme)
        await page.keyboard.press('Enter')
        const alerts = page.getByRole('menu', { name: 'Notifications' })
        await expect(alerts).toBeVisible()
        await tabThrough(page, theme, [alerts], alerts.getByRole('menuitem', { name: 'Manage alert settings' }))
      })

      test('the page header’s back link (pricing), the footer’s Logo.dev link', async ({ page, baseURL }) => {
        await visit(page, baseURL!, '/pricing', 'anon', theme)
        const backLink = page.getByRole('link', { name: 'Back to home' })
        await expect(backLink).toBeVisible()
        await tabThrough(page, theme, [siteHeader(page)], backLink)
        // The footer is many stops down; start from its last nav link, as Tab would arrive there.
        const logoDev = page.getByRole('link', { name: 'Logo.dev' })
        await logoDev.scrollIntoViewIfNeeded()
        await page.locator('footer ul a').last().focus()
        await page.keyboard.press('Tab')
        await expect(logoDev).toBeFocused()
        await expectRing(page, theme)
      })

      test('the auth routes’ header: logo, theme toggle, Back to home', async ({ page, baseURL }) => {
        await visit(page, baseURL!, '/login', 'anon', theme)
        const home = page.getByRole('link', { name: 'Back to home' })
        await expect(home).toBeVisible()
        // The auth shell's header row: the logo, then the theme toggle and Back to home.
        const shellHeader = home.locator('xpath=../..')
        const names = await tabThrough(page, theme, [shellHeader], home, 6)
        expect(names.length).toBe(3)
      })
    })

    test.describe('phone 390x844', () => {
      test.use({ viewport: { width: 390, height: 844 } })

      for (const who of ['anon', 'pro'] as const) {
        test(`${who === 'anon' ? 'a visitor' : 'a signed-in user'}: logo, theme toggle, menu button, every menu link, then Back`, async ({ page, baseURL }) => {
          await visit(page, baseURL!, '/filing/3', who, theme)
          const menuButton = page.getByRole('button', { name: 'Open menu' })
          await expect(menuButton).toBeVisible()
          if (who === 'pro') await expect(page.getByRole('button', { name: 'Account menu' })).toBeHidden()
          const names = await tabThrough(page, theme, [siteHeader(page), page.getByRole('link', { name: 'Skip to main content' })], menuButton)
          expect(names).toEqual(expect.arrayContaining(['EarningsNerd home', `Switch to ${theme === 'light' ? 'dark' : 'light'} mode`, 'Open menu']))

          await page.keyboard.press('Enter')
          const mobileNav = page.getByRole('navigation', { name: 'Mobile navigation' })
          await expect(mobileNav).toBeVisible()
          const last = who === 'anon' ? mobileNav.getByRole('link').last() : mobileNav.getByRole('button', { name: 'Log out' })
          const links = await tabThrough(page, theme, [mobileNav], last)
          expect(links).toEqual(expect.arrayContaining(who === 'anon' ? ['Pricing', 'Contact', 'Log in'] : ['Pricing', 'Dashboard', 'Settings', 'Log out']))

          await page.getByRole('button', { name: 'Close menu' }).focus()
          await expectRing(page, theme)
          await page.keyboard.press('Enter')
          await page.keyboard.press('Tab')
          await expect(backOf(page)).toBeFocused()
          await expectRing(page, theme)
        })
      }
    })
  })
}
