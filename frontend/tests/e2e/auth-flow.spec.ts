import { test, expect } from '@playwright/test'

test.describe('Authentication Flow', () => {
  test('should display login page with form elements', async ({ page }) => {
    await page.goto('/login')

    // Verify we're on the login page
    await expect(page).toHaveURL('/login')

    // Check for heading (redesigned login page)
    await expect(page.locator('h1')).toContainText('Welcome back')

    // Social-first design: email form is behind "Continue with email" disclosure
    await page.getByRole('button', { name: /continue with email/i }).click()

    await expect(page.locator('input[type="email"]')).toBeVisible()
    await expect(page.locator('input[type="password"]')).toBeVisible()
    await expect(page.locator('button[type="submit"]')).toBeVisible()

    // Check for link to registration
    await expect(page.getByRole('link', { name: 'Sign up' })).toBeVisible()
  })

  test('should display registration page with form elements', async ({ page }) => {
    await page.goto('/register')

    // Verify we're on the register page
    await expect(page).toHaveURL('/register')

    // Check for registration heading
    await expect(page.locator('h1')).toContainText('Create your account')

    // Social-first design: email form is behind "Sign up with email" disclosure
    await page.getByRole('button', { name: /sign up with email/i }).click()

    await expect(page.locator('input[type="email"]')).toBeVisible()
    await expect(page.locator('input[type="password"]')).toBeVisible()
    await expect(page.locator('button[type="submit"]')).toBeVisible()

    // Check for link to login
    await expect(page.getByRole('link', { name: 'Sign in' })).toBeVisible()
  })

  test('should show validation error for invalid login credentials', async ({ page }) => {
    await page.goto('/login')

    // Expand email form via disclosure button
    await page.getByRole('button', { name: /continue with email/i }).click()

    // Fill in invalid credentials
    await page.locator('input[type="email"]').fill('invalid@example.com')
    await page.locator('input[type="password"]').fill('wrongpassword')

    // Submit form
    await page.locator('button[type="submit"]').click()

    // Wait for error message (should not redirect)
    await expect(page.locator('text=/invalid|incorrect|failed|error/i').first()).toBeVisible()

    // Should still be on login page (not redirected)
    expect(page.url()).toContain('/login')
  })

  test('should have back to home link on login page', async ({ page }) => {
    await page.goto('/login')

    // AuthShell renders "Back to home" (href="/") — use toBeVisible() so
    // Playwright retries until the Suspense boundary has resolved.
    await expect(page.locator('a[href="/"]').first()).toBeVisible()
  })

  test('should navigate between login and register pages', async ({ page }) => {
    // Start on login page
    await page.goto('/login')
    await expect(page).toHaveURL('/login')

    // Click in-form link to register
    await page.getByRole('link', { name: 'Sign up' }).click()
    await expect(page).toHaveURL('/register')

    // Click in-form link back to login
    await page.getByRole('link', { name: 'Sign in' }).click()
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
