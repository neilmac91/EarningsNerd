import { test, expect, type Locator, type Page } from '@playwright/test'
import { calendarWeekReady, pinCalendarWeek } from './fixtures/calendarWeek'
import { answerApi } from './fixtures/filing3Api'
import { answerLegalReadiness } from './fixtures/legalReady'

/**
 * The native day dialog returns keyboard focus to its opener after every dismissal, from both
 * calendar views. A detached open dialog left BODY focused, even with its opener still mounted.
 * Use the real browser: jsdom cannot model showModal()'s focus restoration or the top layer.
 * CI's calendar fixtures and browser-routed guest API keep this check backend-free.
 */

async function tabTo(page: Page, target: Locator) {
  await expect(target).toBeVisible()
  for (let step = 0; step < 80; step++) {
    if (await target.evaluate((el) => el === document.activeElement)) return
    await page.keyboard.press('Tab')
  }
  await expect(target, 'the opener is reachable in the normal Tab order').toBeFocused()
}

test.use({ viewport: { width: 1440, height: 900 } })

for (const theme of ['light', 'dark'] as const) {
  for (const view of ['week', 'month'] as const) {
    for (const close of ['Escape', 'Close', 'backdrop'] as const) {
      test(`${theme} ${view}: ${close} returns focus to the calendar opener`, async ({ page, baseURL }) => {
        await pinCalendarWeek(page)
        await answerApi(page, baseURL!, 'anon')
        await answerLegalReadiness(page, baseURL!)
        await page.addInitScript((chosenTheme) => {
          localStorage.setItem('theme', chosenTheme)
          localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: new Date().toISOString() }))
        }, theme)
        await page.goto('/calendar')
        await calendarWeekReady(page)

        if (view === 'month') {
          await tabTo(page, page.getByRole('group', { name: 'Calendar view' }).getByRole('button', { name: 'Month', exact: true }))
          await page.keyboard.press('Enter')
        }
        const opener = view === 'week'
          ? page.getByRole('region', { name: 'Wednesday, July 29, 8 companies reporting', exact: true }).getByRole('button', { name: '+3 more', exact: true })
          : page.getByRole('button', { name: /^Wednesday, July 29, 8 companies report:/ })
        await tabTo(page, opener)
        // Retain the actual node, so a replacement matching the locator cannot conceal a lost opener.
        const original = await opener.elementHandle()
        expect(original).not.toBeNull()
        await page.keyboard.press('Enter')

        const dialog = page.getByRole('dialog', { name: 'Earnings on Wednesday, July 29', exact: true })
        await expect(dialog).toBeVisible()
        await expect(dialog.getByRole('button', { name: 'Close', exact: true })).toBeFocused()
        if (close === 'backdrop') {
          const box = await dialog.boundingBox()
          expect(box).not.toBeNull()
          await page.mouse.click(box!.x - 8, box!.y + 8)
        } else {
          await page.keyboard.press(close === 'Escape' ? 'Escape' : 'Enter')
        }

        await expect(dialog).toBeHidden()
        await expect(opener).toBeFocused()
        expect(await original!.evaluate((el) => el.isConnected && el === document.activeElement)).toBe(true)
        await page.keyboard.press('Tab')
        const next = view === 'week'
          ? page.getByRole('region', { name: 'Thursday, July 30, 6 companies reporting', exact: true }).getByRole('link').first()
          : page.getByRole('button', { name: /^Thursday, July 30, 6 companies report:/ })
        await expect(next).toBeFocused()
        await page.keyboard.press('Shift+Tab')
        await expect(opener).toBeFocused()
      })
    }
  }
}
