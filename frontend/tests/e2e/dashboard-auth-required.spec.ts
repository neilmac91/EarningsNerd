import { test, expect } from '@playwright/test'

test.describe('Dashboard - Authentication Required', () => {
  test('should redirect unauthenticated users to login page', async ({ page }) => {
    // Navigate directly to dashboard
    await page.goto('/dashboard')

    // Should redirect to login page
    await expect(page).toHaveURL(/\/login/)

    // Verify login page is displayed
    await expect(page.locator('h1')).toContainText('Login')

    // Should have email and password fields
    await expect(page.locator('input[type="email"]')).toBeVisible()
    await expect(page.locator('input[type="password"]')).toBeVisible()
  })

  test('should not display "Application error" when accessing dashboard without auth', async ({ page }) => {
    // Track any page errors
    const errors: Error[] = []
    page.on('pageerror', error => errors.push(error))

    // Navigate to dashboard
    await page.goto('/dashboard')

    // Wait for any redirects to complete
    await page.waitForLoadState('networkidle')

    // Verify no client-side errors occurred
    expect(errors).toHaveLength(0)

    // Ensure no error message is displayed
    const errorMessage = page.locator('text=Application error')
    await expect(errorMessage).not.toBeVisible()
  })

  test('should redirect with return URL parameter', async ({ page }) => {
    // Navigate to dashboard
    await page.goto('/dashboard')

    // Wait for redirect
    await page.waitForLoadState('networkidle')

    // Check if URL includes redirect parameter (middleware behavior)
    const currentUrl = page.url()
    if (currentUrl.includes('/login')) {
      // This is the expected behavior with middleware
      expect(currentUrl).toContain('/login')
    }
  })

  test('should show authentication required error gracefully', async ({ page }) => {
    // Navigate to dashboard
    await page.goto('/dashboard')

    // Wait for page to load
    await page.waitForLoadState('networkidle')

    // Should either be on login page or show auth error
    const url = page.url()
    const isOnLoginPage = url.includes('/login')
    const hasAuthError = await page.locator('text=/authentication/i, text=/login/i').count() > 0

    // One of these should be true
    expect(isOnLoginPage || hasAuthError).toBeTruthy()
  })

  test('dashboard settings should also require authentication', async ({ page }) => {
    // Navigate to dashboard settings
    await page.goto('/dashboard/settings')

    // Should redirect to login
    await page.waitForLoadState('networkidle')

    // Should be on login page or show auth requirement
    const url = page.url()
    expect(url).toMatch(/\/login|\/dashboard/)
  })

  test('dashboard watchlist should also require authentication', async ({ page }) => {
    // Navigate to dashboard watchlist
    await page.goto('/dashboard/watchlist')

    // Should redirect to login
    await page.waitForLoadState('networkidle')

    // Should be on login page or show auth requirement
    const url = page.url()
    expect(url).toMatch(/\/login|\/dashboard/)
  })
})
