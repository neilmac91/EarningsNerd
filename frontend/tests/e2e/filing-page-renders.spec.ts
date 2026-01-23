import { test, expect } from '@playwright/test'

test.describe('Filing Page Rendering', () => {
  test('should render filing page and switch tabs without errors', async ({ page }) => {
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

    // Navigate to a filing page
    // Using a reliable ID if possible, or we might need to mock this in a real E2E env
    // For now assuming 932 exists as per previous test
    await page.goto('http://localhost:3000/filing/932')

    // Wait for the page to load
    await page.waitForLoadState('networkidle', { timeout: 15000 })

    // Check if page loaded successfully (has filing content)
    // If backend is not available, the page might show an error or subscription gate
    const hasHeading = await page.locator('h1').count() > 0

    // Skip test if backend is not available (no filing data)
    test.skip(!hasHeading, 'Filing page requires backend API - skipping in CI')

    // 1. Check Executive Summary (default tab)
    await expect(page.locator('h1')).toBeVisible()

    // Check if tabs are available (only if filing loaded successfully)
    const hasExecutiveSummaryTab = await page.getByRole('button', { name: 'Executive Summary' }).count() > 0
    if (hasExecutiveSummaryTab) {
      await expect(page.getByRole('button', { name: 'Executive Summary' })).toHaveClass(/text-emerald-700/)
    }
    
    // 2. Click Financials
    const financialsTab = page.getByRole('button', { name: 'Financials' })
    if (await financialsTab.isEnabled()) {
        await financialsTab.click()
        // Check for some content specific to financials
        // Either the table or the empty state or the "Analyst Notes" block
        const financialContent = page.locator('text=Analyst Notes').or(page.locator('table')).or(page.locator('text=No Financial Highlights Found'))
        await expect(financialContent).toBeVisible()
    }

    // 3. Click Risks
    const risksTab = page.getByRole('button', { name: 'Risks' })
    if (await risksTab.isEnabled()) {
        await risksTab.click()
        const riskContent = page.locator('text=Risk Factor').or(page.locator('text=No Risk Factors Found'))
        await expect(riskContent).first().toBeVisible()
    }

    // 4. Click MD&A
    const mdaTab = page.getByRole('button', { name: 'MD&A' })
    if (await mdaTab.isEnabled()) {
        await mdaTab.click()
        // MD&A is markdown, check for generic content container or empty state
        const mdaContent = page.locator('.prose').or(page.locator('text=No Management Discussion Found'))
        await expect(mdaContent).first().toBeVisible()
    }

    // Verify no critical runtime errors occurred during navigation
    const criticalErrors = errors.filter(
      (error) =>
        error.includes('this.clear is not a function') ||
        error.includes('TypeError') ||
        error.includes('Unhandled Runtime Error')
    )

    expect(criticalErrors).toHaveLength(0)
  })
})
