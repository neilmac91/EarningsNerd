import type { LegalReadiness } from '@/features/legal/api/legal-api'

/** A hypothetical released operator, for tests of behavior after the readiness gate. */
export const legalReady: LegalReadiness = {
  collection_available: true,
  checkout_available: true,
  marketing_available: false,
  terms_version: '2026-10-24',
  eligibility_version: '2026-10-24',
  operator: { legal_name: 'Example operator', postal_address: 'Example address', country: 'CH', contact_email: 'legal@example.test' },
}

export const readyLegalHook = { readiness: legalReady, loading: false, recheck: async () => legalReady }
