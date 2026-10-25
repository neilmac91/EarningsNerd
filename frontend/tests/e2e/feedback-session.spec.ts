import { test, expect } from '@playwright/test'
import { answerApi, API_ORIGIN } from './fixtures/filing3Api'
import { answerLegalReadiness } from './fixtures/legalReady'

// Real client navigation and query ownership, with a synthetic session at the API boundary.
// No real account or feedback record is created.
for (const theme of ['light', 'dark']) {
  test(`feedback follows same-tab login and logout, ${theme}`, async ({ page, baseURL }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await answerApi(page, baseURL!, 'pro')
    await answerLegalReadiness(page, baseURL!)
    let signedIn = false
    const cors = {
      'access-control-allow-origin': new URL(baseURL!).origin,
      'access-control-allow-credentials': 'true',
    }
    await page.route(`${API_ORIGIN}/api/auth/me`, (route) => route.fulfill({
      status: signedIn ? 200 : 401,
      headers: cors,
      json: signedIn
        ? { id: 1, email: 'reader@example.test', full_name: 'Beta reader', is_pro: true, is_beta: true, is_admin: false, email_verified: true }
        : { detail: 'Not authenticated' },
    }))
    for (const action of ['login', 'logout']) {
      await page.route(`${API_ORIGIN}/api/auth/${action}`, (route) => {
        signedIn = action === 'login'
        return route.fulfill({ status: 200, headers: cors, json: { ok: true } })
      })
    }
    await page.addInitScript((theme) => {
      localStorage.setItem('theme', theme)
      localStorage.removeItem('en_session_active')
      localStorage.setItem('cookie_consent', JSON.stringify({
        essential: true, analytics: false, sessionRecording: false, timestamp: new Date().toISOString(),
      }))
    }, theme)
    await page.goto('/login?redirect=/terms')
    // A full reload would hide the original regression: Providers must survive this navigation.
    await page.evaluate(() => { document.documentElement.dataset.feedbackSessionTest = 'same-document' })
    const launcher = page.getByRole('button', { name: 'Send feedback', exact: true })
    await expect(launcher).toHaveCount(0)
    await page.getByRole('button', { name: 'Continue with email' }).click()
    await page.locator('input[type="email"]').fill('reader@example.test')
    await page.locator('input[type="password"]').fill('fixture-login-password')
    await page.locator('button[type="submit"]').click()
    await expect(page).toHaveURL('/terms')
    await expect(page.locator('html')).toHaveAttribute('data-feedback-session-test', 'same-document')
    await launcher.click()
    await page.getByRole('textbox', { name: 'Feedback message' }).fill('Private draft for this reader')
    await page.getByRole('dialog', { name: 'Send feedback' }).getByRole('button', { name: 'Close', exact: true }).click()
    await expect(launcher).toBeFocused()
    await page.getByRole('button', { name: 'Account menu' }).click()
    await page.getByRole('menuitem', { name: 'Log out', exact: true }).click()
    await expect(launcher).toHaveCount(0)
    await expect(page.getByRole('dialog', { name: 'Send feedback' })).toHaveCount(0)
  })
}
