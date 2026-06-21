import { test, expect } from '@playwright/test'

/**
 * Opt-in PRODUCTION smoke check — proves the live site is serving current `main`, not a stale build.
 *
 * Why this exists: the "Ask this Filing" Copilot (and other frontend work) merged to `main` but a
 * stale Vercel production deployment kept serving an older build, so the feature was invisible on
 * earningsnerd.io even though it was "shipped". This catches that class of stale-deploy regression.
 *
 * Run against production (or any deployed URL):
 *   SMOKE_BASE_URL=https://earningsnerd.io npx playwright test prod-smoke
 *
 * It is skipped in the normal local/CI e2e run (which has no SMOKE_BASE_URL) so it never depends on
 * a local server or seeded data. The filing path defaults to the public Apple example (/filing/3),
 * which has a pre-generated summary; override with SMOKE_FILING_PATH if that id changes.
 */
const SMOKE_BASE_URL = process.env.SMOKE_BASE_URL
const FILING_PATH = process.env.SMOKE_FILING_PATH || '/filing/3'

test.describe('production smoke', () => {
  test.skip(!SMOKE_BASE_URL, 'Set SMOKE_BASE_URL (e.g. https://earningsnerd.io) to run the prod smoke check')

  test('a filing page serves a summary and the "Ask this Filing" Copilot launcher', async ({ page }) => {
    // new URL(...) avoids a double slash if SMOKE_BASE_URL has a trailing one; the explicit timeout
    // matches the assertion timeout below so navigation doesn't fail early at Playwright's 30s default.
    await page.goto(new URL(FILING_PATH, SMOKE_BASE_URL).toString(), {
      waitUntil: 'domcontentloaded',
      timeout: 45000,
    })

    // 1) The filing summary must load (rules out a broken page / wrong id before we blame the deploy).
    await expect(page.getByRole('heading', { name: /summary/i }).first()).toBeVisible({ timeout: 45000 })

    // 2) The Copilot launcher only renders when the deployed bundle contains the Copilot frontend
    //    (PR #350+). If this fails, production is serving a build older than the Copilot — i.e. a
    //    stale deploy, not a code problem.
    await expect(page.getByRole('button', { name: /ask this filing/i })).toBeVisible({ timeout: 20000 })
  })
})
