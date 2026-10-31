import type { LegalReadiness } from './api/legal-api'

/** Versions of the Terms and adult eligibility wording shipped with this frontend bundle. */
export const ACCOUNT_TERMS_VERSION = '2026-10-24'
export const ACCOUNT_ELIGIBILITY_VERSION = '2026-10-24'

export function isAccountPolicyCurrent(readiness: LegalReadiness | null): boolean {
  return readiness?.terms_version === ACCOUNT_TERMS_VERSION &&
    readiness?.eligibility_version === ACCOUNT_ELIGIBILITY_VERSION
}
