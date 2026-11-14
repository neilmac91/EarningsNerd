import type { Filing } from '@/features/filings/api/filings-api'

/** Foreign private issuer forms. A company that files any of them is a foreign private issuer, which is generally
 *  exempt from Section 16 insider reporting, so it has no Form 4s to show. */
export const FPI_FILING_TYPES = ['20-F', '40-F', '6-K']

/** Whether a company's listed filings mark it a foreign private issuer. */
export const isFpiFiler = (filings: Filing[] | undefined): boolean =>
  (filings ?? []).some((f) => FPI_FILING_TYPES.includes(f.filing_type))
