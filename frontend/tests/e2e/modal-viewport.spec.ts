import { test, expect } from '@playwright/test'

// ui/Modal locks the body, so a panel taller than the viewport must scroll inside itself — otherwise
// its top and bottom are cut off with nothing left to scroll. 320×256 is the WCAG reflow viewport
// (a 1280-wide window at 400% zoom). /terms is static (CI's Playwright job has no backend); the
// session marker shows the FeedbackWidget launcher, whose report dialog is ~300px tall at this width.
test.use({ viewport: { width: 320, height: 256 } })

test('a dialog taller than the viewport scrolls inside and keeps every control reachable', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('en_session_active', '1')
    localStorage.setItem(
      'cookie_consent',
      JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: new Date().toISOString() }),
    )
  })
  await page.goto('/terms')
  const launcher = page.locator('button[aria-haspopup="dialog"][aria-label="Send feedback"]')
  await launcher.click()

  const dialog = page.getByRole('dialog', { name: 'Send feedback' })
  const close = dialog.getByRole('button', { name: 'Close' })
  const submit = dialog.getByRole('button', { name: 'Send feedback' })
  await page.getByRole('textbox', { name: 'Feedback message' }).fill('The export button is broken')

  // Keyboard: whichever end of the Tab cycle is focused is scrolled fully into view.
  await page.keyboard.press('Tab')
  await expect(submit).toBeFocused()
  await expect(submit).toBeInViewport({ ratio: 1 })
  await page.keyboard.press('Tab')
  await expect(close).toBeFocused()
  await expect(close).toBeInViewport({ ratio: 1 })
  await page.keyboard.press('Shift+Tab')
  await expect(submit).toBeFocused()
  await expect(submit).toBeInViewport({ ratio: 1 })

  // The panel stops at the viewport and its content scrolls inside it.
  const box = await dialog.boundingBox()
  expect(box!.y).toBeGreaterThanOrEqual(0)
  expect(box!.y + box!.height).toBeLessThanOrEqual(256)
  expect(await dialog.evaluate((el) => el.scrollHeight > el.clientHeight)).toBe(true)

  // Pointer: the ✕ takes a click, focus returns to the launcher and the page scrolls again.
  await close.click()
  await expect(dialog).toHaveCount(0)
  await expect(launcher).toBeFocused()
  expect(await page.evaluate(() => document.body.style.overflow)).toBe('')
})
