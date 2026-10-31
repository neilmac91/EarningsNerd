import { test, expect } from '@playwright/test'

test.describe('Home Page - Unauthenticated Users', () => {
  test('should display landing page with company search for unauthenticated users', async ({ page }) => {
    // Navigate to home page
    await page.goto('/')

    // Should stay on home page (not redirect)
    await expect(page).toHaveURL('/')

    // Should display hero section (default headline A; the experiment arms all name the filing)
    await expect(page.locator('h1')).toContainText(/filing|10-K/)

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
    await expect(footer.locator('a[href*="contact"]')).toBeVisible()
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

  // D-045: every section after the hero is one ruled row (features/marketing/components/LandingRow.tsx) numbered by
  // the `landing-row` CSS counter that app/page.tsx resets on <main>, so a section that renders nothing takes no
  // number. The number is a ::before box, which no DOM read returns resolved (getComputedStyle gives
  // `counter(landing-row, decimal-leading-zero)`, innerText nothing), so this reads the painted text from Chromium's
  // DOM snapshot: each row's number, in document order, at the default text size.
  test('numbers the landing rows 01, 02, … in document order with no gap', async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('section[data-landing-row]').first()).toBeVisible()
    const rows = await page.locator('section[data-landing-row]').count()
    // Anti-vacuity: with no backend the five rows that need no live data render (claims to pricing).
    expect(rows).toBeGreaterThanOrEqual(5)

    const cdp = await page.context().newCDPSession(page)
    const { documents, strings } = await cdp.send('DOMSnapshot.captureSnapshot', { computedStyles: [] })
    const { nodes, layout } = documents[0]
    const str = (index: number) => (index >= 0 ? strings[index] : '')
    // The number spans in document order, then the painted text of each one's ::before box.
    const spans = (nodes.attributes ?? []).flatMap((attributes, node) =>
      attributes.some((name, i) => i % 2 === 0 && str(name) === 'data-landing-row-number') ? [node] : [],
    )
    const numbers = spans.map((span) => {
      const before = (nodes.parentIndex ?? []).findIndex(
        (parent, node) => parent === span && str((nodes.nodeName ?? [])[node]) === '::before',
      )
      return layout.nodeIndex
        .flatMap((node, entry) => (node === before ? [str(layout.text[entry])] : []))
        .join('')
    })
    expect(spans).toHaveLength(rows)
    expect(numbers).toEqual(Array.from({ length: rows }, (_, i) => String(i + 1).padStart(2, '0')))
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
