import type { Page } from '@playwright/test'

/** Synthetic release details: existing layout cases exercise their original, open form surfaces. */
export const legalReady = {
  collection_available: true,
  checkout_available: false,
  marketing_available: false,
  terms_version: '2026-10-24',
  eligibility_version: '2026-10-24',
  operator: { legal_name: 'Example operator', postal_address: 'Example address', country: 'CH', contact_email: 'legal@example.test' },
}

export async function answerLegalReadiness(page: Page, baseURL: string) {
  await page.route('**/api/legal/readiness', (route) => route.fulfill({
    status: 200,
    headers: { 'access-control-allow-origin': new URL(baseURL).origin, 'access-control-allow-credentials': 'true', 'cache-control': 'no-store' },
    json: legalReady,
  }))
}
