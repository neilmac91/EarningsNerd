import { test, expect } from '@playwright/test'

test.describe('Filing Page Rendering', () => {
  test('renders the structured summary page without a tabbed UI or runtime errors', async ({ page }) => {
    // Listen for console errors
    const errors: string[] = []
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        errors.push(msg.text())
      }
    })

    page.on('pageerror', (error) => {
      errors.push(error.message)
    })

    // Navigate to a filing page. CI runs Playwright against `next start` with NO backend, so this
    // is guarded below and skips when the filing data can't load.
    await page.goto('http://localhost:3000/filing/932')

    // Wait for the page to load
    await page.waitForLoadState('networkidle', { timeout: 15000 })

    // Check if page loaded successfully (has filing content)
    // If backend is not available, the page might show an error or subscription gate
    const hasHeading = await page.locator('h1').count() > 0

    // Skip test if backend is not available (no filing data)
    test.skip(!hasHeading, 'Filing page requires backend API - skipping in CI')

    await expect(page.locator('h1')).toBeVisible()

    // T2: the summary renders as one structured scrolling page — the old tabbed UI is retired, so
    // none of its tab buttons should exist.
    for (const tab of ['Executive Summary', 'Financials', 'Risks', 'MD&A', 'Guidance', 'Liquidity']) {
      expect(await page.getByRole('button', { name: tab, exact: true }).count()).toBe(0)
    }

    // Verify no critical runtime errors occurred while rendering
    const criticalErrors = errors.filter(
      (error) =>
        error.includes('this.clear is not a function') ||
        error.includes('TypeError') ||
        error.includes('Unhandled Runtime Error')
    )

    expect(criticalErrors).toHaveLength(0)
  })
})
