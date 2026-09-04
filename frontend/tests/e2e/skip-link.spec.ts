import { test, expect } from '@playwright/test'

// Bypass Blocks (WCAG 2.4.1): the first Tab stop on a chromed page is a "Skip to main content"
// link that reveals itself on focus and moves focus to the #main wrapper. /terms is a static page
// with no backend dependency (safe in CI's dead-API Playwright job) and no auto-focused field:
// the home page's hero search takes focus on desktop by design, so Tab order there starts inside it.
test.describe('Skip to main content', () => {
  test('is the first Tab stop, becomes visible on focus, and moves focus to #main', async ({ page }) => {
    await page.goto('/terms')
    await page.waitForLoadState('domcontentloaded')

    const skip = page.getByRole('link', { name: 'Skip to main content' })
    // Visually hidden until focused (sr-only), but present in the accessibility tree.
    await expect(skip).toHaveAttribute('href', '#main')

    await page.keyboard.press('Tab')
    await expect(skip).toBeFocused()
    await expect(skip).toBeVisible()
    const box = await skip.boundingBox()
    expect(box).not.toBeNull()
    expect(box!.width).toBeGreaterThan(24)
    expect(box!.height).toBeGreaterThan(24)

    await page.keyboard.press('Enter')
    await expect(page).toHaveURL(/#main$/)
    await expect(page.locator('#main')).toBeFocused()
  })

  test('main target exists exactly once', async ({ page }) => {
    await page.goto('/terms')
    await expect(page.locator('#main')).toHaveCount(1)
    await expect(page.locator('#main')).toHaveAttribute('tabindex', '-1')
  })
})
