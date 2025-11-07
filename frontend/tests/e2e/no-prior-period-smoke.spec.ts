import { test, expect } from '@playwright/test'

const targetUrl = process.env.NO_PRIOR_PERIOD_URL || process.env.PLAYWRIGHT_NO_PRIOR_PERIOD_URL

test('captures financials tab when no prior period is available', async ({ page }, testInfo) => {
  test.skip(!targetUrl, 'NO_PRIOR_PERIOD_URL environment variable is not configured')

  await page.goto(targetUrl!)

  const financialsTab = page.getByRole('button', { name: /financials/i })
  if (await financialsTab.isVisible()) {
    await financialsTab.click()
  }

  const tableLocator = page.locator('table')
  await expect(tableLocator).toBeVisible({ timeout: 10_000 })

  const screenshotPath = testInfo.outputPath('financials-no-prior-period.png')
  await page.screenshot({ path: screenshotPath })
})


