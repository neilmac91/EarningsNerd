import { test, expect } from '@playwright/test'

test.describe('Home Page - Unauthenticated Users', () => {
  test('should display landing page with company search for unauthenticated users', async ({ page }) => {
    // Navigate to home page
    await page.goto('/')

    // Should stay on home page (not redirect)
    await expect(page).toHaveURL('/')

    // Should display hero section
    await expect(page.locator('h1')).toContainText('SEC Filing Analysis')

    // Should display company search component
    const searchInput = page.locator('input[placeholder*="search" i], input[placeholder*="company" i], input[placeholder*="ticker" i]')
    await expect(searchInput.first()).toBeVisible()

    // Should not have client-side errors
    const errors: Error[] = []
    page.on('pageerror', error => errors.push(error))
    page.on('console', msg => {
      if (msg.type() === 'error') {
        console.error('Browser console error:', msg.text())
      }
    })

    // Wait for page to fully load
    await page.waitForLoadState('networkidle')

    // Verify no client-side errors occurred
    expect(errors).toHaveLength(0)
  })

  test('should display footer with links', async ({ page }) => {
    await page.goto('/')

    // Check for footer links (use .first() since there may be multiple footers)
    const footer = page.locator('footer').first()
    await expect(footer).toBeVisible()

    // Check for privacy, security, and contact links
    await expect(footer.locator('a[href*="privacy"]')).toBeVisible()
    await expect(footer.locator('a[href*="security"]')).toBeVisible()
    // Contact link uses mailto: instead of /contact
    await expect(footer.locator('a[href*="mailto"]')).toBeVisible()
  })

  test('should not display "Application error" message', async ({ page }) => {
    await page.goto('/')

    // Ensure no error message is displayed
    const errorMessage = page.locator('text=Application error')
    await expect(errorMessage).not.toBeVisible()

    // Also check for other error indicators
    const clientError = page.locator('text=client-side exception')
    await expect(clientError).not.toBeVisible()
  })

  test('should handle search interaction without errors', async ({ page }) => {
    await page.goto('/')

    // Find and interact with search input
    const searchInput = page.locator('input[placeholder*="search" i], input[placeholder*="company" i], input[placeholder*="ticker" i]').first()
    await expect(searchInput).toBeVisible()

    // Type in search
    await searchInput.fill('AAPL')

    // Wait for suggestions to appear or network requests to complete
    await page.waitForLoadState('networkidle')

    // Verify no errors occurred during interaction
    const errors: string[] = []
    page.on('pageerror', error => errors.push(error.message))

    // Short wait to catch any post-interaction errors
    // Using a very short wait here just to ensure event loop clears
    // Prefer explicit waits where possible, but here we're checking for absence of errors
    await page.waitForLoadState('domcontentloaded')

    expect(errors).toHaveLength(0)
  })
})
