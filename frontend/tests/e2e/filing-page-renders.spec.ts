import { test, expect } from '@playwright/test'

test.describe('Filing Page Rendering', () => {
  test('should render filing page without runtime errors', async ({ page }) => {
    // Listen for console errors
    const errors: string[] = []
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        errors.push(msg.text())
      }
    })

    // Listen for page errors
    page.on('pageerror', (error) => {
      errors.push(error.message)
    })

    // Navigate to a filing page (using a known filing ID from the test data)
    await page.goto('http://localhost:3000/filing/932')

    // Wait for the page to load
    await page.waitForLoadState('networkidle', { timeout: 10000 })

    // Check that the page title is present
    await expect(page.locator('h1')).toBeVisible({ timeout: 5000 })

    // Verify no critical runtime errors occurred
    const criticalErrors = errors.filter(
      (error) =>
        error.includes('this.clear is not a function') ||
        error.includes('TypeError') ||
        error.includes('Unhandled Runtime Error')
    )

    expect(criticalErrors).toHaveLength(0)

    // Verify that either charts render or error boundary shows graceful fallback
    const chartsVisible = await page.locator('[class*="recharts"]').isVisible().catch(() => false)
    const errorBoundaryVisible = await page
      .getByText(/Unable to display charts/i)
      .isVisible()
      .catch(() => false)

    // At least one should be true (charts work OR error boundary shows gracefully)
    expect(chartsVisible || errorBoundaryVisible || !errors.length).toBeTruthy()
  })

  test('should display financial metrics table even if charts fail', async ({ page }) => {
    await page.goto('http://localhost:3000/filing/932')
    await page.waitForLoadState('networkidle', { timeout: 10000 })

    // Financial metrics table should always be visible
    const table = page.locator('table')
    await expect(table).toBeVisible({ timeout: 5000 })
  })
})

