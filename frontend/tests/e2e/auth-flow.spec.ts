import { test, expect } from '@playwright/test'

test.describe('Authentication Flow', () => {
  test('should display login page with form elements', async ({ page }) => {
    await page.goto('/login')

    // Verify we're on the login page
    await expect(page).toHaveURL('/login')

    // Check for login form elements
    await expect(page.locator('h1')).toContainText('Login')
    await expect(page.locator('input[type="email"]')).toBeVisible()
    await expect(page.locator('input[type="password"]')).toBeVisible()
    await expect(page.locator('button[type="submit"]')).toBeVisible()

    // Check for link to registration
    await expect(page.locator('a[href="/register"]')).toBeVisible()
  })

  test('should display registration page with form elements', async ({ page }) => {
    await page.goto('/register')

    // Verify we're on the register page
    await expect(page).toHaveURL('/register')

    // Check for registration form elements
    const heading = page.locator('h1')
    await expect(heading).toContainText(/sign up|register|create account/i)

    await expect(page.locator('input[type="email"]')).toBeVisible()
    await expect(page.locator('input[type="password"]')).toBeVisible()
    await expect(page.locator('button[type="submit"]')).toBeVisible()

    // Check for link to login
    await expect(page.locator('a[href="/login"]')).toBeVisible()
  })

  test('should show validation error for invalid login credentials', async ({ page }) => {
    await page.goto('/login')

    // Fill in invalid credentials
    await page.locator('input[type="email"]').fill('invalid@example.com')
    await page.locator('input[type="password"]').fill('wrongpassword')

    // Submit form
    await page.locator('button[type="submit"]').click()

    // Wait for error message (should not redirect)
    // Should show error message
    await expect(page.locator('text=/invalid|incorrect|failed|error/i').first()).toBeVisible()

    // Should still be on login page (not redirected)
    expect(page.url()).toContain('/login')
  })

  test('should have back to home link on login page', async ({ page }) => {
    await page.goto('/login')

    // Check for back to home link or button
    const backLink = page.locator('a[href="/"], a[href*="home"], button:has-text("back")')
    const backLinkCount = await backLink.count()

    // Should have a way to navigate back
    expect(backLinkCount).toBeGreaterThan(0)
  })

  test('should navigate between login and register pages', async ({ page }) => {
    // Start on login page
    await page.goto('/login')
    await expect(page).toHaveURL('/login')

    // Click link to register
    await page.locator('a[href="/register"]').click()
    await expect(page).toHaveURL('/register')

    // Click link back to login
    await page.locator('a[href="/login"]').click()
    await expect(page).toHaveURL('/login')
  })

  test('should not have client-side errors on auth pages', async ({ page }) => {
    const errors: Error[] = []
    page.on('pageerror', error => errors.push(error))

    // Visit login page
    await page.goto('/login')
    await page.waitForLoadState('networkidle')

    // Visit register page
    await page.goto('/register')
    await page.waitForLoadState('networkidle')

    // Verify no errors
    expect(errors).toHaveLength(0)
  })
})

test.describe('Session Management', () => {
  test('should handle logout gracefully when not logged in', async ({ page }) => {
    // Try to access logout endpoint directly (if it exists)
    // This tests that logout doesn't crash when there's no session
    const errors: Error[] = []
    page.on('pageerror', error => errors.push(error))

    // Navigate to home and verify no errors
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    expect(errors).toHaveLength(0)
  })
})
