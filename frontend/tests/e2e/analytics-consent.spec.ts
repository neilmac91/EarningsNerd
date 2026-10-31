import { test, expect, type Page } from '@playwright/test'
import { API_ORIGIN } from './fixtures/filing3Api'

/**
 * Vercel Web Analytics loads only after the visitor allows analytics (D-046), as the consent bar says.
 *
 * In a production build the library's <Analytics> appends `<script src="/_vercel/insights/script.js">`, and on
 * Vercel that script posts what it counts under /_vercel/insights/; its development build loads
 * https://va.vercel-scripts.com/v1/script.debug.js instead. `next start` serves no /_vercel route, so the request
 * answers 404 here, and it is still a request: before D-046 every page load made it, whatever the visitor chose.
 *
 * A first visit requests nothing from either place and carries no script tag; "Allow analytics" on the bar loads it
 * on that page, and the next page loads it at once; "Essential only" loads nothing, on that page or the next. The
 * unit cases (privateAnalytics.spec.tsx, telemetryPrivacy.spec.tsx) hold the component; this holds the built app,
 * whichever component would mount the script. CI runs e2e with no backend
 * (lessons/test-e2e-runs-without-backend.md): the API origin is answered in the browser, as a guest.
 */

const fromVercel = (url: string) => url.includes('/_vercel/insights') || url.includes('va.vercel-scripts.com')
const SCRIPT = 'script[data-sdkn^="@vercel/analytics"], script[src*="/_vercel/insights"], script[src*="va.vercel-scripts.com"]'
const bar = (page: Page) => page.getByRole('region', { name: 'Cookie consent' })

/** Opens /pricing as a first-time guest and returns the Vercel requests the page makes from then on. */
async function firstVisit(page: Page, baseURL: string) {
  const cors = { 'access-control-allow-origin': new URL(baseURL).origin, 'access-control-allow-credentials': 'true' }
  await page.route((url) => url.origin === API_ORIGIN, (route) =>
    new URL(route.request().url()).pathname === '/api/auth/me'
      ? route.fulfill({ status: 401, headers: cors, json: { detail: 'Not authenticated' } })
      : route.fulfill({ status: 404, headers: cors, json: { detail: 'Not found' } }),
  )
  const requests: string[] = []
  page.on('request', (request) => {
    if (fromVercel(request.url())) requests.push(request.url())
  })
  await page.goto('/pricing')
  // The bar mounts after hydration, in the pass that would mount the analytics too.
  await expect(bar(page)).toBeVisible()
  return requests
}

test.use({ viewport: { width: 1440, height: 900 } })

test('a first visit requests no Vercel analytics; "Allow analytics" loads it there and on the next page', async ({ page, baseURL }) => {
  const requests = await firstVisit(page, baseURL!)
  await page.waitForLoadState('networkidle')
  expect(requests).toEqual([])
  await expect(page.locator(SCRIPT)).toHaveCount(0)

  await bar(page).getByRole('button', { name: 'Allow analytics' }).click()
  await expect(page.locator(SCRIPT)).toHaveCount(1)
  await expect.poll(() => requests.map((url) => new URL(url).pathname)).toContain('/_vercel/insights/script.js')

  requests.length = 0
  await page.reload()
  await expect(page.locator(SCRIPT)).toHaveCount(1)
  await expect.poll(() => requests.map((url) => new URL(url).pathname)).toContain('/_vercel/insights/script.js')
})

test('"Essential only" loads no Vercel analytics, on that page or the next', async ({ page, baseURL }) => {
  const requests = await firstVisit(page, baseURL!)
  await bar(page).getByRole('button', { name: 'Essential only' }).click()
  await expect(bar(page)).toBeHidden()
  await page.waitForLoadState('networkidle')
  await page.reload()
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  await page.waitForLoadState('networkidle')
  expect(requests).toEqual([])
  await expect(page.locator(SCRIPT)).toHaveCount(0)
})
